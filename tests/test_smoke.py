"""Smoke tests. Run with:  pytest -q

NOTE: the suite is currently RED. That is expected — part of the task is to get
it green (and to add coverage for anything you fix or build).
"""
import pytest
from fastapi.testclient import TestClient

from app import config
from app import main as main_module
from app.main import app
from app.ratelimit import RateLimiter

client = TestClient(app)

AUTH = {"X-API-Key": "demo-key-alice"}


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Each test gets a clean rate-limit allowance so tests don't bleed
    into each other through the shared, module-level limiter."""
    main_module._limiter._state.clear()
    yield
    main_module._limiter._state.clear()


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_summarize_requires_api_key():
    r = client.post("/summarize", json={"text": "printer is on fire"})
    assert r.status_code == 401


def test_summarize_happy_path():
    r = client.post("/summarize", json={"text": "printer is on fire"}, headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert "summary" in body
    assert isinstance(body["key_points"], list)
    assert body["sentiment"] in {"positive", "neutral", "negative"}


def test_summarize_is_cached_on_second_call():
    payload = {"text": "this exact ticket should be cached the second time"}
    first = client.post("/summarize", json=payload, headers=AUTH)
    second = client.post("/summarize", json=payload, headers=AUTH)
    assert first.status_code == 200 and second.status_code == 200
    assert second.json()["cached"] is True


def test_force_refresh():
    payload = {"text": "force refresh should bypass the cache"}
    first = client.post("/summarize", json=payload, headers=AUTH)
    second = client.post(
        "/summarize", json={**payload, "force_refresh": True}, headers=AUTH
    )
    assert first.status_code == 200 and second.status_code == 200
    assert second.json()["cached"] is False


def test_style_cache_isolation():
    text = "style isolation should keep brief and detailed separate"
    brief = client.post("/summarize", json={"text": text, "style": "brief"}, headers=AUTH)
    detailed = client.post(
        "/summarize", json={"text": text, "style": "detailed"}, headers=AUTH
    )
    assert brief.status_code == 200 and detailed.status_code == 200
    assert detailed.json()["cached"] is False


def test_prompt_version_cache_invalidation(monkeypatch):
    text = "prompt version bump should invalidate the cache"
    first = client.post("/summarize", json={"text": text}, headers=AUTH)
    assert first.status_code == 200

    monkeypatch.setattr(config, "PROMPT_VERSION", "v2")

    second = client.post("/summarize", json={"text": text}, headers=AUTH)
    assert second.status_code == 200
    assert second.json()["cached"] is False


def test_batch_happy_path():
    texts = ["batch ticket one", "batch ticket two", "batch ticket three"]
    r = client.post("/batch", json={"texts": texts}, headers=AUTH)
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) == 3
    assert [item["index"] for item in results] == [0, 1, 2]
    assert all(item["ok"] for item in results)
    assert all(item["result"] is not None for item in results)


def test_batch_partial_failure(monkeypatch):
    bad_text = "this ticket will blow up"
    good_text = "this ticket will succeed"

    async def fake_summarize(text, style="brief"):
        if text == bad_text:
            raise RuntimeError("simulated provider failure")
        return {"summary": "ok", "key_points": ["a"], "sentiment": "neutral"}

    monkeypatch.setattr(main_module._provider, "summarize", fake_summarize)

    r = client.post("/batch", json={"texts": [bad_text, good_text]}, headers=AUTH)
    assert r.status_code == 200
    results = r.json()["results"]

    assert results[0]["index"] == 0
    assert results[0]["ok"] is False
    assert results[0]["error"] is not None

    assert results[1]["index"] == 1
    assert results[1]["ok"] is True
    assert results[1]["result"] is not None


def test_ratelimit_resets(monkeypatch):
    monkeypatch_limiter = RateLimiter(limit=2, window_seconds=60)
    monkeypatch.setattr(main_module, "_limiter", monkeypatch_limiter)
    key = "demo-key-bob"
    headers = {"X-API-Key": key}

    r1 = client.post("/summarize", json={"text": "rate limit call one"}, headers=headers)
    r2 = client.post("/summarize", json={"text": "rate limit call two"}, headers=headers)
    assert r1.status_code == 200 and r2.status_code == 200

    r3 = client.post("/summarize", json={"text": "rate limit call three"}, headers=headers)
    assert r3.status_code == 429

    # Manually push the window start into the past so it has "elapsed".
    start, count = monkeypatch_limiter._state[key]
    monkeypatch_limiter._state[key] = (start - 61, count)

    r4 = client.post("/summarize", json={"text": "rate limit call four"}, headers=headers)
    assert r4.status_code == 200
