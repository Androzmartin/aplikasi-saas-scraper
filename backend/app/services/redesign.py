"""Generate a redesign concept and a single-file, Tailwind Play CDN landing page.

The generator is deterministic by default so output stays formal and premium
without depending on an AI provider. When AI is enabled the copy fields may be
replaced, but the HTML skeleton below is always what gets rendered.
"""
from __future__ import annotations

import html as html_lib
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.regions import region_label
from app.services.templates import TEMPLATES, NicheTemplate, get_template

SECTION_PLAN = [
    "Hero dengan proposisi nilai dan CTA WhatsApp",
    "Ringkasan layanan / produk unggulan",
    "Alasan memilih (trust builders)",
    "Bukti sosial & testimoni",
    "Galeri / showcase",
    "Lokasi & jam operasional",
    "Penutup CTA dan footer kontak",
]

_INDUSTRY_HINTS = {
    "kuliner": ["kopi", "cafe", "resto", "warung", "catering", "bakery", "kue", "food", "dapur", "kuliner", "seafood", "bakso"],
    "fashion": ["butik", "fashion", "hijab", "batik", "konveksi", "garment", "baju", "sepatu"],
    "jasa": ["jasa", "service", "servis", "konsultan", "kontraktor", "renovasi", "laundry", "cleaning"],
    "kesehatan": ["klinik", "dental", "gigi", "apotek", "terapi", "medis", "health", "spa"],
    "otomotif": ["bengkel", "motor", "mobil", "otomotif", "rental", "sparepart"],
    "properti": ["properti", "property", "rumah", "kost", "kontrakan", "realty"],
    "pendidikan": ["kursus", "bimbel", "les", "academy", "training", "edukasi", "school"],
}

_INDUSTRY_COPY = {
    "kuliner": ("Rasa yang dikenal, layanan yang dipercaya", "Pesan langsung lewat WhatsApp, siap diantar hari ini."),
    "fashion": ("Koleksi pilihan untuk tampil percaya diri", "Stok terbatas — konsultasikan ukuran dan model Anda sekarang."),
    "jasa": ("Pengerjaan rapi, tepat waktu, bergaransi", "Konsultasi kebutuhan Anda gratis melalui WhatsApp."),
    "kesehatan": ("Penanganan profesional yang membuat Anda tenang", "Jadwalkan kunjungan Anda dengan satu pesan."),
    "otomotif": ("Servis presisi oleh teknisi berpengalaman", "Booking jadwal servis tanpa antre panjang."),
    "properti": ("Temukan properti yang tepat, tanpa ribet", "Tanyakan ketersediaan unit hari ini."),
    "pendidikan": ("Belajar terarah dengan pendamping berpengalaman", "Ambil kelas percobaan Anda minggu ini."),
    "umum": ("Solusi tepercaya untuk kebutuhan Anda", "Hubungi kami lewat WhatsApp untuk penawaran terbaik."),
}


def detect_industry(business_name: Optional[str], extra: Optional[str] = None) -> str:
    haystack = f"{business_name or ''} {extra or ''}".lower()
    for industry, keywords in _INDUSTRY_HINTS.items():
        if any(keyword in haystack for keyword in keywords):
            return industry
    return "umum"


def _wa_link(number: Optional[str], business: str) -> Optional[str]:
    if not number:
        return None
    digits = re.sub(r"\D", "", number)
    if not digits:
        return None
    message = f"Halo {business}, saya ingin bertanya mengenai produk/layanan Anda."
    from urllib.parse import quote

    return f"https://wa.me/{digits}?text={quote(message)}"


def build_concept(
    lead: Dict[str, Any],
    audit: Optional[Dict[str, Any]] = None,
    template_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Produce the copy + structure concept for the new landing page.

    template_key lets the user override the auto-detected niche when the
    guess is wrong, which is common for businesses with a generic name.
    """
    business = lead.get("business_name") or "Bisnis Anda"
    industry = template_key if template_key in TEMPLATES else detect_industry(
        business, lead.get("address")
    )
    template = get_template(industry)
    base_headline, base_sub = template.headline, template.subheadline

    area = region_label(lead.get("region"))
    if lead.get("region") and lead["region"] not in ("unknown", "other"):
        headline = f"{base_headline} di {area}"
    else:
        headline = base_headline

    issues = (audit or {}).get("issues", [])
    fix_map = {
        "no_whatsapp": "Tombol WhatsApp melekat di setiap layar.",
        "no_cta": "Ajakan bertindak yang jelas di hero dan penutup.",
        "no_viewport": "Layout mobile-first yang rapi di semua ukuran layar.",
        "no_responsive_css": "Grid responsif menggantikan layout lebar tetap.",
        "no_address": "Blok lokasi dan jam operasional yang mudah ditemukan.",
        "thin_sections": "Struktur section lengkap dari hero sampai penutup.",
        "legacy_markup": "Tampilan modern menggantikan markup lama.",
        "no_images": "Area showcase untuk foto produk dan suasana.",
        "thin_content": "Naskah yang menjelaskan nilai jual secara ringkas.",
        "no_modern_css": "Sistem visual konsisten dengan tipografi profesional.",
    }
    improvements = []
    for issue in issues:
        fix = fix_map.get(issue.get("code"))
        if fix and fix not in improvements:
            improvements.append(fix)
    if not improvements:
        improvements = [
            "Hero yang menegaskan proposisi nilai.",
            "Jalur kontak WhatsApp satu klik.",
            "Bukti sosial untuk meningkatkan kepercayaan.",
        ]

    return {
        "headline": headline,
        "subheadline": base_sub,
        "industry": industry,
        "template_key": template.key,
        "template_label": template.label,
        "sections": template.sections or SECTION_PLAN,
        "improvements": improvements[:6],
        "area_label": area,
    }


def _esc(value: Optional[str]) -> str:
    return html_lib.escape(value or "", quote=True)


def render_index_html(lead: Dict[str, Any], concept: Dict[str, Any], audit: Optional[Dict[str, Any]] = None) -> str:
    """Render the downloadable single-file landing page (Tailwind Play CDN)."""
    business = lead.get("business_name") or "Bisnis Anda"
    headline = concept.get("headline") or business
    subheadline = concept.get("subheadline") or ""
    area = concept.get("area_label") or ""
    improvements: List[str] = concept.get("improvements") or []
    template: NicheTemplate = get_template(concept.get("template_key") or concept.get("industry"))
    accent = template.accent

    whatsapp = lead.get("whatsapp_number")
    phone = lead.get("phone_number")
    email = lead.get("email")
    address = lead.get("address")
    wa_href = _wa_link(whatsapp, business)

    year = datetime.now(timezone.utc).year
    initials = "".join(word[0] for word in re.findall(r"[A-Za-z]+", business)[:2]).upper() or "UM"

    primary_cta = (
        f'<a href="{_esc(wa_href)}" target="_blank" rel="noopener"'
        f' class="inline-flex items-center justify-center gap-2 rounded-lg bg-{accent}-600 px-6 py-3'
        f' text-sm font-semibold text-white shadow-sm transition hover:bg-{accent}-700'
        f' focus:outline-none focus-visible:ring-2 focus-visible:ring-{accent}-400">'
        '<svg class="h-4 w-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">'
        '<path d="M12.04 2c-5.46 0-9.91 4.45-9.91 9.91 0 1.75.46 3.45 1.32 4.95L2 22l5.25-1.38a9.87 9.87 0 0 0 4.79 1.22h.01c5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.82 9.82 0 0 0 12.04 2Zm0 18.02h-.01a8.2 8.2 0 0 1-4.18-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.22 8.22 0 0 1 12.77-10.2 8.16 8.16 0 0 1 2.41 5.82c0 4.54-3.7 8.24-8.2 8.24Z"/>'
        f"</svg>{_esc(template.cta_label)}</a>"
        if wa_href
        else '<a href="#kontak" class="inline-flex items-center justify-center rounded-lg bg-slate-900 px-6 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800">Hubungi Kami</a>'
    )

    contact_rows = []
    if whatsapp:
        contact_rows.append(("WhatsApp", _esc(whatsapp), _esc(wa_href or "#")))
    if phone:
        contact_rows.append(("Telepon", _esc(phone), f"tel:{_esc(re.sub(r'[^0-9+]', '', phone))}"))
    if email:
        contact_rows.append(("Email", _esc(email), f"mailto:{_esc(email)}"))

    contact_html = "".join(
        f'<li class="flex items-center justify-between gap-4 border-b border-slate-200 py-3 last:border-0">'
        f'<span class="text-sm font-medium text-slate-500">{label}</span>'
        f'<a href="{href}" class="text-sm font-semibold text-slate-900 hover:text-{accent}-700">{value}</a></li>'
        for label, value, href in contact_rows
    ) or '<li class="py-3 text-sm text-slate-500">Silakan lengkapi data kontak Anda.</li>'

    # AI copy, when present, replaces the template's generic cards.
    services = concept.get("ai_services") or template.services
    services = [
        (item["title"], item["body"]) if isinstance(item, dict) else item
        for item in services
    ]
    services_html = "".join(
        f'<article class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition hover:shadow-md">'
        f'<div class="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-{accent}-600 text-sm font-semibold text-white">{idx + 1}</div>'
        f'<h3 class="text-base font-semibold text-slate-900">{_esc(title)}</h3>'
        f'<p class="mt-2 text-sm leading-relaxed text-slate-600">{_esc(body)}</p></article>'
        for idx, (title, body) in enumerate(services)
    )

    improvements_html = "".join(
        f'<li class="flex gap-3"><span class="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-{accent}-500"></span>'
        f'<span class="text-sm leading-relaxed text-slate-600">{_esc(item)}</span></li>'
        for item in improvements
    )

    testimonials = [(quote, "Pelanggan", area or "Jakarta") for quote in template.testimonials]

    highlight_items = concept.get("ai_highlight_items") or template.highlight_items
    highlight_items = [
        (item["title"], item["body"]) if isinstance(item, dict) else item
        for item in highlight_items
    ]
    highlight_html = "".join(
        f'<article class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">'
        f'<h3 class="text-base font-semibold text-slate-900">{_esc(title)}</h3>'
        f'<p class="mt-2 text-sm leading-relaxed text-slate-600">{_esc(body)}</p></article>'
        for title, body in highlight_items
    )

    trust_html = "".join(
        f'<li class="flex items-start gap-3">'
        f'<svg class="mt-0.5 h-5 w-5 shrink-0 text-{accent}-600" fill="none" viewBox="0 0 24 24"'
        ' stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round"'
        ' d="M9 12l2 2 4-4"/><circle cx="12" cy="12" r="9"/></svg>'
        f'<span class="text-sm text-slate-700">{_esc(point)}</span></li>'
        for point in (concept.get("ai_trust_points") or template.trust_points)
    )
    testimonials_html = "".join(
        f'<figure class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">'
        f'<blockquote class="text-sm leading-relaxed text-slate-700">&ldquo;{_esc(quote)}&rdquo;</blockquote>'
        f'<figcaption class="mt-4 text-xs font-medium uppercase tracking-wide text-slate-500">{_esc(who)} &middot; {_esc(where)}</figcaption>'
        "</figure>"
        for quote, who, where in testimonials
    )

    address_block = (
        f'<div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">'
        f'<h3 class="text-sm font-semibold uppercase tracking-wide text-slate-500">Lokasi</h3>'
        f'<p class="mt-3 text-sm leading-relaxed text-slate-700">{_esc(address)}</p>'
        f'<p class="mt-4 text-sm text-slate-500">Jam operasional: Senin&ndash;Sabtu, 09.00&ndash;17.00 WIB</p></div>'
        if address
        else ""
    )

    score_badge = ""
    if audit and isinstance(audit.get("score"), int):
        score_badge = (
            f'<span class="ml-3 rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">'
            f'Skor website lama: {audit["score"]}/100</span>'
        )

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(business)} &mdash; {_esc(headline)}</title>
<meta name="description" content="{_esc(subheadline)}">
<script src="https://cdn.tailwindcss.com"></script>
<script>
  tailwind.config = {{
    theme: {{
      extend: {{
        fontFamily: {{ sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'] }},
        colors: {{ navy: {{ 900: '#0f172a', 800: '#1e293b' }} }}
      }}
    }}
  }}
</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
</head>
<body class="bg-white font-sans text-slate-900 antialiased">

<header class="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur">
  <div class="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-4">
    <a href="#" class="flex items-center gap-3">
      <span class="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-900 text-sm font-bold text-white">{_esc(initials)}</span>
      <span class="text-base font-semibold tracking-tight">{_esc(business)}</span>
    </a>
    <nav class="hidden items-center gap-8 md:flex">
      <a href="#layanan" class="text-sm font-medium text-slate-600 transition hover:text-slate-900">Layanan</a>
      <a href="#unggulan" class="text-sm font-medium text-slate-600 transition hover:text-slate-900">{_esc(template.highlight_title)}</a>
      <a href="#keunggulan" class="text-sm font-medium text-slate-600 transition hover:text-slate-900">Keunggulan</a>
      <a href="#testimoni" class="text-sm font-medium text-slate-600 transition hover:text-slate-900">Testimoni</a>
      <a href="#kontak" class="text-sm font-medium text-slate-600 transition hover:text-slate-900">Kontak</a>
    </nav>
    {primary_cta}
  </div>
</header>

<main>
  <section class="relative overflow-hidden border-b border-slate-200 bg-slate-50">
    <div class="mx-auto grid max-w-6xl gap-12 px-6 py-20 md:grid-cols-2 md:items-center md:py-28">
      <div>
        <p class="text-xs font-semibold uppercase tracking-[0.2em] text-{accent}-700">{_esc(template.hero_eyebrow)} &middot; {_esc(area)}</p>
        <h1 class="mt-4 text-4xl font-bold leading-tight tracking-tight text-slate-900 md:text-5xl">{_esc(headline)}</h1>
        <p class="mt-6 text-lg leading-relaxed text-slate-600">{_esc(subheadline)}</p>
        <div class="mt-8 flex flex-wrap items-center gap-4">
          {primary_cta}
          <a href="#layanan" class="text-sm font-semibold text-slate-700 underline-offset-4 hover:underline">Lihat layanan &rarr;</a>
        </div>
      </div>
      <div class="rounded-2xl border border-slate-200 bg-white p-8 shadow-lg">
        <h2 class="text-sm font-semibold uppercase tracking-wide text-slate-500">Hubungi Langsung</h2>
        <ul class="mt-4">{contact_html}</ul>
      </div>
    </div>
  </section>

  <section id="layanan" class="mx-auto max-w-6xl px-6 py-20">
    <h2 class="text-2xl font-bold tracking-tight text-slate-900 md:text-3xl">Yang Kami Tawarkan</h2>
    <p class="mt-3 max-w-2xl text-sm leading-relaxed text-slate-600">Ringkasan layanan utama yang paling sering dicari pelanggan {_esc(business)}.</p>
    <div class="mt-10 grid gap-6 md:grid-cols-3">{services_html}</div>
  </section>

  <section id="unggulan" class="border-y border-slate-200 bg-slate-50">
    <div class="mx-auto max-w-6xl px-6 py-20">
      <h2 class="text-2xl font-bold tracking-tight text-slate-900 md:text-3xl">{_esc(template.highlight_title)}</h2>
      <p class="mt-3 max-w-2xl text-sm leading-relaxed text-slate-600">{_esc(template.highlight_subtitle)}</p>
      <div class="mt-10 grid gap-6 md:grid-cols-3">{highlight_html}</div>
    </div>
  </section>

  <section class="mx-auto max-w-6xl px-6 py-20">
    <div class="grid gap-12 md:grid-cols-2 md:items-center">
      <div>
        <h2 class="text-2xl font-bold tracking-tight text-slate-900 md:text-3xl">Mengapa Memilih Kami</h2>
        <p class="mt-3 text-sm leading-relaxed text-slate-600">Hal-hal yang kami jaga pada setiap pesanan.</p>
      </div>
      <ul class="space-y-4">{trust_html}</ul>
    </div>
  </section>

  <section id="keunggulan" class="border-y border-slate-200 bg-slate-50">
    <div class="mx-auto grid max-w-6xl gap-12 px-6 py-20 md:grid-cols-2">
      <div>
        <h2 class="text-2xl font-bold tracking-tight text-slate-900 md:text-3xl">Yang Diperbaiki di Versi Baru{score_badge}</h2>
        <p class="mt-3 text-sm leading-relaxed text-slate-600">Perubahan berikut disusun dari hasil audit website lama.</p>
      </div>
      <ul class="space-y-4">{improvements_html}</ul>
    </div>
  </section>

  <section id="testimoni" class="mx-auto max-w-6xl px-6 py-20">
    <h2 class="text-2xl font-bold tracking-tight text-slate-900 md:text-3xl">Kata Pelanggan</h2>
    <p class="mt-3 text-sm text-slate-500">Contoh penempatan bukti sosial &mdash; ganti dengan testimoni asli sebelum publikasi.</p>
    <div class="mt-10 grid gap-6 md:grid-cols-2">{testimonials_html}</div>
  </section>

  <section id="kontak" class="border-t border-slate-200 bg-slate-50">
    <div class="mx-auto grid max-w-6xl gap-8 px-6 py-20 md:grid-cols-2">
      <div>
        <h2 class="text-2xl font-bold tracking-tight text-slate-900 md:text-3xl">Siap Membantu Anda</h2>
        <p class="mt-4 text-sm leading-relaxed text-slate-600">Kirim pertanyaan Anda dan tim kami akan membalas pada jam kerja.</p>
        <div class="mt-8">{primary_cta}</div>
      </div>
      {address_block}
    </div>
  </section>
</main>

<footer class="bg-slate-900 py-10 text-slate-300">
  <div class="mx-auto flex max-w-6xl flex-col gap-4 px-6 sm:flex-row sm:items-center sm:justify-between">
    <p class="text-sm">&copy; {year} {_esc(business)}. Seluruh hak cipta dilindungi.</p>
    <p class="text-xs text-slate-500">Konsep redesign &mdash; dibuat untuk keperluan presentasi.</p>
  </div>
</footer>

</body>
</html>
"""


def build_preview_html(index_html: str) -> str:
    """The dashboard preview reuses the same document, rendered in a sandboxed frame."""
    return index_html
