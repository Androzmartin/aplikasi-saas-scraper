import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/api/client'
import type { Job, Lead, Project } from '@/api/types'
import { JobStatusBadge, PageHeader, Panel, ScoreBadge, Spinner, StatCard, EmptyState } from '@/components/ui'
import { formatRelative, regionLabel } from '@/lib/format'

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([])
  const [jobs, setJobs] = useState<Job[]>([])
  const [leads, setLeads] = useState<Lead[]>([])
  const [leadTotal, setLeadTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    async function load() {
      try {
        const [projectList, jobList, leadPage] = await Promise.all([
          api.listProjects(),
          api.listJobs({ limit: 8 }),
          api.listLeads({ page_size: 8 }),
        ])
        if (!active) return
        setProjects(projectList)
        setJobs(jobList)
        setLeads(leadPage.items)
        setLeadTotal(leadPage.total)
      } finally {
        if (active) setLoading(false)
      }
    }
    void load()
    return () => {
      active = false
    }
  }, [])

  if (loading) return <Spinner />

  const activeJobs = jobs.filter((job) => job.status === 'pending' || job.status === 'running').length
  const failedJobs = jobs.filter((job) => job.status === 'failed').length
  const scored = leads.filter((lead) => lead.audit_score !== null)
  const averageScore = scored.length
    ? Math.round(scored.reduce((sum, lead) => sum + (lead.audit_score ?? 0), 0) / scored.length)
    : null

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Ringkasan project, antrean scraping, dan lead terbaru."
        actions={
          <Link to="/projects" className="btn-primary">
            Project baru
          </Link>
        }
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total project" value={projects.length} />
        <StatCard label="Total lead" value={leadTotal} />
        <StatCard label="Job aktif" value={activeJobs} hint={failedJobs ? `${failedJobs} gagal` : undefined} />
        <StatCard label="Rata-rata skor audit" value={averageScore ?? '—'} hint="Dari lead terbaru" />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel
          title="Lead terbaru"
          actions={<Link to="/leads" className="text-sm font-medium text-navy-700 hover:underline">Lihat semua</Link>}
          bodyClassName=""
        >
          {leads.length === 0 ? (
            <EmptyState
              title="Belum ada lead"
              description="Buat project dan jalankan scraping untuk mulai mengumpulkan lead."
              action={<Link to="/projects" className="btn-primary">Buat project</Link>}
            />
          ) : (
            <ul className="divide-y divide-slate-100">
              {leads.map((lead) => (
                <li key={lead.id}>
                  <Link to={`/leads/${lead.id}`} className="flex items-center justify-between gap-4 px-5 py-3.5 hover:bg-slate-50">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-slate-900">
                        {lead.business_name ?? lead.website_url}
                      </p>
                      <p className="truncate text-xs text-slate-500">
                        {regionLabel(lead.region)} · {lead.whatsapp_number ?? lead.phone_number ?? 'Tanpa kontak'}
                      </p>
                    </div>
                    <ScoreBadge score={lead.audit_score} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel
          title="Aktivitas job"
          actions={<Link to="/jobs" className="text-sm font-medium text-navy-700 hover:underline">Lihat semua</Link>}
          bodyClassName=""
        >
          {jobs.length === 0 ? (
            <EmptyState title="Belum ada job" description="Job scraping akan muncul di sini setelah Anda submit URL." />
          ) : (
            <ul className="divide-y divide-slate-100">
              {jobs.map((job) => (
                <li key={job.id} className="flex items-center justify-between gap-4 px-5 py-3.5">
                  <div className="min-w-0">
                    <p className="truncate text-sm text-slate-900">{job.source_url}</p>
                    <p className="truncate text-xs text-slate-500">
                      {job.project_name ?? '—'} · {formatRelative(job.created_at)}
                    </p>
                  </div>
                  <JobStatusBadge status={job.status} />
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      {projects.length > 0 && (
        <div className="mt-6">
          <Panel title="Project aktif" bodyClassName="">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200">
                <thead className="table-head">
                  <tr>
                    <th className="px-5 py-3">Nama project</th>
                    <th className="px-5 py-3">Wilayah target</th>
                    <th className="px-5 py-3">Lead</th>
                    <th className="px-5 py-3">Job</th>
                    <th className="px-5 py-3">Dibuat</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {projects.slice(0, 5).map((project) => (
                    <tr key={project.id} className="hover:bg-slate-50">
                      <td className="table-cell font-medium text-slate-900">
                        <Link to={`/projects/${project.id}`} className="hover:underline">{project.name}</Link>
                      </td>
                      <td className="table-cell">{regionLabel(project.target_region)}</td>
                      <td className="table-cell tabular-nums">{project.lead_count}</td>
                      <td className="table-cell tabular-nums">
                        {Object.values(project.job_counts).reduce((a, b) => a + b, 0)}
                      </td>
                      <td className="table-cell text-slate-500">{formatRelative(project.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
      )}
    </>
  )
}
