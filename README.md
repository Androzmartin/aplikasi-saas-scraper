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
7. Export CSV untuk diserahkan ke tim sales.
8. Admin internal memantau tenant, job, dan error melalui menu Admin.

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
  tests/               # 106 test
frontend/
  src/
    api/               # client + tipe yang mencerminkan skema backend
    components/        # layout dan komponen UI bersama
    context/           # AuthContext
    pages/             # Login, Dashboard, Projects, Leads, LeadDetail, Jobs, Admin, Profile
    lib/               # format tanggal, label wilayah
```

## Pengujian

```bash
cd backend && python -m pytest        # 106 test
cd frontend && npx tsc --noEmit       # typecheck
cd frontend && npm run build          # build produksi
```

Seluruh test backend berjalan tanpa MongoDB (memakai `mongomock-motor`), termasuk
test API end-to-end yang melewati router, auth, dan serializer sebenarnya.

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
| `AI_ENABLED` | `false` | Aktifkan rewrite copy dengan AI |

## Langkah Berikutnya (P1)

Screenshot desktop/mobile untuk before/after, bulk upload yang lebih kaya,
approval admin sebelum unduh, serta monitoring job yang lebih rinci.
