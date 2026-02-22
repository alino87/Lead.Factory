"""
Tenant authentication via X-TENANT-KEY header.
"""

import uuid

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from malin.app.db import get_db
from malin.app.errors import AuthError
from malin.app.models.tables import Tenant


async def get_current_tenant(
    x_tenant_key: str = Header(..., alias="X-TENANT-KEY"),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """Resolve the tenant from the API key header."""
    result = await db.execute(
        select(Tenant).where(Tenant.api_key == x_tenant_key, Tenant.is_active == True)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise AuthError()
    return tenant
