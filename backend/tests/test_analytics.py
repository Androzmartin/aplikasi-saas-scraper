"""Dashboard analytics aggregation (P2)."""
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def seeded(auth_client, mock_db):
    project_a = (
        await auth_client.post("/api/projects", json={"name": "Proyek A", "target_region": "jakarta"})
    ).json()
    project_b = (
        await auth_client.post("/api/projects", json={"name": "Proyek B", "target_region": "bogor"})
    ).json()
    me = (await auth_client.get("/api/auth/me")).json()
    tenant_id = ObjectId(me["tenant"]["id"])
    now = datetime.now(timezone.utc)

    rows = [
        # project, score, status, region, outreach, days_ago
        (project_a, 20, "new", "jakarta_selatan", None, 0),
        (project_a, 35, "contacted", "jakarta_selatan", now, 1),
        (project_a, 55, "qualified", "bogor", now, 2),
        (project_a, 70, "new", "depok", None, 3),
        (project_a, 90, "rejected", "bekasi", None, 40),   # outside a 30-day window
        (project_b, 45, "new", "bogor", now, 1),
    ]
    lead_ids = []
    for project, score, status, region, sent, days_ago in rows:
        result = await mock_db.leads.insert_one(
            {
                "project_id": ObjectId(project["id"]),
                "tenant_id": tenant_id,
                "website_url": f"https://x{len(lead_ids)}.co.id/",
                "business_name": f"Bisnis {len(lead_ids)}",
                "audit_score": score,
                "status": status,
                "region": region,
                "outreach_sent_at": sent,
                "tags": [],
                "created_at": now - timedelta(days=days_ago),
            }
        )
        lead_ids.append(result.inserted_id)

    await mock_db.redesign_outputs.insert_one(
        {"lead_id": lead_ids[0], "tenant_id": tenant_id, "version": 1, "created_at": now}
    )
    await mock_db.redesign_outputs.insert_one(
        {"lead_id": lead_ids[0], "tenant_id": tenant_id, "version": 2, "created_at": now}
    )
    return {"project_a": project_a["id"], "project_b": project_b["id"]}


class TestOverview:
    async def test_headline_numbers(self, auth_client, seeded):
        body = (await auth_client.get("/api/analytics/overview")).json()
        assert body["total_leads"] == 6
        assert body["scored_leads"] == 6
        assert body["average_score"] == round((20 + 35 + 55 + 70 + 90 + 45) / 6)
        assert body["outreach_sent"] == 3
        assert body["contact_rate"] == 50

    async def test_redesigns_counted_once_per_lead(self, auth_client, seeded):
        """Two versions of the same lead's redesign is still one redesigned lead."""
        assert (await auth_client.get("/api/analytics/overview")).json()["redesigns"] == 1

    async def test_funnel_never_widens(self, auth_client, seeded):
        funnel = (await auth_client.get("/api/analytics/overview")).json()["funnel"]
        counts = [stage["count"] for stage in funnel]
        assert counts == sorted(counts, reverse=True), counts
        assert [stage["key"] for stage in funnel] == ["new", "contacted", "qualified"]

    async def test_funnel_counts_reached_not_current_stage(self, auth_client, seeded):
        funnel = (await auth_client.get("/api/analytics/overview")).json()["funnel"]
        by_key = {stage["key"]: stage["count"] for stage in funnel}
        # contacted(1) + qualified(1) + a still-"new" lead that was messaged(1)
        assert by_key["contacted"] == 3
        assert by_key["qualified"] == 1

    async def test_score_bands_partition_the_scored_leads(self, auth_client, seeded):
        body = (await auth_client.get("/api/analytics/overview")).json()
        bands = {band["key"]: band["count"] for band in body["score_bands"]}
        assert bands["0-39"] == 2      # 20, 35
        assert bands["40-59"] == 2     # 55, 45
        assert bands["60-79"] == 1     # 70
        assert bands["80-100"] == 1    # 90
        assert sum(bands.values()) == body["scored_leads"]

    async def test_regions_sorted_by_volume(self, auth_client, seeded):
        regions = (await auth_client.get("/api/analytics/overview")).json()["regions"]
        counts = [r["count"] for r in regions]
        assert counts == sorted(counts, reverse=True)
        assert all(r["label"] for r in regions)

    async def test_trend_covers_every_day_including_empty_ones(self, auth_client, seeded):
        body = (await auth_client.get("/api/analytics/overview?days=30")).json()
        assert len(body["trend"]) == 30
        assert body["days"] == 30
        # The 40-day-old lead must fall outside the window.
        assert sum(point["count"] for point in body["trend"]) == 5
        dates = [point["date"] for point in body["trend"]]
        assert dates == sorted(dates)

    async def test_range_is_selectable(self, auth_client, seeded):
        assert len((await auth_client.get("/api/analytics/overview?days=90")).json()["trend"]) == 90

    async def test_range_is_bounded(self, auth_client, seeded):
        assert (await auth_client.get("/api/analytics/overview?days=1")).status_code == 422
        assert (await auth_client.get("/api/analytics/overview?days=999")).status_code == 422


class TestScoping:
    async def test_project_filter_applies_to_every_number(self, auth_client, seeded):
        body = (
            await auth_client.get(f"/api/analytics/overview?project_id={seeded['project_b']}")
        ).json()
        assert body["total_leads"] == 1
        assert sum(band["count"] for band in body["score_bands"]) == 1
        # The redesign belongs to a project A lead, so it must not leak in here.
        assert body["redesigns"] == 0

    async def test_other_tenants_see_nothing(self, client, seeded):
        other = await client.post(
            "/api/auth/register",
            json={"company_name": "Agency Lain", "name": "Cici",
                  "email": "cici3@lain.co.id", "password": "password-lain-123"},
        )
        token = other.json()["access_token"]
        body = (
            await client.get("/api/analytics/overview", headers={"Authorization": f"Bearer {token}"})
        ).json()
        assert body["total_leads"] == 0
        assert body["average_score"] is None

    async def test_empty_tenant_does_not_divide_by_zero(self, client):
        other = await client.post(
            "/api/auth/register",
            json={"company_name": "Agency Kosong", "name": "Dedi",
                  "email": "dedi@kosong.co.id", "password": "password-lain-123"},
        )
        token = other.json()["access_token"]
        response = await client.get(
            "/api/analytics/overview", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["contact_rate"] == 0
        assert response.json()["qualified_rate"] == 0

    async def test_requires_authentication(self, client):
        assert (await client.get("/api/analytics/overview")).status_code == 401
