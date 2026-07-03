# AI Agents Course — one project, built week by week

A single project that grows into a full research-assistant agent over 5 weeks.
**Current status: Week 2** — real web search (Tavily) + code execution with human-in-the-loop approval.

## The core idea (Week 1)

The agent loop is **Think → Act → Observe → Think again**. The LLM doesn't just
generate text — it generates a *decision*: answer directly, or call a tool (which
one, with what inputs)? We execute the tool, feed the result back, and the LLM
reasons again. `agent.py` implements this loop by hand so nothing is hidden.

## Tool safety (Week 2)

An agent that executes code it wrote itself can do destructive things. Two defenses here:
1. **Human-in-the-loop** — the agent loop shows you the exact code and asks `Run it? [y/N]`
   before executing anything from `TOOLS_REQUIRING_APPROVAL`.
2. **Process isolation + timeout** — code runs in a separate interpreter via `subprocess`
   with a 30-second cap, so an infinite loop can't hang the agent.

## Setup

1. Get a **free** Groq API key (no card): https://console.groq.com → API Keys
2. Get a **free** Tavily API key (1000 searches/month): https://app.tavily.com
3. Then:

```powershell
cd E:\agents-course
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # then paste your real keys into .env
python agent.py
```

## Try these

| Prompt | Expected behavior |
|---|---|
| `What is 847 × 23?` | Calls `calculator` → answers 19481 (computed, not guessed) |
| `What's today's date?` | Calls `get_current_datetime` (not training data) |
| `What are the latest AI news?` | Calls `web_search` → real headlines with source URLs |
| `What is the capital of France?` | **No tool call** — it decides tools aren't needed |
| `Current population of Malta, and at 3%/year growth, what is it in 10 years?` | **Chains tools**: `web_search` for the real number, then `run_python` (you approve the code) for the projection |

The `[tool]` / `[result]` lines printed between your question and the answer are
the Act/Observe steps of the loop, made visible.

## Roadmap

- **Week 1 (done):** agent loop + calculator, datetime, web-search stub
- **Week 2 (done):** real web search (Tavily) + code execution with human approval
- **Week 3:** short-term + long-term memory (ChromaDB)
- **Week 4:** multi-step orchestration with LangGraph (research assistant)
- **Week 5:** FastAPI + React frontend with reasoning trace, deployment
