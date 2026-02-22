"""
Brief-Verarbeitungs-Agent für Einzelunternehmer und KMU.

Verarbeitet gescannte Briefe (Bilder oder PDFs als Base64) mit Claude Vision:
- Klassifiziert Briefe nach Kategorie und Priorität
- Schlägt eine Ordnerstruktur vor
- Erstellt Antwortentwürfe
- Extrahiert Termine und Fristen
- Bereitet Rechnungen zur Überweisung vor
"""

import os
import json
import logging
import base64
from datetime import date
from typing import Optional

import anthropic

from app.models.brief import BriefAnalyse, Termin, Zahlungsinfo

logger = logging.getLogger("leadfactory.brief")

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

HEUTE = date.today().isoformat()

SYSTEM_PROMPT = f"""Du bist ein professioneller Büroassistent für Einzelunternehmer und kleine Unternehmen in Deutschland/Österreich/Schweiz.
Heute ist: {HEUTE}

Deine Aufgabe: Analysiere gescannte Briefe und liefere strukturierte Informationen auf Deutsch.

Du musst IMMER gültiges JSON ausgeben – kein Markdown, keine Erklärungen, kein Text außerhalb von JSON.

JSON-Schema:
{{
  "kategorie": "Rechnung" | "Mahnung" | "Behördenbrief" | "Kundenbrief" | "Vertragsunterlagen" | "Werbung" | "Sonstiges",
  "prioritaet": "hoch" | "mittel" | "niedrig",
  "antwort_erforderlich": true | false,
  "absender_name": "string",
  "absender_adresse": "string oder null",
  "empfaenger_name": "string oder null",
  "datum": "YYYY-MM-DD oder null",
  "betreff": "string (max 120 Zeichen)",
  "zusammenfassung": "string (2-4 Sätze auf Deutsch)",
  "ordner_pfad": "string (z.B. '2024/Rechnungen/Lieferanten' oder '2024/Behoerden/Finanzamt')",
  "datei_name": "string (z.B. '2024-01-15_Firma_Betreff.pdf', nur [A-Za-z0-9_-.])",
  "antwort_entwurf": "string (vollständiger Brief auf Deutsch) oder null",
  "termine": [
    {{
      "titel": "string",
      "datum": "YYYY-MM-DD",
      "uhrzeit": "HH:MM oder null",
      "beschreibung": "string",
      "frist": true | false
    }}
  ],
  "zahlungsinfo": {{
    "betrag": "string (z.B. '1.250,00 EUR')",
    "faelligkeitsdatum": "YYYY-MM-DD",
    "iban": "string oder null",
    "bic": "string oder null",
    "verwendungszweck": "string oder null",
    "glaeubiger": "string",
    "rechnungsnummer": "string oder null",
    "bank_ueberweisung_bereit": true
  }} oder null
}}

Regeln:
- Priorität "hoch": Mahnungen, Behördenpost mit Fristen, Zahlungsaufforderungen
- Priorität "mittel": Rechnungen, Verträge, Kundenbriefe mit Handlungsbedarf
- Priorität "niedrig": Werbung, Informationsschreiben ohne Handlungsbedarf
- Ordnerpfad: Nutze das Jahr aus dem Briefdatum. Keine Umlaute im Pfad (ä→ae, ö→oe, ü→ue, ß→ss)
- Dateiname: Kein Leerzeichen, nur [A-Za-z0-9_-.], Format: YYYY-MM-DD_Absender_Betreff.pdf
- Antwortentwurf: Nur erstellen wenn antwort_erforderlich=true. Vollständiger formeller Brief mit Datum, Anrede, Inhalt, Grußformel
- Termine: Alle erwähnten Fristen, Zahlungsdaten, Termine extrahieren
- Zahlungsinfo: Nur bei Rechnungen oder Mahnungen befüllen
"""


def _analyse_mit_claude(
    bild_base64: str,
    media_type: str,
    unternehmensname: Optional[str] = None,
) -> dict:
    """Sendet das Bild an Claude Opus und gibt das geparste JSON zurück."""
    kontext = ""
    if unternehmensname:
        kontext = f"Der Empfänger heißt: {unternehmensname}\n\n"

    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": bild_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            f"{kontext}Analysiere diesen gescannten Brief vollständig "
                            "und liefere das JSON-Ergebnis gemäß den Systemanweisungen."
                        ),
                    },
                ],
            }
        ],
    ) as stream:
        nachricht = stream.get_final_message()

    # JSON aus der Antwort extrahieren
    for block in nachricht.content:
        if block.type == "text":
            text = block.text.strip()
            # Falls Claude trotzdem Markdown-Blöcke liefert, bereinigen
            if text.startswith("```"):
                lines = text.splitlines()
                text = "\n".join(
                    line for line in lines if not line.startswith("```")
                ).strip()
            return json.loads(text)

    raise ValueError("Claude hat kein Text-Block zurückgegeben")


def _baue_brief_analyse(rohdaten: dict) -> BriefAnalyse:
    """Konvertiert das rohe JSON-Dict in ein typisiertes BriefAnalyse-Objekt."""
    termine = [
        Termin(
            titel=t.get("titel", ""),
            datum=t.get("datum", HEUTE),
            uhrzeit=t.get("uhrzeit"),
            beschreibung=t.get("beschreibung", ""),
            frist=t.get("frist", False),
        )
        for t in rohdaten.get("termine", [])
    ]

    zahlungsinfo = None
    if rohdaten.get("zahlungsinfo"):
        z = rohdaten["zahlungsinfo"]
        zahlungsinfo = Zahlungsinfo(
            betrag=z.get("betrag", ""),
            faelligkeitsdatum=z.get("faelligkeitsdatum", HEUTE),
            iban=z.get("iban"),
            bic=z.get("bic"),
            verwendungszweck=z.get("verwendungszweck"),
            glaeubiger=z.get("glaeubiger", ""),
            rechnungsnummer=z.get("rechnungsnummer"),
            bank_ueberweisung_bereit=z.get("bank_ueberweisung_bereit", True),
        )

    return BriefAnalyse(
        kategorie=rohdaten.get("kategorie", "Sonstiges"),
        prioritaet=rohdaten.get("prioritaet", "mittel"),
        antwort_erforderlich=rohdaten.get("antwort_erforderlich", False),
        absender_name=rohdaten.get("absender_name", "Unbekannt"),
        absender_adresse=rohdaten.get("absender_adresse"),
        empfaenger_name=rohdaten.get("empfaenger_name"),
        datum=rohdaten.get("datum"),
        betreff=rohdaten.get("betreff", ""),
        zusammenfassung=rohdaten.get("zusammenfassung", ""),
        ordner_pfad=rohdaten.get("ordner_pfad", "Sonstiges"),
        datei_name=rohdaten.get("datei_name", "brief.pdf"),
        antwort_entwurf=rohdaten.get("antwort_entwurf"),
        termine=termine,
        zahlungsinfo=zahlungsinfo,
    )


def verarbeite_brief(
    bild_bytes: bytes,
    media_type: str,
    unternehmensname: Optional[str] = None,
) -> BriefAnalyse:
    """
    Hauptfunktion: Verarbeitet einen gescannten Brief.

    Args:
        bild_bytes:      Rohe Bilddaten (JPEG, PNG oder PDF)
        media_type:      MIME-Typ: "image/jpeg", "image/png" oder "application/pdf"
        unternehmensname: Optional – Name des Empfänger-Unternehmens für Kontext

    Returns:
        BriefAnalyse mit allen extrahierten Informationen
    """
    try:
        bild_base64 = base64.standard_b64encode(bild_bytes).decode("utf-8")
        rohdaten = _analyse_mit_claude(bild_base64, media_type, unternehmensname)
        return _baue_brief_analyse(rohdaten)
    except json.JSONDecodeError as e:
        logger.error(f"JSON-Parse-Fehler: {e}")
        return BriefAnalyse(
            kategorie="Sonstiges",
            prioritaet="mittel",
            antwort_erforderlich=False,
            absender_name="Unbekannt",
            betreff="Verarbeitungsfehler",
            zusammenfassung="Der Brief konnte nicht analysiert werden.",
            ordner_pfad="Fehler",
            datei_name="fehler.pdf",
            verarbeitungsfehler="LLM_PARSE_ERROR",
        )
    except anthropic.RateLimitError:
        logger.error("Anthropic Rate-Limit erreicht")
        return BriefAnalyse(
            kategorie="Sonstiges",
            prioritaet="mittel",
            antwort_erforderlich=False,
            absender_name="Unbekannt",
            betreff="Rate-Limit-Fehler",
            zusammenfassung="Zu viele Anfragen. Bitte später erneut versuchen.",
            ordner_pfad="Fehler",
            datei_name="fehler.pdf",
            verarbeitungsfehler="RATE_LIMIT",
        )
    except anthropic.AuthenticationError:
        logger.error("Anthropic Auth-Fehler")
        return BriefAnalyse(
            kategorie="Sonstiges",
            prioritaet="hoch",
            antwort_erforderlich=False,
            absender_name="Unbekannt",
            betreff="API-Authentifizierungsfehler",
            zusammenfassung="API-Schlüssel ungültig.",
            ordner_pfad="Fehler",
            datei_name="fehler.pdf",
            verarbeitungsfehler="AUTH_ERROR",
        )
    except Exception as e:
        logger.error(f"Unbekannter Fehler bei Brief-Verarbeitung: {e}")
        return BriefAnalyse(
            kategorie="Sonstiges",
            prioritaet="mittel",
            antwort_erforderlich=False,
            absender_name="Unbekannt",
            betreff="Unbekannter Fehler",
            zusammenfassung="Ein unbekannter Fehler ist aufgetreten.",
            ordner_pfad="Fehler",
            datei_name="fehler.pdf",
            verarbeitungsfehler=f"UNKNOWN: {type(e).__name__}",
        )
