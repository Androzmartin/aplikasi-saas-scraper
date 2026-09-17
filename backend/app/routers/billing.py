"""Subscription billing through Duitku.

Security notes for the callback, which is a public unauthenticated endpoint:

1. The signature is verified before anything is read from the payload.
2. The amount is compared against the invoice we created. Duitku's own sample
   code does NOT do this; without it a valid-looking callback could mark a
   1.290.000 plan paid for 1.000.
3. Applying a payment is idempotent - a redelivered callback for an already
   paid invoice is acknowledged and ignored, never applied twice.
4. Duitku is always answered 200 with "SUCCESS" once we have accepted the
   notification, otherwise it keeps retrying. Rejections answer non-200.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import PlainTextResponse, RedirectResponse

from app.config import settings
from app.db import get_db
from app.deps import get_current_user, is_admin, to_object_id
from app.models.schemas import (
    CheckoutRequest,
    CheckoutResponse,
    PaymentOut,
    PlanOut,
    SubscriptionOut,
)
from app.services import duitku
from app.services.plans import (
    effective_plan,
    extend_expiry,
    get_plan,
    list_plans,
    purchasable,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])

PENDING = "pending"
PAID = "paid"
FAILED = "failed"
EXPIRED = "expired"


def _payment_out(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "merchant_order_id": doc.get("merchant_order_id", ""),
        "plan_code": doc.get("plan_code", ""),
        "plan_name": doc.get("plan_name", ""),
        "amount_idr": doc.get("amount_idr", 0),
        "status": doc.get("status", PENDING),
        "payment_url": doc.get("payment_url"),
        "va_number": doc.get("va_number"),
        "reference": doc.get("duitku_reference"),
        "created_at": doc.get("created_at"),
        "paid_at": doc.get("paid_at"),
        "expires_at": doc.get("expires_at"),
    }


def _new_order_id(tenant_id: Any) -> str:
    """Unique, non-sequential order id. Duitku requires uniqueness per merchant."""
    stamp = datetime.now(timezone.utc).strftime("%y%m%d%H%M%S")
    return f"UMKM-{stamp}-{secrets.token_hex(3).upper()}"


async def _tenant_of(user: Dict[str, Any]) -> Dict[str, Any]:
    if not user.get("tenant_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Akun ini tidak terhubung ke tenant, jadi tidak punya langganan.",
        )
    tenant = await get_db().tenants.find_one({"_id": user["tenant_id"]})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant tidak ditemukan")
    return tenant


# --------------------------------------------------------------------- reading


@router.get("/plans", response_model=List[PlanOut])
async def get_plans(_: Dict[str, Any] = Depends(get_current_user)) -> Any:
    return list_plans()


@router.get("/subscription", response_model=SubscriptionOut)
async def get_subscription(user: Dict[str, Any] = Depends(get_current_user)) -> Any:
    """Current plan, quota and this month's usage."""
    db = get_db()
    tenant = await _tenant_of(user)
    plan = effective_plan(tenant)

    period_start = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    used = await db.scrape_jobs.count_documents(
        {"tenant_id": tenant["_id"], "created_at": {"$gte": period_start}}
    )

    stored = get_plan(tenant.get("plan_name"))
    return {
        "plan_code": plan.code,
        "plan_name": plan.name,
        "monthly_job_quota": plan.monthly_job_quota,
        "jobs_used_this_month": used,
        "jobs_remaining": max(0, plan.monthly_job_quota - used),
        "expires_at": tenant.get("plan_expires_at"),
        # True when a paid plan lapsed and the tenant dropped back to free.
        "is_expired": stored.code != plan.code,
        "payment_configured": duitku.is_configured(),
    }


@router.get("/payments", response_model=List[PaymentOut])
async def list_payments(user: Dict[str, Any] = Depends(get_current_user)) -> Any:
    db = get_db()
    query: Dict[str, Any] = {} if is_admin(user) else {"tenant_id": user.get("tenant_id")}
    docs = await db.payments.find(query).sort("created_at", -1).limit(100).to_list(100)
    return [_payment_out(doc) for doc in docs]


# -------------------------------------------------------------------- checkout


@router.post("/checkout", response_model=CheckoutResponse, status_code=201)
async def checkout(
    payload: CheckoutRequest, user: Dict[str, Any] = Depends(get_current_user)
) -> Any:
    """Open a Duitku payment for a plan and hand back its payment URL."""
    if not purchasable(payload.plan_code):
        raise HTTPException(
            status_code=400, detail=f"Paket '{payload.plan_code}' tidak bisa dibeli."
        )
    if not duitku.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Pembayaran belum aktif. Hubungi admin untuk mengatur kredensial Duitku.",
        )

    db = get_db()
    tenant = await _tenant_of(user)
    plan = get_plan(payload.plan_code)
    now = datetime.now(timezone.utc)
    order_id = _new_order_id(tenant["_id"])

    # Record the invoice BEFORE calling Duitku, so a callback that arrives
    # while the response is still in flight already has something to match.
    doc = {
        "merchant_order_id": order_id,
        "tenant_id": tenant["_id"],
        "user_id": user["_id"],
        "plan_code": plan.code,
        "plan_name": plan.name,
        "amount_idr": plan.price_idr,
        "status": PENDING,
        "payment_url": None,
        "va_number": None,
        "duitku_reference": None,
        "created_at": now,
        "paid_at": None,
        "expires_at": now + timedelta(minutes=settings.duitku_expiry_minutes),
    }
    result = await db.payments.insert_one(doc)
    doc["_id"] = result.inserted_id

    try:
        inquiry = await duitku.create_inquiry(
            merchant_order_id=order_id,
            amount=plan.price_idr,
            product_details=f"Langganan {plan.name} - {settings.app_name}",
            email=user.get("email", ""),
            customer_name=tenant.get("company_name", "Pelanggan"),
            callback_url=f"{settings.public_api_base_url.rstrip('/')}{settings.api_prefix}/billing/callback",
            return_url=f"{settings.public_app_base_url.rstrip('/')}/billing?order={order_id}",
            phone_number=None,
        )
    except duitku.DuitkuError as exc:
        await db.payments.update_one(
            {"_id": doc["_id"]},
            {"$set": {"status": FAILED, "error_message": str(exc)}},
        )
        logger.warning("Duitku inquiry failed for %s: %s", order_id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    await db.payments.update_one(
        {"_id": doc["_id"]},
        {
            "$set": {
                "payment_url": inquiry.payment_url,
                "va_number": inquiry.va_number,
                "duitku_reference": inquiry.reference,
            }
        },
    )
    await db.activity_logs.insert_one(
        {
            "tenant_id": tenant["_id"],
            "user_id": user["_id"],
            "action": "checkout_created",
            "target": order_id,
            "detail": f"{plan.name} - Rp {plan.price_idr:,}".replace(",", "."),
            "created_at": now,
        }
    )

    refreshed = await db.payments.find_one({"_id": doc["_id"]})
    return {
        "payment": _payment_out(refreshed),
        "payment_url": inquiry.payment_url,
    }


async def _apply_paid(payment: Dict[str, Any], source: str) -> bool:
    """Mark an invoice paid and extend the tenant's plan. Idempotent."""
    db = get_db()
    now = datetime.now(timezone.utc)

    # Only the transition pending -> paid does any work. An atomic guarded
    # update means two concurrent callbacks cannot both extend the plan.
    claimed = await db.payments.find_one_and_update(
        {"_id": payment["_id"], "status": {"$ne": PAID}},
        {"$set": {"status": PAID, "paid_at": now, "paid_via": source}},
    )
    if claimed is None:
        logger.info("Payment %s already applied; ignoring", payment.get("merchant_order_id"))
        return False

    plan = get_plan(payment.get("plan_code"))
    tenant = await db.tenants.find_one({"_id": payment["tenant_id"]})
    new_expiry = extend_expiry((tenant or {}).get("plan_expires_at"), plan)

    await db.tenants.update_one(
        {"_id": payment["tenant_id"]},
        {
            "$set": {
                "plan_name": plan.code,
                "plan_expires_at": new_expiry,
                "monthly_job_quota": plan.monthly_job_quota,
                "status": "active",
            }
        },
    )
    await db.activity_logs.insert_one(
        {
            "tenant_id": payment["tenant_id"],
            "user_id": payment.get("user_id"),
            "action": "payment_paid",
            "target": payment.get("merchant_order_id"),
            "detail": f"{plan.name} aktif sampai {new_expiry.date().isoformat()} ({source})",
            "created_at": now,
        }
    )
    logger.info("Payment %s applied via %s", payment.get("merchant_order_id"), source)
    return True


# -------------------------------------------------------------------- callback


@router.post("/callback", response_class=PlainTextResponse)
async def duitku_callback(
    request: Request,
    merchantCode: str = Form(default=""),
    amount: str = Form(default=""),
    merchantOrderId: str = Form(default=""),
    resultCode: str = Form(default=""),
    signature: str = Form(default=""),
    reference: str = Form(default=""),
) -> Any:
    """Payment notification from Duitku. Public, verified by signature."""
    db = get_db()

    if not duitku.verify_callback_signature(merchantCode, amount, merchantOrderId, signature):
        logger.warning("Rejected Duitku callback with bad signature for %s", merchantOrderId)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    payment = await db.payments.find_one({"merchant_order_id": merchantOrderId})
    if not payment:
        logger.warning("Duitku callback for unknown order %s", merchantOrderId)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown order")

    # Duitku's own sample skips this. Without it, a correctly signed callback
    # carrying a smaller amount would still activate the plan.
    try:
        paid_amount = int(float(amount))
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid amount")

    if paid_amount != int(payment.get("amount_idr", -1)):
        logger.error(
            "Amount mismatch on %s: callback %s vs invoice %s",
            merchantOrderId, paid_amount, payment.get("amount_idr"),
        )
        await db.payments.update_one(
            {"_id": payment["_id"]},
            {"$set": {"error_message": f"Nominal callback ({paid_amount}) tidak cocok dengan invoice"}},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount mismatch")

    # Keep the raw notification for the audit trail.
    form = dict(await request.form())
    await db.payments.update_one(
        {"_id": payment["_id"]},
        {"$set": {"callback_received_at": datetime.now(timezone.utc),
                  "callback_payload": {k: str(v) for k, v in form.items()},
                  "duitku_reference": reference or payment.get("duitku_reference")}},
    )

    if resultCode == duitku.CODE_SUCCESS:
        await _apply_paid(payment, source="callback")
    else:
        await db.payments.update_one(
            {"_id": payment["_id"], "status": PENDING},
            {"$set": {"status": FAILED, "error_message": f"resultCode {resultCode}"}},
        )
        logger.info("Payment %s reported unsuccessful (%s)", merchantOrderId, resultCode)

    # Duitku retries until it gets a 200.
    return PlainTextResponse("SUCCESS")


@router.get("/return")
async def duitku_return(merchantOrderId: str = "", resultCode: str = "") -> Any:
    """Where Duitku sends the browser after payment; just bounce to the app."""
    target = (
        f"{settings.public_app_base_url.rstrip('/')}/billing"
        f"?order={merchantOrderId}&result={resultCode}"
    )
    return RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/payments/{payment_id}/sync", response_model=PaymentOut)
async def sync_payment(
    payment_id: str, user: Dict[str, Any] = Depends(get_current_user)
) -> Any:
    """Reconcile one invoice against Duitku.

    A webhook can be lost, so the user is never left stuck on "pending" with no
    way to recover: this asks Duitku directly.
    """
    db = get_db()
    query: Dict[str, Any] = {"_id": to_object_id(payment_id, "payment_id")}
    if not is_admin(user):
        query["tenant_id"] = user.get("tenant_id")

    payment = await db.payments.find_one(query)
    if not payment:
        raise HTTPException(status_code=404, detail="Pembayaran tidak ditemukan")

    if payment.get("status") == PAID:
        return _payment_out(payment)

    try:
        body = await duitku.check_status(payment["merchant_order_id"])
    except duitku.DuitkuError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    code = str(body.get("statusCode", ""))
    if code == duitku.CODE_SUCCESS:
        await _apply_paid(payment, source="sync")
    elif code == duitku.CODE_PENDING:
        pass  # still waiting; leave it alone
    else:
        await db.payments.update_one(
            {"_id": payment["_id"], "status": PENDING},
            {"$set": {"status": EXPIRED,
                      "error_message": body.get("statusMessage") or f"statusCode {code}"}},
        )

    refreshed = await db.payments.find_one({"_id": payment["_id"]})
    return _payment_out(refreshed)
