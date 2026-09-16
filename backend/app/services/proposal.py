"""Generate a client-ready proposal document from a lead's audit and redesign.

Styling is inlined rather than pulled from a CDN. A proposal is often opened
offline, printed, or rendered to PDF on a machine with no network, and a
CDN-dependent document would come out blank in exactly those cases.
"""
from __future__ import annotations

import html as html_lib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.outreach import pitch_points
from app.services.regions import region_label
from app.services.templates import get_template

# Scope lines keyed by the audit findings they answer.
_SCOPE_BY_ISSUE = {
    "no_viewport": "Penyusunan ulang layout agar tampil benar di ponsel",
    "no_responsive_css": "Implementasi grid responsif untuk semua ukuran layar",
    "fixed_width_layout": "Penghapusan layout lebar tetap yang memaksa scroll menyamping",
    "no_cta": "Perancangan call to action di hero dan penutup halaman",
    "no_action_link": "Pemasangan tombol kontak langsung (WhatsApp, telepon, email)",
    "no_whatsapp": "Integrasi tombol WhatsApp satu klik di setiap layar",
    "no_address": "Penambahan blok lokasi dan jam operasional",
    "thin_sections": "Penyusunan struktur halaman lengkap dari hero sampai penutup",
    "legacy_markup": "Peremajaan tampilan menggantikan markup lama",
    "no_modern_css": "Penerapan sistem visual dan tipografi yang konsisten",
    "no_images": "Penyiapan area showcase untuk foto produk dan suasana",
    "thin_content": "Penulisan ulang naskah yang menjelaskan nilai jual",
    "no_h1": "Penataan hirarki judul halaman",
    "no_navigation": "Perancangan menu navigasi yang jelas",
    "images_missing_alt": "Pelengkapan teks alternatif gambar untuk SEO dan aksesibilitas",
}

_BASELINE_SCOPE = [
    "Perancangan ulang halaman utama (satu halaman, mobile-first)",
    "Penulisan naskah ringkas berbahasa Indonesia",
    "Penyerahan berkas siap pakai beserta panduan singkat",
]

_DELIVERABLES = [
    ("Konsep halaman baru", "Satu halaman penuh siap ditinjau di browser."),
    ("Berkas siap pakai", "File index.html mandiri yang bisa langsung diunggah."),
    ("Ringkasan audit", "Daftar temuan pada website lama beserta dampaknya."),
    ("Panduan singkat", "Langkah menayangkan halaman baru pada domain Anda."),
]

_TIMELINE = [
    ("Hari 1–2", "Peninjauan bahan, penyusunan struktur dan naskah."),
    ("Hari 3–5", "Perancangan visual dan penyusunan halaman."),
    ("Hari 6–7", "Revisi sesuai masukan dan penyerahan berkas."),
]


def _esc(value: Optional[Any]) -> str:
    return html_lib.escape(str(value), quote=True) if value is not None else ""


def build_scope(audit: Optional[Dict[str, Any]]) -> List[str]:
    """Derive the work items from the audit so scope matches the findings."""
    scope: List[str] = []
    for issue in (audit or {}).get("issues", []):
        line = _SCOPE_BY_ISSUE.get(issue.get("code"))
        if line and line not in scope:
            scope.append(line)
    for line in _BASELINE_SCOPE:
        if line not in scope:
            scope.append(line)
    return scope[:8]


def _format_date(value: Optional[datetime] = None) -> str:
    months = [
        "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember",
    ]
    moment = value or datetime.now(timezone.utc)
    return f"{moment.day} {months[moment.month - 1]} {moment.year}"


def build_proposal_html(
    lead: Dict[str, Any],
    audit: Optional[Dict[str, Any]] = None,
    redesign: Optional[Dict[str, Any]] = None,
    tenant: Optional[Dict[str, Any]] = None,
    author: Optional[Dict[str, Any]] = None,
    screenshot_data_uri: Optional[str] = None,
) -> str:
    """Render the full proposal as a single self-contained HTML document."""
    business = lead.get("business_name") or "Calon Klien"
    agency = (tenant or {}).get("company_name") or "Agensi Kami"
    author_name = (author or {}).get("name") or ""
    author_email = (author or {}).get("email") or ""
    area = region_label(lead.get("region"))
    score = (audit or {}).get("score", lead.get("audit_score"))
    grade = (audit or {}).get("grade")
    template = get_template((redesign or {}).get("template_key"))

    findings = pitch_points(audit)
    scope = build_scope(audit)
    issues = (audit or {}).get("issues", [])[:6]

    score_block = (
        f'<div class="score"><span class="score-value">{_esc(score)}</span>'
        f'<span class="score-max">/100</span>'
        + (f'<span class="grade">Grade {_esc(grade)}</span>' if grade else "")
        + "</div>"
        if isinstance(score, int)
        else '<p class="muted">Audit belum dijalankan untuk website ini.</p>'
    )

    findings_html = "".join(
        f"<li><strong>{_esc(issue.get('title'))}</strong>"
        f"<span>{_esc(issue.get('detail'))}</span></li>"
        for issue in issues
    ) or "<li><strong>Tidak ada temuan berat</strong><span>Website sudah dalam kondisi baik.</span></li>"

    scope_html = "".join(f"<li>{_esc(item)}</li>" for item in scope)
    deliverables_html = "".join(
        f"<div class='card'><h4>{_esc(title)}</h4><p>{_esc(body)}</p></div>"
        for title, body in _DELIVERABLES
    )
    timeline_html = "".join(
        f"<tr><td class='phase'>{_esc(phase)}</td><td>{_esc(detail)}</td></tr>"
        for phase, detail in _TIMELINE
    )

    summary_points = findings or ["Tampilan dan alur kontak masih bisa dioptimalkan"]
    summary_html = "".join(f"<li>{_esc(point[0].upper() + point[1:])}</li>" for point in summary_points)

    before_block = (
        f'<figure class="shot"><img src="{screenshot_data_uri}" alt="Tampilan website saat ini">'
        f"<figcaption>Tampilan saat ini</figcaption></figure>"
        if screenshot_data_uri
        else '<div class="shot placeholder"><span>Screenshot belum diambil</span></div>'
    )

    concept_block = (
        f'<div class="concept"><p class="eyebrow">Konsep halaman baru</p>'
        f'<h3>{_esc(redesign.get("headline"))}</h3>'
        f'<p class="lead">{_esc(redesign.get("subheadline"))}</p>'
        f'<p class="muted">Pendekatan: {_esc(template.label)}</p></div>'
        if redesign
        else '<div class="concept"><p class="muted">Konsep redesign belum dibuat.</p></div>'
    )

    contact_rows = "".join(
        f"<tr><th>{label}</th><td>{_esc(value)}</td></tr>"
        for label, value in (
            ("Website", lead.get("website_url")),
            ("WhatsApp", lead.get("whatsapp_number")),
            ("Email", lead.get("email")),
            ("Alamat", lead.get("address")),
        )
        if value
    )

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Proposal Redesign Website &mdash; {_esc(business)}</title>
<style>
  /* Self-contained on purpose: proposals get opened offline and printed. */
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: #f1f5f9; color: #0f172a;
    font-family: -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 14px; line-height: 1.6;
  }}
  .page {{
    width: 210mm; min-height: 297mm; margin: 16px auto; padding: 18mm 16mm;
    background: #fff; box-shadow: 0 2px 12px rgba(15,23,42,.08);
  }}
  h1 {{ font-size: 26px; margin: 0 0 6px; letter-spacing: -.02em; }}
  h2 {{ font-size: 16px; margin: 28px 0 10px; padding-bottom: 6px;
        border-bottom: 2px solid #0f172a; text-transform: uppercase; letter-spacing: .08em; }}
  h3 {{ font-size: 18px; margin: 0 0 6px; }}
  h4 {{ font-size: 13px; margin: 0 0 4px; }}
  p {{ margin: 0 0 10px; }}
  .muted {{ color: #64748b; font-size: 13px; }}
  .eyebrow {{ font-size: 11px; text-transform: uppercase; letter-spacing: .12em;
              color: #475569; margin: 0 0 4px; }}
  .lead {{ font-size: 15px; color: #334155; }}
  header.cover {{ border-bottom: 3px solid #0f172a; padding-bottom: 18px; margin-bottom: 8px; }}
  .meta {{ display: flex; justify-content: space-between; gap: 16px;
           font-size: 12px; color: #475569; margin-top: 12px; }}
  .score {{ display: flex; align-items: baseline; gap: 6px; margin: 8px 0 14px; }}
  .score-value {{ font-size: 40px; font-weight: 700; line-height: 1; }}
  .score-max {{ color: #94a3b8; }}
  .grade {{ margin-left: 10px; background: #0f172a; color: #fff;
            padding: 3px 10px; border-radius: 999px; font-size: 11px; font-weight: 600; }}
  ul.findings {{ list-style: none; padding: 0; margin: 0; }}
  ul.findings li {{ padding: 9px 0; border-bottom: 1px solid #e2e8f0; }}
  ul.findings strong {{ display: block; font-size: 13px; }}
  ul.findings span {{ display: block; color: #64748b; font-size: 12px; }}
  ul.plain {{ margin: 0; padding-left: 18px; }}
  ul.plain li {{ margin-bottom: 5px; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
  .card {{ border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; }}
  .card p {{ margin: 0; color: #64748b; font-size: 12px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  table th {{ text-align: left; color: #64748b; font-weight: 500;
              padding: 7px 10px 7px 0; width: 110px; vertical-align: top; }}
  table td {{ padding: 7px 0; border-bottom: 1px solid #f1f5f9; }}
  td.phase {{ font-weight: 600; width: 110px; }}
  .before-after {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; align-items: start; }}
  .shot img {{ width: 100%; border: 1px solid #e2e8f0; border-radius: 6px; display: block; }}
  .shot figcaption {{ font-size: 11px; color: #64748b; margin-top: 5px; text-align: center; }}
  .shot.placeholder {{ border: 1px dashed #cbd5e1; border-radius: 6px; padding: 40px 12px;
                       text-align: center; color: #94a3b8; font-size: 12px; }}
  .concept {{ border-left: 3px solid #0f172a; padding-left: 14px; }}
  .callout {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px;
              padding: 14px; margin-top: 10px; }}
  footer {{ margin-top: 30px; padding-top: 14px; border-top: 1px solid #e2e8f0;
            font-size: 11px; color: #94a3b8; display: flex; justify-content: space-between; }}
  @page {{ size: A4; margin: 14mm; }}
  @media print {{
    body {{ background: #fff; }}
    .page {{ width: auto; min-height: 0; margin: 0; padding: 0; box-shadow: none; }}
    h2 {{ page-break-after: avoid; }}
    .card, .shot, ul.findings li {{ page-break-inside: avoid; }}
  }}
</style>
</head>
<body>
<div class="page">

  <header class="cover">
    <p class="eyebrow">Proposal Redesign Website</p>
    <h1>{_esc(business)}</h1>
    <p class="muted">{_esc(area)}</p>
    <div class="meta">
      <span>Disiapkan oleh <strong>{_esc(agency)}</strong>{_esc(f" · {author_name}" if author_name else "")}</span>
      <span>{_format_date()}</span>
    </div>
  </header>

  <h2>Ringkasan</h2>
  <p>Dokumen ini merangkum hasil pemeriksaan website <strong>{_esc(business)}</strong>
     dan mengusulkan konsep halaman baru yang lebih mudah dipakai calon pelanggan,
     terutama dari ponsel.</p>
  {score_block}
  <p>Hal yang paling menahan konversi saat ini:</p>
  <ul class="plain">{summary_html}</ul>

  <h2>Temuan Audit</h2>
  <ul class="findings">{findings_html}</ul>

  <h2>Kondisi Sekarang &amp; Usulan</h2>
  <div class="before-after">
    {before_block}
    {concept_block}
  </div>

  <h2>Lingkup Pekerjaan</h2>
  <ul class="plain">{scope_html}</ul>

  <h2>Yang Anda Terima</h2>
  <div class="grid">{deliverables_html}</div>

  <h2>Perkiraan Waktu</h2>
  <table>{timeline_html}</table>

  <h2>Investasi</h2>
  <div class="callout">
    <p class="muted">Nilai investasi disesuaikan dengan lingkup akhir yang disepakati.
       Silakan lengkapi bagian ini sebelum dokumen dikirim ke klien.</p>
    <p><strong>Rp ____________</strong> &mdash; termasuk satu putaran revisi.</p>
  </div>

  <h2>Langkah Berikutnya</h2>
  <ol class="plain">
    <li>Konfirmasi lingkup pekerjaan pada dokumen ini.</li>
    <li>Penyerahan bahan (logo, foto, daftar produk/layanan).</li>
    <li>Pengerjaan dimulai sesuai jadwal di atas.</li>
  </ol>

  <h2>Data Kontak yang Kami Catat</h2>
  <table>{contact_rows or "<tr><td class='muted'>Belum ada data kontak publik.</td></tr>"}</table>

  <footer>
    <span>{_esc(agency)}{_esc(f" · {author_email}" if author_email else "")}</span>
    <span>Proposal untuk {_esc(business)}</span>
  </footer>

</div>
</body>
</html>
"""
