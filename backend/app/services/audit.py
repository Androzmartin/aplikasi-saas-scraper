"""Deterministic website audit scoring for MVP.

Five parameters, 20 points each, producing a 0-100 score plus an issue list and
an opportunity summary that the redesign generator consumes.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from app.services.extractor import page_text

MAX_PER_PARAMETER = 20

_CTA_PHRASES = [
    "hubungi", "pesan sekarang", "order", "beli", "checkout", "daftar", "booking",
    "konsultasi", "chat", "whatsapp", "wa sekarang", "minta penawaran", "get quote",
    "contact us", "buy now", "sign up", "book now", "request", "reservasi", "langganan",
]

_MODERN_MARKERS = [
    "tailwind", "bootstrap 5", "bootstrap.min.css", "flex", "grid-template",
    "--tw-", "css-", "styled-components", "next.js", "__next", "react", "vue",
]

_LEGACY_MARKERS = [
    "<frameset", "<marquee", "<blink", "<font ", "<center>", "bgcolor=",
    "border=\"1\"", "cellpadding", "cellspacing", "text/vbscript", "<applet",
]

_SECTION_KEYWORDS = [
    "tentang", "about", "layanan", "service", "produk", "product", "harga",
    "pricing", "testimoni", "testimonial", "portfolio", "galeri", "gallery",
    "kontak", "contact", "faq", "blog", "tim", "team",
]


def _grade(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "E"


def score_mobile_friendly(html: str, soup: BeautifulSoup) -> Dict[str, Any]:
    """Viewport meta, responsive CSS and fixed-width layout checks."""
    points = 0
    issues: List[Dict[str, str]] = []
    strengths: List[str] = []

    viewport = soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)})
    if viewport and "width" in (viewport.get("content") or "").lower():
        points += 10
        strengths.append("Sudah memiliki meta viewport untuk tampilan mobile.")
    else:
        issues.append(
            {
                "code": "no_viewport",
                "title": "Tidak ada meta viewport",
                "severity": "high",
                "detail": "Halaman tidak mendeklarasikan viewport, sehingga tampil mengecil di HP.",
            }
        )

    if "@media" in html or any(marker in html.lower() for marker in ("tailwind", "bootstrap", "--tw-")):
        points += 6
        strengths.append("Terdapat indikasi CSS responsif (media query / framework).")
    else:
        issues.append(
            {
                "code": "no_responsive_css",
                "title": "Tidak terdeteksi CSS responsif",
                "severity": "high",
                "detail": "Tidak ditemukan media query maupun framework CSS responsif.",
            }
        )

    fixed_width = re.search(r"width\s*:\s*(\d{3,4})px", html)
    if fixed_width and int(fixed_width.group(1)) >= 900:
        issues.append(
            {
                "code": "fixed_width_layout",
                "title": "Layout lebar tetap",
                "severity": "medium",
                "detail": f"Ditemukan lebar tetap {fixed_width.group(1)}px yang memaksa scroll horizontal di HP.",
            }
        )
    else:
        points += 4

    return {"points": min(points, MAX_PER_PARAMETER), "issues": issues, "strengths": strengths}


def score_cta(text: str, soup: BeautifulSoup) -> Dict[str, Any]:
    """Presence and prominence of a call to action."""
    points = 0
    issues: List[Dict[str, str]] = []
    strengths: List[str] = []
    lowered = text.lower()

    matches = [phrase for phrase in _CTA_PHRASES if phrase in lowered]
    if matches:
        points += 10
        strengths.append(f"Terdapat ajakan bertindak ({', '.join(matches[:3])}).")
    else:
        issues.append(
            {
                "code": "no_cta",
                "title": "Tidak ada call to action yang jelas",
                "severity": "high",
                "detail": "Tidak ditemukan ajakan seperti 'Hubungi Kami', 'Pesan Sekarang', atau 'Chat WhatsApp'.",
            }
        )

    action_links = soup.select('a[href^="tel:"], a[href^="mailto:"], a[href*="wa.me"], a[href*="whatsapp"]')
    if action_links:
        points += 6
        strengths.append("Tombol kontak langsung (telepon/WA/email) tersedia.")
    else:
        issues.append(
            {
                "code": "no_action_link",
                "title": "Tidak ada tombol kontak langsung",
                "severity": "medium",
                "detail": "Pengunjung harus menyalin nomor manual karena tidak ada link tel/WA/email.",
            }
        )

    buttons = soup.find_all(["button"]) + soup.select('a[class*="btn"], a[class*="button"], input[type="submit"]')
    if buttons:
        points += 4
    else:
        issues.append(
            {
                "code": "no_button_element",
                "title": "Tidak ada elemen tombol",
                "severity": "low",
                "detail": "Halaman tidak memakai elemen tombol sehingga CTA kurang menonjol secara visual.",
            }
        )

    return {"points": min(points, MAX_PER_PARAMETER), "issues": issues, "strengths": strengths}


def score_contact_clarity(contact: Dict[str, Any]) -> Dict[str, Any]:
    """Whether a prospect can actually reach the business."""
    points = 0
    issues: List[Dict[str, str]] = []
    strengths: List[str] = []

    if contact.get("whatsapp_number"):
        points += 8
        strengths.append("Nomor WhatsApp publik tersedia.")
    else:
        issues.append(
            {
                "code": "no_whatsapp",
                "title": "Tidak ada WhatsApp publik",
                "severity": "high",
                "detail": "WhatsApp adalah kanal utama UMKM Indonesia, namun tidak ditemukan di website.",
            }
        )

    if contact.get("phone_number"):
        points += 4
        strengths.append("Nomor telepon tercantum.")
    if contact.get("email"):
        points += 4
        strengths.append("Email publik tercantum.")
    else:
        issues.append(
            {
                "code": "no_email",
                "title": "Tidak ada email publik",
                "severity": "low",
                "detail": "Tidak ditemukan alamat email yang bisa dihubungi.",
            }
        )

    if contact.get("address"):
        points += 4
        strengths.append("Alamat bisnis ditampilkan.")
    else:
        issues.append(
            {
                "code": "no_address",
                "title": "Alamat tidak ditampilkan",
                "severity": "medium",
                "detail": "Alamat fisik tidak ditemukan, menurunkan kepercayaan calon pelanggan lokal.",
            }
        )

    return {"points": min(points, MAX_PER_PARAMETER), "issues": issues, "strengths": strengths}


def score_structure(soup: BeautifulSoup, text: str) -> Dict[str, Any]:
    """Basic information architecture: headings, sections, navigation."""
    points = 0
    issues: List[Dict[str, str]] = []
    strengths: List[str] = []

    h1s = soup.find_all("h1")
    if len(h1s) == 1:
        points += 6
        strengths.append("Struktur heading utama (H1) tunggal dan jelas.")
    elif not h1s:
        issues.append(
            {
                "code": "no_h1",
                "title": "Tidak ada heading utama (H1)",
                "severity": "medium",
                "detail": "Halaman tidak memiliki H1 sehingga pesan utama tidak tegas.",
            }
        )
    else:
        points += 3
        issues.append(
            {
                "code": "multiple_h1",
                "title": f"Terdapat {len(h1s)} H1",
                "severity": "low",
                "detail": "Lebih dari satu H1 membuat hirarki konten membingungkan.",
            }
        )

    semantic = soup.find_all(["section", "header", "footer", "main", "nav", "article"])
    if len(semantic) >= 4:
        points += 6
        strengths.append("Menggunakan tag semantik (section/header/footer).")
    elif semantic:
        points += 3
    else:
        issues.append(
            {
                "code": "no_semantic_sections",
                "title": "Tidak memakai struktur section semantik",
                "severity": "medium",
                "detail": "Konten tidak dipecah menjadi section sehingga sulit dibaca berurutan.",
            }
        )

    lowered = text.lower()
    found_sections = [kw for kw in _SECTION_KEYWORDS if kw in lowered]
    if len(found_sections) >= 4:
        points += 5
        strengths.append("Bagian penting (tentang, layanan, kontak) sudah ada.")
    elif len(found_sections) >= 2:
        points += 3
    else:
        issues.append(
            {
                "code": "thin_sections",
                "title": "Bagian halaman sangat minim",
                "severity": "high",
                "detail": "Tidak ditemukan bagian standar seperti Tentang, Layanan/Produk, atau Kontak.",
            }
        )

    if soup.find("nav") or len(soup.select("header a")) >= 3:
        points += 3
    else:
        issues.append(
            {
                "code": "no_navigation",
                "title": "Navigasi tidak jelas",
                "severity": "low",
                "detail": "Tidak ada menu navigasi yang mudah dikenali.",
            }
        )

    return {"points": min(points, MAX_PER_PARAMETER), "issues": issues, "strengths": strengths}


def score_visual_impression(html: str, soup: BeautifulSoup, text: str) -> Dict[str, Any]:
    """Modern vs dated visual impression, judged from markup signals."""
    points = 0
    issues: List[Dict[str, str]] = []
    strengths: List[str] = []
    lowered_html = html.lower()

    legacy_hits = [marker for marker in _LEGACY_MARKERS if marker in lowered_html]
    modern_hits = [marker for marker in _MODERN_MARKERS if marker in lowered_html]

    if legacy_hits:
        issues.append(
            {
                "code": "legacy_markup",
                "title": "Markup bergaya lama",
                "severity": "high",
                "detail": f"Ditemukan elemen usang: {', '.join(legacy_hits[:3])}.",
            }
        )
    else:
        points += 6

    if modern_hits:
        points += 6
        strengths.append("Memakai CSS/framework modern.")
    else:
        issues.append(
            {
                "code": "no_modern_css",
                "title": "Tidak ada indikasi styling modern",
                "severity": "medium",
                "detail": "Tidak terdeteksi framework atau teknik layout modern (flex/grid).",
            }
        )

    images = soup.find_all("img")
    if images:
        points += 4
        missing_alt = [img for img in images if not (img.get("alt") or "").strip()]
        if missing_alt:
            issues.append(
                {
                    "code": "images_missing_alt",
                    "title": f"{len(missing_alt)} gambar tanpa teks alternatif",
                    "severity": "low",
                    "detail": "Atribut alt kosong menurunkan aksesibilitas dan SEO.",
                }
            )
        else:
            strengths.append("Semua gambar memiliki teks alternatif.")
    else:
        issues.append(
            {
                "code": "no_images",
                "title": "Tidak ada gambar produk/bisnis",
                "severity": "medium",
                "detail": "Website tanpa visual sulit meyakinkan calon pelanggan.",
            }
        )

    if len(text) >= 600:
        points += 4
        strengths.append("Konten teks cukup untuk menjelaskan bisnis.")
    else:
        issues.append(
            {
                "code": "thin_content",
                "title": "Konten sangat tipis",
                "severity": "medium",
                "detail": f"Hanya sekitar {len(text)} karakter teks pada halaman utama.",
            }
        )

    return {"points": min(points, MAX_PER_PARAMETER), "issues": issues, "strengths": strengths}


def build_opportunity_summary(score: int, issues: List[Dict[str, str]], business: str) -> str:
    name = business or "Website ini"
    high = [i for i in issues if i["severity"] == "high"]
    if score >= 80:
        return (
            f"{name} sudah tergolong baik. Peluang redesign berada pada penajaman pesan "
            "dan konversi, bukan perbaikan fundamental."
        )
    if score >= 60:
        return (
            f"{name} cukup layak, namun ada {len(issues)} temuan yang menahan konversi. "
            "Redesign dapat fokus pada CTA, struktur halaman, dan tampilan mobile."
        )
    if score >= 40:
        return (
            f"{name} memiliki {len(high)} masalah utama dan {len(issues)} temuan total. "
            "Redesign landing page akan memberi peningkatan kredibilitas yang terasa langsung."
        )
    return (
        f"{name} tertinggal cukup jauh dari standar sekarang ({len(high)} masalah utama). "
        "Ini peluang redesign bernilai tinggi: hampir setiap aspek dapat diperbaiki."
    )


def build_redesign_summary(breakdown: Dict[str, int], business: str) -> str:
    weakest = sorted(breakdown.items(), key=lambda kv: kv[1])[:2]
    labels = {
        "mobile_friendly": "tampilan mobile",
        "cta_clarity": "kejelasan call to action",
        "contact_clarity": "akses kontak",
        "structure": "struktur section",
        "visual_impression": "kesan visual",
    }
    focus = " dan ".join(labels.get(key, key) for key, _ in weakest)
    name = business or "bisnis ini"
    return (
        f"Konsep redesign untuk {name} diprioritaskan pada perbaikan {focus}, "
        "dengan hero yang tegas, bukti sosial, dan jalur kontak WhatsApp satu klik."
    )


def run_audit(html: str, contact: Dict[str, Any]) -> Dict[str, Any]:
    """Score a page and return the full audit document body."""
    soup = BeautifulSoup(html or "", "lxml")
    text = page_text(soup)

    parts = {
        "mobile_friendly": score_mobile_friendly(html or "", soup),
        "cta_clarity": score_cta(text, soup),
        "contact_clarity": score_contact_clarity(contact or {}),
        "structure": score_structure(soup, text),
        "visual_impression": score_visual_impression(html or "", soup, text),
    }

    breakdown = {key: part["points"] for key, part in parts.items()}
    score = sum(breakdown.values())
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    issues: List[Dict[str, str]] = []
    strengths: List[str] = []
    for part in parts.values():
        issues.extend(part["issues"])
        strengths.extend(part["strengths"])
    issues.sort(key=lambda issue: severity_rank.get(issue["severity"], 3))

    business = (contact or {}).get("business_name") or ""
    return {
        "score": score,
        "grade": _grade(score),
        "breakdown": breakdown,
        "issues": issues,
        "strengths": strengths,
        "opportunity_summary": build_opportunity_summary(score, issues, business),
        "redesign_summary": build_redesign_summary(breakdown, business),
    }
