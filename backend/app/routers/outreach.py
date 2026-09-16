"""Outreach drafts: compose a WhatsApp/email message from a lead's audit."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import get_db
from app.deps import get_current_user, get_owned_lead
from app.models.schemas import OutreachDraftOut, OutreachLogged
from app.services import outreach as outreach_service

router = APIRouter(prefix="/outreach", tags=["outreach"])


@router.get("/{lead_id}", response_model=OutreachDraftOut)
async def get_draft(
    lead_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
    channel: str = Query(default="whatsapp"),
    tone: str = Query(default="formal"),
) -> Any:
    """Compose a draft. Nothing is sent: the user sends it from their own account."""
    db = get_db()
    lead = await get_owned_lead(lead_id, user)
    audit = await db.website_audits.find_one({"lead_id": lead["_id"]}, sort=[("created_at", -1)])

    tenant = None
    if user.get("tenant_id"):
        tenant = await db.tenants.find_one({"_id": user["tenant_id"]})

    try:
        draft = outreach_service.build_draft(
            lead,
            audit,
            channel=channel,
            tone=tone,
            sender_name=user.get("name"),
            company_name=(tenant or {}).get("company_name"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    payload = draft.to_dict()
    payload["lead_id"] = str(lead["_id"])
    payload["outreach_sent_at"] = lead.get("outreach_sent_at")
    payload["outreach_channel"] = lead.get("outreach_channel")
    return payload


@router.post("/{lead_id}/mark-sent", response_model=OutreachLogged)
async def mark_sent(
    lead_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
    channel: str = Query(default="whatsapp"),
) -> Any:
    """Record that the salesperson sent this outreach, and advance the lead."""
    if channel not in outreach_service.CHANNELS:
        raise HTTPException(status_code=400, detail=f"Channel tidak dikenal: {channel}")

    db = get_db()
    lead = await get_owned_lead(lead_id, user)
    now = datetime.now(timezone.utc)

    updates: Dict[str, Any] = {
        "outreach_sent_at": now,
        "outreach_channel": channel,
        "updated_at": now,
    }
    # Only advance a brand-new lead; never overwrite a later stage such as
    # qualified or rejected.
    if lead.get("status", "new") == "new":
        updates["status"] = "contacted"

    await db.leads.update_one({"_id": lead["_id"]}, {"$set": updates})
    await db.activity_logs.insert_one(
        {
            "tenant_id": lead.get("tenant_id"),
            "user_id": user["_id"],
            "action": "outreach_sent",
            "target": lead.get("website_url"),
            "detail": channel,
            "created_at": now,
        }
    )

    refreshed = await db.leads.find_one({"_id": lead["_id"]})
    return {
        "lead_id": str(lead["_id"]),
        "status": refreshed.get("status", "new"),
        "outreach_channel": channel,
        "outreach_sent_at": now,
    }
