"""Aggregated metrics for the dashboard: funnel, score bands, regions, trend."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from app.db import get_db
from app.deps import get_current_user, tenant_filter, to_object_id
from app.models.common import LeadStatus
from app.models.schemas import AnalyticsOverview
from app.services.regions import region_label

router = APIRouter(prefix="/analytics", tags=["analytics"])

# Ordered so the funnel reads as a progression, not a set.
FUNNEL_STAGES = [
    ("new", "Baru"),
    ("contacted", "Dihubungi"),
    ("qualified", "Qualified"),
]

# Framed by what the score means commercially: a low score is the best
# redesign opportunity, so that band leads.
SCORE_BANDS = [
    ("0-39", "Prioritas tinggi", 0, 39),
    ("40-59", "Prioritas sedang", 40, 59),
    ("60-79", "Prioritas rendah", 60, 79),
    ("80-100", "Sudah baik", 80, 100),
]


@router.get("/overview", response_model=AnalyticsOverview)
async def overview(
    user: Dict[str, Any] = Depends(get_current_user),
    project_id: Optional[str] = None,
    days: int = Query(default=30, ge=7, le=180),
) -> Any:
    db = get_db()
    scope: Dict[str, Any] = dict(tenant_filter(user))
    if project_id:
        scope["project_id"] = to_object_id(project_id, "project_id")

    total_leads = await db.leads.count_documents(scope)

    # --- funnel -----------------------------------------------------------
    status_counts: Dict[str, int] = {}
    async for row in db.leads.aggregate(
        [{"$match": scope}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}]
    ):
        status_counts[row["_id"] or "new"] = row["n"]

    # Each stage counts everyone who reached it or moved past it, so the
    # funnel never widens as it goes down.
    reached_contacted = (
        status_counts.get("contacted", 0)
        + status_counts.get("qualified", 0)
        + await db.leads.count_documents({**scope, "status": "new", "outreach_sent_at": {"$ne": None}})
    )
    funnel = [
        {"key": "new", "label": "Baru", "count": total_leads},
        {"key": "contacted", "label": "Dihubungi", "count": reached_contacted},
        {"key": "qualified", "label": "Qualified", "count": status_counts.get("qualified", 0)},
    ]

    # --- score bands ------------------------------------------------------
    score_bands: List[Dict[str, Any]] = []
    for key, label, low, high in SCORE_BANDS:
        count = await db.leads.count_documents(
            {**scope, "audit_score": {"$gte": low, "$lte": high}}
        )
        score_bands.append({"key": key, "label": label, "count": count})

    scored = await db.leads.count_documents({**scope, "audit_score": {"$ne": None}})
    average_score = None
    if scored:
        async for row in db.leads.aggregate(
            [
                {"$match": {**scope, "audit_score": {"$ne": None}}},
                {"$group": {"_id": None, "avg": {"$avg": "$audit_score"}}},
            ]
        ):
            average_score = round(row["avg"])

    # --- regions ----------------------------------------------------------
    regions: List[Dict[str, Any]] = []
    async for row in db.leads.aggregate(
        [
            {"$match": scope},
            {"$group": {"_id": "$region", "n": {"$sum": 1}}},
            {"$sort": {"n": -1}},
        ]
    ):
        regions.append(
            {
                "key": row["_id"] or "unknown",
                "label": region_label(row["_id"]),
                "count": row["n"],
            }
        )

    # --- trend ------------------------------------------------------------
    since = datetime.now(timezone.utc) - timedelta(days=days)
    buckets: Dict[str, int] = {}
    async for lead in db.leads.find({**scope, "created_at": {"$gte": since}}, {"created_at": 1}):
        created = lead.get("created_at")
        if created:
            buckets[created.date().isoformat()] = buckets.get(created.date().isoformat(), 0) + 1

    trend = []
    start = (datetime.now(timezone.utc) - timedelta(days=days - 1)).date()
    for offset in range(days):
        day = (start + timedelta(days=offset)).isoformat()
        trend.append({"date": day, "count": buckets.get(day, 0)})

    # --- headline numbers -------------------------------------------------
    # Count redesigns for leads inside the same scope, otherwise a
    # project-filtered view would show a tenant-wide number beside
    # project-wide ones.
    scoped_lead_ids = [
        doc["_id"] async for doc in db.leads.find(scope, {"_id": 1})
    ]
    redesigns = 0
    if scoped_lead_ids:
        async for row in db.redesign_outputs.aggregate(
            [
                {"$match": {"lead_id": {"$in": scoped_lead_ids}}},
                {"$group": {"_id": "$lead_id"}},
                {"$count": "n"},
            ]
        ):
            redesigns = row["n"]
    outreach_sent = await db.leads.count_documents({**scope, "outreach_sent_at": {"$ne": None}})
    contact_rate = round(outreach_sent / total_leads * 100) if total_leads else 0
    qualified_rate = (
        round(status_counts.get("qualified", 0) / total_leads * 100) if total_leads else 0
    )

    return {
        "total_leads": total_leads,
        "scored_leads": scored,
        "average_score": average_score,
        "redesigns": redesigns,
        "outreach_sent": outreach_sent,
        "contact_rate": contact_rate,
        "qualified_rate": qualified_rate,
        "funnel": funnel,
        "score_bands": score_bands,
        "regions": regions[:10],
        "trend": trend,
        "days": days,
    }
