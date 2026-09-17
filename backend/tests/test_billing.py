"""Duitku billing: plans, checkout, callback security and reconciliation."""
import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from app.config import settings
from app.services import duitku
from app.services.plans import (
    FREE_PLAN_CODE,
    PLANS,
    effective_plan,
    extend_expiry,
    get_plan,
    purchasable,
)

pytestmark = pytest.mark.asyncio

MERCHANT = "DXXXX"
API_KEY = "test-merchant-key"


@pytest.fixture(autouse=True)
def duitku_config(monkeypatch):
    monkeypatch.setattr(settings, "duitku_merchant_code", MERCHANT)
    monkeypatch.setattr(settings, "duitku_api_key", API_KEY)
    monkeypatch.setattr(settings, "duitku_production", False)
    yield


def md5(value: str) -> str:
    return hashlib.md5(value.encode()).hexdigest()


def callback_form(order_id: str, amount: str, result_code: str = "00", **overrides):
    form = {
        "merchantCode": MERCHANT,
        "amount": amount,
        "merchantOrderId": order_id,
        "resultCode": result_code,
        "reference": "DTK-REF-1",
        "signature": md5(f"{MERCHANT}{amount}{order_id}{API_KEY}"),
    }
    form.update(overrides)
    return form


class TestPlans:
    async def test_free_plan_is_not_purchasable(self):
        assert not purchasable(FREE_PLAN_CODE)
        assert purchasable("pro")
        assert not purchasable("tidak-ada")

    async def test_unknown_code_falls_back_to_free(self):
        assert get_plan("tidak-ada").code == FREE_PLAN_CODE
        assert get_plan(None).code == FREE_PLAN_CODE

    async def test_paid_plans_cost_more_and_give_more(self):
        paid = [p for p in PLANS.values() if not p.is_free]
        by_price = sorted(paid, key=lambda p: p.price_idr)
        quotas = [p.monthly_job_quota for p in by_price]
        assert quotas == sorted(quotas), "a pricier plan must not give less quota"

    async def test_expired_paid_plan_drops_to_free(self):
        past = datetime.now(timezone.utc) - timedelta(seconds=1)
        assert effective_plan({"plan_name": "pro", "plan_expires_at": past}).code == FREE_PLAN_CODE

    async def test_active_paid_plan_is_kept(self):
        future = datetime.now(timezone.utc) + timedelta(days=3)
        assert effective_plan({"plan_name": "pro", "plan_expires_at": future}).code == "pro"

    async def test_naive_datetimes_are_treated_as_utc(self):
        """Mongo can hand back naive datetimes; comparing them must not explode."""
        naive_future = (datetime.now(timezone.utc) + timedelta(days=3)).replace(tzinfo=None)
        assert effective_plan({"plan_name": "pro", "plan_expires_at": naive_future}).code == "pro"

    async def test_renewal_stacks_on_remaining_time(self):
        current = datetime.now(timezone.utc) + timedelta(days=10)
        new = extend_expiry(current, get_plan("pro"))
        assert (new - current).days == 30

    async def test_renewal_from_expired_starts_now(self):
        past = datetime.now(timezone.utc) - timedelta(days=10)
        new = extend_expiry(past, get_plan("pro"))
        assert 29 <= (new - datetime.now(timezone.utc)).days <= 30


class TestSignatures:
    async def test_inquiry_signature_matches_duitku_formula(self):
        assert duitku.inquiry_signature("ORDER1", 149000) == md5(f"{MERCHANT}ORDER1149000{API_KEY}")

    async def test_status_signature_matches_duitku_formula(self):
        assert duitku.status_signature("ORDER1") == md5(f"{MERCHANT}ORDER1{API_KEY}")

    async def test_callback_signature_matches_duitku_formula(self):
        assert duitku.callback_signature(MERCHANT, "149000", "ORDER1") == md5(
            f"{MERCHANT}149000ORDER1{API_KEY}"
        )

    async def test_valid_callback_signature_accepted(self):
        sig = md5(f"{MERCHANT}149000ORDER1{API_KEY}")
        assert duitku.verify_callback_signature(MERCHANT, "149000", "ORDER1", sig)

    async def test_tampered_fields_rejected(self):
        sig = md5(f"{MERCHANT}149000ORDER1{API_KEY}")
        assert not duitku.verify_callback_signature(MERCHANT, "1000", "ORDER1", sig)
        assert not duitku.verify_callback_signature(MERCHANT, "149000", "ORDER2", sig)
        assert not duitku.verify_callback_signature(MERCHANT, "149000", "ORDER1", "deadbeef")

    async def test_other_merchants_callback_rejected(self):
        """A signed callback for a different merchant is not ours to act on."""
        other = "DYYYY"
        sig = md5(f"{other}149000ORDER1{API_KEY}")
        assert not duitku.verify_callback_signature(other, "149000", "ORDER1", sig)

    async def test_missing_fields_rejected(self):
        assert not duitku.verify_callback_signature("", "", "", "")


class TestSubscriptionApi:
    async def test_new_tenant_starts_on_the_free_plan(self, auth_client):
        """A signup must not hand out a paid plan."""
        body = (await auth_client.get("/api/billing/subscription")).json()
        assert body["plan_code"] == FREE_PLAN_CODE
        assert body["monthly_job_quota"] == PLANS[FREE_PLAN_CODE].monthly_job_quota
        assert body["is_expired"] is False

    async def test_usage_is_counted(self, auth_client):
        project = (
            await auth_client.post("/api/projects", json={"name": "Proyek Kuota", "target_region": "jakarta"})
        ).json()
        await auth_client.post(
            "/api/scrape/jobs", json={"project_id": project["id"], "urls": ["a-satu.co.id", "b-dua.co.id"]}
        )
        body = (await auth_client.get("/api/billing/subscription")).json()
        assert body["jobs_used_this_month"] == 2
        assert body["jobs_remaining"] == body["monthly_job_quota"] - 2

    async def test_expired_plan_is_flagged_and_quota_drops(self, auth_client, mock_db):
        me = (await auth_client.get("/api/auth/me")).json()
        from bson import ObjectId

        await mock_db.tenants.update_one(
            {"_id": ObjectId(me["tenant"]["id"])},
            {"$set": {"plan_name": "pro",
                      "plan_expires_at": datetime.now(timezone.utc) - timedelta(days=1),
                      "monthly_job_quota": 2000}},
        )
        body = (await auth_client.get("/api/billing/subscription")).json()
        assert body["is_expired"] is True
        assert body["plan_code"] == FREE_PLAN_CODE
        assert body["monthly_job_quota"] == PLANS[FREE_PLAN_CODE].monthly_job_quota

    async def test_plans_listed(self, auth_client):
        plans = (await auth_client.get("/api/billing/plans")).json()
        assert {p["code"] for p in plans} == set(PLANS)

    async def test_requires_authentication(self, client):
        assert (await client.get("/api/billing/subscription")).status_code == 401


class TestCheckout:
    async def test_rejects_free_and_unknown_plans(self, auth_client):
        assert (
            await auth_client.post("/api/billing/checkout", json={"plan_code": "free"})
        ).status_code == 400
        assert (
            await auth_client.post("/api/billing/checkout", json={"plan_code": "palsu"})
        ).status_code == 400

    async def test_unconfigured_gateway_reports_clearly(self, auth_client, monkeypatch):
        monkeypatch.setattr(settings, "duitku_merchant_code", "")
        response = await auth_client.post("/api/billing/checkout", json={"plan_code": "pro"})
        assert response.status_code == 503
        assert "Duitku" in response.json()["detail"]

    async def test_successful_checkout_records_a_pending_invoice(
        self, auth_client, mock_db, monkeypatch
    ):
        captured = {}

        async def fake_inquiry(**kwargs):
            captured.update(kwargs)
            return duitku.InquiryResult(
                reference="DTK-REF-9",
                payment_url="https://sandbox.duitku.com/pay/abc",
                va_number="8888001",
                amount=str(kwargs["amount"]),
                raw={},
            )

        monkeypatch.setattr(duitku, "create_inquiry", fake_inquiry)
        response = await auth_client.post("/api/billing/checkout", json={"plan_code": "starter"})
        assert response.status_code == 201
        body = response.json()
        assert body["payment_url"].startswith("https://")
        assert body["payment"]["status"] == "pending"
        assert body["payment"]["amount_idr"] == PLANS["starter"].price_idr

        # The amount sent to Duitku must be the plan's price, never client input.
        assert captured["amount"] == PLANS["starter"].price_idr
        assert captured["callback_url"].endswith("/billing/callback")

        stored = await mock_db.payments.find_one({"merchant_order_id": body["payment"]["merchant_order_id"]})
        assert stored["status"] == "pending"
        # The plan must NOT be active yet.
        assert (await auth_client.get("/api/billing/subscription")).json()["plan_code"] == FREE_PLAN_CODE

    async def test_gateway_failure_marks_the_invoice_failed(self, auth_client, mock_db, monkeypatch):
        async def failing(**kwargs):
            raise duitku.DuitkuError("Duitku sedang gangguan")

        monkeypatch.setattr(duitku, "create_inquiry", failing)
        response = await auth_client.post("/api/billing/checkout", json={"plan_code": "pro"})
        assert response.status_code == 502
        doc = await mock_db.payments.find_one({"plan_code": "pro"})
        assert doc["status"] == "failed"


class TestCallbackSecurity:
    @pytest.fixture
    async def invoice(self, auth_client, mock_db, monkeypatch):
        async def fake_inquiry(**kwargs):
            return duitku.InquiryResult("DTK-1", "https://pay/x", None, str(kwargs["amount"]), {})

        monkeypatch.setattr(duitku, "create_inquiry", fake_inquiry)
        body = (
            await auth_client.post("/api/billing/checkout", json={"plan_code": "starter"})
        ).json()
        return body["payment"]

    async def test_bad_signature_is_rejected(self, client, invoice, mock_db):
        form = callback_form(invoice["merchant_order_id"], str(invoice["amount_idr"]))
        form["signature"] = "0" * 32
        response = await client.post("/api/billing/callback", data=form)
        assert response.status_code == 400
        doc = await mock_db.payments.find_one({"merchant_order_id": invoice["merchant_order_id"]})
        assert doc["status"] == "pending"

    async def test_amount_mismatch_is_rejected(self, client, invoice, mock_db):
        """Duitku's own sample omits this check; a cheap callback must not pass."""
        cheap = "1000"
        response = await client.post(
            "/api/billing/callback",
            data=callback_form(invoice["merchant_order_id"], cheap),
        )
        assert response.status_code == 400
        doc = await mock_db.payments.find_one({"merchant_order_id": invoice["merchant_order_id"]})
        assert doc["status"] == "pending"
        assert (await client.get("/api/billing/subscription")).status_code in (200, 401)

    async def test_unknown_order_is_rejected(self, client, invoice):
        response = await client.post(
            "/api/billing/callback", data=callback_form("ORDER-TIDAK-ADA", "149000")
        )
        assert response.status_code == 404

    async def test_valid_callback_activates_the_plan(self, client, auth_client, invoice, mock_db):
        response = await client.post(
            "/api/billing/callback",
            data=callback_form(invoice["merchant_order_id"], str(invoice["amount_idr"])),
        )
        assert response.status_code == 200
        assert response.text == "SUCCESS"

        doc = await mock_db.payments.find_one({"merchant_order_id": invoice["merchant_order_id"]})
        assert doc["status"] == "paid"
        assert doc["paid_at"] is not None

        subscription = (await auth_client.get("/api/billing/subscription")).json()
        assert subscription["plan_code"] == "starter"
        assert subscription["monthly_job_quota"] == PLANS["starter"].monthly_job_quota
        assert subscription["expires_at"]

    async def test_replayed_callback_does_not_extend_twice(
        self, client, auth_client, invoice, mock_db
    ):
        form = callback_form(invoice["merchant_order_id"], str(invoice["amount_idr"]))
        await client.post("/api/billing/callback", data=form)
        first = (await auth_client.get("/api/billing/subscription")).json()["expires_at"]

        again = await client.post("/api/billing/callback", data=form)
        assert again.status_code == 200  # acknowledged, so Duitku stops retrying
        second = (await auth_client.get("/api/billing/subscription")).json()["expires_at"]
        assert first == second, "a redelivered callback must not extend the plan again"

    async def test_failed_result_code_does_not_activate(self, client, auth_client, invoice, mock_db):
        response = await client.post(
            "/api/billing/callback",
            data=callback_form(invoice["merchant_order_id"], str(invoice["amount_idr"]), result_code="02"),
        )
        assert response.status_code == 200
        doc = await mock_db.payments.find_one({"merchant_order_id": invoice["merchant_order_id"]})
        assert doc["status"] == "failed"
        assert (await auth_client.get("/api/billing/subscription")).json()["plan_code"] == FREE_PLAN_CODE

    async def test_callback_needs_no_authentication(self, client, invoice):
        """Duitku cannot send our bearer token, so the endpoint must be public."""
        import httpx

        # A genuinely anonymous client: the shared fixture carries the tenant's
        # Authorization header, which would hide an auth requirement here.
        transport = httpx.ASGITransport(app=client._transport.app)  # type: ignore[attr-defined]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as anon:
            assert "authorization" not in {k.lower() for k in anon.headers}
            response = await anon.post(
                "/api/billing/callback",
                data=callback_form(invoice["merchant_order_id"], str(invoice["amount_idr"])),
            )
        assert response.status_code == 200
        assert response.text == "SUCCESS"

    async def test_raw_callback_is_kept_for_audit(self, client, invoice, mock_db):
        await client.post(
            "/api/billing/callback",
            data=callback_form(invoice["merchant_order_id"], str(invoice["amount_idr"])),
        )
        doc = await mock_db.payments.find_one({"merchant_order_id": invoice["merchant_order_id"]})
        assert doc["callback_payload"]["reference"] == "DTK-REF-1"
        assert doc["callback_received_at"] is not None


class TestReconciliation:
    @pytest.fixture
    async def invoice(self, auth_client, monkeypatch):
        async def fake_inquiry(**kwargs):
            return duitku.InquiryResult("DTK-2", "https://pay/y", None, str(kwargs["amount"]), {})

        monkeypatch.setattr(duitku, "create_inquiry", fake_inquiry)
        return (
            await auth_client.post("/api/billing/checkout", json={"plan_code": "pro"})
        ).json()["payment"]

    async def test_sync_activates_when_duitku_says_paid(self, auth_client, invoice, monkeypatch):
        """A lost webhook must not strand the customer on pending."""
        async def paid(order_id):
            return {"statusCode": "00", "statusMessage": "SUCCESS"}

        monkeypatch.setattr(duitku, "check_status", paid)
        response = await auth_client.post(f"/api/billing/payments/{invoice['id']}/sync")
        assert response.status_code == 200
        assert response.json()["status"] == "paid"
        assert (await auth_client.get("/api/billing/subscription")).json()["plan_code"] == "pro"

    async def test_sync_leaves_pending_alone(self, auth_client, invoice, monkeypatch):
        async def pending(order_id):
            return {"statusCode": "01"}

        monkeypatch.setattr(duitku, "check_status", pending)
        assert (
            await auth_client.post(f"/api/billing/payments/{invoice['id']}/sync")
        ).json()["status"] == "pending"

    async def test_sync_marks_expired(self, auth_client, invoice, monkeypatch):
        async def expired(order_id):
            return {"statusCode": "02", "statusMessage": "EXPIRED"}

        monkeypatch.setattr(duitku, "check_status", expired)
        assert (
            await auth_client.post(f"/api/billing/payments/{invoice['id']}/sync")
        ).json()["status"] == "expired"

    async def test_other_tenants_cannot_sync_this_payment(self, client, invoice):
        other = await client.post(
            "/api/auth/register",
            json={"company_name": "Agency Lain", "name": "Cici",
                  "email": "cici9@lain.co.id", "password": "password-lain-123"},
        )
        token = other.json()["access_token"]
        response = await client.post(
            f"/api/billing/payments/{invoice['id']}/sync",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    async def test_payment_history_is_tenant_scoped(self, auth_client, invoice, client):
        mine = (await auth_client.get("/api/billing/payments")).json()
        assert len(mine) == 1

        other = await client.post(
            "/api/auth/register",
            json={"company_name": "Agency Lain 2", "name": "Dedi",
                  "email": "dedi9@lain.co.id", "password": "password-lain-123"},
        )
        token = other.json()["access_token"]
        theirs = await client.get(
            "/api/billing/payments", headers={"Authorization": f"Bearer {token}"}
        )
        assert theirs.json() == []
