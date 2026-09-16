"""Client-facing proposal document (P2)."""
import html as html_lib
from datetime import datetime, timezone

import pytest
from bson import ObjectId

from app.config import settings
from app.services.proposal import build_proposal_html, build_scope

pytestmark = pytest.mark.asyncio

LEAD = {
    "business_name": "Warung Kopi Senja",
    "website_url": "https://kopisenja.co.id/",
    "whatsapp_number": "+6281234567890",
    "email": "halo@kopisenja.co.id",
    "address": "Jl. Kemang Raya No. 12, Jakarta Selatan",
    "region": "jakarta_selatan",
    "audit_score": 34,
}
AUDIT = {
    "score": 34,
    "grade": "E",
    "issues": [
        {"code": "no_viewport", "severity": "high", "title": "Tidak ada meta viewport",
         "detail": "Halaman tampil mengecil di HP."},
        {"code": "no_cta", "severity": "high", "title": "Tidak ada call to action",
         "detail": "Tidak ada ajakan menghubungi."},
        {"code": "legacy_markup", "severity": "high", "title": "Markup bergaya lama",
         "detail": "Ditemukan elemen usang."},
    ],
}
REDESIGN = {
    "headline": "Rasa yang dikenal di Jakarta Selatan",
    "subheadline": "Pesan lewat WhatsApp.",
    "template_key": "kuliner",
}
TENANT = {"company_name": "Agency Kreatif Nusantara"}
AUTHOR = {"name": "Andi Pratama", "email": "andi@agency.co.id"}


class TestScope:
    async def test_scope_is_derived_from_the_audit(self):
        scope = build_scope(AUDIT)
        assert any("ponsel" in item for item in scope)
        assert any("call to action" in item for item in scope)

    async def test_baseline_items_always_present(self):
        assert any("mobile-first" in item for item in build_scope(None))

    async def test_scope_is_capped_and_unique(self):
        big = {"issues": [{"code": code} for code in
                          ["no_viewport", "no_cta", "no_whatsapp", "no_address", "thin_sections",
                           "legacy_markup", "no_images", "thin_content", "no_h1", "no_navigation"]]}
        scope = build_scope(big)
        assert len(scope) <= 8
        assert len(scope) == len(set(scope))


class TestProposalDocument:
    def _html(self, **kwargs):
        return build_proposal_html(
            kwargs.get("lead", LEAD), kwargs.get("audit", AUDIT),
            kwargs.get("redesign", REDESIGN), TENANT, AUTHOR,
            kwargs.get("shot"),
        )

    async def test_is_a_complete_document(self):
        html = self._html()
        assert html.startswith("<!DOCTYPE html>")
        assert html.rstrip().endswith("</html>")
        assert 'lang="id"' in html

    async def test_is_self_contained_with_no_network_dependency(self):
        """A proposal gets opened offline and printed; a CDN would render blank."""
        html = self._html()
        style = html.split("<style>")[1].split("</style>")[0]
        assert "http" not in style
        assert "cdn." not in html
        assert "<link" not in html

    async def test_carries_the_key_commercial_facts(self):
        html = self._html()
        assert "Warung Kopi Senja" in html
        assert "Agency Kreatif Nusantara" in html
        assert "Andi Pratama" in html
        assert "34" in html and "Grade E" in html
        assert "Jakarta Selatan" in html

    async def test_includes_findings_scope_and_next_steps(self):
        html = self._html()
        assert "Tidak ada meta viewport" in html
        assert "LINGKUP PEKERJAAN" in html.upper()
        assert "Langkah Berikutnya" in html
        assert "Investasi" in html

    async def test_shows_the_redesign_concept(self):
        assert html_lib.escape(REDESIGN["headline"]) in self._html()

    async def test_has_print_rules_for_pdf(self):
        html = self._html()
        assert "@page" in html
        assert "@media print" in html
        assert "page-break-inside: avoid" in html

    async def test_embeds_a_screenshot_when_available(self):
        uri = "data:image/png;base64,AAAA"
        html = self._html(shot=uri)
        assert uri in html
        assert "Tampilan saat ini" in html

    async def test_placeholder_when_no_screenshot(self):
        assert "Screenshot belum diambil" in self._html()

    async def test_uses_the_stored_score_when_there_is_no_audit_doc(self):
        html = self._html(audit=None, redesign=None)
        assert "34" in html  # score carried on the lead itself
        assert "Konsep redesign belum dibuat" in html
        assert html.rstrip().endswith("</html>")

    async def test_degrades_cleanly_when_nothing_has_been_scored(self):
        bare = {k: v for k, v in LEAD.items() if k != "audit_score"}
        html = self._html(lead=bare, audit=None, redesign=None)
        assert "Audit belum dijalankan" in html
        assert "Konsep redesign belum dibuat" in html
        assert html.rstrip().endswith("</html>")

    async def test_escapes_scraped_content(self):
        hostile = dict(LEAD, business_name='<script>alert(1)</script>')
        html = self._html(lead=hostile)
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html


class TestProposalApi:
    @pytest.fixture
    async def lead_id(self, auth_client, mock_db):
        project = (
            await auth_client.post(
                "/api/projects", json={"name": "Proyek Proposal", "target_region": "jakarta_selatan"}
            )
        ).json()
        me = (await auth_client.get("/api/auth/me")).json()
        tenant_id = ObjectId(me["tenant"]["id"])
        lead = await mock_db.leads.insert_one(
            {"project_id": ObjectId(project["id"]), "tenant_id": tenant_id,
             **LEAD, "status": "new", "tags": [], "created_at": datetime.now(timezone.utc)}
        )
        await mock_db.website_audits.insert_one(
            {"lead_id": lead.inserted_id, "tenant_id": tenant_id, **AUDIT,
             "created_at": datetime.now(timezone.utc)}
        )
        return str(lead.inserted_id)

    async def test_preview_returns_html(self, auth_client, lead_id):
        response = await auth_client.get(f"/api/proposals/{lead_id}")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Warung Kopi Senja" in response.text

    async def test_html_download_is_attached(self, auth_client, lead_id):
        response = await auth_client.get(f"/api/proposals/{lead_id}/download?format=html")
        assert response.status_code == 200
        assert "attachment" in response.headers["content-disposition"]
        assert ".html" in response.headers["content-disposition"]

    async def test_pdf_needs_the_optional_browser(self, auth_client, lead_id, monkeypatch):
        monkeypatch.setattr(settings, "screenshot_enabled", False)
        response = await auth_client.get(f"/api/proposals/{lead_id}/download?format=pdf")
        assert response.status_code == 503
        # The message must point at the workaround, not just fail.
        assert "HTML" in response.json()["detail"]

    async def test_invalid_format_rejected(self, auth_client, lead_id):
        assert (
            await auth_client.get(f"/api/proposals/{lead_id}/download?format=docx")
        ).status_code == 422

    async def test_download_is_logged(self, auth_client, lead_id, mock_db):
        await auth_client.get(f"/api/proposals/{lead_id}/download?format=html")
        log = await mock_db.activity_logs.find_one({"action": "proposal_downloaded"})
        assert log is not None and log["detail"] == "html"

    async def test_other_tenants_cannot_read_the_proposal(self, client, lead_id):
        other = await client.post(
            "/api/auth/register",
            json={"company_name": "Agency Lain", "name": "Cici",
                  "email": "cici2@lain.co.id", "password": "password-lain-123"},
        )
        token = other.json()["access_token"]
        response = await client.get(
            f"/api/proposals/{lead_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 404
