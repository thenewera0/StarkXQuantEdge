"""Thin OpenRouter chat client shared by the rationale and debate layers."""

from __future__ import annotations

import httpx

from ..config import settings

_URL = "https://openrouter.ai/api/v1/chat/completions"


class LLMUnavailable(RuntimeError):
    """Raised when OpenRouter is not configured or the call fails."""


def chat(messages: list[dict], *, temperature: float = 0.4, max_tokens: int = 300, model: str | None = None) -> str:
    """Single chat completion. Raises LLMUnavailable on any problem so callers can fall back."""
    if not settings.openrouter_api_key:
        raise LLMUnavailable("OPENROUTER_API_KEY not set")

    payload = {
        "model": model or settings.openrouter_model_strong,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }
    try:
        resp = httpx.post(_URL, json=payload, headers=headers, timeout=45.0)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise LLMUnavailable(str(exc)) from exc

    if isinstance(data, dict) and data.get("error"):
        raise LLMUnavailable(str(data["error"]))
    try:
        message = data["choices"][0]["message"]
        # Some models return text under 'content'; reasoning models may use 'reasoning'.
        content = message.get("content") or message.get("reasoning")
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMUnavailable(f"unexpected response shape: {exc}") from exc

    if not content or not content.strip():
        raise LLMUnavailable("empty completion")
    return content.strip()
