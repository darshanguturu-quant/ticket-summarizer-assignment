# Code Analysis — app/ and tests/

This is a read-only analysis of the current codebase, written before any fixes were made.

## 1. What each file does

| File | Purpose |
|---|---|
| `app/main.py` | FastAPI app. `/health`, `/summarize` (auth → rate-limit → cache → LLM call w/ retries), `/batch` (stub, raises 501). |
| `app/models.py` | Pydantic request/response schemas: `SummarizeRequest/Response`, `BatchRequest/Response`, `BatchItemResult`. |
| `app/llm.py` | LLM provider abstraction — `MockProvider` (deterministic canned output, ~1/3 of the time wraps JSON in a markdown fence + prose to simulate real model noise) and `AnthropicProvider` (real SDK call). `get_provider()` picks one based on config. |
| `app/cache.py` | Thread-safe in-memory `ResponseCache` keyed by SHA-256 hash of the ticket text only. |
| `app/config.py` | Env-driven settings: provider choice, API key, model name, `PROMPT_VERSION`, valid API keys, rate-limit params, retry count. |
| `app/ratelimit.py` | Fixed-window per-key rate limiter (`limit` requests per `window_seconds`). |
| `tests/test_smoke.py` | 4 smoke tests: health check, missing-auth 401, happy path, cache-hit-on-second-call. README states the suite is currently red by design. |
| `app/__init__.py`, `tests/__init__.py` | Empty package markers. |

## 2. Bugs visible from reading the code

- **Cache key ignores `style` and `PROMPT_VERSION`** (`app/cache.py:17`, used from `app/main.py:65`). The key is `sha256(text)` only.
  - Requesting the same ticket with `style="brief"` then `style="detailed"` returns the brief cached result for the second call — wrong content for the requested style.
  - Bumping `PROMPT_VERSION` keeps serving summaries produced under the old prompt version forever, since nothing about the version is part of the key or the stored value.

- **`MockProvider` output is sometimes unparseable JSON, and `_parse` doesn't handle it.** `app/llm.py:74-79`: for ~1/3 of inputs (`_stable_bucket(text, 3) == 0`), `raw` is `"Sure! Here's the summary:\n```json\n{...}\n```"` — not bare JSON. `_parse()` (`app/llm.py:33-35`) just does `json.loads(raw)` with no fence-stripping, so this raises `json.JSONDecodeError`. The exception propagates up, gets caught by `_call_llm_with_retries`'s broad `except Exception`, retries the same input (which deterministically fails the same way every time since the bucket is stable), exhausts retries, and returns a 502. This is likely the "flaky" / "summaries sometimes look off" behavior mentioned in the README — it's actually a hard failure ~33% of the time, not flakiness.

- **`force_refresh` is documented in the model but completely ignored.** `app/models.py:13` defines the field; `app/main.py:62-63` has a TODO comment but the code below it unconditionally checks the cache first regardless of `force_refresh`.

- **Rate limiter's fixed window never truly resets the count.** `app/ratelimit.py:25-28`: when the window elapses, it rolls `start` forward but keeps `count` unchanged (`self._state[key] = (now, count)`) instead of resetting it to 0. After the first window expires, every key is permanently rate-limited at whatever count it had, since `count` only ever increments and the reset path never zeroes it. Clients get permanently throttled after the first window rolls over.

## 3. What's missing / unfinished

- **`POST /batch`** — entirely unimplemented, raises `HTTPException(501)` (`app/main.py:98`). Per the README's spec it needs to: summarize all tickets, preserve order via `BatchItemResult.index`, reuse the existing cache/rate-limiter (not bypass them), and isolate per-item failures so one bad ticket doesn't sink the batch.

- **Caching correctness** — beyond the key bug above, the README explicitly flags (and doesn't require code for) cache expiry, memory bounds, and concurrent-identical-request de-duplication (no in-flight request coalescing — two simultaneous identical requests will both miss cache and both call the LLM).

- **`FINDINGS.md`** does not exist yet — the README requires one documenting symptom/root-cause/fix-rationale per issue plus caching trade-offs not implemented.

- **No tests** cover `/batch`, rate-limiting behavior, `force_refresh`, or the `PROMPT_VERSION` cache-invalidation case — all areas explicitly called out in the README as needing attention.
