"""Website audit: run on demand and fetch the latest result for a lead."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.config import settings
from app.db import get_db
from app.deps import get_current_user, get_owned_lead
from app.models.schemas import AuditOut
from app.serializers import audit_out
from app.services.audit import run_audit
from app.services.scraper import ScrapeError, fetch_page

router = APIRouter(prefix="/audits", tags=["audits"])


@router.post("/run/{lead_id}", response_model=AuditOut)
async def run_lead_audit(lead_id: str, user: Dict[str, Any] = Depends(get_current_user)) -> Any:
    """Re-fetch the lead's website and score it again."""
    db = get_db()
    lead = await get_owned_lead(lead_id, user)
    url = lead.get("website_url")
    if not url:
        raise HTTPException(status_code=400, detail="Lead tidak memiliki URL website")

    headers = {"User-Agent": settings.scraper_user_agent}
    try:
        async with httpx.AsyncClient(
            headers=headers, timeout=settings.scraper_timeout_seconds, follow_redirects=True
        ) as client:
            html = await fetch_page(client, url)
    except ScrapeError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=422, detail=f"Gagal mengakses website: {exc.__class__.__name__}"
        )

    if not html:
        raise HTTPException(status_code=422, detail="Website tidak mengembalikan dokumen HTML")

    contact = {
        "business_name": lead.get("business_name"),
        "whatsapp_number": lead.get("whatsapp_number"),
        "phone_number": lead.get("phone_number"),
        "email": lead.get("email"),
        "address": lead.get("address"),
    }
    result = run_audit(html, contact)
    now = datetime.now(timezone.utc)

    inserted = await db.website_audits.insert_one(
        {"lead_id": lead["_id"], "tenant_id": lead.get("tenant_id"), **result, "created_at": now}
    )
    await db.leads.update_one(
        {"_id": lead["_id"]}, {"$set": {"audit_score": result["score"], "updated_at": now}}
    )

    doc = await db.website_audits.find_one({"_id": inserted.inserted_id})
    return audit_out(doc)


@router.get("/{lead_id}", response_model=AuditOut)
async def get_latest_audit(lead_id: str, user: Dict[str, Any] = Depends(get_current_user)) -> Any:
    db = get_db()
    lead = await get_owned_lead(lead_id, user)
    doc = await db.website_audits.find_one({"lead_id": lead["_id"]}, sort=[("created_at", -1)])
    if not doc:
        raise HTTPException(
            status_code=404, detail="Belum ada audit untuk lead ini. Jalankan audit terlebih dahulu."
        )
    return audit_out(doc)
