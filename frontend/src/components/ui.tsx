import type { ReactNode } from 'react'
import { JOB_STATUS_LABELS, LEAD_STATUS_LABELS, scoreTone } from '@/lib/format'

export function PageHeader({
  title, description, actions,
}: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-4 border-b border-slate-200 pb-5 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-slate-900">{title}</h1>
        {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function Panel({
  title, description, actions, children, bodyClassName = 'p-5',
}: {
  title?: string
  description?: string
  actions?: ReactNode
  children: ReactNode
  bodyClassName?: string
}) {
  return (
    <section className="panel">
      {(title || actions) && (
        <header className="panel-header">
          <div>
            {title && <h2 className="panel-title">{title}</h2>}
            {description && <p className="mt-0.5 text-xs text-slate-500">{description}</p>}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={bodyClassName}>{children}</div>
    </section>
  )
}

export function StatCard({
  label, value, hint,
}: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="panel px-5 py-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold tabular-nums text-slate-900">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
    </div>
  )
}

const JOB_TONES: Record<string, string> = {
  pending: 'bg-slate-100 text-slate-600 ring-1 ring-slate-200',
  running: 'bg-sky-50 text-sky-700 ring-1 ring-sky-200',
  completed: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
  failed: 'bg-red-50 text-red-700 ring-1 ring-red-200',
}

export function JobStatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${JOB_TONES[status] ?? JOB_TONES.pending}`}>
      {status === 'running' && (
        <span className="mr-1.5 h-1.5 w-1.5 animate-pulse rounded-full bg-sky-500" />
      )}
      {JOB_STATUS_LABELS[status] ?? status}
    </span>
  )
}

const LEAD_TONES: Record<string, string> = {
  new: 'bg-navy-50 text-navy-700 ring-1 ring-navy-200',
  contacted: 'bg-amber-50 text-amber-700 ring-1 ring-amber-200',
  qualified: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
  rejected: 'bg-slate-100 text-slate-500 ring-1 ring-slate-200',
}

export function LeadStatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${LEAD_TONES[status] ?? LEAD_TONES.new}`}>
      {LEAD_STATUS_LABELS[status] ?? status}
    </span>
  )
}

export function ScoreBadge({ score }: { score: number | null | undefined }) {
  return (
    <span className={`inline-flex min-w-[3rem] items-center justify-center rounded-md px-2 py-1 text-xs font-semibold tabular-nums ${scoreTone(score)}`}>
      {score ?? '—'}
    </span>
  )
}

export function Alert({
  tone = 'error', children,
}: { tone?: 'error' | 'success' | 'info' | 'warning'; children: ReactNode }) {
  const tones = {
    error: 'border-red-200 bg-red-50 text-red-800',
    success: 'border-emerald-200 bg-emerald-50 text-emerald-800',
    info: 'border-sky-200 bg-sky-50 text-sky-800',
    warning: 'border-amber-200 bg-amber-50 text-amber-800',
  }
  return (
    <div role="status" className={`rounded-md border px-4 py-3 text-sm ${tones[tone]}`}>
      {children}
    </div>
  )
}

export function EmptyState({
  title, description, action,
}: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
      <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-slate-100">
        <svg className="h-5 w-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
        </svg>
      </div>
      <p className="text-sm font-medium text-slate-900">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-slate-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function Spinner({ label = 'Memuat…' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 px-6 py-12 text-sm text-slate-500">
      <svg className="h-4 w-4 animate-spin text-slate-400" viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.37 0 0 5.37 0 12h4z" />
      </svg>
      {label}
    </div>
  )
}

export function Field({
  label, hint, children,
}: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div>
      <label className="label">{label}</label>
      {children}
      {hint && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
    </div>
  )
}
