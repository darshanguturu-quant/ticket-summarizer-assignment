# FINDINGS.md

## Bugs Found and Fixed

### Bug 1: JSONDecodeError on markdown-wrapped LLM output
- Symptom: ~1/3 of /summarize requests returned 502
- Root cause: MockProvider wraps ~33% of outputs in markdown code fences. _parse() called json.loads() on raw text without stripping the fence first
- Fix: Added regex in _parse() to detect and strip ```json ... ``` fences before parsing

### Bug 2: Wrong dictionary key when reading LLM result
- Symptom: /summarize always crashed with KeyError after a successful LLM call
- Root cause: main.py referenced result["points"] and cached["points"] but the LLM result dict uses "key_points" (matching the Pydantic model field name)
- Fix: Changed both occurrences to result["key_points"] and cached["key_points"]

### Bug 3: Rate limiter never resets count on window rollover
- Symptom: After the first rate-limit window expired, keys remained permanently throttled
- Root cause: ratelimit.py rolled the window start timestamp forward but kept the old count value instead of resetting to 0
- Fix: When window has elapsed, set state to (now, 1) and return True immediately

### Bug 4: Cache key ignored style and PROMPT_VERSION
- Symptom: Requesting "detailed" style returned a "brief" summary if the same ticket was cached. Bumping PROMPT_VERSION served stale summaries indefinitely
- Root cause: cache._key() hashed only the ticket text, so different styles and prompt versions collided to the same cache entry
- Fix: _key() now hashes f"{version}:{style}:{text}" so each (text, style, version) triple gets its own entry

### Bug 5: force_refresh not implemented
- Symptom: Passing force_refresh=True had no effect — stale cached result was always returned
- Root cause: main.py had a TODO comment but no code to skip the cache read
- Fix: When req.force_refresh is True, skip cache.get() and proceed directly to LLM call, then overwrite the cache entry with the fresh result

### Bug 6: POST /batch not implemented
- Symptom: Any call to /batch returned 501 Not Implemented
- Root cause: Endpoint was a stub raising HTTPException immediately
- Fix: Implemented full batch logic — rate limit consumed once per ticket, existing cache reused, per-item error isolation so one failure doesn't abort the batch, input order preserved via BatchItemResult.index

## Caching Trade-offs Not Implemented

### TTL / Expiry
Cache entries live forever. In production this means a ticket summarized months ago with an old model could still be served. Fix: use Redis with a TTL (e.g. 24 hours), or cachetools.TTLCache in-process.

### Memory Bounds
The in-memory dict grows without limit. A large enough volume of unique tickets will exhaust process memory. Fix: cap with an LRU eviction policy (cachetools.LRUCache with a max size).

### Concurrent Identical Requests (Cache Stampede)
Two simultaneous requests for the same uncached ticket both miss the cache, both call the LLM, and both write the same result. This wastes LLM calls and can cause inconsistency. Fix: a per-key asyncio.Lock (single-flight pattern) so only one request calls the LLM while others wait and then read the result.

## What I Would Do With More Time
- Add TTLCache with configurable expiry and LRU eviction to replace the unbounded dict
- Add a per-key asyncio.Lock in ResponseCache to prevent cache stampedes on concurrent identical requests
- Expose style as a per-item field in BatchRequest so callers can mix brief and detailed in one batch call
