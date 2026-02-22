"""
SQLAlchemy-Datenbankmodelle für alle Module des KI-Büroassistenten.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey,
    Integer, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Document(Base):
    """Jedes verarbeitete Dokument landet hier – Basis für alle Module."""
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(500))
    archive_path: Mapped[Optional[str]] = mapped_column(String(1000))
    kategorie: Mapped[str] = mapped_column(String(100))
    prioritaet: Mapped[str] = mapped_column(String(50))
    absender_name: Mapped[Optional[str]] = mapped_column(String(300))
    absender_adresse: Mapped[Optional[str]] = mapped_column(Text)
    empfaenger_name: Mapped[Optional[str]] = mapped_column(String(300))
    datum: Mapped[Optional[str]] = mapped_column(String(20))       # ISO YYYY-MM-DD
    betreff: Mapped[str] = mapped_column(String(500), default="")
    zusammenfassung: Mapped[Optional[str]] = mapped_column(Text)
    antwort_entwurf: Mapped[Optional[str]] = mapped_column(Text)
    antwort_erforderlich: Mapped[bool] = mapped_column(Boolean, default=False)
    verarbeitungsfehler: Mapped[Optional[str]] = mapped_column(String(200))
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    raw_json: Mapped[Optional[str]] = mapped_column(Text)

    # Relationen
    rechnungen: Mapped[list["Rechnung"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    vertraege: Mapped[list["Vertrag"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    behoerdenpost: Mapped[list["Behoerdenpost"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    termine: Mapped[list["Termin"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Rechnung(Base):
    """Rechnungen und Mahnungen – Basis für Buchhaltungsmodul."""
    __tablename__ = "rechnungen"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    lieferant: Mapped[Optional[str]] = mapped_column(String(300))
    rechnungsnummer: Mapped[Optional[str]] = mapped_column(String(200))
    rechnungsdatum: Mapped[Optional[date]] = mapped_column(Date)
    faelligkeitsdatum: Mapped[Optional[date]] = mapped_column(Date)
    betrag_netto: Mapped[Optional[float]] = mapped_column(Float)
    ust_satz: Mapped[Optional[float]] = mapped_column(Float)   # 0.19 | 0.07 | 0.0
    betrag_ust: Mapped[Optional[float]] = mapped_column(Float)
    betrag_brutto: Mapped[Optional[float]] = mapped_column(Float)
    kategorie_buchhaltung: Mapped[Optional[str]] = mapped_column(String(200))
    vorsteuer_abzugsfaehig: Mapped[bool] = mapped_column(Boolean, default=True)
    bezahlt: Mapped[bool] = mapped_column(Boolean, default=False)
    iban: Mapped[Optional[str]] = mapped_column(String(50))
    ist_mahnung: Mapped[bool] = mapped_column(Boolean, default=False)

    document: Mapped["Document"] = relationship(back_populates="rechnungen")


class Vertrag(Base):
    """Verträge – Basis für Vertragsmanager-Modul."""
    __tablename__ = "vertraege"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[Optional[int]] = mapped_column(ForeignKey("documents.id"), nullable=True)
    vertragspartner: Mapped[Optional[str]] = mapped_column(String(300))
    vertragsart: Mapped[Optional[str]] = mapped_column(String(200))
    beginn: Mapped[Optional[date]] = mapped_column(Date)
    ende: Mapped[Optional[date]] = mapped_column(Date)
    laufzeit_monate: Mapped[Optional[int]] = mapped_column(Integer)
    kuendigungsfrist_tage: Mapped[Optional[int]] = mapped_column(Integer)
    naechste_kuendigung_bis: Mapped[Optional[date]] = mapped_column(Date)   # berechnet
    monatliche_kosten: Mapped[Optional[float]] = mapped_column(Float)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)
    kuendigungswarnung_gesendet: Mapped[bool] = mapped_column(Boolean, default=False)
    notizen: Mapped[Optional[str]] = mapped_column(Text)

    document: Mapped[Optional["Document"]] = relationship(back_populates="vertraege")


class Kontakt(Base):
    """Kontakte aus eingehenden Briefen – Mini-CRM."""
    __tablename__ = "kontakte"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[Optional[str]] = mapped_column(String(300))
    firma: Mapped[Optional[str]] = mapped_column(String(300))
    email: Mapped[Optional[str]] = mapped_column(String(300))
    telefon: Mapped[Optional[str]] = mapped_column(String(100))
    adresse: Mapped[Optional[str]] = mapped_column(Text)
    erster_kontakt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    letzter_kontakt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    anzahl_briefe: Mapped[int] = mapped_column(Integer, default=1)
    notizen: Mapped[Optional[str]] = mapped_column(Text)


class Behoerdenpost(Base):
    """Behördenbriefe – vereinfachte Erklärung + Checkliste."""
    __tablename__ = "behoerdenpost"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    behoerde: Mapped[Optional[str]] = mapped_column(String(300))
    aktenzeichen: Mapped[Optional[str]] = mapped_column(String(200))
    betreff: Mapped[Optional[str]] = mapped_column(String(500))
    frist: Mapped[Optional[date]] = mapped_column(Date)
    erklaerung_einfach: Mapped[Optional[str]] = mapped_column(Text)   # Claude: einfache Sprache
    was_zu_tun: Mapped[Optional[str]] = mapped_column(Text)            # Checkliste
    erledigt: Mapped[bool] = mapped_column(Boolean, default=False)

    document: Mapped["Document"] = relationship(back_populates="behoerdenpost")


class Termin(Base):
    """Termine und Fristen aus Briefen."""
    __tablename__ = "termine"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    titel: Mapped[str] = mapped_column(String(300))
    datum: Mapped[Optional[str]] = mapped_column(String(20))     # ISO YYYY-MM-DD
    uhrzeit: Mapped[Optional[str]] = mapped_column(String(10))   # HH:MM
    beschreibung: Mapped[Optional[str]] = mapped_column(Text)
    ist_frist: Mapped[bool] = mapped_column(Boolean, default=False)
    erledigt: Mapped[bool] = mapped_column(Boolean, default=False)

    document: Mapped["Document"] = relationship(back_populates="termine")
