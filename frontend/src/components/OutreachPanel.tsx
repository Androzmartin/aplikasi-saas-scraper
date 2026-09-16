import { useCallback, useEffect, useState } from 'react'
import { ApiError, api } from '@/api/client'
import type { OutreachDraft } from '@/api/types'
import { Alert, Field, Panel } from '@/components/ui'
import { formatDate } from '@/lib/format'

const CHANNELS = [
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'email', label: 'Email' },
]
const TONES = [
  { value: 'formal', label: 'Formal' },
  { value: 'ramah', label: 'Ramah / santai' },
]

export default function OutreachPanel({
  leadId, onSent,
}: { leadId: string; onSent?: () => void }) {
  const [channel, setChannel] = useState('whatsapp')
  const [tone, setTone] = useState('formal')
  const [draft, setDraft] = useState<OutreachDraft | null>(null)
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.getOutreachDraft(leadId, channel, tone)
      setDraft(result)
      setText(result.message)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Gagal menyusun draft')
    } finally {
      setLoading(false)
    }
  }, [leadId, channel, tone])

  useEffect(() => {
    void load()
  }, [load])

  async function copy() {
    const payload = draft?.subject ? `${draft.subject}\n\n${text}` : text
    try {
      await navigator.clipboard.writeText(payload)
      setNotice('Pesan disalin ke clipboard.')
    } catch {
      setNotice('Tidak bisa menyalin otomatis — silakan blok teksnya lalu salin manual.')
    }
  }

  async function markSent() {
    try {
      await api.markOutreachSent(leadId, channel)
      setNotice('Ditandai sudah dikirim. Status lead diperbarui.')
      onSent?.()
      await load()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Gagal menandai terkirim')
    }
  }

  const edited = draft ? text !== draft.message : false

  return (
    <Panel
      title="Draft penawaran"
      description={
        draft?.outreach_sent_at
          ? `Terakhir dikirim via ${draft.outreach_channel} pada ${formatDate(draft.outreach_sent_at)}`
          : 'Disusun dari hasil audit. Anda yang mengirim dari akun sendiri.'
      }
    >
      {error && <div className="mb-4"><Alert tone="error">{error}</Alert></div>}
      {notice && <div className="mb-4"><Alert tone="success">{notice}</Alert></div>}

      <div className="mb-4 grid gap-4 sm:grid-cols-2">
        <Field label="Kanal">
          <select className="input" value={channel} onChange={(e) => setChannel(e.target.value)}>
            {CHANNELS.map((item) => (
              <option key={item.value} value={item.value}>{item.label}</option>
            ))}
          </select>
        </Field>
        <Field label="Gaya bahasa">
          <select className="input" value={tone} onChange={(e) => setTone(e.target.value)}>
            {TONES.map((item) => (
              <option key={item.value} value={item.value}>{item.label}</option>
            ))}
          </select>
        </Field>
      </div>

      {loading ? (
        <p className="py-6 text-center text-sm text-slate-500">Menyusun draft…</p>
      ) : (
        <>
          {draft?.subject && (
            <Field label="Subjek">
              <input className="input" value={draft.subject} readOnly />
            </Field>
          )}

          <div className="mt-4">
            <label className="label">Isi pesan</label>
            <textarea
              className="input font-mono text-xs leading-relaxed"
              rows={14}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
            <p className="mt-1 text-xs text-slate-400">
              {draft?.recipient
                ? `Tujuan: ${draft.recipient}`
                : 'Lead ini belum punya nomor/email publik — salin manual ke kanal lain.'}
              {edited && ' · Teks sudah Anda ubah; tombol kirim memakai draft asli.'}
            </p>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <button className="btn-secondary" onClick={copy}>Salin pesan</button>
            {draft?.send_url && (
              <a
                className="btn-primary"
                href={draft.send_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                {channel === 'whatsapp' ? 'Buka WhatsApp' : 'Buka email'}
              </a>
            )}
            <button className="btn-secondary" onClick={markSent}>
              Tandai sudah dikirim
            </button>
          </div>
        </>
      )}
    </Panel>
  )
}
