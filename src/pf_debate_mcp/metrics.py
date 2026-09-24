"""Hosted-mode guardrails and observability, applied to every tool by one decorator.

Budgets are global per-tool daily caps (not per IP: connector traffic arrives from Anthropic/OpenAI/Google
servers, so per-IP limits would throttle everyone together). Logs are one JSON line per call with the
tool, latency and outcome class only: never queries, URLs or card text.
"""

import functools
import json
import sys
import threading
import time
from collections import Counter
from datetime import date

from mcp.server.mcpserver.exceptions import ToolError

ENABLED = False  # turned on by hosted mode only; local installs have no limits and no logs
BUDGETS = {  # calls per UTC day, sized well under the free Space's CPU
    "fetch_source": 20_000, "cut_card": 40_000, "search_cards": 200_000, "get_card": 400_000,
    "export_doc": 20_000, "pf_guide": 200_000, "library_status": 50_000,
}
_lock = threading.Lock()
_day = {"date": None}
calls: Counter = Counter()
outcomes: Counter = Counter()
since = {"start": time.time(), "cards_cut": 0}


def _spend(tool: str) -> None:
    with _lock:
        today = date.today().isoformat()
        if _day["date"] != today:
            _day["date"] = today
            calls.clear()
        if calls[tool] >= BUDGETS.get(tool, 100_000):
            raise ToolError(f"The free server hit today's limit for {tool}. Try again tomorrow, "
                            "or install pf-debate locally (no limits): github.com/SujayGG/pf-debate-mcp")
        calls[tool] += 1


def observe(fn):
    """Budget + log wrapper for a tool function. functools.wraps keeps the signature the SDK reads."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if not ENABLED:
            return fn(*args, **kwargs)
        name = fn.__name__
        _spend(name)
        start, outcome = time.perf_counter(), "ok"
        try:
            return fn(*args, **kwargs)
        except ToolError as e:
            outcome = "rejected" if "REJECTED" in str(e) else "tool_error"
            raise
        except Exception as e:  # logged by class name only, then re-raised for the SDK to report
            outcome = type(e).__name__
            raise
        finally:
            with _lock:
                outcomes[f"{name}:{outcome}"] += 1
                if name == "cut_card" and outcome == "ok":
                    since["cards_cut"] += 1
            print(json.dumps({"tool": name, "ms": round((time.perf_counter() - start) * 1000),
                              "outcome": outcome}), file=sys.stderr, flush=True)

    return wrapper


def stats() -> dict:
    with _lock:
        return {"day": _day["date"], "calls_today": dict(calls), "outcomes_since_start": dict(outcomes),
                "verified_cards_cut_since_start": since["cards_cut"],
                "uptime_hours": round((time.time() - since["start"]) / 3600, 1)}
