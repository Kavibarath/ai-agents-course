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
