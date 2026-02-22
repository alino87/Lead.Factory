#!/usr/bin/env bash
# ============================================================
#  LeadFactory – Starter für macOS / Linux
#  Voraussetzung: Python 3.10+ muss installiert sein
# ============================================================

set -e

# --- .env laden ---
if [ -f .env ]; then
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
else
    echo "[FEHLER] .env Datei nicht gefunden!"
    echo "Kopiere .env.example nach .env und trage deine API-Schluessel ein."
    exit 1
fi

# --- Python-Version prüfen (min. 3.10) ---
PY=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
REQUIRED="3.10"
if [ "$(printf '%s\n' "$REQUIRED" "$PY" | sort -V | head -n1)" != "$REQUIRED" ]; then
    echo "[FEHLER] Python $REQUIRED oder neuer wird benötigt (gefunden: $PY)"
    echo "macOS:  brew install python@3.12"
    echo "Ubuntu: sudo apt install python3.12"
    exit 1
fi

# --- Virtuelle Umgebung anlegen (nur beim ersten Start) ---
if [ ! -d venv ]; then
    echo "[INFO] Erstelle virtuelle Python-Umgebung..."
    python3 -m venv venv
fi

# --- Abhängigkeiten installieren ---
echo "[INFO] Installiere Abhaengigkeiten..."
venv/bin/pip install -q -r requirements.txt

# --- Server starten ---
echo ""
echo "============================================================"
echo " LeadFactory läuft unter: http://localhost:8000"
echo " API-Docs:                http://localhost:8000/docs"
echo " Stoppen mit:             Ctrl+C"
echo "============================================================"
echo ""
venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
