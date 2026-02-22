"""
Buchhaltungsmodul: Verarbeitet Rechnungen und Mahnungen.

- Extrahiert Netto/Brutto/USt via Claude
- Kategorisiert Betriebsausgaben automatisch
- Erstellt EÜR-Export als CSV
- Berechnet USt-Voranmeldung
"""

import csv
import io
import json
import logging
import re
from datetime import date
from typing import Optional

import anthropic

from app.config import settings
from app.models.brief import BriefAnalyse
from app.models.db_models import Document, Rechnung

logger = logging.getLogger("leadfactory.buchhaltung")

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

_PROMPT = """\
Du bist Steuerberater-Assistent für Deutschland/Österreich/Schweiz.
Extrahiere buchhalterische Daten aus der folgenden Briefanalyse.
Antworte NUR mit gültigem JSON, kein Markdown, keine Erklärungen.

JSON-Schema:
{
  "lieferant": "Firmenname oder null",
  "rechnungsnummer": "string oder null",
  "rechnungsdatum": "YYYY-MM-DD oder null",
  "faelligkeitsdatum": "YYYY-MM-DD oder null",
  "betrag_brutto": float,
  "ust_satz": float,
  "betrag_netto": float,
  "betrag_ust": float,
  "kategorie_buchhaltung": "string",
  "vorsteuer_abzugsfaehig": true | false,
  "iban": "string oder null"
}

ust_satz: 0.19 (Standard), 0.07 (ermäßigt: Lebensmittel, Bücher, ÖPNV),
          0.0 (steuerbefreit: Miete, Versicherung, Arzt)

Kategorien (verwende genau eine):
Büromaterial | IT-Hardware | IT-Software | Telekommunikation | Reisekosten |
Bewirtung | Werbung/Marketing | Beratung/Rechtskosten | Miete/Raumkosten |
Personal | Versicherungen | Fahrzeugkosten | Energiekosten | Sonstiges

vorsteuer_abzugsfaehig:
- true: fast alle unternehmerischen Ausgaben
- false: Miete (privat), nicht-abzugsfähige Bewirtung >70%, Strafen
"""


def verarbeite(doc: Document, analyse: BriefAnalyse, db) -> None:
    """Erstellt einen Rechnung-Eintrag aus einem Rechnungs- oder Mahnungs-Brief."""
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
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Buchhaltung Claude-Fehler: {e}")
        # Fallback: nur Basisdaten aus zahlungsinfo
        rohdaten = _fallback_aus_zahlungsinfo(analyse)

    rechnung = Rechnung(
        document_id=doc.id,
        lieferant=rohdaten.get("lieferant") or analyse.absender_name,
        rechnungsnummer=rohdaten.get("rechnungsnummer") or (
            analyse.zahlungsinfo.rechnungsnummer if analyse.zahlungsinfo else None
        ),
        rechnungsdatum=_parse_date(rohdaten.get("rechnungsdatum") or analyse.datum),
        faelligkeitsdatum=_parse_date(
            rohdaten.get("faelligkeitsdatum") or
            (analyse.zahlungsinfo.faelligkeitsdatum if analyse.zahlungsinfo else None)
        ),
        betrag_netto=rohdaten.get("betrag_netto"),
        ust_satz=rohdaten.get("ust_satz", 0.19),
        betrag_ust=rohdaten.get("betrag_ust"),
        betrag_brutto=rohdaten.get("betrag_brutto") or _parse_betrag(
            analyse.zahlungsinfo.betrag if analyse.zahlungsinfo else None
        ),
        kategorie_buchhaltung=rohdaten.get("kategorie_buchhaltung", "Sonstiges"),
        vorsteuer_abzugsfaehig=rohdaten.get("vorsteuer_abzugsfaehig", True),
        iban=rohdaten.get("iban") or (
            analyse.zahlungsinfo.iban if analyse.zahlungsinfo else None
        ),
        ist_mahnung=(analyse.kategorie == "Mahnung"),
    )
    db.add(rechnung)
    logger.info(f"Rechnung erfasst: {rechnung.lieferant}, {rechnung.betrag_brutto} EUR")


def _baue_kontext(analyse: BriefAnalyse) -> str:
    parts = [
        f"Kategorie: {analyse.kategorie}",
        f"Absender: {analyse.absender_name}",
        f"Betreff: {analyse.betreff}",
        f"Zusammenfassung: {analyse.zusammenfassung}",
    ]
    if analyse.zahlungsinfo:
        z = analyse.zahlungsinfo
        parts += [
            f"Betrag: {z.betrag}",
            f"Fälligkeitsdatum: {z.faelligkeitsdatum}",
            f"Rechnungsnummer: {z.rechnungsnummer or 'unbekannt'}",
            f"Gläubiger: {z.glaeubiger}",
            f"IBAN: {z.iban or 'keine'}",
        ]
    return "\n".join(parts)


def _fallback_aus_zahlungsinfo(analyse: BriefAnalyse) -> dict:
    betrag_brutto = None
    if analyse.zahlungsinfo:
        betrag_brutto = _parse_betrag(analyse.zahlungsinfo.betrag)
    netto = round(betrag_brutto / 1.19, 2) if betrag_brutto else None
    ust = round(betrag_brutto - netto, 2) if betrag_brutto and netto else None
    return {
        "lieferant": analyse.absender_name,
        "betrag_brutto": betrag_brutto,
        "betrag_netto": netto,
        "ust_satz": 0.19,
        "betrag_ust": ust,
        "kategorie_buchhaltung": "Sonstiges",
        "vorsteuer_abzugsfaehig": True,
    }


def _parse_betrag(betrag_str: Optional[str]) -> Optional[float]:
    """Parst '1.250,00 EUR' oder '1250.00' zu float."""
    if not betrag_str:
        return None
    cleaned = re.sub(r"[€$£¥\s]", "", betrag_str)
    cleaned = re.sub(r"(EUR|USD|GBP|CHF)", "", cleaned, flags=re.IGNORECASE).strip()
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


def _parse_date(d: Optional[str]) -> Optional[date]:
    if not d:
        return None
    try:
        return date.fromisoformat(d[:10])
    except ValueError:
        return None


# ── Export & Reports ──────────────────────────────────────────────────────────

def export_eur_csv(rechnungen: list[Rechnung]) -> str:
    """Erstellt eine EÜR-CSV für den Steuerberater (Semikolon-getrennt)."""
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "Datum", "Lieferant", "Rechnungsnummer", "Kategorie",
        "Netto (EUR)", "USt-Satz", "USt (EUR)", "Brutto (EUR)",
        "Vorsteuer abzugsfähig", "Bezahlt", "IBAN",
    ])
    for r in rechnungen:
        writer.writerow([
            r.rechnungsdatum or "",
            r.lieferant or "",
            r.rechnungsnummer or "",
            r.kategorie_buchhaltung or "",
            f"{r.betrag_netto:.2f}" if r.betrag_netto else "",
            f"{r.ust_satz * 100:.0f}%" if r.ust_satz is not None else "",
            f"{r.betrag_ust:.2f}" if r.betrag_ust else "",
            f"{r.betrag_brutto:.2f}" if r.betrag_brutto else "",
            "Ja" if r.vorsteuer_abzugsfaehig else "Nein",
            "Ja" if r.bezahlt else "Nein",
            r.iban or "",
        ])
    return output.getvalue()


def berechne_monatsbericht(rechnungen: list[Rechnung]) -> dict:
    """Gruppiert Ausgaben nach Kategorie und berechnet USt-Summen."""
    kategorien: dict[str, float] = {}
    gesamt_netto = 0.0
    gesamt_ust = 0.0
    gesamt_brutto = 0.0
    offene_posten = 0.0

    for r in rechnungen:
        kat = r.kategorie_buchhaltung or "Sonstiges"
        brutto = r.betrag_brutto or 0.0
        netto = r.betrag_netto or 0.0
        ust = r.betrag_ust or 0.0

        kategorien[kat] = round(kategorien.get(kat, 0.0) + brutto, 2)
        gesamt_netto = round(gesamt_netto + netto, 2)
        gesamt_ust = round(gesamt_ust + ust, 2)
        gesamt_brutto = round(gesamt_brutto + brutto, 2)
        if not r.bezahlt:
            offene_posten = round(offene_posten + brutto, 2)

    return {
        "gesamt_netto": gesamt_netto,
        "gesamt_ust": gesamt_ust,
        "gesamt_brutto": gesamt_brutto,
        "offene_posten": offene_posten,
        "vorsteuer_erstattung": round(
            sum((r.betrag_ust or 0) for r in rechnungen if r.vorsteuer_abzugsfaehig), 2
        ),
        "ausgaben_nach_kategorie": dict(sorted(kategorien.items(), key=lambda x: -x[1])),
    }
