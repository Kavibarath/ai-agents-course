"""Week 1 — a basic tool-calling agent, loop written by hand.

The agent loop: Think -> Act -> Observe -> Think again.

  1. THINK   : send the conversation + tool schemas to the LLM
  2. ACT     : if the LLM asks for tool calls, execute them
  3. OBSERVE : feed each tool's result back as a `tool` message
  4. repeat until the LLM answers in plain text

No framework — every step of the loop is visible below.
"""

import json
import os
import sys

from dotenv import load_dotenv
from openai import BadRequestError, OpenAI

from tools import TOOL_FUNCTIONS, TOOL_SCHEMAS, TOOLS_REQUIRING_APPROVAL

load_dotenv()

# Windows consoles default to a legacy codepage (cp1252) that can't print
# many characters web search results contain — force UTF-8.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MODEL = "openai/gpt-oss-120b"  # Groq free tier, strong tool calling
MAX_ITERATIONS = 10  # safety cap so a confused model can't loop forever

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ["GROQ_API_KEY"],
)

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


def _approve(name: str, args: dict) -> bool:
    """Show the user exactly what is about to run and ask for confirmation."""
    print(f"\n  [approval needed] The agent wants to run {name}:")
    body = args.get("code", json.dumps(args, indent=2))
    for line in body.splitlines():
        print(f"    | {line}")
    answer = input("  Run it? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def run_agent(messages: list) -> str:
    """Run the agent loop until the model produces a final text answer."""
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
                print("  [retry] model produced a malformed tool call, asking again...")
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
            print(f"  [tool] {name}({json.dumps(args)})")

            # Human-in-the-loop: dangerous tools need explicit approval.
            # The model wrote this code — never run it blind.
            if name in TOOLS_REQUIRING_APPROVAL and not _approve(name, args):
                result = "The user declined to run this. Ask them how to proceed."
                print("  [result] declined by user")
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
            print(f"  [result] {result}")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })
        # loop again: the model now THINKS about what it OBSERVED

    return "Stopped: hit the maximum number of tool-call iterations."


def main() -> None:
    print("Agent — tools: calculator, datetime, web_search (Tavily), run_python (with approval).")
    print("Type 'exit' to quit.\n")

    # Conversation history persists across turns (short-term memory, Week 3 preview)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

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

        messages.append({"role": "user", "content": user_input})
        answer = run_agent(messages)
        print(f"Agent: {answer}\n")


if __name__ == "__main__":
    main()
