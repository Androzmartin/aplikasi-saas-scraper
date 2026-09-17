"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import close, connect, ensure_indexes
from app.models.common import Role, TenantStatus
from app.routers import (
    admin,
    analytics,
    billing,
    audits,
    auth,
    exports,
    leads,
    outreach,
    projects,
    proposals,
    redesign,
    scrape,
    screenshots,
)
from app.security import hash_password
from app.services.jobs import start_workers, stop_workers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def _bootstrap_admin() -> None:
    """Create the internal admin on first boot when a password is configured."""
    if not settings.bootstrap_admin_password:
        return
    db = connect()
    email = settings.bootstrap_admin_email.lower().strip()
    if await db.users.find_one({"email": email}):
        return
    await db.users.insert_one(
        {
            "tenant_id": None,
            "name": settings.bootstrap_admin_name,
            "email": email,
            "password_hash": hash_password(settings.bootstrap_admin_password),
            "role": Role.ADMIN_INTERNAL.value,
            "created_at": datetime.now(timezone.utc),
        }
    )
    logger.info("Bootstrap admin created: %s", email)


@asynccontextmanager
async def lifespan(app: FastAPI):
    connect()
    try:
        await ensure_indexes()
        await _bootstrap_admin()
    except Exception:  # noqa: BLE001 - surface the cause but let the API start
        logger.exception("Database bootstrap failed; check MONGO_URI")
    await start_workers()
    logger.info("%s ready (environment=%s)", settings.app_name, settings.environment)
    yield
    await stop_workers()
    await close()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "SaaS untuk mengumpulkan lead UMKM dari website publik, mengaudit kualitas "
        "website, dan menghasilkan konsep redesign siap presentasi."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

for router in (
    auth.router,
    analytics.router,
    billing.router,
    projects.router,
    scrape.router,
    leads.router,
    audits.router,
    redesign.router,
    outreach.router,
    proposals.router,
    screenshots.router,
    exports.router,
    admin.router,
):
    app.include_router(router, prefix=settings.api_prefix)


@app.get("/health", tags=["system"])
async def health() -> dict:
    """Liveness probe that also reports database reachability."""
    db_ok = True
    try:
        await connect().command("ping")
    except Exception:  # noqa: BLE001
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "app": settings.app_name,
        "environment": settings.environment,
        "database": "up" if db_ok else "down",
    }
