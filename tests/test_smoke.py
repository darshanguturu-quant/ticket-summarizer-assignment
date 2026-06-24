"""Smoke tests. Run with:  pytest -q

NOTE: the suite is currently RED. That is expected — part of the task is to get
it green (and to add coverage for anything you fix or build).
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

AUTH = {"X-API-Key": "demo-key-alice"}


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
