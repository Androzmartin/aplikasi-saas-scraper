from app.services.redesign import build_concept, detect_industry, render_index_html

LEAD = {
    "business_name": "Warung Kopi Senja",
    "whatsapp_number": "+6281234567890",
    "phone_number": "+62217220091",
    "email": "halo@kopisenja.co.id",
    "address": "Jl. Kemang Raya No. 12, Jakarta Selatan",
    "region": "jakarta_selatan",
}
AUDIT = {"score": 38, "issues": [{"code": "no_cta"}, {"code": "no_viewport"}, {"code": "legacy_markup"}]}


def test_industry_detection():
    assert detect_industry("Warung Kopi Senja") == "kuliner"
    assert detect_industry("Bengkel Motor Jaya") == "otomotif"
    assert detect_industry("PT Sinar Abadi") == "umum"


def test_concept_uses_region_and_audit_findings():
    concept = build_concept(LEAD, AUDIT)
    assert "Jakarta Selatan" in concept["headline"]
    assert concept["sections"]
    assert any("WhatsApp" in item or "mobile" in item for item in concept["improvements"])


class TestSingleFileOutput:
    def setup_method(self):
        self.html = render_index_html(LEAD, build_concept(LEAD, AUDIT), AUDIT)

    def test_is_one_self_contained_document(self):
        assert self.html.startswith("<!DOCTYPE html>")
        assert self.html.rstrip().endswith("</html>")
        assert "cdn.tailwindcss.com" in self.html

    def test_stays_lightweight(self):
        # The brief calls for a single file that is not heavy to open or email.
        assert len(self.html.encode("utf-8")) < 100_000

    def test_contains_contact_actions(self):
        assert "wa.me/6281234567890" in self.html
        assert "tel:+62217220091" in self.html
        assert "mailto:halo@kopisenja.co.id" in self.html

    def test_is_responsive_and_localised(self):
        assert 'name="viewport"' in self.html
        assert 'lang="id"' in self.html

    def test_escapes_injected_markup(self):
        hostile = dict(LEAD, business_name='<script>alert("xss")</script>')
        html = render_index_html(hostile, build_concept(hostile, AUDIT), AUDIT)
        assert "<script>alert" not in html
        assert "&lt;script&gt;" in html


def test_missing_contact_fields_still_render():
    sparse = {"business_name": "Toko Sepi", "region": "unknown"}
    html = render_index_html(sparse, build_concept(sparse, None), None)
    assert "Toko Sepi" in html
    assert "Hubungi Kami" in html
