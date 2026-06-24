"""Application configuration.

Values can be overridden with environment variables (see .env.example).
"""
import os


# Which LLM backend to use: "mock" (no API key needed) or "anthropic".
# Defaults to "mock" so the service runs locally with zero setup.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock")

# Used only when LLM_PROVIDER == "anthropic".
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# Version of the summarization prompt/logic. Bumping this means previously
# cached summaries were produced by an OLDER prompt and should no longer be
# served. (Try changing it to "v2" and watch what the cache does.)
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v1")

# Valid client API keys. In a real system these would live in a secrets store /
# database; hard-coded here to keep the exercise self-contained.
VALID_API_KEYS = {
    "demo-key-alice",
    "demo-key-bob",
}

# Per-API-key rate limit: at most RATE_LIMIT requests per RATE_WINDOW seconds.
RATE_LIMIT = int(os.getenv("RATE_LIMIT", "5"))
RATE_WINDOW_SECONDS = int(os.getenv("RATE_WINDOW_SECONDS", "60"))

# How many times to retry the LLM call on transient failure.
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
