@echo off
rem Menjalankan seluruh aplikasi dengan satu perintah (Windows).
rem
rem   start.bat            jalankan + isi data contoh
rem   start.bat --kosong   jalankan tanpa data contoh
rem
rem Rahasia (JWT_SECRET, password admin) dibuat sekali lalu disimpan di .env,
rem sehingga menjalankan ulang tidak mengubah kredensial yang sudah dipakai.

setlocal enabledelayedexpansion
cd /d "%~dp0"

set ENV_FILE=.env
set WITH_DEMO=1
if "%~1"=="--kosong" set WITH_DEMO=0

rem --- 1. Pastikan Docker siap ------------------------------------------------
where docker >nul 2>&1
if errorlevel 1 (
    echo.
    echo Docker belum terpasang.
    echo Unduh Docker Desktop di https://www.docker.com/products/docker-desktop/
    echo lalu jalankan skrip ini lagi.
    pause
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo.
    echo Docker terpasang tapi belum berjalan.
    echo Buka aplikasi Docker Desktop, tunggu sampai statusnya "Running",
    echo lalu jalankan skrip ini lagi.
    pause
    exit /b 1
)

docker compose version >nul 2>&1
if errorlevel 1 (
    echo.
    echo Docker Compose tidak ditemukan. Perbarui Docker Desktop ke versi terbaru.
    pause
    exit /b 1
)

rem --- 2. Siapkan rahasia (sekali saja) --------------------------------------
if not exist "%ENV_FILE%" (
    echo.
    echo Membuat kredensial baru di %ENV_FILE%
    rem PowerShell selalu ada di Windows 10/11 dan menghasilkan acak yang layak.
    for /f "delims=" %%A in ('powershell -NoProfile -Command ^
        "[Convert]::ToBase64String((1..36 ^| ForEach-Object {Get-Random -Max 256})) -replace '[^a-zA-Z0-9]','' ^| ForEach-Object {$_.Substring(0,40)}"') do set JWT=%%A
    for /f "delims=" %%A in ('powershell -NoProfile -Command ^
        "[Convert]::ToBase64String((1..16 ^| ForEach-Object {Get-Random -Max 256})) -replace '[^a-zA-Z0-9]','' ^| ForEach-Object {$_.Substring(0,12)}"') do set ADMINPASS=%%A

    > "%ENV_FILE%" echo # Dibuat otomatis oleh start.bat. Jangan dibagikan.
    >> "%ENV_FILE%" echo JWT_SECRET=!JWT!
    >> "%ENV_FILE%" echo BOOTSTRAP_ADMIN_EMAIL=admin@example.com
    >> "%ENV_FILE%" echo BOOTSTRAP_ADMIN_PASSWORD=!ADMINPASS!
    echo   Selesai. Kredensial admin akan ditampilkan di bawah.
) else (
    echo Memakai kredensial yang sudah ada di %ENV_FILE%
)

rem --- 3. Bangun dan jalankan ------------------------------------------------
echo.
echo Membangun dan menjalankan aplikasi ^(pertama kali bisa 3-5 menit^)
docker compose up -d --build
if errorlevel 1 (
    echo.
    echo Gagal menjalankan. Lihat log dengan: docker compose logs --tail=50
    pause
    exit /b 1
)

rem --- 4. Tunggu backend siap ------------------------------------------------
echo.
echo Menunggu aplikasi siap
set READY=0
for /l %%i in (1,1,60) do (
    if !READY!==0 (
        powershell -NoProfile -Command ^
            "try { (Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://localhost:8080/health).StatusCode } catch { exit 1 }" >nul 2>&1
        if not errorlevel 1 (
            set READY=1
        ) else (
            timeout /t 2 /nobreak >nul
        )
    )
)

if !READY!==0 (
    echo.
    echo Aplikasi belum merespons. Lihat log dengan:
    echo   docker compose logs --tail=50
    pause
    exit /b 1
)

rem --- 5. Data contoh --------------------------------------------------------
if !WITH_DEMO!==1 (
    echo.
    echo Mengisi data contoh
    docker compose exec -T backend python -m app.seed --demo
)

rem --- 6. Ringkasan ----------------------------------------------------------
for /f "tokens=1,* delims==" %%A in ('findstr /b "BOOTSTRAP_ADMIN_EMAIL=" "%ENV_FILE%"') do set ADMIN_EMAIL=%%B
for /f "tokens=1,* delims==" %%A in ('findstr /b "BOOTSTRAP_ADMIN_PASSWORD=" "%ENV_FILE%"') do set ADMIN_PASSWORD=%%B

echo.
echo ============================================
echo  Aplikasi siap dipakai
echo ============================================
echo.
echo   Buka di browser : http://localhost:8080
echo.
echo   Login admin internal
echo     email    : !ADMIN_EMAIL!
echo     password : !ADMIN_PASSWORD!
echo.
echo   Akun demo (tenant biasa) tercetak di bagian "Seed selesai" di atas.
echo.
echo   Menghentikan              : docker compose down
echo   Menghentikan + hapus data : docker compose down -v
echo   Melihat log               : docker compose logs -f
echo.
pause
