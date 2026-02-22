"""
Document endpoints: upload, list, get.
"""

import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from malin.app.auth import get_current_tenant
from malin.app.db import get_db
from malin.app.errors import NotFoundError
from malin.app.models.tables import AuditAction, AuditLog, Document, Tenant
from malin.app.services.storage import upload_file

router = APIRouter(prefix="/documents", tags=["Documents"])

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        from malin.app.errors import MalinError
        raise MalinError("FILE_TOO_LARGE", f"Max file size is {MAX_FILE_SIZE // (1024*1024)} MB")

    s3_key = upload_file(
        data=data,
        content_type=file.content_type or "application/octet-stream",
        tenant_id=tenant.id,
        filename=file.filename or "unnamed",
    )

    doc = Document(
        tenant_id=tenant.id,
        filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        s3_key=s3_key,
        file_size=len(data),
    )
    db.add(doc)

    db.add(AuditLog(
        tenant_id=tenant.id,
        action=AuditAction.DOCUMENT_UPLOADED,
        entity_type="document",
        entity_id=doc.id,
        diff={"filename": doc.filename, "size": doc.file_size},
    ))

    await db.commit()
    await db.refresh(doc)

    return _doc_to_dict(doc)


@router.get("")
async def list_documents(
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    result = await db.execute(
        select(Document)
        .where(Document.tenant_id == tenant.id)
        .order_by(Document.created_at.desc())
    )
    return [_doc_to_dict(d) for d in result.scalars().all()]


@router.get("/{document_id}")
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == tenant.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundError("Document", str(document_id))
    return _doc_to_dict(doc)


def _doc_to_dict(doc: Document) -> dict:
    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "content_type": doc.content_type,
        "file_size": doc.file_size,
        "s3_key": doc.s3_key,
        "metadata": doc.metadata_,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }
