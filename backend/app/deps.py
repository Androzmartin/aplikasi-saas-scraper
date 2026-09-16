"""Shared FastAPI dependencies: auth, role guards and tenant scoping."""
from __future__ import annotations

from typing import Any, Dict, Optional

import jwt
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db import get_db
from app.models.common import Role
from app.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Kredensial tidak valid atau sesi telah berakhir",
    headers={"WWW-Authenticate": "Bearer"},
)


def to_object_id(value: str, field: str = "id") -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Nilai {field} tidak valid"
        )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Dict[str, Any]:
    if credentials is None or not credentials.credentials:
        raise CREDENTIALS_ERROR
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise CREDENTIALS_ERROR

    user_id = payload.get("sub")
    if not user_id:
        raise CREDENTIALS_ERROR

    db = get_db()
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except (InvalidId, TypeError):
        raise CREDENTIALS_ERROR
    if not user:
        raise CREDENTIALS_ERROR

    if user.get("role") != Role.ADMIN_INTERNAL.value and user.get("tenant_id"):
        tenant = await db.tenants.find_one({"_id": user["tenant_id"]})
        if not tenant or tenant.get("status") != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Akun tenant sedang tidak aktif. Hubungi admin.",
            )
    return user


async def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if user.get("role") != Role.ADMIN_INTERNAL.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akses khusus admin internal",
        )
    return user


def is_admin(user: Dict[str, Any]) -> bool:
    return user.get("role") == Role.ADMIN_INTERNAL.value


def tenant_filter(user: Dict[str, Any]) -> Dict[str, Any]:
    """Scope a query to the caller's tenant. Admins see everything."""
    if is_admin(user):
        return {}
    tenant_id = user.get("tenant_id")
    if tenant_id is None:
        # A non-admin without a tenant must never see other tenants' data.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Akun tidak terhubung ke tenant manapun"
        )
    return {"tenant_id": tenant_id}


async def get_owned_project(project_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    query = {"_id": to_object_id(project_id, "project_id"), **tenant_filter(user)}
    project = await db.projects.find_one(query)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project tidak ditemukan")
    return project


async def get_owned_lead(lead_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    query = {"_id": to_object_id(lead_id, "lead_id"), **tenant_filter(user)}
    lead = await db.leads.find_one(query)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead tidak ditemukan")
    return lead
