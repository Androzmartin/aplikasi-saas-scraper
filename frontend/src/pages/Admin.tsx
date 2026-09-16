import { useCallback, useEffect, useState } from 'react'
import { ApiError, api } from '@/api/client'
import type { ActivityLog, AdminRedesign, AdminStats, Job, Project, Tenant, User } from '@/api/types'
import { Alert, EmptyState, JobStatusBadge, PageHeader, Panel, Spinner, StatCard } from '@/components/ui'
import { formatDate, formatRelative, regionLabel } from '@/lib/format'

type Tab = 'overview' | 'tenants' | 'users' | 'projects' | 'jobs' | 'redesigns' | 'activity'

const TABS: { id: Tab; label: string }[] = [
  { id: 'overview', label: 'Ringkasan' },
  { id: 'tenants', label: 'Tenants' },
  { id: 'users', label: 'Users' },
  { id: 'projects', label: 'Projects' },
  { id: 'jobs', label: 'Jobs' },
  { id: 'redesigns', label: 'Review redesign' },
  { id: 'activity', label: 'Audit log' },
]

export default function Admin() {
  const [tab, setTab] = useState<Tab>('overview')
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [jobs, setJobs] = useState<Job[]>([])
  const [errors, setErrors] = useState<Job[]>([])
  const [activity, setActivity] = useState<ActivityLog[]>([])
  const [redesigns, setRedesigns] = useState<AdminRedesign[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [statsData, errorJobs] = await Promise.all([api.adminStats(), api.adminErrors()])
      setStats(statsData)
      setErrors(errorJobs)

      if (tab === 'tenants') setTenants(await api.adminTenants())
      if (tab === 'users') setUsers(await api.adminUsers())
      if (tab === 'projects') setProjects(await api.adminProjects())
      if (tab === 'jobs') setJobs(await api.adminJobs())
      if (tab === 'redesigns') setRedesigns(await api.adminRedesigns())
      if (tab === 'activity') setActivity(await api.adminActivity())
      setError(null)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Gagal memuat data admin')
    } finally {
      setLoading(false)
    }
  }, [tab])

  useEffect(() => {
    void load()
  }, [load])

  async function decide(id: string, status: 'approved' | 'rejected') {
    const note = status === 'rejected'
      ? window.prompt('Alasan penolakan (opsional, tampil ke user):') ?? undefined
      : undefined
    try {
      await api.decideRedesign(id, status, note)
      setRedesigns(await api.adminRedesigns())
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Gagal memproses persetujuan')
    }
  }

  async function toggleTenant(tenant: Tenant) {
    try {
      await api.setTenantStatus(tenant.id, tenant.status === 'active' ? 'suspended' : 'active')
      setTenants(await api.adminTenants())
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Gagal mengubah status tenant')
    }
  }

  return (
    <>
      <PageHeader
        title="Admin Internal"
        description="Monitoring operasional SaaS: tenant, pengguna, job, dan jejak aktivitas."
        actions={<button className="btn-secondary" onClick={() => void load()}>Muat ulang</button>}
      />

      {error && <div className="mb-4"><Alert tone="error">{error}</Alert></div>}

      <div className="mb-6 flex flex-wrap gap-1 border-b border-slate-200">
        {TABS.map((item) => (
          <button
            key={item.id}
            onClick={() => setTab(item.id)}
            className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-medium transition ${
              tab === item.id
                ? 'border-navy-900 text-navy-900'
                : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {loading ? (
        <Spinner />
      ) : tab === 'overview' ? (
        <>
          <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <StatCard label="Tenants" value={stats?.tenants ?? 0} />
            <StatCard label="Users" value={stats?.users ?? 0} />
            <StatCard label="Projects" value={stats?.projects ?? 0} />
            <StatCard label="Leads" value={stats?.leads ?? 0} />
            <StatCard label="Output redesign" value={stats?.redesigns ?? 0} />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Panel title="Status job keseluruhan">
              <dl className="space-y-3">
                {Object.entries(stats?.jobs_by_status ?? {}).map(([status, count]) => (
                  <div key={status} className="flex items-center justify-between">
                    <dt><JobStatusBadge status={status} /></dt>
                    <dd className="text-sm font-semibold tabular-nums text-slate-900">{count}</dd>
                  </div>
                ))}
                {Object.keys(stats?.jobs_by_status ?? {}).length === 0 && (
                  <p className="text-sm text-slate-500">Belum ada job yang tercatat.</p>
                )}
              </dl>
            </Panel>

            <Panel title={`Error terbaru (${errors.length})`} bodyClassName="">
              {errors.length === 0 ? (
                <EmptyState title="Tidak ada error" description="Semua job berjalan tanpa kegagalan." />
              ) : (
                <ul className="max-h-80 divide-y divide-slate-100 overflow-y-auto">
                  {errors.slice(0, 20).map((job) => (
                    <li key={job.id} className="px-5 py-3">
                      <p className="truncate font-mono text-xs text-slate-700">{job.source_url}</p>
                      <p className="mt-1 text-xs text-red-600">{job.error_message}</p>
                      <p className="mt-1 text-xs text-slate-400">{formatRelative(job.completed_at)}</p>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>
        </>
      ) : (
        <Panel bodyClassName="">
          <div className="overflow-x-auto">
            {tab === 'tenants' && (
              <table className="min-w-full divide-y divide-slate-200">
                <thead className="table-head">
                  <tr>
                    <th className="px-5 py-3">Perusahaan</th>
                    <th className="px-5 py-3">Paket</th>
                    <th className="px-5 py-3">Kuota</th>
                    <th className="px-5 py-3">Status</th>
                    <th className="px-5 py-3">Dibuat</th>
                    <th className="px-5 py-3">Aksi</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {tenants.map((tenant) => (
                    <tr key={tenant.id} className="hover:bg-slate-50">
                      <td className="table-cell font-medium text-slate-900">{tenant.company_name}</td>
                      <td className="table-cell">{tenant.plan_name}</td>
                      <td className="table-cell tabular-nums">{tenant.monthly_job_quota}</td>
                      <td className="table-cell">
                        <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                          tenant.status === 'active'
                            ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200'
                            : 'bg-red-50 text-red-700 ring-1 ring-red-200'
                        }`}>
                          {tenant.status === 'active' ? 'Aktif' : 'Ditangguhkan'}
                        </span>
                      </td>
                      <td className="table-cell text-slate-500">{formatDate(tenant.created_at)}</td>
                      <td className="table-cell">
                        <button
                          className="text-sm font-medium text-navy-700 hover:underline"
                          onClick={() => void toggleTenant(tenant)}
                        >
                          {tenant.status === 'active' ? 'Tangguhkan' : 'Aktifkan'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {tab === 'users' && (
              <table className="min-w-full divide-y divide-slate-200">
                <thead className="table-head">
                  <tr>
                    <th className="px-5 py-3">Nama</th>
                    <th className="px-5 py-3">Email</th>
                    <th className="px-5 py-3">Peran</th>
                    <th className="px-5 py-3">Terdaftar</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {users.map((user) => (
                    <tr key={user.id} className="hover:bg-slate-50">
                      <td className="table-cell font-medium text-slate-900">{user.name}</td>
                      <td className="table-cell">{user.email}</td>
                      <td className="table-cell">
                        {user.role === 'admin_internal' ? 'Admin Internal' : 'User Tenant'}
                      </td>
                      <td className="table-cell text-slate-500">{formatDate(user.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {tab === 'projects' && (
              <table className="min-w-full divide-y divide-slate-200">
                <thead className="table-head">
                  <tr>
                    <th className="px-5 py-3">Project</th>
                    <th className="px-5 py-3">Wilayah</th>
                    <th className="px-5 py-3">Lead</th>
                    <th className="px-5 py-3">Dibuat</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {projects.map((project) => (
                    <tr key={project.id} className="hover:bg-slate-50">
                      <td className="table-cell font-medium text-slate-900">{project.name}</td>
                      <td className="table-cell">{regionLabel(project.target_region)}</td>
                      <td className="table-cell tabular-nums">{project.lead_count}</td>
                      <td className="table-cell text-slate-500">{formatDate(project.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {tab === 'jobs' && (
              <table className="min-w-full divide-y divide-slate-200">
                <thead className="table-head">
                  <tr>
                    <th className="px-5 py-3">URL</th>
                    <th className="px-5 py-3">Project</th>
                    <th className="px-5 py-3">Status</th>
                    <th className="px-5 py-3">Percobaan</th>
                    <th className="px-5 py-3">Dibuat</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {jobs.map((job) => (
                    <tr key={job.id} className="hover:bg-slate-50">
                      <td className="table-cell max-w-xs truncate font-mono text-xs">{job.source_url}</td>
                      <td className="table-cell">{job.project_name ?? '—'}</td>
                      <td className="table-cell"><JobStatusBadge status={job.status} /></td>
                      <td className="table-cell tabular-nums">{job.attempts}</td>
                      <td className="table-cell text-slate-500">{formatRelative(job.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {tab === 'redesigns' && (
              redesigns.length === 0 ? (
                <EmptyState
                  title="Belum ada output redesign"
                  description="Hasil generate redesign dari semua tenant akan muncul di sini."
                />
              ) : (
              <table className="min-w-full divide-y divide-slate-200">
                <thead className="table-head">
                  <tr>
                    <th className="px-5 py-3">Bisnis</th>
                    <th className="px-5 py-3">Headline</th>
                    <th className="px-5 py-3">Versi</th>
                    <th className="px-5 py-3">Status</th>
                    <th className="px-5 py-3">Dibuat</th>
                    <th className="px-5 py-3">Aksi</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {redesigns.map((item) => (
                    <tr key={item.id} className="hover:bg-slate-50">
                      <td className="table-cell">
                        <span className="block font-medium text-slate-900">
                          {item.business_name ?? '—'}
                        </span>
                        <span className="block max-w-xs truncate text-xs text-slate-500">
                          {item.website_url ?? ''}
                        </span>
                      </td>
                      <td className="table-cell w-full max-w-0">
                        <span className="block truncate">{item.headline}</span>
                        {item.approval_note && (
                          <span className="block truncate text-xs text-slate-500">
                            Catatan: {item.approval_note}
                          </span>
                        )}
                      </td>
                      <td className="table-cell tabular-nums">
                        <span className="block">v{item.version}</span>
                        <span className="block text-xs text-slate-400">
                          {item.generated_with.startsWith('ai:') ? 'AI' : 'Template'}
                        </span>
                      </td>
                      <td className="table-cell">
                        <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                          item.approval_status === 'approved'
                            ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200'
                            : item.approval_status === 'rejected'
                              ? 'bg-red-50 text-red-700 ring-1 ring-red-200'
                              : 'bg-amber-50 text-amber-700 ring-1 ring-amber-200'
                        }`}>
                          {item.approval_status === 'approved'
                            ? 'Disetujui'
                            : item.approval_status === 'rejected'
                              ? 'Ditolak'
                              : 'Menunggu'}
                        </span>
                      </td>
                      <td className="table-cell text-slate-500">{formatDate(item.created_at)}</td>
                      <td className="table-cell">
                        <div className="flex gap-3">
                          {item.approval_status !== 'approved' && (
                            <button
                              className="text-sm font-medium text-emerald-700 hover:underline"
                              onClick={() => void decide(item.id, 'approved')}
                            >
                              Setujui
                            </button>
                          )}
                          {item.approval_status !== 'rejected' && (
                            <button
                              className="text-sm font-medium text-red-600 hover:underline"
                              onClick={() => void decide(item.id, 'rejected')}
                            >
                              Tolak
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              )
            )}

            {tab === 'activity' && (
              <table className="min-w-full divide-y divide-slate-200">
                <thead className="table-head">
                  <tr>
                    <th className="px-5 py-3">Aksi</th>
                    <th className="px-5 py-3">Target</th>
                    <th className="px-5 py-3">Detail</th>
                    <th className="px-5 py-3">Waktu</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {activity.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-50">
                      <td className="table-cell font-medium text-slate-900">{log.action}</td>
                      <td className="table-cell max-w-xs truncate">{log.target ?? '—'}</td>
                      <td className="table-cell text-slate-500">{log.detail ?? '—'}</td>
                      <td className="table-cell text-slate-500">{formatDate(log.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </Panel>
      )}
    </>
  )
}
