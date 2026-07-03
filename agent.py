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

from dotenv import load_dotenv
from openai import OpenAI

from tools import TOOL_FUNCTIONS, TOOL_SCHEMAS

load_dotenv()

MODEL = "llama-3.3-70b-versatile"  # Groq free tier, supports tool calling
MAX_ITERATIONS = 10  # safety cap so a confused model can't loop forever

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ["GROQ_API_KEY"],
)

SYSTEM_PROMPT = (
    "You are a helpful assistant with tools. "
    "Use the calculator for any arithmetic instead of computing it yourself. "
    "Use get_current_datetime for anything involving today's date or the current time. "
    "Use web_search for current events or information you might not know. "
    "For general knowledge questions you already know, answer directly without tools."
)


def run_agent(messages: list) -> str:
    """Run the agent loop until the model produces a final text answer."""
    for _ in range(MAX_ITERATIONS):
        # THINK: the model decides — answer directly, or request tool calls?
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
        )
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
    print("Week 1 agent — tools: calculator, datetime, web_search (stub).")
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
