"""
CRM-Light: Baut automatisch eine Kontaktdatenbank aus eingehenden Briefen auf.

Kein extra AI-Call nötig – nutzt die bereits extrahierten Felder aus BriefAnalyse.
Bei jedem eingehenden Brief wird der Absender als Kontakt gespeichert oder aktualisiert.
"""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.brief import BriefAnalyse
from app.models.db_models import Kontakt

logger = logging.getLogger("leadfactory.crm")


def upsert_kontakt(analyse: BriefAnalyse, db: Session) -> Kontakt:
    """
    Erstellt einen neuen Kontakt oder aktualisiert einen bestehenden.
    Matching: Firmenname (bevorzugt) oder Absendername.
    """
    absender = analyse.absender_name
    if not absender or absender == "Unbekannt":
        return None

    # Firma aus Adresse extrahieren (erste Zeile = oft Firmenname)
    firma = _extrahiere_firma(absender, analyse.absender_adresse)

    # Existierenden Kontakt suchen
    kontakt = _finde_kontakt(db, firma or absender)

    if kontakt:
        kontakt.letzter_kontakt = datetime.utcnow()
        kontakt.anzahl_briefe += 1
        # Fehlende Daten ergänzen
        if not kontakt.adresse and analyse.absender_adresse:
            kontakt.adresse = analyse.absender_adresse
        logger.info(f"Kontakt aktualisiert: {kontakt.name or kontakt.firma} (#{kontakt.anzahl_briefe} Briefe)")
    else:
        kontakt = Kontakt(
            name=absender if not firma else absender,
            firma=firma,
            adresse=analyse.absender_adresse,
        )
        db.add(kontakt)
        logger.info(f"Neuer Kontakt: {absender}")

    return kontakt


def _finde_kontakt(db: Session, suchbegriff: str) -> Kontakt | None:
    """Sucht nach Name oder Firmenname (case-insensitive)."""
    suchbegriff_lower = suchbegriff.lower()
    kontakte = db.query(Kontakt).all()
    for k in kontakte:
        if (k.firma and suchbegriff_lower in k.firma.lower()) or \
           (k.name and suchbegriff_lower in k.name.lower()):
            return k
    return None


def _extrahiere_firma(absender: str, adresse: str | None) -> str | None:
    """
    Heuristik: Wenn der Absendername typische Firmenkennzeichen enthält,
    gilt er als Firmenname.
    """
    firmenkennzeichen = ["GmbH", "AG", "KG", "OHG", "UG", "e.V.", "e.G.",
                         "GbR", "Inc", "Ltd", "SE", "mbH", "Verlag", "Bank",
                         "Versicherung", "Finanzamt", "Amt", "Behörde"]
    for kz in firmenkennzeichen:
        if kz.lower() in absender.lower():
            return absender
    return None
