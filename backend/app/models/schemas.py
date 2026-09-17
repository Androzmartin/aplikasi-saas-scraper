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
    # Optional because an internal admin has no tenant. Declaring it required
    # turned that case into a 500 from response validation instead of a clear
    # error the user could act on.
    tenant_id: Optional[str] = None
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
    tenant_id: Optional[str] = None
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
    tenant_id: Optional[str] = None
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
    # Profil sosial yang ditautkan bisnis dari websitenya sendiri.
    social_links: Dict[str, str] = Field(default_factory=dict)
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


# ---------------------------------------------------------------------- discovery


class DiscoveryOption(ApiModel):
    key: str
    label: str


class DiscoveryOptions(ApiModel):
    regions: List[DiscoveryOption] = Field(default_factory=list)
    categories: List[DiscoveryOption] = Field(default_factory=list)
    # Google Places only appears when the server has an API key configured.
    providers: List[DiscoveryOption] = Field(default_factory=list)
    attribution: str = ""


class DiscoverySearchRequest(ApiModel):
    region: str = Field(min_length=2, max_length=40)
    category: str = Field(default="kuliner", min_length=2, max_length=40)
    provider: str = Field(default="osm", pattern="^(osm|google)$")
    # Free-text search in the client's own words. Google only; OpenStreetMap
    # coverage of Indonesian UMKM names is far too thin to search this way.
    keyword: Optional[str] = Field(default=None, max_length=120)
    # Lead filter: a business with a website and a poor rating is the strongest
    # redesign prospect.
    max_rating: Optional[float] = Field(default=None, ge=1.0, le=5.0)
    min_reviews: int = Field(default=0, ge=0, le=10_000)
    limit: int = Field(default=60, ge=1, le=200)


class DiscoveredPlaceOut(ApiModel):
    name: str
    website: Optional[str] = None
    raw_website: str = ""
    address: Optional[str] = None
    category: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    osm_id: str = ""
    is_social_only: bool = False
    rating: Optional[float] = None
    review_count: Optional[int] = None


class DiscoveryResultOut(ApiModel):
    region: str
    category: str
    provider: str = "osm"
    places: List[DiscoveredPlaceOut] = Field(default_factory=list)
    social_only: List[DiscoveredPlaceOut] = Field(default_factory=list)
    attribution: str = ""


class DiscoveryImportRequest(ApiModel):
    project_id: str
    urls: List[str] = Field(min_length=1, max_length=200)


# ------------------------------------------------------------------------ billing


class PlanOut(ApiModel):
    code: str
    name: str
    price_idr: int
    monthly_job_quota: int
    duration_days: int
    features: List[str] = Field(default_factory=list)
    is_free: bool = False


class SubscriptionOut(ApiModel):
    plan_code: str
    plan_name: str
    monthly_job_quota: int
    jobs_used_this_month: int
    jobs_remaining: int
    expires_at: Optional[datetime] = None
    is_expired: bool = False
    payment_configured: bool = False


class PaymentOut(ApiModel):
    id: str
    merchant_order_id: str
    plan_code: str
    plan_name: str
    amount_idr: int
    status: str
    payment_url: Optional[str] = None
    va_number: Optional[str] = None
    reference: Optional[str] = None
    created_at: datetime
    paid_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class CheckoutRequest(ApiModel):
    plan_code: str = Field(min_length=2, max_length=40)


class CheckoutResponse(ApiModel):
    payment: PaymentOut
    payment_url: str


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
