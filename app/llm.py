"""LLM provider abstraction.

Two providers:
  - MockProvider:      no API key required, deterministic, used for local dev/tests.
  - AnthropicProvider: real calls via the `anthropic` SDK (optional dependency).

Both return a dict shaped like:
    {"summary": str, "key_points": list[str], "sentiment": str}

The output depends on BOTH the ticket text and the requested `style`, and is
tagged with the current prompt version (config.PROMPT_VERSION).
"""
import hashlib
import json
import re
from typing import Protocol

from . import config

_PROMPT = (
    "You are a support-ticket summarizer (prompt {version}). Summarize the ticket "
    "in the '{style}' style. Reply with a JSON object containing exactly these "
    "fields: summary (string), key_points (array of strings), sentiment (one of "
    "positive/neutral/negative). Ticket:\n\n{text}"
)


def _stable_bucket(text: str, mod: int) -> int:
    """Deterministic bucket for a string (builtin hash() is salted per-process)."""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest, 16) % mod


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _parse(raw: str) -> dict:
    """Turn the model's raw text reply into a dict.

    Real models sometimes wrap the JSON in a markdown code fence (optionally
    preceded/followed by prose) instead of returning bare JSON; strip the
    fence and use its contents if present.
    """
    match = _FENCE_RE.search(raw)
    if match:
        raw = match.group(1)
    return json.loads(raw)


class LLMProvider(Protocol):
    async def summarize(self, text: str, style: str = "brief") -> dict: ...


class MockProvider:
    """Returns canned-but-plausible output. Deterministic per (text, style, version).

    To mimic real models, roughly a third of inputs come back with the JSON
    wrapped in a markdown code fence plus a sentence of prose, instead of bare
    JSON.
    """

    async def summarize(self, text: str, style: str = "brief") -> dict:
        version = config.PROMPT_VERSION
        sentiment = "negative" if "angry" in text.lower() else "neutral"

        if style == "detailed":
            payload = {
                "summary": f"[{version}] Detailed summary of a {len(text)}-char ticket "
                           f"covering the customer's reported problem and context.",
                "key_points": [
                    "Customer described the issue in detail",
                    "Impact and context captured",
                    "Awaiting triage and follow-up",
                ],
                "sentiment": sentiment,
            }
        else:  # "brief"
            payload = {
                "summary": f"[{version}] Brief summary ({len(text)} chars).",
                "key_points": ["Issue reported by customer"],
                "sentiment": sentiment,
            }

        body = json.dumps(payload)

        if _stable_bucket(text, 3) == 0:
            raw = f"Sure! Here's the summary:\n```json\n{body}\n```"
        else:
            raw = body

        return _parse(raw)


class AnthropicProvider:
    def __init__(self) -> None:
        import anthropic  # imported lazily so mock mode needs no dependency

        if not config.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    async def summarize(self, text: str, style: str = "brief") -> dict:
        prompt = _PROMPT.format(version=config.PROMPT_VERSION, style=style, text=text)
        msg = self._client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text
        return _parse(raw)


def get_provider() -> LLMProvider:
    if config.LLM_PROVIDER == "anthropic":
        return AnthropicProvider()
    return MockProvider()
