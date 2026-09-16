export const REGION_LABELS: Record<string, string> = {
  jakarta: 'DKI Jakarta',
  jakarta_pusat: 'Jakarta Pusat',
  jakarta_utara: 'Jakarta Utara',
  jakarta_barat: 'Jakarta Barat',
  jakarta_selatan: 'Jakarta Selatan',
  jakarta_timur: 'Jakarta Timur',
  bogor: 'Bogor',
  depok: 'Depok',
  tangerang: 'Tangerang',
  bekasi: 'Bekasi',
  other: 'Luar Jabodetabek',
  unknown: 'Belum diketahui',
}

export const JABODETABEK_REGIONS = [
  'jakarta', 'jakarta_pusat', 'jakarta_utara', 'jakarta_barat',
  'jakarta_selatan', 'jakarta_timur', 'bogor', 'depok', 'tangerang', 'bekasi',
]

export function regionLabel(region: string | null | undefined): string {
  if (!region) return REGION_LABELS.unknown
  return REGION_LABELS[region] ?? region.replace(/_/g, ' ')
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('id-ID', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  }).format(date)
}

export function formatRelative(value: string | null | undefined): string {
  if (!value) return '—'
  const then = new Date(value).getTime()
  if (Number.isNaN(then)) return '—'
  const seconds = Math.round((then - Date.now()) / 1000)
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ['day', 86400], ['hour', 3600], ['minute', 60], ['second', 1],
  ]
  const formatter = new Intl.RelativeTimeFormat('id-ID', { numeric: 'auto' })
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size || unit === 'second') {
      return formatter.format(Math.round(seconds / size), unit)
    }
  }
  return '—'
}

export function scoreTone(score: number | null | undefined): string {
  if (score === null || score === undefined) return 'bg-slate-100 text-slate-600'
  if (score >= 80) return 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200'
  if (score >= 60) return 'bg-sky-50 text-sky-700 ring-1 ring-sky-200'
  if (score >= 40) return 'bg-amber-50 text-amber-700 ring-1 ring-amber-200'
  return 'bg-red-50 text-red-700 ring-1 ring-red-200'
}

export const LEAD_STATUS_LABELS: Record<string, string> = {
  new: 'Baru',
  contacted: 'Sudah dihubungi',
  qualified: 'Qualified',
  rejected: 'Ditolak',
}

export const JOB_STATUS_LABELS: Record<string, string> = {
  pending: 'Menunggu',
  running: 'Berjalan',
  completed: 'Selesai',
  failed: 'Gagal',
}

export const AUDIT_PARAM_LABELS: Record<string, string> = {
  mobile_friendly: 'Mobile friendly',
  cta_clarity: 'Kejelasan CTA',
  contact_clarity: 'Akses kontak',
  structure: 'Struktur section',
  visual_impression: 'Kesan visual',
}
