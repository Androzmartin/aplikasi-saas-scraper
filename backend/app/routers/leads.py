"""Lead dashboard: listing with search/filters, detail and inline updates."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from app.db import get_db
from app.deps import get_current_user, get_owned_lead, tenant_filter, to_object_id
from app.models.common import LeadStatus, Page
from app.models.schemas import LeadOut, LeadUpdate
from app.serializers import lead_out

router = APIRouter(prefix="/leads", tags=["leads"])


def build_lead_query(
    user: Dict[str, Any],
    project_id: Optional[str],
    region: Optional[str],
    lead_status: Optional[LeadStatus],
    search: Optional[str],
    min_score: Optional[int],
    max_score: Optional[int],
) -> Dict[str, Any]:
    query: Dict[str, Any] = dict(tenant_filter(user))
    if project_id:
        query["project_id"] = to_object_id(project_id, "project_id")
    if region:
        query["region"] = region
    if lead_status:
        query["status"] = lead_status.value

    score_filter: Dict[str, int] = {}
    if min_score is not None:
        score_filter["$gte"] = min_score
    if max_score is not None:
        score_filter["$lte"] = max_score
    if score_filter:
        query["audit_score"] = score_filter

    if search and search.strip():
        # Escaped so user input can never act as a regex.
        pattern = re.escape(search.strip())
        query["$or"] = [
            {"business_name": {"$regex": pattern, "$options": "i"}},
            {"website_url": {"$regex": pattern, "$options": "i"}},
            {"address": {"$regex": pattern, "$options": "i"}},
            {"email": {"$regex": pattern, "$options": "i"}},
            {"whatsapp_number": {"$regex": pattern, "$options": "i"}},
        ]
    return query


@router.get("", response_model=Page[LeadOut])
async def list_leads(
    user: Dict[str, Any] = Depends(get_current_user),
    project_id: Optional[str] = None,
    region: Optional[str] = None,
    lead_status: Optional[LeadStatus] = Query(default=None, alias="status"),
    search: Optional[str] = None,
    min_score: Optional[int] = Query(default=None, ge=0, le=100),
    max_score: Optional[int] = Query(default=None, ge=0, le=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> Any:
    db = get_db()
    query = build_lead_query(user, project_id, region, lead_status, search, min_score, max_score)

    total = await db.leads.count_documents(query)
    cursor = (
        db.leads.find(query)
        .sort("created_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    leads = await cursor.to_list(length=page_size)

    lead_ids = [lead["_id"] for lead in leads]
    with_redesign = set()
    if lead_ids:
        async for row in db.redesign_outputs.aggregate(
            [{"$match": {"lead_id": {"$in": lead_ids}}}, {"$group": {"_id": "$lead_id"}}]
        ):
            with_redesign.add(row["_id"])

    return {
        "items": [lead_out(lead, lead["_id"] in with_redesign) for lead in leads],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/regions", response_model=List[Dict[str, Any]])
async def region_facets(
    user: Dict[str, Any] = Depends(get_current_user),
    project_id: Optional[str] = None,
) -> Any:
    """Counts per region, used to populate the dashboard filter."""
    db = get_db()
    match: Dict[str, Any] = dict(tenant_filter(user))
    if project_id:
        match["project_id"] = to_object_id(project_id, "project_id")

    cursor = db.leads.aggregate(
        [{"$match": match}, {"$group": {"_id": "$region", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
    )
    return [{"region": row["_id"] or "unknown", "count": row["count"]} async for row in cursor]


@router.get("/{lead_id}", response_model=LeadOut)
async def get_lead(lead_id: str, user: Dict[str, Any] = Depends(get_current_user)) -> Any:
    db = get_db()
    lead = await get_owned_lead(lead_id, user)
    has_redesign = await db.redesign_outputs.count_documents({"lead_id": lead["_id"]}) > 0
    return lead_out(lead, has_redesign)


@router.patch("/{lead_id}", response_model=LeadOut)
async def update_lead(
    lead_id: str, payload: LeadUpdate, user: Dict[str, Any] = Depends(get_current_user)
) -> Any:
    db = get_db()
    lead = await get_owned_lead(lead_id, user)

    updates: Dict[str, Any] = {}
    if payload.status is not None:
        # ApiModel uses use_enum_values, so this is already the string value.
        updates["status"] = payload.status
    if payload.notes is not None:
        updates["notes"] = payload.notes.strip() or None
    if payload.tags is not None:
        cleaned = {tag.strip()[:40] for tag in payload.tags if tag and tag.strip()}
        updates["tags"] = sorted(cleaned)[:20]
    if payload.contact_person is not None:
        updates["contact_person"] = payload.contact_person.strip() or None
    if payload.business_name is not None:
        updates["business_name"] = payload.business_name.strip() or None
    if payload.region is not None:
        updates["region"] = payload.region.strip().lower() or None

    if updates:
        updates["updated_at"] = datetime.now(timezone.utc)
        await db.leads.update_one({"_id": lead["_id"]}, {"$set": updates})
        lead = await db.leads.find_one({"_id": lead["_id"]})

    has_redesign = await db.redesign_outputs.count_documents({"lead_id": lead["_id"]}) > 0
    return lead_out(lead, has_redesign)
