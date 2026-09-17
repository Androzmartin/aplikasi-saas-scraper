"""MongoDB connection handling and index bootstrap."""
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

from app.config import settings

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


def connect() -> AsyncIOMotorDatabase:
    global _client, _db
    if _db is None:
        _client = AsyncIOMotorClient(settings.mongo_uri, uuidRepresentation="standard")
        _db = _client[settings.mongo_db]
    return _db


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        return connect()
    return _db


async def close() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None


async def ensure_indexes() -> None:
    """Create the indexes the MVP queries rely on. Safe to call repeatedly."""
    db = get_db()
    await db.users.create_index([("email", ASCENDING)], unique=True)
    await db.users.create_index([("tenant_id", ASCENDING)])
    await db.tenants.create_index([("company_name", ASCENDING)])
    await db.projects.create_index([("tenant_id", ASCENDING), ("created_at", DESCENDING)])
    await db.scrape_jobs.create_index([("project_id", ASCENDING), ("created_at", DESCENDING)])
    await db.scrape_jobs.create_index([("tenant_id", ASCENDING), ("status", ASCENDING)])
    await db.scrape_jobs.create_index([("status", ASCENDING), ("created_at", ASCENDING)])
    await db.leads.create_index([("project_id", ASCENDING), ("created_at", DESCENDING)])
    await db.leads.create_index([("tenant_id", ASCENDING), ("region", ASCENDING)])
    await db.leads.create_index([("tenant_id", ASCENDING), ("status", ASCENDING)])
    await db.leads.create_index(
        [("business_name", "text"), ("website_url", "text"), ("address", "text")],
        name="leads_text_search",
    )
    await db.website_audits.create_index([("lead_id", ASCENDING), ("created_at", DESCENDING)])
    await db.redesign_outputs.create_index([("lead_id", ASCENDING), ("version", DESCENDING)])
    await db.redesign_outputs.create_index([("approval_status", ASCENDING), ("created_at", DESCENDING)])
    await db.screenshots.create_index([("lead_id", ASCENDING), ("version", DESCENDING)])
    # merchant_order_id is what Duitku quotes back in callbacks; it must be unique.
    await db.payments.create_index([("merchant_order_id", ASCENDING)], unique=True)
    await db.payments.create_index([("tenant_id", ASCENDING), ("created_at", DESCENDING)])
    await db.payments.create_index([("status", ASCENDING), ("created_at", DESCENDING)])
    await db.activity_logs.create_index([("tenant_id", ASCENDING), ("created_at", DESCENDING)])
    await db.activity_logs.create_index([("created_at", DESCENDING)])
