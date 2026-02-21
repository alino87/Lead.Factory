from fastapi import APIRouter

from app.models.lead import LeadRequest, LeadResponse
from app.services import anthropic_service, gatekeeper

router = APIRouter()


@router.post("/enrich", response_model=LeadResponse)
async def enrich_lead(lead: LeadRequest) -> LeadResponse:
    is_valid, skip_reason = gatekeeper.validate(lead)
    if not is_valid:
        return LeadResponse(enrichment_skipped=True, skip_reason=skip_reason)

    result = await anthropic_service.enrich(lead.text)

    return LeadResponse(
        name=result.name,
        email=result.email,
        company=result.company,
        website=result.website,
        enriched=True,
        company_summary=result.company_summary,
        industry=result.industry,
        signal=result.signal,
        icebreaker_text=result.icebreaker_text,
        quality_score=result.quality_score,
    )
