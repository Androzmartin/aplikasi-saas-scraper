"""In-process scraping job queue.

A pool of asyncio workers claims pending jobs from MongoDB, crawls the target,
stores the lead, and runs the initial audit. Claiming uses an atomic
find_one_and_update so a job is never processed twice, which also lets the queue
recover jobs left RUNNING by a crash.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from bson import ObjectId

from app.config import settings
from app.db import get_db
from app.models.common import JobStatus
from app.services import audit as audit_service
from app.services.scraper import ScrapeError, scrape_url

logger = logging.getLogger(__name__)

_workers: list[asyncio.Task] = []
_shutdown = asyncio.Event()
_wakeup = asyncio.Event()

IDLE_POLL_SECONDS = 3.0
# Enough page text for the optional AI to understand the business.
AI_CONTEXT_CHARS = 6_000
STALE_RUNNING_MINUTES = 15


def notify_new_jobs() -> None:
    """Wake idle workers immediately after jobs are enqueued."""
    _wakeup.set()


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _claim_job() -> Optional[Dict[str, Any]]:
    db = get_db()
    return await db.scrape_jobs.find_one_and_update(
        {"status": JobStatus.PENDING.value},
        {"$set": {"status": JobStatus.RUNNING.value, "started_at": _now()}, "$inc": {"attempts": 1}},
        sort=[("created_at", 1)],
        return_document=True,
    )


async def _requeue_stale_jobs() -> int:
    """Return jobs stuck in RUNNING (e.g. after a restart) to the pending queue."""
    db = get_db()
    cutoff = _now() - timedelta(minutes=STALE_RUNNING_MINUTES)
    result = await db.scrape_jobs.update_many(
        {"status": JobStatus.RUNNING.value, "started_at": {"$lt": cutoff}},
        {"$set": {"status": JobStatus.PENDING.value, "error_message": "Dijadwalkan ulang setelah timeout"}},
    )
    if result.modified_count:
        logger.info("Requeued %s stale running job(s)", result.modified_count)
    return result.modified_count


async def _record_activity(job: Dict[str, Any], action: str, detail: str) -> None:
    db = get_db()
    await db.activity_logs.insert_one(
        {
            "tenant_id": job.get("tenant_id"),
            "user_id": job.get("created_by"),
            "action": action,
            "target": job.get("source_url"),
            "detail": detail,
            "created_at": _now(),
        }
    )


async def _maybe_capture_screenshots(job: Dict[str, Any], lead_id: ObjectId, url: str) -> None:
    """Best-effort screenshot after a successful scrape. Never fails the job."""
    if not (settings.screenshot_enabled and settings.screenshot_on_scrape):
        return

    from app.services import screenshots as shots

    db = get_db()
    try:
        result = await shots.capture(url, str(lead_id), version=1)
    except shots.ScreenshotUnavailable as exc:
        logger.info("Screenshots skipped for %s: %s", url, exc)
        return
    except Exception:  # noqa: BLE001 - a screenshot is never worth failing a scrape
        logger.exception("Screenshot capture failed for %s", url)
        return

    if not result.any_captured:
        return

    await db.screenshots.update_one(
        {"lead_id": lead_id, "version": 1},
        {
            "$set": {
                "lead_id": lead_id,
                "tenant_id": job.get("tenant_id"),
                "version": 1,
                "keys": result.keys,
                "failures": result.failures,
                "created_at": _now(),
            }
        },
        upsert=True,
    )


async def _upsert_lead(job: Dict[str, Any], data: Dict[str, Any], html: str) -> ObjectId:
    """Create or refresh the lead for this URL within its project."""
    db = get_db()
    now = _now()
    url = job["source_url"]

    audit_result = audit_service.run_audit(html, data)

    # Keep a trimmed copy of the visible text so the optional AI enrichment has
    # the business's own words to work from instead of just its name.
    page_text = ""
    if html:
        try:
            from bs4 import BeautifulSoup

            from app.services.extractor import page_text as extract_text

            page_text = extract_text(BeautifulSoup(html, "lxml"))[:AI_CONTEXT_CHARS]
        except Exception:  # noqa: BLE001 - context is a nicety, never fatal
            page_text = ""

    lead_doc = {
        "project_id": job["project_id"],
        "tenant_id": job["tenant_id"],
        "website_url": url,
        "business_name": data.get("business_name"),
        "whatsapp_number": data.get("whatsapp_number"),
        "phone_number": data.get("phone_number"),
        "email": data.get("email"),
        "address": data.get("address"),
        "contact_person": data.get("contact_person"),
        "region": data.get("region"),
        "source_page": data.get("source_page"),
        "field_sources": data.get("field_sources", {}),
        "field_confidence": data.get("field_confidence", {}),
        "social_links": data.get("social_links", {}),
        # The business's own photos, used to build the redesign concept.
        "images": data.get("images", {"logo": None, "gallery": []}),
        "audit_score": audit_result["score"],
        "page_text": page_text,
        "updated_at": now,
    }

    existing = await db.leads.find_one({"project_id": job["project_id"], "website_url": url})
    if existing:
        lead_id = existing["_id"]
        await db.leads.update_one({"_id": lead_id}, {"$set": lead_doc})
    else:
        lead_doc.update({"status": "new", "notes": None, "tags": [], "created_at": now})
        insert = await db.leads.insert_one(lead_doc)
        lead_id = insert.inserted_id

    await db.website_audits.insert_one(
        {
            "lead_id": lead_id,
            "tenant_id": job["tenant_id"],
            **audit_result,
            "created_at": now,
        }
    )
    return lead_id


async def process_job(job: Dict[str, Any]) -> None:
    db = get_db()
    job_id = job["_id"]
    url = job["source_url"]

    try:
        data, crawl = await scrape_url(url)
        lead_id = await _upsert_lead(job, data, crawl.root_html)
        await _maybe_capture_screenshots(job, lead_id, url)
        await db.scrape_jobs.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": JobStatus.COMPLETED.value,
                    "completed_at": _now(),
                    "error_message": None,
                    "lead_id": lead_id,
                    "pages_crawled": len(crawl.fetched_urls),
                }
            },
        )
        await _record_activity(job, "scrape_completed", f"{len(crawl.fetched_urls)} halaman dirayapi")
        logger.info("Job %s completed (%s pages)", job_id, len(crawl.fetched_urls))

    except ScrapeError as exc:
        await _fail_or_retry(job, str(exc))
    except Exception as exc:  # noqa: BLE001 - one bad site must not kill the worker
        logger.exception("Unexpected error processing job %s", job_id)
        await _fail_or_retry(job, f"Kesalahan tak terduga: {exc.__class__.__name__}")


async def _fail_or_retry(job: Dict[str, Any], message: str) -> None:
    db = get_db()
    attempts = job.get("attempts", 1)
    if attempts <= settings.scraper_max_retries:
        await db.scrape_jobs.update_one(
            {"_id": job["_id"]},
            {"$set": {"status": JobStatus.PENDING.value, "error_message": f"{message} (percobaan {attempts})"}},
        )
        logger.info("Job %s will retry (attempt %s): %s", job["_id"], attempts, message)
        notify_new_jobs()
        return

    await db.scrape_jobs.update_one(
        {"_id": job["_id"]},
        {"$set": {"status": JobStatus.FAILED.value, "completed_at": _now(), "error_message": message}},
    )
    await _record_activity(job, "scrape_failed", message)
    logger.warning("Job %s failed permanently: %s", job["_id"], message)


async def _worker(worker_id: int) -> None:
    logger.info("Scrape worker %s started", worker_id)
    while not _shutdown.is_set():
        try:
            job = await _claim_job()
        except Exception:  # noqa: BLE001 - keep the loop alive through DB hiccups
            logger.exception("Worker %s failed to claim a job", worker_id)
            job = None

        if job is None:
            _wakeup.clear()
            try:
                await asyncio.wait_for(_wakeup.wait(), timeout=IDLE_POLL_SECONDS)
            except asyncio.TimeoutError:
                pass
            continue

        await process_job(job)

    logger.info("Scrape worker %s stopped", worker_id)


async def start_workers() -> None:
    if _workers:
        return
    _shutdown.clear()
    try:
        await _requeue_stale_jobs()
    except Exception:  # noqa: BLE001 - startup must not hard-fail on this
        logger.exception("Could not requeue stale jobs at startup")

    for index in range(max(1, settings.scraper_worker_concurrency)):
        _workers.append(asyncio.create_task(_worker(index + 1)))


async def stop_workers() -> None:
    _shutdown.set()
    _wakeup.set()
    for task in _workers:
        task.cancel()
    for task in _workers:
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
    _workers.clear()
