import time

import jwt
import pytest

from app.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_round_trip():
    hashed = hash_password("rahasia-super-aman")
    assert hashed != "rahasia-super-aman"
    assert verify_password("rahasia-super-aman", hashed)
    assert not verify_password("password-salah", hashed)


def test_hashes_are_salted():
    assert hash_password("sama") != hash_password("sama")


def test_overlong_password_is_rejected_not_truncated():
    # bcrypt ignores bytes past 72; accepting them would silently weaken the hash.
    with pytest.raises(ValueError):
        hash_password("a" * 73)
    assert not verify_password("a" * 73, hash_password("a" * 72))


def test_token_carries_claims():
    token = create_access_token("user-1", {"role": "user_tenant", "tenant_id": "t-1"})
    payload = decode_access_token(token)
    assert payload["sub"] == "user-1"
    assert payload["role"] == "user_tenant"
    assert payload["tenant_id"] == "t-1"


def test_expired_token_rejected():
    token = create_access_token("user-1", expires_minutes=-1)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_tampered_token_rejected():
    token = create_access_token("user-1")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token + "x")
