# AI Agents Course — one project, built week by week

A single project that grows into a full research-assistant agent over 5 weeks.
**Current status: Week 1** — a basic tool-calling agent with a hand-written agent loop.

## The core idea (Week 1)

The agent loop is **Think → Act → Observe → Think again**. The LLM doesn't just
generate text — it generates a *decision*: answer directly, or call a tool (which
one, with what inputs)? We execute the tool, feed the result back, and the LLM
reasons again. `agent.py` implements this loop by hand so nothing is hidden.

## Setup

1. Get a **free** Groq API key (no card): https://console.groq.com → API Keys
2. Then:

```powershell
cd E:\agents-course
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # then paste your real key into .env
python agent.py
```

## Try these

| Prompt | Expected behavior |
|---|---|
| `What is 847 × 23?` | Calls `calculator` → answers 19481 (computed, not guessed) |
| `What's today's date?` | Calls `get_current_datetime` (not training data) |
| `What are the latest AI news?` | Chooses `web_search` — a stub until Week 2 |
| `What is the capital of France?` | **No tool call** — it decides tools aren't needed |

The `[tool]` / `[result]` lines printed between your question and the answer are
the Act/Observe steps of the loop, made visible.

## Roadmap

- **Week 1 (done):** agent loop + calculator, datetime, web-search stub
- **Week 2:** real web search (Tavily) + sandboxed code execution
- **Week 3:** short-term + long-term memory (ChromaDB)
- **Week 4:** multi-step orchestration with LangGraph (research assistant)
- **Week 5:** FastAPI + React frontend with reasoning trace, deployment
