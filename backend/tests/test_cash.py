"""Saldo di cassa dei conti — test d'integrazione (PostgreSQL + Redis), saltati senza DB."""
import uuid
from contextlib import asynccontextmanager
from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete as sa_delete

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, hash_password
from app.main import app
from app.mcp.tokens import generate_token, hash_token
from app.models.account import Account
from app.models.mcp_token import McpAccessToken
from app.models.user import User
from app.services.cash import latest_balances

MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json",
               "MCP-Protocol-Version": "2025-06-18"}


@asynccontextmanager
async def _env():
    sfx = uuid.uuid4().hex[:8]
    try:
        async with AsyncSessionLocal() as db:
            user = User(email=f"cash_{sfx}@test.nextfolio", password_hash=hash_password("x" * 12), name="Cash")
            other = User(email=f"cash_o_{sfx}@test.nextfolio", password_hash=hash_password("x" * 12), name="O")
            db.add_all([user, other])
            await db.flush()
            acc = Account(user_id=user.id, name="Trade Republic", currency="EUR", is_sostituto_imposta=True)
            other_acc = Account(user_id=other.id, name="Altrui", currency="EUR")
            db.add_all([acc, other_acc])
            await db.flush()
            tokens = {}
            for name, w in (("ro", False), ("w", True)):
                t = generate_token()
                db.add(McpAccessToken(user_id=user.id, name=name, token_hash=hash_token(t), token_prefix=t[:12],
                                      can_read_values=True, can_write=w))
                tokens[name] = t
            await db.commit()
            ids = dict(user=user.id, other=other.id, account=acc.id, other_account=other_acc.id)
    except OSError as e:
        pytest.skip(f"Database non disponibile: {e}")
    auth = {"Authorization": f"Bearer {create_access_token(str(ids['user']))}"}
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            async def mcp(token, tool, args=None):
                r = await c.post("/api/mcp", headers={**MCP_HEADERS, "Authorization": f"Bearer {tokens[token]}"},
                                 json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                       "params": {"name": tool, "arguments": args or {}}})
                res = r.json()["result"]
                return res["isError"], res["content"][0]["text"]
            try:
                yield c, auth, mcp, ids
            finally:
                async with AsyncSessionLocal() as db:
                    await db.execute(sa_delete(User).where(User.id.in_([ids["user"], ids["other"]])))
                    await db.commit()


async def test_balance_history_latest_and_same_date_replace():
    async with _env() as (c, auth, _, ids):
        url = f"/api/v1/accounts/{ids['account']}/balances"
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        assert (await c.post(url, json={"balance": 1000, "date": yesterday}, headers=auth)).status_code == 201
        assert (await c.post(url, json={"balance": 1500}, headers=auth)).status_code == 201
        assert (await c.post(url, json={"balance": 1200}, headers=auth)).status_code == 201   # stessa data: sostituisce
        hist = (await c.get(url, headers=auth)).json()
        assert [h["balance"] for h in hist] == [1200, 1000]
        accounts = (await c.get("/api/v1/accounts", headers=auth)).json()
        acc = next(a for a in accounts if a["id"] == ids["account"])
        assert acc["cash_balance"] == 1200 and acc["cash_balance_date"] == date.today().isoformat()
        async with AsyncSessionLocal() as db:
            assert [b.balance for b in await latest_balances(db, ids["user"])] == [1200]
        # cancellazione di un saldo: torna corrente quello precedente
        r = await c.delete(f"{url}/{hist[0]['id']}", headers=auth)
        assert r.status_code == 204
        acc = next(a for a in (await c.get("/api/v1/accounts", headers=auth)).json() if a["id"] == ids["account"])
        assert acc["cash_balance"] == 1000


async def test_balance_validation_and_ownership():
    async with _env() as (c, auth, _, ids):
        future = (date.today() + timedelta(days=3)).isoformat()
        r = await c.post(f"/api/v1/accounts/{ids['account']}/balances", json={"balance": 1, "date": future}, headers=auth)
        assert r.status_code == 400
        r = await c.post(f"/api/v1/accounts/{ids['other_account']}/balances", json={"balance": 1}, headers=auth)
        assert r.status_code == 404


async def test_cash_in_dashboard_and_xray():
    async with _env() as (c, auth, _, ids):
        await c.post(f"/api/v1/accounts/{ids['account']}/balances", json={"balance": 2500}, headers=auth)
        d = (await c.get("/api/v1/portfolio/dashboard", headers=auth)).json()
        assert d["summary"]["cash_eur"] == 2500 and d["summary"]["net_worth_eur"] == 2500
        assert {i["label"]: i["pct"] for i in d["allocation"]["by_asset_class"]} == {"Monetario": 100.0}
        s = (await c.get("/api/v1/portfolio/summary", headers=auth)).json()
        assert s["cash_eur"] == 2500


async def test_mcp_update_account_balance():
    async with _env() as (_, __, mcp, ids):
        err, text = await mcp("ro", "update-account-balance", {"account_id": ids["account"], "balance": 800})
        assert err and "sola lettura" in text
        err, text = await mcp("w", "update-account-balance", {"account_id": ids["account"], "balance": 800})
        assert not err and "800.00 EUR" in text
        err, text = await mcp("w", "update-account-balance", {"account_id": ids["other_account"], "balance": 1})
        assert err and "non trovato" in text
        err, text = await mcp("ro", "get-accounts")
        assert not err and date.today().isoformat() in text and "800" in text
