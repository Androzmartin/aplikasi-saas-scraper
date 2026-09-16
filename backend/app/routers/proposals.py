"""Client-ready proposal document built from the lead's audit and redesign."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, Response

from app.config import settings
from app.db import get_db
from app.deps import get_current_user, get_owned_lead
from app.services.proposal import build_proposal_html
from app.services.screenshots import ScreenshotUnavailable
from app.services.storage import storage

router = APIRouter(prefix="/proposals", tags=["proposals"])


def _slug(lead: Dict[str, Any]) -> str:
    raw = (lead.get("business_name") or "proposal").lower()
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in raw).strip("-")[:40]
    return cleaned or "proposal"


async def _compose(lead: Dict[str, Any], user: Dict[str, Any]) -> str:
    db = get_db()
    audit = await db.website_audits.find_one({"lead_id": lead["_id"]}, sort=[("created_at", -1)])
    redesign = await db.redesign_outputs.find_one({"lead_id": lead["_id"]}, sort=[("version", -1)])
    tenant = None
    if user.get("tenant_id"):
        tenant = await db.tenants.find_one({"_id": user["tenant_id"]})

    # Inline the desktop screenshot so the proposal stays a single file.
    data_uri: Optional[str] = None
    shots = await db.screenshots.find_one({"lead_id": lead["_id"]}, sort=[("version", -1)])
    key = (shots or {}).get("keys", {}).get("desktop")
    if key:
        raw = storage.get_bytes(key)
        if raw:
            data_uri = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")

    return build_proposal_html(lead, audit, redesign, tenant, user, data_uri)


@router.get("/{lead_id}", response_class=HTMLResponse)
async def preview_proposal(lead_id: str, user: Dict[str, Any] = Depends(get_current_user)) -> Any:
    """The proposal as HTML, for preview in an iframe."""
    lead = await get_owned_lead(lead_id, user)
    return HTMLResponse(content=await _compose(lead, user))


@router.get("/{lead_id}/download")
async def download_proposal(
    lead_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
    format: str = Query(default="pdf", pattern="^(pdf|html)$"),
) -> Any:
    """Download the proposal. PDF needs Playwright; HTML always works."""
    lead = await get_owned_lead(lead_id, user)
    html = await _compose(lead, user)
    slug = _slug(lead)

    db = get_db()
    await db.activity_logs.insert_one(
        {
            "tenant_id": lead.get("tenant_id"),
            "user_id": user["_id"],
            "action": "proposal_downloaded",
            "target": lead.get("website_url"),
            "detail": format,
            "created_at": datetime.now(timezone.utc),
        }
    )

    if format == "html":
        return Response(
            content=html,
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="proposal-{slug}.html"'},
        )

    if not settings.screenshot_enabled:
        raise HTTPException(
            status_code=503,
            detail=(
                "Ekspor PDF membutuhkan Playwright (SCREENSHOT_ENABLED). "
                "Unduh format HTML lalu cetak ke PDF dari browser."
            ),
        )

    from app.services.pdf import html_to_pdf

    try:
        pdf = await html_to_pdf(html)
    except ScreenshotUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail=f"{exc} Unduh format HTML lalu cetak ke PDF dari browser.",
        )

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="proposal-{slug}.pdf"'},
    )
