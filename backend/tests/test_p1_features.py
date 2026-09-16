"""Tests for the P1 features: approval gate, dedupe, bulk retry, screenshots."""
from datetime import datetime, timezone

import pytest
from bson import ObjectId

from app.config import settings
from app.services import screenshots as shots

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def lead_fixture(auth_client, mock_db):
    project = (
        await auth_client.post(
            "/api/projects", json={"name": "Proyek P1", "target_region": "jakarta_selatan"}
        )
    ).json()
    me = (await auth_client.get("/api/auth/me")).json()
    tenant_id = ObjectId(me["tenant"]["id"])
    lead = await mock_db.leads.insert_one(
        {
            "project_id": ObjectId(project["id"]),
            "tenant_id": tenant_id,
            "website_url": "https://warungkopisenja.co.id/",
            "business_name": "Warung Kopi Senja",
            "whatsapp_number": "+6281234567890",
            "region": "jakarta_selatan",
            "audit_score": 34,
            "status": "new",
            "tags": [],
            "created_at": datetime.now(timezone.utc),
        }
    )
    return {"project_id": project["id"], "lead_id": str(lead.inserted_id)}


class TestApprovalGate:
    async def test_download_open_when_approval_disabled(self, auth_client, lead_fixture, monkeypatch):
        monkeypatch.setattr(settings, "require_redesign_approval", False)
        generated = await auth_client.post(f"/api/redesign/{lead_fixture['lead_id']}/generate")
        assert generated.status_code == 201
        body = generated.json()
        assert body["approval_status"] == "approved"
        assert body["can_download"] is True
        assert (
            await auth_client.get(f"/api/redesign/{lead_fixture['lead_id']}/download")
        ).status_code == 200

    async def test_download_blocked_until_admin_approves(
        self, auth_client, admin_client, lead_fixture, monkeypatch
    ):
        monkeypatch.setattr(settings, "require_redesign_approval", True)

        generated = await auth_client.post(f"/api/redesign/{lead_fixture['lead_id']}/generate")
        body = generated.json()
        assert body["approval_status"] == "pending"
        assert body["can_download"] is False
        assert body["approval_required"] is True

        blocked = await auth_client.get(f"/api/redesign/{lead_fixture['lead_id']}/download")
        assert blocked.status_code == 403
        assert "menunggu persetujuan" in blocked.json()["detail"].lower()

        # The preview itself stays visible so the user can still see the concept.
        assert (await auth_client.get(f"/api/redesign/{lead_fixture['lead_id']}")).status_code == 200

        pending = await admin_client.get("/api/admin/redesigns?status=pending")
        assert pending.status_code == 200
        assert len(pending.json()) == 1
        redesign_id = pending.json()[0]["id"]
        assert pending.json()[0]["business_name"] == "Warung Kopi Senja"

        decided = await admin_client.patch(
            f"/api/admin/redesigns/{redesign_id}/approval",
            json={"status": "approved", "note": "Sudah sesuai standar."},
        )
        assert decided.status_code == 200
        assert decided.json()["approval_status"] == "approved"

        allowed = await auth_client.get(f"/api/redesign/{lead_fixture['lead_id']}/download")
        assert allowed.status_code == 200
        assert allowed.text.startswith("<!DOCTYPE html>")

    async def test_rejection_message_includes_note(
        self, auth_client, admin_client, lead_fixture, monkeypatch
    ):
        monkeypatch.setattr(settings, "require_redesign_approval", True)
        await auth_client.post(f"/api/redesign/{lead_fixture['lead_id']}/generate")
        redesign_id = (await admin_client.get("/api/admin/redesigns")).json()[0]["id"]

        await admin_client.patch(
            f"/api/admin/redesigns/{redesign_id}/approval",
            json={"status": "rejected", "note": "Copy terlalu berlebihan."},
        )
        blocked = await auth_client.get(f"/api/redesign/{lead_fixture['lead_id']}/download")
        assert blocked.status_code == 403
        assert "Copy terlalu berlebihan." in blocked.json()["detail"]

    async def test_admin_can_download_for_review(self, admin_client, auth_client, lead_fixture, monkeypatch):
        monkeypatch.setattr(settings, "require_redesign_approval", True)
        await auth_client.post(f"/api/redesign/{lead_fixture['lead_id']}/generate")
        # The admin needs the file to judge it, so the gate does not apply to them.
        assert (
            await admin_client.get(f"/api/redesign/{lead_fixture['lead_id']}/download")
        ).status_code == 200

    async def test_tenant_cannot_approve_own_redesign(self, auth_client, lead_fixture, monkeypatch):
        monkeypatch.setattr(settings, "require_redesign_approval", True)
        await auth_client.post(f"/api/redesign/{lead_fixture['lead_id']}/generate")
        assert (await auth_client.get("/api/admin/redesigns")).status_code == 403


class TestSkipExisting:
    async def test_already_scraped_urls_are_skipped(self, auth_client, lead_fixture, mock_db):
        project_id = lead_fixture["project_id"]
        first = await auth_client.post(
            "/api/scrape/jobs", json={"project_id": project_id, "urls": ["toko-baru.co.id"]}
        )
        assert len(first.json()["created"]) == 1

        second = await auth_client.post(
            "/api/scrape/jobs", json={"project_id": project_id, "urls": ["toko-baru.co.id"]}
        )
        assert second.json()["created"] == []
        assert "Sudah pernah diproses" in second.json()["rejected"][0]["reason"]

    async def test_skip_can_be_turned_off(self, auth_client, lead_fixture):
        project_id = lead_fixture["project_id"]
        await auth_client.post(
            "/api/scrape/jobs", json={"project_id": project_id, "urls": ["ulang.co.id"]}
        )
        again = await auth_client.post(
            "/api/scrape/jobs",
            json={"project_id": project_id, "urls": ["ulang.co.id"], "skip_existing": False},
        )
        assert len(again.json()["created"]) == 1

    async def test_failed_url_can_be_resubmitted(self, auth_client, lead_fixture, mock_db):
        project_id = lead_fixture["project_id"]
        await auth_client.post(
            "/api/scrape/jobs", json={"project_id": project_id, "urls": ["gagal.co.id"]}
        )
        await mock_db.scrape_jobs.update_one(
            {"source_url": "https://gagal.co.id/"}, {"$set": {"status": "failed"}}
        )
        # A failed URL is not "already done", so submitting it again must work.
        retry = await auth_client.post(
            "/api/scrape/jobs", json={"project_id": project_id, "urls": ["gagal.co.id"]}
        )
        assert len(retry.json()["created"]) == 1


class TestBulkRetry:
    async def test_requeues_only_failed_jobs(self, auth_client, lead_fixture, mock_db):
        project_id = lead_fixture["project_id"]
        await auth_client.post(
            "/api/scrape/jobs",
            json={"project_id": project_id, "urls": ["a-satu.co.id", "b-dua.co.id", "c-tiga.co.id"]},
        )
        await mock_db.scrape_jobs.update_many(
            {"source_url": {"$in": ["https://a-satu.co.id/", "https://b-dua.co.id/"]}},
            {"$set": {"status": "failed", "attempts": 3, "error_message": "HTTP 403"}},
        )

        response = await auth_client.post("/api/scrape/jobs/retry-failed")
        assert response.status_code == 200
        assert response.json()["requeued"] == 2

        assert (await auth_client.get("/api/scrape/jobs?status=failed")).json() == []
        pending = (await auth_client.get("/api/scrape/jobs?status=pending")).json()
        assert len(pending) == 3
        assert all(job["attempts"] == 0 for job in pending if job["source_url"] != "https://c-tiga.co.id/")

    async def test_no_failures_is_a_no_op(self, auth_client, lead_fixture):
        response = await auth_client.post("/api/scrape/jobs/retry-failed")
        assert response.status_code == 200
        assert response.json()["requeued"] == 0


class TestScreenshots:
    async def test_disabled_by_default(self, auth_client, lead_fixture, monkeypatch):
        monkeypatch.setattr(settings, "screenshot_enabled", False)
        response = await auth_client.post(f"/api/screenshots/{lead_fixture['lead_id']}/capture")
        assert response.status_code == 503
        assert "dinonaktifkan" in response.json()["detail"]

    async def test_missing_playwright_reports_clearly(self, auth_client, lead_fixture, monkeypatch):
        monkeypatch.setattr(settings, "screenshot_enabled", True)

        async def unavailable(*args, **kwargs):
            raise shots.ScreenshotUnavailable("Playwright belum terpasang.")

        monkeypatch.setattr(shots, "capture", unavailable)
        response = await auth_client.post(f"/api/screenshots/{lead_fixture['lead_id']}/capture")
        assert response.status_code == 503
        assert "Playwright" in response.json()["detail"]

    async def test_capture_stores_and_serves_images(self, auth_client, lead_fixture, monkeypatch, mock_db):
        monkeypatch.setattr(settings, "screenshot_enabled", True)
        png = b"\x89PNG\r\n\x1a\n" + b"stub-image-bytes"

        async def fake_capture(url, lead_id, version=1, variants=None):
            from app.services.storage import storage

            result = shots.ScreenshotResult()
            for variant in (variants or ["desktop", "mobile"]):
                key = shots.storage_key(lead_id, variant, version)
                storage.put_bytes(key, png)
                result.keys[variant] = key
            return result

        monkeypatch.setattr(shots, "capture", fake_capture)

        created = await auth_client.post(f"/api/screenshots/{lead_fixture['lead_id']}/capture")
        assert created.status_code == 201
        body = created.json()
        assert sorted(body["variants"]) == ["desktop", "mobile"]
        assert body["version"] == 1

        fetched = await auth_client.get(f"/api/screenshots/{lead_fixture['lead_id']}")
        assert fetched.status_code == 200

        image = await auth_client.get(f"/api/screenshots/{lead_fixture['lead_id']}/desktop")
        assert image.status_code == 200
        assert image.headers["content-type"] == "image/png"
        assert image.content == png

    async def test_unknown_variant_404s(self, auth_client, lead_fixture):
        assert (
            await auth_client.get(f"/api/screenshots/{lead_fixture['lead_id']}/tablet")
        ).status_code == 404

    async def test_no_screenshot_yet_404s(self, auth_client, lead_fixture):
        assert (await auth_client.get(f"/api/screenshots/{lead_fixture['lead_id']}")).status_code == 404

    async def test_storage_key_is_namespaced_per_lead_and_version(self):
        key = shots.storage_key("abc123", "desktop", 2)
        assert key == "screenshots/abc123/v2/desktop.png"

    async def test_viewports_cover_desktop_and_mobile(self):
        assert shots.VIEWPORTS["desktop"]["width"] > shots.VIEWPORTS["mobile"]["width"]


class TestEnumUnwrapping:
    """Regression guard: enum-typed fields reach the DB layer from two sources.

    Query params arrive as Enum members; request-body fields are already plain
    strings because ApiModel sets use_enum_values. Calling .value on the latter
    raised AttributeError twice during development, so enum_value handles both.
    """

    async def test_handles_enum_and_string(self):
        from app.models.common import ApprovalStatus, LeadStatus, enum_value

        assert enum_value(ApprovalStatus.APPROVED) == "approved"
        assert enum_value("approved") == "approved"
        assert enum_value(LeadStatus.QUALIFIED) == "qualified"
        assert enum_value(None) is None

    async def test_body_enum_field_is_already_a_string(self):
        from app.models.schemas import ApprovalDecision

        decision = ApprovalDecision(status="approved")
        assert isinstance(decision.status, str)
        assert not hasattr(decision.status, "value")
