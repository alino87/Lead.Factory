from pydantic import BaseModel
from typing import Optional, List


class Termin(BaseModel):
    titel: str
    datum: str                  # ISO-Format: YYYY-MM-DD
    uhrzeit: Optional[str]      # HH:MM oder None
    beschreibung: str
    frist: bool = False         # True wenn es eine Frist/Deadline ist


class Zahlungsinfo(BaseModel):
    betrag: str                 # z.B. "1.250,00 EUR"
    faelligkeitsdatum: str      # ISO-Format: YYYY-MM-DD
    iban: Optional[str]
    bic: Optional[str]
    verwendungszweck: Optional[str]
    glaeubiger: str
    rechnungsnummer: Optional[str]
    bank_ueberweisung_bereit: bool = True


class BriefAnalyse(BaseModel):
    # Klassifizierung
    kategorie: str              # "Rechnung", "Mahnung", "Behördenbrief", "Kundenbrief", "Vertragsunterlagen", "Werbung", "Sonstiges"
    prioritaet: str             # "hoch", "mittel", "niedrig"
    antwort_erforderlich: bool

    # Absender & Inhalt
    absender_name: str
    absender_adresse: Optional[str]
    empfaenger_name: Optional[str]
    datum: Optional[str]        # ISO-Format: YYYY-MM-DD
    betreff: str
    zusammenfassung: str        # Kurze deutsche Zusammenfassung

    # Ordnerstruktur
    ordner_pfad: str            # z.B. "2024/Rechnungen/Lieferanten" oder "2024/Behoerden/Finanzamt"
    datei_name: str             # Vorschlag: "2024-01-15_Finanzamt_Steuerbescheid.pdf"

    # Aktionen
    antwort_entwurf: Optional[str]  # Ausformulierter Antwortentwurf auf Deutsch

    # Termine & Fristen
    termine: List[Termin] = []

    # Zahlungsinformationen (nur bei Rechnungen/Mahnungen)
    zahlungsinfo: Optional[Zahlungsinfo] = None

    # Metadaten
    verarbeitungsfehler: Optional[str] = None
