"""A tiny in-memory cache so identical tickets don't re-hit the LLM.

Keyed on a stable hash of the input text. Process-local only; fine for the
exercise, would be Redis/memcached in production.
"""
import hashlib
import threading
from typing import Dict, Optional


class ResponseCache:
    def __init__(self) -> None:
        self._store: Dict[str, dict] = {}
        self._lock = threading.Lock()
#fixed
    @staticmethod
    def _key(text: str, style: str, version: str) -> str:
        digest_input = f"{version}\x00{style}\x00{text}"
        return hashlib.sha256(digest_input.encode("utf-8")).hexdigest()

    def get(self, text: str, style: str, version: str) -> Optional[dict]:
        with self._lock:
            return self._store.get(self._key(text, style, version))

    def set(self, text: str, style: str, version: str, value: dict) -> None:
        with self._lock:
            self._store[self._key(text, style, version)] = value
#fixed
