# Agent Lab

A full-stack AI research agent with **visible reasoning**: a hand-written agent loop, real tools (web search, sandboxed code execution, multi-step research), memory that survives restarts, and a React chat UI that shows every step the agent takes — which tools it called, with what arguments, and what came back — not just the final answer.

Built without agent frameworks for the core loop, so every mechanism is explicit and readable. LangGraph is used only where it earns its place: orchestrating the multi-step research pipeline.

## Features

- **Hand-written agent loop** (Think → Act → Observe) — the LLM decides per question whether to answer directly or call tools; nothing is hidden behind a framework
- **Five tools**: safe calculator, date/time, live web search (Tavily), Python code execution, and a deep-research pipeline that writes cited markdown reports
- **Human-in-the-loop safety**: agent-written code is shown to you with Approve/Reject before it runs, in both the CLI and the browser
- **Two-tier memory**: a windowed conversation buffer per session, plus durable facts distilled by the LLM on exit and stored in ChromaDB — tell it once that you prefer metric units, and next week it answers in kilometres
- **Research graph**: an explicit LangGraph state machine (search → read pages → synthesize → save) with conditional retry branching
- **Web UI**: dark chat interface with collapsible tool-trace cards, in-browser code approval, a report viewer, and a memory indicator
- **Streaming backend**: FastAPI WebSocket that streams each loop event to the UI in real time
- **Optional observability**: set a LangSmith key and every LLM call is traced

## Architecture

```
┌───────────────┐  WebSocket   ┌──────────────┐        ┌──────────────────┐
│  React UI     │◄────────────►│  FastAPI     │───────►│  Agent loop      │
│  (Vite +      │  tool_call   │  server.py   │        │  agent.py        │
│   Tailwind)   │  tool_result │              │        │  Think→Act→      │
│               │  approval_*  │  /api/reports│        │  Observe loop    │
│               │  final       │              │        └────────┬─────────┘
└───────────────┘              └──────────────┘                 │
                                                    ┌───────────┴───────────┐
                                                    │        tools.py       │
                                                    │ calculator  datetime  │
                                                    │ web_search (Tavily)   │
                                                    │ run_python (subprocess│
                                                    │   + human approval)   │
                                                    │ research_topic ───────┼──► research.py
                                                    └───────────┬───────────┘    (LangGraph)
                                                                │
                                          ┌─────────────────────┴──────┐
                                          │  memory.py (ChromaDB)      │
                                          │  facts distilled on exit,  │
                                          │  injected on startup       │
                                          └────────────────────────────┘
```

The same `run_agent()` loop powers both interfaces: the CLI passes print/`input()` callbacks, the server passes WebSocket-send callbacks. LLM access goes through `llm.py` (Groq's OpenAI-compatible API, model `openai/gpt-oss-120b` — free tier).

## Tech stack

| Layer | Choice |
|---|---|
| LLM | `openai/gpt-oss-120b` on Groq (free tier, strong tool calling) |
| Agent loop | Hand-written Python (`agent.py`) |
| Research orchestration | LangGraph `StateGraph` (`research.py`) |
| Web search | Tavily API (free tier) |
| Page extraction | trafilatura |
| Long-term memory | ChromaDB + local ONNX MiniLM embeddings |
| Backend | FastAPI + WebSockets (uvicorn) |
| Frontend | React (Vite) + Tailwind CSS v4, react-markdown |
| Observability | LangSmith (optional) |
| Deployment | Docker (multi-stage) + Render |

## Getting started

**Prerequisites:** Python 3.12+, Node 20+, and two free API keys:
- Groq: https://console.groq.com → API Keys (no card required)
- Tavily: https://app.tavily.com (1000 searches/month free)

```powershell
git clone https://github.com/Kavibarath/ai-agents-course.git
cd ai-agents-course

# Backend
python -m venv venv
venv\Scripts\activate          # Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # then paste your real keys into .env

# Frontend
cd frontend
npm install
cd ..
```

### Run the web UI (development)

Two terminals:

```powershell
# 1 — backend
uvicorn server:app --reload --port 8000

# 2 — frontend with hot reload
cd frontend
npm run dev
```

Open **http://localhost:5173** (Vite proxies `/ws` and `/api` to the backend).

### Run the web UI (single server)

```powershell
cd frontend
npm run build
cd ..
uvicorn server:app --port 8000
```

Open **http://localhost:8000** — FastAPI serves the built UI, the API, and the WebSocket from one process.

### Run the CLI instead

```powershell
python agent.py
```

Same agent, same memory, tool trace printed inline, `exit` to quit.

### Run a research job directly

```powershell
python research.py "latest trends in health data analytics"
```

Saves a cited markdown report to `reports/` with no further input.

## Things to try

| Prompt | What you'll see |
|---|---|
| `What is 847 × 23?` | A `calculator` trace card → 19481, computed rather than guessed |
| `What's today's date?` | The datetime tool — not stale training data |
| `What are the latest AI news?` | Live Tavily search with source URLs |
| `What is the capital of France?` | **No tool call at all** — the agent decides tools aren't needed |
| `Write Python to find the 3 largest primes below 1000` | The code appears with **Approve & run / Reject** buttons; nothing executes without you |
| `Research the pros and cons of intermittent fasting` | The research graph runs (search → read → synthesize) and the report opens from the 📄 reports panel |
| `Remember that I prefer metric units` → restart → `How far is Valletta from Mdina?` | The 🧠 memory chip shows the recalled fact; the answer comes back in kilometres |

## How it works

### The agent loop

Each turn, the model receives the conversation plus JSON schemas describing the tools. It responds either with text (done) or with structured tool calls. The loop executes each call, appends the result as a `tool` message, and asks the model again — repeating until it answers in text (capped at 10 iterations). Tool errors are returned *to the model* as results so it can recover instead of crashing. Malformed tool calls (an occasional model failure mode) are retried up to 3 times.

### Tool safety

Code the agent writes is (1) gated behind explicit human approval — the loop blocks until you decide — and (2) executed in a separate interpreter via `subprocess` with a 30-second timeout, so an infinite loop can't hang the agent. The calculator similarly avoids `eval()` in favour of a whitelisted AST evaluator.

### Memory

Short-term memory is the running message list, trimmed to the last 30 messages (never cutting between a tool call and its result). Long-term memory: when a session ends, the LLM distills the transcript into durable third-person facts, which are embedded into a persistent ChromaDB store. On startup, stored facts are injected into the system prompt as a user profile.

Why inject rather than retrieve? Semantic search fails for preferences — the embedding distance between *"How far is Valletta from Mdina?"* and *"The user prefers metric units"* is ~2.0, effectively unrelated, yet the preference must shape the answer. So small stores are injected wholesale, and per-question semantic recall only takes over once the store outgrows the profile (the same design mem0 uses).

### The research graph

`research.py` is the architectural counterpart to the chat agent — a graph where *we* define the flow and the LLM fills in decisions at branch points:

```
START → search → read_pages ──(readable pages?)──► synthesize → save → END
           ▲                        │
           └──── refine_query ◄─────┘  (none readable: LLM rewrites the
                                        query; max 2 search rounds)
```

Unreadable pages (paywalls, JS-heavy sites) are skipped; if nothing is readable, the conditional edge routes back through an LLM query-rewrite. The synthesizer is restricted to the extracted source material and must cite URLs inline. The chat agent can delegate to this graph via the `research_topic` tool — a dynamic ReAct-style agent calling a structured pipeline, which is how production systems typically combine the two patterns.

### The WebSocket protocol

The server streams typed JSON events per turn: `tool_call`, `tool_result`, `approval_request` (the UI answers with `approval_response`), `memory_loaded` / `memory_recalled`, `retry`, and `final`. The UI renders these as live collapsible trace cards. The synchronous agent loop runs in a worker thread; approvals bridge back through a thread-safe queue.

## Project structure

```
agent.py        agent loop + CLI (event/approver callbacks shared with the server)
tools.py        tool implementations + JSON schemas + approval registry
memory.py       ChromaDB long-term memory (extract / save / profile / recall)
research.py     LangGraph research pipeline
llm.py          shared LLM client (Groq) + optional LangSmith wrapper
server.py       FastAPI: WebSocket streaming, reports API, static frontend
frontend/       React app (components: ToolStep, ApprovalCard, ReportsPanel, Markdown)
reports/        generated research reports (markdown)
memory_db/      ChromaDB store (gitignored)
```

## Configuration

`.env` (see `.env.example`):

| Variable | Required | Purpose |
|---|---|---|
| `GROQ_API_KEY` | yes | LLM calls |
| `TAVILY_API_KEY` | yes | Web search |
| `LANGSMITH_API_KEY` | no | Traces every LLM call to a LangSmith dashboard |
| `LANGSMITH_TRACING` | no | Set `true` alongside the key |

## Deployment

**Docker (anywhere):**

```bash
docker build -t agent-lab .
docker run -p 8000:8000 --env-file .env agent-lab
```

The multi-stage build compiles the React app with Node, then packages a slim Python image that serves everything on one port.

**Render:** the repo includes `render.yaml` — create a new Blueprint service pointing at this repo, paste `GROQ_API_KEY` and `TAVILY_API_KEY` in the dashboard, and deploy. The free tier works (cold starts after idle are normal).

## Limitations

- Sessions are single-user: each WebSocket connection gets its own conversation, but the long-term memory store is shared and unauthenticated
- Free-tier rate limits (Groq requests/min, Tavily searches/month) apply
- `run_python` executes on the host after your approval — isolation is a subprocess + timeout, not a container sandbox; review code before approving

---

*Built step by step as a learning project — the commit history walks from a bare agent loop to the full stack.*
