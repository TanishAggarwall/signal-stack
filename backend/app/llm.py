"""Free-tier LLM layer: Groq (OpenAI-compatible) and Google Gemini, with fallback + retry.

Every call asks for JSON. Callers must still validate the output: the model is never treated as a
source of facts, only as an analyst over text we collected ourselves.
"""
import json
import logging
import re
import threading
import time

import httpx

from .config import GEMINI_API_KEY, GEMINI_MODEL, GROQ_API_KEY, GROQ_MODEL, LLM_ORDER

log = logging.getLogger("llm")


class LLMError(RuntimeError):
    pass


_lock = threading.Lock()
_last_call: dict[str, float] = {}
_MIN_INTERVAL = {"groq": 2.2, "gemini": 4.5}  # stay under free-tier requests/minute
_cooldown_until: dict[str, float] = {}
usage = {"calls": 0, "by_provider": {}, "failures": 0}


def _throttle(provider: str):
    with _lock:
        wait = _last_call.get(provider, 0) + _MIN_INTERVAL.get(provider, 2) - time.time()
        if wait > 0:
            time.sleep(wait)
        _last_call[provider] = time.time()


def _call_groq(system: str, prompt: str, temperature: float, max_tokens: int) -> str:
    r = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={
            "model": GROQ_MODEL,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_completion_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        },
        timeout=120,
    )
    if r.status_code != 200:
        raise _HTTPFail(r.status_code, r.text[:500], r.headers.get("retry-after"))
    return r.json()["choices"][0]["message"]["content"]


def _call_gemini(system: str, prompt: str, temperature: float, max_tokens: int) -> str:
    r = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        headers={"x-goog-api-key": GEMINI_API_KEY},
        json={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
            },
        },
        timeout=120,
    )
    if r.status_code != 200:
        raise _HTTPFail(r.status_code, r.text[:500], r.headers.get("retry-after"))
    data = r.json()
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts if not p.get("thought"))


class _HTTPFail(Exception):
    def __init__(self, status, body, retry_after=None):
        super().__init__(f"HTTP {status}: {body}")
        self.status = status
        self.retry_after = retry_after


_PROVIDERS = {
    "groq": (_call_groq, lambda: bool(GROQ_API_KEY)),
    "gemini": (_call_gemini, lambda: bool(GEMINI_API_KEY)),
}


def parse_json(text: str):
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"(\{.*\}|\[.*\])", text, re.S)
        if m:
            return json.loads(m.group(1))
        raise


def complete_json(prompt: str, system: str = "", temperature: float = 0.2, max_tokens: int = 4096,
                  prefer: str | None = None) -> dict:
    """prefer: provider to try first (e.g. 'gemini' for large batch prompts: higher free token quota)."""
    system = (system or "You are a precise business-intelligence analyst.") + (
        "\nAlways answer with a single valid JSON object and nothing else."
    )
    if prefer is None and len(prompt) + len(system) > 14000:
        prefer = "gemini"  # Groq free tier is capped at 8k tokens/minute; big prompts go to Gemini first
    order = ([prefer] if prefer in LLM_ORDER else []) + [p for p in LLM_ORDER if p != prefer]
    errors = []
    for attempt in range(3):
        for name in order:
            fn, available = _PROVIDERS.get(name, (None, lambda: False))
            if not fn or not available():
                continue
            if _cooldown_until.get(name, 0) > time.time():
                continue
            try:
                _throttle(name)
                raw = fn(system, prompt, temperature, max_tokens)
                usage["calls"] += 1
                usage["by_provider"][name] = usage["by_provider"].get(name, 0) + 1
                return parse_json(raw)
            except _HTTPFail as e:
                errors.append(f"{name}: {e}")
                if e.status == 429 or e.status >= 500:
                    pause = float(e.retry_after) if (e.retry_after or "").replace(".", "").isdigit() else 20
                    _cooldown_until[name] = time.time() + min(pause, 90)
                log.warning("LLM %s failed: %s", name, e)
            except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError) as e:
                errors.append(f"{name}: {type(e).__name__}: {e}")
                log.warning("LLM %s failed: %s", name, e)
        # every provider failed or is cooling down: wait for the earliest cooldown, then retry
        soonest = min([t for t in _cooldown_until.values() if t > time.time()], default=time.time() + 5)
        time.sleep(min(max(soonest - time.time(), 3), 60))
    usage["failures"] += 1
    raise LLMError("All LLM providers failed: " + " | ".join(errors[-4:]))


def available_providers() -> list[str]:
    return [n for n in LLM_ORDER if n in _PROVIDERS and _PROVIDERS[n][1]()]
