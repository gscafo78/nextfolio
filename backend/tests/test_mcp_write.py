"""
Tool MCP di scrittura e cancellazione — test d'integrazione (PostgreSQL + Redis).

Saltati se il database non è raggiungibile. In locale:
    DATABASE_URL=postgresql+asyncpg://... REDIS_URL=redis://... pytest tests/test_mcp_write.py
"""
import uuid
from contextlib import asynccontextmanager
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete as sa_delete
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.main import app
from app.mcp.tokens import generate_token, hash_token
from app.models.account import Account
from app.models.alert import PriceAlert
from app.models.asset import Asset
from app.models.audit_log import AuditLog
from app.models.mcp_token import McpAccessToken
from app.models.transaction import Transaction
from app.models.user import User
from app.models.watchlist import WatchlistItem

HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json",
           "MCP-Protocol-Version": "2025-06-18"}


@asynccontextmanager
async def _env():
    """Utente, conto, asset e tre token (lettura / scrittura / scrittura+cancellazione)."""
    sfx = uuid.uuid4().hex[:8]
    try:
        async with AsyncSessionLocal() as db:
            user = User(email=f"mcpw_{sfx}@test.nextfolio", password_hash=hash_password("x" * 12), name="MCP")
            other = User(email=f"mcpw_other_{sfx}@test.nextfolio", password_hash=hash_password("x" * 12), name="Other")
            db.add_all([user, other])
            await db.flush()
            acc = Account(user_id=user.id, name="Conto test", currency="EUR")
            other_acc = Account(user_id=other.id, name="Altrui", currency="EUR")
            asset = Asset(isin=None, symbol=f"T{sfx}".upper(), name=f"Test ETF World {sfx}", type="ETF",
                          exchange="OTHER", currency="EUR")
            db.add_all([acc, other_acc, asset])
            await db.flush()
            tokens = {}
            for name, w, d in (("ro", False, False), ("w", True, False), ("wd", True, True)):
                t = generate_token()
                db.add(McpAccessToken(user_id=user.id, name=name, token_hash=hash_token(t), token_prefix=t[:12],
                                      can_read_values=True, can_write=w, can_delete=d))
                tokens[name] = t
            other_tx = Transaction(account_id=other_acc.id, asset_id=asset.id, type="BUY", date=date(2025, 1, 2),
                                   quantity=1, price=10, price_currency="EUR", exchange_rate=1, fee=0)
            db.add(other_tx)
            await db.commit()
            ids = dict(user=user.id, other=other.id, account=acc.id, other_account=other_acc.id, asset=asset.id,
                       other_tx=other_tx.id)
    except OSError as e:
        pytest.skip(f"Database non disponibile: {e}")

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            async def call(token: str, tool: str, args: dict | None = None) -> tuple[bool, str]:
                r = await c.post("/api/mcp", headers={**HEADERS, "Authorization": f"Bearer {tokens[token]}"},
                                 json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                       "params": {"name": tool, "arguments": args or {}}})
                assert r.status_code == 200, r.text
                res = r.json()["result"]
                return res["isError"], res["content"][0]["text"]
            try:
                yield call, ids
            finally:
                async with AsyncSessionLocal() as db:
                    # delete SQL: lascia al DB le cascate (conti, transazioni, token, watchlist, alert)
                    await db.execute(sa_delete(User).where(User.id.in_([ids["user"], ids["other"]])))
                    await db.execute(sa_delete(Asset).where(Asset.id == ids["asset"]))
                    await db.commit()


def _tx(ids, **kw):
    row = dict(account_id=ids["account"], asset_id=ids["asset"], type="BUY", date="2025-03-03",
               quantity=10, price=100.0, fee=1.5)
    row.update(kw)
    return row


async def _count(model, **where):
    async with AsyncSessionLocal() as db:
        q = select(model)
        for k, v in where.items():
            q = q.where(getattr(model, k) == v)
        return len((await db.execute(q)).scalars().all())


async def test_read_only_token_cannot_write():
    async with _env() as (call, ids):
        err, text = await call("ro", "create-transactions", {"transactions": [_tx(ids)]})
        assert err and "sola lettura" in text
        assert await _count(Transaction, account_id=ids["account"]) == 0
        err, text = await call("ro", "search-assets", {"query": "Test ETF World"})
        assert not err and str(ids["asset"]) in text


async def test_create_transactions_all_or_nothing_and_dedup():
    async with _env() as (call, ids):
        rows = [_tx(ids), _tx(ids, type="SELL", date="2025-04-01", quantity=4, price=110.0)]
        err, text = await call("w", "create-transactions", {"transactions": rows})
        assert not err and "registrate: 2" in text
        # stessa chiamata ripetuta: nessun doppione
        err, text = await call("w", "create-transactions", {"transactions": rows})
        assert not err and "registrate: 0" in text and "già presenti: 2" in text
        # riga non valida (conto altrui): nulla viene scritto
        bad = [_tx(ids, date="2025-05-01"), _tx(ids, account_id=ids["other_account"])]
        err, text = await call("w", "create-transactions", {"transactions": bad})
        assert err and "riga 2" in text and "Nessuna transazione registrata" in text
        assert await _count(Transaction, account_id=ids["account"]) == 2
        # data futura rifiutata
        err, text = await call("w", "create-transactions", {"transactions": [_tx(ids, date="2099-01-01")]})
        assert err and "futura" in text
        assert await _count(AuditLog, user_id=ids["user"], action="MCP_CREATE_TRANSACTIONS") == 2


async def test_update_and_delete_transaction_permissions():
    async with _env() as (call, ids):
        await call("w", "create-transactions", {"transactions": [_tx(ids)]})
        async with AsyncSessionLocal() as db:
            tx_id = (await db.execute(select(Transaction.id).where(Transaction.account_id == ids["account"]))).scalar_one()

        err, text = await call("w", "update-transaction", {"transaction_id": tx_id, "price": 95.0})
        assert not err and "100.0 → 95.0" in text
        async with AsyncSessionLocal() as db:
            assert (await db.get(Transaction, tx_id)).price == 95.0

        # la transazione di un altro utente non è raggiungibile
        err, text = await call("wd", "update-transaction", {"transaction_id": ids["other_tx"], "price": 1.0})
        assert err and "non trovata" in text
        err, text = await call("wd", "delete-transaction", {"transaction_id": ids["other_tx"]})
        assert err and "non trovata" in text

        # cancellazione: serve il permesso dedicato
        err, text = await call("w", "delete-transaction", {"transaction_id": tx_id})
        assert err and "cancellazione" in text
        err, text = await call("wd", "delete-transaction", {"transaction_id": tx_id})
        assert not err and "cancellata" in text
        assert await _count(Transaction, id=tx_id) == 0
        assert await _count(Transaction, id=ids["other_tx"]) == 1
        assert await _count(AuditLog, user_id=ids["user"], action="MCP_DELETE_TRANSACTION") == 1


async def test_create_asset_is_idempotent_by_isin():
    async with _env() as (call, ids):
        args = {"name": "iShares Core MSCI World", "symbol": "SWDA", "type": "ETF", "isin": "IE00B4L5Y983",
                "currency": "EUR"}
        async with AsyncSessionLocal() as db:
            pre_existing = (await db.execute(select(Asset).where(Asset.isin == "IE00B4L5Y983"))).scalar_one_or_none()
        err, first = await call("w", "create-asset", args)
        err2, second = await call("w", "create-asset", args)
        assert not err and not err2
        assert first.split("ID ")[1].split(" ")[0] == second.split("ID ")[1].split(" ")[0]
        assert "già presente" in second
        err, text = await call("w", "create-asset", {**args, "isin": "IE00B4L5Y984"})
        assert err  # checksum ISIN non valido
        if pre_existing is None:
            async with AsyncSessionLocal() as db:
                await db.execute(sa_delete(Asset).where(Asset.isin == "IE00B4L5Y983"))
                await db.commit()


async def test_update_asset_classification():
    async with _env() as (call, ids):
        err, text = await call("w", "update-asset", {"asset_id": ids["asset"], "asset_class": "BOND",
                                                     "govt_bond_share_pct": 80})
        assert not err
        async with AsyncSessionLocal() as db:
            a = await db.get(Asset, ids["asset"])
            assert a.asset_class_override == "BOND" and a.govt_bond_share == pytest.approx(0.8)
        err, text = await call("w", "update-asset", {"asset_id": ids["asset"], "government_bond": "YES"})
        assert err and "BOND" in text  # è un ETF
        err, text = await call("w", "update-asset", {"asset_id": ids["asset"], "asset_class": "AUTO",
                                                     "govt_bond_share_pct": -1})
        assert not err
        async with AsyncSessionLocal() as db:
            a = await db.get(Asset, ids["asset"])
            assert a.asset_class_override is None and a.govt_bond_share is None


async def test_watchlist_and_alerts():
    async with _env() as (call, ids):
        err, text = await call("w", "add-to-watchlist", {"asset_id": ids["asset"], "target_price": 90})
        assert not err
        item_id = int(text.split("voce ")[1].split(" ")[0])
        err, text = await call("w", "add-to-watchlist", {"asset_id": ids["asset"]})
        assert err and "già in watchlist" in text
        err, _ = await call("w", "update-watchlist-item", {"item_id": item_id, "note": "comprare sotto 90"})
        assert not err
        err, text = await call("w", "remove-from-watchlist", {"item_id": item_id})
        assert err and "cancellazione" in text
        err, _ = await call("wd", "remove-from-watchlist", {"item_id": item_id})
        assert not err
        assert await _count(WatchlistItem, user_id=ids["user"]) == 0

        err, text = await call("w", "create-alert", {"asset_id": ids["asset"], "alert_type": "PRICE_BELOW",
                                                     "threshold": 80})
        assert not err
        alert_id = int(text.split("Alert ")[1].split(" ")[0])
        err, text = await call("w", "update-alert", {"alert_id": alert_id, "is_active": False})
        assert not err and "disattivo" in text
        err, text = await call("ro", "get-alerts")
        assert not err and "PRICE_BELOW" in text
        err, _ = await call("wd", "delete-alert", {"alert_id": alert_id})
        assert not err
        assert await _count(PriceAlert, user_id=ids["user"]) == 0


async def test_transactions_table_has_ids_for_editing():
    async with _env() as (call, ids):
        await call("w", "create-transactions", {"transactions": [_tx(ids)]})
        err, text = await call("ro", "get-transactions")
        assert not err and text.splitlines()[0].startswith("| ID |")
