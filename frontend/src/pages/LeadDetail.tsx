import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, api } from '@/api/client'
import type { Audit, Lead, NicheTemplate, Redesign } from '@/api/types'
import ScreenshotPanel from '@/components/ScreenshotPanel'
import { Alert, Field, LeadStatusBadge, PageHeader, Panel, Spinner } from '@/components/ui'
import { AUDIT_PARAM_LABELS, LEAD_STATUS_LABELS, formatDate, regionLabel } from '@/lib/format'

const SEVERITY_TONES: Record<string, string> = {
  high: 'bg-red-50 text-red-700 ring-red-200',
  medium: 'bg-amber-50 text-amber-700 ring-amber-200',
  low: 'bg-slate-50 text-slate-600 ring-slate-200',
}

const SEVERITY_LABELS: Record<string, string> = {
  high: 'Tinggi', medium: 'Sedang', low: 'Rendah',
}

function ContactRow({ label, value, href, confidence }: {
  label: string; value: string | null; href?: string; confidence?: number
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-slate-100 py-3 last:border-0">
      <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</span>
      <span className="text-right text-sm">
        {value ? (
          href ? (
            <a href={href} target="_blank" rel="noopener noreferrer" className="font-medium text-navy-700 hover:underline">
              {value}
            </a>
          ) : (
            <span className="text-slate-900">{value}</span>
          )
        ) : (
          <span className="text-slate-400">Tidak ditemukan</span>
        )}
        {value && confidence !== undefined && (
          <span className="mt-0.5 block text-[11px] text-slate-400">
            Keyakinan {Math.round(confidence * 100)}%
          </span>
        )}
      </span>
    </div>
  )
}

export default function LeadDetail() {
  const { leadId = '' } = useParams()
  const [lead, setLead] = useState<Lead | null>(null)
  const [audit, setAudit] = useState<Audit | null>(null)
  const [redesign, setRedesign] = useState<Redesign | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [notes, setNotes] = useState('')
  const [tagText, setTagText] = useState('')
  const [templates, setTemplates] = useState<NicheTemplate[]>([])
  const [templateKey, setTemplateKey] = useState('')

  const load = useCallback(async () => {
    const leadData = await api.getLead(leadId)
    setLead(leadData)
    setNotes(leadData.notes ?? '')
    setTagText(leadData.tags.join(', '))

    // Audit and redesign are optional; a 404 just means "not generated yet".
    const [auditResult, redesignResult] = await Promise.allSettled([
      api.getAudit(leadId),
      api.getRedesign(leadId),
    ])
    setAudit(auditResult.status === 'fulfilled' ? auditResult.value : null)
    setRedesign(redesignResult.status === 'fulfilled' ? redesignResult.value : null)
  }, [leadId])

  useEffect(() => {
    void load().finally(() => setLoading(false))
  }, [load])

  useEffect(() => {
    void api.listTemplates().then(setTemplates).catch(() => setTemplates([]))
  }, [])

  // Default the picker to whatever the last generation used.
  useEffect(() => {
    if (redesign?.template_key) setTemplateKey(redesign.template_key)
  }, [redesign?.template_key])

  async function act(key: string, action: () => Promise<void>, success: string) {
    setBusy(key)
    setError(null)
    setNotice(null)
    try {
      await action()
      setNotice(success)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Terjadi kesalahan')
    } finally {
      setBusy(null)
    }
  }

  if (loading) return <Spinner />
  if (!lead) return <Alert tone="error">Lead tidak ditemukan.</Alert>

  const confidence = lead.field_confidence ?? {}

  return (
    <>
      <PageHeader
        title={lead.business_name ?? lead.website_url}
        description={`${regionLabel(lead.region)} · Ditemukan ${formatDate(lead.created_at)}`}
        actions={
          <>
            <Link to="/leads" className="btn-secondary">Kembali</Link>
            <button
              className="btn-secondary"
              disabled={busy === 'audit'}
              onClick={() =>
                act('audit', async () => {
                  setAudit(await api.runAudit(leadId))
                  setLead(await api.getLead(leadId))
                }, 'Audit selesai dijalankan ulang.')
              }
            >
              {busy === 'audit' ? 'Mengaudit…' : 'Jalankan audit ulang'}
            </button>
            <button
              className="btn-primary"
              disabled={busy === 'redesign'}
              onClick={() =>
                act('redesign', async () => {
                  setRedesign(await api.generateRedesign(leadId, templateKey || undefined))
                }, 'Konsep redesign berhasil dibuat.')
              }
            >
              {busy === 'redesign' ? 'Membuat…' : redesign ? 'Generate ulang redesign' : 'Generate redesign'}
            </button>
          </>
        }
      />

      {error && <div className="mb-4"><Alert tone="error">{error}</Alert></div>}
      {notice && <div className="mb-4"><Alert tone="success">{notice}</Alert></div>}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-1">
          <Panel title="Data kontak publik" description="Diambil dari halaman yang tampil publik.">
            <ContactRow label="Website" value={lead.website_url} href={lead.website_url} />
            <ContactRow label="Nama bisnis" value={lead.business_name} confidence={confidence.business_name} />
            <ContactRow
              label="WhatsApp" value={lead.whatsapp_number}
              href={lead.whatsapp_number ? `https://wa.me/${lead.whatsapp_number.replace(/\D/g, '')}` : undefined}
              confidence={confidence.whatsapp_number}
            />
            <ContactRow
              label="Telepon" value={lead.phone_number}
              href={lead.phone_number ? `tel:${lead.phone_number}` : undefined}
              confidence={confidence.phone_number}
            />
            <ContactRow
              label="Email" value={lead.email}
              href={lead.email ? `mailto:${lead.email}` : undefined}
              confidence={confidence.email}
            />
            <ContactRow label="Alamat" value={lead.address} confidence={confidence.address} />
            <ContactRow label="Contact person" value={lead.contact_person} confidence={confidence.contact_person} />
            <ContactRow label="Halaman sumber" value={lead.source_page} href={lead.source_page ?? undefined} />
          </Panel>

          <Panel title="Catatan internal">
            <div className="space-y-4">
              <Field label="Status lead">
                <select
                  className="input" value={lead.status}
                  onChange={(event) =>
                    act('status', async () => {
                      setLead(await api.updateLead(leadId, { status: event.target.value as Lead['status'] }))
                    }, 'Status lead diperbarui.')
                  }
                >
                  {Object.entries(LEAD_STATUS_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </Field>

              <Field label="Tags" hint="Pisahkan dengan koma.">
                <input
                  className="input" value={tagText}
                  onChange={(event) => setTagText(event.target.value)}
                  placeholder="prioritas, kuliner"
                />
              </Field>

              <Field label="Catatan">
                <textarea
                  className="input" rows={4} value={notes} maxLength={4000}
                  onChange={(event) => setNotes(event.target.value)}
                  placeholder="Hasil telepon, jadwal follow-up, keberatan calon klien…"
                />
              </Field>

              <button
                className="btn-primary w-full"
                disabled={busy === 'notes'}
                onClick={() =>
                  act('notes', async () => {
                    setLead(await api.updateLead(leadId, {
                      notes,
                      tags: tagText.split(',').map((tag) => tag.trim()).filter(Boolean),
                    }))
                  }, 'Catatan tersimpan.')
                }
              >
                {busy === 'notes' ? 'Menyimpan…' : 'Simpan catatan'}
              </button>

              <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3">
                <LeadStatusBadge status={lead.status} />
                {lead.tags.map((tag) => (
                  <span key={tag} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          </Panel>
        </div>

        <div className="space-y-6 lg:col-span-2">
          <Panel
            title="Audit website"
            description={audit ? `Dijalankan ${formatDate(audit.created_at)}` : undefined}
          >
            {!audit ? (
              <p className="py-6 text-center text-sm text-slate-500">
                Belum ada audit. Klik “Jalankan audit ulang” untuk menilai website ini.
              </p>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-6 border-b border-slate-100 pb-5">
                  <div className="flex items-baseline gap-2">
                    <span className="text-4xl font-semibold tabular-nums text-slate-900">{audit.score}</span>
                    <span className="text-sm text-slate-400">/ 100</span>
                  </div>
                  <span className="rounded-md bg-navy-900 px-3 py-1 text-sm font-semibold text-white">
                    Grade {audit.grade}
                  </span>
                  <p className="min-w-[16rem] flex-1 text-sm leading-relaxed text-slate-600">
                    {audit.opportunity_summary}
                  </p>
                </div>

                <div className="grid gap-4 py-5 sm:grid-cols-2 lg:grid-cols-5">
                  {Object.entries(audit.breakdown).map(([key, value]) => (
                    <div key={key}>
                      <p className="text-xs font-medium text-slate-500">
                        {AUDIT_PARAM_LABELS[key] ?? key}
                      </p>
                      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className={`h-full rounded-full ${value >= 15 ? 'bg-emerald-500' : value >= 8 ? 'bg-amber-500' : 'bg-red-500'}`}
                          style={{ width: `${(value / 20) * 100}%` }}
                        />
                      </div>
                      <p className="mt-1 text-xs tabular-nums text-slate-400">{value}/20</p>
                    </div>
                  ))}
                </div>

                <div className="grid gap-6 border-t border-slate-100 pt-5 lg:grid-cols-2">
                  <div>
                    <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Temuan ({audit.issues.length})
                    </h3>
                    <ul className="space-y-2">
                      {audit.issues.map((issue) => (
                        <li key={issue.code} className="rounded-md border border-slate-200 px-3 py-2.5">
                          <div className="flex items-start justify-between gap-3">
                            <p className="text-sm font-medium text-slate-900">{issue.title}</p>
                            <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ${SEVERITY_TONES[issue.severity]}`}>
                              {SEVERITY_LABELS[issue.severity]}
                            </span>
                          </div>
                          <p className="mt-1 text-xs leading-relaxed text-slate-500">{issue.detail}</p>
                        </li>
                      ))}
                      {audit.issues.length === 0 && (
                        <li className="text-sm text-slate-500">Tidak ada temuan berarti.</li>
                      )}
                    </ul>
                  </div>
                  <div>
                    <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Kekuatan ({audit.strengths.length})
                    </h3>
                    <ul className="space-y-2">
                      {audit.strengths.map((strength) => (
                        <li key={strength} className="flex gap-2.5 text-sm text-slate-600">
                          <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-500" />
                          {strength}
                        </li>
                      ))}
                      {audit.strengths.length === 0 && (
                        <li className="text-sm text-slate-500">Belum ada kekuatan yang menonjol.</li>
                      )}
                    </ul>
                  </div>
                </div>
              </>
            )}
          </Panel>

          <ScreenshotPanel leadId={leadId} />

          <Panel
            title="Konsep redesign"
            description={redesign ? `Versi ${redesign.version} · ${formatDate(redesign.created_at)}` : undefined}
            actions={
              redesign && (
                <div className="flex items-center gap-3">
                  {redesign.approval_required && (
                    <span
                      className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                        redesign.approval_status === 'approved'
                          ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200'
                          : redesign.approval_status === 'rejected'
                            ? 'bg-red-50 text-red-700 ring-1 ring-red-200'
                            : 'bg-amber-50 text-amber-700 ring-1 ring-amber-200'
                      }`}
                    >
                      {redesign.approval_status === 'approved'
                        ? 'Disetujui admin'
                        : redesign.approval_status === 'rejected'
                          ? 'Ditolak admin'
                          : 'Menunggu persetujuan'}
                    </span>
                  )}
                  <button
                    className="btn-secondary"
                    disabled={busy === 'download' || !redesign.can_download}
                    title={
                      redesign.can_download
                        ? undefined
                        : 'Menunggu persetujuan admin internal sebelum bisa diunduh'
                    }
                    onClick={() => act('download', () => api.downloadRedesign(leadId), 'index.html diunduh.')}
                  >
                    Download index.html
                  </button>
                </div>
              )
            }
          >
            <div className="mb-5 rounded-lg border border-slate-200 bg-slate-50 p-4">
              <label className="label" htmlFor="template">Template niche</label>
              <div className="flex flex-wrap items-center gap-3">
                <select
                  id="template"
                  className="input w-auto min-w-[16rem]"
                  value={templateKey}
                  onChange={(event) => setTemplateKey(event.target.value)}
                >
                  <option value="">Deteksi otomatis dari nama bisnis</option>
                  {templates.map((item) => (
                    <option key={item.key} value={item.key}>
                      {item.label} — {item.highlight}
                    </option>
                  ))}
                </select>
                {redesign && (
                  <span className="text-xs text-slate-500">
                    Versi {redesign.version} memakai:{' '}
                    <span className="font-medium text-slate-700">
                      {redesign.template_label || redesign.template_key}
                    </span>
                  </span>
                )}
              </div>
              <p className="mt-2 text-xs text-slate-400">
                Ganti template lalu klik “Generate ulang redesign” untuk membuat versi baru.
              </p>
            </div>

            {!redesign ? (
              <p className="py-6 text-center text-sm text-slate-500">
                Belum ada konsep redesign. Klik “Generate redesign” untuk membuatnya.
              </p>
            ) : (
              <>
                {redesign.approval_required && !redesign.can_download && (
                  <div className="mb-5">
                    <Alert tone={redesign.approval_status === 'rejected' ? 'error' : 'warning'}>
                      {redesign.approval_status === 'rejected'
                        ? 'Admin internal menolak hasil redesign ini.'
                        : 'Hasil redesign menunggu persetujuan admin internal sebelum dapat diunduh.'}
                      {redesign.approval_note && (
                        <p className="mt-1 text-xs">Catatan admin: {redesign.approval_note}</p>
                      )}
                    </Alert>
                  </div>
                )}

                <div className="mb-5 rounded-lg border border-slate-200 bg-slate-50 p-5">
                  <p className="text-lg font-semibold leading-snug text-slate-900">{redesign.headline}</p>
                  <p className="mt-2 text-sm text-slate-600">{redesign.subheadline}</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {redesign.sections.map((section) => (
                      <span key={section} className="rounded-full bg-white px-3 py-1 text-xs text-slate-600 ring-1 ring-slate-200">
                        {section}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="overflow-hidden rounded-lg border border-slate-200">
                  <div className="flex items-center gap-2 border-b border-slate-200 bg-slate-100 px-4 py-2.5">
                    <span className="h-2.5 w-2.5 rounded-full bg-red-400" />
                    <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
                    <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
                    <span className="ml-3 text-xs text-slate-500">Preview redesign</span>
                  </div>
                  {/*
                    allow-scripts is required for the Tailwind Play CDN to style the
                    preview. It is deliberately NOT paired with allow-same-origin, so
                    the frame stays in an opaque origin and cannot read the parent DOM,
                    our cookies or the stored token. Scraped text is HTML-escaped when
                    the page is generated.
                  */}
                  <iframe
                    title="Preview redesign"
                    srcDoc={redesign.preview_html}
                    sandbox="allow-scripts"
                    className="h-[620px] w-full border-0 bg-white"
                  />
                </div>
              </>
            )}
          </Panel>
        </div>
      </div>
    </>
  )
}
