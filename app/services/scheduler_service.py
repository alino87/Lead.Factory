"""
Scheduler: Tägliche Hintergrundaufgaben.

- 07:00 Uhr: Verträge auf ablaufende Kündigungsfristen prüfen
- Logging aller Warnungen
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("leadfactory.scheduler")

_scheduler = BackgroundScheduler(timezone="Europe/Berlin")


def start() -> None:
    _scheduler.add_job(
        _pruefe_vertragslaufzeiten,
        trigger=CronTrigger(hour=7, minute=0),
        id="vertrag_deadlines",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler gestartet – Vertragsfristen-Check täglich um 07:00")


def stop() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler gestoppt")


def _pruefe_vertragslaufzeiten() -> None:
    """Wird täglich um 07:00 aufgerufen. Loggt Warnungen für ablaufende Verträge."""
    from app.db import SessionLocal
    from app.services import vertrag_service

    db = SessionLocal()
    try:
        ablaufende = vertrag_service.prüfe_deadlines(db)
        if not ablaufende:
            logger.info("Vertragsfristen-Check: Keine Warnungen heute.")
        else:
            logger.warning(
                f"Vertragsfristen-Check: {len(ablaufende)} Vertrag/Verträge "
                f"erfordern bald eine Kündigung!"
            )
    finally:
        db.close()
