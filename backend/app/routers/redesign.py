"""Redesign concept generation, preview and single-file index.html download."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from app.config import settings
from app.db import get_db
from app.deps import get_current_user, get_owned_lead, is_admin
from app.models.schemas import RedesignOut
from app.serializers import redesign_out
from app.services.ai import enrich_concept
from app.services.redesign import build_concept, build_preview_html, render_index_html
from app.services.storage import storage

router = APIRouter(prefix="/redesign", tags=["redesign"])


def _storage_key(lead_id: str, version: int) -> str:
    return f"redesign/{lead_id}/v{version}/index.html"


@router.post("/{lead_id}/generate", response_model=RedesignOut, status_code=201)
async def generate_redesign(lead_id: str, user: Dict[str, Any] = Depends(get_current_user)) -> Any:
    db = get_db()
    lead = await get_owned_lead(lead_id, user)
    audit = await db.website_audits.find_one({"lead_id": lead["_id"]}, sort=[("created_at", -1)])

    concept = build_concept(lead, audit)
    concept = await enrich_concept(concept, lead, audit)

    index_html = render_index_html(lead, concept, audit)

    latest = await db.redesign_outputs.find_one({"lead_id": lead["_id"]}, sort=[("version", -1)])
    version = (latest.get("version", 0) + 1) if latest else 1

    key = _storage_key(str(lead["_id"]), version)
    storage.put_text(key, index_html)

    now = datetime.now(timezone.utc)
    approval_required = settings.require_redesign_approval
    doc = {
        "lead_id": lead["_id"],
        "tenant_id": lead.get("tenant_id"),
        "version": version,
        "approval_status": "pending" if approval_required else "approved",
        "approval_note": None,
        "reviewed_by": None,
        "reviewed_at": None,
        "headline": concept["headline"],
        "subheadline": concept["subheadline"],
        "sections": concept["sections"],
        "improvements": concept.get("improvements", []),
        "preview_html": build_preview_html(index_html),
        "storage_key": key,
        "generated_with": concept.get("generated_with", "template"),
        "created_at": now,
    }
    result = await db.redesign_outputs.insert_one(doc)
    doc["_id"] = result.inserted_id

    await db.activity_logs.insert_one(
        {
            "tenant_id": lead.get("tenant_id"),
            "user_id": user["_id"],
            "action": "redesign_generated",
            "target": lead.get("website_url"),
            "detail": f"versi {version}",
            "created_at": now,
        }
    )
    return redesign_out(doc, settings.api_prefix, approval_required)


@router.get("/{lead_id}", response_model=RedesignOut)
async def get_redesign(lead_id: str, user: Dict[str, Any] = Depends(get_current_user)) -> Any:
    db = get_db()
    lead = await get_owned_lead(lead_id, user)
    doc = await db.redesign_outputs.find_one({"lead_id": lead["_id"]}, sort=[("version", -1)])
    if not doc:
        raise HTTPException(status_code=404, detail="Belum ada hasil redesign untuk lead ini")
    return redesign_out(doc, settings.api_prefix, settings.require_redesign_approval)


@router.get("/{lead_id}/download")
async def download_redesign(lead_id: str, user: Dict[str, Any] = Depends(get_current_user)) -> Any:
    db = get_db()
    lead = await get_owned_lead(lead_id, user)
    doc = await db.redesign_outputs.find_one({"lead_id": lead["_id"]}, sort=[("version", -1)])
    if not doc:
        raise HTTPException(status_code=404, detail="Belum ada hasil redesign untuk lead ini")

    # Internal admins can always fetch the file so they can review it.
    if settings.require_redesign_approval and not is_admin(user):
        approval_status = doc.get("approval_status", "approved")
        if approval_status != "approved":
            detail = (
                "Hasil redesign ditolak admin internal."
                if approval_status == "rejected"
                else "Hasil redesign menunggu persetujuan admin internal."
            )
            note = doc.get("approval_note")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{detail} {note}".strip() if note else detail,
            )

    html = storage.get_text(doc["storage_key"]) if doc.get("storage_key") else None
    if html is None:
        # Fall back to the stored preview so a missing object never breaks download.
        html = doc.get("preview_html") or ""
    if not html:
        raise HTTPException(status_code=410, detail="Berkas redesign tidak tersedia lagi")

    slug = (lead.get("business_name") or "redesign").lower()
    slug = "".join(ch if ch.isalnum() else "-" for ch in slug).strip("-")[:40] or "redesign"
    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{slug}-index.html"'},
    )
