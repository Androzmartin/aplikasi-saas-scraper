"""Internal admin panel: cross-tenant monitoring of users, projects and jobs."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import get_db
from app.deps import require_admin, to_object_id
from app.models.common import JobStatus, TenantStatus
from app.models.schemas import (
    ActivityLogOut,
    AdminStats,
    JobOut,
    ProjectOut,
    TenantOut,
    UserOut,
)
from app.serializers import activity_out, job_out, project_out, tenant_out, user_out

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/stats", response_model=AdminStats)
async def stats() -> Any:
    db = get_db()
    jobs_by_status: Dict[str, int] = {}
    async for row in db.scrape_jobs.aggregate([{"$group": {"_id": "$status", "n": {"$sum": 1}}}]):
        jobs_by_status[row["_id"]] = row["n"]

    return {
        "tenants": await db.tenants.count_documents({}),
        "users": await db.users.count_documents({}),
        "projects": await db.projects.count_documents({}),
        "leads": await db.leads.count_documents({}),
        "redesigns": await db.redesign_outputs.count_documents({}),
        "jobs_by_status": jobs_by_status,
    }


@router.get("/users", response_model=List[UserOut])
async def list_users(limit: int = Query(default=200, ge=1, le=500)) -> Any:
    db = get_db()
    users = await db.users.find().sort("created_at", -1).limit(limit).to_list(limit)
    return [user_out(user) for user in users]


@router.get("/tenants", response_model=List[TenantOut])
async def list_tenants(limit: int = Query(default=200, ge=1, le=500)) -> Any:
    db = get_db()
    tenants = await db.tenants.find().sort("created_at", -1).limit(limit).to_list(limit)
    return [tenant_out(tenant) for tenant in tenants]


@router.patch("/tenants/{tenant_id}/status", response_model=TenantOut)
async def set_tenant_status(tenant_id: str, value: TenantStatus) -> Any:
    """Suspend or reactivate a tenant; suspended tenants cannot call the API."""
    db = get_db()
    oid = to_object_id(tenant_id, "tenant_id")
    result = await db.tenants.update_one({"_id": oid}, {"$set": {"status": value.value}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Tenant tidak ditemukan")
    tenant = await db.tenants.find_one({"_id": oid})
    return tenant_out(tenant)


@router.get("/projects", response_model=List[ProjectOut])
async def list_all_projects(limit: int = Query(default=200, ge=1, le=500)) -> Any:
    db = get_db()
    projects = await db.projects.find().sort("created_at", -1).limit(limit).to_list(limit)
    out = []
    for project in projects:
        lead_count = await db.leads.count_documents({"project_id": project["_id"]})
        out.append(project_out(project, {}, lead_count))
    return out


@router.get("/jobs", response_model=List[JobOut])
async def list_all_jobs(
    job_status: Optional[JobStatus] = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=500),
) -> Any:
    db = get_db()
    query: Dict[str, Any] = {}
    if job_status:
        query["status"] = job_status.value
    jobs = await db.scrape_jobs.find(query).sort("created_at", -1).limit(limit).to_list(limit)

    project_ids = {job["project_id"] for job in jobs if job.get("project_id")}
    names: Dict[Any, str] = {}
    if project_ids:
        async for project in db.projects.find({"_id": {"$in": list(project_ids)}}):
            names[project["_id"]] = project.get("name", "")
    return [job_out(job, names.get(job.get("project_id"))) for job in jobs]


@router.get("/activity", response_model=List[ActivityLogOut])
async def list_activity(limit: int = Query(default=100, ge=1, le=500)) -> Any:
    """Audit trail of scraping and generation activity across all tenants."""
    db = get_db()
    logs = await db.activity_logs.find().sort("created_at", -1).limit(limit).to_list(limit)
    return [activity_out(log) for log in logs]


@router.get("/errors", response_model=List[JobOut])
async def list_errors(limit: int = Query(default=100, ge=1, le=500)) -> Any:
    db = get_db()
    jobs = (
        await db.scrape_jobs.find({"status": JobStatus.FAILED.value})
        .sort("completed_at", -1)
        .limit(limit)
        .to_list(limit)
    )
    return [job_out(job) for job in jobs]
