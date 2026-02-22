import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import archiv, brief, buchhaltung, crm, dashboard, enrich, vertrag

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-30s  %(levelname)-7s  %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────
    from app.db import create_tables
    from app.services import scheduler_service

    create_tables()
    scheduler_service.start()

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    scheduler_service.stop()


app = FastAPI(
    title="KI-Büroassistent",
    description=(
        "All-in-One KI-Assistent für Einzelunternehmer und KMU.\n\n"
        "**Module:**\n"
        "- 📬 **Briefpost-Agent** – Scans klassifizieren, Antworten generieren\n"
        "- 💶 **Buchhaltung** – Rechnungen erfassen, EÜR exportieren\n"
        "- 📋 **Vertragsmanager** – Verträge tracken, Fristen nie mehr verpassen\n"
        "- 👥 **CRM-Light** – Kontaktdatenbank aus Briefen\n"
        "- 🏛️ **Behördenassistent** – Behördenbriefe in einfacher Sprache\n"
        "- 🗂️ **Archiv** – Alle Dokumente durchsuchbar\n"
        "- 📊 **Dashboard** – Alles auf einen Blick\n"
        "- 🎯 **Lead-Enrichment** – B2B Sales Intelligence"
    ),
    version="3.0.0",
    lifespan=lifespan,
)

app.include_router(enrich.router)
app.include_router(brief.router)
app.include_router(buchhaltung.router)
app.include_router(vertrag.router)
app.include_router(crm.router)
app.include_router(archiv.router)
app.include_router(dashboard.router)


@app.get("/health", tags=["System"])
async def health():
    from app.db import engine
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "operational", "database": "ok" if db_ok else "error"}
