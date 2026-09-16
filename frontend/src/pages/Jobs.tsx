import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, api } from '@/api/client'
import type { Job } from '@/api/types'
import { Alert, EmptyState, JobStatusBadge, PageHeader, Panel, Spinner, StatCard } from '@/components/ui'
import { JOB_STATUS_LABELS, formatRelative } from '@/lib/format'

export default function Jobs() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setJobs(await api.listJobs({ status: statusFilter || undefined, limit: 200 }))
      setError(null)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Gagal memuat job')
    } finally {
      setLoading(false)
    }
  }, [statusFilter])

  useEffect(() => {
    void load()
  }, [load])

  const hasActive = jobs.some((job) => job.status === 'pending' || job.status === 'running')
  useEffect(() => {
    if (!hasActive) return
    const timer = setInterval(() => void load(), 4000)
    return () => clearInterval(timer)
  }, [hasActive, load])

  const [notice, setNotice] = useState<string | null>(null)

  async function retryAllFailed() {
    setError(null)
    setNotice(null)
    try {
      const { requeued } = await api.retryFailedJobs()
      setNotice(
        requeued > 0
          ? `${requeued} job gagal dimasukkan kembali ke antrean.`
          : 'Tidak ada job gagal untuk diulang.',
      )
      await load()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Gagal mengulang job')
    }
  }

  async function retry(jobId: string) {
    try {
      await api.retryJob(jobId)
      await load()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Gagal mengulang job')
    }
  }

  const byStatus = (status: string) => jobs.filter((job) => job.status === status).length

  return (
    <>
      <PageHeader
        title="Scraping Jobs"
        description="Pantau antrean, status, dan kegagalan job scraping."
        actions={
          <>
            <button
              className="btn-secondary"
              onClick={() => void retryAllFailed()}
              disabled={byStatus('failed') === 0}
            >
              Ulangi semua yang gagal
            </button>
            <button className="btn-secondary" onClick={() => void load()}>Muat ulang</button>
          </>
        }
      />

      {error && <div className="mb-4"><Alert tone="error">{error}</Alert></div>}
      {notice && <div className="mb-4"><Alert tone="success">{notice}</Alert></div>}

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Menunggu" value={byStatus('pending')} />
        <StatCard label="Berjalan" value={byStatus('running')} />
        <StatCard label="Selesai" value={byStatus('completed')} />
        <StatCard label="Gagal" value={byStatus('failed')} />
      </div>

      <Panel
        actions={
          <select
            className="input w-auto" value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="">Semua status</option>
            {Object.entries(JOB_STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        }
        title="Daftar job"
        description={hasActive ? 'Diperbarui otomatis setiap 4 detik.' : undefined}
        bodyClassName=""
      >
        {loading ? (
          <Spinner />
        ) : jobs.length === 0 ? (
          <EmptyState title="Tidak ada job" description="Job akan muncul setelah Anda submit URL di sebuah project." />
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="table-head">
                <tr>
                  <th className="px-5 py-3">URL sumber</th>
                  <th className="px-5 py-3">Project</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Halaman</th>
                  <th className="px-5 py-3">Percobaan</th>
                  <th className="px-5 py-3">Dibuat</th>
                  <th className="px-5 py-3">Aksi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {jobs.map((job) => (
                  <tr key={job.id} className="hover:bg-slate-50">
                    <td className="table-cell max-w-xs">
                      <span className="block truncate font-mono text-xs">{job.source_url}</span>
                      {job.error_message && (
                        <span className="mt-1 block max-w-xs truncate text-xs text-red-600" title={job.error_message}>
                          {job.error_message}
                        </span>
                      )}
                    </td>
                    <td className="table-cell">
                      {job.project_id ? (
                        <Link to={`/projects/${job.project_id}`} className="hover:underline">
                          {job.project_name ?? '—'}
                        </Link>
                      ) : '—'}
                    </td>
                    <td className="table-cell"><JobStatusBadge status={job.status} /></td>
                    <td className="table-cell tabular-nums">{job.pages_crawled || '—'}</td>
                    <td className="table-cell tabular-nums">{job.attempts}</td>
                    <td className="table-cell text-slate-500">{formatRelative(job.created_at)}</td>
                    <td className="table-cell">
                      {job.lead_id ? (
                        <Link to={`/leads/${job.lead_id}`} className="text-sm font-medium text-navy-700 hover:underline">
                          Lihat lead
                        </Link>
                      ) : job.status === 'failed' ? (
                        <button className="text-sm font-medium text-navy-700 hover:underline" onClick={() => void retry(job.id)}>
                          Ulangi
                        </button>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  )
}
