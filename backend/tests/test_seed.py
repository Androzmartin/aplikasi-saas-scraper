"""The demo seed script.

It is the first thing a new install runs, so it gets tested like anything else.
"""
import pytest

from app.seed import DEMO_LEADS, seed
from app.security import verify_password
from app.services.plans import get_plan

pytestmark = pytest.mark.asyncio


class TestAccountSeed:
    async def test_creates_a_usable_account(self, mock_db):
        result = await seed(mock_db, demo=False, password="rahasia-demo-123")
        assert result["created"] is True

        user = await mock_db.users.find_one({"email": "demo@agency.co.id"})
        assert user is not None
        assert user["role"] == "user_tenant"
        # The printed password must actually work.
        assert verify_password("rahasia-demo-123", user["password_hash"])

        tenant = await mock_db.tenants.find_one({"_id": user["tenant_id"]})
        assert tenant["plan_name"] == "starter"
        assert tenant["plan_expires_at"] is not None
        assert await mock_db.projects.count_documents({"tenant_id": tenant["_id"]}) == 1

    async def test_running_twice_does_not_duplicate(self, mock_db):
        await seed(mock_db, password="rahasia-demo-123")
        second = await seed(mock_db, password="rahasia-demo-123")
        assert second["created"] is False
        assert await mock_db.users.count_documents({"email": "demo@agency.co.id"}) == 1

    async def test_details_are_overridable(self, mock_db):
        await seed(
            mock_db, password="rahasia-demo-123",
            email="Owner@Agency.CO.ID", company="Agency Saya", name="Pak Owner",
        )
        # The email is normalised, otherwise login would not find it.
        user = await mock_db.users.find_one({"email": "owner@agency.co.id"})
        assert user["name"] == "Pak Owner"
        tenant = await mock_db.tenants.find_one({"_id": user["tenant_id"]})
        assert tenant["company_name"] == "Agency Saya"

    async def test_plain_seed_leaves_the_project_empty(self, mock_db):
        result = await seed(mock_db, demo=False, password="rahasia-demo-123")
        assert result["leads"] == 0
        assert await mock_db.leads.count_documents({}) == 0


class TestDemoSeed:
    @pytest.fixture
    async def seeded(self, mock_db):
        return await seed(mock_db, demo=True, password="rahasia-demo-123")

    async def test_populates_every_screen(self, mock_db, seeded):
        assert seeded["leads"] == len(DEMO_LEADS)
        assert seeded["jobs"] == len(DEMO_LEADS)
        assert seeded["redesigns"] == 1
        assert await mock_db.website_audits.count_documents({}) == len(DEMO_LEADS)
        assert await mock_db.payments.count_documents({"status": "paid"}) == 1
        assert await mock_db.activity_logs.count_documents({}) >= 1

    async def test_audit_scores_are_spread_not_identical(self, mock_db, seeded):
        """A single repeated score would make the analytics page meaningless."""
        scores = [lead["audit_score"] async for lead in mock_db.leads.find({})]
        assert all(0 <= score <= 100 for score in scores)
        assert len(set(scores)) > 1, scores

    async def test_regions_cover_jakarta_and_bodetabek(self, mock_db, seeded):
        regions = {lead["region"] async for lead in mock_db.leads.find({})}
        assert "jakarta_selatan" in regions
        assert regions & {"bogor", "depok", "tangerang", "bekasi"}

    async def test_job_states_are_exercisable(self, mock_db, seeded):
        states = {job["status"] async for job in mock_db.scrape_jobs.find({})}
        # A failed job is needed for the retry button to be reachable.
        assert {"completed", "running", "failed"} <= states

        failed = await mock_db.scrape_jobs.find_one({"status": "failed"})
        assert failed["error_message"]

    async def test_lead_statuses_cover_the_funnel(self, mock_db, seeded):
        statuses = {lead["status"] async for lead in mock_db.leads.find({})}
        assert {"new", "contacted", "qualified"} <= statuses

    async def test_redesign_is_downloadable_without_object_storage(self, mock_db, seeded):
        """No storage_key is seeded, so download must fall back to preview_html."""
        doc = await mock_db.redesign_outputs.find_one({})
        assert doc.get("storage_key") is None
        assert doc["preview_html"].startswith("<!DOCTYPE html>")
        assert "cdn.tailwindcss.com" in doc["preview_html"]
        assert doc["approval_status"] == "approved"

    async def test_demo_urls_are_obviously_fictional(self):
        """The seed must never point a scraper at somebody's real website."""
        for row in DEMO_LEADS:
            assert "contoh-" in row["website_url"], row["website_url"]
            if row["email"]:
                assert "contoh-" in row["email"], row["email"]


class TestSeededDataWorksThroughTheApi:
    async def test_login_and_browse(self, client, mock_db):
        await seed(mock_db, demo=True, email="demo@agency.co.id", password="rahasia-demo-123")

        token = (
            await client.post(
                "/api/auth/login",
                json={"email": "demo@agency.co.id", "password": "rahasia-demo-123"},
            )
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        leads = await client.get("/api/leads", headers=headers)
        assert leads.status_code == 200
        assert leads.json()["total"] == len(DEMO_LEADS)

        lead_id = leads.json()["items"][0]["id"]
        assert (await client.get(f"/api/audits/{lead_id}", headers=headers)).status_code == 200

        analytics = await client.get("/api/analytics/overview", headers=headers)
        assert analytics.json()["total_leads"] == len(DEMO_LEADS)
        assert analytics.json()["average_score"] is not None

        subscription = await client.get("/api/billing/subscription", headers=headers)
        assert subscription.json()["plan_code"] == "starter"

        payments = await client.get("/api/billing/payments", headers=headers)
        assert len(payments.json()) == 1

    async def test_seeded_redesign_downloads(self, client, mock_db):
        await seed(mock_db, demo=True, email="demo@agency.co.id", password="rahasia-demo-123")
        token = (
            await client.post(
                "/api/auth/login",
                json={"email": "demo@agency.co.id", "password": "rahasia-demo-123"},
            )
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        doc = await mock_db.redesign_outputs.find_one({})
        lead_id = str(doc["lead_id"])

        assert (await client.get(f"/api/redesign/{lead_id}", headers=headers)).status_code == 200
        download = await client.get(f"/api/redesign/{lead_id}/download", headers=headers)
        assert download.status_code == 200
        assert download.text.startswith("<!DOCTYPE html>")

    async def test_seeded_proposal_renders(self, client, mock_db):
        await seed(mock_db, demo=True, email="demo@agency.co.id", password="rahasia-demo-123")
        token = (
            await client.post(
                "/api/auth/login",
                json={"email": "demo@agency.co.id", "password": "rahasia-demo-123"},
            )
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        lead = await mock_db.leads.find_one({})
        proposal = await client.get(f"/api/proposals/{lead['_id']}", headers=headers)
        assert proposal.status_code == 200
        assert lead["business_name"] in proposal.text

    async def test_quota_reflects_the_seeded_plan(self, client, mock_db):
        await seed(mock_db, demo=True, email="demo@agency.co.id", password="rahasia-demo-123")
        token = (
            await client.post(
                "/api/auth/login",
                json={"email": "demo@agency.co.id", "password": "rahasia-demo-123"},
            )
        ).json()["access_token"]
        body = (
            await client.get(
                "/api/billing/subscription", headers={"Authorization": f"Bearer {token}"}
            )
        ).json()
        assert body["monthly_job_quota"] == get_plan("starter").monthly_job_quota
        assert body["jobs_used_this_month"] == len(DEMO_LEADS)
