"""The web app's shared free AI: a pool of free-tier, OpenAI-compatible providers tried in order.

  request ──▶ Cerebras (1M tokens/day free) ──429──▶ Groq (free tier) ──429──▶ Workers AI (10k neurons/day)
                                                                            └──▶ all used up: PoolExhausted

Keys come from env vars. A provider without a key is skipped. Nothing here can create a bill: free tiers
return 429 instead of charging, and a provider that says its daily quota is gone is parked until the next
UTC day. Chat content is sent to these providers, and the web app's privacy note says so.
"""

import os
import threading
import time
from datetime import date

import httpx


class PoolExhausted(RuntimeError):
    pass


def _providers() -> list[dict]:
    cf = os.environ.get("CF_ACCOUNT_ID")
    return [p for p in [
        {"name": "cerebras", "base": "https://api.cerebras.ai/v1", "key": os.environ.get("CEREBRAS_API_KEY"),
         "models": ["gpt-oss-120b", "qwen-3-235b-a22b-instruct-2507", "llama-3.3-70b", "llama3.1-8b"]},
        {"name": "groq", "base": "https://api.groq.com/openai/v1", "key": os.environ.get("GROQ_API_KEY"),
         "models": ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]},
        {"name": "workers-ai", "base": f"https://api.cloudflare.com/client/v4/accounts/{cf}/ai/v1",
         "key": os.environ.get("CF_AI_TOKEN") if cf else None,
         "models": ["@cf/meta/llama-3.3-70b-instruct-fp8-fast", "@cf/meta/llama-3.1-8b-instruct-fp8-fast"]},
    ] if p["key"]]


_lock = threading.Lock()
_parked: dict[str, float] = {}  # provider name -> unix time it may be tried again
_model: dict[str, str] = {}  # provider name -> first preferred model it actually serves


def _pick_model(p: dict) -> str:
    if p["name"] not in _model:
        try:  # use the first preferred model the provider still offers (free-tier menus change)
            r = httpx.get(f"{p['base']}/models", headers={"Authorization": f"Bearer {p['key']}"}, timeout=10)
            have = {m["id"] for m in r.json().get("data", [])}
            _model[p["name"]] = next((m for m in p["models"] if m in have), p["models"][0])
        except (httpx.HTTPError, ValueError):
            return p["models"][0]
    return _model[p["name"]]


def _park(name: str, response: httpx.Response) -> None:
    text = response.text.lower()
    daily = "day" in text or "daily" in text or "quota" in text
    until = time.time() + (86_400 - time.time() % 86_400 if daily else 30)  # next UTC midnight, or 30 s
    with _lock:
        _parked[name] = until


def chat(messages: list[dict], tools: list[dict] | None = None) -> dict:
    """One model turn: {"message": <OpenAI assistant message>, "provider": name}."""
    tried = []
    for p in _providers():
        if _parked.get(p["name"], 0) > time.time():
            continue
        tried.append(p["name"])
        body = {"model": _pick_model(p), "messages": messages, "max_tokens": 2000, "temperature": 0.3}
        if tools:
            body["tools"] = tools
        try:
            r = httpx.post(f"{p['base']}/chat/completions", json=body, timeout=60,
                           headers={"Authorization": f"Bearer {p['key']}"})
        except httpx.HTTPError:
            continue  # network trouble: try the next provider
        if r.status_code in (429, 402, 503):
            _park(p["name"], r)
            continue
        if r.status_code >= 400:
            continue  # e.g. the model rejected the request shape; another provider may accept it
        msg = r.json()["choices"][0]["message"]
        return {"message": {k: v for k, v in msg.items() if k in ("role", "content", "tool_calls")},
                "provider": p["name"]}
    raise PoolExhausted("The free AI pool is used up for today" if tried or _providers() else
                        "The free AI isn't configured on this server")


def status() -> dict:
    now = time.time()
    return {"providers": [p["name"] for p in _providers()],
            "parked": {n: round(t - now) for n, t in _parked.items() if t > now}, "day": date.today().isoformat()}
