"""
Tenant auth via X-TENANT-KEY header — SPEC §7.1 + §7.7 plan gating.
"""

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from malin.app.db import get_db
from malin.app.errors import AuthError, TenantSuspendedError
from malin.app.models.tables import Tenant, TenantStatus


async def get_current_tenant(
    x_tenant_key: str = Header(..., alias="X-TENANT-KEY"),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """Resolve tenant from API key. Raises AuthError or TenantSuspendedError."""
    result = await db.execute(
        select(Tenant).where(Tenant.api_key == x_tenant_key)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise AuthError()
    if tenant.status == TenantStatus.SUSPENDED:
        raise TenantSuspendedError()
    return tenant


def get_client_ip(request: Request) -> str:
    """Extract client IP for audit logs (SPEC §5.1 audit_logs.ip)."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_user_agent(request: Request) -> str:
    """Extract User-Agent for audit logs (SPEC §5.1 audit_logs.user_agent)."""
    return request.headers.get("User-Agent", "")[:500]
