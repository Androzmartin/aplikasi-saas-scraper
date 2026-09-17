"""Subscription plans.

Plans live in code rather than the database: they change rarely, deserve review
like any other code, and a pricing row that can be edited at runtime is an easy
way to give the product away by accident.

Prices are whole rupiah - Duitku expects an integer amount.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Plan:
    code: str
    name: str
    price_idr: int
    monthly_job_quota: int
    duration_days: int
    features: List[str]
    is_free: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "price_idr": self.price_idr,
            "monthly_job_quota": self.monthly_job_quota,
            "duration_days": self.duration_days,
            "features": list(self.features),
            "is_free": self.is_free,
        }


FREE_PLAN_CODE = "free"

PLANS: Dict[str, Plan] = {
    "free": Plan(
        code="free",
        name="Gratis",
        price_idr=0,
        monthly_job_quota=50,
        duration_days=0,  # never expires
        is_free=True,
        features=[
            "50 job scraping per bulan",
            "Audit website dan skor",
            "Generate redesign + index.html",
            "Export CSV",
        ],
    ),
    "starter": Plan(
        code="starter",
        name="Starter",
        price_idr=149_000,
        monthly_job_quota=500,
        duration_days=30,
        features=[
            "500 job scraping per bulan",
            "Semua fitur paket Gratis",
            "Template redesign per niche",
            "Draft outreach WhatsApp & email",
            "Proposal klien (HTML & PDF)",
        ],
    ),
    "pro": Plan(
        code="pro",
        name="Pro",
        price_idr=399_000,
        monthly_job_quota=2_000,
        duration_days=30,
        features=[
            "2.000 job scraping per bulan",
            "Semua fitur paket Starter",
            "Screenshot desktop & mobile",
            "Analitik pipeline lengkap",
            "Prioritas antrean scraping",
        ],
    ),
    "business": Plan(
        code="business",
        name="Business",
        price_idr=1_290_000,
        monthly_job_quota=10_000,
        duration_days=30,
        features=[
            "10.000 job scraping per bulan",
            "Semua fitur paket Pro",
            "Multi-user dalam satu tenant",
            "Dukungan prioritas",
        ],
    ),
}


def get_plan(code: Optional[str]) -> Plan:
    """Return a plan by code, falling back to free for anything unknown."""
    if code and code in PLANS:
        return PLANS[code]
    return PLANS[FREE_PLAN_CODE]


def list_plans() -> List[Dict[str, Any]]:
    return [plan.to_dict() for plan in PLANS.values()]


def purchasable(code: str) -> bool:
    plan = PLANS.get(code)
    return bool(plan and not plan.is_free and plan.price_idr > 0)


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def effective_plan(tenant: Optional[Dict[str, Any]]) -> Plan:
    """The plan a tenant is actually entitled to right now.

    A paid plan whose period has ended falls back to free, so an expired
    subscription cannot keep spending a paid quota.
    """
    if not tenant:
        return PLANS[FREE_PLAN_CODE]

    plan = get_plan(tenant.get("plan_name"))
    if plan.is_free:
        return plan

    expires_at = _as_utc(tenant.get("plan_expires_at"))
    if expires_at is None:
        return plan
    if expires_at <= datetime.now(timezone.utc):
        return PLANS[FREE_PLAN_CODE]
    return plan


def extend_expiry(current: Optional[datetime], plan: Plan) -> datetime:
    """Stack a renewal on top of remaining time instead of discarding it."""
    now = datetime.now(timezone.utc)
    current = _as_utc(current)
    base = current if current and current > now else now
    return base + timedelta(days=plan.duration_days)
