"""
Buchhaltungs-Endpunkte.

GET  /buchhaltung/rechnungen          – alle Rechnungen (filter by Monat/Jahr)
GET  /buchhaltung/monatsbericht       – EÜR-Übersicht für Monat
GET  /buchhaltung/export.csv          – CSV-Export für Steuerberater
PATCH /buchhaltung/rechnungen/{id}/bezahlt – Rechnung als bezahlt markieren
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import require_api_key
from app.models.db_models import Rechnung
from app.services import buchhaltung_service

router = APIRouter(prefix="/buchhaltung", tags=["Buchhaltung"])


@router.get("/rechnungen")
def get_rechnungen(
    jahr: Optional[int] = None,
    monat: Optional[int] = None,
    unbezahlt: bool = False,
    ist_mahnung: bool = False,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Alle erfassten Rechnungen, optional gefiltert."""
    q = db.query(Rechnung)
    if jahr:
        from sqlalchemy import extract
        q = q.filter(extract("year", Rechnung.rechnungsdatum) == jahr)
    if monat:
        from sqlalchemy import extract
        q = q.filter(extract("month", Rechnung.rechnungsdatum) == monat)
    if unbezahlt:
        q = q.filter(Rechnung.bezahlt == False)
    if ist_mahnung:
        q = q.filter(Rechnung.ist_mahnung == True)

    rechnungen = q.order_by(Rechnung.faelligkeitsdatum).all()

    return [
        {
            "id": r.id,
            "lieferant": r.lieferant,
            "rechnungsnummer": r.rechnungsnummer,
            "rechnungsdatum": r.rechnungsdatum,
            "faelligkeitsdatum": r.faelligkeitsdatum,
            "betrag_netto": r.betrag_netto,
            "ust_satz": r.ust_satz,
            "betrag_brutto": r.betrag_brutto,
            "kategorie_buchhaltung": r.kategorie_buchhaltung,
            "vorsteuer_abzugsfaehig": r.vorsteuer_abzugsfaehig,
            "bezahlt": r.bezahlt,
            "ist_mahnung": r.ist_mahnung,
            "iban": r.iban,
            "document_id": r.document_id,
            "ueberfaellig": (
                r.faelligkeitsdatum < date.today() and not r.bezahlt
            ) if r.faelligkeitsdatum else False,
        }
        for r in rechnungen
    ]


@router.get("/monatsbericht")
def get_monatsbericht(
    jahr: int = date.today().year,
    monat: int = date.today().month,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """EÜR-Zusammenfassung für den angegebenen Monat."""
    q = db.query(Rechnung)
    from sqlalchemy import extract
    rechnungen = (
        q.filter(
            extract("year", Rechnung.rechnungsdatum) == jahr,
            extract("month", Rechnung.rechnungsdatum) == monat,
        )
        .all()
    )
    return {
        "periode": f"{jahr}-{monat:02d}",
        **buchhaltung_service.berechne_monatsbericht(rechnungen),
    }


@router.get("/export.csv", response_class=Response)
def export_csv(
    jahr: Optional[int] = None,
    monat: Optional[int] = None,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """EÜR als CSV-Datei herunterladen (für Steuerberater)."""
    q = db.query(Rechnung)
    if jahr:
        from sqlalchemy import extract
        q = q.filter(extract("year", Rechnung.rechnungsdatum) == jahr)
    if monat:
        from sqlalchemy import extract
        q = q.filter(extract("month", Rechnung.rechnungsdatum) == monat)

    rechnungen = q.order_by(Rechnung.rechnungsdatum).all()
    csv_content = buchhaltung_service.export_eur_csv(rechnungen)

    filename = f"eur_{jahr or 'alle'}_{monat or 'alle'}.csv"
    return Response(
        content=csv_content.encode("utf-8-sig"),  # BOM für Excel
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.patch("/rechnungen/{rechnung_id}/bezahlt")
def mark_bezahlt(
    rechnung_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Rechnung als bezahlt markieren."""
    rechnung = db.query(Rechnung).filter(Rechnung.id == rechnung_id).first()
    if not rechnung:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    rechnung.bezahlt = True
    db.commit()
    return {"id": rechnung_id, "bezahlt": True}
