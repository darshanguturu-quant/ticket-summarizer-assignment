"""Support-ticket summarization API.

Endpoints:
  GET  /health              liveness check
  POST /summarize           summarize one ticket   (auth + cache + rate limit)
  POST /batch               summarize many tickets  (UNFINISHED — see README)

Auth: send header `X-API-Key: demo-key-alice` (or demo-key-bob).
"""
import asyncio

from fastapi import Depends, FastAPI, Header, HTTPException

from . import config
from .cache import ResponseCache
from .llm import get_provider
from .models import (
    BatchRequest,
    BatchResponse,
    SummarizeRequest,
    SummarizeResponse,
)
from .ratelimit import RateLimiter

app = FastAPI(title="Ticket Summarizer", version="0.1.0")

_provider = get_provider()
_cache = ResponseCache()
_limiter = RateLimiter(config.RATE_LIMIT, config.RATE_WINDOW_SECONDS)


def require_api_key(x_api_key: str = Header(default="")) -> str:
    if x_api_key not in config.VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key


async def _call_llm_with_retries(text: str, style: str = "brief") -> dict:
    last_err = None
    for _ in range(config.LLM_MAX_RETRIES + 1):
        try:
            return await _provider.summarize(text, style)
        except Exception as exc:  # transient model/network errors
            last_err = exc
            await asyncio.sleep(0.05)
    raise HTTPException(status_code=502, detail=f"LLM call failed: {last_err}")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/summarize", response_model=SummarizeResponse)
async def summarize(
    req: SummarizeRequest,
    api_key: str = Depends(require_api_key),
) -> SummarizeResponse:
    if not _limiter.allow(api_key):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # TODO(candidate, Part 3): honor req.force_refresh — when it is true, skip
    # the cache read below and overwrite the stored entry with a fresh summary.

    cached = _cache.get(req.text)
    if cached is not None:
        return SummarizeResponse(
            summary=cached["summary"],
            key_points=cached["key_points"],
            sentiment=cached["sentiment"],
            cached=True,
        )

    result = await _call_llm_with_retries(req.text, req.style)
    _cache.set(req.text, result)

    return SummarizeResponse(
        summary=result["summary"],
        key_points=result["key_points"],
        sentiment=result["sentiment"],
        cached=False,
    )


@app.post("/batch", response_model=BatchResponse)
async def batch(
    req: BatchRequest,
    api_key: str = Depends(require_api_key),
) -> BatchResponse:
    # TODO(candidate, Part 2): implement batch summarization.
    #
    # Expected behaviour (see README "Part 2"):
    #   - Summarize every ticket in req.texts.
    #   - Reuse the existing cache and rate limiter rather than bypassing them.
    #   - Partial failure must not sink the whole batch: if one ticket fails,
    #     return its error in that item and still return results for the rest.
    #   - Preserve input order in the response (use BatchItemResult.index).
    raise HTTPException(status_code=501, detail="Not implemented")
