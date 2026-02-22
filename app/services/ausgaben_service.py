"""
Ausgabenoptimierung: Analysiert Ausgabenmuster und erkennt Einsparpotenziale.

Braucht keine extra AI-Calls – reine SQL-Aggregation über die Rechnungstabelle.
Claude wird nur für den Freitext-Report genutzt (optional).
"""

import logging
from datetime import date
from typing import Optional

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.models.db_models import Rechnung, Vertrag

logger = logging.getLogger("leadfactory.ausgaben")


def monatsbericht(db: Session, jahr: int, monat: int) -> dict:
    """Ausgaben-Breakdown für einen bestimmten Monat."""
    rechnungen = (
        db.query(Rechnung)
        .join(Rechnung.document)
        .filter(
            extract("year", Rechnung.rechnungsdatum) == jahr,
            extract("month", Rechnung.rechnungsdatum) == monat,
        )
        .all()
    )

    # Kategorien-Aggregation
    kategorien: dict[str, float] = {}
    for r in rechnungen:
        kat = r.kategorie_buchhaltung or "Sonstiges"
        kategorien[kat] = round(kategorien.get(kat, 0.0) + (r.betrag_brutto or 0.0), 2)

    gesamt = sum(r.betrag_brutto or 0 for r in rechnungen)
    offen = sum(r.betrag_brutto or 0 for r in rechnungen if not r.bezahlt)

    return {
        "jahr": jahr,
        "monat": monat,
        "gesamt_brutto": round(gesamt, 2),
        "offene_posten": round(offen, 2),
        "anzahl_rechnungen": len(rechnungen),
        "ausgaben_nach_kategorie": dict(
            sorted(kategorien.items(), key=lambda x: -x[1])
        ),
    }


def jahresbericht(db: Session, jahr: int) -> dict:
    """Monat-für-Monat Ausgaben-Übersicht für ein Jahr."""
    monate = []
    for monat in range(1, 13):
        bericht = monatsbericht(db, jahr, monat)
        if bericht["anzahl_rechnungen"] > 0:
            monate.append(bericht)

    gesamt_jahr = sum(m["gesamt_brutto"] for m in monate)

    # Feste Kosten aus Verträgen
    fixkosten = _berechne_fixkosten(db)

    return {
        "jahr": jahr,
        "gesamt_brutto": round(gesamt_jahr, 2),
        "monatliche_fixkosten": fixkosten,
        "monate": monate,
    }


def trend_analyse(db: Session, monate_vergleich: int = 3) -> list[dict]:
    """
    Vergleicht die letzten N Monate. Flaggt Kategorien mit >20% Anstieg.
    """
    heute = date.today()
    ergebnisse = []

    for kat in _alle_kategorien(db):
        werte = []
        monat = heute.month
        jahr = heute.year
        for _ in range(monate_vergleich):
            summe = (
                db.query(func.sum(Rechnung.betrag_brutto))
                .filter(
                    Rechnung.kategorie_buchhaltung == kat,
                    extract("year", Rechnung.rechnungsdatum) == jahr,
                    extract("month", Rechnung.rechnungsdatum) == monat,
                )
                .scalar() or 0.0
            )
            werte.append(round(summe, 2))
            monat -= 1
            if monat == 0:
                monat = 12
                jahr -= 1

        werte.reverse()  # ältester Monat zuerst

        if len(werte) >= 2 and werte[-2] > 0:
            aenderung = (werte[-1] - werte[-2]) / werte[-2] * 100
            ergebnisse.append({
                "kategorie": kat,
                "werte": werte,
                "aenderung_prozent": round(aenderung, 1),
                "alarm": aenderung > 20,
            })

    return sorted(ergebnisse, key=lambda x: -abs(x["aenderung_prozent"]))


def _berechne_fixkosten(db: Session) -> float:
    """Summiert monatliche Kosten aller aktiven Verträge."""
    result = (
        db.query(func.sum(Vertrag.monatliche_kosten))
        .filter(Vertrag.aktiv == True, Vertrag.monatliche_kosten != None)
        .scalar()
    )
    return round(result or 0.0, 2)


def _alle_kategorien(db: Session) -> list[str]:
    rows = db.query(Rechnung.kategorie_buchhaltung).distinct().all()
    return [r[0] for r in rows if r[0]]
