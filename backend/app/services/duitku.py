"""Duitku payment gateway client.

Protocol verified against Duitku's own published SDK source rather than from
memory:

  - Request transaction: POST {base}/webapi/api/merchant/v2/inquiry
    signature = MD5(merchantCode + merchantOrderId + paymentAmount + merchantKey)
  - Transaction status:  POST {base}/webapi/api/merchant/transactionStatus
    signature = MD5(merchantCode + merchantOrderId + merchantKey)
  - Callback (form POST to callbackUrl)
    signature = MD5(merchantCode + amount + merchantOrderId + merchantKey)
    resultCode "00" = paid

MD5 is Duitku's requirement, not a choice made here; it is used only to match
their signature scheme. Comparisons go through hmac.compare_digest so a wrong
signature cannot be probed byte by byte.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

SANDBOX_BASE = "https://sandbox.duitku.com"
PRODUCTION_BASE = "https://passport.duitku.com"

INQUIRY_PATH = "/webapi/api/merchant/v2/inquiry"
STATUS_PATH = "/webapi/api/merchant/transactionStatus"

# Duitku status/result codes.
CODE_SUCCESS = "00"
CODE_PENDING = "01"


class DuitkuError(Exception):
    """Raised when Duitku rejects a request or is unreachable."""


class DuitkuNotConfigured(DuitkuError):
    """Raised when merchant credentials are missing."""


@dataclass
class InquiryResult:
    reference: str
    payment_url: str
    va_number: Optional[str]
    amount: Optional[str]
    raw: Dict[str, Any]


def base_url() -> str:
    return PRODUCTION_BASE if settings.duitku_production else SANDBOX_BASE


def is_configured() -> bool:
    return bool(settings.duitku_merchant_code and settings.duitku_api_key)


def _require_config() -> None:
    if not is_configured():
        raise DuitkuNotConfigured(
            "Duitku belum dikonfigurasi. Isi DUITKU_MERCHANT_CODE dan DUITKU_API_KEY."
        )


def _md5(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()  # noqa: S324 - gateway protocol


def inquiry_signature(merchant_order_id: str, amount: int) -> str:
    return _md5(
        f"{settings.duitku_merchant_code}{merchant_order_id}{amount}{settings.duitku_api_key}"
    )


def status_signature(merchant_order_id: str) -> str:
    return _md5(
        f"{settings.duitku_merchant_code}{merchant_order_id}{settings.duitku_api_key}"
    )


def callback_signature(merchant_code: str, amount: str, merchant_order_id: str) -> str:
    return _md5(f"{merchant_code}{amount}{merchant_order_id}{settings.duitku_api_key}")


def verify_callback_signature(
    merchant_code: str, amount: str, merchant_order_id: str, signature: str
) -> bool:
    """Constant-time check that the callback really came from Duitku."""
    if not (merchant_code and amount and merchant_order_id and signature):
        return False
    # A callback quoting someone else's merchant code is not ours to act on.
    if merchant_code != settings.duitku_merchant_code:
        return False
    expected = callback_signature(merchant_code, amount, merchant_order_id)
    return hmac.compare_digest(expected.lower(), signature.strip().lower())


async def create_inquiry(
    *,
    merchant_order_id: str,
    amount: int,
    product_details: str,
    email: str,
    customer_name: str,
    callback_url: str,
    return_url: str,
    phone_number: Optional[str] = None,
    expiry_minutes: Optional[int] = None,
) -> InquiryResult:
    """Ask Duitku to open a payment and return the hosted payment URL."""
    _require_config()

    payload: Dict[str, Any] = {
        "merchantCode": settings.duitku_merchant_code,
        "paymentAmount": amount,
        "merchantOrderId": merchant_order_id,
        "productDetails": product_details,
        "email": email,
        "customerVaName": customer_name[:20] or "Pelanggan",
        "callbackUrl": callback_url,
        "returnUrl": return_url,
        "signature": inquiry_signature(merchant_order_id, amount),
        "expiryPeriod": expiry_minutes or settings.duitku_expiry_minutes,
    }
    if phone_number:
        payload["phoneNumber"] = phone_number

    url = f"{base_url()}{INQUIRY_PATH}"
    try:
        async with httpx.AsyncClient(timeout=settings.duitku_timeout_seconds) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        raise DuitkuError(f"Tidak bisa menghubungi Duitku: {exc.__class__.__name__}") from exc

    if response.status_code >= 400:
        # Duitku puts the reason in the body; surface it instead of a bare 500.
        raise DuitkuError(f"Duitku menolak permintaan (HTTP {response.status_code}): {response.text[:300]}")

    try:
        body = response.json()
    except ValueError as exc:
        raise DuitkuError("Balasan Duitku bukan JSON yang valid") from exc

    status_code = str(body.get("statusCode", ""))
    payment_url = body.get("paymentUrl")
    if status_code != CODE_SUCCESS or not payment_url:
        raise DuitkuError(
            f"Duitku gagal membuat transaksi ({status_code or 'tanpa kode'}): "
            f"{body.get('statusMessage') or 'tidak ada pesan'}"
        )

    return InquiryResult(
        reference=str(body.get("reference") or ""),
        payment_url=payment_url,
        va_number=body.get("vaNumber"),
        amount=str(body.get("amount")) if body.get("amount") is not None else None,
        raw=body,
    )


async def check_status(merchant_order_id: str) -> Dict[str, Any]:
    """Poll Duitku for a transaction's status.

    Used to reconcile when a callback never arrived - a webhook can be lost, so
    payment state must not depend on it alone.
    """
    _require_config()

    payload = {
        "merchantCode": settings.duitku_merchant_code,
        "merchantOrderId": merchant_order_id,
        "signature": status_signature(merchant_order_id),
    }
    url = f"{base_url()}{STATUS_PATH}"
    try:
        async with httpx.AsyncClient(timeout=settings.duitku_timeout_seconds) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        raise DuitkuError(f"Tidak bisa menghubungi Duitku: {exc.__class__.__name__}") from exc

    if response.status_code >= 400:
        raise DuitkuError(f"Duitku menolak permintaan (HTTP {response.status_code})")

    try:
        return response.json()
    except ValueError as exc:
        raise DuitkuError("Balasan Duitku bukan JSON yang valid") from exc
