"""
Dashboard: Kompakter Überblick über den gesamten Stand.

GET /dashboard  – alles auf einen Blick
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import require_api_key
from app.models.db_models import Behoerdenpost, Document, Rechnung, Termin, Vertrag

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/")
def get_dashboard(
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """
    Übersicht: offene Rechnungen, ablaufende Vertragsfristen,
    offene Behördenpost, anstehende Termine, Monatsausgaben.
    """
    heute = date.today()

    # ── Dokumente ──────────────────────────────────────────────────────────
    total_dokumente = db.query(func.count(Document.id)).scalar()
    neue_heute = (
        db.query(func.count(Document.id))
        .filter(func.date(Document.processed_at) == heute)
        .scalar()
    )

    # ── Rechnungen ──────────────────────────────────────────────────────────
    offene_rechnungen = (
        db.query(Rechnung)
        .filter(Rechnung.bezahlt == False, Rechnung.ist_mahnung == False)
        .order_by(Rechnung.faelligkeitsdatum)
        .limit(10)
        .all()
    )
    ueberfaellige = [
        r for r in offene_rechnungen
        if r.faelligkeitsdatum and r.faelligkeitsdatum < heute
    ]
    summe_offen = round(
        sum(r.betrag_brutto or 0 for r in offene_rechnungen), 2
    )

    # ── Mahnungen ──────────────────────────────────────────────────────────
    offene_mahnungen = (
        db.query(func.count(Rechnung.id))
        .filter(Rechnung.ist_mahnung == True, Rechnung.bezahlt == False)
        .scalar()
    )

    # ── Vertragsfristen ────────────────────────────────────────────────────
    warnschwelle_60 = heute + timedelta(days=60)
    ablaufende_vertraege = (
        db.query(Vertrag)
        .filter(
            Vertrag.aktiv == True,
            Vertrag.naechste_kuendigung_bis != None,
            Vertrag.naechste_kuendigung_bis >= heute,
            Vertrag.naechste_kuendigung_bis <= warnschwelle_60,
        )
        .order_by(Vertrag.naechste_kuendigung_bis)
        .all()
    )

    # ── Behördenpost ───────────────────────────────────────────────────────
    offene_behoerdenpost = (
        db.query(Behoerdenpost)
        .filter(Behoerdenpost.erledigt == False)
        .order_by(Behoerdenpost.frist)
        .limit(5)
        .all()
    )

    # ── Termine/Fristen ────────────────────────────────────────────────────
    naechste_termine = (
        db.query(Termin)
        .filter(
            Termin.erledigt == False,
            Termin.datum >= heute.isoformat(),
        )
        .order_by(Termin.datum)
        .limit(5)
        .all()
    )

    # ── Monat Ausgaben ──────────────────────────────────────────────────────
    from sqlalchemy import extract
    rechnungen_monat = (
        db.query(Rechnung)
        .filter(
            extract("year", Rechnung.rechnungsdatum) == heute.year,
            extract("month", Rechnung.rechnungsdatum) == heute.month,
        )
        .all()
    )
    ausgaben_monat = round(
        sum(r.betrag_brutto or 0 for r in rechnungen_monat), 2
    )

    return {
        "datum": heute.isoformat(),

        "dokumente": {
            "gesamt": total_dokumente,
            "neu_heute": neue_heute,
        },

        "rechnungen": {
            "offene_summe_eur": summe_offen,
            "anzahl_offen": len(offene_rechnungen),
            "anzahl_ueberfaellig": len(ueberfaellige),
            "offene_mahnungen": offene_mahnungen,
            "top_offen": [
                {
                    "id": r.id,
                    "lieferant": r.lieferant,
                    "betrag_brutto": r.betrag_brutto,
                    "faelligkeitsdatum": r.faelligkeitsdatum,
                    "ueberfaellig": r.faelligkeitsdatum < heute if r.faelligkeitsdatum else False,
                }
                for r in offene_rechnungen[:5]
            ],
        },

        "vertraege": {
            "ablaufende_fristen": [
                {
                    "id": v.id,
                    "vertragspartner": v.vertragspartner,
                    "vertragsart": v.vertragsart,
                    "naechste_kuendigung_bis": v.naechste_kuendigung_bis,
                    "tage_verbleibend": (v.naechste_kuendigung_bis - heute).days,
                    "monatliche_kosten": v.monatliche_kosten,
                }
                for v in ablaufende_vertraege
            ],
        },

        "behoerdenpost": {
            "offen": [
                {
                    "id": b.id,
                    "behoerde": b.behoerde,
                    "betreff": b.betreff,
                    "frist": b.frist,
                    "tage_bis_frist": (b.frist - heute).days if b.frist else None,
                    "erklaerung_einfach": b.erklaerung_einfach,
                }
                for b in offene_behoerdenpost
            ],
        },

        "termine": {
            "naechste": [
                {
                    "id": t.id,
                    "titel": t.titel,
                    "datum": t.datum,
                    "ist_frist": t.ist_frist,
                    "beschreibung": t.beschreibung,
                }
                for t in naechste_termine
            ],
        },

        "ausgaben": {
            "diesen_monat_eur": ausgaben_monat,
            "anzahl_rechnungen_monat": len(rechnungen_monat),
        },
    }
