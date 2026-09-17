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
    """Render the downloadable single-file landing page (Tailwind Play CDN).

    Layout notes, since this page is what the agency shows a prospect:
    - One rhythm for every section (py-24 / md:py-32) so the page breathes
      evenly instead of some blocks feeling cramped and others loose.
    - Surfaces alternate white -> tinted -> white -> dark, which gives each
      section its own footing and stops the page reading as one long slab.
    - A single type scale: hero 5xl->7xl, section heads 3xl->5xl, body base.
      Each section leads with a small accent eyebrow so it is scannable.
    - The accent hue comes from the niche template, written as literal class
      names so the Play CDN picks them up when it scans the DOM.
    """
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

    services = concept.get("ai_services") or template.services
    services = [
        (item["title"], item["body"]) if isinstance(item, dict) else item for item in services
    ]
    highlight_items = concept.get("ai_highlight_items") or template.highlight_items
    highlight_items = [
        (item["title"], item["body"]) if isinstance(item, dict) else item for item in highlight_items
    ]
    trust_points = concept.get("ai_trust_points") or template.trust_points

    # ---------------------------------------------------------------- buttons
    wa_icon = (
        '<svg class="h-[18px] w-[18px]" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">'
        '<path d="M12.04 2c-5.46 0-9.91 4.45-9.91 9.91 0 1.75.46 3.45 1.32 4.95L2 22l5.25-1.38a9.87 9.87 0 0 0 4.79 1.22h.01c5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.82 9.82 0 0 0 12.04 2Zm0 18.02h-.01a8.2 8.2 0 0 1-4.18-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.22 8.22 0 0 1 12.77-10.2 8.16 8.16 0 0 1 2.41 5.82c0 4.54-3.7 8.24-8.2 8.24Z"/>'
        "</svg>"
    )

    def cta(size: str = "base", light: bool = False) -> str:
        pad = "px-7 py-4 text-base" if size == "lg" else "px-5 py-2.5 text-sm"
        if light:
            shell = "bg-white text-slate-900 hover:bg-slate-100"
        else:
            shell = f"bg-{accent}-600 text-white hover:bg-{accent}-700"
        if wa_href:
            return (
                f'<a href="{_esc(wa_href)}" target="_blank" rel="noopener" '
                f'class="group inline-flex items-center justify-center gap-2.5 rounded-xl {pad} '
                f'font-semibold {shell} shadow-lg shadow-{accent}-600/20 transition-all '
                f'hover:-translate-y-0.5 hover:shadow-xl focus:outline-none '
                f'focus-visible:ring-2 focus-visible:ring-{accent}-400 focus-visible:ring-offset-2">'
                f"{wa_icon}{_esc(template.cta_label)}</a>"
            )
        return (
            f'<a href="#kontak" class="inline-flex items-center justify-center rounded-xl {pad} '
            f'font-semibold {shell} shadow-lg transition-all hover:-translate-y-0.5">'
            f"{_esc(template.cta_label)}</a>"
        )

    def eyebrow(text: str, on_dark: bool = False) -> str:
        tone = f"text-{accent}-300" if on_dark else f"text-{accent}-600"
        return (
            f'<p class="mb-4 flex items-center gap-2.5 text-xs font-bold uppercase '
            f'tracking-[0.18em] {tone}">'
            f'<span class="h-px w-8 bg-current opacity-60"></span>{_esc(text)}</p>'
        )

    # ---------------------------------------------------------------- blocks
    contact_rows = []
    if whatsapp:
        contact_rows.append(("WhatsApp", whatsapp, wa_href or "#"))
    if phone:
        contact_rows.append(("Telepon", phone, f"tel:{re.sub(r'[^0-9+]', '', phone)}"))
    if email:
        contact_rows.append(("Email", email, f"mailto:{email}"))

    contact_html = "".join(
        f'<li><a href="{_esc(href)}" class="group flex items-center justify-between gap-4 '
        f'rounded-xl px-4 py-3.5 transition hover:bg-{accent}-50">'
        f'<span class="text-sm font-medium text-slate-500">{_esc(label)}</span>'
        f'<span class="text-sm font-bold text-slate-900 group-hover:text-{accent}-700">'
        f"{_esc(value)}</span></a></li>"
        for label, value, href in contact_rows
    ) or (
        '<li class="px-4 py-3.5 text-sm text-slate-400">Lengkapi data kontak Anda di sini.</li>'
    )

    services_html = "".join(
        f'<article class="group relative overflow-hidden rounded-2xl border border-slate-200 '
        f'bg-white p-8 transition-all duration-300 hover:-translate-y-1 hover:border-{accent}-200 '
        f'hover:shadow-2xl hover:shadow-slate-900/5">'
        f'<div class="absolute -right-6 -top-6 h-24 w-24 rounded-full bg-{accent}-50 '
        f'transition-transform duration-500 group-hover:scale-150"></div>'
        f'<div class="relative">'
        f'<div class="mb-6 flex h-12 w-12 items-center justify-center rounded-xl '
        f'bg-{accent}-600 text-lg font-bold text-white shadow-lg shadow-{accent}-600/25">'
        f"{idx + 1}</div>"
        f'<h3 class="text-xl font-bold tracking-tight text-slate-900">{_esc(title)}</h3>'
        f'<p class="mt-3 leading-relaxed text-slate-600">{_esc(body)}</p>'
        f"</div></article>"
        for idx, (title, body) in enumerate(services)
    )

    highlight_html = "".join(
        f'<article class="rounded-2xl border border-white/10 bg-white/5 p-8 backdrop-blur '
        f'transition hover:border-white/20 hover:bg-white/10">'
        f'<div class="mb-5 h-1 w-12 rounded-full bg-{accent}-400"></div>'
        f'<h3 class="text-xl font-bold text-white">{_esc(title)}</h3>'
        f'<p class="mt-3 leading-relaxed text-slate-300">{_esc(body)}</p></article>'
        for title, body in highlight_items
    )

    trust_html = "".join(
        f'<li class="flex items-start gap-4 rounded-xl p-4 transition hover:bg-white">'
        f'<span class="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg '
        f'bg-{accent}-100">'
        f'<svg class="h-4 w-4 text-{accent}-700" fill="none" viewBox="0 0 24 24" '
        'stroke="currentColor" stroke-width="3"><path stroke-linecap="round" '
        'stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg></span>'
        f'<span class="text-[15px] font-medium leading-relaxed text-slate-700">{_esc(point)}</span></li>'
        for point in trust_points
    )

    improvements_html = "".join(
        f'<li class="flex items-start gap-3">'
        f'<span class="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-{accent}-500"></span>'
        f'<span class="leading-relaxed text-slate-600">{_esc(item)}</span></li>'
        for item in improvements
    )

    testimonials_html = "".join(
        f'<figure class="relative rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">'
        f'<span class="absolute right-7 top-5 font-serif text-6xl leading-none '
        f'text-{accent}-100" aria-hidden="true">&rdquo;</span>'
        f'<blockquote class="relative text-lg leading-relaxed text-slate-700">'
        f"&ldquo;{_esc(quote)}&rdquo;</blockquote>"
        f'<figcaption class="mt-6 flex items-center gap-3 border-t border-slate-100 pt-5">'
        f'<span class="flex h-10 w-10 items-center justify-center rounded-full '
        f'bg-{accent}-100 text-sm font-bold text-{accent}-700">P</span>'
        f'<span class="text-sm"><span class="block font-semibold text-slate-900">Pelanggan</span>'
        f'<span class="block text-slate-500">{_esc(area or "Jakarta")}</span></span>'
        "</figcaption></figure>"
        for quote in template.testimonials
    )

    # Three quick facts give the eye somewhere to land between hero and body.
    facts = [
        ("Lokasi", area or "Jabodetabek"),
        ("Jam operasional", "Senin&ndash;Sabtu, 09.00&ndash;17.00"),
        ("Respons", "Dibalas pada jam kerja"),
    ]
    facts_html = "".join(
        f'<div class="px-6 py-6 sm:px-8">'
        f'<dt class="text-xs font-bold uppercase tracking-[0.15em] text-{accent}-600">{label}</dt>'
        f'<dd class="mt-2 text-lg font-semibold text-slate-900">{value}</dd></div>'
        for label, value in facts
    )

    address_block = (
        f'<div class="rounded-2xl bg-white/5 p-8 backdrop-blur ring-1 ring-white/10">'
        f'<p class="text-xs font-bold uppercase tracking-[0.15em] text-{accent}-300">Alamat</p>'
        f'<p class="mt-4 text-lg leading-relaxed text-white">{_esc(address)}</p>'
        f'<p class="mt-5 text-sm text-slate-400">Senin&ndash;Sabtu, 09.00&ndash;17.00 WIB</p></div>'
        if address
        else ""
    )

    # On its own line: crammed beside a 4xl heading it read as a stray label.
    score_badge = ""
    if audit and isinstance(audit.get("score"), int):
        score_badge = (
            f'<p class="mt-5"><span class="inline-flex items-center gap-2 rounded-full '
            f'bg-slate-100 px-4 py-2 text-xs font-semibold text-slate-600">'
            f'<span class="h-1.5 w-1.5 rounded-full bg-{accent}-500"></span>'
            f'Skor website lama: {audit["score"]}/100</span></p>'
        )

    improvements_block = (
        f"""
  <section class="border-t border-slate-200 bg-white">
    <div class="mx-auto max-w-6xl px-6 py-24 md:py-32">
      <div class="grid gap-14 md:grid-cols-5 md:items-start">
        <div class="md:col-span-2">
          {eyebrow("Perubahan")}
          <h2 class="text-3xl font-bold leading-tight tracking-tight text-slate-900 md:text-4xl">
            Yang diperbaiki di versi baru
          </h2>
          <p class="mt-5 leading-relaxed text-slate-600">
            Disusun dari hasil audit website lama, bukan daftar umum.
          </p>{score_badge}
        </div>
        <ul class="space-y-4 md:col-span-3">{improvements_html}</ul>
      </div>
    </div>
  </section>"""
        if improvements_html
        else ""
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
        fontFamily: {{ sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'] }}
      }}
    }}
  }}
</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  html {{ scroll-behavior: smooth; }}
  body {{ -webkit-font-smoothing: antialiased; }}
</style>
</head>
<body class="bg-white font-sans text-slate-900">

<header class="sticky top-0 z-50 border-b border-slate-200/80 bg-white/80 backdrop-blur-xl">
  <div class="mx-auto flex max-w-6xl items-center justify-between gap-6 px-6 py-4">
    <a href="#" class="flex items-center gap-3">
      <span class="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900 text-sm font-extrabold text-white">{_esc(initials)}</span>
      <span class="text-[15px] font-bold tracking-tight">{_esc(business)}</span>
    </a>
    <nav class="hidden items-center gap-9 lg:flex">
      <a href="#layanan" class="text-sm font-medium text-slate-600 transition hover:text-slate-900">Layanan</a>
      <a href="#unggulan" class="text-sm font-medium text-slate-600 transition hover:text-slate-900">{_esc(template.highlight_title)}</a>
      <a href="#alasan" class="text-sm font-medium text-slate-600 transition hover:text-slate-900">Keunggulan</a>
      <a href="#testimoni" class="text-sm font-medium text-slate-600 transition hover:text-slate-900">Testimoni</a>
      <a href="#kontak" class="text-sm font-medium text-slate-600 transition hover:text-slate-900">Kontak</a>
    </nav>
    <div class="shrink-0">{cta()}</div>
  </div>
</header>

<main>

  <!-- HERO -->
  <section class="relative overflow-hidden bg-slate-50">
    <div class="pointer-events-none absolute -right-40 -top-40 h-[32rem] w-[32rem] rounded-full bg-{accent}-200/40 blur-3xl"></div>
    <div class="pointer-events-none absolute -bottom-32 left-1/4 h-96 w-96 rounded-full bg-{accent}-100/50 blur-3xl"></div>

    <div class="relative mx-auto grid max-w-6xl gap-16 px-6 py-24 lg:grid-cols-12 lg:items-center lg:py-32">
      <div class="lg:col-span-7">
        <span class="inline-flex items-center gap-2 rounded-full bg-white px-4 py-1.5 text-xs font-bold uppercase tracking-[0.15em] text-{accent}-700 shadow-sm ring-1 ring-{accent}-100">
          {_esc(template.hero_eyebrow)}{f' &middot; {_esc(area)}' if area else ''}
        </span>
        <h1 class="mt-7 text-5xl font-extrabold leading-[1.05] tracking-tight text-slate-900 md:text-6xl lg:text-7xl">
          {_esc(headline)}
        </h1>
        <p class="mt-7 max-w-xl text-lg leading-relaxed text-slate-600 md:text-xl">{_esc(subheadline)}</p>
        <div class="mt-10 flex flex-wrap items-center gap-5">
          {cta("lg")}
          <a href="#layanan" class="group inline-flex items-center gap-2 text-sm font-semibold text-slate-700">
            Lihat layanan
            <span class="transition-transform group-hover:translate-x-1">&rarr;</span>
          </a>
        </div>
      </div>

      <div class="lg:col-span-5">
        <div class="rounded-3xl border border-slate-200 bg-white p-8 shadow-2xl shadow-slate-900/10">
          <p class="text-xs font-bold uppercase tracking-[0.15em] text-slate-400">Hubungi langsung</p>
          <ul class="mt-5 space-y-1">{contact_html}</ul>
          <div class="mt-7 border-t border-slate-100 pt-6">{cta()}</div>
        </div>
      </div>
    </div>

    <!-- Quick facts strip -->
    <div class="relative border-t border-slate-200 bg-white/70">
      <dl class="mx-auto grid max-w-6xl divide-y divide-slate-200 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        {facts_html}
      </dl>
    </div>
  </section>

  <!-- LAYANAN -->
  <section id="layanan" class="bg-white">
    <div class="mx-auto max-w-6xl px-6 py-24 md:py-32">
      <div class="max-w-2xl">
        {eyebrow("Layanan")}
        <h2 class="text-3xl font-bold leading-tight tracking-tight text-slate-900 md:text-5xl">
          Yang kami tawarkan
        </h2>
        <p class="mt-5 text-lg leading-relaxed text-slate-600">
          Ringkasan layanan utama yang paling sering dicari pelanggan {_esc(business)}.
        </p>
      </div>
      <div class="mt-16 grid gap-7 md:grid-cols-3">{services_html}</div>
    </div>
  </section>

  <!-- HIGHLIGHT (dark band, niche-specific) -->
  <section id="unggulan" class="relative overflow-hidden bg-slate-900">
    <div class="pointer-events-none absolute -left-40 top-0 h-96 w-96 rounded-full bg-{accent}-500/20 blur-3xl"></div>
    <div class="relative mx-auto max-w-6xl px-6 py-24 md:py-32">
      <div class="max-w-2xl">
        {eyebrow(template.highlight_title, on_dark=True)}
        <h2 class="text-3xl font-bold leading-tight tracking-tight text-white md:text-5xl">
          {_esc(template.highlight_title)}
        </h2>
        <p class="mt-5 text-lg leading-relaxed text-slate-300">{_esc(template.highlight_subtitle)}</p>
      </div>
      <div class="mt-16 grid gap-7 md:grid-cols-3">{highlight_html}</div>
    </div>
  </section>

  <!-- ALASAN MEMILIH -->
  <section id="alasan" class="bg-slate-50">
    <div class="mx-auto max-w-6xl px-6 py-24 md:py-32">
      <div class="grid gap-16 md:grid-cols-2 md:items-center">
        <div>
          {eyebrow("Alasan memilih")}
          <h2 class="text-3xl font-bold leading-tight tracking-tight text-slate-900 md:text-5xl">
            Mengapa memilih kami
          </h2>
          <p class="mt-5 text-lg leading-relaxed text-slate-600">
            Hal-hal yang kami jaga pada setiap pesanan.
          </p>
          <div class="mt-9">{cta()}</div>
        </div>
        <ul class="space-y-2">{trust_html}</ul>
      </div>
    </div>
  </section>
{improvements_block}
  <!-- TESTIMONI -->
  <!-- Tinted, because the section above it is white: two white bands in a row
       merge into one oversized void with no visual separation. -->
  <section id="testimoni" class="border-t border-slate-200 bg-slate-50">
    <div class="mx-auto max-w-6xl px-6 py-24 md:py-32">
      <div class="max-w-2xl">
        {eyebrow("Testimoni")}
        <h2 class="text-3xl font-bold leading-tight tracking-tight text-slate-900 md:text-5xl">
          Kata pelanggan
        </h2>
        <p class="mt-4 text-sm text-slate-500">
          Contoh penempatan bukti sosial &mdash; ganti dengan testimoni asli sebelum publikasi.
        </p>
      </div>
      <div class="mt-16 grid gap-7 md:grid-cols-2">{testimonials_html}</div>
    </div>
  </section>

  <!-- KONTAK / CTA PENUTUP -->
  <section id="kontak" class="relative overflow-hidden bg-slate-900">
    <div class="pointer-events-none absolute right-0 top-0 h-[28rem] w-[28rem] rounded-full bg-{accent}-500/20 blur-3xl"></div>
    <div class="relative mx-auto grid max-w-6xl gap-14 px-6 py-24 md:grid-cols-2 md:items-center md:py-32">
      <div>
        {eyebrow("Kontak", on_dark=True)}
        <h2 class="text-3xl font-bold leading-tight tracking-tight text-white md:text-5xl">
          Siap membantu Anda
        </h2>
        <p class="mt-5 text-lg leading-relaxed text-slate-300">
          Kirim pertanyaan Anda dan tim kami akan membalas pada jam kerja.
        </p>
        <div class="mt-10">{cta("lg", light=True)}</div>
      </div>
      {address_block}
    </div>
  </section>

</main>

<footer class="bg-slate-950 py-10">
  <div class="mx-auto flex max-w-6xl flex-col gap-3 px-6 sm:flex-row sm:items-center sm:justify-between">
    <p class="text-sm text-slate-400">&copy; {year} {_esc(business)}. Seluruh hak cipta dilindungi.</p>
    <p class="text-xs text-slate-600">Konsep redesign &mdash; dibuat untuk keperluan presentasi.</p>
  </div>
</footer>

</body>
</html>
"""


def build_preview_html(index_html: str) -> str:
    """The dashboard preview reuses the same document, rendered in a sandboxed frame."""
    return index_html
