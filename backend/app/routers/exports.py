"""CSV export of leads for the sales team."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.db import get_db
from app.deps import get_current_user
from app.models.common import LeadStatus
from app.routers.leads import build_lead_query
from app.services.regions import region_label

router = APIRouter(prefix="/exports", tags=["exports"])

CSV_COLUMNS = [
    "business_name",
    "website_url",
    "whatsapp_number",
    "phone_number",
    "email",
    "address",
    "contact_person",
    "region",
    "audit_score",
    "status",
    "tags",
    "notes",
    "source_page",
    "created_at",
]

MAX_EXPORT_ROWS = 10_000


def _csv_safe(value: Any) -> str:
    """Neutralise spreadsheet formula injection in exported values."""
    text = "" if value is None else str(value)
    if text[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


@router.get("/leads.csv")
async def export_leads_csv(
    user: Dict[str, Any] = Depends(get_current_user),
    project_id: Optional[str] = None,
    region: Optional[str] = None,
    lead_status: Optional[LeadStatus] = Query(default=None, alias="status"),
    search: Optional[str] = None,
    min_score: Optional[int] = Query(default=None, ge=0, le=100),
    max_score: Optional[int] = Query(default=None, ge=0, le=100),
) -> Any:
    """Stream the current filtered lead set as CSV, matching what the table shows."""
    db = get_db()
    query = build_lead_query(user, project_id, region, lead_status, search, min_score, max_score)

    async def rows():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        # BOM so Excel opens UTF-8 Indonesian characters correctly.
        yield "﻿"
        writer.writerow(CSV_COLUMNS)
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)

        cursor = db.leads.find(query).sort("created_at", -1).limit(MAX_EXPORT_ROWS)
        async for lead in cursor:
            created = lead.get("created_at")
            writer.writerow(
                [
                    _csv_safe(lead.get("business_name")),
                    _csv_safe(lead.get("website_url")),
                    _csv_safe(lead.get("whatsapp_number")),
                    _csv_safe(lead.get("phone_number")),
                    _csv_safe(lead.get("email")),
                    _csv_safe(lead.get("address")),
                    _csv_safe(lead.get("contact_person")),
                    _csv_safe(region_label(lead.get("region"))),
                    _csv_safe(lead.get("audit_score")),
                    _csv_safe(lead.get("status")),
                    _csv_safe(", ".join(lead.get("tags") or [])),
                    _csv_safe(lead.get("notes")),
                    _csv_safe(lead.get("source_page")),
                    _csv_safe(created.isoformat() if created else ""),
                ]
            )
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return StreamingResponse(
        rows(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="leads-{stamp}.csv"'},
    )
