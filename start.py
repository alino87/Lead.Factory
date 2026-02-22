"""
LeadFactory – Plattformunabhängiger Starter
Funktioniert auf Windows, macOS und Linux ohne externe Tools.

Verwendung:
  Windows:   python start.py   (oder Doppelklick auf start.bat)
  macOS:     python3 start.py  (oder ./start.sh)
  Linux:     python3 start.py
"""

import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

MIN_PYTHON = (3, 10)
ROOT = Path(__file__).parent.resolve()


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def check_python_version() -> None:
    if sys.version_info < MIN_PYTHON:
        v = f"{sys.version_info.major}.{sys.version_info.minor}"
        req = f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
        print(f"[FEHLER] Python {req}+ wird benötigt (gefunden: {v})")
        print("  macOS:   brew install python@3.12")
        print("  Windows: https://www.python.org/downloads/")
        _pause_and_exit(1)


def load_env(env_file: Path) -> dict:
    """
    Liest KEY=VALUE Zeilen aus einer .env-Datei.
    Unterstützt Kommentare (#) und optional gequotete Werte.
    Benötigt keine externen Bibliotheken.
    """
    env: dict[str, str] = {}
    with env_file.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Anführungszeichen entfernen falls vorhanden ("wert" oder 'wert')
            if len(value) >= 2 and value[0] in ('"', "'") and value[0] == value[-1]:
                value = value[1:-1]
            env[key] = value
    return env


def venv_python() -> Path:
    """Pfad zum Python-Interpreter in der venv – plattformabhängig."""
    if sys.platform == "win32":
        return ROOT / "venv" / "Scripts" / "python.exe"
    return ROOT / "venv" / "bin" / "python"


def setup_venv() -> None:
    """Legt die venv an (nur beim ersten Start) und installiert Abhängigkeiten."""
    venv_dir = ROOT / "venv"
    if not venv_dir.exists():
        print("[INFO] Erstelle virtuelle Python-Umgebung ...")
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            check=True,
        )

    print("[INFO] Installiere Abhängigkeiten ...")
    subprocess.run(
        [
            str(venv_python()),
            "-m", "pip", "install", "-q", "-r",
            str(ROOT / "requirements.txt"),
        ],
        check=True,
    )


def wait_for_server(url: str, timeout: int = 20) -> bool:
    """Wartet bis der Server antwortet – nutzt nur stdlib (urllib)."""
    print("[INFO] Warte auf Server", end="", flush=True)
    for _ in range(timeout):
        time.sleep(1)
        try:
            urllib.request.urlopen(url, timeout=1)
            print(" bereit")
            return True
        except Exception:
            print(".", end="", flush=True)
    print(" (Timeout)")
    return False


def _pause_and_exit(code: int) -> None:
    """Auf Windows: kurze Pause damit die Fehlermeldung lesbar bleibt."""
    if sys.platform == "win32":
        input("\nEnter drücken zum Beenden ...")
    sys.exit(code)


# ---------------------------------------------------------------------------
# Hauptprogramm
# ---------------------------------------------------------------------------

def main() -> None:
    check_python_version()

    # .env laden
    env_file = ROOT / ".env"
    if not env_file.exists():
        print("[FEHLER] .env Datei nicht gefunden!")
        print(f"  Kopiere '{ROOT / '.env.example'}' nach '{env_file}'")
        print("  und trage deine API-Schlüssel ein.")
        _pause_and_exit(1)

    env_vars = load_env(env_file)
    os.environ.update(env_vars)

    # venv + Abhängigkeiten
    setup_venv()

    # Scan-Ordner anlegen (absoluter Pfad, falls in .env konfiguriert)
    scan_eingang = Path(os.environ.get("SCAN_EINGANG", ROOT / "Scanner-Eingang"))
    archiv = Path(os.environ.get("ARCHIV_ORDNER", ROOT / "Archiv"))
    scan_eingang.mkdir(parents=True, exist_ok=True)
    archiv.mkdir(parents=True, exist_ok=True)

    # Prozesse
    server_proc: subprocess.Popen | None = None
    watcher_proc: subprocess.Popen | None = None

    def cleanup(signum=None, frame=None) -> None:
        print("\n[INFO] Beende Server und Watcher ...")
        for proc in (watcher_proc, server_proc):
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    # SIGTERM nicht auf Windows registrieren – dort ist es nicht zuverlässig
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, cleanup)

    # Server starten
    print("[INFO] Starte API-Server ...")
    server_proc = subprocess.Popen(
        [
            str(venv_python()), "-m", "uvicorn",
            "app.main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
        ],
        cwd=str(ROOT),
        env=os.environ.copy(),
    )

    wait_for_server("http://localhost:8000/health")

    # Info-Banner
    print()
    print("=" * 60)
    print("  LeadFactory läuft vollautomatisch!")
    print()
    print(f"  Scanner-Eingang : {scan_eingang}")
    print(f"  Archiv          : {archiv}")
    print(f"  API-Docs        : http://localhost:8000/docs")
    print()
    print("  Scanne Dokumente in den Ordner 'Scanner-Eingang'.")
    print("  Der Agent verarbeitet sie automatisch.")
    print()
    print("  Stoppen mit: Strg+C / Ctrl+C")
    print("=" * 60)
    print()

    # Watcher starten und auf ihn warten
    watcher_proc = subprocess.Popen(
        [str(venv_python()), str(ROOT / "watcher.py")],
        cwd=str(ROOT),
        env=os.environ.copy(),
    )

    try:
        watcher_proc.wait()
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
