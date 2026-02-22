"""
Behördenassistent: Erklärt Behördenbriefe in einfacher Sprache.

Das wichtigste Feature: Behördenbriefe machen Angst.
Claude erklärt in 3-5 klaren Sätzen was wirklich drin steht,
was zu tun ist, und bis wann.
"""

import json
import logging
from datetime import date
from typing import Optional

import anthropic

from app.config import settings
from app.models.brief import BriefAnalyse
from app.models.db_models import Behoerdenpost, Document

logger = logging.getLogger("leadfactory.behoerden")

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

_PROMPT = """\
Du bist ein Behördenbrief-Dolmetscher für Kleinunternehmer in Deutschland/Österreich/Schweiz.
Deine Aufgabe: Mache komplizierte Behördenbriefe verständlich.

Antworte NUR mit gültigem JSON, kein Markdown.

JSON-Schema:
{
  "behoerde": "Name der Behörde (z.B. 'Finanzamt München', 'Gewerbeamt', 'IHK')",
  "aktenzeichen": "string oder null",
  "frist": "YYYY-MM-DD oder null",
  "erklaerung_einfach": "3-5 Sätze in einfachem Deutsch. Was will die Behörde? Warum? Was passiert wenn nichts getan wird?",
  "was_zu_tun": "Nummerierte Liste der konkreten Schritte. Maximal 5 Schritte."
}

Beispiel für erklaerung_einfach:
"Das Finanzamt möchte deine Umsatzsteuervoranmeldung für Q3 2024.
Du musst erklären wie viel Umsatzsteuer du eingenommen und gezahlt hast.
Die Frist ist der 10. November 2024. Wenn du nichts tust, können Bußgelder entstehen."

Beispiel für was_zu_tun:
"1. Umsatzsteuervoranmeldung in ELSTER online ausfüllen\\n2. Alle Rechnungen aus Q3 bereithalten\\n3. Bis 10.11.2024 absenden"

Wichtig: Einfache, klare Sprache. Kein Juristendeutsch. Keine Panik verbreiten, aber Fristen klar benennen.
"""


def verarbeite(doc: Document, analyse: BriefAnalyse, db) -> None:
    """Erstellt einen Behördenpost-Eintrag mit Erklärung und Checkliste."""
    context = _baue_kontext(analyse)

    try:
        msg = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            temperature=0,
            system=_PROMPT,
            messages=[{"role": "user", "content": context}],
        )
        rohdaten = json.loads(msg.content[0].text)
    except Exception as e:
        logger.error(f"Behörden Claude-Fehler: {e}")
        rohdaten = {
            "behoerde": analyse.absender_name,
            "erklaerung_einfach": analyse.zusammenfassung,
            "was_zu_tun": "Bitte prüfe diesen Brief manuell.",
        }

    # Frist: aus Claude-Antwort oder aus bereits extrahierten Terminen
    frist = _parse_date(rohdaten.get("frist"))
    if not frist and analyse.termine:
        fristen = [t for t in analyse.termine if t.frist]
        if fristen:
            frist = _parse_date(fristen[0].datum)

    bp = Behoerdenpost(
        document_id=doc.id,
        behoerde=rohdaten.get("behoerde") or analyse.absender_name,
        aktenzeichen=rohdaten.get("aktenzeichen"),
        betreff=analyse.betreff,
        frist=frist,
        erklaerung_einfach=rohdaten.get("erklaerung_einfach"),
        was_zu_tun=rohdaten.get("was_zu_tun"),
    )
    db.add(bp)
    logger.info(f"Behördenpost erfasst: {bp.behoerde}, Frist: {bp.frist}")


def _baue_kontext(analyse: BriefAnalyse) -> str:
    parts = [
        f"Behörde/Absender: {analyse.absender_name}",
        f"Betreff: {analyse.betreff}",
        f"Priorität: {analyse.prioritaet}",
        f"Zusammenfassung: {analyse.zusammenfassung}",
    ]
    if analyse.datum:
        parts.append(f"Briefdatum: {analyse.datum}")
    if analyse.termine:
        fristen_str = ", ".join(
            f"{t.titel} am {t.datum}" for t in analyse.termine if t.frist
        )
        if fristen_str:
            parts.append(f"Erkannte Fristen: {fristen_str}")
    return "\n".join(parts)


def _parse_date(d: Optional[str]) -> Optional[date]:
    if not d:
        return None
    try:
        return date.fromisoformat(d[:10])
    except ValueError:
        return None
