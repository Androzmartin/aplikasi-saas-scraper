import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, api } from '@/api/client'
import type { Job, Project } from '@/api/types'
import { Alert, EmptyState, JobStatusBadge, PageHeader, Panel, Spinner, StatCard } from '@/components/ui'
import { formatRelative, regionLabel } from '@/lib/format'

const POLL_INTERVAL_MS = 4000

export default function ProjectDetail() {
  const { projectId = '' } = useParams()
  const [project, setProject] = useState<Project | null>(null)
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [urlText, setUrlText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<{ created: number; rejected: { url: string; reason: string }[] } | null>(null)
  const [uploadName, setUploadName] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const refresh = useCallback(async () => {
    const [projectData, jobList] = await Promise.all([
      api.getProject(projectId),
      api.listJobs({ project_id: projectId, limit: 200 }),
    ])
    setProject(projectData)
    setJobs(jobList)
  }, [projectId])

  useEffect(() => {
    let active = true
    void refresh().finally(() => {
      if (active) setLoading(false)
    })
    return () => {
      active = false
    }
  }, [refresh])

  // Keep the job table live while anything is still queued or running.
  const hasActiveJobs = jobs.some((job) => job.status === 'pending' || job.status === 'running')
  useEffect(() => {
    if (!hasActiveJobs) return
    const timer = setInterval(() => void refresh(), POLL_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [hasActiveJobs, refresh])

  const urlCount = urlText
    .split(/[\n,]/)
    .map((line) => line.trim())
    .filter(Boolean).length

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setResult(null)
    setSubmitting(true)
    try {
      const urls = urlText.split(/[\n,]/).map((line) => line.trim()).filter(Boolean)
      const response = await api.createJobs(projectId, urls)
      setResult({ created: response.created.length, rejected: response.rejected })
      if (response.created.length > 0) setUrlText('')
      await refresh()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Gagal mengirim URL')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    setUploadName(file.name)
    const text = await file.text()
    // Accept a plain URL list or a one-column CSV export.
    const lines = text
      .split(/\r?\n/)
      .map((line) => line.split(',')[0].trim().replace(/^"|"$/g, ''))
      .filter((line) => line && !/^(website|url|domain)$/i.test(line))
    setUrlText((previous) => (previous ? `${previous}\n${lines.join('\n')}` : lines.join('\n')))
    if (fileInput.current) fileInput.current.value = ''
  }

  async function handleRetry(jobId: string) {
    try {
      await api.retryJob(jobId)
      await refresh()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Gagal mengulang job')
    }
  }

  if (loading) return <Spinner />
  if (!project) return <Alert tone="error">Project tidak ditemukan.</Alert>

  const counts = project.job_counts

  return (
    <>
      <PageHeader
        title={project.name}
        description={`Wilayah target: ${regionLabel(project.target_region)}${project.description ? ` · ${project.description}` : ''}`}
        actions={
          <Link to={`/leads?project_id=${project.id}`} className="btn-secondary">
            Lihat lead project ini
          </Link>
        }
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Lead terkumpul" value={project.lead_count} />
        <StatCard label="Job selesai" value={counts.completed ?? 0} />
        <StatCard label="Dalam antrean" value={(counts.pending ?? 0) + (counts.running ?? 0)} />
        <StatCard label="Job gagal" value={counts.failed ?? 0} />
      </div>

      <div className="mb-6">
        <Panel
          title="Input URL target"
          description="Satu URL per baris, atau pisahkan dengan koma. Bisa juga unggah file .txt/.csv."
        >
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && <Alert tone="error">{error}</Alert>}
            {result && (
              <Alert tone={result.created > 0 ? 'success' : 'warning'}>
                <p className="font-medium">
                  {result.created} URL masuk antrean
                  {result.rejected.length > 0 && `, ${result.rejected.length} ditolak`}
                </p>
                {result.rejected.length > 0 && (
                  <ul className="mt-2 max-h-32 space-y-1 overflow-y-auto text-xs">
                    {result.rejected.map((item) => (
                      <li key={`${item.url}-${item.reason}`}>
                        <span className="font-mono">{item.url}</span> — {item.reason}
                      </li>
                    ))}
                  </ul>
                )}
              </Alert>
            )}

            <textarea
              className="input font-mono text-xs"
              rows={8}
              value={urlText}
              onChange={(event) => setUrlText(event.target.value)}
              placeholder={'https://warungkopisenja.co.id\nhttps://butikhijabjakarta.com\nbengkelmotorjaya.id'}
            />

            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <input
                  ref={fileInput} type="file" accept=".txt,.csv"
                  onChange={handleFile} className="hidden" id="bulk-upload"
                />
                <label htmlFor="bulk-upload" className="btn-secondary cursor-pointer">
                  Unggah file
                </label>
                <span className="text-xs text-slate-500">
                  {uploadName ? `${uploadName} dimuat` : 'Format .txt atau .csv satu kolom'}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-sm tabular-nums text-slate-500">{urlCount} URL siap dikirim</span>
                <button type="submit" className="btn-primary" disabled={submitting || urlCount === 0}>
                  {submitting ? 'Mengirim…' : 'Jalankan scraping'}
                </button>
              </div>
            </div>
          </form>
        </Panel>
      </div>

      <Panel
        title="Status job"
        description={hasActiveJobs ? 'Diperbarui otomatis setiap 4 detik.' : undefined}
        actions={
          <button className="btn-secondary" onClick={() => void refresh()}>
            Muat ulang
          </button>
        }
        bodyClassName=""
      >
        {jobs.length === 0 ? (
          <EmptyState title="Belum ada job" description="Masukkan URL di atas untuk memulai scraping." />
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="table-head">
                <tr>
                  <th className="px-5 py-3">URL sumber</th>
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
                      <span className="block truncate font-mono text-xs text-slate-700">{job.source_url}</span>
                      {job.error_message && (
                        <span className="mt-1 block max-w-xs truncate text-xs text-red-600" title={job.error_message}>
                          {job.error_message}
                        </span>
                      )}
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
                        <button className="text-sm font-medium text-navy-700 hover:underline" onClick={() => void handleRetry(job.id)}>
                          Ulangi
                        </button>
                      ) : (
                        <span className="text-sm text-slate-400">—</span>
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
