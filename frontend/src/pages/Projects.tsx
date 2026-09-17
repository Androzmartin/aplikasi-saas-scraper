import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, api } from '@/api/client'
import type { Project } from '@/api/types'
import { Alert, EmptyState, Field, PageHeader, Panel, Spinner } from '@/components/ui'
import { useAuth } from '@/context/AuthContext'
import { JABODETABEK_REGIONS, formatDate, regionLabel } from '@/lib/format'

export default function Projects() {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const { isAdmin } = useAuth()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', target_region: 'jakarta', description: '' })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function load() {
    setProjects(await api.listProjects())
    setLoading(false)
  }

  useEffect(() => {
    void load()
  }, [])

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await api.createProject({
        name: form.name,
        target_region: form.target_region,
        description: form.description || undefined,
      })
      setForm({ name: '', target_region: 'jakarta', description: '' })
      setShowForm(false)
      await load()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Gagal membuat project')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader
        title="Projects"
        description={
          isAdmin
            ? 'Semua project dari seluruh tenant, untuk pemantauan.'
            : 'Satu project mengelompokkan URL target dan lead hasil scraping.'
        }
        actions={
          // An internal admin has no tenant, so creating a project would fail.
          // Do not offer a button that cannot work.
          isAdmin ? undefined : (
            <button className="btn-primary" onClick={() => setShowForm((open) => !open)}>
              {showForm ? 'Tutup form' : 'Project baru'}
            </button>
          )
        }
      />

      {isAdmin && (
        <div className="mb-6">
          <Alert tone="info">
            Anda masuk sebagai admin internal. Akun ini memantau seluruh tenant dan tidak
            terhubung ke tenant manapun, jadi tidak bisa membuat project atau menjalankan
            scraping. Gunakan akun tenant untuk itu.
          </Alert>
        </div>
      )}

      {showForm && !isAdmin && (
        <div className="mb-6">
          <Panel title="Buat project baru">
            <form onSubmit={handleCreate} className="space-y-4">
              {error && <Alert tone="error">{error}</Alert>}
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Nama project">
                  <input
                    className="input" required minLength={2} value={form.name}
                    onChange={(event) => setForm({ ...form, name: event.target.value })}
                    placeholder="Kuliner Jakarta Selatan Q1"
                  />
                </Field>
                <Field label="Wilayah target">
                  <select
                    className="input" value={form.target_region}
                    onChange={(event) => setForm({ ...form, target_region: event.target.value })}
                  >
                    {JABODETABEK_REGIONS.map((region) => (
                      <option key={region} value={region}>{regionLabel(region)}</option>
                    ))}
                  </select>
                </Field>
              </div>
              <Field label="Deskripsi" hint="Opsional — catatan internal tentang target project ini.">
                <textarea
                  className="input" rows={2} maxLength={500} value={form.description}
                  onChange={(event) => setForm({ ...form, description: event.target.value })}
                  placeholder="Target: kafe dan restoran dengan website lama."
                />
              </Field>
              <div className="flex justify-end gap-2">
                <button type="button" className="btn-secondary" onClick={() => setShowForm(false)}>
                  Batal
                </button>
                <button type="submit" className="btn-primary" disabled={busy}>
                  {busy ? 'Menyimpan…' : 'Simpan project'}
                </button>
              </div>
            </form>
          </Panel>
        </div>
      )}

      <Panel bodyClassName="">
        {loading ? (
          <Spinner />
        ) : projects.length === 0 ? (
          <EmptyState
            title="Belum ada project"
            description="Buat project pertama Anda untuk mulai mengumpulkan lead UMKM."
            action={<button className="btn-primary" onClick={() => setShowForm(true)}>Buat project</button>}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="table-head">
                <tr>
                  <th className="px-5 py-3">Nama project</th>
                  <th className="px-5 py-3">Wilayah</th>
                  <th className="px-5 py-3">Lead</th>
                  <th className="px-5 py-3">Selesai</th>
                  <th className="px-5 py-3">Antrean</th>
                  <th className="px-5 py-3">Gagal</th>
                  <th className="px-5 py-3">Dibuat</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {projects.map((project) => {
                  const counts = project.job_counts
                  return (
                    <tr key={project.id} className="hover:bg-slate-50">
                      <td className="table-cell">
                        <Link to={`/projects/${project.id}`} className="font-medium text-slate-900 hover:underline">
                          {project.name}
                        </Link>
                        {project.description && (
                          <p className="mt-0.5 max-w-xs truncate text-xs text-slate-500">
                            {project.description}
                          </p>
                        )}
                      </td>
                      <td className="table-cell">{regionLabel(project.target_region)}</td>
                      <td className="table-cell tabular-nums">{project.lead_count}</td>
                      <td className="table-cell tabular-nums text-emerald-700">{counts.completed ?? 0}</td>
                      <td className="table-cell tabular-nums">
                        {(counts.pending ?? 0) + (counts.running ?? 0)}
                      </td>
                      <td className="table-cell tabular-nums text-red-600">{counts.failed ?? 0}</td>
                      <td className="table-cell text-slate-500">{formatDate(project.created_at)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  )
}
