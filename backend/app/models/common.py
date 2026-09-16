"""Shared enums and base helpers for API schemas."""
from datetime import datetime
from enum import Enum
from typing import Any, Generic, List, TypeVar

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


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, use_enum_values=True)


def enum_value(value: Any) -> Any:
    """Return the plain value of an enum-ish input.

    Query parameters arrive as real Enum members, while request-body fields are
    already strings because ApiModel sets use_enum_values. Calling .value blindly
    on the latter raises AttributeError, so always route through this.
    """
    return value.value if isinstance(value, Enum) else value


class Page(ApiModel, Generic[T]):
    items: List[T] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 25


class Message(ApiModel):
    detail: str


class Timestamped(ApiModel):
    created_at: datetime
