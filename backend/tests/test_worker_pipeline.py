"""Tests for the scrape worker: crawl -> extract -> lead -> audit, plus retries."""
from datetime import datetime, timezone

import httpx
import pytest
from bson import ObjectId

from app.models.common import JobStatus
from app.services import jobs as jobs_service
from app.services.scraper import CrawlResult, ScrapeError

pytestmark = pytest.mark.asyncio

HOMEPAGE = """
<html><head><title>Warung Kopi Senja</title>
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body><h1>Warung Kopi Senja</h1>
<p>Alamat: Jl. Kemang Raya No. 12, Jakarta Selatan 12730</p>
<a href="https://wa.me/6281234567890">Chat WhatsApp</a>
<a href="mailto:halo@kopisenja.co.id">Email</a>
<a class="btn" href="#pesan">Pesan Sekarang</a>
</body></html>
"""


@pytest.fixture
async def job(mock_db):
    project_id, tenant_id = ObjectId(), ObjectId()
    inserted = await mock_db.scrape_jobs.insert_one(
        {
            "project_id": project_id,
            "tenant_id": tenant_id,
            "created_by": ObjectId(),
            "source_url": "https://warungkopisenja.co.id/",
            "status": JobStatus.RUNNING.value,
            "attempts": 1,
            "error_message": None,
            "lead_id": None,
            "pages_crawled": 0,
            "created_at": datetime.now(timezone.utc),
            "started_at": datetime.now(timezone.utc),
            "completed_at": None,
        }
    )
    return await mock_db.scrape_jobs.find_one({"_id": inserted.inserted_id})


class TestSuccessfulJob:
    async def test_creates_lead_and_audit(self, mock_db, job, monkeypatch):
        from app.services.extractor import extract_from_page, merge_page_results

        async def fake_scrape(url):
            pages = [extract_from_page(HOMEPAGE, url)]
            contact = merge_page_results(pages).to_dict()
            contact["website_url"] = url
            crawl = CrawlResult(root_html=HOMEPAGE, pages=pages, fetched_urls=[url])
            return contact, crawl

        monkeypatch.setattr(jobs_service, "scrape_url", fake_scrape)
        await jobs_service.process_job(job)

        updated = await mock_db.scrape_jobs.find_one({"_id": job["_id"]})
        assert updated["status"] == JobStatus.COMPLETED.value
        assert updated["pages_crawled"] == 1
        assert updated["lead_id"] is not None
        assert updated["error_message"] is None

        lead = await mock_db.leads.find_one({"_id": updated["lead_id"]})
        assert lead["business_name"] == "Warung Kopi Senja"
        assert lead["whatsapp_number"] == "+6281234567890"
        assert lead["email"] == "halo@kopisenja.co.id"
        assert lead["region"] == "jakarta_selatan"
        assert lead["status"] == "new"
        assert isinstance(lead["audit_score"], int)

        audit = await mock_db.website_audits.find_one({"lead_id": lead["_id"]})
        assert audit["score"] == lead["audit_score"]
        assert audit["breakdown"]

    async def test_rerunning_same_url_updates_rather_than_duplicates(self, mock_db, job, monkeypatch):
        from app.services.extractor import extract_from_page, merge_page_results

        async def fake_scrape(url):
            pages = [extract_from_page(HOMEPAGE, url)]
            contact = merge_page_results(pages).to_dict()
            contact["website_url"] = url
            return contact, CrawlResult(root_html=HOMEPAGE, pages=pages, fetched_urls=[url])

        monkeypatch.setattr(jobs_service, "scrape_url", fake_scrape)
        await jobs_service.process_job(job)
        await jobs_service.process_job(job)

        assert await mock_db.leads.count_documents({"project_id": job["project_id"]}) == 1
        # Each run still records its own audit so history is preserved.
        assert await mock_db.website_audits.count_documents({}) == 2


class TestFailureHandling:
    async def test_scrape_error_requeues_until_retries_exhausted(self, mock_db, job, monkeypatch):
        async def failing(url):
            raise ScrapeError("Diblokir oleh robots.txt")

        monkeypatch.setattr(jobs_service, "scrape_url", failing)
        monkeypatch.setattr(jobs_service.settings, "scraper_max_retries", 2)

        await jobs_service.process_job(job)
        requeued = await mock_db.scrape_jobs.find_one({"_id": job["_id"]})
        assert requeued["status"] == JobStatus.PENDING.value
        assert "robots.txt" in requeued["error_message"]

        # Once attempts pass the retry budget the job is marked failed for good.
        await mock_db.scrape_jobs.update_one({"_id": job["_id"]}, {"$set": {"attempts": 3}})
        exhausted = await mock_db.scrape_jobs.find_one({"_id": job["_id"]})
        await jobs_service.process_job(exhausted)

        final = await mock_db.scrape_jobs.find_one({"_id": job["_id"]})
        assert final["status"] == JobStatus.FAILED.value
        assert final["completed_at"] is not None

    async def test_unexpected_error_does_not_escape(self, mock_db, job, monkeypatch):
        async def boom(url):
            raise httpx.ConnectError("dns failure")

        monkeypatch.setattr(jobs_service, "scrape_url", boom)
        monkeypatch.setattr(jobs_service.settings, "scraper_max_retries", 0)

        await jobs_service.process_job(job)  # must not raise
        final = await mock_db.scrape_jobs.find_one({"_id": job["_id"]})
        assert final["status"] == JobStatus.FAILED.value

    async def test_failure_is_written_to_the_audit_log(self, mock_db, job, monkeypatch):
        async def failing(url):
            raise ScrapeError("HTTP 403")

        monkeypatch.setattr(jobs_service, "scrape_url", failing)
        monkeypatch.setattr(jobs_service.settings, "scraper_max_retries", 0)
        await jobs_service.process_job(job)

        log = await mock_db.activity_logs.find_one({"action": "scrape_failed"})
        assert log is not None
        assert "403" in log["detail"]


class TestQueueClaiming:
    async def test_claim_marks_running_and_is_exclusive(self, mock_db):
        await mock_db.scrape_jobs.insert_one(
            {
                "project_id": ObjectId(), "tenant_id": ObjectId(),
                "source_url": "https://a.co.id/", "status": JobStatus.PENDING.value,
                "attempts": 0, "created_at": datetime.now(timezone.utc),
            }
        )
        first = await jobs_service._claim_job()
        assert first is not None
        assert first["status"] == JobStatus.RUNNING.value
        assert first["attempts"] == 1
        # No pending jobs remain, so a second worker gets nothing.
        assert await jobs_service._claim_job() is None

    async def test_stale_running_jobs_are_requeued(self, mock_db):
        from datetime import timedelta

        await mock_db.scrape_jobs.insert_one(
            {
                "project_id": ObjectId(), "tenant_id": ObjectId(),
                "source_url": "https://stale.co.id/", "status": JobStatus.RUNNING.value,
                "attempts": 1, "created_at": datetime.now(timezone.utc),
                "started_at": datetime.now(timezone.utc) - timedelta(hours=2),
            }
        )
        assert await jobs_service._requeue_stale_jobs() == 1
        job = await mock_db.scrape_jobs.find_one({"source_url": "https://stale.co.id/"})
        assert job["status"] == JobStatus.PENDING.value
