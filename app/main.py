"""Support-ticket summarization API.

Endpoints:
  GET  /health              liveness check
  POST /summarize           summarize one ticket   (auth + cache + rate limit)
  POST /batch               summarize many tickets   (auth + cache + per-ticket rate limit)

Auth: send header `X-API-Key: demo-key-alice` (or demo-key-bob).
"""
import asyncio

from fastapi import Depends, FastAPI, Header, HTTPException

from . import config
from .cache import ResponseCache
from .llm import get_provider
from .models import (
    BatchItemResult,
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


# ADDED: new helper function extracted so both /summarize and /batch can share
# the same logic (rate limit, cache, LLM call) instead of duplicating it.
async def _summarize_one(
    text: str, style: str, force_refresh: bool, api_key: str
) -> SummarizeResponse:
    # MOVED: rate limit check, moved here from the /summarize endpoint so it
    # also applies per-ticket when called from /batch.
    if not _limiter.allow(api_key):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # FIXED: force_refresh was previously ignored with just a TODO comment.
    if not force_refresh:
        # FIXED: cache.get() now passes style and PROMPT_VERSION, previously
        # only passed text.
        cached = _cache.get(text, style, config.PROMPT_VERSION)
        if cached is not None:
            return SummarizeResponse(
                summary=cached["summary"],
                # FIXED: was cached["points"] before, wrong key caused
                # KeyError crash.
                key_points=cached["key_points"],
                sentiment=cached["sentiment"],
                cached=True,
            )

    result = await _call_llm_with_retries(text, style)
    # FIXED: cache.set() now passes style and PROMPT_VERSION, previously only
    # passed text.
    _cache.set(text, style, config.PROMPT_VERSION, result)

    return SummarizeResponse(
        summary=result["summary"],
        # FIXED: was result["points"] before, wrong key caused KeyError crash.
        key_points=result["key_points"],
        sentiment=result["sentiment"],
        cached=False,
    )


@app.post("/summarize", response_model=SummarizeResponse)
async def summarize(
    req: SummarizeRequest,
    api_key: str = Depends(require_api_key),
) -> SummarizeResponse:
    # CHANGED: previously had all logic inline, now delegates to shared helper.
    return await _summarize_one(req.text, req.style, req.force_refresh, api_key)


# ADDED: whole implementation, was previously a stub that just raised
# HTTPException 501.
@app.post("/batch", response_model=BatchResponse)
async def batch(
    req: BatchRequest,
    api_key: str = Depends(require_api_key),
) -> BatchResponse:
    # Each ticket goes through the same per-key rate limiter as /summarize
    # (one allowance consumed per ticket), and the same cache. A failure on
    # one ticket (rate limit or LLM error) is recorded as that item's error
    # without aborting the rest of the batch.
    results: list[BatchItemResult] = []
    for index, text in enumerate(req.texts):
        # ADDED: try/except block, partial failure handling so one bad
        # ticket does not abort the whole batch.
        try:
            summary = await _summarize_one(text, "brief", False, api_key)
            results.append(BatchItemResult(index=index, ok=True, result=summary))
        # ADDED: except line, catches rate limit and LLM errors per ticket.
        except HTTPException as exc:
            results.append(BatchItemResult(index=index, ok=False, error=str(exc.detail)))

    return BatchResponse(results=results)
