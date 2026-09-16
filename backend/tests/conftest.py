"""Test fixtures: an in-memory MongoDB and an authenticated API client.

The whole API is exercised against mongomock so the suite needs no running
database, while still going through the real routers, auth and serializers.
"""
import asyncio
from typing import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from mongomock_motor import AsyncMongoMockClient

from app import db as db_module


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def mock_db(monkeypatch):
    """Point the app's db module at a fresh in-memory database per test."""
    database = AsyncMongoMockClient()["umkm_scraper_test"]
    monkeypatch.setattr(db_module, "_db", database, raising=False)
    monkeypatch.setattr(db_module, "get_db", lambda: database)
    monkeypatch.setattr(db_module, "connect", lambda: database)

    # Routers do `from app.db import get_db`, which binds the original function
    # at import time, so patch every module that holds such a reference.
    # Discovered rather than hardcoded: a hardcoded list silently misses each
    # new router and the tests then run against the wrong database.
    import importlib
    import pkgutil

    import app.routers
    import app.services

    module_paths = ["app.deps"]
    for package in (app.routers, app.services):
        for info in pkgutil.iter_modules(package.__path__):
            module_paths.append(f"{package.__name__}.{info.name}")

    for module_path in module_paths:
        module = importlib.import_module(module_path)
        if hasattr(module, "get_db"):
            monkeypatch.setattr(module, "get_db", lambda: database)

    # Build the real indexes so tests exercise the same constraints production
    # has -- notably the unique index on users.email, which the registration
    # race-condition fallback depends on.
    await db_module.ensure_indexes()

    yield database


@pytest_asyncio.fixture
async def client(mock_db, tmp_path, monkeypatch) -> AsyncIterator[httpx.AsyncClient]:
    """An API client with the background worker and storage isolated."""
    from app.services import storage as storage_module

    monkeypatch.setattr(storage_module, "storage", storage_module.LocalStorage(str(tmp_path)))
    import app.routers.redesign as redesign_router

    monkeypatch.setattr(redesign_router, "storage", storage_module.storage)

    from app.main import app

    # Bypass lifespan: no real Mongo, and the worker pool is driven manually.
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as api_client:
        yield api_client


@pytest_asyncio.fixture
async def auth_client(client, mock_db) -> AsyncIterator[httpx.AsyncClient]:
    """A client registered as a tenant user, with the bearer token attached."""
    response = await client.post(
        "/api/auth/register",
        json={
            "company_name": "Agency Nusantara",
            "name": "Budi Santoso",
            "email": "budi@agency.co.id",
            "password": "rahasia-aman-123",
        },
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    yield client


@pytest_asyncio.fixture
async def admin_client(client, mock_db) -> AsyncIterator[httpx.AsyncClient]:
    """A second client authenticated as the internal admin."""
    from datetime import datetime, timezone

    from app.security import hash_password

    await mock_db.users.insert_one(
        {
            "tenant_id": None,
            "name": "Internal Admin",
            "email": "admin@internal.co.id",
            "password_hash": hash_password("admin-rahasia-123"),
            "role": "admin_internal",
            "created_at": datetime.now(timezone.utc),
        }
    )
    transport = httpx.ASGITransport(app=client._transport.app)  # type: ignore[attr-defined]
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as admin:
        response = await admin.post(
            "/api/auth/login",
            json={"email": "admin@internal.co.id", "password": "admin-rahasia-123"},
        )
        assert response.status_code == 200, response.text
        admin.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
        yield admin
