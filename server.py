"""Week 5 — FastAPI backend: the same agent loop, streamed over a WebSocket.

Protocol (JSON messages):

  client -> server:
    {"type": "user_message", "content": "..."}
    {"type": "approval_response", "approved": true|false}

  server -> client:
    {"type": "memory_loaded",   "facts": [...]}      on connect
    {"type": "memory_recalled", "facts": [...]}      per-question recall
    {"type": "tool_call",   "name": ..., "args": {...}}
    {"type": "tool_result", "name": ..., "result": "...", "declined"?: true}
    {"type": "retry"}
    {"type": "approval_request", "name": ..., "args": {...}}
    {"type": "final", "content": "..."}
    {"type": "error", "message": "..."}

The agent loop is synchronous, so each turn runs in a worker thread; events
are marshalled back onto the event loop, and approvals block the worker on a
queue the WebSocket receiver feeds.

Run:  uvicorn server:app --reload --port 8000
"""

import asyncio
import queue
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import memory
from agent import SYSTEM_PROMPT, run_agent, trim_history
from llm import MODEL, client

REPORTS_DIR = Path(__file__).parent / "reports"
APPROVAL_TIMEOUT_SECONDS = 300

app = FastAPI(title="Agents Course — Week 5 server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev convenience; tighten for real deployments
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Reports API (the Week 4 research outputs)
# ---------------------------------------------------------------------------

@app.get("/api/reports")
def list_reports() -> list[str]:
    REPORTS_DIR.mkdir(exist_ok=True)
    return sorted((p.name for p in REPORTS_DIR.glob("*.md")), reverse=True)


@app.get("/api/reports/{name}")
def get_report(name: str) -> dict:
    if "/" in name or "\\" in name or ".." in name or not name.endswith(".md"):
        raise HTTPException(status_code=400, detail="bad report name")
    path = REPORTS_DIR / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="report not found")
    return {"name": name, "content": path.read_text(encoding="utf-8")}


# ---------------------------------------------------------------------------
# The agent WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def agent_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    event_loop = asyncio.get_running_loop()
    approvals: queue.Queue = queue.Queue()

    def send_from_thread(payload: dict) -> None:
        """Called from the agent worker thread; marshals onto the event loop."""
        asyncio.run_coroutine_threadsafe(websocket.send_json(payload), event_loop).result()

    # Session start: same memory bootstrap as the CLI
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    profile = memory.load_profile()
    if profile:
        messages[0]["content"] += (
            "\n\nFacts remembered about the user from past sessions:\n"
            + "\n".join(f"- {fact}" for fact in profile)
        )
    await websocket.send_json({"type": "memory_loaded", "facts": profile})

    def on_event(event: str, data: dict) -> None:
        send_from_thread({"type": event, **data})

    def approver(name: str, args: dict) -> bool:
        send_from_thread({"type": "approval_request", "name": name, "args": args})
        try:
            return bool(approvals.get(timeout=APPROVAL_TIMEOUT_SECONDS))
        except queue.Empty:
            return False

    def run_turn(user_input: str) -> None:
        nonlocal messages
        try:
            recalled = []
            if memory.total_count() > memory.PROFILE_LIMIT:
                recalled = [f for f in memory.recall(user_input) if f not in profile]
            if recalled:
                send_from_thread({"type": "memory_recalled", "facts": recalled})
                messages.append({
                    "role": "system",
                    "content": "Relevant facts remembered from past sessions:\n"
                               + "\n".join(f"- {fact}" for fact in recalled),
                })
            messages.append({"role": "user", "content": user_input})
            messages = trim_history(messages)
            answer = run_agent(messages, on_event=on_event, approver=approver)
            send_from_thread({"type": "final", "content": answer})
        except Exception as exc:  # noqa: BLE001 — surface anything to the UI
            try:
                send_from_thread({"type": "error", "message": str(exc)})
            except Exception:
                pass  # socket already gone

    turn_task = None
    try:
        while True:
            incoming = await websocket.receive_json()
            kind = incoming.get("type")
            if kind == "user_message":
                if turn_task and not turn_task.done():
                    await websocket.send_json(
                        {"type": "error", "message": "Agent is still working on the previous message."}
                    )
                    continue
                turn_task = event_loop.run_in_executor(None, run_turn, incoming.get("content", ""))
            elif kind == "approval_response":
                approvals.put(incoming.get("approved", False))
    except WebSocketDisconnect:
        pass
    finally:
        # Session over — distill durable facts, exactly like the CLI exit path
        try:
            facts = memory.extract_facts(messages, client, MODEL)
            memory.save_facts(facts)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Production: serve the built React app (frontend/dist) if it exists
# ---------------------------------------------------------------------------

_dist = Path(__file__).parent / "frontend" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
