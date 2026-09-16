"""Optional AI copy enrichment.

Disabled by default. When enabled, only the headline/subheadline copy is
replaced; the HTML skeleton and every other field stay deterministic so output
quality and formality remain under our control.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_PROMPT = """Anda adalah copywriter senior untuk agency digital Indonesia.
Tulis ulang headline dan subheadline landing page untuk bisnis berikut.

Nama bisnis: {business}
Industri: {industry}
Wilayah: {area}
Temuan audit utama: {issues}

Aturan:
- Bahasa Indonesia, nada formal-profesional, bukan hiperbolis.
- Headline maksimal 70 karakter.
- Subheadline maksimal 140 karakter, memuat ajakan menghubungi.
- Jangan mengarang klaim (penghargaan, jumlah pelanggan, sertifikasi).

Jawab HANYA dengan JSON: {{"headline": "...", "subheadline": "..."}}"""


async def enrich_concept(concept: Dict[str, Any], lead: Dict[str, Any], audit: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return the concept with AI copy applied, or unchanged on any failure."""
    if not settings.ai_enabled or not settings.ai_api_key:
        return concept

    issues = ", ".join(i.get("title", "") for i in (audit or {}).get("issues", [])[:4]) or "tidak ada"
    prompt = _PROMPT.format(
        business=lead.get("business_name") or "UMKM",
        industry=concept.get("industry", "umum"),
        area=concept.get("area_label", "Jakarta"),
        issues=issues,
    )

    try:
        text = await _call_provider(prompt)
        if not text:
            return concept
        payload = _parse_json(text)
        headline = (payload.get("headline") or "").strip()
        subheadline = (payload.get("subheadline") or "").strip()
        if headline and subheadline and len(headline) <= 120 and len(subheadline) <= 240:
            enriched = dict(concept)
            enriched["headline"] = headline
            enriched["subheadline"] = subheadline
            enriched["generated_with"] = f"ai:{settings.ai_model}"
            return enriched
    except Exception as exc:  # noqa: BLE001 - AI is best-effort, never fatal
        logger.warning("AI enrichment failed, using template copy: %s", exc)

    return concept


def _parse_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return {}
    return json.loads(text[start : end + 1])


async def _call_provider(prompt: str) -> Optional[str]:
    provider = settings.ai_provider.lower()
    async with httpx.AsyncClient(timeout=45.0) as client:
        if provider == "anthropic":
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.ai_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": settings.ai_model,
                    "max_tokens": 512,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            blocks = response.json().get("content", [])
            return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")

        if provider == "openai":
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.ai_api_key}"},
                json={
                    "model": settings.ai_model,
                    "max_tokens": 512,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    logger.warning("Unknown AI provider %r; falling back to template copy", provider)
    return None
