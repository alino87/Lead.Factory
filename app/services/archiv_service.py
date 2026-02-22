"""
Dokumentenarchiv mit Smart Search.

Volltextsuche über alle verarbeiteten Dokumente.
Natürliche Sprachsuche via Claude → SQL-Filter.
"""

import json
import logging
from typing import Optional

import anthropic
from sqlalchemy.orm import Session

from app.config import settings
from app.models.db_models import Document

logger = logging.getLogger("leadfactory.archiv")

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

_SUCHFILTER_PROMPT = """\
Du bist ein Datenbankfilter-Assistent. Übersetze natürlichsprachliche Suchanfragen
in strukturierte JSON-Filter für eine Dokumentendatenbank.

Verfügbare Felder:
- kategorie: "Rechnung" | "Mahnung" | "Behördenbrief" | "Kundenbrief" | "Vertragsunterlagen" | "Werbung" | "Sonstiges"
- prioritaet: "hoch" | "mittel" | "niedrig"
- absender_name: string (Teilsuche)
- betreff: string (Teilsuche)
- datum_von: YYYY-MM-DD (Briefdatum ab)
- datum_bis: YYYY-MM-DD (Briefdatum bis)
- text: string (Freitext-Suche in Betreff + Zusammenfassung)

Antworte NUR mit JSON, kein Markdown:
{
  "kategorie": null oder string,
  "prioritaet": null oder string,
  "absender_name": null oder string,
  "datum_von": null oder string,
  "datum_bis": null oder string,
  "text": null oder string
}

Beispiele:
"Alle Rechnungen von letztem Monat" → {"kategorie": "Rechnung", "datum_von": "2025-11-01", "datum_bis": "2025-11-30", ...}
"Briefe vom Finanzamt" → {"absender_name": "Finanzamt", ...}
"Offene Rechnungen über 500 Euro" → {"kategorie": "Rechnung", "text": "500", ...}
"""


def suche(
    db: Session,
    query: str,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """
    Natürliche Sprachsuche: Übersetzt den Query via Claude in SQL-Filter.
    Fallback: einfache LIKE-Suche über alle Textfelder.
    """
    filter_params = _parse_query_mit_claude(query)
    return suche_mit_filtern(db, limit=limit, offset=offset, **filter_params)


def suche_mit_filtern(
    db: Session,
    text: Optional[str] = None,
    kategorie: Optional[str] = None,
    prioritaet: Optional[str] = None,
    absender_name: Optional[str] = None,
    datum_von: Optional[str] = None,
    datum_bis: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """Direkte Filtersuche – wird auch von /archiv/dokumente genutzt."""
    q = db.query(Document)

    if kategorie:
        q = q.filter(Document.kategorie == kategorie)
    if prioritaet:
        q = q.filter(Document.prioritaet == prioritaet)
    if absender_name:
        q = q.filter(Document.absender_name.ilike(f"%{absender_name}%"))
    if datum_von:
        q = q.filter(Document.datum >= datum_von)
    if datum_bis:
        q = q.filter(Document.datum <= datum_bis)
    if text:
        pattern = f"%{text}%"
        from sqlalchemy import or_
        q = q.filter(or_(
            Document.betreff.ilike(pattern),
            Document.zusammenfassung.ilike(pattern),
            Document.absender_name.ilike(pattern),
        ))

    total = q.count()
    docs = q.order_by(Document.processed_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "dokumente": [_doc_zu_dict(d) for d in docs],
    }


def _parse_query_mit_claude(query: str) -> dict:
    """Übersetzt natürliche Sprache in Filterparameter."""
    try:
        msg = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            temperature=0,
            system=_SUCHFILTER_PROMPT,
            messages=[{"role": "user", "content": f"Suchanfrage: {query}"}],
        )
        result = json.loads(msg.content[0].text)
        # Null-Werte entfernen
        return {k: v for k, v in result.items() if v is not None}
    except Exception as e:
        logger.warning(f"Smart-Search Fallback auf Freitext: {e}")
        return {"text": query}


def _doc_zu_dict(d: Document) -> dict:
    return {
        "id": d.id,
        "filename": d.filename,
        "kategorie": d.kategorie,
        "prioritaet": d.prioritaet,
        "absender_name": d.absender_name,
        "datum": d.datum,
        "betreff": d.betreff,
        "zusammenfassung": d.zusammenfassung,
        "archive_path": d.archive_path,
        "processed_at": d.processed_at.isoformat() if d.processed_at else None,
        "antwort_erforderlich": d.antwort_erforderlich,
    }
