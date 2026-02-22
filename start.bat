@echo off
REM ============================================================
REM  LeadFactory – Vollautomatischer Starter für Windows
REM  Startet Server + Ordner-Watcher gleichzeitig.
REM  Voraussetzung: Python 3.10+  https://www.python.org/downloads/
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

REM --- Scan-Eingang und Archiv anlegen ---
if not exist "Scanner-Eingang" mkdir "Scanner-Eingang"
if not exist "Archiv"          mkdir "Archiv"

REM --- Server im Hintergrund starten ---
echo.
echo [INFO] Starte API-Server ...
start "LeadFactory Server" /min venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000

REM --- Kurz warten bis Server hochgefahren ist ---
timeout /t 3 /nobreak >nul

REM --- Watcher im Vordergrund starten ---
echo ============================================================
echo  LeadFactory laeuft vollautomatisch!
echo.
echo  Scanner-Eingang:  %CD%\Scanner-Eingang
echo  Archiv:           %CD%\Archiv
echo  API-Docs:         http://localhost:8000/docs
echo.
echo  Scanne Dokumente in den Ordner "Scanner-Eingang"
echo  Der Agent verarbeitet sie automatisch.
echo.
echo  Stoppen mit: Strg+C (beide Fenster schliessen)
echo ============================================================
echo.
venv\Scripts\python watcher.py

endlocal
