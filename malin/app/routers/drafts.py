"""
Draft endpoints: list, create (dev), approve, reject, edit, execute.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from malin.app.auth import get_current_tenant
from malin.app.db import get_db
from malin.app.errors import NotFoundError
from malin.app.models.tables import (
    AuditAction, AuditLog, Document, Draft, DraftStatus,
    Execution, Tenant,
)
from malin.app.services.draft_machine import validate_can_execute, validate_transition

router = APIRouter(prefix="/drafts", tags=["Drafts"])


# ── Request schemas ───────────────────────────────────────────────────────────

class DraftCreateRequest(BaseModel):
    document_id: uuid.UUID
    title: str = ""
    body: dict = {}


class DraftEditRequest(BaseModel):
    title: str | None = None
    body: dict | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_drafts(
    document_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    q = select(Draft).where(Draft.tenant_id == tenant.id)
    if document_id:
        q = q.where(Draft.document_id == document_id)
    q = q.order_by(Draft.created_at.desc())
    result = await db.execute(q)
    return [_draft_to_dict(d) for d in result.scalars().all()]


@router.post("/create")
async def create_draft(
    req: DraftCreateRequest,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """Dev/test endpoint to manually create a draft."""
    # Verify document belongs to tenant
    doc_result = await db.execute(
        select(Document).where(
            Document.id == req.document_id,
            Document.tenant_id == tenant.id,
        )
    )
    if not doc_result.scalar_one_or_none():
        raise NotFoundError("Document", str(req.document_id))

    draft = Draft(
        document_id=req.document_id,
        tenant_id=tenant.id,
        title=req.title,
        body=req.body,
        version=1,
        status=DraftStatus.DRAFT,
    )
    db.add(draft)

    db.add(AuditLog(
        tenant_id=tenant.id,
        action=AuditAction.DRAFT_CREATED,
        entity_type="draft",
        entity_id=draft.id,
        diff={"title": req.title, "body": req.body},
    ))

    await db.commit()
    await db.refresh(draft)
    return _draft_to_dict(draft)


@router.post("/{draft_id}/approve")
async def approve_draft(
    draft_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    draft = await _get_draft(db, draft_id, tenant.id)
    validate_transition(draft.status, DraftStatus.APPROVED)
    draft.status = DraftStatus.APPROVED

    db.add(AuditLog(
        tenant_id=tenant.id,
        action=AuditAction.DRAFT_APPROVED,
        entity_type="draft",
        entity_id=draft.id,
        diff={"from_status": "DRAFT", "to_status": "APPROVED"},
    ))

    await db.commit()
    await db.refresh(draft)
    return _draft_to_dict(draft)


@router.post("/{draft_id}/reject")
async def reject_draft(
    draft_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    draft = await _get_draft(db, draft_id, tenant.id)
    validate_transition(draft.status, DraftStatus.REJECTED)
    draft.status = DraftStatus.REJECTED

    db.add(AuditLog(
        tenant_id=tenant.id,
        action=AuditAction.DRAFT_REJECTED,
        entity_type="draft",
        entity_id=draft.id,
        diff={"from_status": draft.status.value, "to_status": "REJECTED"},
    ))

    await db.commit()
    await db.refresh(draft)
    return _draft_to_dict(draft)


@router.post("/{draft_id}/edit")
async def edit_draft(
    draft_id: uuid.UUID,
    req: DraftEditRequest,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """Creates a new version of the draft (immutable versions)."""
    old_draft = await _get_draft(db, draft_id, tenant.id)

    # If rejected, allow re-edit by transitioning back to DRAFT
    if old_draft.status == DraftStatus.REJECTED:
        validate_transition(old_draft.status, DraftStatus.DRAFT)

    old_title = old_draft.title
    old_body = old_draft.body

    new_draft = Draft(
        document_id=old_draft.document_id,
        tenant_id=tenant.id,
        title=req.title if req.title is not None else old_draft.title,
        body=req.body if req.body is not None else old_draft.body,
        version=old_draft.version + 1,
        status=DraftStatus.DRAFT,
        parent_id=old_draft.id,
    )
    db.add(new_draft)

    # Build diff
    diff = {}
    if req.title is not None and req.title != old_title:
        diff["title"] = {"old": old_title, "new": req.title}
    if req.body is not None and req.body != old_body:
        diff["body"] = {"old": old_body, "new": req.body}

    db.add(AuditLog(
        tenant_id=tenant.id,
        action=AuditAction.DRAFT_EDITED,
        entity_type="draft",
        entity_id=new_draft.id,
        diff={
            "parent_id": str(old_draft.id),
            "from_version": old_draft.version,
            "to_version": new_draft.version,
            **diff,
        },
    ))

    await db.commit()
    await db.refresh(new_draft)
    return _draft_to_dict(new_draft)


@router.post("/{draft_id}/execute/calendar_ics")
async def execute_calendar_ics(
    draft_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """
    Execute the draft as a calendar ICS action.
    MUST be APPROVED – this is the "Draft is Law" guard.
    """
    draft = await _get_draft(db, draft_id, tenant.id)

    # Core guard: only APPROVED drafts can be executed
    validate_can_execute(draft.status)

    # Stub ICS generation
    ics_data = (
        "BEGIN:VCALENDAR\n"
        "VERSION:2.0\n"
        "PRODID:-//MALIN//Phase1//EN\n"
        f"BEGIN:VEVENT\n"
        f"SUMMARY:{draft.title}\n"
        f"DESCRIPTION:Generated from draft {draft.id}\n"
        f"END:VEVENT\n"
        "END:VCALENDAR\n"
    )

    # Write execution receipt
    execution = Execution(
        draft_id=draft.id,
        tenant_id=tenant.id,
        action_type="calendar_ics",
        result={"ics": ics_data, "stub": True},
    )
    db.add(execution)

    # Transition to EXECUTED
    validate_transition(draft.status, DraftStatus.EXECUTED)
    draft.status = DraftStatus.EXECUTED

    db.add(AuditLog(
        tenant_id=tenant.id,
        action=AuditAction.DRAFT_EXECUTED,
        entity_type="draft",
        entity_id=draft.id,
        diff={
            "action_type": "calendar_ics",
            "execution_id": str(execution.id),
        },
    ))

    await db.commit()
    await db.refresh(draft)
    await db.refresh(execution)

    return {
        "draft": _draft_to_dict(draft),
        "execution": {
            "id": str(execution.id),
            "action_type": execution.action_type,
            "result": execution.result,
            "executed_at": execution.executed_at.isoformat() if execution.executed_at else None,
        },
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_draft(db: AsyncSession, draft_id: uuid.UUID, tenant_id: uuid.UUID) -> Draft:
    result = await db.execute(
        select(Draft).where(Draft.id == draft_id, Draft.tenant_id == tenant_id)
    )
    draft = result.scalar_one_or_none()
    if not draft:
        raise NotFoundError("Draft", str(draft_id))
    return draft


def _draft_to_dict(d: Draft) -> dict:
    return {
        "id": str(d.id),
        "document_id": str(d.document_id),
        "version": d.version,
        "status": d.status.value,
        "title": d.title,
        "body": d.body,
        "parent_id": str(d.parent_id) if d.parent_id else None,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }
