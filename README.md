# UMKM Scraper SaaS — Website Redesign untuk Jakarta/Bodetabek

Platform SaaS untuk agency digital marketing, freelancer web designer, dan tim
sales: kumpulkan lead UMKM dari website publik, nilai kualitas websitenya, lalu
hasilkan konsep redesign beserta file `index.html` siap presentasi.

> Status: **MVP**. Fitur P0 dari dokumen breakdown sudah lengkap dan berjalan.

## Ringkasan Fitur

| Modul | Status | Catatan |
|---|---|---|
| Auth & tenant dasar | ✅ | JWT, role `admin_internal` / `user_tenant`, registrasi membuat tenant |
| Project & URL input | ✅ | Input manual, bulk paste, unggah `.txt`/`.csv`, validasi URL |
| Scraping job engine | ✅ | Antrean, status pending/running/completed/failed, retry, recovery |
| Public contact extractor | ✅ | Nama bisnis, WA, telepon, email, alamat, contact person + sumber |
| Lead dashboard | ✅ | Tabel, pencarian, filter wilayah/status/skor, notes, tags |
| Website audit scoring | ✅ | 5 parameter × 20 poin → skor 0–100, issue list, ringkasan peluang |
| Redesign generator | ✅ | Konsep + preview + single-file `index.html` (Tailwind Play CDN) |
| Export CSV | ✅ | Streaming, BOM UTF-8 agar rapi di Excel |
| Admin internal | ✅ | Monitoring tenant, user, project, job, error, audit log |

### Tambahan P1

| Fitur | Status | Catatan |
|---|---|---|
| Screenshot desktop/mobile | ✅ | Opsional (Playwright), untuk perbandingan before/after |
| Approval admin | ✅ | Opsional, menahan download `index.html` sampai disetujui |
| Bulk retry job | ✅ | Ulangi semua job gagal sekaligus, per project atau global |
| Anti-duplikat URL | ✅ | URL yang sudah diproses di project dilewati, hemat kuota |
| Confidence per field | ✅ | Ditampilkan di detail lead |
| Lead notes & tags | ✅ | Tersimpan per lead |

### Tambahan P2

| Fitur | Status | Catatan |
|---|---|---|
| Template redesign per niche | ✅ | 8 niche, masing-masing punya palet, section, dan CTA sendiri |
| Draft outreach WA/email | ✅ | Pesan disusun dari hasil audit + deep link wa.me/mailto |
| Proposal klien (HTML/PDF) | ✅ | Dokumen siap kirim, mandiri tanpa CDN |
| Analitik | ✅ | Funnel lead, sebaran skor & wilayah, tren harian |
| Billing (Duitku) | ✅ | Paket berlangganan, checkout, callback, rekonsiliasi |
| AI enrichment | ✅ | Naskah redesign khusus per bisnis + klasifikasi niche (opsional) |

Sesuai dokumen breakdown, hal berikut **sengaja ditunda**: billing, outreach
WhatsApp/email otomatis, editor visual drag-and-drop, proposal PDF, export
Excel/JSON, white-label, dan discovery engine dari pihak ketiga.

## Tech Stack

- **Frontend** — React 18 + TypeScript + Vite + Tailwind CSS
- **Backend** — FastAPI (Python 3.11), Motor (async MongoDB)
- **Database** — MongoDB 7
- **Auth** — JWT bearer token
- **Storage** — driver filesystem lokal (mudah diganti S3/GCS)
- **AI (opsional)** — Anthropic atau OpenAI untuk rewrite copy; nonaktif secara
  default dan otomatis jatuh kembali ke template deterministik

## Menjalankan secara Lokal

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Wajib: isi JWT_SECRET. Buat dengan:
python -c "import secrets; print(secrets.token_urlsafe(48))"

# Jalankan MongoDB (paling mudah lewat Docker):
docker run -d -p 27017:27017 --name mongo mongo:7

uvicorn app.main:app --reload
```

API tersedia di `http://localhost:8000`, dokumentasi interaktif di
`http://localhost:8000/docs`.

Membuat akun demo:

```bash
python -m app.seed          # mencetak email + password yang dihasilkan
```

Admin internal dibuat otomatis saat startup bila `BOOTSTRAP_ADMIN_PASSWORD`
diisi pada `.env`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Buka `http://localhost:5173`. Vite mem-proxy `/api` ke `http://localhost:8000`,
jadi tidak perlu konfigurasi CORS tambahan saat pengembangan.

### 3. Docker Compose

```bash
export JWT_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
export BOOTSTRAP_ADMIN_PASSWORD='ganti-password-ini'
docker compose up --build
```

## Template Redesign per Niche

Generator memilih template berdasarkan nama bisnis, dan user bisa menimpanya
secara manual dari halaman detail lead.

| Niche | Aksen | Section khusus | CTA |
|---|---|---|---|
| Kuliner & F&B | amber | Menu Favorit | Pesan via WhatsApp |
| Fashion & Retail | rose | Kategori Koleksi | Tanya Stok via WhatsApp |
| Jasa & Kontraktor | sky | Paket Layanan | Konsultasi Gratis |
| Kesehatan & Klinik | teal | Layanan Kami | Buat Janji Temu |
| Otomotif & Bengkel | orange | Jenis Pengerjaan | Booking Servis |
| Properti | indigo | Tipe Unit | Tanya Ketersediaan |
| Pendidikan & Kursus | violet | Program Kelas | Daftar Kelas Percobaan |
| Umum / Lainnya | emerald | Yang Kami Tawarkan | Hubungi via WhatsApp |

Tiap template mengubah palet warna, copy hero, kartu layanan, trust points,
testimoni, dan satu section khusus sesuai cara industri itu berjualan. Ukuran
`index.html` tetap sekitar 15 KB.

```
GET  /api/redesign/templates                          # daftar niche
POST /api/redesign/{lead_id}/generate?template=jasa   # timpa deteksi otomatis
```

## Langganan & Pembayaran (Duitku)

Empat paket, kuota scraping per bulan mengikuti paket:

| Paket | Harga | Kuota | Masa aktif |
|---|---|---|---|
| Gratis | Rp 0 | 50 job/bulan | selamanya |
| Starter | Rp 149.000 | 500 job/bulan | 30 hari |
| Pro | Rp 399.000 | 2.000 job/bulan | 30 hari |
| Business | Rp 1.290.000 | 10.000 job/bulan | 30 hari |

Paket didefinisikan di `app/services/plans.py`, bukan di database — harga perlu
ditinjau seperti kode, dan baris harga yang bisa diubah saat runtime mudah
membuat produk terjual terlalu murah tanpa sengaja.

### Alur pembayaran

1. User memilih paket → `POST /billing/checkout`
2. Server mencatat invoice **berstatus pending lebih dulu**, lalu memanggil
   Duitku (`/webapi/api/merchant/v2/inquiry`)
3. User diarahkan ke halaman pembayaran Duitku
4. Duitku memanggil `POST /billing/callback` → paket diaktifkan
5. User kembali ke `/billing`; bila callback belum sampai, aplikasi otomatis
   menanyakan status ke Duitku

### Pengamanan callback

Callback adalah endpoint publik tanpa autentikasi, jadi diperlakukan sebagai
input yang tidak dipercaya:

- **Signature diverifikasi** — `MD5(merchantCode + amount + merchantOrderId + apiKey)`,
  dibandingkan secara constant-time. Callback dengan merchant code lain ditolak.
- **Nominal dicocokkan dengan invoice.** Contoh resmi Duitku **tidak** melakukan
  ini; tanpa pemeriksaan ini callback bertanda tangan sah dengan nominal
  Rp 1.000 bisa mengaktifkan paket Rp 1.290.000.
- **Idempoten.** Transisi `pending → paid` dijaga update atomik, sehingga
  callback yang dikirim ulang tidak memperpanjang masa aktif dua kali.
- **Rekonsiliasi.** Webhook bisa hilang, jadi status tidak pernah bergantung
  pada callback saja — tersedia `POST /billing/payments/{id}/sync` yang bertanya
  langsung ke Duitku.
- Payload callback mentah disimpan untuk audit.

### Konfigurasi

```
DUITKU_MERCHANT_CODE=...
DUITKU_API_KEY=...
DUITKU_PRODUCTION=false          # false = sandbox
PUBLIC_API_BASE_URL=https://api.domain-anda.com   # wajib bisa diakses Duitku
PUBLIC_APP_BASE_URL=https://app.domain-anda.com
```

`PUBLIC_API_BASE_URL` dipakai menyusun `callbackUrl`. Di produksi ini **harus**
URL publik — `localhost` tidak akan bisa dipanggil Duitku. Daftarkan juga URL
callback tersebut pada dashboard Duitku.

Kuota mengikuti paket yang **sedang berlaku**: paket berbayar yang masa aktifnya
habis otomatis turun ke kuota Gratis, bukan tetap memakai kuota lama.

## Analitik

Halaman **Analitik** merangkum kondisi pipeline:

- **Perjalanan lead** — berapa yang mencapai tiap tahap (Baru → Dihubungi →
  Qualified). Tiap tahap menghitung lead yang *pernah sampai* ke tahap itu,
  sehingga funnel tidak pernah melebar ke bawah.
- **Peluang redesign** — sebaran skor audit dalam empat pita, diurutkan dari
  yang paling bernilai bagi agency (skor rendah = peluang besar).
- **Sebaran wilayah** — sepuluh wilayah dengan lead terbanyak.
- **Tren lead masuk** — jumlah lead baru per hari, 30/60/90 hari.

Catatan desain grafik: setiap grafik menampilkan **satu ukuran** dengan kategori
tertulis pada sumbunya, jadi tidak memerlukan palet kategorikal maupun legenda —
sekaligus menghilangkan risiko warna yang sulit dibedakan oleh penyandang buta
warna. Kategori berurutan memakai satu ramp biru yang sudah divalidasi (lightness
monoton, jarak antar-langkah memadai, ujung paling terang tetap kontras terhadap
latar). Warna tidak pernah menjadi satu-satunya pembawa makna: setiap nilai juga
tertulis, dan tersedia tampilan tabel.

```
GET /api/analytics/overview?project_id=...&days=30
```

## Draft Outreach

Setelah audit dan redesign siap, aplikasi menyusun **draft pesan penawaran**
yang mengutip temuan audit lead tersebut:

- Kanal: WhatsApp atau email
- Gaya bahasa: formal atau ramah
- Menyebut skor audit dan 3 temuan paling berat dalam bahasa awam
- Menghasilkan deep link `wa.me` / `mailto` yang sudah terisi pesannya
- Tombol "Tandai sudah dikirim" menaikkan status lead `new` → `contacted`
  (status yang lebih lanjut seperti `qualified` tidak akan diturunkan)

Aplikasi **tidak mengirim apa pun sendiri**. Pesan dikirim dari akun WhatsApp
atau email milik user, sehingga MVP tidak perlu tunduk pada ketentuan WhatsApp
Business API dan tidak menyimpan kredensial kanal apa pun.

```
GET  /api/outreach/{lead_id}?channel=whatsapp&tone=formal
POST /api/outreach/{lead_id}/mark-sent?channel=whatsapp
```

## Proposal untuk Klien

Menghasilkan dokumen siap kirim yang menggabungkan seluruh hasil kerja:
ringkasan dan skor audit, temuan utama, screenshot kondisi sekarang
berdampingan dengan konsep halaman baru, lingkup pekerjaan, deliverable,
perkiraan waktu, kolom investasi, dan langkah berikutnya.

Dokumen ini **menyertakan seluruh CSS-nya sendiri** (tidak memanggil CDN) dan
screenshot di-embed sebagai data URI, sehingga tetap tampil benar saat dibuka
offline, diteruskan lewat email, atau dicetak.

```
GET /api/proposals/{lead_id}                       # preview HTML
GET /api/proposals/{lead_id}/download?format=html  # selalu tersedia
GET /api/proposals/{lead_id}/download?format=pdf   # butuh Playwright
```

Ekspor PDF memakai browser opsional yang sama dengan fitur screenshot. Bila
browser tidak terpasang, API menjawab 503 dengan pesan yang mengarahkan user
mengunduh HTML lalu mencetaknya ke PDF dari browser — jadi fitur ini tidak
pernah menjadi jalan buntu.

## AI Enrichment (opsional)

Secara default generator memakai template deterministik — gratis, cepat, dan
hasilnya bisa diprediksi. Bila diaktifkan, AI mengerjakan dua hal:

1. **Klasifikasi niche** dari isi website itu sendiri, bukan sekadar mencocokkan
   nama bisnis dengan daftar kata kunci. Tebakan dengan keyakinan di bawah 0,6
   ditolak karena tebakan ragu-ragu lebih buruk daripada heuristik yang diganti.
2. **Menulis seluruh naskah** landing page untuk bisnis itu — hero, kartu
   layanan, alasan memilih, dan section khusus industri — bukan mengisi template
   generik.

```bash
pip install -r requirements-ai.txt
```

```
AI_ENABLED=true
AI_API_KEY=sk-ant-...
AI_MODEL=claude-opus-5
```

### Penjaga anti-karangan

Dokumen ini dikirim ke calon klien sungguhan, jadi klaim palsu lebih berbahaya
daripada naskah template yang datar. Ada tiga lapis:

1. **Instruksi sistem** melarang keras menyebut jumlah pelanggan, tahun berdiri,
   lama pengalaman, persentase, peringkat, penghargaan, atau sertifikasi.
2. **Structured output** mengunci bentuk balasan (`additionalProperties: false`),
   sehingga responsnya selalu bisa diproses.
3. **Validasi lokal** menolak naskah yang tetap memuat klaim berbentuk angka
   ("1000+ pelanggan", "sejak 1998", "98% puas", "nomor 1 di Jakarta",
   "bersertifikat"). Satu klaim mencurigakan membatalkan **seluruh** set naskah,
   dan sistem kembali memakai template.

Kegagalan apa pun — API key salah, rate limit, SDK belum terpasang, balasan
tidak valid — selalu jatuh kembali ke template. AI tidak pernah bisa
menggagalkan scraping, audit, maupun generate redesign.

## Fitur Opsional

### Screenshot desktop/mobile

Butuh Playwright dan browser, jadi tidak dipasang secara default:

```bash
pip install -r requirements-screenshot.txt
playwright install chromium
```

Lalu pada `.env`:

```
SCREENSHOT_ENABLED=true
SCREENSHOT_ON_SCRAPE=true   # ambil otomatis setiap selesai scraping
```

Bila Playwright tidak terpasang, tombol screenshot memberi pesan yang jelas dan
**tidak** mengganggu scraping, audit, maupun generate redesign.

### Approval admin sebelum download

```
REQUIRE_REDESIGN_APPROVAL=true
```

Saat aktif, hasil redesign berstatus `pending`. User tetap bisa melihat preview,
tetapi tombol download terkunci sampai admin internal menyetujui lewat tab
**Review redesign**. Admin bisa menolak disertai catatan yang ditampilkan ke user.
Admin internal selalu bisa mengunduh berkasnya untuk keperluan review.

## Alur Pemakaian

1. Daftar/masuk, lalu buat **project** dengan wilayah target.
2. Tempel daftar URL website UMKM (atau unggah file), klik **Jalankan scraping**.
3. Worker merayapi halaman publik: homepage plus halaman kontak/tentang.
4. Data kontak publik diekstrak dan disimpan sebagai **lead**, lengkap dengan
   skor audit awal.
5. Buka detail lead untuk melihat audit: skor, rincian per parameter, daftar
   temuan, dan ringkasan peluang.
6. Klik **Generate redesign** untuk membuat konsep, preview, dan
   `index.html` satu file yang bisa diunduh.
7. Unduh proposal (HTML/PDF) untuk dikirim ke calon klien.
8. Susun draft penawaran WhatsApp/email dari temuan audit, lalu kirim dari
   akun Anda sendiri dan tandai sebagai terkirim.
9. Export CSV untuk diserahkan ke tim sales.
10. (Opsional) Ambil screenshot desktop/mobile untuk bahan before/after.
11. Admin internal memantau tenant, job, error, dan meninjau hasil redesign
   melalui menu Admin.

## Struktur Proyek

```
backend/
  app/
    main.py            # entrypoint FastAPI, lifespan, CORS
    config.py          # settings dari environment
    db.py              # koneksi Mongo + index
    deps.py            # auth, guard role, scoping tenant
    security.py        # hashing password, JWT
    serializers.py     # dokumen Mongo -> respons API
    models/            # skema Pydantic
    routers/           # auth, projects, scrape, leads, audits, redesign, exports, admin
    services/
      urls.py          # normalisasi & validasi URL (termasuk proteksi SSRF)
      scraper.py       # crawler, robots.txt, rate limit per domain
      extractor.py     # ekstraksi kontak publik + confidence
      audit.py         # mesin skoring 0–100
      redesign.py      # konsep + render index.html
      jobs.py          # antrean worker
      storage.py       # object storage
      ai.py            # enrichment opsional
  tests/               # 307 test
frontend/
  src/
    api/               # client + tipe yang mencerminkan skema backend
    components/        # layout dan komponen UI bersama
    context/           # AuthContext
    pages/             # Login, Dashboard, Projects, Leads, LeadDetail, Jobs,
                       # Analytics, Admin, Profile
    lib/               # format tanggal, label wilayah
```

## Pengujian

```bash
cd backend && python -m pytest        # 307 test
cd frontend && npx tsc --noEmit       # typecheck
cd frontend && npm run build          # build produksi
```

Seluruh test backend berjalan tanpa MongoDB, termasuk test API end-to-end yang
melewati router, auth, dan serializer sebenarnya.

### Cara kebenaran query dijaga tanpa mongod

Karena server MongoDB asli tidak tersedia di CI, kebenaran dijaga tiga lapis:

1. **Index produksi benar-benar dibuat di test.** `ensure_indexes()` dipanggil
   pada fixture, sehingga constraint seperti unique `users.email` betul-betul
   ditegakkan — termasuk jalur `DuplicateKeyError` pada registrasi.
2. **Dua engine query independen dibandingkan.** Setiap bentuk query yang
   dipakai aplikasi dijalankan di `mongomock` **dan** `montydb`, lalu hasilnya
   diverifikasi identik. Dua implementasi terpisah yang sepakat adalah bukti
   kuat bahwa query-nya benar. Lihat `tests/test_database_contract.py`.
3. **Output query builder diuji sebagai query sungguhan**, bukan sekadar dict
   Python — termasuk memastikan input pencarian ber-metakarakter regex tidak
   bisa berlaku sebagai regex.

Yang **belum** tercakup dan tetap perlu satu kali uji dengan mongod asli:
perilaku sisi server yang tidak punya implementasi Python, khususnya scoring
`$text` search dan concurrency sungguhan pada pengambilan job.

## Kepatuhan dan Batasan

Diterapkan sesuai bagian *Kepatuhan dan Batasan MVP* pada dokumen breakdown:

- Hanya data yang **tampil publik** di website target yang dikumpulkan.
- `robots.txt` dipatuhi (dapat dinonaktifkan hanya lewat konfigurasi eksplisit).
- **Rate limit per domain** dengan jeda antar permintaan yang dapat diatur.
- Aktivitas scraping dan generate dicatat pada **audit log** (`activity_logs`).
- Kuota job per tenant per bulan untuk mencegah penyalahgunaan.
- Alamat internal/privat (localhost, 10.x, 192.168.x, dll.) **ditolak** sehingga
  scraper tidak bisa dipakai sebagai alat SSRF.
- Nilai CSV dinetralkan terhadap **formula injection**.
- Konten hasil scraping **di-escape** saat dirender ke `index.html`.
- Preview redesign dijalankan di iframe `sandbox="allow-scripts"` tanpa
  `allow-same-origin`, sehingga terisolasi dari DOM dan token aplikasi.

Menambahkan discovery dari platform pihak ketiga perlu review Terms of Service
terlebih dahulu dan sengaja tidak termasuk dalam MVP.

## Konfigurasi Penting

| Variabel | Default | Keterangan |
|---|---|---|
| `JWT_SECRET` | — | **Wajib diganti** di produksi |
| `MONGO_URI` | `mongodb://localhost:27017` | Koneksi MongoDB |
| `SCRAPER_MAX_PAGES_PER_SITE` | `6` | Halaman maksimum per situs |
| `SCRAPER_DELAY_SECONDS` | `1.0` | Jeda antar permintaan ke domain yang sama |
| `SCRAPER_WORKER_CONCURRENCY` | `3` | Jumlah worker paralel |
| `SCRAPER_RESPECT_ROBOTS` | `true` | Patuhi robots.txt |
| `DEFAULT_MONTHLY_JOB_QUOTA` | `500` | Kuota job per tenant per bulan |
| `AI_ENABLED` | `false` | Aktifkan penulisan naskah dengan AI |
| `AI_MODEL` | `claude-opus-5` | Model Claude yang dipakai |
| `SCREENSHOT_ENABLED` | `false` | Aktifkan fitur screenshot (butuh Playwright) |
| `SCREENSHOT_ON_SCRAPE` | `false` | Ambil screenshot otomatis saat scraping selesai |
| `REQUIRE_REDESIGN_APPROVAL` | `false` | Wajib approval admin sebelum download |
| `DUITKU_MERCHANT_CODE` | — | Merchant code dari dashboard Duitku |
| `DUITKU_API_KEY` | — | API key Duitku |
| `DUITKU_PRODUCTION` | `false` | `false` = sandbox, `true` = produksi |
| `PUBLIC_API_BASE_URL` | `http://localhost:8000` | URL publik API untuk callback Duitku |

## Status

Seluruh item **P0, P1, dan P2** dari dokumen breakdown sudah diimplementasikan.

Yang perlu dilakukan sebelum produksi:

1. Satu kali uji dengan **MongoDB asli** — perilaku `$text` search dan
   concurrency belum pernah diuji terhadap mongod sungguhan.
2. Satu kali transaksi uji di **sandbox Duitku** — logika dan pengamanan
   callback sudah terverifikasi, tetapi handshake dengan server Duitku belum
   pernah terjadi.
3. Isi `PUBLIC_API_BASE_URL` dengan URL publik dan daftarkan URL callback pada
   dashboard Duitku.
