import { useId, useState } from 'react'

/**
 * Chart primitives for the analytics page.
 *
 * Every chart here plots ONE measure with its categories labelled on the axis,
 * so no categorical palette and no legend are needed — which also means no
 * colour-blindness adjacency problem to solve. Ordered categories use a single
 * blue ordinal ramp (validated: monotone lightness, >=0.06 step gaps, light end
 * clears 2:1 against the surface). Colours are never used to carry a value that
 * is not also written down.
 *
 * The app shell is light-only by design (the formal white/navy/slate direction),
 * so these deliberately do not flip with prefers-color-scheme: a dark chart on a
 * white panel would be a defect, not a feature.
 */

// Blue ordinal ramp, darkest first. Steps 550 / 500 / 400 / 250.
export const RAMP = ['#1c5cab', '#256abf', '#3987e5', '#86b6ef']
const SINGLE = '#2a78d6' // categorical slot 1 — one series, no adjacency to clear
const SURFACE = '#ffffff'

export interface Bucket {
  key: string
  label: string
  count: number
}

function Tooltip({ x, y, children }: { x: number; y: number; children: React.ReactNode }) {
  return (
    <div
      role="tooltip"
      className="pointer-events-none absolute z-20 -translate-x-1/2 -translate-y-full rounded-md
                 border border-slate-200 bg-white px-2.5 py-1.5 text-xs shadow-lg"
      style={{ left: x, top: y - 8 }}
    >
      {children}
    </div>
  )
}

function DataTable({ rows, unit }: { rows: Bucket[]; unit: string }) {
  return (
    <table className="mt-3 w-full text-sm">
      <thead>
        <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
          <th className="py-1.5">Kategori</th>
          <th className="py-1.5 text-right">{unit}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.key} className="border-t border-slate-100">
            <td className="py-1.5 text-slate-700">{row.label}</td>
            <td className="py-1.5 text-right tabular-nums text-slate-900">{row.count}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/** Horizontal bars: magnitude across labelled categories. */
export function HorizontalBars({
  data, unit = 'Lead', ordinal = false, emptyText = 'Belum ada data.',
}: {
  data: Bucket[]
  unit?: string
  /** true = ordered categories (ramp darkest→lightest); false = one flat hue */
  ordinal?: boolean
  emptyText?: string
}) {
  const [hover, setHover] = useState<{ index: number; x: number; y: number } | null>(null)
  const [showTable, setShowTable] = useState(false)

  const max = Math.max(1, ...data.map((d) => d.count))
  const total = data.reduce((sum, d) => sum + d.count, 0)

  if (data.length === 0 || total === 0) {
    return <p className="py-8 text-center text-sm text-slate-500">{emptyText}</p>
  }

  return (
    <div className="relative">
      <ul className="space-y-2.5">
        {data.map((row, index) => {
          const width = (row.count / max) * 100
          const color = ordinal ? RAMP[Math.min(index, RAMP.length - 1)] : SINGLE
          return (
            <li
              key={row.key}
              onMouseMove={(event) => {
                const box = event.currentTarget.getBoundingClientRect()
                const parent = event.currentTarget.offsetParent?.getBoundingClientRect()
                setHover({
                  index,
                  x: event.clientX - (parent?.left ?? 0),
                  y: box.top - (parent?.top ?? 0),
                })
              }}
              onMouseLeave={() => setHover(null)}
            >
              <div className="mb-1 flex items-baseline justify-between gap-3">
                <span className="text-xs font-medium text-slate-600">{row.label}</span>
                <span className="text-xs tabular-nums text-slate-500">
                  {row.count}
                  {total > 0 && <span className="ml-1 text-slate-400">
                    ({Math.round((row.count / total) * 100)}%)
                  </span>}
                </span>
              </div>
              {/* Track sits behind the bar; 4px rounded data-end, anchored left. */}
              <div className="h-2.5 w-full overflow-hidden rounded-sm bg-slate-100">
                <div
                  className="h-full rounded-sm transition-[width] duration-500"
                  style={{
                    width: `${Math.max(width, row.count > 0 ? 1.5 : 0)}%`,
                    background: color,
                    boxShadow: `0 0 0 2px ${SURFACE}`,
                  }}
                />
              </div>
            </li>
          )
        })}
      </ul>

      {hover && (
        <Tooltip x={hover.x} y={hover.y}>
          <span className="block font-medium text-slate-900">{data[hover.index].label}</span>
          <span className="text-slate-600">
            {data[hover.index].count} {unit.toLowerCase()}
          </span>
        </Tooltip>
      )}

      <button
        className="mt-3 text-xs font-medium text-slate-500 underline-offset-2 hover:underline"
        onClick={() => setShowTable((open) => !open)}
      >
        {showTable ? 'Sembunyikan tabel' : 'Lihat sebagai tabel'}
      </button>
      {showTable && <DataTable rows={data} unit={unit} />}
    </div>
  )
}

export interface TrendPoint {
  date: string
  count: number
}

/** Lead volume over time: area + line with a crosshair tooltip. */
export function TrendChart({ data }: { data: TrendPoint[] }) {
  const gradientId = useId()
  const [hover, setHover] = useState<number | null>(null)

  const width = 720
  const height = 180
  const padding = { top: 12, right: 14, bottom: 22, left: 30 }
  const plotWidth = width - padding.left - padding.right
  const plotHeight = height - padding.top - padding.bottom

  if (data.length === 0) {
    return <p className="py-8 text-center text-sm text-slate-500">Belum ada data.</p>
  }

  const max = Math.max(1, ...data.map((d) => d.count))
  const stepX = data.length > 1 ? plotWidth / (data.length - 1) : plotWidth
  const pointX = (i: number) => padding.left + i * stepX
  const pointY = (v: number) => padding.top + plotHeight - (v / max) * plotHeight

  const line = data.map((d, i) => `${i === 0 ? 'M' : 'L'} ${pointX(i)} ${pointY(d.count)}`).join(' ')
  const area =
    `${line} L ${pointX(data.length - 1)} ${padding.top + plotHeight}` +
    ` L ${pointX(0)} ${padding.top + plotHeight} Z`

  const ticks = [0, Math.round(max / 2), max].filter((v, i, a) => a.indexOf(v) === i)
  const labelEvery = Math.max(1, Math.floor(data.length / 6))
  const total = data.reduce((sum, d) => sum + d.count, 0)

  return (
    <div className="relative">
      <p className="mb-2 text-xs text-slate-500">
        <span className="font-semibold tabular-nums text-slate-900">{total}</span> lead masuk pada
        periode ini
      </p>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        role="img"
        aria-label={`Tren lead harian, total ${total} lead`}
        onMouseLeave={() => setHover(null)}
        onMouseMove={(event) => {
          const box = event.currentTarget.getBoundingClientRect()
          const ratio = ((event.clientX - box.left) / box.width) * width
          const index = Math.round((ratio - padding.left) / stepX)
          setHover(index >= 0 && index < data.length ? index : null)
        }}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={SINGLE} stopOpacity="0.18" />
            <stop offset="100%" stopColor={SINGLE} stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {/* Recessive grid; labels in text tokens, never the series colour. */}
        {ticks.map((tick) => (
          <g key={tick}>
            <line
              x1={padding.left} x2={width - padding.right}
              y1={pointY(tick)} y2={pointY(tick)}
              stroke="#e2e8f0" strokeWidth="1"
            />
            <text x={padding.left - 6} y={pointY(tick) + 3} textAnchor="end"
                  fontSize="9" fill="#94a3b8">{tick}</text>
          </g>
        ))}

        <path d={area} fill={`url(#${gradientId})`} />
        <path d={line} fill="none" stroke={SINGLE} strokeWidth="2"
              strokeLinejoin="round" strokeLinecap="round" />

        {data.map((point, index) =>
          index % labelEvery === 0 ? (
            <text key={point.date} x={pointX(index)} y={height - 6} textAnchor="middle"
                  fontSize="9" fill="#94a3b8">
              {new Date(point.date).getDate()}
            </text>
          ) : null,
        )}

        {hover !== null && (
          <g>
            <line
              x1={pointX(hover)} x2={pointX(hover)}
              y1={padding.top} y2={padding.top + plotHeight}
              stroke="#cbd5e1" strokeWidth="1" strokeDasharray="3 3"
            />
            {/* 2px surface ring keeps the marker readable over the line. */}
            <circle cx={pointX(hover)} cy={pointY(data[hover].count)} r="4.5"
                    fill={SINGLE} stroke={SURFACE} strokeWidth="2" />
          </g>
        )}
      </svg>

      {hover !== null && (
        <div
          role="tooltip"
          className="pointer-events-none absolute -top-1 z-20 -translate-x-1/2 rounded-md border
                     border-slate-200 bg-white px-2.5 py-1.5 text-xs shadow-lg"
          style={{ left: `${(pointX(hover) / width) * 100}%` }}
        >
          <span className="block font-medium text-slate-900">
            {new Intl.DateTimeFormat('id-ID', { day: 'numeric', month: 'short' })
              .format(new Date(data[hover].date))}
          </span>
          <span className="tabular-nums text-slate-600">{data[hover].count} lead</span>
        </div>
      )}
    </div>
  )
}
