"""Request and response schemas."""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class SummarizeRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Raw support ticket text to summarize.")
    # The summary should reflect the requested style. "detailed" produces a
    # longer summary with more key points than "brief".
    style: Literal["brief", "detailed"] = "brief"
    # When true, ignore any cached value and produce (and store) a fresh one.
    force_refresh: bool = False


class SummarizeResponse(BaseModel):
    summary: str
    key_points: List[str]
    sentiment: str  # one of: "positive", "neutral", "negative"
    cached: bool = False


class BatchRequest(BaseModel):
    texts: List[str] = Field(..., min_length=1)


class BatchItemResult(BaseModel):
    index: int
    ok: bool
    result: Optional[SummarizeResponse] = None
    error: Optional[str] = None


class BatchResponse(BaseModel):
    results: List[BatchItemResult]
