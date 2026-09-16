"""End-to-end API tests covering the MVP user flow from the brief."""
import pytest

pytestmark = pytest.mark.asyncio


class TestAuth:
    async def test_register_creates_tenant_and_returns_token(self, client):
        response = await client.post(
            "/api/auth/register",
            json={
                "company_name": "Studio Kreatif",
                "name": "Siti Rahayu",
                "email": "siti@studio.co.id",
                "password": "password-kuat-123",
            },
        )
        assert response.status_code == 201
        assert response.json()["access_token"]

    async def test_duplicate_email_rejected(self, client):
        payload = {
            "company_name": "A", "name": "Aa", "email": "dup@x.co.id", "password": "password-123",
        }
        payload["company_name"] = "Agency A"
        assert (await client.post("/api/auth/register", json=payload)).status_code == 201
        assert (await client.post("/api/auth/register", json=payload)).status_code == 409

    async def test_login_and_me(self, auth_client):
        me = await auth_client.get("/api/auth/me")
        assert me.status_code == 200
        body = me.json()
        assert body["user"]["email"] == "budi@agency.co.id"
        assert body["user"]["role"] == "user_tenant"
        assert body["tenant"]["company_name"] == "Agency Nusantara"

    async def test_wrong_password_rejected(self, auth_client):
        response = await auth_client.post(
            "/api/auth/login", json={"email": "budi@agency.co.id", "password": "salah"}
        )
        assert response.status_code == 401

    async def test_protected_route_requires_token(self, client):
        assert (await client.get("/api/projects")).status_code == 401

    async def test_tampered_token_rejected(self, client):
        client.headers["Authorization"] = "Bearer not.a.real.token"
        assert (await client.get("/api/projects")).status_code == 401


class TestProjectsAndJobs:
    async def test_create_and_list_project(self, auth_client):
        created = await auth_client.post(
            "/api/projects",
            json={"name": "Kuliner Jaksel", "target_region": "jakarta_selatan"},
        )
        assert created.status_code == 201
        project = created.json()
        assert project["name"] == "Kuliner Jaksel"

        listed = await auth_client.get("/api/projects")
        assert listed.status_code == 200
        assert len(listed.json()) == 1

    async def test_job_submission_validates_urls(self, auth_client):
        project = (
            await auth_client.post("/api/projects", json={"name": "Proyek Uji", "target_region": "jakarta"})
        ).json()

        response = await auth_client.post(
            "/api/scrape/jobs",
            json={
                "project_id": project["id"],
                "urls": [
                    "warungkopi.co.id",
                    "https://warungkopi.co.id/",   # duplicate of the above
                    "http://127.0.0.1/admin",      # SSRF attempt
                    "ftp://bad.com",               # unsupported scheme
                    "butikhijab.id",
                ],
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert len(body["created"]) == 2
        assert {job["source_url"] for job in body["created"]} == {
            "https://warungkopi.co.id/",
            "https://butikhijab.id/",
        }
        reasons = {item["url"]: item["reason"] for item in body["rejected"]}
        assert len(reasons) == 3
        assert all(job["status"] == "pending" for job in body["created"])

    async def test_bulk_paste_string_is_accepted(self, auth_client):
        project = (
            await auth_client.post("/api/projects", json={"name": "P2", "target_region": "bogor"})
        ).json()
        response = await auth_client.post(
            "/api/scrape/jobs",
            json={"project_id": project["id"], "urls": "toko-a.co.id\ntoko-b.co.id"},
        )
        assert response.status_code == 201
        assert len(response.json()["created"]) == 2

    async def test_cannot_submit_to_another_tenants_project(self, auth_client, client, mock_db):
        project = (
            await auth_client.post("/api/projects", json={"name": "Milik A", "target_region": "jakarta"})
        ).json()

        # A second tenant must not see or use the first tenant's project.
        other = await client.post(
            "/api/auth/register",
            json={
                "company_name": "Agency B", "name": "Cici", "email": "cici@b.co.id",
                "password": "password-lain-123",
            },
        )
        token = other.json()["access_token"]
        response = await client.post(
            "/api/scrape/jobs",
            json={"project_id": project["id"], "urls": ["x.co.id"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404


class TestLeadsAuditRedesignExport:
    @pytest.fixture
    async def seeded(self, auth_client, mock_db):
        """A completed lead with an audit, as the worker would leave it."""
        from datetime import datetime, timezone

        from bson import ObjectId

        project = (
            await auth_client.post(
                "/api/projects", json={"name": "Seed", "target_region": "jakarta_selatan"}
            )
        ).json()
        me = (await auth_client.get("/api/auth/me")).json()
        tenant_id = ObjectId(me["tenant"]["id"])
        now = datetime.now(timezone.utc)

        lead = await mock_db.leads.insert_one(
            {
                "project_id": ObjectId(project["id"]),
                "tenant_id": tenant_id,
                "website_url": "https://warungkopisenja.co.id/",
                "business_name": "Warung Kopi Senja",
                "whatsapp_number": "+6281234567890",
                "phone_number": "+62217220091",
                "email": "halo@kopisenja.co.id",
                "address": "Jl. Kemang Raya No. 12, Jakarta Selatan",
                "contact_person": "Budi Santoso",
                "region": "jakarta_selatan",
                "source_page": "https://warungkopisenja.co.id/",
                "field_confidence": {"email": 0.9},
                "audit_score": 38,
                "status": "new",
                "notes": None,
                "tags": [],
                "created_at": now,
            }
        )
        await mock_db.website_audits.insert_one(
            {
                "lead_id": lead.inserted_id,
                "tenant_id": tenant_id,
                "score": 38,
                "grade": "E",
                "breakdown": {"mobile_friendly": 4, "cta_clarity": 6, "contact_clarity": 16,
                              "structure": 6, "visual_impression": 6},
                "issues": [{"code": "no_cta", "title": "Tidak ada CTA", "severity": "high", "detail": "x"}],
                "strengths": ["Nomor WhatsApp publik tersedia."],
                "opportunity_summary": "Peluang redesign tinggi.",
                "redesign_summary": "Fokus pada CTA.",
                "created_at": now,
            }
        )
        return {"project_id": project["id"], "lead_id": str(lead.inserted_id)}

    async def test_lead_list_and_detail(self, auth_client, seeded):
        listed = await auth_client.get("/api/leads")
        assert listed.status_code == 200
        body = listed.json()
        assert body["total"] == 1
        assert body["items"][0]["business_name"] == "Warung Kopi Senja"

        detail = await auth_client.get(f"/api/leads/{seeded['lead_id']}")
        assert detail.status_code == 200
        assert detail.json()["whatsapp_number"] == "+6281234567890"

    async def test_search_and_region_filters(self, auth_client, seeded):
        assert (await auth_client.get("/api/leads?search=Senja")).json()["total"] == 1
        assert (await auth_client.get("/api/leads?search=TidakAda")).json()["total"] == 0
        assert (await auth_client.get("/api/leads?region=jakarta_selatan")).json()["total"] == 1
        assert (await auth_client.get("/api/leads?region=bekasi")).json()["total"] == 0
        assert (await auth_client.get("/api/leads?max_score=40")).json()["total"] == 1
        assert (await auth_client.get("/api/leads?min_score=80")).json()["total"] == 0

    async def test_region_facets(self, auth_client, seeded):
        facets = (await auth_client.get("/api/leads/regions")).json()
        assert {"region": "jakarta_selatan", "count": 1} in facets

    async def test_update_lead_notes_and_status(self, auth_client, seeded):
        response = await auth_client.patch(
            f"/api/leads/{seeded['lead_id']}",
            json={"status": "contacted", "notes": "Sudah WA, minta proposal.", "tags": ["prioritas", "kuliner"]},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "contacted"
        assert body["notes"] == "Sudah WA, minta proposal."
        assert body["tags"] == ["kuliner", "prioritas"]

    async def test_get_audit(self, auth_client, seeded):
        audit = await auth_client.get(f"/api/audits/{seeded['lead_id']}")
        assert audit.status_code == 200
        assert audit.json()["score"] == 38
        assert audit.json()["grade"] == "E"

    async def test_generate_and_download_redesign(self, auth_client, seeded):
        generated = await auth_client.post(f"/api/redesign/{seeded['lead_id']}/generate")
        assert generated.status_code == 201
        body = generated.json()
        assert body["version"] == 1
        assert "Jakarta Selatan" in body["headline"]
        assert body["sections"]

        fetched = await auth_client.get(f"/api/redesign/{seeded['lead_id']}")
        assert fetched.status_code == 200

        download = await auth_client.get(f"/api/redesign/{seeded['lead_id']}/download")
        assert download.status_code == 200
        assert "attachment" in download.headers["content-disposition"]
        html = download.text
        assert html.startswith("<!DOCTYPE html>")
        assert "cdn.tailwindcss.com" in html
        assert "wa.me/6281234567890" in html

    async def test_regenerate_increments_version(self, auth_client, seeded):
        await auth_client.post(f"/api/redesign/{seeded['lead_id']}/generate")
        second = await auth_client.post(f"/api/redesign/{seeded['lead_id']}/generate")
        assert second.json()["version"] == 2

    async def test_export_csv(self, auth_client, seeded):
        response = await auth_client.get("/api/exports/leads.csv")
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        text = response.text
        assert text.startswith("﻿")
        assert "business_name" in text
        assert "Warung Kopi Senja" in text
        assert "Jakarta Selatan" in text

    async def test_export_respects_filters(self, auth_client, seeded):
        empty = await auth_client.get("/api/exports/leads.csv?region=bekasi")
        assert "Warung Kopi Senja" not in empty.text


class TestAdmin:
    async def test_tenant_user_cannot_reach_admin(self, auth_client):
        assert (await auth_client.get("/api/admin/stats")).status_code == 403
        assert (await auth_client.get("/api/admin/users")).status_code == 403

    async def test_admin_sees_cross_tenant_stats(self, admin_client, mock_db):
        stats = await admin_client.get("/api/admin/stats")
        assert stats.status_code == 200
        assert "tenants" in stats.json()

        users = await admin_client.get("/api/admin/users")
        assert users.status_code == 200
        assert any(user["role"] == "admin_internal" for user in users.json())


class TestJobStatusFiltering:
    """Covers the query-param enum paths that unwrap .value."""

    @pytest.fixture
    async def project_with_jobs(self, auth_client, mock_db):
        from bson import ObjectId

        project = (
            await auth_client.post(
                "/api/projects", json={"name": "Filter Test", "target_region": "depok"}
            )
        ).json()
        await auth_client.post(
            "/api/scrape/jobs", json={"project_id": project["id"], "urls": ["a-satu.co.id", "b-dua.co.id"]}
        )
        # Mark one job failed so each status filter has something to match.
        await mock_db.scrape_jobs.update_one(
            {"project_id": ObjectId(project["id"]), "source_url": "https://a-satu.co.id/"},
            {"$set": {"status": "failed", "error_message": "HTTP 404"}},
        )
        return project

    async def test_filter_by_status(self, auth_client, project_with_jobs):
        failed = await auth_client.get("/api/scrape/jobs?status=failed")
        assert failed.status_code == 200
        assert len(failed.json()) == 1
        assert failed.json()[0]["status"] == "failed"

        pending = await auth_client.get("/api/scrape/jobs?status=pending")
        assert len(pending.json()) == 1

    async def test_invalid_status_rejected(self, auth_client, project_with_jobs):
        assert (await auth_client.get("/api/scrape/jobs?status=bogus")).status_code == 422

    async def test_retry_resets_failed_job(self, auth_client, project_with_jobs):
        failed_id = (await auth_client.get("/api/scrape/jobs?status=failed")).json()[0]["id"]
        response = await auth_client.post(f"/api/scrape/jobs/{failed_id}/retry")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "pending"
        assert body["attempts"] == 0
        assert body["error_message"] is None

    async def test_cannot_retry_a_pending_job(self, auth_client, project_with_jobs):
        pending_id = (await auth_client.get("/api/scrape/jobs?status=pending")).json()[0]["id"]
        assert (await auth_client.post(f"/api/scrape/jobs/{pending_id}/retry")).status_code == 409

    async def test_job_detail_and_bad_id(self, auth_client, project_with_jobs):
        job_id = (await auth_client.get("/api/scrape/jobs")).json()[0]["id"]
        assert (await auth_client.get(f"/api/scrape/jobs/{job_id}")).status_code == 200
        assert (await auth_client.get("/api/scrape/jobs/not-an-objectid")).status_code == 400
