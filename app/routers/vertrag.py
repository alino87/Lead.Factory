"""
Vertragsmanager-Endpunkte.

GET  /vertrag                  – alle Verträge
GET  /vertrag/fristen          – Verträge mit ablaufender Kündigungsfrist
GET  /vertrag/{id}             – Einzelvertrag
PATCH /vertrag/{id}/kuendigen  – Vertrag als gekündigt markieren
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import require_api_key
from app.models.db_models import Vertrag
from app.services import vertrag_service

router = APIRouter(prefix="/vertrag", tags=["Vertragsmanager"])


@router.get("/")
def get_vertraege(
    nur_aktive: bool = True,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Alle erfassten Verträge."""
    q = db.query(Vertrag)
    if nur_aktive:
        q = q.filter(Vertrag.aktiv == True)
    vertraege = q.order_by(Vertrag.naechste_kuendigung_bis).all()
    return [_vertrag_zu_dict(v) for v in vertraege]


@router.get("/fristen")
def get_ablaufende_fristen(
    tage_voraus: int = 60,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """
    Verträge, bei denen die Kündigungsfrist in den nächsten N Tagen abläuft.
    Standard: 60 Tage. Perfekt für wöchentliche Kontrolle.
    """
    from datetime import timedelta
    heute = date.today()
    warnschwelle = heute + timedelta(days=tage_voraus)

    vertraege = (
        db.query(Vertrag)
        .filter(
            Vertrag.aktiv == True,
            Vertrag.naechste_kuendigung_bis != None,
            Vertrag.naechste_kuendigung_bis >= heute,
            Vertrag.naechste_kuendigung_bis <= warnschwelle,
        )
        .order_by(Vertrag.naechste_kuendigung_bis)
        .all()
    )

    result = []
    for v in vertraege:
        d = _vertrag_zu_dict(v)
        d["tage_bis_kuendigung"] = (v.naechste_kuendigung_bis - heute).days
        result.append(d)

    return result


@router.get("/{vertrag_id}")
def get_vertrag(
    vertrag_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
):
    vertrag = db.query(Vertrag).filter(Vertrag.id == vertrag_id).first()
    if not vertrag:
        raise HTTPException(status_code=404, detail="Vertrag nicht gefunden")
    return _vertrag_zu_dict(vertrag)


@router.patch("/{vertrag_id}/kuendigen")
def vertrag_kuendigen(
    vertrag_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Vertrag als inaktiv (gekündigt) markieren."""
    vertrag = db.query(Vertrag).filter(Vertrag.id == vertrag_id).first()
    if not vertrag:
        raise HTTPException(status_code=404, detail="Vertrag nicht gefunden")
    vertrag.aktiv = False
    db.commit()
    return {"id": vertrag_id, "aktiv": False, "message": "Vertrag als gekündigt markiert"}


def _vertrag_zu_dict(v: Vertrag) -> dict:
    return {
        "id": v.id,
        "vertragspartner": v.vertragspartner,
        "vertragsart": v.vertragsart,
        "beginn": v.beginn,
        "ende": v.ende,
        "laufzeit_monate": v.laufzeit_monate,
        "kuendigungsfrist_tage": v.kuendigungsfrist_tage,
        "naechste_kuendigung_bis": v.naechste_kuendigung_bis,
        "monatliche_kosten": v.monatliche_kosten,
        "aktiv": v.aktiv,
        "notizen": v.notizen,
        "document_id": v.document_id,
    }
