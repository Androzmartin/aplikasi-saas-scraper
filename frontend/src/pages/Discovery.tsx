import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, api } from '@/api/client'
import type { DiscoveredPlace, DiscoveryOptions, DiscoveryResult, Project } from '@/api/types'
import { Alert, EmptyState, Field, PageHeader, Panel, Spinner } from '@/components/ui'

export default function Discovery() {
  const navigate = useNavigate()
  const [options, setOptions] = useState<DiscoveryOptions | null>(null)
  const [projects, setProjects] = useState<Project[]>([])
  const [region, setRegion] = useState('jakarta_utara')
  const [category, setCategory] = useState('kuliner')
  const [provider, setProvider] = useState('osm')
  const [keyword, setKeyword] = useState('')
  const [maxRating, setMaxRating] = useState('')
  const [projectId, setProjectId] = useState('')
  const [result, setResult] = useState<DiscoveryResult | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [searching, setSearching] = useState(false)
  const [importing, setImporting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    void api.discoveryOptions().then(setOptions).catch(() => setOptions(null))
    void api.listProjects().then((list) => {
      setProjects(list)
      if (list.length > 0) setProjectId((current) => current || list[0].id)
    })
  }, [])

  const search = useCallback(async () => {
    setSearching(true)
    setError(null)
    setNotice(null)
    setResult(null)
    setSelected(new Set())
    try {
      const found = await api.discoverySearch({
        region,
        category,
        provider,
        keyword: provider === 'google' && keyword.trim() ? keyword.trim() : undefined,
        max_rating: provider === 'google' && maxRating ? Number(maxRating) : undefined,
      })
      setResult(found)
      // Pre-select everything: the common case is importing the whole batch.
      setSelected(new Set(found.places.map((p) => p.website!).filter(Boolean)))
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Pencarian gagal')
    } finally {
      setSearching(false)
    }
  }, [region, category, provider, keyword, maxRating])

  function toggle(url: string) {
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(url)) next.delete(url)
      else next.add(url)
      return next
    })
  }

  async function importSelected() {
    if (!projectId || selected.size === 0) return
    setImporting(true)
    setError(null)
    setNotice(null)
    try {
      const response = await api.discoveryImport(projectId, Array.from(selected))
      const skipped = response.rejected.length
      setNotice(
        `${response.created.length} website masuk antrean scraping` +
          (skipped > 0 ? `, ${skipped} dilewati (sudah pernah diproses).` : '.'),
      )
      if (response.created.length > 0) {
        setTimeout(() => navigate(`/projects/${projectId}`), 1400)
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Gagal menambahkan ke project')
    } finally {
      setImporting(false)
    }
  }

  const regionLabel = useMemo(
    () => options?.regions.find((r) => r.key === region)?.label ?? region,
    [options, region],
  )

  return (
    <>
      <PageHeader
        title="Temukan Bisnis"
        description="Cari UMKM yang sudah punya website berdasarkan wilayah dan kategori, lalu kirim ke project untuk di-scraping."
      />

      {error && <div className="mb-4"><Alert tone="error">{error}</Alert></div>}
      {notice && <div className="mb-4"><Alert tone="success">{notice}</Alert></div>}

      <div className="mb-6">
        <Panel>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Wilayah">
              <select className="input" value={region} onChange={(e) => setRegion(e.target.value)}>
                {options?.regions.map((r) => (
                  <option key={r.key} value={r.key}>{r.label}</option>
                ))}
              </select>
            </Field>
            <Field label="Kategori usaha">
              <select className="input" value={category} onChange={(e) => setCategory(e.target.value)}>
                {options?.categories.map((c) => (
                  <option key={c.key} value={c.key}>{c.label}</option>
                ))}
              </select>
            </Field>
            {/* Google is listed even without a key, greyed out. Hiding it made
                keyword search and rating filters undiscoverable. */}
            <Field label="Sumber data">
              <select className="input" value={provider} onChange={(e) => setProvider(e.target.value)}>
                {options?.providers.map((p) => (
                  <option
                    key={p.key}
                    value={p.key}
                    disabled={p.key === 'google' && !options?.google_configured}
                  >
                    {p.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Masukkan ke project">
              <select className="input" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
                {projects.length === 0 && <option value="">(belum ada project)</option>}
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </Field>
            <div className="flex items-end">
              <button className="btn-primary w-full" onClick={() => void search()} disabled={searching}>
                {searching ? 'Mencari…' : 'Cari bisnis'}
              </button>
            </div>
          </div>
          {/* Keyword and rating only exist on Google: OpenStreetMap has no
              ratings, and its coverage of Indonesian business names is too
              sparse to search by keyword. */}
          {provider === 'google' && (
            <div className="mt-4 grid gap-4 border-t border-slate-100 pt-4 sm:grid-cols-2">
              <Field
                label="Kata kunci (opsional)"
                hint="Contoh: bengkel mobil, klinik gigi, butik hijab. Kosongkan untuk memakai kategori di atas."
              >
                <input
                  className="input"
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  placeholder="bengkel mobil"
                />
              </Field>
              <Field
                label="Rating maksimal"
                hint="Rating rendah = peluang redesign paling besar. Yang belum punya rating tetap ditampilkan."
              >
                <select className="input" value={maxRating} onChange={(e) => setMaxRating(e.target.value)}>
                  <option value="">Semua rating</option>
                  <option value="3">≤ 3,0 — sangat perlu dibenahi</option>
                  <option value="3.5">≤ 3,5 — perlu dibenahi</option>
                  <option value="4">≤ 4,0 — masih bisa ditingkatkan</option>
                </select>
              </Field>
            </div>
          )}

          {options && !options.google_configured && (
            <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-900">
              <p className="font-semibold">Kolom RATING kosong karena Google Places belum aktif.</p>
              <p className="mt-1">
                OpenStreetMap tidak menyimpan rating sama sekali. Untuk mencari bisnis
                ber-rating jelek (calon klien redesign terbaik) dan mencari dengan kata
                kunci bebas, isi <code className="font-mono">GOOGLE_PLACES_API_KEY</code> di
                berkas <code className="font-mono">backend/.env</code>, lalu nyalakan ulang
                backend.
              </p>
            </div>
          )}

          <p className="mt-3 text-xs text-slate-400">
            Sumber data: {options?.attribution ?? 'OpenStreetMap'} — data terbuka, bukan hasil
            scraping mesin pencari.
          </p>
        </Panel>
      </div>

      {searching && <Spinner label="Mencari di OpenStreetMap…" />}

      {result && !searching && (
        <>
          <Panel
            title={`${result.places.length} bisnis punya website di ${regionLabel}`}
            description="Centang yang ingin Anda scraping, lalu kirim ke project."
            actions={
              <>
                <button
                  className="btn-secondary"
                  onClick={() =>
                    setSelected(
                      selected.size === result.places.length
                        ? new Set()
                        : new Set(result.places.map((p) => p.website!).filter(Boolean)),
                    )
                  }
                >
                  {selected.size === result.places.length ? 'Kosongkan' : 'Pilih semua'}
                </button>
                <button
                  className="btn-primary"
                  onClick={() => void importSelected()}
                  disabled={importing || selected.size === 0 || !projectId}
                >
                  {importing ? 'Mengirim…' : `Scraping ${selected.size} terpilih`}
                </button>
              </>
            }
            bodyClassName=""
          >
            {result.places.length === 0 ? (
              <EmptyState
                title="Tidak ada bisnis dengan website di area ini"
                description="Coba wilayah atau kategori lain. Data OpenStreetMap tidak selalu lengkap untuk semua area."
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200">
                  <thead className="table-head">
                    <tr>
                      <th className="w-10 px-5 py-3"></th>
                      <th className="px-5 py-3">Nama bisnis</th>
                      <th className="px-5 py-3">Rating</th>
                      <th className="px-5 py-3">Website</th>
                      <th className="px-5 py-3">Alamat</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {result.places.map((place) => (
                      <PlaceRow
                        key={place.osm_id}
                        place={place}
                        checked={selected.has(place.website!)}
                        onToggle={() => toggle(place.website!)}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          {result.social_only.length > 0 && (
            <div className="mt-6">
              <Panel
                title={`${result.social_only.length} bisnis belum punya website`}
                description="Hanya punya media sosial. Tidak bisa di-scraping, tapi justru calon klien paling potensial."
                bodyClassName=""
              >
                <ul className="divide-y divide-slate-100">
                  {result.social_only.map((place) => (
                    <li key={place.osm_id} className="flex items-center justify-between gap-4 px-5 py-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-slate-900">{place.name}</p>
                        <p className="truncate text-xs text-slate-500">{place.address ?? '—'}</p>
                      </div>
                      <a
                        href={place.raw_website.startsWith('http') ? place.raw_website : `https://${place.raw_website}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="shrink-0 text-xs font-medium text-navy-700 hover:underline"
                      >
                        Lihat sosmed
                      </a>
                    </li>
                  ))}
                </ul>
              </Panel>
            </div>
          )}
        </>
      )}
    </>
  )
}

function PlaceRow({
  place, checked, onToggle,
}: { place: DiscoveredPlace; checked: boolean; onToggle: () => void }) {
  return (
    <tr className={checked ? 'bg-navy-50/40' : 'hover:bg-slate-50'}>
      <td className="px-5 py-3">
        <input
          type="checkbox"
          checked={checked}
          onChange={onToggle}
          className="h-4 w-4 rounded border-slate-300 text-navy-900 focus:ring-navy-500"
          aria-label={`Pilih ${place.name}`}
        />
      </td>
      <td className="table-cell font-medium text-slate-900">{place.name}</td>
      <td className="table-cell">
        {place.rating === null ? (
          <span className="text-xs text-slate-400">—</span>
        ) : (
          <span
            className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-semibold ${
              place.rating < 3.5
                ? 'bg-red-50 text-red-700 ring-1 ring-red-200'
                : place.rating < 4.2
                  ? 'bg-amber-50 text-amber-700 ring-1 ring-amber-200'
                  : 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200'
            }`}
          >
            ★ {place.rating.toFixed(1)}
            {place.review_count ? (
              <span className="font-normal opacity-70">({place.review_count})</span>
            ) : null}
          </span>
        )}
      </td>
      <td className="table-cell max-w-xs">
        <a
          href={place.website ?? '#'}
          target="_blank"
          rel="noopener noreferrer"
          className="block truncate text-navy-700 hover:underline"
        >
          {place.website}
        </a>
      </td>
      <td className="table-cell max-w-xs truncate text-slate-500">{place.address ?? '—'}</td>
    </tr>
  )
}
