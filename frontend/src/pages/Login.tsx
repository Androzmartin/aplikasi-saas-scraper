import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { Alert } from '@/components/ui'
import { useAuth } from '@/context/AuthContext'

export default function Login() {
  const { user, loading, login, register } = useAuth()
  const navigate = useNavigate()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [form, setForm] = useState({ email: '', password: '', name: '', company_name: '' })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (!loading && user) return <Navigate to="/" replace />

  function update(field: keyof typeof form) {
    return (event: React.ChangeEvent<HTMLInputElement>) =>
      setForm((previous) => ({ ...previous, [field]: event.target.value }))
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setBusy(true)
    try {
      if (mode === 'login') {
        await login(form.email, form.password)
      } else {
        await register({
          company_name: form.company_name,
          name: form.name,
          email: form.email,
          password: form.password,
        })
      }
      navigate('/', { replace: true })
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Terjadi kesalahan, coba lagi')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen">
      <div className="hidden w-1/2 flex-col justify-between bg-navy-900 p-12 lg:flex">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-md bg-white text-sm font-bold text-navy-900">
            US
          </span>
          <span className="text-lg font-semibold text-white">UMKM Scraper SaaS</span>
        </div>
        <div>
          <h2 className="max-w-md text-3xl font-semibold leading-tight text-white">
            Kumpulkan lead UMKM, audit websitenya, lalu tunjukkan konsep redesign.
          </h2>
          <p className="mt-5 max-w-md text-sm leading-relaxed text-navy-300">
            Platform untuk agency digital marketing, freelancer web designer, dan tim sales
            yang menggarap pasar Jakarta dan Bodetabek.
          </p>
          <dl className="mt-10 grid grid-cols-3 gap-6 border-t border-navy-800 pt-8">
            {[
              ['Ekstraksi', 'Kontak publik'],
              ['Audit', 'Skor 0–100'],
              ['Output', 'index.html'],
            ].map(([term, detail]) => (
              <div key={term}>
                <dt className="text-xs uppercase tracking-wide text-navy-400">{term}</dt>
                <dd className="mt-1 text-sm font-medium text-white">{detail}</dd>
              </div>
            ))}
          </dl>
        </div>
        <p className="text-xs text-navy-400">
          Hanya memproses data yang ditampilkan publik di website target.
        </p>
      </div>

      <div className="flex w-full items-center justify-center px-6 py-12 lg:w-1/2">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <span className="flex h-10 w-10 items-center justify-center rounded-md bg-navy-900 text-sm font-bold text-white">
              US
            </span>
          </div>

          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            {mode === 'login' ? 'Masuk ke akun Anda' : 'Buat akun baru'}
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            {mode === 'login'
              ? 'Gunakan email dan password yang terdaftar.'
              : 'Satu akun membuat satu tenant untuk tim Anda.'}
          </p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-4">
            {error && <Alert tone="error">{error}</Alert>}

            {mode === 'register' && (
              <>
                <div>
                  <label className="label" htmlFor="company_name">Nama perusahaan</label>
                  <input
                    id="company_name" className="input" required minLength={2}
                    value={form.company_name} onChange={update('company_name')}
                    placeholder="Agency Kreatif Nusantara"
                  />
                </div>
                <div>
                  <label className="label" htmlFor="name">Nama lengkap</label>
                  <input
                    id="name" className="input" required minLength={2}
                    value={form.name} onChange={update('name')} placeholder="Budi Santoso"
                  />
                </div>
              </>
            )}

            <div>
              <label className="label" htmlFor="email">Email</label>
              <input
                id="email" type="email" className="input" required autoComplete="email"
                value={form.email} onChange={update('email')} placeholder="nama@perusahaan.co.id"
              />
            </div>

            <div>
              <label className="label" htmlFor="password">Password</label>
              <input
                id="password" type="password" className="input" required minLength={mode === 'register' ? 8 : 1}
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                value={form.password} onChange={update('password')} placeholder="••••••••"
              />
              {mode === 'register' && (
                <p className="mt-1 text-xs text-slate-400">Minimal 8 karakter.</p>
              )}
            </div>

            <button type="submit" className="btn-primary w-full" disabled={busy}>
              {busy ? 'Memproses…' : mode === 'login' ? 'Masuk' : 'Daftar'}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-500">
            {mode === 'login' ? 'Belum punya akun?' : 'Sudah punya akun?'}{' '}
            <button
              type="button"
              className="font-medium text-navy-700 underline-offset-4 hover:underline"
              onClick={() => {
                setMode(mode === 'login' ? 'register' : 'login')
                setError(null)
              }}
            >
              {mode === 'login' ? 'Daftar sekarang' : 'Masuk di sini'}
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}
