# Ticket Summarizer — take-home exercise

This is a small FastAPI service that summarizes customer support tickets using an
LLM. A teammate handed it over half-finished. We've had **scattered reports that
it's flaky and that the summaries sometimes look off**, but nobody has sat down
and characterized what's actually wrong.

Treat it the way you'd treat any service that lands on your plate: get it into
good shape, then finish the part that isn't done.

**Time:** aim for ~3–4 hours. A smaller, well-reasoned, well-explained
submission beats a large rushed one. If you run out of time, write down what you
*would* have done.

**AI tools (Claude, ChatGPT, Copilot, etc.) are allowed and encouraged.** We use
them every day. We care how you use them and whether you stay in control of the
result — be ready to explain and defend every change you make, including
anything an assistant generated.

---

## What the service does

- `GET  /health` — liveness check.
- `POST /summarize` — summarize one ticket. Takes `{text, style, force_refresh}`,
  returns `{summary, key_points, sentiment, cached}`. Auth + caching + per-key
  rate limiting.
- `POST /batch` — *meant* to summarize many tickets at once. Currently a stub.

Auth is via header `X-API-Key`. Two demo keys exist: `demo-key-alice` and
`demo-key-bob`. There's a `style` field (`brief` | `detailed`) and a
`PROMPT_VERSION` in `app/config.py`.

Runs in **mock mode by default** — no API key, no network, no model needed.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Try it:

```bash
curl -s localhost:8000/health

curl -s -X POST localhost:8000/summarize \
  -H "X-API-Key: demo-key-alice" \
  -H "Content-Type: application/json" \
  -d '{"text":"My order arrived broken and Im angry","style":"brief"}'
```

Run the tests:

```bash
pytest -q
```

The test suite is currently **red**. That's expected.

---

## What we're asking for

**1. Get it healthy.** Find what's wrong, fix it, and for each issue write a
short note in `FINDINGS.md`: the symptom, the root cause, and why your fix is
correct. We're deliberately not giving you a checklist — figuring out what's
broken is part of the exercise.

**2. Finish `POST /batch`.** It takes `{"texts": [...]}` and should return a
per-ticket result. Requirements:
- Summarize every ticket; preserve input order.
- Reuse the existing cache and rate limiter — don't bypass them.
- Partial failure isn't total failure: one bad ticket returns its error for that
  item while the rest still succeed.
- How you apply the rate limit *within* a batch is your call — be ready to
  explain it.

**3. Make caching correct.** A cached summary must only ever be served when it
genuinely matches the request. Also: `force_refresh=true` must bypass and update
the cache, and changing `PROMPT_VERSION` must not serve summaries cached under
the old version. Note any caching concern you know about but didn't implement
(expiry, memory bounds, concurrent identical requests) in `FINDINGS.md`.

If something is genuinely ambiguous, make a reasonable assumption, write it
down, and move on — or ask us.

## What to hand back

1. Your modified code.
2. `FINDINGS.md` — issues you found (with root causes) and caching trade-offs.
3. Any tests you added or fixed.
4. 2–3 sentences on what you'd do with more time.

We'll then spend ~30 minutes together walking through your changes.
