from pydantic import BaseModel
from typing import Optional


class LeadRequest(BaseModel):
    text: str


# Flat schema for Clay — all fields are top-level columns.
class LeadResponse(BaseModel):
    # Extracted from input text
    name: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    website: Optional[str] = None
    # Enrichment status
    enriched: bool = False
    enrichment_skipped: bool = False
    skip_reason: Optional[str] = None
    # AI-generated fields (null = not enough signal)
    company_summary: Optional[str] = None
    industry: Optional[str] = None
    signal: Optional[str] = None
    icebreaker_text: Optional[str] = None  # null enforced by No-Cringe policy
    quality_score: Optional[int] = None    # 0–100
