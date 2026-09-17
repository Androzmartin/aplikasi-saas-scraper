import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'

interface NavItem {
  to: string
  label: string
  icon: JSX.Element
  adminOnly?: boolean
  tenantOnly?: boolean
  end?: boolean
}

const icon = (path: string) => (
  <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
    <path strokeLinecap="round" strokeLinejoin="round" d={path} />
  </svg>
)

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Dashboard', end: true, icon: icon('M3 12l9-9 9 9M5 10v10a1 1 0 001 1h3a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1h3a1 1 0 001-1V10') },
  { to: '/projects', label: 'Projects', icon: icon('M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z') },
  { to: '/discovery', label: 'Temukan Bisnis', icon: icon('M21 21l-4.35-4.35M11 19a8 8 0 100-16 8 8 0 000 16z') },
  { to: '/leads', label: 'Leads', icon: icon('M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z') },
  { to: '/analytics', label: 'Analitik', icon: icon('M3 3v18h18M7 15l3-4 3 3 4-6') },
  { to: '/jobs', label: 'Scraping Jobs', icon: icon('M4 6h16M4 12h16M4 18h7M18 15l3 3-3 3') },
  // Internal admins have no tenant, so they have no subscription of their own;
  // cross-tenant payments live in the Admin panel instead.
  { to: '/billing', label: 'Langganan', tenantOnly: true, icon: icon('M3 10h18M7 15h4M5 6h14a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2z') },
  { to: '/admin', label: 'Admin Internal', adminOnly: true, icon: icon('M12 3l7 4v5c0 4.418-2.865 7.59-7 9-4.135-1.41-7-4.582-7-9V7l7-4z') },
]

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { isAdmin, tenant } = useAuth()
  const items = NAV_ITEMS.filter(
    (item) => (!item.adminOnly || isAdmin) && (!item.tenantOnly || !isAdmin),
  )

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-navy-800/60 px-5 py-5">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-white text-sm font-bold text-navy-900">
          US
        </span>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-white">UMKM Scraper</p>
          <p className="truncate text-xs text-navy-300">{tenant?.company_name ?? 'Admin Internal'}</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={onNavigate}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition ${
                isActive
                  ? 'bg-navy-800 text-white'
                  : 'text-navy-200 hover:bg-navy-800/60 hover:text-white'
              }`
            }
          >
            {item.icon}
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-navy-800/60 px-5 py-4">
        <p className="text-[11px] leading-relaxed text-navy-400">
          Hanya mengumpulkan data yang tampil publik di website target.
        </p>
      </div>
    </div>
  )
}

export default function Layout() {
  const { user, tenant, logout } = useAuth()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 bg-navy-900 lg:block">
        <SidebarContent />
      </aside>

      {sidebarOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            aria-label="Tutup menu"
            className="absolute inset-0 bg-slate-900/50"
            onClick={() => setSidebarOpen(false)}
          />
          <aside className="absolute inset-y-0 left-0 w-64 bg-navy-900">
            <SidebarContent onNavigate={() => setSidebarOpen(false)} />
          </aside>
        </div>
      )}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 border-b border-slate-200 bg-white">
          <div className="flex h-16 items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
            <button
              className="rounded-md p-2 text-slate-500 hover:bg-slate-100 lg:hidden"
              onClick={() => setSidebarOpen(true)}
              aria-label="Buka menu"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>

            <div className="hidden text-sm text-slate-500 sm:block">
              {tenant ? (
                <>
                  Paket <span className="font-medium text-slate-700">{tenant.plan_name}</span>
                  <span className="mx-2 text-slate-300">|</span>
                  Kuota bulanan{' '}
                  <span className="font-medium tabular-nums text-slate-700">
                    {tenant.monthly_job_quota}
                  </span>{' '}
                  job
                </>
              ) : (
                'Mode admin internal'
              )}
            </div>

            <div className="relative ml-auto">
              <button
                onClick={() => setMenuOpen((open) => !open)}
                className="flex items-center gap-3 rounded-md px-2 py-1.5 text-left hover:bg-slate-100"
              >
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-navy-100 text-xs font-semibold text-navy-700">
                  {(user?.name ?? '?').slice(0, 2).toUpperCase()}
                </span>
                <span className="hidden sm:block">
                  <span className="block text-sm font-medium text-slate-900">{user?.name}</span>
                  <span className="block text-xs text-slate-500">
                    {user?.role === 'admin_internal' ? 'Admin Internal' : 'User Tenant'}
                  </span>
                </span>
                <svg className="h-4 w-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {menuOpen && (
                <>
                  <button
                    className="fixed inset-0 z-10 cursor-default"
                    aria-hidden
                    onClick={() => setMenuOpen(false)}
                  />
                  <div className="absolute right-0 z-20 mt-2 w-56 overflow-hidden rounded-md border border-slate-200 bg-white shadow-lg">
                    <div className="border-b border-slate-100 px-4 py-3">
                      <p className="truncate text-sm font-medium text-slate-900">{user?.name}</p>
                      <p className="truncate text-xs text-slate-500">{user?.email}</p>
                    </div>
                    <button
                      onClick={() => {
                        setMenuOpen(false)
                        navigate('/profile')
                      }}
                      className="block w-full px-4 py-2.5 text-left text-sm text-slate-700 hover:bg-slate-50"
                    >
                      Profil saya
                    </button>
                    <button
                      onClick={handleLogout}
                      className="block w-full border-t border-slate-100 px-4 py-2.5 text-left text-sm text-red-600 hover:bg-red-50"
                    >
                      Keluar
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </header>

        <main className="px-4 py-8 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-7xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
