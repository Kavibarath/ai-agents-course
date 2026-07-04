"""Week 3 — long-term memory: RAG over your own past conversations.

Flow:
  session end   -> LLM extracts durable facts -> embed -> ChromaDB (persistent)
  session start -> each user message queries ChromaDB -> relevant facts
                   are injected into the prompt

Short-term memory (the running `messages` list) lives in agent.py;
this module only handles memory that survives across sessions.
"""

import uuid
from datetime import datetime
from pathlib import Path

import chromadb

DB_PATH = str(Path(__file__).parent / "memory_db")

# Chroma's default embedding fn (all-MiniLM-L6-v2, local ONNX) uses L2 distance
# on normalized vectors: 0 = identical, ~2 = unrelated. Facts further than this
# from the query are noise — don't inject them.
MAX_DISTANCE = 1.5

# Up to this many facts are injected wholesale at session start (a "user
# profile"). Semantic recall alone fails for preferences: "How far is X from
# Y?" is embedding-space-unrelated to "The user prefers metric units" (measured
# distance ~2.0), yet the preference must influence the answer. Small store ->
# inject everything; recall() takes over once the store outgrows the profile.
PROFILE_LIMIT = 20

_collection = None


def _get_collection():
    # Lazy init: only touch the DB (and the embedding model) when first used
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=DB_PATH)
        _collection = client.get_or_create_collection("agent_memory")
    return _collection


def _text_of(message) -> tuple[str, str]:
    """Return (role, content) for dict messages and SDK message objects alike."""
    if isinstance(message, dict):
        return message.get("role", ""), message.get("content") or ""
    return getattr(message, "role", ""), getattr(message, "content", None) or ""


EXTRACT_PROMPT = (
    "Review this conversation transcript and extract durable facts worth remembering "
    "in FUTURE sessions: user preferences, personal details, ongoing projects, "
    "standing instructions. Rules:\n"
    "- One fact per line, no bullets or numbering.\n"
    "- Phrase in third person, e.g. 'The user prefers metric units.'\n"
    "- Skip trivia that only mattered in this conversation (one-off questions, results).\n"
    "- If nothing is worth remembering, reply with exactly: NONE"
)


def extract_facts(messages, llm_client, model: str) -> list[str]:
    """Ask the LLM to distill the session into facts worth keeping."""
    transcript = []
    for m in messages:
        role, content = _text_of(m)
        if role in ("user", "assistant") and content:
            transcript.append(f"{role}: {content}")
    if not transcript:
        return []

    response = llm_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": EXTRACT_PROMPT},
            {"role": "user", "content": "\n".join(transcript)},
        ],
    )
    text = (response.choices[0].message.content or "").strip()
    if text.upper() == "NONE":
        return []
    facts = [line.strip("-•* ").strip() for line in text.splitlines()]
    return [f for f in facts if f and f.upper() != "NONE"]


def save_facts(facts: list[str]) -> None:
    if not facts:
        return
    col = _get_collection()
    saved_at = datetime.now().isoformat(timespec="seconds")
    col.add(
        ids=[str(uuid.uuid4()) for _ in facts],
        documents=facts,
        metadatas=[{"saved_at": saved_at} for _ in facts],
    )


def total_count() -> int:
    return _get_collection().count()


def load_profile(limit: int = PROFILE_LIMIT) -> list[str]:
    """Most recent facts, newest last — injected at session start."""
    col = _get_collection()
    if col.count() == 0:
        return []
    data = col.get(include=["documents", "metadatas"])
    rows = sorted(
        zip(data["documents"], data["metadatas"]),
        key=lambda row: row[1].get("saved_at", ""),
    )
    return [doc for doc, _ in rows[-limit:]]


def recall(query: str, k: int = 3) -> list[str]:
    """Return up to k stored facts semantically relevant to the query."""
    col = _get_collection()
    if col.count() == 0:
        return []
    result = col.query(query_texts=[query], n_results=min(k, col.count()))
    docs = result["documents"][0]
    distances = result["distances"][0]
    return [doc for doc, dist in zip(docs, distances) if dist <= MAX_DISTANCE]
