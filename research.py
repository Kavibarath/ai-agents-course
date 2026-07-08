"""Week 4 — research assistant as an explicit LangGraph StateGraph.

The contrast with agent.py:
  - agent.py is a ReAct-style agent: the LLM decides everything dynamically,
    one tool call at a time. Flexible, but unpredictable.
  - This is a graph-based agent: WE define the flow structure (nodes + edges),
    and the LLM fills in decisions at specific points. Controlled, debuggable.

Graph:

    START -> search -> read_pages --(enough pages?)--> synthesize -> save -> END
                ^                        |
                |                        | no pages left to try
                +----- refine_query <----+   (max 2 search attempts)

The conditional edge after read_pages is the key idea: branching logic lives
in the graph, not in the model's head.

Run standalone:  python research.py "latest trends in health data analytics"
Or via the chat agent, which has this graph registered as a `research_topic` tool.
"""

import re
import sys
from datetime import date
from pathlib import Path
from typing import TypedDict

import trafilatura
from langgraph.graph import END, START, StateGraph

from llm import MODEL, client
from tools import _get_tavily

MAX_ATTEMPTS = 2   # search rounds before we give up refining
PAGES_WANTED = 3   # how many pages to read and synthesize from
MIN_CHARS = 800    # extraction shorter than this = page not really readable
PAGE_CHAR_CAP = 6000  # per-page cap so 3 pages fit comfortably in context

REPORTS_DIR = Path(__file__).parent / "reports"


class ResearchState(TypedDict):
    """The state that flows through the graph. Nodes return partial updates."""
    topic: str
    query: str          # current search query (refine_query rewrites it)
    results: list       # [{title, url}] from the last search
    pages: list         # [{title, url, text}] successfully read
    attempts: int       # search rounds used
    report: str
    output_path: str


# --------------------------------------------------------------------------
# Nodes — each is a plain function: state in, partial state update out
# --------------------------------------------------------------------------

def search(state: ResearchState) -> dict:
    print(f"  [graph:search] query: {state['query']!r}")
    response = _get_tavily().search(state["query"], max_results=8)
    results = [{"title": r["title"], "url": r["url"]} for r in response["results"]]
    print(f"  [graph:search] {len(results)} results")
    return {"results": results, "attempts": state["attempts"] + 1}


def read_pages(state: ResearchState) -> dict:
    """Fetch result URLs and extract the main article text until we have enough."""
    pages = list(state["pages"])  # keep pages from a previous round
    for r in state["results"]:
        if len(pages) >= PAGES_WANTED:
            break
        if any(p["url"] == r["url"] for p in pages):
            continue
        print(f"  [graph:read] {r['url']}")
        try:
            html = trafilatura.fetch_url(r["url"])
            text = trafilatura.extract(html) if html else None
        except Exception:
            text = None
        if text and len(text) >= MIN_CHARS:
            pages.append({**r, "text": text[:PAGE_CHAR_CAP]})
        else:
            print("  [graph:read]   skipped (couldn't extract enough text)")
    print(f"  [graph:read] have {len(pages)} readable page(s)")
    return {"pages": pages}


def route_after_reading(state: ResearchState) -> str:
    """The conditional edge: decide where the graph goes next."""
    if state["pages"] or state["attempts"] >= MAX_ATTEMPTS:
        return "synthesize"
    return "refine_query"


def refine_query(state: ResearchState) -> dict:
    """LLM decision at a branch point: rewrite the failing search query."""
    print("  [graph:refine_query] no readable pages — rewriting the query")
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{
            "role": "user",
            "content": (
                f"A web search for {state['query']!r} only returned pages whose text "
                f"could not be extracted. Write ONE alternative search query for "
                f"researching the topic {state['topic']!r}, favouring article-style "
                f"sources (blogs, news, reviews). Reply with only the query."
            ),
        }],
    )
    new_query = (response.choices[0].message.content or "").strip().strip('"')
    return {"query": new_query}


def synthesize(state: ResearchState) -> dict:
    print(f"  [graph:synthesize] writing report from {len(state['pages'])} page(s)")
    if state["pages"]:
        material = "\n\n---\n\n".join(
            f"SOURCE: {p['title']}\nURL: {p['url']}\n\n{p['text']}"
            for p in state["pages"]
        )
    else:  # both search rounds failed to yield readable pages — degrade gracefully
        material = (
            "No page text could be extracted. Only these search results are known:\n"
            + "\n".join(f"- {r['title']} ({r['url']})" for r in state["results"])
        )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You write structured markdown research reports. Use ONLY the "
                    "provided source material — no outside knowledge, no invented "
                    "facts. Structure: # title, date line, ## Executive Summary "
                    "(3-5 sentences), ## Key Findings (grouped by theme, cite the "
                    "source URL inline after each claim), ## Conclusion, ## Sources "
                    "(list every URL used). If the material is thin, say so honestly."
                ),
            },
            {
                "role": "user",
                "content": f"Topic: {state['topic']}\n\nSource material:\n\n{material}",
            },
        ],
    )
    return {"report": response.choices[0].message.content or ""}


def save(state: ResearchState) -> dict:
    slug = re.sub(r"[^a-z0-9]+", "-", state["topic"].lower()).strip("-")[:60]
    REPORTS_DIR.mkdir(exist_ok=True)
    path = REPORTS_DIR / f"{date.today().isoformat()}-{slug}.md"
    path.write_text(state["report"], encoding="utf-8")
    print(f"  [graph:save] {path}")
    return {"output_path": str(path)}


# --------------------------------------------------------------------------
# Graph wiring
# --------------------------------------------------------------------------

def build_graph():
    graph = StateGraph(ResearchState)
    graph.add_node("search", search)
    graph.add_node("read_pages", read_pages)
    graph.add_node("refine_query", refine_query)
    graph.add_node("synthesize", synthesize)
    graph.add_node("save", save)

    graph.add_edge(START, "search")
    graph.add_edge("search", "read_pages")
    graph.add_conditional_edges(
        "read_pages",
        route_after_reading,
        {"synthesize": "synthesize", "refine_query": "refine_query"},
    )
    graph.add_edge("refine_query", "search")  # the loop back
    graph.add_edge("synthesize", "save")
    graph.add_edge("save", END)
    return graph.compile()


def research(topic: str) -> str:
    """Run the full pipeline; returns the saved report's path."""
    final_state = build_graph().invoke({
        "topic": topic,
        "query": topic,
        "results": [],
        "pages": [],
        "attempts": 0,
        "report": "",
        "output_path": "",
    })
    return final_state["output_path"]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    topic = " ".join(sys.argv[1:]).strip() or input("Research topic: ").strip()
    print(f"Researching: {topic}")
    output = research(topic)
    print(f"\nDone. Report saved to: {output}")
