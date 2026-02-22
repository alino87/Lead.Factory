#!/usr/bin/env bash
# ============================================================
#  LeadFactory – Vollautomatischer Starter für macOS / Linux
#  Startet Server + Ordner-Watcher gleichzeitig.
#  Voraussetzung: Python 3.10+
# ============================================================

set -e

# --- .env laden ---
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
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

# --- Scan-Eingang und Archiv anlegen ---
mkdir -p "${SCAN_EINGANG:-Scanner-Eingang}"
mkdir -p "${ARCHIV_ORDNER:-Archiv}"

# --- Aufräumen beim Beenden (Strg+C) ---
SERVER_PID=""
cleanup() {
    echo ""
    echo "[INFO] Beende Server und Watcher ..."
    if [ -n "$SERVER_PID" ]; then
        kill "$SERVER_PID" 2>/dev/null || true
    fi
    exit 0
}
trap cleanup INT TERM

# --- Server im Hintergrund starten ---
echo "[INFO] Starte API-Server ..."
venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 &
SERVER_PID=$!

# Warten bis Server antwortet
echo -n "[INFO] Warte auf Server"
for i in $(seq 1 15); do
    sleep 1
    if curl -s http://localhost:8000/health >/dev/null 2>&1; then
        echo " OK"
        break
    fi
    echo -n "."
done

# --- Info ausgeben ---
echo ""
echo "============================================================"
echo " LeadFactory läuft vollautomatisch!"
echo ""
echo " Scanner-Eingang:  $(pwd)/${SCAN_EINGANG:-Scanner-Eingang}"
echo " Archiv:           $(pwd)/${ARCHIV_ORDNER:-Archiv}"
echo " API-Docs:         http://localhost:8000/docs"
echo ""
echo " Scanne Dokumente in den Ordner 'Scanner-Eingang'"
echo " Der Agent verarbeitet sie automatisch."
echo ""
echo " Stoppen mit: Ctrl+C"
echo "============================================================"
echo ""

# --- Watcher im Vordergrund starten ---
venv/bin/python watcher.py
