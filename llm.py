"""Shared LLM client — one place for the provider, model, and key loading."""

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = "openai/gpt-oss-120b"  # Groq free tier, strong tool calling

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ["GROQ_API_KEY"],
)

# Optional observability (Week 5): create a free account at smith.langchain.com,
# set LANGSMITH_API_KEY and LANGSMITH_TRACING=true in .env, and every LLM call
# (with inputs, outputs, latency, and errors) appears in the LangSmith dashboard.
if os.getenv("LANGSMITH_API_KEY"):
    from langsmith.wrappers import wrap_openai

    client = wrap_openai(client)
