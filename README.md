# AI Agents Course — one project, built week by week

A single project that grows into a full research-assistant agent over 5 weeks.
**Current status: Week 3** — short-term + long-term memory (ChromaDB, RAG over past sessions).

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

## Memory (Week 3)

Two kinds, both hand-rolled:

- **Short-term** — the running `messages` list, windowed to the last 30 messages
  (`trim_history` in `agent.py`; the cut never lands mid tool-exchange).
- **Long-term** — `memory.py`. On exit, the LLM distills the session into durable
  facts ("The user prefers metric units"), embedded into a persistent ChromaDB store
  (`memory_db/`). On startup, stored facts are injected as a user profile; once the
  store outgrows `PROFILE_LIMIT`, per-question semantic recall takes over.

**Lesson learned the hard way:** pure semantic recall fails for preferences — the
embedding distance between "How far is Valletta from Mdina?" and "The user prefers
metric units" is ~2.0 (unrelated), yet the preference must shape the answer. That's
why small stores are injected wholesale and recall only supplements later — the same
design mem0 uses.

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
| Session 1: `Remember that I prefer metric units` → exit. Session 2: `How far is Valletta from Mdina?` | On exit: `[saved] The user prefers metric units.` On restart: `[memory] loaded 1 fact(s)` → answers in **km** without being told |

The `[tool]` / `[result]` lines printed between your question and the answer are
the Act/Observe steps of the loop, made visible.

## Roadmap

- **Week 1 (done):** agent loop + calculator, datetime, web-search stub
- **Week 2 (done):** real web search (Tavily) + code execution with human approval
- **Week 3 (done):** short-term window + long-term ChromaDB memory across sessions
- **Week 4:** multi-step orchestration with LangGraph (research assistant)
- **Week 5:** FastAPI + React frontend with reasoning trace, deployment
