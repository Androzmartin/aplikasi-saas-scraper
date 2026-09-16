import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, api, fetchImageObjectUrl } from '@/api/client'
import type { Screenshots } from '@/api/types'
import { Alert, Panel } from '@/components/ui'
import { formatDate } from '@/lib/format'

const VARIANT_LABELS: Record<string, string> = {
  desktop: 'Desktop (1440px)',
  mobile: 'Mobile (390px)',
}

/** Renders one protected screenshot, cleaning up its object URL on unmount. */
function ShotImage({ path, label }: { path: string; label: string }) {
  const [src, setSrc] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let revoked = false
    let url: string | null = null
    fetchImageObjectUrl(path)
      .then((objectUrl) => {
        if (revoked) {
          URL.revokeObjectURL(objectUrl)
          return
        }
        url = objectUrl
        setSrc(objectUrl)
      })
      .catch(() => setFailed(true))
    return () => {
      revoked = true
      if (url) URL.revokeObjectURL(url)
    }
  }, [path])

  return (
    <figure className="overflow-hidden rounded-lg border border-slate-200 bg-slate-50">
      <figcaption className="border-b border-slate-200 bg-white px-4 py-2 text-xs font-medium text-slate-600">
        {label}
      </figcaption>
      <div className="flex min-h-[200px] items-center justify-center p-3">
        {failed ? (
          <span className="text-xs text-slate-400">Gambar gagal dimuat</span>
        ) : src ? (
          <img src={src} alt={label} className="max-h-[420px] w-auto rounded border border-slate-200" />
        ) : (
          <span className="text-xs text-slate-400">Memuat…</span>
        )}
      </div>
    </figure>
  )
}

export default function ScreenshotPanel({ leadId }: { leadId: string }) {
  const [shots, setShots] = useState<Screenshots | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [unavailable, setUnavailable] = useState<string | null>(null)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const load = useCallback(async () => {
    try {
      setShots(await api.getScreenshots(leadId))
    } catch (caught) {
      // 404 simply means nothing captured yet.
      if (!(caught instanceof ApiError) || caught.status !== 404) {
        setError(caught instanceof ApiError ? caught.message : 'Gagal memuat screenshot')
      }
    } finally {
      if (mounted.current) setLoading(false)
    }
  }, [leadId])

  useEffect(() => {
    void load()
  }, [load])

  async function capture() {
    setBusy(true)
    setError(null)
    setUnavailable(null)
    try {
      setShots(await api.captureScreenshots(leadId))
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 503) {
        setUnavailable(caught.message)
      } else {
        setError(caught instanceof ApiError ? caught.message : 'Gagal mengambil screenshot')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <Panel
      title="Screenshot website lama"
      description={
        shots?.captured_at
          ? `Versi ${shots.version} · diambil ${formatDate(shots.captured_at)}`
          : 'Tangkapan layar desktop dan mobile untuk perbandingan before/after.'
      }
      actions={
        <button className="btn-secondary" onClick={capture} disabled={busy}>
          {busy ? 'Mengambil…' : shots ? 'Ambil ulang' : 'Ambil screenshot'}
        </button>
      }
    >
      {error && <div className="mb-4"><Alert tone="error">{error}</Alert></div>}
      {unavailable && (
        <div className="mb-4">
          <Alert tone="info">
            {unavailable}
            <p className="mt-1 text-xs">
              Fitur ini opsional dan tidak memengaruhi audit maupun generate redesign.
            </p>
          </Alert>
        </div>
      )}

      {loading ? (
        <p className="py-6 text-center text-sm text-slate-500">Memuat…</p>
      ) : !shots ? (
        <p className="py-6 text-center text-sm text-slate-500">
          Belum ada screenshot. Klik “Ambil screenshot” untuk menangkap tampilan desktop dan mobile.
        </p>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            {shots.variants.map((variant) => (
              <ShotImage
                key={variant}
                path={`/screenshots/${leadId}/${variant}`}
                label={VARIANT_LABELS[variant] ?? variant}
              />
            ))}
          </div>
          {Object.keys(shots.failures).length > 0 && (
            <div className="mt-4">
              <Alert tone="warning">
                Sebagian viewport gagal:{' '}
                {Object.entries(shots.failures).map(([k, v]) => `${k} (${v})`).join(', ')}
              </Alert>
            </div>
          )}
        </>
      )}
    </Panel>
  )
}
