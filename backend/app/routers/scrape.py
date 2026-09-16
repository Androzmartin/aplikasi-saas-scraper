"""Scraping job submission, monitoring and retry."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import settings
from app.db import get_db
from app.deps import (
    get_current_user,
    get_owned_project,
    is_admin,
    tenant_filter,
    to_object_id,
)
from app.models.common import JobStatus
from app.models.schemas import JobCreate, JobCreateResponse, JobOut
from app.serializers import job_out
from app.services.jobs import notify_new_jobs
from app.services.urls import parse_url_list

router = APIRouter(prefix="/scrape", tags=["scraping"])


async def _check_quota(user: Dict[str, Any], requested: int) -> None:
    """Enforce the tenant's monthly job quota before enqueueing."""
    if is_admin(user) or not user.get("tenant_id"):
        return
    db = get_db()
    tenant = await db.tenants.find_one({"_id": user["tenant_id"]})
    quota = (tenant or {}).get("monthly_job_quota") or settings.default_monthly_job_quota
    if quota <= 0:
        return

    period_start = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    used = await db.scrape_jobs.count_documents(
        {"tenant_id": user["tenant_id"], "created_at": {"$gte": period_start}}
    )
    if used + requested > quota:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Kuota scraping bulan ini habis ({used}/{quota}). "
                f"Permintaan {requested} URL melebihi sisa kuota."
            ),
        )


@router.post("/jobs", response_model=JobCreateResponse, status_code=201)
async def create_jobs(payload: JobCreate, user: Dict[str, Any] = Depends(get_current_user)) -> Any:
    """Queue one job per valid URL. Invalid/duplicate URLs come back as rejections."""
    project = await get_owned_project(payload.project_id, user)
    accepted, rejected = parse_url_list(payload.urls)

    if not accepted:
        return {"created": [], "rejected": rejected}

    await _check_quota(user, len(accepted))

    db = get_db()
    now = datetime.now(timezone.utc)
    docs = [
        {
            "project_id": project["_id"],
            "tenant_id": project.get("tenant_id"),
            "created_by": user["_id"],
            "source_url": url,
            "status": JobStatus.PENDING.value,
            "attempts": 0,
            "error_message": None,
            "lead_id": None,
            "pages_crawled": 0,
            "created_at": now,
            "started_at": None,
            "completed_at": None,
        }
        for url in accepted
    ]
    result = await db.scrape_jobs.insert_many(docs)
    for doc, inserted_id in zip(docs, result.inserted_ids):
        doc["_id"] = inserted_id

    await db.activity_logs.insert_one(
        {
            "tenant_id": project.get("tenant_id"),
            "user_id": user["_id"],
            "action": "scrape_enqueued",
            "target": project["name"],
            "detail": f"{len(docs)} URL masuk antrean",
            "created_at": now,
        }
    )
    notify_new_jobs()

    return {
        "created": [job_out(doc, project["name"]) for doc in docs],
        "rejected": rejected,
    }


@router.get("/jobs", response_model=List[JobOut])
async def list_jobs(
    user: Dict[str, Any] = Depends(get_current_user),
    project_id: Optional[str] = None,
    job_status: Optional[JobStatus] = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=300),
) -> Any:
    db = get_db()
    query: Dict[str, Any] = dict(tenant_filter(user))
    if project_id:
        query["project_id"] = to_object_id(project_id, "project_id")
    if job_status:
        query["status"] = job_status.value

    jobs = await db.scrape_jobs.find(query).sort("created_at", -1).limit(limit).to_list(limit)

    project_ids = {job["project_id"] for job in jobs if job.get("project_id")}
    names: Dict[Any, str] = {}
    if project_ids:
        async for project in db.projects.find({"_id": {"$in": list(project_ids)}}):
            names[project["_id"]] = project.get("name", "")

    return [job_out(job, names.get(job.get("project_id"))) for job in jobs]


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(job_id: str, user: Dict[str, Any] = Depends(get_current_user)) -> Any:
    db = get_db()
    job = await db.scrape_jobs.find_one({"_id": to_object_id(job_id, "job_id"), **tenant_filter(user)})
    if not job:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan")
    project = await db.projects.find_one({"_id": job.get("project_id")})
    return job_out(job, (project or {}).get("name"))


@router.post("/jobs/{job_id}/retry", response_model=JobOut)
async def retry_job(job_id: str, user: Dict[str, Any] = Depends(get_current_user)) -> Any:
    db = get_db()
    oid = to_object_id(job_id, "job_id")
    job = await db.scrape_jobs.find_one({"_id": oid, **tenant_filter(user)})
    if not job:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan")
    if job.get("status") in (JobStatus.PENDING.value, JobStatus.RUNNING.value):
        raise HTTPException(status_code=409, detail="Job masih dalam antrean atau sedang berjalan")

    await db.scrape_jobs.update_one(
        {"_id": oid},
        {
            "$set": {
                "status": JobStatus.PENDING.value,
                "attempts": 0,
                "error_message": None,
                "started_at": None,
                "completed_at": None,
            }
        },
    )
    notify_new_jobs()
    refreshed = await db.scrape_jobs.find_one({"_id": oid})
    project = await db.projects.find_one({"_id": job.get("project_id")})
    return job_out(refreshed, (project or {}).get("name"))
