"""Optional AI enrichment: validation, fabrication guard, and fallbacks.

No network calls here — the provider is stubbed. What is tested is the part
that protects the customer: AI output is only used when it is well-formed and
makes no claim we cannot back up, and any failure falls back to templates.
"""
import pytest

from app.config import settings
from app.services import ai
from app.services.redesign import build_concept, render_index_html
from app.services.templates import TEMPLATES

pytestmark = pytest.mark.asyncio

LEAD = {
    "business_name": "Warung Kopi Senja",
    "whatsapp_number": "+6281234567890",
    "region": "jakarta_selatan",
    "address": "Jl. Kemang Raya, Jakarta Selatan",
}
AUDIT = {"score": 34, "issues": [{"code": "no_cta", "title": "Tidak ada CTA"}]}

GOOD_PAYLOAD = {
    "headline": "Kopi diseduh segar setiap pagi",
    "subheadline": "Pesan lewat WhatsApp, kami antar ke meja Anda.",
    "services": [
        {"title": "Seduh Manual", "body": "Biji dipilih dan diseduh saat dipesan."},
        {"title": "Pesan Antar", "body": "Diantar dalam kondisi terbaik."},
        {"title": "Pesanan Kantor", "body": "Melayani rapat dan acara kecil."},
    ],
    "trust_points": [
        "Biji kopi digiling saat dipesan",
        "Tempat bersih dan nyaman",
        "Harga tertera jelas di menu",
    ],
    "highlight_items": [
        {"title": "Kopi Susu", "body": "Paling sering dipesan pelanggan."},
        {"title": "Americano", "body": "Untuk yang suka rasa pekat."},
        {"title": "Paket Hemat", "body": "Kombinasi kopi dan camilan."},
    ],
}


@pytest.fixture
def ai_on(monkeypatch):
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    monkeypatch.setattr(settings, "ai_model", "claude-opus-5")
    yield


class TestFabricationGuard:
    @pytest.mark.parametrize(
        "text",
        [
            "Dipercaya 1000+ pelanggan",
            "Melayani sejak 1998",
            "15 tahun pengalaman",
            "98% pelanggan puas",
            "Bengkel nomor 1 di Jakarta",
            "Kopi terbaik se-Jakarta",
            "Teknisi bersertifikat resmi",
            "Pemenang penghargaan kuliner",
        ],
    )
    async def test_claims_are_flagged(self, text):
        assert ai.looks_fabricated(text), text

    @pytest.mark.parametrize(
        "text",
        [
            "Kopi diseduh segar setiap pagi",
            "Pesan lewat WhatsApp, kami antar hari ini",
            "Tempat bersih dan nyaman untuk keluarga",
            "Harga tertera jelas di menu",
        ],
    )
    async def test_honest_copy_passes(self, text):
        assert not ai.looks_fabricated(text), text


class TestValidation:
    async def test_good_payload_accepted(self):
        result = ai.validate_copy(GOOD_PAYLOAD)
        assert result is not None
        assert result.headline == GOOD_PAYLOAD["headline"]
        assert len(result.services) == 3
        assert len(result.trust_points) == 3
        assert len(result.highlight_items) == 3

    async def test_fabricated_headline_rejects_the_whole_set(self):
        bad = dict(GOOD_PAYLOAD, headline="Dipercaya 5000+ pelanggan sejak 2009")
        assert ai.validate_copy(bad) is None

    async def test_fabrication_anywhere_rejects(self):
        bad = dict(GOOD_PAYLOAD)
        bad["trust_points"] = list(GOOD_PAYLOAD["trust_points"])
        bad["trust_points"][1] = "Sudah 20 tahun melayani"
        assert ai.validate_copy(bad) is None

    async def test_overlong_text_rejected(self):
        bad = dict(GOOD_PAYLOAD, headline="A" * 200)
        assert ai.validate_copy(bad) is None

    async def test_missing_or_short_lists_rejected(self):
        assert ai.validate_copy(dict(GOOD_PAYLOAD, services=[])) is None
        assert ai.validate_copy(dict(GOOD_PAYLOAD, trust_points=["cuma satu"])) is None
        assert ai.validate_copy({}) is None

    async def test_wrong_shapes_rejected(self):
        assert ai.validate_copy(dict(GOOD_PAYLOAD, services=["bukan objek"] * 3)) is None
        assert ai.validate_copy(dict(GOOD_PAYLOAD, headline=123)) is None

    async def test_whitespace_is_normalised(self):
        payload = dict(GOOD_PAYLOAD, headline="  Kopi   segar\n  setiap pagi  ")
        result = ai.validate_copy(payload)
        assert result.headline == "Kopi segar setiap pagi"


class TestDisabledByDefault:
    async def test_disabled_without_flag(self, monkeypatch):
        monkeypatch.setattr(settings, "ai_enabled", False)
        assert not ai.is_enabled()
        assert await ai.generate_copy(LEAD, AUDIT, "kuliner") is None
        assert await ai.classify_niche("Warung Kopi", "teks") is None

    async def test_enabled_flag_without_key_is_still_off(self, monkeypatch):
        """A half-configured deployment must not try to call the API."""
        monkeypatch.setattr(settings, "ai_enabled", True)
        monkeypatch.setattr(settings, "ai_api_key", "")
        assert not ai.is_enabled()

    async def test_concept_unchanged_when_disabled(self, monkeypatch):
        monkeypatch.setattr(settings, "ai_enabled", False)
        concept = build_concept(LEAD, AUDIT)
        assert await ai.enrich_concept(concept, LEAD, AUDIT) == concept


class TestFailureFallsBackToTemplates:
    async def test_missing_sdk_returns_none(self, ai_on, monkeypatch):
        monkeypatch.setattr(ai, "_client", lambda: None)
        assert await ai.generate_copy(LEAD, AUDIT, "kuliner") is None

    async def test_provider_failure_returns_none(self, ai_on, monkeypatch):
        """_ask swallows provider errors and reports None; callers rely on that."""
        async def failed(prompt, schema):
            return None

        monkeypatch.setattr(ai, "_ask", failed)
        assert await ai.generate_copy(LEAD, AUDIT, "kuliner") is None

    async def test_rejected_copy_leaves_concept_alone(self, ai_on, monkeypatch):
        async def fabricating(prompt, schema):
            return dict(GOOD_PAYLOAD, headline="Sudah 30 tahun melayani Jakarta")

        monkeypatch.setattr(ai, "_ask", fabricating)
        concept = build_concept(LEAD, AUDIT)
        enriched = await ai.enrich_concept(concept, LEAD, AUDIT, "teks")
        assert enriched == concept
        assert "ai_services" not in enriched


class TestSuccessfulEnrichment:
    async def test_concept_carries_ai_copy(self, ai_on, monkeypatch):
        async def good(prompt, schema):
            return GOOD_PAYLOAD

        monkeypatch.setattr(ai, "_ask", good)
        concept = build_concept(LEAD, AUDIT)
        enriched = await ai.enrich_concept(concept, LEAD, AUDIT, "teks halaman")

        assert enriched["headline"] == GOOD_PAYLOAD["headline"]
        assert enriched["generated_with"] == "ai:claude-opus-5"
        assert len(enriched["ai_services"]) == 3

    async def test_rendered_page_uses_ai_copy(self, ai_on, monkeypatch):
        async def good(prompt, schema):
            return GOOD_PAYLOAD

        monkeypatch.setattr(ai, "_ask", good)
        concept = await ai.enrich_concept(build_concept(LEAD, AUDIT), LEAD, AUDIT, "teks")
        html = render_index_html(LEAD, concept, AUDIT)

        assert "Seduh Manual" in html
        assert "Biji kopi digiling saat dipesan" in html
        assert "Kopi Susu" in html
        # The generic template copy it replaced must be gone.
        assert TEMPLATES["kuliner"].services[0][0] not in html

    async def test_template_still_renders_without_ai(self):
        concept = build_concept(LEAD, AUDIT)
        html = render_index_html(LEAD, concept, AUDIT)
        assert TEMPLATES["kuliner"].services[0][0] in html


class TestNicheClassification:
    async def test_confident_guess_is_used(self, ai_on, monkeypatch):
        async def confident(prompt, schema):
            return {"niche": "otomotif", "confidence": 0.9}

        monkeypatch.setattr(ai, "_ask", confident)
        assert await ai.classify_niche("Jaya Motor", "bengkel mobil") == "otomotif"

    async def test_low_confidence_is_rejected(self, ai_on, monkeypatch):
        """A hesitant guess is worse than the keyword heuristic it would replace."""
        async def unsure(prompt, schema):
            return {"niche": "otomotif", "confidence": 0.3}

        monkeypatch.setattr(ai, "_ask", unsure)
        assert await ai.classify_niche("Jaya Motor", "bengkel mobil") is None

    async def test_unknown_niche_rejected(self, ai_on, monkeypatch):
        async def bogus(prompt, schema):
            return {"niche": "peternakan-naga", "confidence": 1.0}

        monkeypatch.setattr(ai, "_ask", bogus)
        assert await ai.classify_niche("X", "teks") is None

    async def test_empty_page_text_skips_the_call(self, ai_on, monkeypatch):
        called = False

        async def tracker(prompt, schema):
            nonlocal called
            called = True
            return {"niche": "umum", "confidence": 1.0}

        monkeypatch.setattr(ai, "_ask", tracker)
        assert await ai.classify_niche("X", "   ") is None
        assert not called, "no point spending a request with nothing to classify"


class TestPromptSafety:
    async def test_system_prompt_forbids_invention(self):
        assert "JANGAN PERNAH mengarang" in ai._SYSTEM

    async def test_schema_pins_the_allowed_niches(self):
        assert set(ai._NICHE_SCHEMA["properties"]["niche"]["enum"]) == set(TEMPLATES)

    async def test_schema_is_closed(self):
        """additionalProperties:false keeps the response shape predictable."""
        assert ai._COPY_SCHEMA["additionalProperties"] is False
        assert ai._NICHE_SCHEMA["additionalProperties"] is False
