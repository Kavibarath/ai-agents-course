"""Tools for the agent.

Each tool is two things:
1. A plain Python function (what WE execute).
2. A JSON schema definition (what the LLM SEES — it never runs code,
   it only emits a structured request to call one of these).
"""

import ast
import operator
import os
import subprocess
import sys
from datetime import datetime

from tavily import TavilyClient

# ---------------------------------------------------------------------------
# Tool 1: calculator
# ---------------------------------------------------------------------------

# Safe AST-based evaluator: only arithmetic, no eval(), no builtins.
_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError(f"Unsupported expression element: {ast.dump(node)}")


def calculator(expression: str) -> str:
    """Evaluate an arithmetic expression like '847 * 23' or '(3 + 4) ** 2'."""
    tree = ast.parse(expression, mode="eval")
    result = _eval_node(tree)
    # Render integers without a trailing .0
    if isinstance(result, float) and result.is_integer():
        result = int(result)
    return str(result)


# ---------------------------------------------------------------------------
# Tool 2: current date/time
# ---------------------------------------------------------------------------

def get_current_datetime() -> str:
    """Return the current local date and time."""
    now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S (%A)")


# ---------------------------------------------------------------------------
# Tool 3: web search (real since Week 2 — Tavily)
# ---------------------------------------------------------------------------

_tavily_client = None


def _get_tavily() -> TavilyClient:
    # Lazy init so importing tools.py never requires the key
    global _tavily_client
    if _tavily_client is None:
        _tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    return _tavily_client


def web_search(query: str) -> str:
    """Live web search via Tavily. Returns a short answer plus top sources."""
    response = _get_tavily().search(query, max_results=5, include_answer=True)

    parts = []
    if response.get("answer"):
        parts.append(f"Answer summary: {response['answer']}")
    for r in response.get("results", []):
        snippet = r.get("content", "")[:300]
        parts.append(f"- {r['title']} ({r['url']})\n  {snippet}")
    return "\n".join(parts) or "No results found."


# ---------------------------------------------------------------------------
# Tool 4: run Python code (Week 2) — DANGEROUS, requires human approval
# ---------------------------------------------------------------------------

def run_python(code: str) -> str:
    """Run agent-written Python in a subprocess with a timeout.

    The approval prompt lives in the agent loop (agent.py), not here —
    by the time this function is called, the human already said yes.
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return "Error: code timed out after 30 seconds."

    if proc.returncode != 0:
        return f"Error (exit code {proc.returncode}):\n{proc.stderr.strip()}"
    output = proc.stdout.strip()
    return output if output else "(code ran but printed nothing — use print() to output results)"


# Tools the agent loop must get human confirmation for before executing
TOOLS_REQUIRING_APPROVAL = {"run_python"}


# ---------------------------------------------------------------------------
# What the LLM sees: OpenAI-format tool schemas
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": (
                "Evaluate an arithmetic expression exactly. Use this for ANY math "
                "instead of computing in your head. Supports + - * / // % ** and parentheses."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "The arithmetic expression, e.g. '847 * 23'",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_datetime",
            "description": (
                "Get the current local date and time. Use this whenever the user asks "
                "about today's date, the current time, or anything relative to now."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for current information (news, prices, statistics, recent "
                "events, anything after your training data). Use this instead of guessing. "
                "Results include an answer summary and source URLs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_python",
            "description": (
                "Write and execute Python code for anything beyond simple arithmetic: "
                "projections, loops, data processing, date math, simulations. "
                "The code runs in a fresh interpreter — it must be self-contained and "
                "print() its results. Call this tool directly; never ask the user for "
                "permission in chat — the system shows them the code for approval "
                "automatically when you call it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Self-contained Python code that print()s its result",
                    }
                },
                "required": ["code"],
            },
        },
    },
]

# What WE dispatch on: tool name -> callable
TOOL_FUNCTIONS = {
    "calculator": calculator,
    "get_current_datetime": get_current_datetime,
    "web_search": web_search,
    "run_python": run_python,
}
