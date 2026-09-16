"""Shared enums and base helpers for API schemas."""
from datetime import datetime
from enum import Enum
from typing import Generic, List, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Role(str, Enum):
    ADMIN_INTERNAL = "admin_internal"
    USER_TENANT = "user_tenant"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class LeadStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    REJECTED = "rejected"


class TenantStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, use_enum_values=True)


class Page(ApiModel, Generic[T]):
    items: List[T] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 25


class Message(ApiModel):
    detail: str


class Timestamped(ApiModel):
    created_at: datetime
