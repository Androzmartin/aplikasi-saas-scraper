"""Per-niche redesign templates (P2)."""
import html as html_lib
import re
from datetime import datetime, timezone

import pytest
from bson import ObjectId

from app.services.redesign import build_concept, detect_industry, render_index_html
from app.services.templates import DEFAULT_TEMPLATE, TEMPLATES, get_template, list_templates

pytestmark = pytest.mark.asyncio

LEAD = {
    "business_name": "Warung Kopi Senja",
    "whatsapp_number": "+6281234567890",
    "phone_number": "+62217220091",
    "email": "halo@kopisenja.co.id",
    "address": "Jl. Kemang Raya No. 12, Jakarta Selatan",
    "region": "jakarta_selatan",
}
AUDIT = {"score": 38, "issues": [{"code": "no_cta"}, {"code": "no_viewport"}]}


class TestTemplateCatalogue:
    async def test_every_niche_is_complete(self):
        for key, template in TEMPLATES.items():
            assert template.key == key
            assert template.accent
            assert template.cta_label
            assert len(template.services) == 3, key
            assert len(template.highlight_items) == 3, key
            assert len(template.trust_points) >= 3, key
            assert template.testimonials, key
            assert template.sections, key

    async def test_accents_are_distinct_enough_to_look_different(self):
        accents = [t.accent for t in TEMPLATES.values()]
        # A shared accent would make two niches indistinguishable on screen.
        assert len(set(accents)) == len(accents)

    async def test_unknown_key_falls_back(self):
        assert get_template("tidak-ada").key == DEFAULT_TEMPLATE
        assert get_template(None).key == DEFAULT_TEMPLATE

    async def test_listing_exposes_what_the_ui_needs(self):
        listed = list_templates()
        assert len(listed) == len(TEMPLATES)
        assert all({"key", "label", "accent", "headline", "highlight"} <= set(x) for x in listed)


class TestConceptSelection:
    async def test_auto_detection_picks_the_niche(self):
        assert build_concept(LEAD, AUDIT)["template_key"] == "kuliner"
        assert detect_industry("Bengkel Motor Jaya") == "otomotif"

    async def test_explicit_override_wins(self):
        concept = build_concept(LEAD, AUDIT, "kesehatan")
        assert concept["template_key"] == "kesehatan"
        assert concept["template_label"] == TEMPLATES["kesehatan"].label

    async def test_invalid_override_falls_back_to_detection(self):
        # A bad key must not crash or silently produce a blank page.
        concept = build_concept(LEAD, AUDIT, "tidak-ada")
        assert concept["template_key"] == "kuliner"

    async def test_sections_differ_per_niche(self):
        kuliner = build_concept(LEAD, AUDIT, "kuliner")["sections"]
        jasa = build_concept(LEAD, AUDIT, "jasa")["sections"]
        assert kuliner != jasa


class TestRenderedOutput:
    @pytest.mark.parametrize("key", sorted(TEMPLATES))
    async def test_each_niche_renders_valid_light_html(self, key):
        concept = build_concept(LEAD, AUDIT, key)
        html = render_index_html(LEAD, concept, AUDIT)
        template = TEMPLATES[key]

        assert html.startswith("<!DOCTYPE html>")
        assert html.rstrip().endswith("</html>")
        assert "cdn.tailwindcss.com" in html
        assert len(html.encode("utf-8")) < 100_000

        # The niche must actually show through in the output. Template copy is
        # HTML-escaped on the way in, so compare against the escaped form
        # (e.g. "Survei & Estimasi" renders as "Survei &amp; Estimasi").
        def rendered(text: str) -> str:
            return html_lib.escape(text, quote=True)

        assert f"bg-{template.accent}-600" in html
        assert rendered(template.cta_label) in html
        assert rendered(template.highlight_title) in html
        assert rendered(template.services[0][0]) in html
        assert rendered(template.trust_points[0]) in html

    async def test_accent_is_consistent_within_one_page(self):
        html = render_index_html(LEAD, build_concept(LEAD, AUDIT, "otomotif"), AUDIT)
        accents = set(re.findall(r"bg-(\w+)-600", html))
        assert accents == {"orange"}

    async def test_two_niches_produce_different_pages(self):
        a = render_index_html(LEAD, build_concept(LEAD, AUDIT, "kuliner"), AUDIT)
        b = render_index_html(LEAD, build_concept(LEAD, AUDIT, "properti"), AUDIT)
        assert a != b

    async def test_template_content_is_still_escaped(self):
        hostile = dict(LEAD, business_name='<img src=x onerror="alert(1)">')
        html = render_index_html(hostile, build_concept(hostile, AUDIT, "jasa"), AUDIT)
        assert 'onerror="alert(1)"' not in html
        assert "&lt;img" in html


class TestTemplateApi:
    @pytest.fixture
    async def lead_id(self, auth_client, mock_db):
        project = (
            await auth_client.post(
                "/api/projects", json={"name": "Proyek Niche", "target_region": "jakarta_selatan"}
            )
        ).json()
        me = (await auth_client.get("/api/auth/me")).json()
        lead = await mock_db.leads.insert_one(
            {
                "project_id": ObjectId(project["id"]),
                "tenant_id": ObjectId(me["tenant"]["id"]),
                "website_url": "https://warungkopisenja.co.id/",
                "business_name": "Warung Kopi Senja",
                "whatsapp_number": "+6281234567890",
                "region": "jakarta_selatan",
                "status": "new",
                "tags": [],
                "created_at": datetime.now(timezone.utc),
            }
        )
        return str(lead.inserted_id)

    async def test_templates_endpoint_is_not_shadowed_by_lead_id(self, auth_client, lead_id):
        """/redesign/templates must not be parsed as /redesign/{lead_id}."""
        response = await auth_client.get("/api/redesign/templates")
        assert response.status_code == 200
        keys = {item["key"] for item in response.json()}
        assert "kuliner" in keys and "umum" in keys

    async def test_generate_uses_detected_niche(self, auth_client, lead_id):
        body = (await auth_client.post(f"/api/redesign/{lead_id}/generate")).json()
        assert body["template_key"] == "kuliner"
        assert body["template_label"]

    async def test_generate_accepts_template_override(self, auth_client, lead_id):
        body = (
            await auth_client.post(f"/api/redesign/{lead_id}/generate?template=properti")
        ).json()
        assert body["template_key"] == "properti"

        download = await auth_client.get(f"/api/redesign/{lead_id}/download")
        assert html_lib.escape(TEMPLATES["properti"].highlight_title) in download.text

    async def test_regenerating_with_another_niche_bumps_version(self, auth_client, lead_id):
        first = (await auth_client.post(f"/api/redesign/{lead_id}/generate?template=kuliner")).json()
        second = (await auth_client.post(f"/api/redesign/{lead_id}/generate?template=jasa")).json()
        assert second["version"] == first["version"] + 1
        assert second["template_key"] == "jasa"
