"""Generate outreach drafts (WhatsApp / email) from a lead's audit findings.

No third-party messaging provider is involved: the app produces the text plus a
wa.me or mailto deep link, and the salesperson sends it from their own account.
That keeps the MVP clear of WhatsApp Business API terms while still removing the
blank-page problem, which is the part that actually slows a sales team down.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from app.services.regions import region_label

CHANNELS = ("whatsapp", "email")
TONES = ("formal", "ramah")

# Audit issue codes rendered as a plain-language selling point.
_ISSUE_PITCH = {
    "no_viewport": "tampilannya belum menyesuaikan layar HP",
    "no_responsive_css": "layout-nya belum responsif di HP",
    "fixed_width_layout": "halaman memaksa scroll menyamping di HP",
    "no_cta": "belum ada ajakan jelas untuk menghubungi",
    "no_action_link": "nomor kontak belum bisa diklik langsung",
    "no_whatsapp": "belum ada tombol WhatsApp",
    "no_email": "email kontak belum tercantum",
    "no_address": "alamat belum ditampilkan",
    "thin_sections": "bagian penting seperti layanan dan kontak belum lengkap",
    "no_h1": "judul utama halaman belum tegas",
    "legacy_markup": "tampilannya masih bergaya lama",
    "no_modern_css": "tampilannya belum mengikuti standar sekarang",
    "no_images": "belum ada foto produk atau suasana",
    "thin_content": "penjelasan tentang bisnisnya masih terlalu singkat",
    "images_missing_alt": "gambar belum punya teks alternatif",
    "no_navigation": "menu navigasinya belum jelas",
    "multiple_h1": "struktur judulnya belum rapi",
    "no_semantic_sections": "struktur halamannya belum tertata",
    "no_button_element": "tombol ajakan belum menonjol",
}

MAX_POINTS = 3


@dataclass
class OutreachDraft:
    channel: str
    tone: str
    subject: Optional[str]
    message: str
    send_url: Optional[str]
    recipient: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "channel": self.channel,
            "tone": self.tone,
            "subject": self.subject,
            "message": self.message,
            "send_url": self.send_url,
            "recipient": self.recipient,
        }


def _greeting(lead: Dict[str, Any], tone: str) -> str:
    person = (lead.get("contact_person") or "").strip()
    if person:
        return f"Halo Bapak/Ibu {person}," if tone == "formal" else f"Halo Kak {person},"
    business = lead.get("business_name") or "Bapak/Ibu"
    return f"Selamat siang, {business}." if tone == "formal" else f"Halo {business}!"


def pitch_points(audit: Optional[Dict[str, Any]]) -> List[str]:
    """Turn the audit's highest-severity findings into plain-language points."""
    if not audit:
        return []
    ranking = {"high": 0, "medium": 1, "low": 2}
    issues = sorted(
        audit.get("issues", []), key=lambda issue: ranking.get(issue.get("severity"), 3)
    )
    points: List[str] = []
    for issue in issues:
        text = _ISSUE_PITCH.get(issue.get("code"))
        if text and text not in points:
            points.append(text)
        if len(points) >= MAX_POINTS:
            break
    return points


def _wa_url(number: str, message: str) -> Optional[str]:
    digits = re.sub(r"\D", "", number or "")
    if not digits:
        return None
    return f"https://wa.me/{digits}?text={quote(message)}"


def _mailto_url(email: str, subject: str, body: str) -> Optional[str]:
    if not email:
        return None
    return f"mailto:{email}?subject={quote(subject)}&body={quote(body)}"


def build_draft(
    lead: Dict[str, Any],
    audit: Optional[Dict[str, Any]] = None,
    channel: str = "whatsapp",
    tone: str = "formal",
    sender_name: Optional[str] = None,
    company_name: Optional[str] = None,
) -> OutreachDraft:
    """Compose a ready-to-send outreach draft for one lead."""
    if channel not in CHANNELS:
        raise ValueError(f"Channel tidak dikenal: {channel}")
    if tone not in TONES:
        raise ValueError(f"Tone tidak dikenal: {tone}")

    business = lead.get("business_name") or "bisnis Anda"
    area = region_label(lead.get("region"))
    score = audit.get("score") if audit else lead.get("audit_score")
    points = pitch_points(audit)
    sender = (sender_name or "").strip() or "Tim kami"
    company = (company_name or "").strip()
    signature = f"{sender}" + (f" — {company}" if company else "")

    if points:
        # Only lift the first character: .capitalize() would lowercase the rest
        # and turn "HP" into "hp".
        bullet_lines = "\n".join(f"- {point[0].upper()}{point[1:]}" for point in points)
    else:
        bullet_lines = "- Tampilan dan alur kontaknya masih bisa dioptimalkan"

    score_line = (
        f"Dari pengecekan cepat, website {business} kami beri skor {score}/100."
        if isinstance(score, int)
        else f"Kami sempat melihat website {business}."
    )

    if channel == "whatsapp":
        # Kept short: long WhatsApp openers get ignored.
        if tone == "formal":
            message = (
                f"{_greeting(lead, tone)}\n\n"
                f"Saya {sender}"
                + (f" dari {company}" if company else "")
                + f". Kami membantu UMKM di {area} memperbarui tampilan website.\n\n"
                f"{score_line} Beberapa hal yang kami catat:\n{bullet_lines}\n\n"
                "Kami sudah menyiapkan contoh konsep halaman baru untuk "
                f"{business}. Boleh saya kirimkan sebagai bahan perbandingan?\n\n"
                "Terima kasih."
            )
        else:
            message = (
                f"{_greeting(lead, tone)}\n\n"
                f"Saya {sender}"
                + (f" dari {company}" if company else "")
                + f", bantu UMKM di {area} memperbarui website.\n\n"
                f"{score_line} Yang paling kelihatan:\n{bullet_lines}\n\n"
                f"Kebetulan saya sudah bikin contoh konsep barunya untuk {business}. "
                "Mau saya kirim buat dilihat-lihat dulu?"
            )
        recipient = lead.get("whatsapp_number") or lead.get("phone_number")
        return OutreachDraft(
            channel=channel,
            tone=tone,
            subject=None,
            message=message,
            send_url=_wa_url(recipient, message) if recipient else None,
            recipient=recipient,
        )

    subject = (
        f"Usulan perbaikan tampilan website {business}"
        if tone == "formal"
        else f"Ada beberapa ide untuk website {business}"
    )
    message = (
        f"{_greeting(lead, tone)}\n\n"
        f"Saya {sender}"
        + (f" dari {company}" if company else "")
        + f". Kami membantu pelaku usaha di {area} memperbarui website agar lebih "
        "mudah dipakai calon pelanggan, terutama dari HP.\n\n"
        f"{score_line} Beberapa catatan utama:\n{bullet_lines}\n\n"
        f"Sebagai bahan perbandingan, kami sudah menyiapkan konsep halaman baru untuk "
        f"{business} — satu halaman, siap dilihat langsung di browser. "
        "Jika berkenan, saya kirimkan filenya.\n\n"
        "Silakan balas email ini bila ingin melihat konsepnya.\n\n"
        f"Hormat kami,\n{signature}"
    )
    recipient = lead.get("email")
    return OutreachDraft(
        channel=channel,
        tone=tone,
        subject=subject,
        message=message,
        send_url=_mailto_url(recipient, subject, message) if recipient else None,
        recipient=recipient,
    )
