import type {
  ActivityLog, AdminStats, Audit, Job, JobCreateResponse, Lead, MeResponse,
  PageResult, Project, Redesign, Tenant, TokenResponse, User,
} from './types'

const BASE = import.meta.env.VITE_API_BASE ?? '/api'
const TOKEN_KEY = 'umkm_scraper_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}
export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}
export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

/** Unwraps FastAPI's error shapes into a single readable message. */
async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json()
    const detail = body?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail
        .map((item: { loc?: string[]; msg?: string }) => {
          const field = item.loc?.slice(1).join('.') ?? ''
          return field ? `${field}: ${item.msg}` : item.msg
        })
        .join(', ')
    }
  } catch {
    /* fall through to the status text */
  }
  return response.statusText || `Request gagal (${response.status})`
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers = new Headers(init.headers)
  if (!headers.has('Content-Type') && init.body) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(`${BASE}${path}`, { ...init, headers })

  if (response.status === 401) {
    clearToken()
    // Let the auth context redirect rather than throwing a raw 401 at the page.
    window.dispatchEvent(new CustomEvent('auth:expired'))
    throw new ApiError(401, 'Sesi berakhir, silakan masuk kembali')
  }
  if (!response.ok) throw new ApiError(response.status, await errorMessage(response))
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

function query(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

/** Downloads a file through fetch so the Authorization header is sent. */
async function download(path: string, fallbackName: string): Promise<void> {
  const token = getToken()
  const response = await fetch(`${BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!response.ok) throw new ApiError(response.status, await errorMessage(response))

  const disposition = response.headers.get('Content-Disposition') ?? ''
  const match = /filename="?([^"]+)"?/.exec(disposition)
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = match?.[1] ?? fallbackName
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

export interface LeadFilters {
  project_id?: string
  region?: string
  status?: string
  search?: string
  min_score?: number
  max_score?: number
  page?: number
  page_size?: number
}

export const api = {
  // auth
  login: (email: string, password: string) =>
    request<TokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  register: (data: { company_name: string; name: string; email: string; password: string }) =>
    request<TokenResponse>('/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  logout: () => request<{ detail: string }>('/auth/logout', { method: 'POST' }),
  me: () => request<MeResponse>('/auth/me'),
  updateProfile: (data: { name?: string; password?: string }) =>
    request<User>('/auth/me', { method: 'PATCH', body: JSON.stringify(data) }),

  // projects
  listProjects: () => request<Project[]>('/projects'),
  getProject: (id: string) => request<Project>(`/projects/${id}`),
  createProject: (data: { name: string; target_region: string; description?: string }) =>
    request<Project>('/projects', { method: 'POST', body: JSON.stringify(data) }),

  // scraping
  createJobs: (project_id: string, urls: string[]) =>
    request<JobCreateResponse>('/scrape/jobs', {
      method: 'POST',
      body: JSON.stringify({ project_id, urls }),
    }),
  listJobs: (params: { project_id?: string; status?: string; limit?: number } = {}) =>
    request<Job[]>(`/scrape/jobs${query(params)}`),
  getJob: (id: string) => request<Job>(`/scrape/jobs/${id}`),
  retryJob: (id: string) => request<Job>(`/scrape/jobs/${id}/retry`, { method: 'POST' }),

  // leads
  listLeads: (filters: LeadFilters = {}) =>
    request<PageResult<Lead>>(`/leads${query(filters as Record<string, string | number>)}`),
  regionFacets: (project_id?: string) =>
    request<{ region: string; count: number }[]>(`/leads/regions${query({ project_id })}`),
  getLead: (id: string) => request<Lead>(`/leads/${id}`),
  updateLead: (id: string, data: Partial<Pick<Lead, 'status' | 'notes' | 'tags' | 'contact_person' | 'business_name' | 'region'>>) =>
    request<Lead>(`/leads/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

  // audit
  runAudit: (leadId: string) => request<Audit>(`/audits/run/${leadId}`, { method: 'POST' }),
  getAudit: (leadId: string) => request<Audit>(`/audits/${leadId}`),

  // redesign
  generateRedesign: (leadId: string) =>
    request<Redesign>(`/redesign/${leadId}/generate`, { method: 'POST' }),
  getRedesign: (leadId: string) => request<Redesign>(`/redesign/${leadId}`),
  downloadRedesign: (leadId: string) =>
    download(`/redesign/${leadId}/download`, 'index.html'),

  // exports
  exportLeadsCsv: (filters: LeadFilters = {}) =>
    download(`/exports/leads.csv${query(filters as Record<string, string | number>)}`, 'leads.csv'),

  // admin
  adminStats: () => request<AdminStats>('/admin/stats'),
  adminUsers: () => request<User[]>('/admin/users'),
  adminTenants: () => request<Tenant[]>('/admin/tenants'),
  adminProjects: () => request<Project[]>('/admin/projects'),
  adminJobs: (status?: string) => request<Job[]>(`/admin/jobs${query({ status })}`),
  adminErrors: () => request<Job[]>('/admin/errors'),
  adminActivity: () => request<ActivityLog[]>('/admin/activity'),
  setTenantStatus: (id: string, value: 'active' | 'suspended') =>
    request<Tenant>(`/admin/tenants/${id}/status${query({ value })}`, { method: 'PATCH' }),
}
