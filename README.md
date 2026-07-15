# AI Agents Course — one project, built week by week

A single project that grows into a full research-assistant agent over 5 weeks.
**Current status: Week 5 (complete)** — web UI with a live reasoning trace, FastAPI + WebSockets
backend, optional LangSmith tracing, Docker + Render deployment.

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

## Research graph (Week 4)

`research.py` is a **graph-based agent** — the conceptual counterpart to `agent.py`'s
ReAct loop. We define the flow as explicit nodes and edges; the LLM only fills in
decisions at branch points:

```
START -> search -> read_pages --(readable pages?)--> synthesize -> save -> END
            ^                        |
            +---- refine_query <-----+  (no pages: LLM rewrites the query, max 2 rounds)
```

- **search** — Tavily, top 8 results
- **read_pages** — trafilatura extracts article text; unreadable pages are skipped
- **conditional edge** — zero readable pages routes back through `refine_query`
- **synthesize** — LLM writes a cited, structured markdown report from the sources only
- **save** — report lands in `reports/<date>-<topic>.md`

Run it standalone (`python research.py "your topic"`) or just ask the chat agent to
"research X" — the graph is registered as the `research_topic` tool, so the dynamic
agent delegates to the structured pipeline.

**ReAct vs graphs:** the chat agent decides everything per turn (flexible, opaque);
the graph guarantees search always precedes reading, capping retries and making every
step debuggable. Real systems use both — exactly like this project now does.

## Web UI (Week 5)

`server.py` exposes the SAME agent loop over a WebSocket — `run_agent()` takes an
`on_event` callback and an `approver`, so the CLI and the web UI share one loop with
different front ends. The React app (`frontend/`) renders:

- **Inline collapsible tool steps** — every Think → Act → Observe step appears live in
  the chat; expand a card to see the exact arguments and result
- **In-browser code approval** — `run_python` blocks server-side until you click
  Approve/Reject (the WebSocket receiver feeds a queue the agent thread waits on)
- **Memory indicator** — a 🧠 chip shows which long-term facts were loaded; per-question
  recalls appear inside the turn
- **Report viewer** — browse, read, and download the Week 4 research reports

Run it (two terminals):

```powershell
# terminal 1 — backend
venv\Scripts\uvicorn server:app --reload --port 8000
# terminal 2 — frontend (dev, proxies /ws and /api to :8000)
cd frontend; npm install; npm run dev    # open http://localhost:5173
```

Optional observability: set `LANGSMITH_TRACING=true` + `LANGSMITH_API_KEY` in `.env`
(free tier at smith.langchain.com) and every LLM call is traced in the dashboard.

## Deployment

`Dockerfile` is multi-stage: Node builds the frontend, then a Python image runs
uvicorn and serves the built UI itself. `render.yaml` deploys it on Render's free
tier — create the service from the repo, paste `GROQ_API_KEY` and `TAVILY_API_KEY`
in the dashboard. (Note: the free tier's disk is ephemeral, so long-term memory and
reports reset on redeploy.)

```powershell
docker build -t agent-lab .
docker run -p 8000:8000 --env-file .env agent-lab   # open http://localhost:8000
```

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
| `Research the latest trends in health data analytics` | Delegates to the LangGraph pipeline → cited markdown report saved in `reports/`, no further input needed |

The `[tool]` / `[result]` lines printed between your question and the answer are
the Act/Observe steps of the loop, made visible.

## Roadmap

- **Week 1 (done):** agent loop + calculator, datetime, web-search stub
- **Week 2 (done):** real web search (Tavily) + code execution with human approval
- **Week 3 (done):** short-term window + long-term ChromaDB memory across sessions
- **Week 4 (done):** LangGraph research pipeline with conditional retry branching
- **Week 5 (done):** React chat UI with live reasoning trace, in-browser code approval,
  report viewer, memory indicator; FastAPI + WebSockets; LangSmith hook; Docker + Render
