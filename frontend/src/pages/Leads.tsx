import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ApiError, api } from '@/api/client'
import type { Lead, Project } from '@/api/types'
import { Alert, EmptyState, LeadStatusBadge, PageHeader, Panel, ScoreBadge, Spinner } from '@/components/ui'
import { LEAD_STATUS_LABELS, formatDate, regionLabel } from '@/lib/format'

const PAGE_SIZE = 25

export default function Leads() {
  const [params, setParams] = useSearchParams()
  const [leads, setLeads] = useState<Lead[]>([])
  const [total, setTotal] = useState(0)
  const [projects, setProjects] = useState<Project[]>([])
  const [facets, setFacets] = useState<{ region: string; count: number }[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)
  const [searchDraft, setSearchDraft] = useState(params.get('search') ?? '')

  const filters = useMemo(
    () => ({
      project_id: params.get('project_id') ?? undefined,
      region: params.get('region') ?? undefined,
      status: params.get('status') ?? undefined,
      search: params.get('search') ?? undefined,
      min_score: params.get('min_score') ? Number(params.get('min_score')) : undefined,
      max_score: params.get('max_score') ? Number(params.get('max_score')) : undefined,
      page: Number(params.get('page') ?? '1'),
    }),
    [params],
  )

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [page, regionFacets] = await Promise.all([
        api.listLeads({ ...filters, page_size: PAGE_SIZE }),
        api.regionFacets(filters.project_id),
      ])
      setLeads(page.items)
      setTotal(page.total)
      setFacets(regionFacets)
      setError(null)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Gagal memuat lead')
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    void api.listProjects().then(setProjects)
  }, [])

  // Debounce the search box so typing does not fire a request per keystroke.
  useEffect(() => {
    const timer = setTimeout(() => {
      if ((params.get('search') ?? '') === searchDraft) return
      updateFilter('search', searchDraft || null)
    }, 350)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchDraft])

  function updateFilter(key: string, value: string | null) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key !== 'page') next.delete('page')
    setParams(next, { replace: true })
  }

  async function handleExport() {
    setExporting(true)
    try {
      await api.exportLeadsCsv(filters)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Gagal mengekspor CSV')
    } finally {
      setExporting(false)
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const activeFilters = ['project_id', 'region', 'status', 'min_score', 'max_score', 'search'].filter((key) =>
    params.get(key),
  ).length

  return (
    <>
      <PageHeader
        title="Leads"
        description={`${total} lead ditemukan${activeFilters ? ` dengan ${activeFilters} filter aktif` : ''}.`}
        actions={
          <button className="btn-primary" onClick={handleExport} disabled={exporting || total === 0}>
            {exporting ? 'Menyiapkan…' : 'Export CSV'}
          </button>
        }
      />

      {error && <div className="mb-4"><Alert tone="error">{error}</Alert></div>}

      <div className="mb-6">
        <Panel>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <div className="lg:col-span-2">
              <label className="label">Cari</label>
              <input
                className="input"
                value={searchDraft}
                onChange={(event) => setSearchDraft(event.target.value)}
                placeholder="Nama bisnis, website, alamat, kontak…"
              />
            </div>
            <div>
              <label className="label">Project</label>
              <select
                className="input" value={params.get('project_id') ?? ''}
                onChange={(event) => updateFilter('project_id', event.target.value || null)}
              >
                <option value="">Semua project</option>
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>{project.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Wilayah</label>
              <select
                className="input" value={params.get('region') ?? ''}
                onChange={(event) => updateFilter('region', event.target.value || null)}
              >
                <option value="">Semua wilayah</option>
                {facets.map((facet) => (
                  <option key={facet.region} value={facet.region}>
                    {regionLabel(facet.region)} ({facet.count})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Status</label>
              <select
                className="input" value={params.get('status') ?? ''}
                onChange={(event) => updateFilter('status', event.target.value || null)}
              >
                <option value="">Semua status</option>
                {Object.entries(LEAD_STATUS_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-slate-100 pt-4">
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Peluang redesign
            </span>
            {[
              { label: 'Semua', value: null },
              { label: 'Skor < 40 (prioritas tinggi)', value: '39' },
              { label: 'Skor < 60', value: '59' },
            ].map((preset) => (
              <button
                key={preset.label}
                className={`rounded-full px-3 py-1 text-xs font-medium ${
                  (params.get('max_score') ?? null) === preset.value
                    ? 'bg-navy-900 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
                onClick={() => updateFilter('max_score', preset.value)}
              >
                {preset.label}
              </button>
            ))}
            {activeFilters > 0 && (
              <button
                className="ml-auto text-xs font-medium text-navy-700 hover:underline"
                onClick={() => {
                  setSearchDraft('')
                  setParams(new URLSearchParams(), { replace: true })
                }}
              >
                Reset filter
              </button>
            )}
          </div>
        </Panel>
      </div>

      <Panel bodyClassName="">
        {loading ? (
          <Spinner />
        ) : leads.length === 0 ? (
          <EmptyState
            title="Tidak ada lead yang cocok"
            description="Ubah filter pencarian, atau jalankan scraping pada project Anda."
            action={<Link to="/projects" className="btn-primary">Ke halaman project</Link>}
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200">
                <thead className="table-head">
                  <tr>
                    <th className="px-5 py-3">Bisnis</th>
                    <th className="px-5 py-3">Kontak</th>
                    <th className="px-5 py-3">Wilayah</th>
                    <th className="px-5 py-3">Skor</th>
                    <th className="px-5 py-3">Status</th>
                    <th className="px-5 py-3">Redesign</th>
                    <th className="px-5 py-3">Outreach</th>
                    <th className="px-5 py-3">Ditemukan</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {leads.map((lead) => (
                    <tr key={lead.id} className="hover:bg-slate-50">
                      <td className="table-cell max-w-xs">
                        <Link to={`/leads/${lead.id}`} className="block truncate font-medium text-slate-900 hover:underline">
                          {lead.business_name ?? '(tanpa nama)'}
                        </Link>
                        <span className="block max-w-xs truncate text-xs text-slate-500">
                          {lead.website_url}
                        </span>
                      </td>
                      <td className="table-cell">
                        {lead.whatsapp_number ? (
                          <span className="block text-slate-900">{lead.whatsapp_number}</span>
                        ) : lead.phone_number ? (
                          <span className="block text-slate-900">{lead.phone_number}</span>
                        ) : (
                          <span className="block text-slate-400">Tanpa nomor</span>
                        )}
                        <span className="block max-w-[14rem] truncate text-xs text-slate-500">
                          {lead.email ?? '—'}
                        </span>
                      </td>
                      <td className="table-cell">{regionLabel(lead.region)}</td>
                      <td className="table-cell"><ScoreBadge score={lead.audit_score} /></td>
                      <td className="table-cell"><LeadStatusBadge status={lead.status} /></td>
                      <td className="table-cell">
                        {lead.has_redesign ? (
                          <span className="text-xs font-medium text-emerald-700">Tersedia</span>
                        ) : (
                          <span className="text-xs text-slate-400">Belum</span>
                        )}
                      </td>
                      <td className="table-cell">
                        {lead.outreach_sent_at ? (
                          <span className="text-xs font-medium text-slate-700">
                            {lead.outreach_channel === 'email' ? 'Email' : 'WhatsApp'}
                          </span>
                        ) : (
                          <span className="text-xs text-slate-400">Belum</span>
                        )}
                      </td>
                      <td className="table-cell text-slate-500">{formatDate(lead.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {totalPages > 1 && (
              <div className="flex items-center justify-between border-t border-slate-200 px-5 py-3">
                <p className="text-sm text-slate-500">
                  Halaman <span className="tabular-nums">{filters.page}</span> dari{' '}
                  <span className="tabular-nums">{totalPages}</span>
                </p>
                <div className="flex gap-2">
                  <button
                    className="btn-secondary" disabled={filters.page <= 1}
                    onClick={() => updateFilter('page', String(filters.page - 1))}
                  >
                    Sebelumnya
                  </button>
                  <button
                    className="btn-secondary" disabled={filters.page >= totalPages}
                    onClick={() => updateFilter('page', String(filters.page + 1))}
                  >
                    Berikutnya
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </Panel>
    </>
  )
}
