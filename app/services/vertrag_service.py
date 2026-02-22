"""
Vertragsmanager: Erkennt, speichert und überwacht Verträge.

- Extrahiert Vertragsdaten via Claude
- Berechnet nächsten Kündigungstermin automatisch
- Warnt 60 Tage vor Ablauf der Kündigungsfrist
"""

import json
import logging
from datetime import date, timedelta
from typing import Optional

import anthropic

from app.config import settings
from app.models.brief import BriefAnalyse
from app.models.db_models import Document, Vertrag

logger = logging.getLogger("leadfactory.vertrag")

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

_PROMPT = """\
Du bist Vertragsexperte für Deutschland/Österreich/Schweiz.
Extrahiere Vertragsdaten aus der folgenden Briefanalyse.
Antworte NUR mit gültigem JSON, kein Markdown.

JSON-Schema:
{
  "vertragspartner": "Firmenname",
  "vertragsart": "string",
  "beginn": "YYYY-MM-DD oder null",
  "ende": "YYYY-MM-DD oder null",
  "laufzeit_monate": int oder null,
  "kuendigungsfrist_tage": int oder null,
  "monatliche_kosten": float oder null,
  "notizen": "wichtige Besonderheiten oder null"
}

vertragsart: Mietvertrag | Versicherung | Telekommunikation | Leasing |
             Wartungsvertrag | Lizenzvertrag | Dienstleistung | Sonstiges

kuendigungsfrist_tage: typische Werte:
- Mietvertrag: 90 (3 Monate)
- Versicherung: 30 (1 Monat vor Ablauf)
- Telekommunikation: 28 (4 Wochen)
- Wenn nicht explizit genannt: 30
"""


def verarbeite(doc: Document, analyse: BriefAnalyse, db) -> None:
    """Extrahiert Vertragsdaten und speichert sie in der DB."""
    context = _baue_kontext(analyse)

    try:
        msg = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            temperature=0,
            system=_PROMPT,
            messages=[{"role": "user", "content": context}],
        )
        rohdaten = json.loads(msg.content[0].text)
    except Exception as e:
        logger.error(f"Vertrag Claude-Fehler: {e}")
        rohdaten = {}

    beginn = _parse_date(rohdaten.get("beginn"))
    ende = _parse_date(rohdaten.get("ende"))
    laufzeit = rohdaten.get("laufzeit_monate")
    frist_tage = rohdaten.get("kuendigungsfrist_tage", 30)

    # Ende aus Beginn + Laufzeit berechnen falls Ende fehlt
    if not ende and beginn and laufzeit:
        from dateutil.relativedelta import relativedelta
        try:
            ende = beginn + relativedelta(months=laufzeit)
        except Exception:
            pass

    # Nächsten Kündigungstermin berechnen
    naechste_kuendigung = _berechne_kuendigungstermin(ende, frist_tage)

    vertrag = Vertrag(
        document_id=doc.id,
        vertragspartner=rohdaten.get("vertragspartner") or analyse.absender_name,
        vertragsart=rohdaten.get("vertragsart", "Sonstiges"),
        beginn=beginn,
        ende=ende,
        laufzeit_monate=laufzeit,
        kuendigungsfrist_tage=frist_tage,
        naechste_kuendigung_bis=naechste_kuendigung,
        monatliche_kosten=rohdaten.get("monatliche_kosten"),
        notizen=rohdaten.get("notizen"),
    )
    db.add(vertrag)
    logger.info(
        f"Vertrag erfasst: {vertrag.vertragspartner}, "
        f"Kündigung bis: {vertrag.naechste_kuendigung_bis}"
    )


def _baue_kontext(analyse: BriefAnalyse) -> str:
    return "\n".join([
        f"Kategorie: {analyse.kategorie}",
        f"Absender: {analyse.absender_name}",
        f"Betreff: {analyse.betreff}",
        f"Zusammenfassung: {analyse.zusammenfassung}",
        f"Datum: {analyse.datum or 'unbekannt'}",
    ])


def _berechne_kuendigungstermin(
    ende: Optional[date],
    frist_tage: Optional[int],
) -> Optional[date]:
    """
    Berechnet den spätesten Termin für eine fristgerechte Kündigung.
    Kündigungsfrist zählt rückwärts vom Vertragsende.
    """
    if not ende or not frist_tage:
        return None
    return ende - timedelta(days=frist_tage)


def prüfe_deadlines(db) -> list[Vertrag]:
    """
    Gibt alle aktiven Verträge zurück, bei denen der Kündigungstermin
    in den nächsten 60 Tagen liegt. Wird vom Scheduler täglich aufgerufen.
    """
    heute = date.today()
    warnschwelle = heute + timedelta(days=60)

    vertraege = (
        db.query(Vertrag)
        .filter(
            Vertrag.aktiv == True,
            Vertrag.naechste_kuendigung_bis != None,
            Vertrag.naechste_kuendigung_bis >= heute,
            Vertrag.naechste_kuendigung_bis <= warnschwelle,
        )
        .all()
    )

    for v in vertraege:
        verbleibend = (v.naechste_kuendigung_bis - heute).days
        logger.warning(
            f"⚠️  KÜNDIGUNG IN {verbleibend} TAGEN: "
            f"{v.vertragspartner} ({v.vertragsart}) – "
            f"Kündigen bis {v.naechste_kuendigung_bis}"
        )

    return vertraege


def _parse_date(d: Optional[str]) -> Optional[date]:
    if not d:
        return None
    try:
        return date.fromisoformat(d[:10])
    except ValueError:
        return None
