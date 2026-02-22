"""
Automatischer Ordner-Watcher für den Brief-Verarbeitungs-Agenten.

Workflow:
  1. Scanner speichert Datei in SCAN_EINGANG (Standard: ./Scanner-Eingang)
  2. Dieser Watcher erkennt die neue Datei sofort
  3. Sendet sie an den Agenten (POST /brief/verarbeiten)
  4. Legt die Ergebnisdatei (JSON) neben dem Original ab
  5. Verschiebt das Original in die vorgeschlagene Ordnerstruktur unter ARCHIV_ORDNER

Start:
  Windows:  python watcher.py
  Mac/Linux: python3 watcher.py

Konfiguration über Umgebungsvariablen (oder .env):
  SCAN_EINGANG      Pfad zum Scan-Eingangsordner  (Standard: ./Scanner-Eingang)
  ARCHIV_ORDNER     Pfad zum Archiv               (Standard: ./Archiv)
  API_URL           URL des Agenten               (Standard: http://localhost:8000)
  API_FACTORY_KEY   API-Schlüssel
  UNTERNEHMENSNAME  Eigener Firmenname (optional)
  SCAN_VERZOEGERUNG Sekunden warten nach Erkennung (Standard: 2)
"""

import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# --- Konfiguration aus .env laden ----------------------------------------
load_dotenv()

SCAN_EINGANG = Path(os.getenv("SCAN_EINGANG", "./Scanner-Eingang"))
ARCHIV_ORDNER = Path(os.getenv("ARCHIV_ORDNER", "./Archiv"))
API_URL = os.getenv("API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_FACTORY_KEY", "")
UNTERNEHMENSNAME = os.getenv("UNTERNEHMENSNAME", "")
SCAN_VERZOEGERUNG = int(os.getenv("SCAN_VERZOEGERUNG", "2"))

# Unterstützte Dateiformate
ERLAUBTE_ENDUNGEN = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}

# --- Logging einrichten ---------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("watcher.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("watcher")


# --- Hilfsfunktionen ------------------------------------------------------

def warte_bis_datei_fertig(pfad: Path, max_sekunden: int = 30) -> bool:
    """
    Wartet bis der Scanner die Datei vollständig geschrieben hat.
    Erkennt das daran, dass sich die Dateigröße nicht mehr ändert.
    """
    letzte_groesse = -1
    for _ in range(max_sekunden):
        try:
            aktuelle_groesse = pfad.stat().st_size
        except FileNotFoundError:
            return False
        if aktuelle_groesse == letzte_groesse and aktuelle_groesse > 0:
            return True
        letzte_groesse = aktuelle_groesse
        time.sleep(1)
    return False


def sende_an_agenten(pfad: Path) -> dict | None:
    """Schickt die Datei an POST /brief/verarbeiten und gibt das JSON-Ergebnis zurück."""
    mime_typen = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".pdf": "application/pdf",
    }
    mime = mime_typen.get(pfad.suffix.lower(), "application/octet-stream")

    try:
        with pfad.open("rb") as f:
            dateien = {"datei": (pfad.name, f, mime)}
            daten = {}
            if UNTERNEHMENSNAME:
                daten["unternehmensname"] = UNTERNEHMENSNAME

            antwort = requests.post(
                f"{API_URL}/brief/verarbeiten",
                headers={"X-API-KEY": API_KEY},
                files=dateien,
                data=daten,
                timeout=120,  # Claude kann etwas Zeit brauchen
            )
            antwort.raise_for_status()
            return antwort.json()

    except requests.exceptions.ConnectionError:
        log.error(f"Verbindung zum Server fehlgeschlagen ({API_URL}). Läuft der Server?")
    except requests.exceptions.Timeout:
        log.error(f"Zeitüberschreitung bei Verarbeitung von: {pfad.name}")
    except requests.exceptions.HTTPError as e:
        log.error(f"HTTP-Fehler {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        log.error(f"Unbekannter Fehler: {e}")
    return None


def archiviere_datei(original: Path, ergebnis: dict) -> Path:
    """
    Verschiebt die gescannte Datei in die vom Agenten vorgeschlagene
    Ordnerstruktur unter ARCHIV_ORDNER.

    Beispiel:  ./Archiv/2024/Rechnungen/Lieferanten/2024-01-15_Firma_Rechnung.pdf
    """
    ordner_pfad = ergebnis.get("ordner_pfad", "Sonstiges")
    datei_name = ergebnis.get("datei_name", original.name)

    # Sicherheitscheck: keine absoluten Pfade oder ".." aus dem LLM übernehmen
    teile = [t for t in Path(ordner_pfad).parts if t not in ("", ".", "..") and not Path(t).is_absolute()]
    ziel_ordner = ARCHIV_ORDNER.joinpath(*teile) if teile else ARCHIV_ORDNER / "Sonstiges"
    ziel_ordner.mkdir(parents=True, exist_ok=True)

    # Dateinamens-Konflikt vermeiden
    ziel = ziel_ordner / datei_name
    if ziel.exists():
        stamm = ziel.stem
        endung = ziel.suffix
        zaehler = 1
        while ziel.exists():
            ziel = ziel_ordner / f"{stamm}_{zaehler}{endung}"
            zaehler += 1

    shutil.move(str(original), str(ziel))
    return ziel


def speichere_ergebnis(ziel_datei: Path, ergebnis: dict) -> None:
    """Speichert das JSON-Ergebnis als .analyse.json neben der archivierten Datei."""
    json_pfad = ziel_datei.with_suffix(".analyse.json")
    with json_pfad.open("w", encoding="utf-8") as f:
        json.dump(ergebnis, f, ensure_ascii=False, indent=2)


def verarbeite_datei(pfad: Path) -> None:
    """Kompletter Verarbeitungsprozess für eine einzelne Datei."""
    log.info(f"Neue Datei erkannt: {pfad.name}")

    # Warten bis Scanner fertig geschrieben hat
    time.sleep(SCAN_VERZOEGERUNG)
    if not warte_bis_datei_fertig(pfad):
        log.warning(f"Datei scheint unvollständig: {pfad.name} – übersprungen")
        return

    # An Agenten senden
    log.info(f"Sende an Agenten: {pfad.name} ...")
    ergebnis = sende_an_agenten(pfad)
    if ergebnis is None:
        log.error(f"Verarbeitung fehlgeschlagen: {pfad.name}")
        return

    # Ergebnis zusammenfassen
    kategorie = ergebnis.get("kategorie", "?")
    prioritaet = ergebnis.get("prioritaet", "?")
    betreff = ergebnis.get("betreff", "")
    log.info(f"  Kategorie:  {kategorie}  |  Priorität: {prioritaet}")
    log.info(f"  Betreff:    {betreff}")
    log.info(f"  Ordner:     {ergebnis.get('ordner_pfad', '')}")

    if ergebnis.get("zahlungsinfo"):
        z = ergebnis["zahlungsinfo"]
        log.info(f"  Zahlung:    {z.get('betrag', '')} fällig {z.get('faelligkeitsdatum', '')}")

    if ergebnis.get("termine"):
        for t in ergebnis["termine"]:
            frist = " [FRIST]" if t.get("frist") else ""
            log.info(f"  Termin:     {t.get('datum', '')} – {t.get('titel', '')}{frist}")

    # Archivieren und JSON speichern
    ziel = archiviere_datei(pfad, ergebnis)
    speichere_ergebnis(ziel, ergebnis)
    log.info(f"Archiviert: {ziel}")
    log.info("-" * 60)


# --- Watchdog Event-Handler -----------------------------------------------

class ScanEingangHandler(FileSystemEventHandler):
    """Reagiert auf neue Dateien im Scan-Eingangsordner."""

    def on_created(self, event):
        if event.is_directory:
            return
        pfad = Path(event.src_path)
        if pfad.suffix.lower() in ERLAUBTE_ENDUNGEN:
            verarbeite_datei(pfad)

    def on_moved(self, event):
        # Manche Scanner verschieben erst in Temp-Datei, dann zum Ziel
        if event.is_directory:
            return
        pfad = Path(event.dest_path)
        if pfad.suffix.lower() in ERLAUBTE_ENDUNGEN:
            verarbeite_datei(pfad)


# --- Hauptprogramm --------------------------------------------------------

def main():
    # Ordner anlegen falls nicht vorhanden
    SCAN_EINGANG.mkdir(parents=True, exist_ok=True)
    ARCHIV_ORDNER.mkdir(parents=True, exist_ok=True)

    log.info("=" * 60)
    log.info("  LeadFactory – Automatischer Brief-Watcher")
    log.info("=" * 60)
    log.info(f"  Scan-Eingang:  {SCAN_EINGANG.resolve()}")
    log.info(f"  Archiv:        {ARCHIV_ORDNER.resolve()}")
    log.info(f"  Server:        {API_URL}")
    if UNTERNEHMENSNAME:
        log.info(f"  Unternehmen:   {UNTERNEHMENSNAME}")
    log.info(f"  Formate:       {', '.join(ERLAUBTE_ENDUNGEN)}")
    log.info("-" * 60)
    log.info("Warte auf neue Scans ... (Strg+C zum Beenden)")
    log.info("")

    handler = ScanEingangHandler()
    observer = Observer()
    observer.schedule(handler, str(SCAN_EINGANG), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Watcher wird beendet ...")
    finally:
        observer.stop()
        observer.join()
        log.info("Watcher beendet.")


if __name__ == "__main__":
    main()
