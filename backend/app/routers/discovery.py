"""Find candidate businesses by area and category, then queue them for scraping."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

from app.db import get_db
from app.deps import get_current_user, get_owned_project
from app.models.schemas import (
    DiscoveryImportRequest,
    DiscoveryOptions,
    DiscoveryResultOut,
    DiscoverySearchRequest,
    JobCreateResponse,
)
from app.services import discovery, places
from app.services.jobs import notify_new_jobs
from app.services.urls import parse_url_list

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.get("/options", response_model=DiscoveryOptions)
async def get_options(_: Dict[str, Any] = Depends(get_current_user)) -> Any:
    """Areas, categories and the data sources available on this server."""
    providers = [
        {"key": "osm", "label": "OpenStreetMap (gratis)"},
    ]
    if places.is_configured():
        providers.append({"key": "google", "label": "Google Places (berbayar, cakupan lebih luas)"})

    return {
        "regions": discovery.list_regions(),
        "categories": discovery.list_categories(),
        "providers": providers,
        "attribution": discovery.ATTRIBUTION,
    }


@router.post("/search", response_model=DiscoveryResultOut)
async def search_places(
    payload: DiscoverySearchRequest, _: Dict[str, Any] = Depends(get_current_user)
) -> Any:
    """Search for businesses that already publish a website.

    Nothing is saved: this only returns candidates for the user to review.
    """
    if payload.provider == "google":
        if payload.region not in discovery.REGION_BBOX:
            raise HTTPException(status_code=400, detail=f"Wilayah tidak dikenal: {payload.region}")
        try:
            found = await places.search_nearby(
                discovery.REGION_BBOX[payload.region], payload.category, payload.limit
            )
        except places.PlacesNotConfigured as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except places.PlacesError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

        return {
            "region": payload.region,
            "category": payload.category,
            "provider": "google",
            "places": [place.to_dict() for place in found],
            # Google only returns places it has a website for, so there is no
            # social-only bucket to report here.
            "social_only": [],
            "attribution": places.ATTRIBUTION,
        }

    try:
        result = await discovery.search(payload.region, payload.category, payload.limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except discovery.DiscoveryError as exc:
        # The upstream is a shared free service; say so rather than returning
        # an empty list that looks like "no businesses here".
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    return {
        "region": payload.region,
        "category": payload.category,
        "provider": "osm",
        "places": [place.to_dict() for place in result.places],
        "social_only": [place.to_dict() for place in result.social_only],
        "attribution": result.attribution,
    }


@router.post("/import", response_model=JobCreateResponse, status_code=201)
async def import_places(
    payload: DiscoveryImportRequest, user: Dict[str, Any] = Depends(get_current_user)
) -> Any:
    """Queue selected discovery results as scraping jobs in a project."""
    project = await get_owned_project(payload.project_id, user)
    accepted, rejected = parse_url_list(payload.urls)
    if not accepted:
        return {"created": [], "rejected": rejected}

    db = get_db()

    # Same skip rule as manual submission: do not re-scrape what this project
    # already has, so a repeated import does not burn quota.
    existing = set()
    async for job in db.scrape_jobs.find(
        {
            "project_id": project["_id"],
            "source_url": {"$in": accepted},
            "status": {"$in": ["completed", "pending", "running"]},
        },
        {"source_url": 1},
    ):
        existing.add(job["source_url"])

    if existing:
        rejected.extend(
            {"url": url, "reason": "Sudah pernah diproses di project ini"}
            for url in accepted
            if url in existing
        )
        accepted = [url for url in accepted if url not in existing]

    if not accepted:
        return {"created": [], "rejected": rejected}

    # Reuse the quota check that guards manual submission.
    from app.routers.scrape import _check_quota

    await _check_quota(user, len(accepted))

    now = datetime.now(timezone.utc)
    docs = [
        {
            "project_id": project["_id"],
            "tenant_id": project.get("tenant_id"),
            "created_by": user["_id"],
            "source_url": url,
            "status": "pending",
            "attempts": 0,
            "error_message": None,
            "lead_id": None,
            "pages_crawled": 0,
            "discovered_via": "openstreetmap",
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
            "action": "discovery_imported",
            "target": project["name"],
            "detail": f"{len(docs)} URL dari OpenStreetMap",
            "created_at": now,
        }
    )
    notify_new_jobs()

    from app.serializers import job_out

    return {
        "created": [job_out(doc, project["name"]) for doc in docs],
        "rejected": rejected,
    }
