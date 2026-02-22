@echo off
REM ============================================================
REM  LeadFactory – Starter für Windows
REM  Voraussetzung: Python 3.10+ muss installiert sein
REM  https://www.python.org/downloads/
REM ============================================================

setlocal

REM --- .env laden (KEY=VALUE Zeilen, Kommentare ignorieren) ---
if exist .env (
    for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
        set "%%A=%%B"
    )
) else (
    echo [FEHLER] .env Datei nicht gefunden!
    echo Kopiere .env.example nach .env und trage deine API-Schluessel ein.
    pause
    exit /b 1
)

REM --- Virtuelle Umgebung anlegen (nur beim ersten Start) ---
if not exist venv (
    echo [INFO] Erstelle virtuelle Python-Umgebung...
    python -m venv venv
)

REM --- Abhängigkeiten installieren ---
echo [INFO] Installiere Abhaengigkeiten...
call venv\Scripts\pip install -q -r requirements.txt

REM --- Server starten ---
echo.
echo ============================================================
echo  LeadFactory laeuft unter: http://localhost:8000
echo  API-Docs:                 http://localhost:8000/docs
echo  Stoppen mit:              Strg+C
echo ============================================================
echo.
call venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

endlocal
