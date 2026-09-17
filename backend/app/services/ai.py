"""Optional AI enrichment for the redesign generator.

Disabled by default. Everything here is best-effort: on any failure the caller
falls back to the deterministic templates, so a missing API key, a rate limit or
a malformed response can never break scraping, auditing or generation.

Two jobs:
  1. classify_niche()   - pick the right template from the page's own words,
                          which is more accurate than matching the business name
                          against a keyword list.
  2. generate_copy()    - write the whole copy set (hero, service cards, trust
                          points, highlight section) for this specific business
                          instead of filling a generic template.

Output is constrained with structured outputs, then validated again locally:
the model is told not to invent claims, and claim-shaped text is rejected even
if it slips through. An agency sends this to a real prospect, so a fabricated
"sejak 1998" or "1000+ pelanggan" is worse than a plain template.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.templates import TEMPLATES

logger = logging.getLogger(__name__)

MAX_PAGE_CHARS = 6_000

# Hard limits so AI copy cannot break the page layout.
LIMITS = {
    "headline": 80,
    "subheadline": 160,
    "card_title": 45,
    "card_body": 140,
    "trust_point": 90,
}

# Claim-shaped text we refuse to put in front of a prospect unless the business
# actually published it. The model is instructed not to write these; this is the
# backstop for when it does anyway.
_FABRICATION_PATTERNS = [
    re.compile(r"\d+\s*\+", re.IGNORECASE),                 # "1000+ pelanggan"
    re.compile(r"\bsejak\s+\d{4}\b", re.IGNORECASE),        # "sejak 1998"
    re.compile(r"\b\d+\s*(tahun|thn)\b", re.IGNORECASE),    # "15 tahun pengalaman"
    re.compile(r"\b\d+\s*%", re.IGNORECASE),                # "98% puas"
    re.compile(r"\b(nomor|no\.?)\s*1\b", re.IGNORECASE),    # "nomor 1 di Jakarta"
    re.compile(r"\bter(baik|murah|besar|laris)\s+(se|di)\b", re.IGNORECASE),
    re.compile(r"\b(bersertifikat|tersertifikasi|iso\s*\d+)\b", re.IGNORECASE),
    re.compile(r"\b(juara|penghargaan|award)\b", re.IGNORECASE),
]


@dataclass
class CopySet:
    headline: str
    subheadline: str
    services: List[Dict[str, str]] = field(default_factory=list)
    trust_points: List[str] = field(default_factory=list)
    highlight_items: List[Dict[str, str]] = field(default_factory=list)


def is_enabled() -> bool:
    return bool(settings.ai_enabled and settings.ai_api_key)


def _client():
    """Build an async Anthropic client, or None when unavailable.

    The SDK is an optional dependency so a deployment that never turns AI on
    does not have to install it.
    """
    try:
        from anthropic import AsyncAnthropic  # noqa: PLC0415
    except ImportError:
        logger.info("AI enabled but the anthropic SDK is not installed; using templates")
        return None
    return AsyncAnthropic(api_key=settings.ai_api_key, timeout=settings.ai_timeout_seconds)


def looks_fabricated(text: str) -> bool:
    """True when the text makes a claim we have no evidence for."""
    return any(pattern.search(text or "") for pattern in _FABRICATION_PATTERNS)


def _clean(value: Any, limit: int) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = re.sub(r"\s+", " ", value).strip()
    if not text or len(text) > limit or looks_fabricated(text):
        return None
    return text


def _clean_cards(raw: Any, count: int = 3) -> Optional[List[Dict[str, str]]]:
    if not isinstance(raw, list) or len(raw) < count:
        return None
    cards: List[Dict[str, str]] = []
    for item in raw[:count]:
        if not isinstance(item, dict):
            return None
        title = _clean(item.get("title"), LIMITS["card_title"])
        body = _clean(item.get("body"), LIMITS["card_body"])
        if not title or not body:
            return None
        cards.append({"title": title, "body": body})
    return cards


def validate_copy(payload: Dict[str, Any]) -> Optional[CopySet]:
    """Turn a raw model response into a CopySet, or None if anything is off."""
    headline = _clean(payload.get("headline"), LIMITS["headline"])
    subheadline = _clean(payload.get("subheadline"), LIMITS["subheadline"])
    services = _clean_cards(payload.get("services"))
    highlight_items = _clean_cards(payload.get("highlight_items"))

    raw_points = payload.get("trust_points")
    trust_points: List[str] = []
    if isinstance(raw_points, list):
        for point in raw_points[:3]:
            cleaned = _clean(point, LIMITS["trust_point"])
            if not cleaned:
                trust_points = []
                break
            trust_points.append(cleaned)

    if not (headline and subheadline and services and highlight_items and len(trust_points) == 3):
        return None

    return CopySet(
        headline=headline,
        subheadline=subheadline,
        services=services,
        trust_points=trust_points,
        highlight_items=highlight_items,
    )


# --------------------------------------------------------------------- prompts

_SYSTEM = (
    "Anda copywriter senior untuk agency digital di Indonesia. Anda menulis "
    "naskah landing page berbahasa Indonesia yang formal-profesional, ringkas, "
    "dan tidak hiperbolis.\n\n"
    "Aturan mutlak: JANGAN PERNAH mengarang fakta. Dilarang menyebut jumlah "
    "pelanggan, tahun berdiri, lama pengalaman, persentase, peringkat, "
    "penghargaan, atau sertifikasi — kecuali informasi itu tertulis jelas pada "
    "konten yang diberikan. Jika tidak ada buktinya, tulis manfaat yang umum "
    "dan jujur saja."
)

_COPY_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "description": "Maksimal 70 karakter."},
        "subheadline": {"type": "string", "description": "Maksimal 140 karakter, memuat ajakan menghubungi."},
        "services": {
            "type": "array",
            "description": "Tepat 3 kartu layanan/produk unggulan.",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Maksimal 40 karakter."},
                    "body": {"type": "string", "description": "Maksimal 120 karakter."},
                },
                "required": ["title", "body"],
                "additionalProperties": False,
            },
        },
        "trust_points": {
            "type": "array",
            "description": "Tepat 3 alasan memilih, masing-masing maksimal 80 karakter.",
            "items": {"type": "string"},
        },
        "highlight_items": {
            "type": "array",
            "description": "Tepat 3 item untuk section khusus industri ini.",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Maksimal 40 karakter."},
                    "body": {"type": "string", "description": "Maksimal 120 karakter."},
                },
                "required": ["title", "body"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["headline", "subheadline", "services", "trust_points", "highlight_items"],
    "additionalProperties": False,
}

_NICHE_SCHEMA = {
    "type": "object",
    "properties": {
        "niche": {"type": "string", "enum": sorted(TEMPLATES.keys())},
        "confidence": {"type": "number", "description": "0 sampai 1."},
    },
    "required": ["niche", "confidence"],
    "additionalProperties": False,
}


async def _ask(prompt: str, schema: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """One structured-output request. Returns parsed JSON, or None on any failure."""
    client = _client()
    if client is None:
        return None

    import json  # noqa: PLC0415

    try:
        response = await client.messages.create(
            model=settings.ai_model,
            max_tokens=2048,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            thinking={"type": "adaptive"},
            output_config={
                # Copywriting within fixed constraints does not need deep
                # reasoning, and this runs once per lead.
                "effort": "low",
                "format": {"type": "json_schema", "schema": schema},
            },
        )
        # output_config.format guarantees the first text block is valid JSON.
        text = next((b.text for b in response.content if b.type == "text"), None)
        if not text:
            return None
        return json.loads(text)
    except Exception as exc:  # noqa: BLE001 - AI is optional, never fatal
        logger.warning("AI request failed (%s); falling back to templates", exc.__class__.__name__)
        return None
    finally:
        try:
            await client.close()
        except Exception:  # noqa: BLE001
            pass


async def classify_niche(business_name: str, page_text: str) -> Optional[str]:
    """Pick a template niche from the page's own words."""
    if not is_enabled() or not page_text.strip():
        return None

    prompt = (
        f"Tentukan kategori usaha untuk bisnis berikut.\n\n"
        f"Nama bisnis: {business_name or '(tidak diketahui)'}\n\n"
        f"Cuplikan isi website:\n{page_text[:MAX_PAGE_CHARS]}\n\n"
        f"Pilih satu kategori yang paling sesuai. Gunakan 'umum' bila ragu."
    )
    payload = await _ask(prompt, _NICHE_SCHEMA)
    if not payload:
        return None

    niche = payload.get("niche")
    confidence = payload.get("confidence")
    if niche not in TEMPLATES:
        return None
    # A low-confidence guess is worse than the keyword heuristic it replaces.
    if not isinstance(confidence, (int, float)) or confidence < 0.6:
        logger.info("AI niche guess %r rejected (confidence %s)", niche, confidence)
        return None
    return niche


async def generate_copy(
    lead: Dict[str, Any],
    audit: Optional[Dict[str, Any]],
    template_key: str,
    page_text: str = "",
    area_label: str = "",
) -> Optional[CopySet]:
    """Write the full copy set for one business."""
    if not is_enabled():
        return None

    template = TEMPLATES.get(template_key) or TEMPLATES["umum"]
    issues = ", ".join(
        issue.get("title", "") for issue in (audit or {}).get("issues", [])[:4]
    ) or "tidak ada catatan"

    prompt = (
        f"Tulis naskah landing page baru untuk bisnis ini.\n\n"
        f"Nama bisnis: {lead.get('business_name') or 'UMKM'}\n"
        f"Kategori: {template.label}\n"
        f"Wilayah: {area_label or 'Jabodetabek'}\n"
        f"Temuan audit website lama: {issues}\n"
        f"Nama section khusus: {template.highlight_title}\n\n"
        f"Cuplikan isi website lama (pakai hanya sebagai konteks, jangan menyalin "
        f"klaim yang tidak ada di sini):\n{(page_text or '(tidak tersedia)')[:MAX_PAGE_CHARS]}\n\n"
        f"Tulis: headline, subheadline, 3 kartu layanan, 3 alasan memilih, dan "
        f"3 item untuk section '{template.highlight_title}'. "
        f"Gunakan Bahasa Indonesia yang formal dan wajar."
    )

    payload = await _ask(prompt, _COPY_SCHEMA)
    if not payload:
        return None

    copy_set = validate_copy(payload)
    if copy_set is None:
        logger.warning("AI copy rejected by validation; using template for %s", template_key)
        return None
    return copy_set


async def enrich_concept(
    concept: Dict[str, Any],
    lead: Dict[str, Any],
    audit: Optional[Dict[str, Any]],
    page_text: str = "",
) -> Dict[str, Any]:
    """Apply AI copy to a concept, or return it unchanged."""
    if not is_enabled():
        return concept

    copy_set = await generate_copy(
        lead,
        audit,
        concept.get("template_key", "umum"),
        page_text,
        concept.get("area_label", ""),
    )
    if copy_set is None:
        return concept

    enriched = dict(concept)
    enriched["headline"] = copy_set.headline
    enriched["subheadline"] = copy_set.subheadline
    enriched["ai_services"] = copy_set.services
    enriched["ai_trust_points"] = copy_set.trust_points
    enriched["ai_highlight_items"] = copy_set.highlight_items
    enriched["generated_with"] = f"ai:{settings.ai_model}"
    return enriched
