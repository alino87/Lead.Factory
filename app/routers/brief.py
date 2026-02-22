"""
Router für den Brief-Verarbeitungs-Agenten.

Endpunkte:
  POST /brief/verarbeiten   – Scann hochladen, Analyse erhalten
  POST /brief/base64        – Base64-kodiertes Bild übergeben
"""

import asyncio
import base64
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.dependencies import require_api_key
from app.models.brief import BriefAnalyse
from app.pipeline import verarbeite_im_hintergrund
from app.services.brief_service import verarbeite_brief

logger = logging.getLogger("leadfactory.brief.router")

router = APIRouter(prefix="/brief", tags=["Briefverarbeitung"])

ERLAUBTE_TYPEN = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "application/pdf",
}

MAX_DATEIGROESSE = 20 * 1024 * 1024  # 20 MB


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
    background_tasks: BackgroundTasks,
    datei: UploadFile = File(..., description="JPEG, PNG, WebP oder PDF (max. 20 MB)"),
    unternehmensname: Optional[str] = Form(
        None,
        description="Name des eigenen Unternehmens (für Kontext und Antwortentwurf)",
    ),
    _: str = Depends(require_api_key),
):
    media_type = datei.content_type or "application/octet-stream"
    if media_type not in ERLAUBTE_TYPEN:
        raise HTTPException(
            status_code=415,
            detail=f"Nicht unterstützter Dateityp: {media_type}. Erlaubt: JPEG, PNG, WebP, PDF",
        )

    inhalt = await datei.read()
    if not inhalt:
        raise HTTPException(status_code=400, detail="Leere Datei hochgeladen")
    if len(inhalt) > MAX_DATEIGROESSE:
        raise HTTPException(
            status_code=413,
            detail=f"Datei zu groß ({len(inhalt) // 1024} KB). Maximum: 20 MB",
        )

    logger.info(f"Brief-Analyse gestartet: {datei.filename!r}, {len(inhalt) // 1024} KB, Typ={media_type}")

    ergebnis = await asyncio.to_thread(verarbeite_brief, inhalt, media_type, unternehmensname)

    logger.info(f"Brief-Analyse abgeschlossen: Kategorie={ergebnis.kategorie}, Priorität={ergebnis.prioritaet}")

    # Pipeline im Hintergrund starten – Antwort kommt sofort zurück
    background_tasks.add_task(verarbeite_im_hintergrund, ergebnis, datei.filename or "upload")

    return ergebnis


class BriefBase64Request(BaseModel):
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
    anfrage: BriefBase64Request,
    background_tasks: BackgroundTasks,
    _: str = Depends(require_api_key),
):
    if anfrage.media_type not in ERLAUBTE_TYPEN:
        raise HTTPException(
            status_code=415,
            detail=f"Nicht unterstützter Dateityp: {anfrage.media_type}",
        )

    try:
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

    logger.info(f"Brief-Analyse (Base64) gestartet: {len(bild_bytes) // 1024} KB, Typ={anfrage.media_type}")

    ergebnis = await asyncio.to_thread(verarbeite_brief, bild_bytes, anfrage.media_type, anfrage.unternehmensname)

    logger.info(f"Brief-Analyse (Base64) abgeschlossen: Kategorie={ergebnis.kategorie}, Priorität={ergebnis.prioritaet}")

    background_tasks.add_task(verarbeite_im_hintergrund, ergebnis, "base64-upload")

    return ergebnis
