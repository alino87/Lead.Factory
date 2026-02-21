import os, asyncio, logging, json, re
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field
from typing import Optional
import anthropic

logger = logging.getLogger("leadfactory")
logging.basicConfig(level=logging.INFO)

API_FACTORY_KEY = os.getenv("API_FACTORY_KEY")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

app = FastAPI(title="LeadFactory API")
api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)

SYSTEM_PROMPT = """
You are a data extraction engine. Output ONLY valid JSON.
Schema:
{
  "quality_score": int (0-100),
  "company_summary": "max 300 chars",
  "buying_signal": "specific trigger or null",
  "contact_angle": "specific approach or null"
}
Rules: No markdown, no explanations, no extra keys. If unsure, use null.
"""

class LeadRequest(BaseModel):
    text: str

class LeadResponse(BaseModel):
    quality_score: Optional[int] = None
    company_summary: Optional[str] = None
    buying_signal: Optional[str] = None
    contact_angle: Optional[str] = None
    meta_error: Optional[bool] = None
    meta_error_code: Optional[str] = None

def extract_json(text: str) -> dict:
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if not match:
        raise ValueError("No JSON found")
    return json.loads(match.group())

def call_anthropic_sync(text: str) -> dict:
    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            temperature=0,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text[:8000]}]
        )
        return extract_json(message.content[0].text)
    except json.JSONDecodeError:
        logger.error("JSON parse error")
        return {"meta_error": True, "meta_error_code": "LLM_PARSE"}
    except anthropic.RateLimitError:
        logger.error("Rate limit hit")
        return {"meta_error": True, "meta_error_code": "LLM_RATE_LIMIT"}
    except anthropic.AuthenticationError:
        logger.error("Auth error")
        return {"meta_error": True, "meta_error_code": "LLM_AUTH"}
    except Exception as e:
        logger.error(f"Unknown error: {e}")
        return {"meta_error": True, "meta_error_code": "LLM_UNKNOWN"}

async def validate_api_key(header_key: str = Security(api_key_header)):
    if header_key == API_FACTORY_KEY:
        return header_key
    raise HTTPException(status_code=401, detail="Unauthorized")

@app.post("/enrich", response_model=LeadResponse)
async def enrich(request: LeadRequest, token: str = Depends(validate_api_key)):
    result = await asyncio.to_thread(call_anthropic_sync, request.text)
    return LeadResponse(**result)

@app.get("/health")
async def health():
    return {"status": "operational"}
