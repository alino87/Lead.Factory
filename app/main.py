import logging

from fastapi import FastAPI

from app.routers import brief, enrich

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="LeadFactory API",
    description="Lead-Qualifizierung und KI-gestützte Briefverarbeitung für KMU",
    version="2.0.0",
)

app.include_router(enrich.router)
app.include_router(brief.router)


@app.get("/health")
async def health():
    return {"status": "operational"}
