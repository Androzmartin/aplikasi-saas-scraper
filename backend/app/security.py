"""Password hashing and JWT helpers."""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from passlib.context import CryptContext

from app.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    # bcrypt silently truncates beyond 72 bytes; reject early so a long password
    # never becomes a weaker prefix match without the user knowing.
    if len(plain.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 bytes")
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    if len(plain.encode("utf-8")) > 72:
        return False
    try:
        return _pwd_context.verify(plain, hashed)
    except ValueError:
        return False


def create_access_token(
    subject: str, claims: Optional[Dict[str, Any]] = None, expires_minutes: Optional[int] = None
) -> str:
    expire_minutes = expires_minutes or settings.access_token_expire_minutes
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expire_minutes)).timestamp()),
    }
    if claims:
        payload.update(claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode a token, raising jwt.PyJWTError subclasses on failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
