"""
Router für den Brief-Verarbeitungs-Agenten.

Endpunkte:
  POST /brief/verarbeiten   – Scann hochladen, Analyse erhalten
  POST /brief/base64        – Base64-kodiertes Bild übergeben
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Security, UploadFile
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel

from app.models.brief import BriefAnalyse
from app.services.brief_service import verarbeite_brief

logger = logging.getLogger("leadfactory.brief.router")

router = APIRouter(prefix="/brief", tags=["Briefverarbeitung"])

# -- Auth (gleiche Logik wie im Haupt-App) ---------------------------------
import os

API_FACTORY_KEY = os.getenv("API_FACTORY_KEY")
api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)


async def validate_api_key(header_key: str = Security(api_key_header)):
    if header_key == API_FACTORY_KEY:
        return header_key
    raise HTTPException(status_code=401, detail="Unauthorized")


# -- Erlaubte MIME-Typen ---------------------------------------------------
ERLAUBTE_TYPEN = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "application/pdf",
}

MAX_DATEIGROESSE = 20 * 1024 * 1024  # 20 MB


# -- Endpunkt 1: Datei-Upload ----------------------------------------------

@router.post(
    "/verarbeiten",
    response_model=BriefAnalyse,
    summary="Gescannten Brief analysieren (Datei-Upload)",
    description=(
        "Lädt ein gescanntes Bild oder PDF hoch und gibt eine vollständige Analyse zurück: "
        "Klassifizierung, Ordnervorschlag, Antwortentwurf, Termine und Zahlungsinfos."
    ),
)
async def brief_verarbeiten(
    datei: UploadFile = File(..., description="JPEG, PNG, WebP oder PDF (max. 20 MB)"),
    unternehmensname: Optional[str] = Form(
        None,
        description="Name des eigenen Unternehmens (für Kontext und Antwortentwurf)",
    ),
    token: str = Depends(validate_api_key),
):
    # Content-Type prüfen
    media_type = datei.content_type or "application/octet-stream"
    if media_type not in ERLAUBTE_TYPEN:
        raise HTTPException(
            status_code=415,
            detail=f"Nicht unterstützter Dateityp: {media_type}. Erlaubt: JPEG, PNG, WebP, PDF",
        )

    # Datei einlesen
    inhalt = await datei.read()
    if len(inhalt) > MAX_DATEIGROESSE:
        raise HTTPException(
            status_code=413,
            detail=f"Datei zu groß ({len(inhalt) // 1024} KB). Maximum: 20 MB",
        )
    if not inhalt:
        raise HTTPException(status_code=400, detail="Leere Datei hochgeladen")

    logger.info(
        f"Brief-Analyse gestartet: {datei.filename!r}, "
        f"{len(inhalt) // 1024} KB, Typ={media_type}"
    )

    # Verarbeitung in Thread auslagern (sync Claude-SDK)
    ergebnis = await asyncio.to_thread(
        verarbeite_brief, inhalt, media_type, unternehmensname
    )

    logger.info(
        f"Brief-Analyse abgeschlossen: Kategorie={ergebnis.kategorie}, "
        f"Priorität={ergebnis.prioritaet}"
    )
    return ergebnis


# -- Endpunkt 2: Base64-Input ----------------------------------------------

class BriefBase64Request(BaseModel):
    bild_base64: str
    media_type: str = "image/jpeg"
    unternehmensname: Optional[str] = None


class BriefBase64RequestFull(BaseModel):
    """Request-Body für Base64-kodierten Brief."""
    bild_base64: str
    media_type: str = "image/jpeg"
    unternehmensname: Optional[str] = None


@router.post(
    "/base64",
    response_model=BriefAnalyse,
    summary="Gescannten Brief analysieren (Base64)",
    description=(
        "Übergibt ein Base64-kodiertes Bild oder PDF und gibt eine vollständige Analyse zurück. "
        "Nützlich für Integrationen ohne Multipart-Upload."
    ),
)
async def brief_base64(
    anfrage: BriefBase64RequestFull,
    token: str = Depends(validate_api_key),
):
    if anfrage.media_type not in ERLAUBTE_TYPEN:
        raise HTTPException(
            status_code=415,
            detail=f"Nicht unterstützter Dateityp: {anfrage.media_type}",
        )

    try:
        import base64
        bild_bytes = base64.b64decode(anfrage.bild_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Ungültiger Base64-String")

    if not bild_bytes:
        raise HTTPException(status_code=400, detail="Leere Bilddaten")

    if len(bild_bytes) > MAX_DATEIGROESSE:
        raise HTTPException(
            status_code=413,
            detail=f"Bild zu groß ({len(bild_bytes) // 1024} KB). Maximum: 20 MB",
        )

    logger.info(
        f"Brief-Analyse (Base64) gestartet: "
        f"{len(bild_bytes) // 1024} KB, Typ={anfrage.media_type}"
    )

    ergebnis = await asyncio.to_thread(
        verarbeite_brief, bild_bytes, anfrage.media_type, anfrage.unternehmensname
    )

    logger.info(
        f"Brief-Analyse (Base64) abgeschlossen: "
        f"Kategorie={ergebnis.kategorie}, Priorität={ergebnis.prioritaet}"
    )
    return ergebnis
