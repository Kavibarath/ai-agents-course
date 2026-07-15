"""Week 1 — a basic tool-calling agent, loop written by hand.

The agent loop: Think -> Act -> Observe -> Think again.

  1. THINK   : send the conversation + tool schemas to the LLM
  2. ACT     : if the LLM asks for tool calls, execute them
  3. OBSERVE : feed each tool's result back as a `tool` message
  4. repeat until the LLM answers in plain text

No framework — every step of the loop is visible below.
"""

import json
import sys

from openai import BadRequestError

import memory
from llm import MODEL, client
from tools import TOOL_FUNCTIONS, TOOL_SCHEMAS, TOOLS_REQUIRING_APPROVAL

# Windows consoles default to a legacy codepage (cp1252) that can't print
# many characters web search results contain — force UTF-8.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MAX_ITERATIONS = 10  # safety cap so a confused model can't loop forever
MAX_HISTORY_MESSAGES = 30  # short-term memory window (excluding the system prompt)

SYSTEM_PROMPT = (
    "You are a helpful assistant with tools. "
    "Use the calculator for simple arithmetic instead of computing it yourself. "
    "Use run_python for multi-step computation (projections, loops, date math) — "
    "write self-contained code that print()s its result. "
    "Use get_current_datetime for anything involving today's date or the current time. "
    "Use web_search for current events, statistics, or information you might not know. "
    "For questions needing current data AND computation, search first, then compute "
    "with the real numbers you found. "
    "For general knowledge questions you already know, answer directly without tools."
)


def _role(message) -> str:
    return message.get("role", "") if isinstance(message, dict) else getattr(message, "role", "")


def trim_history(messages: list) -> list:
    """Short-term memory window: keep the system prompt + the last N messages.

    The window must not start mid tool-exchange (a `tool` result whose
    matching assistant tool_calls message was trimmed away would be an API
    error), so advance the cut to the next user message.
    """
    if len(messages) <= MAX_HISTORY_MESSAGES + 1:
        return messages
    tail = messages[-MAX_HISTORY_MESSAGES:]
    while tail and _role(tail[0]) != "user":
        tail.pop(0)
    return [messages[0]] + tail


def _approve(name: str, args: dict) -> bool:
    """CLI approver: show the user exactly what will run, ask for confirmation."""
    print(f"\n  [approval needed] The agent wants to run {name}:")
    body = args.get("code", json.dumps(args, indent=2))
    for line in body.splitlines():
        print(f"    | {line}")
    answer = input("  Run it? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def _print_event(event: str, data: dict) -> None:
    """CLI event sink — the web server substitutes its own (WebSocket sends)."""
    if event == "tool_call":
        print(f"  [tool] {data['name']}({json.dumps(data['args'])})")
    elif event == "tool_result":
        print(f"  [result] {data['result']}")
    elif event == "retry":
        print("  [retry] model produced a malformed tool call, asking again...")


def run_agent(messages: list, on_event=None, approver=None) -> str:
    """Run the agent loop until the model produces a final text answer.

    on_event(event, data) receives the trace ("tool_call", "tool_result",
    "retry"); approver(name, args) -> bool gates dangerous tools. Defaults
    are the CLI implementations.
    """
    emit = on_event or _print_event
    approve = approver or _approve
    for _ in range(MAX_ITERATIONS):
        # THINK: the model decides — answer directly, or request tool calls?
        # Models occasionally emit malformed tool-call syntax; Groq rejects it
        # with a 400 'tool_use_failed'. It's transient, so retry a few times.
        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    tools=TOOL_SCHEMAS,
                )
                break
            except BadRequestError as exc:
                if "tool_use_failed" not in str(exc) or attempt == 2:
                    raise
                emit("retry", {})
        message = response.choices[0].message

        # No tool calls -> the model chose to answer. Loop ends.
        if not message.tool_calls:
            messages.append({"role": "assistant", "content": message.content})
            return message.content

        # The assistant turn (including its tool_calls) must go into history
        messages.append(message)

        # ACT + OBSERVE: run each requested tool, feed the result back
        for tool_call in message.tool_calls:
            name = tool_call.function.name
            # Parse, never string-match. Models sometimes send "" or "null"
            # instead of "{}" for no-argument tools — normalize to a dict.
            args = json.loads(tool_call.function.arguments or "{}") or {}
            emit("tool_call", {"name": name, "args": args})

            # Human-in-the-loop: dangerous tools need explicit approval.
            # The model wrote this code — never run it blind.
            if name in TOOLS_REQUIRING_APPROVAL and not approve(name, args):
                result = "The user declined to run this. Ask them how to proceed."
                emit("tool_result", {"name": name, "result": result, "declined": True})
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })
                continue

            try:
                result = TOOL_FUNCTIONS[name](**args)
            except Exception as exc:  # return errors to the model so it can recover
                result = f"Error running {name}: {exc}"
            emit("tool_result", {"name": name, "result": result})

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })
        # loop again: the model now THINKS about what it OBSERVED

    return "Stopped: hit the maximum number of tool-call iterations."


def main() -> None:
    print("Agent — tools: calculator, datetime, web_search (Tavily), run_python (with approval).")
    print("Long-term memory: on. Type 'exit' to quit.\n")

    # Short-term memory: the running history, windowed by trim_history()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Long-term memory, part 1: inject the user profile (all facts while the
    # store is small — semantic recall alone misses standing preferences)
    profile = memory.load_profile()
    if profile:
        print(f"  [memory] loaded {len(profile)} fact(s) from past sessions")
        messages[0]["content"] += (
            "\n\nFacts remembered about the user from past sessions:\n"
            + "\n".join(f"- {fact}" for fact in profile)
        )

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            break

        # Long-term memory, part 2: once the store outgrows the profile,
        # semantically recall facts relevant to this specific question
        recalled = []
        if memory.total_count() > memory.PROFILE_LIMIT:
            recalled = [f for f in memory.recall(user_input) if f not in profile]
        if recalled:
            for fact in recalled:
                print(f"  [memory] {fact}")
            messages.append({
                "role": "system",
                "content": "Relevant facts remembered from past sessions:\n"
                           + "\n".join(f"- {fact}" for fact in recalled),
            })

        messages.append({"role": "user", "content": user_input})
        messages = trim_history(messages)
        answer = run_agent(messages)
        print(f"Agent: {answer}\n")

    # Session over: distill it into durable facts for future sessions
    print("Saving memories...")
    facts = memory.extract_facts(messages, client, MODEL)
    memory.save_facts(facts)
    if facts:
        for fact in facts:
            print(f"  [saved] {fact}")
    else:
        print("  (nothing worth remembering this session)")


if __name__ == "__main__":
    main()
