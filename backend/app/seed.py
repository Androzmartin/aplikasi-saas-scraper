"""Seed a demo tenant, user and project.

Usage (from backend/):  python -m app.seed
Intended for local development and demos only.
"""
import asyncio
import os
import secrets
from datetime import datetime, timezone

from app.db import connect, ensure_indexes
from app.models.common import Role, TenantStatus
from app.security import hash_password


async def main() -> None:
    db = connect()
    await ensure_indexes()

    email = os.getenv("SEED_EMAIL", "demo@agency.co.id")
    password = os.getenv("SEED_PASSWORD") or secrets.token_urlsafe(12)
    now = datetime.now(timezone.utc)

    if await db.users.find_one({"email": email}):
        print(f"User {email} already exists; nothing to do.")
        return

    tenant = await db.tenants.insert_one(
        {
            "company_name": os.getenv("SEED_COMPANY", "Agency Kreatif Nusantara"),
            "plan_name": "starter",
            "status": TenantStatus.ACTIVE.value,
            "monthly_job_quota": 500,
            "created_at": now,
        }
    )
    user = await db.users.insert_one(
        {
            "tenant_id": tenant.inserted_id,
            "name": os.getenv("SEED_NAME", "Demo User"),
            "email": email,
            "password_hash": hash_password(password),
            "role": Role.USER_TENANT.value,
            "created_at": now,
        }
    )
    await db.projects.insert_one(
        {
            "tenant_id": tenant.inserted_id,
            "name": "Contoh Project Jabodetabek",
            "target_region": "jakarta",
            "description": "Project contoh untuk mencoba alur scraping.",
            "created_by": user.inserted_id,
            "created_at": now,
        }
    )

    print("Seed complete.")
    print(f"  email    : {email}")
    print(f"  password : {password}")


if __name__ == "__main__":
    asyncio.run(main())
