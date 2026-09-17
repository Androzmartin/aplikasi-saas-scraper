"""Per-niche landing page templates for the redesign generator.

Each niche gets its own accent palette, section plan, service cards, trust
points and a highlight section that matches how that kind of business actually
sells (a menu for food, a package list for services, and so on).

Accent colours are written into the markup as literal Tailwind class names, so
the Play CDN picks them up when it scans the DOM.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class NicheTemplate:
    key: str
    label: str
    accent: str  # Tailwind colour family used for CTAs and highlights
    hero_eyebrow: str
    headline: str
    subheadline: str
    cta_label: str
    services: List[Tuple[str, str]]
    trust_points: List[str]
    highlight_title: str
    highlight_subtitle: str
    highlight_items: List[Tuple[str, str]]
    testimonials: List[str]
    sections: List[str] = field(default_factory=list)

    # --- layout, so a clinic does not come out shaped like a restaurant ---
    # "overlay"   full-bleed photo behind the headline; for places you sell by
    #             atmosphere (food, salon, hotel, workshop)
    # "split"     calm two-column with a framed photo; for trust-led services
    #             (clinic, school, contractor)
    # "editorial" asymmetric overlapping photos; for visual catalogues
    #             (fashion, property)
    hero_style: str = "split"
    gallery_title: str = "Galeri"
    gallery_subtitle: str = "Beberapa dokumentasi dari kami."
    # Tailwind aspect utility for gallery tiles - portrait suits fashion,
    # landscape suits property, square suits beauty work.
    gallery_aspect: str = "aspect-[4/3]"
    show_gallery: bool = True


_BASE_SECTIONS = [
    "Hero dengan proposisi nilai dan CTA WhatsApp",
    "Ringkasan layanan / produk unggulan",
    "Alasan memilih (trust builders)",
    "Bukti sosial & testimoni",
    "Lokasi & jam operasional",
    "Penutup CTA dan footer kontak",
]


def _sections(highlight: str) -> List[str]:
    plan = list(_BASE_SECTIONS)
    plan.insert(3, highlight)
    return plan


TEMPLATES: Dict[str, NicheTemplate] = {
    "kuliner": NicheTemplate(
        key="kuliner",
        label="Kuliner & F&B",
        accent="amber",
        hero_eyebrow="Rumah makan & kuliner",
        headline="Rasa yang dikenal, layanan yang dipercaya",
        subheadline="Pesan langsung lewat WhatsApp, siap diantar hari ini.",
        cta_label="Pesan via WhatsApp",
        services=[
            ("Dine-in Nyaman", "Tempat bersih dan nyaman untuk makan bersama keluarga maupun rekan kerja."),
            ("Pesan Antar", "Pesanan diproses cepat dan diantar dalam kondisi terbaik."),
            ("Pesanan Partai", "Melayani catering kantor, arisan, dan acara keluarga."),
        ],
        trust_points=[
            "Bahan dipilih segar setiap hari",
            "Dapur bersih dan higienis",
            "Harga jelas tanpa biaya tersembunyi",
        ],
        highlight_title="Menu Favorit",
        highlight_subtitle="Pilihan yang paling sering dipesan pelanggan.",
        highlight_items=[
            ("Menu Andalan", "Sajian khas yang paling banyak dicari."),
            ("Paket Hemat", "Kombinasi lengkap dengan harga bersahabat."),
            ("Menu Keluarga", "Porsi besar untuk disantap bersama."),
        ],
        testimonials=[
            "Rasanya konsisten dan pengantarannya cepat. Sudah jadi langganan kantor kami.",
            "Pesan lewat WhatsApp gampang, responsnya cepat, porsinya pas.",
        ],
        sections=_sections("Menu / produk unggulan"),
        hero_style="overlay",
        gallery_title="Galeri & Suasana",
        gallery_subtitle="Sajian dan suasana tempat kami.",
        gallery_aspect="aspect-[4/3]",
    ),
    "fashion": NicheTemplate(
        key="fashion",
        label="Fashion & Retail",
        accent="rose",
        hero_eyebrow="Butik & fashion",
        headline="Koleksi pilihan untuk tampil percaya diri",
        subheadline="Konsultasikan ukuran dan model Anda, stok terbatas.",
        cta_label="Tanya Stok via WhatsApp",
        services=[
            ("Koleksi Terbaru", "Model diperbarui mengikuti tren tanpa meninggalkan kenyamanan."),
            ("Bahan Berkualitas", "Material dipilih agar nyaman dipakai seharian."),
            ("Custom Ukuran", "Penyesuaian ukuran untuk hasil yang pas di badan."),
        ],
        trust_points=[
            "Foto produk sesuai barang asli",
            "Penukaran ukuran dipermudah",
            "Pengiriman ke seluruh Jabodetabek",
        ],
        highlight_title="Kategori Koleksi",
        highlight_subtitle="Temukan yang sesuai dengan gaya Anda.",
        highlight_items=[
            ("Koleksi Harian", "Pilihan nyaman untuk aktivitas sehari-hari."),
            ("Koleksi Formal", "Tampil rapi untuk kerja dan acara resmi."),
            ("Koleksi Spesial", "Edisi terbatas untuk momen istimewa."),
        ],
        testimonials=[
            "Bahannya adem dan jahitannya rapi. Sesuai dengan foto di katalog.",
            "Admin sabar bantu pilih ukuran. Barang sampai cepat dan aman.",
        ],
        sections=_sections("Katalog / kategori koleksi"),
        hero_style="editorial",
        gallery_title="Koleksi",
        gallery_subtitle="Pilihan yang sedang tersedia.",
        gallery_aspect="aspect-[3/4]",
    ),
    "jasa": NicheTemplate(
        key="jasa",
        label="Jasa & Kontraktor",
        accent="sky",
        hero_eyebrow="Layanan profesional",
        headline="Pengerjaan rapi, tepat waktu, bergaransi",
        subheadline="Konsultasikan kebutuhan Anda gratis melalui WhatsApp.",
        cta_label="Konsultasi Gratis",
        services=[
            ("Survei & Estimasi", "Pengukuran dan perhitungan biaya sebelum pekerjaan dimulai."),
            ("Pengerjaan Terjadwal", "Progres dilaporkan sesuai tahapan yang disepakati."),
            ("Garansi Pengerjaan", "Perbaikan lanjutan bila hasil tidak sesuai kesepakatan."),
        ],
        trust_points=[
            "Estimasi biaya tertulis di awal",
            "Tim berpengalaman dan tertib",
            "Progres dilaporkan berkala",
        ],
        highlight_title="Paket Layanan",
        highlight_subtitle="Disesuaikan dengan skala kebutuhan Anda.",
        highlight_items=[
            ("Paket Dasar", "Untuk kebutuhan perbaikan skala kecil."),
            ("Paket Menengah", "Untuk renovasi atau pengerjaan bertahap."),
            ("Paket Lengkap", "Penanganan menyeluruh dari survei sampai finishing."),
        ],
        testimonials=[
            "Pengerjaan sesuai jadwal dan hasilnya rapi. Komunikasi jelas dari awal.",
            "Estimasi biaya transparan, tidak ada tambahan mendadak di akhir.",
        ],
        sections=_sections("Paket layanan & estimasi"),
        hero_style="split",
        gallery_title="Hasil Pengerjaan",
        gallery_subtitle="Dokumentasi pekerjaan yang telah selesai.",
        gallery_aspect="aspect-[4/3]",
    ),
    "kesehatan": NicheTemplate(
        key="kesehatan",
        label="Kesehatan & Klinik",
        accent="teal",
        hero_eyebrow="Klinik & layanan kesehatan",
        headline="Penanganan profesional yang membuat Anda tenang",
        subheadline="Jadwalkan kunjungan Anda cukup dengan satu pesan.",
        cta_label="Buat Janji Temu",
        services=[
            ("Konsultasi", "Pemeriksaan awal dan penjelasan tindakan yang dibutuhkan."),
            ("Penanganan", "Prosedur dilakukan tenaga berpengalaman dengan alat terawat."),
            ("Kontrol Lanjutan", "Pemantauan setelah tindakan agar pemulihan optimal."),
        ],
        trust_points=[
            "Tenaga profesional berpengalaman",
            "Peralatan disterilkan sesuai prosedur",
            "Biaya dijelaskan sebelum tindakan",
        ],
        highlight_title="Layanan Kami",
        highlight_subtitle="Penanganan yang paling sering dibutuhkan pasien.",
        highlight_items=[
            ("Pemeriksaan Umum", "Konsultasi dan pemeriksaan kondisi awal."),
            ("Tindakan Rutin", "Perawatan berkala untuk menjaga kondisi."),
            ("Penanganan Lanjutan", "Tindakan khusus sesuai hasil pemeriksaan."),
        ],
        testimonials=[
            "Penjelasannya detail dan tidak terburu-buru. Saya jadi paham kondisi saya.",
            "Tempatnya bersih, antrean teratur, dan jadwal janji temu ditepati.",
        ],
        sections=_sections("Daftar layanan & prosedur"),
        hero_style="split",
        gallery_title="Fasilitas",
        gallery_subtitle="Ruang praktik dan peralatan kami.",
        gallery_aspect="aspect-[16/9]",
    ),
    "otomotif": NicheTemplate(
        key="otomotif",
        label="Otomotif & Bengkel",
        accent="orange",
        hero_eyebrow="Bengkel & otomotif",
        headline="Servis presisi oleh teknisi berpengalaman",
        subheadline="Booking jadwal servis Anda tanpa antre panjang.",
        cta_label="Booking Servis",
        services=[
            ("Servis Berkala", "Perawatan rutin agar kendaraan tetap prima."),
            ("Perbaikan", "Diagnosa menyeluruh sebelum penggantian komponen."),
            ("Sparepart", "Komponen sesuai spesifikasi kendaraan Anda."),
        ],
        trust_points=[
            "Diagnosa dijelaskan sebelum dikerjakan",
            "Sparepart sesuai spesifikasi",
            "Estimasi waktu pengerjaan jelas",
        ],
        highlight_title="Jenis Pengerjaan",
        highlight_subtitle="Dari perawatan rutin sampai perbaikan menyeluruh.",
        highlight_items=[
            ("Servis Ringan", "Ganti oli, tune up, dan pengecekan berkala."),
            ("Servis Besar", "Penanganan mesin dan komponen utama."),
            ("Perbaikan Khusus", "Penanganan kerusakan spesifik sesuai diagnosa."),
        ],
        testimonials=[
            "Dijelaskan dulu apa yang rusak sebelum dikerjakan. Tidak asal ganti part.",
            "Booking dulu lewat WA jadi tidak perlu menunggu lama di bengkel.",
        ],
        sections=_sections("Jenis pengerjaan & estimasi"),
        hero_style="overlay",
        gallery_title="Hasil Pengerjaan",
        gallery_subtitle="Beberapa pekerjaan yang sudah kami tangani.",
        gallery_aspect="aspect-[4/3]",
    ),
    "properti": NicheTemplate(
        key="properti",
        label="Properti",
        accent="indigo",
        hero_eyebrow="Properti & hunian",
        headline="Temukan properti yang tepat, tanpa ribet",
        subheadline="Tanyakan ketersediaan unit dan jadwalkan survei hari ini.",
        cta_label="Tanya Ketersediaan",
        services=[
            ("Pilihan Unit", "Beragam tipe yang bisa disesuaikan kebutuhan dan anggaran."),
            ("Pendampingan", "Dibantu dari survei sampai proses administrasi."),
            ("Informasi Jelas", "Detail harga, lokasi, dan fasilitas disampaikan apa adanya."),
        ],
        trust_points=[
            "Data unit diperbarui berkala",
            "Pendampingan proses administrasi",
            "Lokasi strategis di Jabodetabek",
        ],
        highlight_title="Tipe Unit",
        highlight_subtitle="Sesuaikan dengan kebutuhan dan anggaran Anda.",
        highlight_items=[
            ("Tipe Standar", "Pilihan ekonomis untuk kebutuhan dasar."),
            ("Tipe Menengah", "Ruang lebih luas untuk keluarga kecil."),
            ("Tipe Premium", "Fasilitas lengkap dengan lokasi terbaik."),
        ],
        testimonials=[
            "Informasinya jelas sejak awal, tidak ada biaya yang tiba-tiba muncul.",
            "Dibantu sampai proses administrasi selesai. Sangat membantu.",
        ],
        sections=_sections("Tipe unit & ketersediaan"),
        hero_style="editorial",
        gallery_title="Galeri Unit",
        gallery_subtitle="Tampilan unit yang tersedia.",
        gallery_aspect="aspect-[16/9]",
    ),
    "pendidikan": NicheTemplate(
        key="pendidikan",
        label="Pendidikan & Kursus",
        accent="violet",
        hero_eyebrow="Kursus & pelatihan",
        headline="Belajar terarah dengan pendamping berpengalaman",
        subheadline="Ambil kelas percobaan Anda minggu ini.",
        cta_label="Daftar Kelas Percobaan",
        services=[
            ("Kurikulum Terarah", "Materi disusun bertahap sesuai level peserta."),
            ("Kelas Kecil", "Jumlah peserta dibatasi agar pendampingan maksimal."),
            ("Evaluasi Berkala", "Perkembangan peserta dilaporkan secara rutin."),
        ],
        trust_points=[
            "Pengajar berpengalaman di bidangnya",
            "Jadwal fleksibel mengikuti peserta",
            "Laporan perkembangan berkala",
        ],
        highlight_title="Program Kelas",
        highlight_subtitle="Pilih program sesuai kebutuhan dan jadwal Anda.",
        highlight_items=[
            ("Kelas Dasar", "Untuk peserta yang baru memulai."),
            ("Kelas Lanjutan", "Pendalaman materi untuk peserta berpengalaman."),
            ("Kelas Privat", "Pendampingan satu per satu sesuai target."),
        ],
        testimonials=[
            "Pengajarnya sabar dan materinya runtut. Anak saya jadi lebih percaya diri.",
            "Jadwalnya fleksibel, cocok untuk yang sambil bekerja.",
        ],
        sections=_sections("Program kelas & jadwal"),
        hero_style="split",
        gallery_title="Suasana Belajar",
        gallery_subtitle="Kegiatan dan ruang kelas kami.",
        gallery_aspect="aspect-[4/3]",
    ),
    "umum": NicheTemplate(
        key="umum",
        label="Umum / Lainnya",
        accent="emerald",
        hero_eyebrow="Bisnis lokal tepercaya",
        headline="Solusi tepercaya untuk kebutuhan Anda",
        subheadline="Hubungi kami lewat WhatsApp untuk penawaran terbaik.",
        cta_label="Hubungi via WhatsApp",
        services=[
            ("Kualitas Terjaga", "Standar pengerjaan dan bahan yang konsisten pada setiap pesanan."),
            ("Respons Cepat", "Pertanyaan Anda dibalas pada jam kerja melalui WhatsApp."),
            ("Harga Transparan", "Penawaran jelas di depan, tanpa biaya tersembunyi."),
        ],
        trust_points=[
            "Pelayanan ramah dan responsif",
            "Harga jelas sejak awal",
            "Melayani area Jabodetabek",
        ],
        highlight_title="Yang Kami Tawarkan",
        highlight_subtitle="Pilihan layanan yang paling sering dibutuhkan.",
        highlight_items=[
            ("Layanan Utama", "Penanganan kebutuhan paling umum pelanggan."),
            ("Layanan Tambahan", "Pelengkap agar hasilnya lebih maksimal."),
            ("Konsultasi", "Diskusi kebutuhan sebelum memutuskan."),
        ],
        testimonials=[
            "Pelayanannya cepat dan hasilnya sesuai ekspektasi.",
            "Sudah beberapa kali pesan dan selalu konsisten. Recommended.",
        ],
        sections=_sections("Layanan unggulan"),
        hero_style="split",
        gallery_title="Galeri",
        gallery_subtitle="Beberapa dokumentasi dari kami.",
        gallery_aspect="aspect-[4/3]",
    ),
}

DEFAULT_TEMPLATE = "umum"


def get_template(key: Optional[str]) -> NicheTemplate:
    """Return the template for a niche, falling back to the generic one."""
    if key and key in TEMPLATES:
        return TEMPLATES[key]
    return TEMPLATES[DEFAULT_TEMPLATE]


def list_templates() -> List[Dict[str, str]]:
    return [
        {
            "key": template.key,
            "label": template.label,
            "accent": template.accent,
            "headline": template.headline,
            "highlight": template.highlight_title,
        }
        for template in TEMPLATES.values()
    ]
