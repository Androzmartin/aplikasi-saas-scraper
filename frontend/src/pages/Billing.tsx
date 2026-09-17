import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ApiError, api } from '@/api/client'
import type { Payment, Plan, Subscription } from '@/api/types'
import { Alert, EmptyState, PageHeader, Panel, Spinner, StatCard } from '@/components/ui'
import { formatDate } from '@/lib/format'

function rupiah(value: number): string {
  return new Intl.NumberFormat('id-ID', {
    style: 'currency',
    currency: 'IDR',
    maximumFractionDigits: 0,
  }).format(value)
}

const STATUS_LABELS: Record<string, string> = {
  pending: 'Menunggu pembayaran',
  paid: 'Lunas',
  failed: 'Gagal',
  expired: 'Kedaluwarsa',
}

const STATUS_TONES: Record<string, string> = {
  pending: 'bg-amber-50 text-amber-700 ring-1 ring-amber-200',
  paid: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
  failed: 'bg-red-50 text-red-700 ring-1 ring-red-200',
  expired: 'bg-slate-100 text-slate-500 ring-1 ring-slate-200',
}

export default function Billing() {
  const [params] = useSearchParams()
  const [plans, setPlans] = useState<Plan[]>([])
  const [subscription, setSubscription] = useState<Subscription | null>(null)
  const [payments, setPayments] = useState<Payment[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const returnedOrder = params.get('order')

  const load = useCallback(async () => {
    try {
      const [planList, sub, paymentList] = await Promise.all([
        api.listPlans(),
        api.getSubscription(),
        api.listPayments(),
      ])
      setPlans(planList)
      setSubscription(sub)
      setPayments(paymentList)
      setError(null)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Gagal memuat data langganan')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  // Coming back from Duitku, the callback may not have landed yet, so ask
  // Duitku directly instead of leaving the user staring at "pending".
  useEffect(() => {
    if (!returnedOrder || payments.length === 0) return
    const match = payments.find((item) => item.merchant_order_id === returnedOrder)
    if (!match || match.status !== 'pending') return
    void (async () => {
      try {
        await api.syncPayment(match.id)
        await load()
      } catch {
        /* the manual button is still available */
      }
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [returnedOrder, payments.length])

  async function buy(plan: Plan) {
    setBusy(plan.code)
    setError(null)
    setNotice(null)
    try {
      const { payment_url } = await api.checkout(plan.code)
      // Duitku hosts the payment page; leave the SPA for it.
      window.location.href = payment_url
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Gagal memulai pembayaran')
      setBusy(null)
    }
  }

  async function sync(payment: Payment) {
    setBusy(payment.id)
    setError(null)
    try {
      const updated = await api.syncPayment(payment.id)
      setNotice(
        updated.status === 'paid'
          ? 'Pembayaran terkonfirmasi. Paket Anda sudah aktif.'
          : `Status terbaru: ${STATUS_LABELS[updated.status] ?? updated.status}.`,
      )
      await load()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Gagal memeriksa status')
    } finally {
      setBusy(null)
    }
  }

  if (loading) return <Spinner />

  const rawPercent = subscription
    ? Math.min(100, (subscription.jobs_used_this_month / Math.max(1, subscription.monthly_job_quota)) * 100)
    : 0
  // Showing "0%" next to a non-zero usage count reads as a bug.
  const usedPercent =
    rawPercent > 0 && rawPercent < 1 ? '<1%' : `${Math.round(rawPercent)}%`

  return (
    <>
      <PageHeader
        title="Langganan"
        description="Kelola paket, kuota scraping, dan riwayat pembayaran."
      />

      {error && <div className="mb-4"><Alert tone="error">{error}</Alert></div>}
      {notice && <div className="mb-4"><Alert tone="success">{notice}</Alert></div>}

      {subscription?.is_expired && (
        <div className="mb-4">
          <Alert tone="warning">
            Masa aktif paket berbayar Anda sudah berakhir, jadi kuota kembali ke paket Gratis.
            Perpanjang di bawah untuk mengaktifkan kembali.
          </Alert>
        </div>
      )}

      {subscription && !subscription.payment_configured && (
        <div className="mb-4">
          <Alert tone="info">
            Pembayaran belum aktif di server ini. Admin perlu mengisi kredensial Duitku
            (<span className="font-mono text-xs">DUITKU_MERCHANT_CODE</span> dan{' '}
            <span className="font-mono text-xs">DUITKU_API_KEY</span>) sebelum paket bisa dibeli.
          </Alert>
        </div>
      )}

      {subscription && (
        <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Paket aktif" value={subscription.plan_name} />
          <StatCard
            label="Kuota bulan ini"
            value={`${subscription.jobs_used_this_month} / ${subscription.monthly_job_quota}`}
            hint={`${subscription.jobs_remaining} job tersisa`}
          />
          <StatCard label="Pemakaian" value={usedPercent} />
          <StatCard
            label="Berlaku sampai"
            value={subscription.expires_at ? formatDate(subscription.expires_at).split(',')[0] : '—'}
            hint={subscription.expires_at ? undefined : 'Paket gratis tidak kedaluwarsa'}
          />
        </div>
      )}

      <div className="mb-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {plans.map((plan) => {
          const current = subscription?.plan_code === plan.code
          return (
            <div
              key={plan.code}
              className={`panel flex flex-col p-5 ${current ? 'ring-2 ring-navy-900' : ''}`}
            >
              <div className="flex items-baseline justify-between gap-2">
                <h3 className="text-base font-semibold text-slate-900">{plan.name}</h3>
                {current && (
                  <span className="rounded-full bg-navy-900 px-2.5 py-1 text-xs font-medium text-white">
                    Aktif
                  </span>
                )}
              </div>
              <p className="mt-3 text-2xl font-semibold tabular-nums text-slate-900">
                {plan.is_free ? 'Gratis' : rupiah(plan.price_idr)}
              </p>
              <p className="text-xs text-slate-500">
                {plan.is_free ? 'Selamanya' : `per ${plan.duration_days} hari`}
              </p>

              <ul className="mt-4 flex-1 space-y-2">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex gap-2 text-sm text-slate-600">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-500" />
                    {feature}
                  </li>
                ))}
              </ul>

              <button
                className={current ? 'btn-secondary mt-5' : 'btn-primary mt-5'}
                disabled={plan.is_free || busy !== null || !subscription?.payment_configured}
                onClick={() => void buy(plan)}
              >
                {plan.is_free
                  ? 'Paket dasar'
                  : busy === plan.code
                    ? 'Mengalihkan…'
                    : current
                      ? 'Perpanjang'
                      : 'Pilih paket'}
              </button>
            </div>
          )
        })}
      </div>

      <Panel
        title="Riwayat pembayaran"
        description="Pembayaran diproses oleh Duitku. Kami tidak menyimpan data kartu Anda."
        bodyClassName=""
      >
        {payments.length === 0 ? (
          <EmptyState
            title="Belum ada pembayaran"
            description="Riwayat akan muncul setelah Anda membeli paket."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="table-head">
                <tr>
                  <th className="px-5 py-3">Order ID</th>
                  <th className="px-5 py-3">Paket</th>
                  <th className="px-5 py-3">Nominal</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Dibuat</th>
                  <th className="px-5 py-3">Aksi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {payments.map((payment) => (
                  <tr key={payment.id} className="hover:bg-slate-50">
                    <td className="table-cell font-mono text-xs">{payment.merchant_order_id}</td>
                    <td className="table-cell">{payment.plan_name}</td>
                    <td className="table-cell tabular-nums">{rupiah(payment.amount_idr)}</td>
                    <td className="table-cell">
                      <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_TONES[payment.status]}`}>
                        {STATUS_LABELS[payment.status] ?? payment.status}
                      </span>
                    </td>
                    <td className="table-cell text-slate-500">{formatDate(payment.created_at)}</td>
                    <td className="table-cell">
                      {payment.status === 'pending' ? (
                        <div className="flex gap-3">
                          {payment.payment_url && (
                            <a
                              href={payment.payment_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-sm font-medium text-navy-700 hover:underline"
                            >
                              Bayar
                            </a>
                          )}
                          <button
                            className="text-sm font-medium text-slate-600 hover:underline"
                            disabled={busy === payment.id}
                            onClick={() => void sync(payment)}
                          >
                            {busy === payment.id ? 'Memeriksa…' : 'Cek status'}
                          </button>
                        </div>
                      ) : (
                        <span className="text-sm text-slate-400">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  )
}
