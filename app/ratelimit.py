"""Fixed-window per-API-key rate limiter.

Each key is allowed RATE_LIMIT requests per RATE_WINDOW_SECONDS. When the
window elapses, the key should get a fresh allowance.
"""
import threading
import time
from typing import Dict, Tuple


class RateLimiter:
    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window = window_seconds
        # key -> (window_start_timestamp, count_in_window)
        self._state: Dict[str, Tuple[float, int]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Return True if the request is allowed, False if rate-limited."""
        now = time.time()
        with self._lock:
            start, count = self._state.get(key, (now, 0))

            if now - start > self.window:
                # Window has elapsed: start a fresh window with a clean count.
                self._state[key] = (now, 1)
                return True

            if count >= self.limit:
                return False

            self._state[key] = (start, count + 1)
            return True
