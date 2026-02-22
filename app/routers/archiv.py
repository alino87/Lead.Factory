"""
Dokumentenarchiv-Endpunkte.

GET /archiv/suche              – natürliche Sprachsuche
GET /archiv/dokumente          – alle Dokumente mit Filtern
GET /archiv/dokumente/{id}     – Einzeldokument mit allen Details
GET /archiv/termine            – alle offenen Termine/Fristen
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import require_api_key
from app.models.db_models import Behoerdenpost, Document, Termin
from app.services import archiv_service

router = APIRouter(prefix="/archiv", tags=["Archiv"])


@router.get("/suche")
def smart_suche(
    q: str = Query(..., min_length=2, description="Natürlichsprachliche Suchanfrage"),
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """
    Intelligente Volltextsuche.
    Beispiele: 'Rechnungen vom Finanzamt letzten Monat',
               'Alle offenen Mahnungen', 'Vertrag mit Telekom'
    """
    return archiv_service.suche(db, q, limit=limit, offset=offset)


@router.get("/dokumente")
def get_dokumente(
    kategorie: Optional[str] = None,
    prioritaet: Optional[str] = None,
    absender: Optional[str] = None,
    datum_von: Optional[str] = None,
    datum_bis: Optional[str] = None,
    text: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Dokumentenliste mit optionalen Filtern."""
    return archiv_service.suche_mit_filtern(
        db,
        text=text,
        kategorie=kategorie,
        prioritaet=prioritaet,
        absender_name=absender,
        datum_von=datum_von,
        datum_bis=datum_bis,
        limit=limit,
        offset=offset,
    )


@router.get("/dokumente/{doc_id}")
def get_dokument(
    doc_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Einzelnes Dokument mit allen verknüpften Daten."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")

    return {
        "id": doc.id,
        "filename": doc.filename,
        "archive_path": doc.archive_path,
        "kategorie": doc.kategorie,
        "prioritaet": doc.prioritaet,
        "absender_name": doc.absender_name,
        "absender_adresse": doc.absender_adresse,
        "empfaenger_name": doc.empfaenger_name,
        "datum": doc.datum,
        "betreff": doc.betreff,
        "zusammenfassung": doc.zusammenfassung,
        "antwort_entwurf": doc.antwort_entwurf,
        "antwort_erforderlich": doc.antwort_erforderlich,
        "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
        "termine": [
            {
                "titel": t.titel,
                "datum": t.datum,
                "uhrzeit": t.uhrzeit,
                "beschreibung": t.beschreibung,
                "ist_frist": t.ist_frist,
                "erledigt": t.erledigt,
            }
            for t in doc.termine
        ],
        "rechnungen": [
            {
                "id": r.id,
                "lieferant": r.lieferant,
                "betrag_brutto": r.betrag_brutto,
                "faelligkeitsdatum": r.faelligkeitsdatum,
                "bezahlt": r.bezahlt,
            }
            for r in doc.rechnungen
        ],
        "vertraege": [
            {
                "id": v.id,
                "vertragspartner": v.vertragspartner,
                "vertragsart": v.vertragsart,
                "naechste_kuendigung_bis": v.naechste_kuendigung_bis,
            }
            for v in doc.vertraege
        ],
        "behoerdenpost": [
            {
                "id": b.id,
                "behoerde": b.behoerde,
                "frist": b.frist,
                "erklaerung_einfach": b.erklaerung_einfach,
                "was_zu_tun": b.was_zu_tun,
                "erledigt": b.erledigt,
            }
            for b in doc.behoerdenpost
        ],
    }


@router.get("/termine")
def get_termine(
    nur_offene: bool = True,
    nur_fristen: bool = False,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Alle Termine und Fristen aus verarbeiteten Briefen."""
    q = db.query(Termin)
    if nur_offene:
        q = q.filter(Termin.erledigt == False)
    if nur_fristen:
        q = q.filter(Termin.ist_frist == True)

    termine = q.order_by(Termin.datum).all()
    return [
        {
            "id": t.id,
            "document_id": t.document_id,
            "titel": t.titel,
            "datum": t.datum,
            "uhrzeit": t.uhrzeit,
            "beschreibung": t.beschreibung,
            "ist_frist": t.ist_frist,
            "erledigt": t.erledigt,
        }
        for t in termine
    ]


@router.patch("/termine/{termin_id}/erledigt")
def termin_erledigt(
    termin_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
):
    termin = db.query(Termin).filter(Termin.id == termin_id).first()
    if not termin:
        raise HTTPException(status_code=404, detail="Termin nicht gefunden")
    termin.erledigt = True
    db.commit()
    return {"id": termin_id, "erledigt": True}


@router.patch("/behoerdenpost/{bp_id}/erledigt")
def behoerdenpost_erledigt(
    bp_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
):
    bp = db.query(Behoerdenpost).filter(Behoerdenpost.id == bp_id).first()
    if not bp:
        raise HTTPException(status_code=404, detail="Behördenpost nicht gefunden")
    bp.erledigt = True
    db.commit()
    return {"id": bp_id, "erledigt": True}
