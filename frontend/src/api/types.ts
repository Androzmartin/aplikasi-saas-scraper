// Mirrors the backend Pydantic schemas in backend/app/models/schemas.py
export type Role = 'admin_internal' | 'user_tenant'
export type JobStatus = 'pending' | 'running' | 'completed' | 'failed'
export type LeadStatus = 'new' | 'contacted' | 'qualified' | 'rejected'
export type TenantStatus = 'active' | 'suspended'
export type ApprovalStatus = 'pending' | 'approved' | 'rejected'

export interface User {
  id: string
  tenant_id: string | null
  name: string
  email: string
  role: Role
  created_at: string
}

export interface Tenant {
  id: string
  company_name: string
  plan_name: string
  status: TenantStatus
  monthly_job_quota: number
  created_at: string
}

export interface MeResponse {
  user: User
  tenant: Tenant | null
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
}

export interface Project {
  id: string
  tenant_id: string
  name: string
  target_region: string
  description: string | null
  created_by: string
  created_at: string
  job_counts: Record<string, number>
  lead_count: number
}

export interface Job {
  id: string
  project_id: string
  project_name: string | null
  tenant_id: string
  source_url: string
  status: JobStatus
  attempts: number
  error_message: string | null
  lead_id: string | null
  pages_crawled: number
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export interface JobCreateResponse {
  created: Job[]
  rejected: { url: string; reason: string }[]
}

export interface Lead {
  id: string
  project_id: string
  tenant_id: string
  business_name: string | null
  website_url: string
  whatsapp_number: string | null
  phone_number: string | null
  email: string | null
  address: string | null
  contact_person: string | null
  region: string | null
  source_page: string | null
  audit_score: number | null
  status: LeadStatus
  notes: string | null
  tags: string[]
  field_confidence: Record<string, number>
  has_redesign: boolean
  created_at: string
  updated_at: string | null
}

export interface PageResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface AuditIssue {
  code: string
  title: string
  severity: 'high' | 'medium' | 'low'
  detail: string
}

export interface Audit {
  id: string
  lead_id: string
  score: number
  grade: string
  issues: AuditIssue[]
  strengths: string[]
  breakdown: Record<string, number>
  redesign_summary: string
  opportunity_summary: string
  created_at: string
}

export interface Redesign {
  id: string
  lead_id: string
  version: number
  headline: string
  subheadline: string
  sections: string[]
  preview_html: string
  download_url: string
  generated_with: string
  approval_status: ApprovalStatus
  approval_required: boolean
  can_download: boolean
  approval_note: string | null
  reviewed_at: string | null
  created_at: string
}

export interface AdminRedesign {
  id: string
  lead_id: string
  tenant_id: string | null
  business_name: string | null
  website_url: string | null
  version: number
  headline: string
  approval_status: ApprovalStatus
  approval_note: string | null
  generated_with: string
  created_at: string
  reviewed_at: string | null
}

export interface Screenshots {
  lead_id: string
  version: number
  variants: string[]
  failures: Record<string, string>
  image_urls: Record<string, string>
  captured_at: string | null
}

export interface AdminStats {
  tenants: number
  users: number
  projects: number
  leads: number
  redesigns: number
  jobs_by_status: Record<string, number>
}

export interface ActivityLog {
  id: string
  tenant_id: string | null
  user_id: string | null
  action: string
  target: string | null
  detail: string | null
  created_at: string
}
