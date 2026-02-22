"""
Verarbeitungs-Pipeline: Verbindet den Briefpost-Agenten mit allen Modulen.

Wenn ein Dokument verarbeitet wurde, leitet diese Pipeline es automatisch
an das richtige Modul weiter – ohne manuelle Eingriffe.

Routing:
  Rechnung / Mahnung    → Buchhaltungsmodul
  Vertragsunterlagen    → Vertragsmanager
  Behördenbrief         → Behördenassistent
  Alle Briefe           → CRM (Kontakt upsert)
  Alle Briefe           → Termine in DB speichern
"""

import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.brief import BriefAnalyse
from app.models.db_models import Document, Termin

logger = logging.getLogger("leadfactory.pipeline")

# Mapping Kategorie → Handler-Funktionen (werden lazy importiert)
_KATEGORIE_HANDLER = {
    "Rechnung":           ["buchhaltung"],
    "Mahnung":            ["buchhaltung"],
    "Vertragsunterlagen": ["vertrag"],
    "Behördenbrief":      ["behoerden"],
}


def verarbeite_im_hintergrund(
    analyse: BriefAnalyse,
    filename: str,
    archive_path: str | None = None,
) -> None:
    """
    Einstiegspunkt für FastAPI BackgroundTasks.
    Erstellt eine eigene DB-Session (unabhängig vom Request).
    """
    db = SessionLocal()
    try:
        _verarbeite(analyse, filename, archive_path, db)
    except Exception as e:
        logger.error(f"Pipeline-Fehler für '{filename}': {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


def _verarbeite(
    analyse: BriefAnalyse,
    filename: str,
    archive_path: str | None,
    db: Session,
) -> Document:
    # 1. Dokument in DB speichern
    doc = Document(
        filename=filename,
        archive_path=archive_path,
        kategorie=analyse.kategorie,
        prioritaet=analyse.prioritaet,
        absender_name=analyse.absender_name,
        absender_adresse=analyse.absender_adresse,
        empfaenger_name=analyse.empfaenger_name,
        datum=analyse.datum,
        betreff=analyse.betreff,
        zusammenfassung=analyse.zusammenfassung,
        antwort_entwurf=analyse.antwort_entwurf,
        antwort_erforderlich=analyse.antwort_erforderlich,
        verarbeitungsfehler=analyse.verarbeitungsfehler,
        processed_at=datetime.utcnow(),
        raw_json=analyse.model_dump_json(),
    )
    db.add(doc)
    db.flush()  # doc.id wird benötigt

    # 2. Termine speichern
    for t in analyse.termine:
        db.add(Termin(
            document_id=doc.id,
            titel=t.titel,
            datum=t.datum,
            uhrzeit=t.uhrzeit,
            beschreibung=t.beschreibung,
            ist_frist=t.frist,
        ))

    # 3. Modul-Routing
    handlers = _KATEGORIE_HANDLER.get(analyse.kategorie, [])

    if "buchhaltung" in handlers:
        try:
            from app.services import buchhaltung_service
            buchhaltung_service.verarbeite(doc, analyse, db)
        except Exception as e:
            logger.error(f"Buchhaltung-Fehler: {e}", exc_info=True)

    if "vertrag" in handlers:
        try:
            from app.services import vertrag_service
            vertrag_service.verarbeite(doc, analyse, db)
        except Exception as e:
            logger.error(f"Vertrags-Fehler: {e}", exc_info=True)

    if "behoerden" in handlers:
        try:
            from app.services import behoerden_service
            behoerden_service.verarbeite(doc, analyse, db)
        except Exception as e:
            logger.error(f"Behörden-Fehler: {e}", exc_info=True)

    # Kontakt aus jedem eingehenden Brief extrahieren
    if analyse.absender_name and analyse.absender_name != "Unbekannt":
        try:
            from app.services import crm_service
            crm_service.upsert_kontakt(analyse, db)
        except Exception as e:
            logger.error(f"CRM-Fehler: {e}", exc_info=True)

    db.commit()
    logger.info(f"Pipeline abgeschlossen: '{filename}' → {analyse.kategorie} (doc.id={doc.id})")
    return doc
