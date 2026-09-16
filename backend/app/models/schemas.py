"""Request/response schemas for every MVP API group."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import EmailStr, Field, field_validator

from app.models.common import (
    ApiModel,
    ApprovalStatus,
    JobStatus,
    LeadStatus,
    Role,
    TenantStatus,
)

# --------------------------------------------------------------------------- auth


class LoginRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RegisterRequest(ApiModel):
    company_name: str = Field(min_length=2, max_length=120)
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class TokenResponse(ApiModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(ApiModel):
    id: str
    tenant_id: Optional[str] = None
    name: str
    email: EmailStr
    role: Role
    created_at: datetime


class TenantOut(ApiModel):
    id: str
    company_name: str
    plan_name: str
    status: TenantStatus
    monthly_job_quota: int
    created_at: datetime


class MeResponse(ApiModel):
    user: UserOut
    tenant: Optional[TenantOut] = None


class ProfileUpdate(ApiModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    password: Optional[str] = Field(default=None, min_length=8, max_length=72)


# ----------------------------------------------------------------------- projects


class ProjectCreate(ApiModel):
    name: str = Field(min_length=2, max_length=140)
    target_region: str = Field(default="jakarta", max_length=60)
    description: Optional[str] = Field(default=None, max_length=500)


class ProjectOut(ApiModel):
    id: str
    tenant_id: str
    name: str
    target_region: str
    description: Optional[str] = None
    created_by: str
    created_at: datetime
    job_counts: Dict[str, int] = Field(default_factory=dict)
    lead_count: int = 0


# ------------------------------------------------------------------------ scraping


class JobCreate(ApiModel):
    project_id: str
    urls: List[str] = Field(min_length=1, max_length=200)
    # Skip URLs this project already scraped successfully or has queued.
    skip_existing: bool = True

    @field_validator("urls", mode="before")
    @classmethod
    def _split_bulk_paste(cls, value: Any) -> Any:
        """Accept a textarea bulk paste as well as a JSON array."""
        if isinstance(value, str):
            return [line.strip() for line in value.replace(",", "\n").splitlines() if line.strip()]
        return value


class JobOut(ApiModel):
    id: str
    project_id: str
    project_name: Optional[str] = None
    tenant_id: str
    source_url: str
    status: JobStatus
    attempts: int = 0
    error_message: Optional[str] = None
    lead_id: Optional[str] = None
    pages_crawled: int = 0
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class JobCreateResponse(ApiModel):
    created: List[JobOut] = Field(default_factory=list)
    rejected: List[Dict[str, str]] = Field(default_factory=list)


# --------------------------------------------------------------------------- leads


class LeadOut(ApiModel):
    id: str
    project_id: str
    tenant_id: str
    business_name: Optional[str] = None
    website_url: str
    whatsapp_number: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    contact_person: Optional[str] = None
    region: Optional[str] = None
    source_page: Optional[str] = None
    audit_score: Optional[int] = None
    status: LeadStatus = LeadStatus.NEW
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    field_confidence: Dict[str, float] = Field(default_factory=dict)
    has_redesign: bool = False
    outreach_sent_at: Optional[datetime] = None
    outreach_channel: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class LeadUpdate(ApiModel):
    status: Optional[LeadStatus] = None
    notes: Optional[str] = Field(default=None, max_length=4000)
    tags: Optional[List[str]] = None
    contact_person: Optional[str] = Field(default=None, max_length=140)
    business_name: Optional[str] = Field(default=None, max_length=200)
    region: Optional[str] = Field(default=None, max_length=60)


# --------------------------------------------------------------------------- audit


class AuditIssue(ApiModel):
    code: str
    title: str
    severity: str
    detail: str


class AuditOut(ApiModel):
    id: str
    lead_id: str
    score: int
    grade: str
    issues: List[AuditIssue] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    breakdown: Dict[str, int] = Field(default_factory=dict)
    redesign_summary: str = ""
    opportunity_summary: str = ""
    created_at: datetime


# ------------------------------------------------------------------------ redesign


class RedesignOut(ApiModel):
    id: str
    lead_id: str
    version: int
    headline: str
    subheadline: str
    sections: List[str] = Field(default_factory=list)
    preview_html: str = ""
    download_url: str
    generated_with: str = "template"
    template_key: str = "umum"
    template_label: str = ""
    approval_status: ApprovalStatus = ApprovalStatus.APPROVED
    approval_required: bool = False
    can_download: bool = True
    approval_note: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime


class TemplateOut(ApiModel):
    key: str
    label: str
    accent: str
    headline: str
    highlight: str


class ApprovalDecision(ApiModel):
    status: ApprovalStatus
    note: Optional[str] = Field(default=None, max_length=500)


class AdminRedesignOut(ApiModel):
    id: str
    lead_id: str
    tenant_id: Optional[str] = None
    business_name: Optional[str] = None
    website_url: Optional[str] = None
    version: int
    headline: str
    approval_status: ApprovalStatus
    approval_note: Optional[str] = None
    generated_with: str = "template"
    created_at: datetime
    reviewed_at: Optional[datetime] = None


# ---------------------------------------------------------------------- analytics


class MetricBucket(ApiModel):
    key: str
    label: str
    count: int


class TrendPoint(ApiModel):
    date: str
    count: int


class AnalyticsOverview(ApiModel):
    total_leads: int
    scored_leads: int
    average_score: Optional[int] = None
    redesigns: int
    outreach_sent: int
    contact_rate: int
    qualified_rate: int
    funnel: List[MetricBucket] = Field(default_factory=list)
    score_bands: List[MetricBucket] = Field(default_factory=list)
    regions: List[MetricBucket] = Field(default_factory=list)
    trend: List[TrendPoint] = Field(default_factory=list)
    days: int = 30


# ----------------------------------------------------------------------- outreach


class OutreachDraftOut(ApiModel):
    lead_id: str
    channel: str
    tone: str
    subject: Optional[str] = None
    message: str
    send_url: Optional[str] = None
    recipient: Optional[str] = None
    outreach_sent_at: Optional[datetime] = None
    outreach_channel: Optional[str] = None


class OutreachLogged(ApiModel):
    lead_id: str
    status: LeadStatus
    outreach_channel: str
    outreach_sent_at: datetime


# ---------------------------------------------------------------------- screenshot


class ScreenshotOut(ApiModel):
    lead_id: str
    version: int = 0
    variants: List[str] = Field(default_factory=list)
    failures: Dict[str, str] = Field(default_factory=dict)
    image_urls: Dict[str, str] = Field(default_factory=dict)
    captured_at: Optional[datetime] = None


# --------------------------------------------------------------------------- admin


class AdminStats(ApiModel):
    tenants: int
    users: int
    projects: int
    leads: int
    redesigns: int
    jobs_by_status: Dict[str, int] = Field(default_factory=dict)


class ActivityLogOut(ApiModel):
    id: str
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    action: str
    target: Optional[str] = None
    detail: Optional[str] = None
    created_at: datetime
