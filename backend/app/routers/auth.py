"""Authentication, registration and profile endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.models.common import Message, Role, TenantStatus
from app.models.schemas import (
    LoginRequest,
    MeResponse,
    ProfileUpdate,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.security import create_access_token, hash_password, verify_password
from app.serializers import tenant_out, user_out

router = APIRouter(prefix="/auth", tags=["auth"])

INVALID_LOGIN = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="Email atau password salah"
)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest) -> Any:
    """Self-service signup: creates a tenant and its first user."""
    db = get_db()
    email = payload.email.lower().strip()
    now = datetime.now(timezone.utc)

    if await db.users.find_one({"email": email}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email sudah terdaftar"
        )

    tenant = await db.tenants.insert_one(
        {
            "company_name": payload.company_name.strip(),
            "plan_name": "starter",
            "status": TenantStatus.ACTIVE.value,
            "monthly_job_quota": settings.default_monthly_job_quota,
            "created_at": now,
        }
    )

    try:
        user = await db.users.insert_one(
            {
                "tenant_id": tenant.inserted_id,
                "name": payload.name.strip(),
                "email": email,
                "password_hash": hash_password(payload.password),
                "role": Role.USER_TENANT.value,
                "created_at": now,
            }
        )
    except DuplicateKeyError:
        # Lost a race against a concurrent signup; roll the tenant back.
        await db.tenants.delete_one({"_id": tenant.inserted_id})
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email sudah terdaftar"
        )

    token = create_access_token(
        str(user.inserted_id),
        {"role": Role.USER_TENANT.value, "tenant_id": str(tenant.inserted_id)},
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest) -> Any:
    db = get_db()
    user = await db.users.find_one({"email": payload.email.lower().strip()})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        raise INVALID_LOGIN

    token = create_access_token(
        str(user["_id"]),
        {
            "role": user.get("role"),
            "tenant_id": str(user["tenant_id"]) if user.get("tenant_id") else None,
        },
    )
    await db.activity_logs.insert_one(
        {
            "tenant_id": user.get("tenant_id"),
            "user_id": user["_id"],
            "action": "login",
            "target": user.get("email"),
            "detail": None,
            "created_at": datetime.now(timezone.utc),
        }
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


@router.post("/logout", response_model=Message)
async def logout(user: Dict[str, Any] = Depends(get_current_user)) -> Any:
    """Stateless JWT: the client discards the token. Logged for the audit trail."""
    db = get_db()
    await db.activity_logs.insert_one(
        {
            "tenant_id": user.get("tenant_id"),
            "user_id": user["_id"],
            "action": "logout",
            "target": user.get("email"),
            "detail": None,
            "created_at": datetime.now(timezone.utc),
        }
    )
    return {"detail": "Berhasil keluar"}


@router.get("/me", response_model=MeResponse)
async def me(user: Dict[str, Any] = Depends(get_current_user)) -> Any:
    db = get_db()
    tenant = None
    if user.get("tenant_id"):
        tenant_doc = await db.tenants.find_one({"_id": user["tenant_id"]})
        tenant = tenant_out(tenant_doc) if tenant_doc else None
    return {"user": user_out(user), "tenant": tenant}


@router.patch("/me", response_model=UserOut)
async def update_profile(
    payload: ProfileUpdate, user: Dict[str, Any] = Depends(get_current_user)
) -> Any:
    db = get_db()
    updates: Dict[str, Any] = {}
    if payload.name:
        updates["name"] = payload.name.strip()
    if payload.password:
        updates["password_hash"] = hash_password(payload.password)
    if not updates:
        return user_out(user)

    await db.users.update_one({"_id": user["_id"]}, {"$set": updates})
    refreshed = await db.users.find_one({"_id": user["_id"]})
    return user_out(refreshed)
