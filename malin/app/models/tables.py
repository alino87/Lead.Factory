"""
MALIN v0.1 — Datenmodell exakt nach SPEC.md §5.

Jede Tabelle, jedes Feld, jedes Enum 1:1 wie spezifiziert.
"Draft is Law" — kein Feld erfunden, keins weggelassen.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey, Index,
    Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from malin.app.db import Base


# ── Enums (SPEC §5) ──────────────────────────────────────────────────────────

class TenantStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class TenantPlan(str, enum.Enum):
    FREE = "FREE"
    STARTER = "STARTER"
    BUSINESS = "BUSINESS"
    ENTERPRISE = "ENTERPRISE"


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    REVIEWER = "REVIEWER"
    VIEWER = "VIEWER"


class DocumentSource(str, enum.Enum):
    UPLOAD = "UPLOAD"
    EMAIL = "EMAIL"


class DocumentStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    OCR_DONE = "OCR_DONE"
    INTELLIGENCE_DONE = "INTELLIGENCE_DONE"
    NEEDS_ATTENTION = "NEEDS_ATTENTION"


class DocType(str, enum.Enum):
    AUTHORITY = "AUTHORITY"
    INVOICE = "INVOICE"
    CONTRACT = "CONTRACT"
    CRM = "CRM"
    GENERAL = "GENERAL"


class ModuleType(str, enum.Enum):
    INBOX = "INBOX"
    INVOICE = "INVOICE"
    CONTRACT = "CONTRACT"
    CRM = "CRM"
    AUTHORITY = "AUTHORITY"
    ARCHIVE = "ARCHIVE"
    SPEND = "SPEND"


class ActionType(str, enum.Enum):
    CALENDAR = "CALENDAR"
    REPLY_EMAIL = "REPLY_EMAIL"
    PAYMENT_EXPORT = "PAYMENT_EXPORT"
    DATEV_EXPORT = "DATEV_EXPORT"
    SEPA_EXPORT = "SEPA_EXPORT"
    ZIP_EXPORT = "ZIP_EXPORT"
    TAGGING = "TAGGING"
    SPEND_REPORT = "SPEND_REPORT"


class DraftStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    ARCHIVED = "ARCHIVED"


class ActorType(str, enum.Enum):
    SYSTEM = "SYSTEM"
    USER = "USER"


class AuditAction(str, enum.Enum):
    CREATE_DRAFT = "CREATE_DRAFT"
    UPDATE_DRAFT = "UPDATE_DRAFT"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    EXECUTE = "EXECUTE"
    ERROR = "ERROR"


class ExecutionType(str, enum.Enum):
    CALENDAR_ICS = "CALENDAR_ICS"
    SEPA_EXPORT = "SEPA_EXPORT"
    DATEV_EXPORT = "DATEV_EXPORT"
    ZIP_EXPORT = "ZIP_EXPORT"


# ── Tables (SPEC §5.1) ───────────────────────────────────────────────────────

class Tenant(Base):
    """SPEC §5.1 — tenants"""
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    api_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, name="tenant_status"), default=TenantStatus.ACTIVE
    )
    plan: Mapped[TenantPlan] = mapped_column(
        Enum(TenantPlan, name="tenant_plan"), default=TenantPlan.FREE
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    users: Mapped[list["User"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")


class User(Base):
    """SPEC §5.1 — users"""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(300), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), default=UserRole.REVIEWER
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="users")

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )


class Document(Base):
    """SPEC §5.1 — documents"""
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    source: Mapped[DocumentSource] = mapped_column(
        Enum(DocumentSource, name="document_source"), default=DocumentSource.UPLOAD
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status"), default=DocumentStatus.UPLOADED
    )
    doc_type: Mapped[DocType | None] = mapped_column(
        Enum(DocType, name="doc_type"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="documents")
    drafts: Mapped[list["Draft"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    ocr_spans: Mapped[list["OcrSpan"]] = relationship(back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_documents_tenant_status", "tenant_id", "status"),
    )


class OcrSpan(Base):
    """SPEC §5.1 — ocr_spans"""
    __tablename__ = "ocr_spans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    page: Mapped[int] = mapped_column(Integer, default=0)
    bbox: Mapped[dict | None] = mapped_column(JSONB, default=dict)    # [x, y, w, h]
    text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    document: Mapped["Document"] = relationship(back_populates="ocr_spans")

    __table_args__ = (
        Index("ix_ocr_spans_document", "document_id"),
    )


class Draft(Base):
    """
    SPEC §5.1 — drafts (versioned).
    version_group_id gruppiert alle Versionen eines logischen Drafts.
    """
    __tablename__ = "drafts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    version_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    module_type: Mapped[ModuleType] = mapped_column(
        Enum(ModuleType, name="module_type"), nullable=False
    )
    action_type: Mapped[ActionType] = mapped_column(
        Enum(ActionType, name="action_type"), nullable=False
    )
    payload: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    confidence: Mapped[dict | None] = mapped_column(JSONB, default=dict)    # {field: 0..1}
    evidence: Mapped[list | None] = mapped_column(JSONB, default=list)      # [{field, span_id}]
    status: Mapped[DraftStatus] = mapped_column(
        Enum(DraftStatus, name="draft_status"), default=DraftStatus.DRAFT
    )
    review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    document: Mapped["Document"] = relationship(back_populates="drafts")
    executions: Mapped[list["Execution"]] = relationship(back_populates="draft", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_drafts_version_group", "version_group_id", "version"),
        Index("ix_drafts_document", "document_id"),
        Index("ix_drafts_tenant_status", "tenant_id", "status"),
    )


class AuditLog(Base):
    """SPEC §5.1 — audit_logs (append-only)"""
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    draft_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    actor_type: Mapped[ActorType] = mapped_column(
        Enum(ActorType, name="actor_type"), default=ActorType.SYSTEM
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action"), nullable=False
    )
    before_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    diff: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_audit_logs_draft", "draft_id"),
        Index("ix_audit_logs_tenant_created", "tenant_id", "created_at"),
    )


class Execution(Base):
    """SPEC §5.1 — executions (receipts)"""
    __tablename__ = "executions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drafts.id"), nullable=False
    )
    execution_type: Mapped[ExecutionType] = mapped_column(
        Enum(ExecutionType, name="execution_type"), nullable=False
    )
    receipt: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    executed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    draft: Mapped["Draft"] = relationship(back_populates="executions")


class Usage(Base):
    """Usage counters scaffold — populated in later phases."""
    __tablename__ = "usage"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    metric: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[int] = mapped_column(Integer, default=0)
    period: Mapped[str] = mapped_column(String(20), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "metric", "period", name="uq_usage_tenant_metric_period"),
    )
