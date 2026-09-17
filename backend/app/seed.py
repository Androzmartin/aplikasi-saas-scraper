"""Seed a demo tenant, user and project - optionally with example data.

    python -m app.seed            # akun + project kosong
    python -m app.seed --demo     # + lead, audit, job, redesign, pembayaran

Lewat Docker:

    docker compose exec backend python -m app.seed --demo

The --demo data is clearly fictional and exists so a fresh install shows a
populated dashboard immediately, instead of an empty one that only fills up
after a scraping run.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from app.db import close, connect, ensure_indexes
from app.models.common import Role, TenantStatus
from app.security import hash_password
from app.services.audit import run_audit
from app.services.plans import get_plan
from app.services.redesign import build_concept, render_index_html

# Fictional businesses across the regions the product targets, with a spread of
# audit scores so the analytics and filters have something to show.
DEMO_LEADS = [
    {
        "business_name": "Warung Kopi Senja",
        "website_url": "https://contoh-warungkopisenja.co.id/",
        "whatsapp_number": "+6281234567890",
        "phone_number": "+62217220091",
        "email": "halo@contoh-kopisenja.co.id",
        "address": "Jl. Kemang Raya No. 12, Jakarta Selatan 12730",
        "contact_person": "Budi Santoso",
        "region": "jakarta_selatan",
        "status": "new",
        "tags": ["prioritas"],
        "legacy": True,
    },
    {
        "business_name": "Butik Hijab Amara",
        "website_url": "https://contoh-butikhijabamara.com/",
        "whatsapp_number": "+6281298765432",
        "phone_number": None,
        "email": "cs@contoh-hijabamara.com",
        "address": "Ruko Sentul City Blok B2, Bogor",
        "contact_person": "Siti Rahayu",
        "region": "bogor",
        "status": "contacted",
        "tags": [],
        "legacy": False,
        "notes": "Sudah dihubungi via WhatsApp, minta dikirim proposal.",
    },
    {
        "business_name": "Bengkel Motor Jaya",
        "website_url": "https://contoh-bengkelmotorjaya.id/",
        "whatsapp_number": "+6281377788899",
        "phone_number": "+62215550123",
        "email": None,
        "address": "Jl. Margonda Raya No. 88, Depok",
        "contact_person": None,
        "region": "depok",
        "status": "new",
        "tags": [],
        "legacy": True,
    },
    {
        "business_name": "Katering Dapur Ibu",
        "website_url": "https://contoh-dapuribucatering.co.id/",
        "whatsapp_number": "+6281244455566",
        "phone_number": None,
        "email": "order@contoh-dapuribu.co.id",
        "address": "Harapan Indah Blok C, Bekasi",
        "contact_person": "Dewi Lestari",
        "region": "bekasi",
        "status": "qualified",
        "tags": ["prioritas"],
        "legacy": False,
    },
    {
        "business_name": "Klinik Gigi Senyum",
        "website_url": "https://contoh-kliniksenyum.co.id/",
        "whatsapp_number": None,
        "phone_number": "+62215557788",
        "email": "info@contoh-kliniksenyum.co.id",
        "address": "Alam Sutera, Tangerang",
        "contact_person": None,
        "region": "tangerang",
        "status": "new",
        "tags": [],
        "legacy": False,
    },
    {
        "business_name": "Toko Bangunan Makmur",
        "website_url": "https://contoh-tbmakmur.com/",
        "whatsapp_number": "+6281255566677",
        "phone_number": None,
        "email": None,
        "address": "Jl. Daan Mogot, Jakarta Barat",
        "contact_person": "Pak Hadi",
        "region": "jakarta_barat",
        "status": "new",
        "tags": [],
        "legacy": True,
    },
]

# Two shapes of target site, so the audit engine produces a realistic spread
# rather than one score repeated.
_LEGACY_HTML = (
    '<html><body><table width="980px"><font color="red">'
    "<marquee>Selamat Datang</marquee></font><p>Hubungi kami</p></table></body></html>"
)


def _modern_html(name: str) -> str:
    return (
        '<html><head><meta name="viewport" content="width=device-width, initial-scale=1">'
        "<style>@media (min-width: 640px){.a{display:flex}}</style></head><body>"
        '<header><nav><a href="#a">Tentang</a><a href="#b">Layanan</a>'
        '<a href="#c">Kontak</a></nav></header><main><h1>' + name + "</h1>"
        "<section><p>" + ("Kami melayani kebutuhan pelanggan dengan produk berkualitas. " * 20)
        + '</p><img src="produk.jpg" alt="produk">'
        '<a class="btn" href="https://wa.me/628123456789">Hubungi Kami</a></section>'
        "<section>Testimoni pelanggan kami</section></main>"
        "<footer>Kontak: Jakarta</footer></body></html>"
    )


async def seed(db: Any, demo: bool = False, email: str = "", password: str = "",
               company: str = "", name: str = "") -> Dict[str, Any]:
    """Create the demo account, and example data when demo is True.

    Returns a summary dict. Safe to call twice: an existing account is reported
    rather than duplicated.
    """
    now = datetime.now(timezone.utc)
    email = (email or "demo@agency.co.id").lower()

    if await db.users.find_one({"email": email}):
        return {"created": False, "email": email, "reason": "sudah ada"}

    plan = get_plan("starter")
    tenant = await db.tenants.insert_one(
        {
            "company_name": company or "Agency Kreatif Nusantara",
            "plan_name": plan.code,
            "status": TenantStatus.ACTIVE.value,
            "monthly_job_quota": plan.monthly_job_quota,
            # A real expiry so the billing screens show something meaningful.
            "plan_expires_at": now + timedelta(days=30),
            "created_at": now,
        }
    )
    tenant_id = tenant.inserted_id

    user = await db.users.insert_one(
        {
            "tenant_id": tenant_id,
            "name": name or "Demo User",
            "email": email,
            "password_hash": hash_password(password),
            "role": Role.USER_TENANT.value,
            "created_at": now,
        }
    )
    user_id = user.inserted_id

    project = await db.projects.insert_one(
        {
            "tenant_id": tenant_id,
            "name": "Kuliner & Retail Jabodetabek",
            "target_region": "jakarta",
            "description": "Project contoh untuk mencoba alur scraping.",
            "created_by": user_id,
            "created_at": now,
        }
    )
    project_id = project.inserted_id

    summary = {"created": True, "email": email, "leads": 0, "jobs": 0, "redesigns": 0}
    if not demo:
        return summary

    for index, row in enumerate(DEMO_LEADS):
        html = _LEGACY_HTML if row["legacy"] else _modern_html(row["business_name"])
        contact = {key: row.get(key) for key in
                   ("business_name", "whatsapp_number", "phone_number", "email", "address")}
        audit = run_audit(html, contact)

        lead = await db.leads.insert_one(
            {
                "project_id": project_id,
                "tenant_id": tenant_id,
                "website_url": row["website_url"],
                "business_name": row["business_name"],
                "whatsapp_number": row["whatsapp_number"],
                "phone_number": row["phone_number"],
                "email": row["email"],
                "address": row["address"],
                "contact_person": row["contact_person"],
                "region": row["region"],
                "source_page": row["website_url"],
                "field_confidence": {
                    "business_name": 0.95, "whatsapp_number": 0.9,
                    "email": 0.9, "address": 0.75, "contact_person": 0.75,
                },
                "audit_score": audit["score"],
                "status": row["status"],
                "notes": row.get("notes"),
                "tags": row["tags"],
                "outreach_sent_at": now if row["status"] != "new" else None,
                "outreach_channel": "whatsapp" if row["status"] != "new" else None,
                "page_text": "",
                "created_at": now - timedelta(hours=index * 5),
                "updated_at": now,
            }
        )
        lead_id = lead.inserted_id
        summary["leads"] += 1

        await db.website_audits.insert_one(
            {"lead_id": lead_id, "tenant_id": tenant_id, **audit,
             "created_at": now - timedelta(hours=index * 5)}
        )

        # A spread of job states so the monitor and retry button are exercisable.
        status = "completed" if index < 4 else ("running" if index == 4 else "failed")
        await db.scrape_jobs.insert_one(
            {
                "project_id": project_id,
                "tenant_id": tenant_id,
                "created_by": user_id,
                "source_url": row["website_url"],
                "status": status,
                "attempts": 1 if status != "failed" else 3,
                "pages_crawled": 3 if status == "completed" else 0,
                "error_message": None if status != "failed"
                else "HTTP 403 saat mengakses situs (diblokir crawler)",
                "lead_id": lead_id if status == "completed" else None,
                "created_at": now - timedelta(hours=index),
                "started_at": now - timedelta(hours=index),
                "completed_at": now if status in ("completed", "failed") else None,
            }
        )
        summary["jobs"] += 1

        # One ready-made redesign so the preview and download work immediately.
        if index == 0:
            lead_doc = await db.leads.find_one({"_id": lead_id})
            concept = build_concept(lead_doc, audit)
            html_out = render_index_html(lead_doc, concept, audit)
            await db.redesign_outputs.insert_one(
                {
                    "lead_id": lead_id,
                    "tenant_id": tenant_id,
                    "version": 1,
                    "headline": concept["headline"],
                    "subheadline": concept["subheadline"],
                    "sections": concept["sections"],
                    "improvements": concept.get("improvements", []),
                    "template_key": concept.get("template_key", "umum"),
                    "template_label": concept.get("template_label", ""),
                    "preview_html": html_out,
                    # No storage_key: download falls back to preview_html, so
                    # this works without seeding the object store.
                    "generated_with": "template",
                    "approval_status": "approved",
                    "approval_note": None,
                    "reviewed_by": None,
                    "reviewed_at": None,
                    "created_at": now,
                }
            )
            summary["redesigns"] += 1

    await db.payments.insert_one(
        {
            "merchant_order_id": "UMKM-DEMO-000001",
            "tenant_id": tenant_id,
            "user_id": user_id,
            "plan_code": "starter",
            "plan_name": get_plan("starter").name,
            "amount_idr": get_plan("starter").price_idr,
            "status": "paid",
            "payment_url": None,
            "va_number": "8009900112233",
            "duitku_reference": "DEMO-REF-000001",
            "created_at": now - timedelta(days=1),
            "paid_at": now - timedelta(days=1),
            "paid_via": "seed",
            "expires_at": now - timedelta(days=1) + timedelta(hours=1),
        }
    )
    await db.activity_logs.insert_one(
        {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "action": "scrape_enqueued",
            "target": "Kuliner & Retail Jabodetabek",
            "detail": f"{len(DEMO_LEADS)} URL masuk antrean",
            "created_at": now,
        }
    )
    return summary


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo data.")
    parser.add_argument(
        "--demo", action="store_true",
        help="Ikut membuat lead, audit, job, redesign, dan pembayaran contoh.",
    )
    args = parser.parse_args()

    db = connect()
    await ensure_indexes()

    password = os.getenv("SEED_PASSWORD") or secrets.token_urlsafe(12)
    try:
        result = await seed(
            db,
            demo=args.demo,
            email=os.getenv("SEED_EMAIL", ""),
            password=password,
            company=os.getenv("SEED_COMPANY", ""),
            name=os.getenv("SEED_NAME", ""),
        )
    finally:
        await close()

    if not result["created"]:
        print(f"User {result['email']} {result['reason']}; tidak ada yang dibuat.")
        return

    print("Seed selesai.")
    print(f"  email    : {result['email']}")
    print(f"  password : {password}")
    if args.demo:
        print(f"  data     : {result['leads']} lead, {result['jobs']} job, "
              f"{result['redesigns']} redesign, 1 pembayaran")
    else:
        print("  data     : akun + 1 project kosong (pakai --demo untuk data contoh)")


if __name__ == "__main__":
    asyncio.run(main())
