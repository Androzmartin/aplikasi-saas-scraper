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

    Two things carry the design:

    1. The business's own photographs, lifted from its current site. A concept
       built from the client's real material reads as *their* page restyled,
       which is what an agency actually pitches. Without images the page is
       coloured boxes, which is how the first version looked.
    2. A hero shape chosen per niche, so a dental clinic is not laid out like a
       warung. "overlay" sells atmosphere, "split" sells trust, "editorial"
       sells a catalogue.

    Photos are hotlinked from the client's own server: always current, nothing
    copied. If a host blocks hotlinking the image hides itself and the layout
    still holds - every image sits on a neutral block, never a broken icon.
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

    media = lead.get("images") or {}
    logo = media.get("logo")
    gallery: List[str] = [src for src in (media.get("gallery") or []) if src][:8]

    # A full-bleed hero stretches its image across the viewport, so a thumbnail
    # there looks blurry no matter how good the photo is. Prefer the widest one
    # we can identify for that slot; the gallery keeps its own order.
    from app.services.extractor import width_from_url

    hero_image = None
    if gallery:
        hero_image = max(gallery[:4], key=width_from_url) if template.hero_style == "overlay" else gallery[0]
    has_photos = bool(gallery)

    services = concept.get("ai_services") or template.services
    services = [
        (item["title"], item["body"]) if isinstance(item, dict) else item for item in services
    ]
    highlight_items = concept.get("ai_highlight_items") or template.highlight_items
    highlight_items = [
        (item["title"], item["body"]) if isinstance(item, dict) else item for item in highlight_items
    ]
    trust_points = concept.get("ai_trust_points") or template.trust_points

    # ------------------------------------------------------------- primitives
    def photo(src: str, alt: str, classes: str = "") -> str:
        """An image that fails quietly: a blocked hotlink leaves a neutral tile."""
        return (
            f'<img src="{_esc(src)}" alt="{_esc(alt)}" loading="lazy" decoding="async" '
            f'onerror="this.style.visibility=\'hidden\'" '
            f'class="h-full w-full object-cover {classes}">'
        )

    wa_icon = (
        '<svg class="h-[18px] w-[18px]" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">'
        '<path d="M12.04 2c-5.46 0-9.91 4.45-9.91 9.91 0 1.75.46 3.45 1.32 4.95L2 22l5.25-1.38a9.87 9.87 0 0 0 4.79 1.22h.01c5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.82 9.82 0 0 0 12.04 2Zm0 18.02h-.01a8.2 8.2 0 0 1-4.18-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.22 8.22 0 0 1 12.77-10.2 8.16 8.16 0 0 1 2.41 5.82c0 4.54-3.7 8.24-8.2 8.24Z"/>'
        "</svg>"
    )

    def cta(size: str = "base", light: bool = False) -> str:
        pad = "px-8 py-4 text-base" if size == "lg" else "px-5 py-2.5 text-sm"
        shell = (
            "bg-white text-slate-900 hover:bg-slate-100"
            if light
            else f"bg-{accent}-600 text-white hover:bg-{accent}-700"
        )
        if wa_href:
            return (
                f'<a href="{_esc(wa_href)}" target="_blank" rel="noopener" '
                f'class="inline-flex items-center justify-center gap-2.5 rounded-full {pad} '
                f'font-semibold {shell} shadow-lg shadow-slate-900/10 transition-all '
                f'hover:-translate-y-0.5 hover:shadow-xl focus:outline-none '
                f'focus-visible:ring-2 focus-visible:ring-{accent}-400 focus-visible:ring-offset-2">'
                f"{wa_icon}{_esc(template.cta_label)}</a>"
            )
        return (
            f'<a href="#kontak" class="inline-flex items-center justify-center rounded-full {pad} '
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

    brand_mark = (
        f'<span class="flex h-11 items-center"><img src="{_esc(logo)}" alt="{_esc(business)}" '
        f'onerror="this.style.display=\'none\'" class="h-9 w-auto object-contain"></span>'
        if logo
        else f'<span class="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900 '
        f'text-sm font-extrabold text-white">{_esc(initials)}</span>'
    )

    # ----------------------------------------------------------------- blocks
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
    ) or '<li class="px-4 py-3.5 text-sm text-slate-400">Lengkapi data kontak Anda di sini.</li>'

    contact_card = (
        f'<div class="rounded-3xl border border-slate-200 bg-white p-7 shadow-2xl shadow-slate-900/10">'
        f'<p class="text-xs font-bold uppercase tracking-[0.15em] text-slate-400">Hubungi langsung</p>'
        f'<ul class="mt-4 space-y-1">{contact_html}</ul>'
        f'<div class="mt-6 border-t border-slate-100 pt-5">{cta()}</div></div>'
    )

    # Service cards carry a photo when the site gave us enough of them.
    card_photos = gallery[1:4] if len(gallery) >= 4 else []
    services_html = ""
    for idx, (title, body) in enumerate(services):
        thumb = (
            f'<div class="mb-6 {template.gallery_aspect} overflow-hidden rounded-xl bg-slate-100">'
            f'{photo(card_photos[idx], title, "transition-transform duration-500 group-hover:scale-105")}</div>'
            if idx < len(card_photos)
            else f'<div class="mb-6 flex h-12 w-12 items-center justify-center rounded-xl '
            f'bg-{accent}-600 text-lg font-bold text-white shadow-lg">{idx + 1}</div>'
        )
        services_html += (
            f'<article class="group rounded-2xl border border-slate-200 bg-white p-6 '
            f'transition-all duration-300 hover:-translate-y-1 hover:border-{accent}-200 '
            f'hover:shadow-2xl hover:shadow-slate-900/5">{thumb}'
            f'<h3 class="text-lg font-bold tracking-tight text-slate-900">{_esc(title)}</h3>'
            f'<p class="mt-2.5 text-sm leading-relaxed text-slate-600">{_esc(body)}</p></article>'
        )

    highlight_html = "".join(
        f'<article class="rounded-2xl border border-white/10 bg-white/5 p-7 backdrop-blur '
        f'transition hover:border-white/20 hover:bg-white/10">'
        f'<div class="mb-5 h-1 w-12 rounded-full bg-{accent}-400"></div>'
        f'<h3 class="text-lg font-bold text-white">{_esc(title)}</h3>'
        f'<p class="mt-2.5 text-sm leading-relaxed text-slate-300">{_esc(body)}</p></article>'
        for title, body in highlight_items
    )

    trust_html = "".join(
        f'<li class="flex items-start gap-4 rounded-xl p-4 transition hover:bg-white">'
        f'<span class="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-{accent}-100">'
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

    facts = [
        ("Lokasi", _esc(area or "Jabodetabek")),
        ("Jam operasional", "Senin&ndash;Sabtu, 09.00&ndash;17.00"),
        ("Respons", "Dibalas pada jam kerja"),
    ]
    facts_html = "".join(
        f'<div class="px-6 py-6 sm:px-8">'
        f'<dt class="text-xs font-bold uppercase tracking-[0.15em] text-{accent}-600">{label}</dt>'
        f'<dd class="mt-2 text-lg font-semibold text-slate-900">{value}</dd></div>'
        for label, value in facts
    )

    # ------------------------------------------------------------------ heroes
    eyebrow_text = f"{template.hero_eyebrow}" + (f" &middot; {_esc(area)}" if area else "")

    if template.hero_style == "overlay" and hero_image:
        hero = f"""
  <section class="relative isolate min-h-[72vh] overflow-hidden">
    <div class="absolute inset-0 -z-10 bg-slate-900">
      {photo(hero_image, business, "scale-105")}
    </div>
    <div class="absolute inset-0 -z-10 bg-gradient-to-t from-slate-950 via-slate-950/80 to-slate-900/40"></div>

    <div class="mx-auto flex min-h-[72vh] max-w-6xl flex-col justify-end px-6 pb-20 pt-32 md:pb-28">
      <span class="inline-flex w-fit items-center rounded-full border border-white/20 bg-white/10 px-4 py-1.5 text-xs font-bold uppercase tracking-[0.15em] text-white backdrop-blur">
        {eyebrow_text}
      </span>
      <h1 class="mt-7 max-w-4xl text-5xl font-extrabold leading-[1.02] tracking-tight text-white md:text-7xl">
        {_esc(headline)}
      </h1>
      <p class="mt-7 max-w-xl text-lg leading-relaxed text-slate-200 md:text-xl">{_esc(subheadline)}</p>
      <div class="mt-10 flex flex-wrap items-center gap-5">
        {cta("lg")}
        <a href="#layanan" class="text-sm font-semibold text-white/90 hover:text-white">Lihat layanan &rarr;</a>
      </div>
    </div>
  </section>

  <section class="border-b border-slate-200 bg-white">
    <div class="mx-auto grid max-w-6xl gap-10 px-6 py-14 lg:grid-cols-3 lg:items-center">
      <dl class="grid divide-y divide-slate-200 sm:grid-cols-3 sm:divide-x sm:divide-y-0 lg:col-span-2">{facts_html}</dl>
      <div class="lg:col-span-1">{contact_card}</div>
    </div>
  </section>"""

    elif template.hero_style == "editorial" and len(gallery) >= 2:
        hero = f"""
  <section class="relative overflow-hidden bg-slate-50">
    <div class="pointer-events-none absolute -right-32 top-0 h-96 w-96 rounded-full bg-{accent}-200/40 blur-3xl"></div>
    <div class="relative mx-auto grid max-w-6xl gap-14 px-6 py-24 lg:grid-cols-2 lg:items-center lg:py-28">
      <div>
        <span class="inline-flex items-center rounded-full bg-white px-4 py-1.5 text-xs font-bold uppercase tracking-[0.15em] text-{accent}-700 shadow-sm ring-1 ring-{accent}-100">
          {eyebrow_text}
        </span>
        <h1 class="mt-7 text-5xl font-extrabold leading-[1.05] tracking-tight text-slate-900 md:text-6xl">
          {_esc(headline)}
        </h1>
        <p class="mt-7 max-w-lg text-lg leading-relaxed text-slate-600">{_esc(subheadline)}</p>
        <div class="mt-10 flex flex-wrap items-center gap-5">{cta("lg")}</div>
      </div>

      <div class="relative">
        <div class="{template.gallery_aspect} overflow-hidden rounded-3xl bg-slate-200 shadow-2xl shadow-slate-900/15">
          {photo(gallery[0], business)}
        </div>
        <div class="absolute -bottom-10 -left-10 hidden w-2/5 overflow-hidden rounded-2xl bg-slate-200 shadow-xl ring-8 ring-slate-50 sm:block">
          <div class="aspect-square">{photo(gallery[1], business)}</div>
        </div>
      </div>
    </div>

    <div class="relative border-t border-slate-200 bg-white/70">
      <dl class="mx-auto grid max-w-6xl divide-y divide-slate-200 sm:grid-cols-3 sm:divide-x sm:divide-y-0">{facts_html}</dl>
    </div>
  </section>

  <section class="bg-white">
    <div class="mx-auto max-w-6xl px-6 py-14">
      <div class="mx-auto max-w-md">{contact_card}</div>
    </div>
  </section>"""

    else:
        # "split", and the fallback whenever a site gave us no usable photo.
        visual = (
            f'<div class="relative">'
            f'<div class="absolute -right-6 -top-6 h-40 w-40 rounded-3xl bg-{accent}-200/60"></div>'
            f'<div class="relative {template.gallery_aspect} overflow-hidden rounded-3xl '
            f'bg-slate-200 shadow-2xl shadow-slate-900/15">{photo(hero_image, business)}</div></div>'
            if hero_image
            else contact_card
        )
        extra_contact = (
            f'<div class="mx-auto mt-14 max-w-md">{contact_card}</div>' if hero_image else ""
        )
        hero = f"""
  <section class="relative overflow-hidden bg-slate-50">
    <div class="pointer-events-none absolute -right-40 -top-40 h-[32rem] w-[32rem] rounded-full bg-{accent}-200/40 blur-3xl"></div>
    <div class="relative mx-auto grid max-w-6xl gap-14 px-6 py-24 lg:grid-cols-12 lg:items-center lg:py-32">
      <div class="lg:col-span-7">
        <span class="inline-flex items-center rounded-full bg-white px-4 py-1.5 text-xs font-bold uppercase tracking-[0.15em] text-{accent}-700 shadow-sm ring-1 ring-{accent}-100">
          {eyebrow_text}
        </span>
        <h1 class="mt-7 text-5xl font-extrabold leading-[1.05] tracking-tight text-slate-900 md:text-6xl lg:text-7xl">
          {_esc(headline)}
        </h1>
        <p class="mt-7 max-w-xl text-lg leading-relaxed text-slate-600 md:text-xl">{_esc(subheadline)}</p>
        <div class="mt-10 flex flex-wrap items-center gap-5">
          {cta("lg")}
          <a href="#layanan" class="text-sm font-semibold text-slate-700 hover:underline">Lihat layanan &rarr;</a>
        </div>
      </div>
      <div class="lg:col-span-5">{visual}</div>
    </div>
    {extra_contact}
    <div class="relative mt-14 border-t border-slate-200 bg-white/70">
      <dl class="mx-auto grid max-w-6xl divide-y divide-slate-200 sm:grid-cols-3 sm:divide-x sm:divide-y-0">{facts_html}</dl>
    </div>
  </section>"""

    # ----------------------------------------------------------------- gallery
    gallery_block = ""
    if template.show_gallery and len(gallery) >= 3:
        tiles = "".join(
            f'<figure class="group {template.gallery_aspect} overflow-hidden rounded-2xl bg-slate-200">'
            f'{photo(src, f"{business} - dokumentasi", "transition-transform duration-700 group-hover:scale-110")}'
            "</figure>"
            for src in gallery[:6]
        )
        gallery_block = f"""
  <section id="galeri" class="border-t border-slate-200 bg-white">
    <div class="mx-auto max-w-6xl px-6 py-24 md:py-32">
      <div class="max-w-2xl">
        {eyebrow(template.gallery_title)}
        <h2 class="text-3xl font-bold leading-tight tracking-tight text-slate-900 md:text-5xl">
          {_esc(template.gallery_title)}
        </h2>
        <p class="mt-5 text-lg leading-relaxed text-slate-600">{_esc(template.gallery_subtitle)}</p>
      </div>
      <div class="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{tiles}</div>
    </div>
  </section>"""

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

    address_block = (
        f'<div class="rounded-2xl bg-white/5 p-8 backdrop-blur ring-1 ring-white/10">'
        f'<p class="text-xs font-bold uppercase tracking-[0.15em] text-{accent}-300">Alamat</p>'
        f'<p class="mt-4 text-lg leading-relaxed text-white">{_esc(address)}</p>'
        f'<p class="mt-5 text-sm text-slate-400">Senin&ndash;Sabtu, 09.00&ndash;17.00 WIB</p></div>'
        if address
        else ""
    )

    gallery_nav = (
        f'<a href="#galeri" class="whitespace-nowrap text-sm font-medium text-slate-600 transition hover:text-slate-900">{_esc(template.gallery_title)}</a>'
        if gallery_block
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

<header class="sticky top-0 z-50 border-b border-slate-200/80 bg-white/85 backdrop-blur-xl">
  <div class="mx-auto flex max-w-6xl items-center justify-between gap-6 px-6 py-3.5">
    <a href="#" class="flex items-center gap-3">
      {brand_mark}
      <span class="text-[15px] font-bold tracking-tight">{_esc(business)}</span>
    </a>
    <nav class="hidden items-center gap-8 lg:flex">
      <a href="#layanan" class="whitespace-nowrap text-sm font-medium text-slate-600 transition hover:text-slate-900">Layanan</a>
      {gallery_nav}
      <a href="#unggulan" class="whitespace-nowrap text-sm font-medium text-slate-600 transition hover:text-slate-900">{_esc(template.highlight_title)}</a>
      <a href="#testimoni" class="whitespace-nowrap text-sm font-medium text-slate-600 transition hover:text-slate-900">Testimoni</a>
      <a href="#kontak" class="whitespace-nowrap text-sm font-medium text-slate-600 transition hover:text-slate-900">Kontak</a>
    </nav>
    <div class="shrink-0">{cta()}</div>
  </div>
</header>

<main>
{hero}

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
      <div class="mt-14 grid gap-6 md:grid-cols-3">{services_html}</div>
    </div>
  </section>
{gallery_block}
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
      <div class="mt-14 grid gap-6 md:grid-cols-3">{highlight_html}</div>
    </div>
  </section>

  <section id="alasan" class="bg-slate-50">
    <div class="mx-auto max-w-6xl px-6 py-24 md:py-32">
      <div class="grid gap-14 md:grid-cols-2 md:items-center">
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
      <div class="mt-14 grid gap-6 md:grid-cols-2">{testimonials_html}</div>
    </div>
  </section>

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
