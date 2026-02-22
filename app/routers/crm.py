"""
CRM-Light Endpunkte.

GET /crm/kontakte            – alle Kontakte
GET /crm/kontakte/{id}       – Einzelkontakt mit Briefverlauf
GET /crm/kontakte/suche      – Kontaktsuche
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import require_api_key
from app.models.db_models import Document, Kontakt

router = APIRouter(prefix="/crm", tags=["CRM"])


@router.get("/kontakte")
def get_kontakte(
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Alle bekannten Kontakte, sortiert nach letztem Kontakt."""
    kontakte = db.query(Kontakt).order_by(Kontakt.letzter_kontakt.desc()).all()
    return [_kontakt_zu_dict(k) for k in kontakte]


@router.get("/kontakte/suche")
def suche_kontakte(
    q: str = Query(..., min_length=2, description="Name oder Firma"),
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Kontaktsuche nach Name oder Firma."""
    pattern = f"%{q}%"
    from sqlalchemy import or_
    kontakte = (
        db.query(Kontakt)
        .filter(or_(
            Kontakt.name.ilike(pattern),
            Kontakt.firma.ilike(pattern),
        ))
        .order_by(Kontakt.letzter_kontakt.desc())
        .all()
    )
    return [_kontakt_zu_dict(k) for k in kontakte]


@router.get("/kontakte/{kontakt_id}")
def get_kontakt(
    kontakt_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Einzelner Kontakt mit allen Briefen."""
    kontakt = db.query(Kontakt).filter(Kontakt.id == kontakt_id).first()
    if not kontakt:
        raise HTTPException(status_code=404, detail="Kontakt nicht gefunden")

    # Alle Dokumente von diesem Absender
    briefe = (
        db.query(Document)
        .filter(Document.absender_name.ilike(f"%{kontakt.name or kontakt.firma}%"))
        .order_by(Document.processed_at.desc())
        .limit(50)
        .all()
    )

    return {
        **_kontakt_zu_dict(kontakt),
        "briefe": [
            {
                "id": d.id,
                "datum": d.datum,
                "kategorie": d.kategorie,
                "betreff": d.betreff,
                "prioritaet": d.prioritaet,
                "processed_at": d.processed_at.isoformat() if d.processed_at else None,
            }
            for d in briefe
        ],
    }


def _kontakt_zu_dict(k: Kontakt) -> dict:
    return {
        "id": k.id,
        "name": k.name,
        "firma": k.firma,
        "email": k.email,
        "telefon": k.telefon,
        "adresse": k.adresse,
        "anzahl_briefe": k.anzahl_briefe,
        "erster_kontakt": k.erster_kontakt.isoformat() if k.erster_kontakt else None,
        "letzter_kontakt": k.letzter_kontakt.isoformat() if k.letzter_kontakt else None,
        "notizen": k.notizen,
    }
