"""
MALIN v0.1 – Phase 1 Backend.

"Draft is Law" – no action is executed without an approved draft.
"""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from malin.app.errors import MalinError, generic_error_handler, malin_error_handler
from malin.app.routers import documents, drafts, health

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-30s  %(levelname)-7s  %(message)s",
)
logger = logging.getLogger("malin")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: run Alembic migrations + ensure S3 bucket
    from malin.app.services.storage import ensure_bucket
    try:
        ensure_bucket()
        logger.info("S3 bucket ready")
    except Exception as e:
        logger.warning(f"S3 bucket init failed (will retry on first upload): {e}")

    # Seed default tenant if not present
    await _seed_default_tenant()

    yield


async def _seed_default_tenant():
    """Create a default dev tenant if the table is empty."""
    from sqlalchemy import select, func

    from malin.app.config import settings
    from malin.app.db import async_session
    from malin.app.models.tables import Tenant

    async with async_session() as db:
        count = await db.scalar(select(func.count(Tenant.id)))
        if count == 0:
            tenant = Tenant(
                name="Default Dev Tenant",
                api_key=settings.master_tenant_key,
            )
            db.add(tenant)
            await db.commit()
            logger.info(f"Seeded default tenant: {tenant.id}")


app = FastAPI(
    title="MALIN",
    description="Mail AI Navigator – Draft is Law",
    version="0.1.0",
    lifespan=lifespan,
)

# Error handlers: no raw 500s
app.add_exception_handler(MalinError, malin_error_handler)
app.add_exception_handler(Exception, generic_error_handler)

# Routers
app.include_router(health.router)
app.include_router(documents.router)
app.include_router(drafts.router)

if __name__ == "__main__":
    uvicorn.run(
        "malin.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
