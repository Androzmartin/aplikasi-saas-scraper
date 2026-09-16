"""Capture and serve desktop/mobile screenshots for a lead's website."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.config import settings
from app.db import get_db
from app.deps import get_current_user, get_owned_lead
from app.models.schemas import ScreenshotOut
from app.services import screenshots as shots

router = APIRouter(prefix="/screenshots", tags=["screenshots"])


def _out(lead_id: str, doc: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    doc = doc or {}
    variants = sorted(doc.get("keys", {}).keys())
    return {
        "lead_id": lead_id,
        "version": doc.get("version", 0),
        "variants": variants,
        "failures": doc.get("failures", {}),
        "image_urls": {
            variant: f"{settings.api_prefix}/screenshots/{lead_id}/{variant}"
            for variant in variants
        },
        "captured_at": doc.get("created_at"),
    }


@router.post("/{lead_id}/capture", response_model=ScreenshotOut, status_code=201)
async def capture_screenshots(
    lead_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
    variants: Optional[List[str]] = Query(default=None),
) -> Any:
    """Screenshot the lead's current website at desktop and mobile widths."""
    if not settings.screenshot_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Fitur screenshot dinonaktifkan. Aktifkan SCREENSHOT_ENABLED pada server.",
        )

    db = get_db()
    lead = await get_owned_lead(lead_id, user)
    url = lead.get("website_url")
    if not url:
        raise HTTPException(status_code=400, detail="Lead tidak memiliki URL website")

    latest = await db.screenshots.find_one({"lead_id": lead["_id"]}, sort=[("version", -1)])
    version = (latest.get("version", 0) + 1) if latest else 1

    try:
        result = await shots.capture(url, str(lead["_id"]), version, variants)
    except shots.ScreenshotUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not result.any_captured:
        reason = "; ".join(f"{k}: {v}" for k, v in result.failures.items()) or "tidak diketahui"
        raise HTTPException(status_code=422, detail=f"Gagal mengambil screenshot ({reason})")

    now = datetime.now(timezone.utc)
    doc = {
        "lead_id": lead["_id"],
        "tenant_id": lead.get("tenant_id"),
        "version": version,
        "keys": result.keys,
        "failures": result.failures,
        "created_at": now,
    }
    await db.screenshots.insert_one(doc)
    await db.activity_logs.insert_one(
        {
            "tenant_id": lead.get("tenant_id"),
            "user_id": user["_id"],
            "action": "screenshot_captured",
            "target": url,
            "detail": f"versi {version}: {', '.join(sorted(result.keys))}",
            "created_at": now,
        }
    )
    return _out(str(lead["_id"]), doc)


@router.get("/{lead_id}", response_model=ScreenshotOut)
async def get_screenshots(lead_id: str, user: Dict[str, Any] = Depends(get_current_user)) -> Any:
    db = get_db()
    lead = await get_owned_lead(lead_id, user)
    doc = await db.screenshots.find_one({"lead_id": lead["_id"]}, sort=[("version", -1)])
    if not doc:
        raise HTTPException(status_code=404, detail="Belum ada screenshot untuk lead ini")
    return _out(str(lead["_id"]), doc)


@router.get("/{lead_id}/{variant}")
async def get_screenshot_image(
    lead_id: str, variant: str, user: Dict[str, Any] = Depends(get_current_user)
) -> Any:
    """Serve the stored PNG. Access is scoped to the lead's tenant."""
    if variant not in shots.VIEWPORTS:
        raise HTTPException(status_code=404, detail="Variant screenshot tidak dikenal")

    db = get_db()
    lead = await get_owned_lead(lead_id, user)
    doc = await db.screenshots.find_one({"lead_id": lead["_id"]}, sort=[("version", -1)])
    key = (doc or {}).get("keys", {}).get(variant)
    if not key:
        raise HTTPException(status_code=404, detail="Screenshot tidak ditemukan")

    from app.services.storage import storage

    data = storage.get_bytes(key)
    if data is None:
        raise HTTPException(status_code=410, detail="Berkas screenshot tidak tersedia lagi")
    return Response(content=data, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})
