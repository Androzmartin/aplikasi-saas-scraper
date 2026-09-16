import { useState } from 'react'
import { ApiError, api } from '@/api/client'
import { Alert, Field, PageHeader, Panel } from '@/components/ui'
import { useAuth } from '@/context/AuthContext'
import { formatDate } from '@/lib/format'

export default function Profile() {
  const { user, tenant, refresh } = useAuth()
  const [name, setName] = useState(user?.name ?? '')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setNotice(null)
    setBusy(true)
    try {
      await api.updateProfile({
        name: name !== user?.name ? name : undefined,
        password: password || undefined,
      })
      setPassword('')
      await refresh()
      setNotice('Profil berhasil diperbarui.')
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Gagal memperbarui profil')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader title="Profil saya" description="Kelola informasi akun dan kata sandi Anda." />

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Informasi akun">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && <Alert tone="error">{error}</Alert>}
            {notice && <Alert tone="success">{notice}</Alert>}

            <Field label="Nama lengkap">
              <input className="input" value={name} minLength={2} onChange={(event) => setName(event.target.value)} />
            </Field>
            <Field label="Email" hint="Email tidak dapat diubah pada MVP ini.">
              <input className="input" value={user?.email ?? ''} disabled />
            </Field>
            <Field label="Password baru" hint="Kosongkan jika tidak ingin mengganti. Minimal 8 karakter.">
              <input
                className="input" type="password" value={password} minLength={8}
                onChange={(event) => setPassword(event.target.value)} placeholder="••••••••"
                autoComplete="new-password"
              />
            </Field>
            <button className="btn-primary" disabled={busy}>
              {busy ? 'Menyimpan…' : 'Simpan perubahan'}
            </button>
          </form>
        </Panel>

        <Panel title="Detail tenant">
          <dl className="divide-y divide-slate-100 text-sm">
            {[
              ['Peran', user?.role === 'admin_internal' ? 'Admin Internal' : 'User Tenant'],
              ['Perusahaan', tenant?.company_name ?? '—'],
              ['Paket', tenant?.plan_name ?? '—'],
              ['Status', tenant?.status ?? '—'],
              ['Kuota job / bulan', tenant ? String(tenant.monthly_job_quota) : '—'],
              ['Terdaftar sejak', formatDate(user?.created_at)],
            ].map(([term, detail]) => (
              <div key={term} className="flex justify-between gap-4 py-3">
                <dt className="text-slate-500">{term}</dt>
                <dd className="font-medium text-slate-900">{detail}</dd>
              </div>
            ))}
          </dl>
        </Panel>
      </div>
    </>
  )
}
