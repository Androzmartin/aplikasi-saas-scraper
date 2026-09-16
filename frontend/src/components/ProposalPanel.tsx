import { useCallback, useEffect, useState } from 'react'
import { ApiError, api } from '@/api/client'
import { Alert, Panel } from '@/components/ui'

export default function ProposalPanel({ leadId }: { leadId: string }) {
  const [html, setHtml] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [hint, setHint] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setHtml(await api.fetchProposalHtml(leadId))
      setError(null)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Gagal memuat proposal')
    } finally {
      setLoading(false)
    }
  }, [leadId])

  useEffect(() => {
    void load()
  }, [load])

  async function download(format: 'pdf' | 'html') {
    setBusy(format)
    setError(null)
    setHint(null)
    try {
      await api.downloadProposal(leadId, format)
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 503) {
        // PDF needs the optional browser; HTML always works.
        setHint(caught.message)
      } else {
        setError(caught instanceof ApiError ? caught.message : 'Gagal mengunduh proposal')
      }
    } finally {
      setBusy(null)
    }
  }

  return (
    <Panel
      title="Proposal untuk klien"
      description="Dokumen siap kirim: ringkasan audit, konsep redesign, lingkup kerja, dan investasi."
      actions={
        <>
          <button className="btn-secondary" onClick={() => download('html')} disabled={busy !== null}>
            {busy === 'html' ? 'Menyiapkan…' : 'Unduh HTML'}
          </button>
          <button className="btn-primary" onClick={() => download('pdf')} disabled={busy !== null}>
            {busy === 'pdf' ? 'Membuat PDF…' : 'Unduh PDF'}
          </button>
        </>
      }
    >
      {error && <div className="mb-4"><Alert tone="error">{error}</Alert></div>}
      {hint && (
        <div className="mb-4">
          <Alert tone="info">
            {hint}
            <p className="mt-1 text-xs">
              Tips: buka file HTML di browser lalu tekan Ctrl/Cmd + P dan pilih “Save as PDF”.
            </p>
          </Alert>
        </div>
      )}
      <p className="mb-4 text-xs text-slate-500">
        Lengkapi bagian <span className="font-medium text-slate-700">Investasi</span> sebelum
        mengirim dokumen ke calon klien.
      </p>

      {loading ? (
        <p className="py-6 text-center text-sm text-slate-500">Menyusun proposal…</p>
      ) : html ? (
        <div className="overflow-hidden rounded-lg border border-slate-200">
          {/* The proposal inlines its own CSS, so no scripts are needed here. */}
          <iframe
            title="Preview proposal"
            srcDoc={html}
            sandbox=""
            className="h-[640px] w-full border-0 bg-white"
          />
        </div>
      ) : null}
    </Panel>
  )
}
