from typing import Optional

import anthropic
from pydantic import BaseModel

from app.config import settings

_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """\
You are a B2B sales intelligence assistant. Given a free-form text describing a lead, \
you must first extract structured contact info, then enrich it.

## Extraction
Pull out whatever is present in the text:
- name: person's full name, or null
- email: email address, or null
- company: company name, or null
- website: company website/domain, or null

## Enrichment + No-Cringe Policy
Return null for icebreaker_text UNLESS you can write a specific, personalized opener \
grounded in a concrete, verifiable signal (e.g. recent funding, product launch, \
job posting, published article, industry award, or notable public event tied to the company).

A cringe icebreaker — always return null instead:
- Generic flattery: "Your company is doing amazing things"
- Obvious filler: "I noticed you work at [Company]"
- Anything that could be copy-pasted to any lead without changing a word

A good icebreaker:
- References one specific, recent signal
- Is 1–2 sentences, sounds human
- Is directly tied to the company or the contact's role

If the text is too thin to enrich (no real company context), return null for all \
enrichment fields and set quality_score between 0 and 30.

## Output Rules
- Be concise. company_summary ≤ 2 sentences.
- signal: one concrete recent event/fact, or null.
- quality_score: 0–100 reflecting how much real signal the input contains.\
"""


class _EnrichmentOutput(BaseModel):
    # Extracted
    name: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    website: Optional[str] = None
    # Enriched
    company_summary: Optional[str] = None
    industry: Optional[str] = None
    signal: Optional[str] = None
    icebreaker_text: Optional[str] = None
    quality_score: int = 0


async def enrich(text: str) -> _EnrichmentOutput:
    response = await _client.messages.parse(
        model=MODEL,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
        output_format=_EnrichmentOutput,
    )

    return response.parsed_output
