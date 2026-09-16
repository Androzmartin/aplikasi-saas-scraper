import { useCallback, useEffect, useState } from 'react'
import { ApiError, api } from '@/api/client'
import type { AnalyticsOverview, Project } from '@/api/types'
import { HorizontalBars, TrendChart } from '@/components/charts'
import { Alert, PageHeader, Panel, Spinner, StatCard } from '@/components/ui'

const RANGES = [
  { value: 30, label: '30 hari' },
  { value: 60, label: '60 hari' },
  { value: 90, label: '90 hari' },
]

export default function Analytics() {
  const [data, setData] = useState<AnalyticsOverview | null>(null)
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [days, setDays] = useState(30)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setData(await api.analyticsOverview({ project_id: projectId || undefined, days }))
      setError(null)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Gagal memuat analitik')
    } finally {
      setLoading(false)
    }
  }, [projectId, days])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    void api.listProjects().then(setProjects).catch(() => setProjects([]))
  }, [])

  return (
    <>
      <PageHeader
        title="Analitik"
        description="Sebaran peluang redesign dan perjalanan lead dari ditemukan sampai qualified."
      />

      {error && <div className="mb-4"><Alert tone="error">{error}</Alert></div>}

      {/* Filters in one row above the charts. */}
      <div className="mb-6 flex flex-wrap items-end gap-3">
        <div>
          <label className="label" htmlFor="an-project">Project</label>
          <select
            id="an-project" className="input w-auto min-w-[14rem]"
            value={projectId} onChange={(event) => setProjectId(event.target.value)}
          >
            <option value="">Semua project</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>{project.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="an-range">Rentang tren</label>
          <select
            id="an-range" className="input w-auto"
            value={days} onChange={(event) => setDays(Number(event.target.value))}
          >
            {RANGES.map((range) => (
              <option key={range.value} value={range.value}>{range.label}</option>
            ))}
          </select>
        </div>
      </div>

      {loading || !data ? (
        <Spinner />
      ) : (
        <>
          <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Total lead" value={data.total_leads} />
            <StatCard
              label="Rata-rata skor audit"
              value={data.average_score ?? '—'}
              hint={`${data.scored_leads} lead sudah diaudit`}
            />
            <StatCard
              label="Outreach terkirim"
              value={data.outreach_sent}
              hint={`${data.contact_rate}% dari total lead, dikirim lewat aplikasi`}
            />
            <StatCard
              label="Lead punya redesign"
              value={data.redesigns}
              hint={`${data.qualified_rate}% lead berstatus qualified`}
            />
          </div>

          <div className="mb-6">
            <Panel
              title="Tren lead masuk"
              description={`Jumlah lead baru per hari, ${data.days} hari terakhir.`}
            >
              <TrendChart data={data.trend} />
            </Panel>
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <Panel
              title="Perjalanan lead"
              description="Berapa banyak yang sampai ke tiap tahap."
            >
              <HorizontalBars data={data.funnel} ordinal unit="Lead" />
            </Panel>

            <Panel
              title="Peluang redesign"
              description="Semakin rendah skor, semakin besar peluangnya."
            >
              <HorizontalBars
                data={data.score_bands}
                ordinal
                unit="Lead"
                emptyText="Belum ada lead yang diaudit."
              />
            </Panel>

            <Panel title="Sebaran wilayah" description="Sepuluh wilayah teratas.">
              <HorizontalBars data={data.regions} unit="Lead" />
            </Panel>
          </div>
        </>
      )}
    </>
  )
}
