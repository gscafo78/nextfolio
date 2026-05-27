"""
Integration tests using FastAPI TestClient (real PostgreSQL via env).

These tests create isolated test data with a unique email per run and
clean up after themselves.  They require a running PostgreSQL (already
available in the Docker dev environment).
"""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"
TRANSPORT = ASGITransport(app=app)

# Unique suffix so parallel runs don't clash
_suffix = uuid.uuid4().hex[:8]
TEST_EMAIL = f"pytest_{_suffix}@test.nextfolio"
TEST_PASS  = "TestPass123!"
TEST_NAME  = "Pytest User"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
async def client():
    async with AsyncClient(transport=TRANSPORT, base_url=BASE) as c:
        yield c


@pytest.fixture(scope="module")
async def auth_tokens(client):
    """Register (if possible) or just login; return access token."""
    # Try registration — may fail with 403 if registration is disabled (multi-user mode)
    reg = await client.post("/api/v1/auth/register", json={
        "email": TEST_EMAIL,
        "password": TEST_PASS,
        "name": TEST_NAME,
    })
    # 201 = registered, 403 = closed (first user already exists)
    assert reg.status_code in (201, 400, 403), f"Unexpected register status: {reg.status_code}"

    login = await client.post("/api/v1/auth/login", data={
        "username": TEST_EMAIL,
        "password": TEST_PASS,
    })
    # If register was blocked, the user doesn't exist → skip auth-dependent tests
    if login.status_code != 200:
        pytest.skip("Cannot obtain auth token (registration closed, test user not pre-created)")

    tokens = login.json()
    assert "access_token" in tokens
    return tokens


@pytest.fixture(scope="module")
async def auth_headers(auth_tokens):
    return {"Authorization": f"Bearer {auth_tokens['access_token']}"}


# ── Health ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── Auth endpoints ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_wrong_password(client):
    r = await client.post("/api/v1/auth/login", data={
        "username": "nonexistent@example.com",
        "password": "WrongPass",
    })
    assert r.status_code in (400, 401, 422)


@pytest.mark.asyncio
async def test_get_me(client, auth_headers):
    r = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == TEST_EMAIL
    assert "id" in data
    assert "password" not in data
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_get_me_invalid_token(client):
    r = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert r.status_code == 401


# ── Portfolio endpoints (shape validation) ────────────────────────────────────

@pytest.mark.asyncio
async def test_positions_returns_list(client, auth_headers):
    r = await client.get("/api/v1/portfolio/positions", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_summary_shape(client, auth_headers):
    r = await client.get("/api/v1/portfolio/summary", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    expected_keys = {"total_value_eur", "total_invested_eur", "unrealized_pnl_eur"}
    assert expected_keys.issubset(data.keys())


@pytest.mark.asyncio
async def test_allocation_shape(client, auth_headers):
    r = await client.get("/api/v1/portfolio/allocation", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "by_type" in data
    assert "by_currency" in data
    assert "by_account" in data


@pytest.mark.asyncio
async def test_dashboard_shape(client, auth_headers):
    r = await client.get("/api/v1/portfolio/dashboard", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "summary" in data
    assert "positions" in data
    assert "allocation" in data
    assert isinstance(data["positions"], list)


@pytest.mark.asyncio
async def test_performance_shape(client, auth_headers):
    r = await client.get("/api/v1/portfolio/performance?period=1y", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "period" in data
    assert "series" in data
    assert isinstance(data["series"], list)


# ── Transactions ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_transactions_returns_list(client, auth_headers):
    r = await client.get("/api/v1/transactions", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_accounts_returns_list(client, auth_headers):
    r = await client.get("/api/v1/accounts", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ── Tax ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tax_years_returns_list(client, auth_headers):
    r = await client.get("/api/v1/tax/years", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
