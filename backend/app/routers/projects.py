"""Project CRUD for the MVP (create, list, detail)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query

from app.db import get_db
from app.deps import get_current_user, get_owned_project, tenant_filter
from app.models.schemas import ProjectCreate, ProjectOut
from app.serializers import project_out

router = APIRouter(prefix="/projects", tags=["projects"])


async def _project_stats(project_id) -> tuple[Dict[str, int], int]:
    db = get_db()
    counts: Dict[str, int] = {}
    cursor = db.scrape_jobs.aggregate(
        [{"$match": {"project_id": project_id}}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}]
    )
    async for row in cursor:
        counts[row["_id"]] = row["n"]
    lead_count = await db.leads.count_documents({"project_id": project_id})
    return counts, lead_count


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    payload: ProjectCreate, user: Dict[str, Any] = Depends(get_current_user)
) -> Any:
    db = get_db()
    doc = {
        "tenant_id": user.get("tenant_id"),
        "name": payload.name.strip(),
        "target_region": payload.target_region.strip().lower(),
        "description": (payload.description or "").strip() or None,
        "created_by": user["_id"],
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.projects.insert_one(doc)
    doc["_id"] = result.inserted_id
    return project_out(doc, {}, 0)


@router.get("", response_model=List[ProjectOut])
async def list_projects(
    user: Dict[str, Any] = Depends(get_current_user),
    limit: int = Query(default=100, ge=1, le=200),
) -> Any:
    db = get_db()
    cursor = db.projects.find(tenant_filter(user)).sort("created_at", -1).limit(limit)
    projects = await cursor.to_list(length=limit)

    out = []
    for project in projects:
        counts, lead_count = await _project_stats(project["_id"])
        out.append(project_out(project, counts, lead_count))
    return out


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: str, user: Dict[str, Any] = Depends(get_current_user)) -> Any:
    project = await get_owned_project(project_id, user)
    counts, lead_count = await _project_stats(project["_id"])
    return project_out(project, counts, lead_count)
