#!/usr/bin/env bash
#
# Menjalankan seluruh aplikasi dengan satu perintah (Mac / Linux).
#
#   ./start.sh            jalankan + isi data contoh
#   ./start.sh --kosong   jalankan tanpa data contoh
#
# Rahasia (JWT_SECRET, password admin) dibuat sekali lalu disimpan di .env,
# sehingga menjalankan ulang tidak mengubah kredensial yang sudah dipakai.

set -euo pipefail

cd "$(dirname "$0")"

ENV_FILE=".env"
WITH_DEMO=1
[ "${1:-}" = "--kosong" ] && WITH_DEMO=0

say()  { printf '\n\033[1m%s\033[0m\n' "$1"; }
fail() { printf '\n\033[31m%s\033[0m\n' "$1" >&2; exit 1; }

# --- 1. Pastikan Docker siap -------------------------------------------------
command -v docker >/dev/null 2>&1 || fail \
"Docker belum terpasang.
Unduh Docker Desktop di https://www.docker.com/products/docker-desktop/
lalu jalankan skrip ini lagi."

docker info >/dev/null 2>&1 || fail \
"Docker terpasang tapi belum berjalan.
Buka aplikasi Docker Desktop, tunggu sampai statusnya 'Running',
lalu jalankan skrip ini lagi."

# Compose v2 is a docker subcommand; v1 was a separate binary.
if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  fail "Docker Compose tidak ditemukan. Perbarui Docker Desktop ke versi terbaru."
fi

# --- 2. Siapkan rahasia (sekali saja) ----------------------------------------
random_string() {
  # Tidak bergantung pada Python: openssl ada di Mac dan hampir semua Linux.
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 36 | tr -d '\n/+=' | cut -c1-40
  else
    head -c 512 /dev/urandom | LC_ALL=C tr -dc 'A-Za-z0-9' | cut -c1-40
  fi
}

if [ ! -f "$ENV_FILE" ]; then
  say "Membuat kredensial baru di $ENV_FILE"
  ADMIN_PASS="$(random_string | cut -c1-16)"
  {
    echo "# Dibuat otomatis oleh start.sh. Jangan dibagikan."
    echo "JWT_SECRET=$(random_string)"
    echo "BOOTSTRAP_ADMIN_EMAIL=admin@example.com"
    echo "BOOTSTRAP_ADMIN_PASSWORD=$ADMIN_PASS"
  } > "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "  Selesai. Kredensial admin akan ditampilkan di bawah."
else
  echo "Memakai kredensial yang sudah ada di $ENV_FILE"
fi

# --- 3. Bangun dan jalankan --------------------------------------------------
say "Membangun dan menjalankan aplikasi (pertama kali bisa 3-5 menit)"
$COMPOSE up -d --build

# --- 4. Tunggu backend siap --------------------------------------------------
say "Menunggu aplikasi siap"
READY=0
for _ in $(seq 1 60); do
  if curl -fsS -m 2 http://localhost:8080/health >/dev/null 2>&1; then
    READY=1
    break
  fi
  printf '.'
  sleep 2
done
printf '\n'

if [ "$READY" -ne 1 ]; then
  printf '\033[31m%s\033[0m\n' "Aplikasi belum merespons. Lihat log dengan:"
  echo "  $COMPOSE logs --tail=50"
  exit 1
fi

# --- 5. Data contoh ----------------------------------------------------------
DEMO_OUTPUT=""
if [ "$WITH_DEMO" -eq 1 ]; then
  say "Mengisi data contoh"
  # Gagal di sini tidak fatal: aplikasi tetap bisa dipakai tanpa data contoh.
  DEMO_OUTPUT="$($COMPOSE exec -T backend python -m app.seed --demo 2>&1 || true)"
  echo "$DEMO_OUTPUT"
fi

# --- 6. Ringkasan ------------------------------------------------------------
ADMIN_EMAIL="$(grep '^BOOTSTRAP_ADMIN_EMAIL=' "$ENV_FILE" | cut -d= -f2-)"
ADMIN_PASSWORD="$(grep '^BOOTSTRAP_ADMIN_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"

say "Aplikasi siap dipakai"
cat <<INFO
  Buka di browser : http://localhost:8080

  Login admin internal
    email    : $ADMIN_EMAIL
    password : $ADMIN_PASSWORD

  Akun demo (tenant biasa) tercetak di bagian "Seed selesai" di atas.

  Menghentikan       : $COMPOSE down
  Menghentikan + hapus data : $COMPOSE down -v
  Melihat log        : $COMPOSE logs -f
INFO
