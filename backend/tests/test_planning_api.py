"""Pagina Pianifica — integrazione (PostgreSQL + Redis), Yahoo simulato. Saltati senza DB."""
import datetime
import uuid
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete as sa_delete
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.account import Account
from app.models.asset import Asset, PriceHistory
from app.models.transaction import Transaction
from app.models.user import User
from app.services.market_data import external

TODAY = datetime.date.today()


@pytest.fixture
def fake_yahoo(monkeypatch):
    async def search(q, limit=10, search_fn=None):
        return [external.map_yahoo_quote({"symbol": "X13G.DE", "shortname": "Xtrackers Eurozone Govt Bond 1-3",
                                          "quoteType": "ETF", "exchange": "GER"})]

    async def quote(symbol):
        return {"price": 140.0, "price_eur": 140.0, "currency": "EUR", "change_pct": 0.1}

    async def profile(symbol, t):
        return {"countries": [{"code": "FR", "weight": 0.5}, {"code": "IT", "weight": 0.5}]}

    async def history(symbol, period="1y"):
        return [{"date": (TODAY - datetime.timedelta(days=i)).isoformat(), "close": 140.0 - i * 0.01}
                for i in range(400, -1, -1)]

    async def no_enrich(db, asset):
        return False

    monkeypatch.setattr(external, "search_yahoo", search)
    monkeypatch.setattr(external, "quote_eur", quote)
    monkeypatch.setattr(external, "profile", profile)
    monkeypatch.setattr(external, "history_eur", history)
    import app.services.market_data.enricher as enricher
    monkeypatch.setattr(enricher, "enrich_asset", no_enrich)


@asynccontextmanager
async def _env():
    sfx = uuid.uuid4().hex[:8]
    try:
        async with AsyncSessionLocal() as db:
            user = User(email=f"plan_{sfx}@test.nextfolio", password_hash=hash_password("x" * 12), name="P")
            other = User(email=f"plan_o_{sfx}@test.nextfolio", password_hash=hash_password("x" * 12), name="O")
            db.add_all([user, other])
            await db.flush()
            acc = Account(user_id=user.id, name="Broker", currency="EUR")
            asset = Asset(symbol=f"W{sfx}".upper(), name=f"World Equity {sfx}", type="ETF", exchange="OTHER",
                          currency="EUR", countries=[{"code": "US", "weight": 1.0}])
            db.add_all([acc, asset])
            await db.flush()
            db.add(Transaction(account_id=acc.id, asset_id=asset.id, type="BUY", date=TODAY - datetime.timedelta(days=30),
                               quantity=100, price=90, price_currency="EUR", exchange_rate=1, fee=0))
            for i in range(40):
                db.add(PriceHistory(asset_id=asset.id, date=TODAY - datetime.timedelta(days=i), open=100, high=100,
                                    low=100, close=100.0, volume=0))
            await db.commit()
            ids = dict(user=user.id, other=other.id, account=acc.id, asset=asset.id, sfx=sfx)
    except OSError as e:
        pytest.skip(f"Database non disponibile: {e}")

    def auth(uid):
        return {"Authorization": f"Bearer {create_access_token(str(uid))}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        try:
            yield c, auth, ids
        finally:
            async with AsyncSessionLocal() as db:
                await db.execute(sa_delete(User).where(User.id.in_([ids["user"], ids["other"]])))
                await db.execute(sa_delete(Asset).where(Asset.id == ids["asset"]))
                await db.execute(sa_delete(Asset).where(Asset.yahoo_ticker == "X13G.DE"))
                await db.commit()


async def test_search_min_chars_local_first_and_yahoo(fake_yahoo):
    async with _env() as (c, auth, ids):
        h = auth(ids["user"])
        assert (await c.get("/api/v1/planning/search", params={"q": "Wo"}, headers=h)).status_code == 422
        res = (await c.get("/api/v1/planning/search", params={"q": f"World Equity {ids['sfx']}"}, headers=h)).json()
        assert res[0]["source"] == "local" and res[0]["in_portfolio"] is True
        assert any(r["source"] == "yahoo" and r["symbol"] == "X13G.DE" for r in res)
        only_stock = (await c.get("/api/v1/planning/search", params={"q": "Govt Bond", "type": "STOCK"}, headers=h)).json()
        assert not any(r["source"] == "yahoo" for r in only_stock)


async def test_security_cards(fake_yahoo):
    async with _env() as (c, auth, ids):
        h = auth(ids["user"])
        local = (await c.get("/api/v1/planning/security", params={"asset_id": ids["asset"]}, headers=h)).json()
        assert local["price_eur"] == 100.0 and local["in_portfolio"] and local["asset_class"] == "Azioni"
        ext = (await c.get("/api/v1/planning/security", headers=h, params={
            "symbol": "X13G.DE", "type": "ETF", "name": "Xtrackers Eurozone Govt Bond 1-3"})).json()
        assert ext["source"] == "yahoo" and ext["asset_class"] == "Obbligazioni" and ext["price_eur"] == 140.0
        assert ext["metrics"]["return_1y_pct"] is not None and ext["history"]


async def test_simulate_local_and_external(fake_yahoo):
    async with _env() as (c, auth, ids):
        h = auth(ids["user"])
        body = {"items": [{"symbol": "X13G.DE", "name": "Xtrackers Eurozone Govt Bond 1-3", "type": "ETF",
                           "amount_eur": 2500, "account_id": ids["account"]},
                          {"asset_id": ids["asset"], "quantity": 10}]}
        r = await c.post("/api/v1/planning/simulate", json=body, headers=h)
        assert r.status_code == 200, r.text
        sim = r.json()
        after = {i["label"]: i["pct"] for i in sim["allocation_after"]["by_asset_class"]}
        assert after["Obbligazioni"] == pytest.approx(2500 / 13500 * 100, abs=0.1)
        assert sim["invested_eur"] == pytest.approx(3500)
        bad = await c.post("/api/v1/planning/simulate", headers=h,
                           json={"items": [{"asset_id": ids["asset"], "quantity": 1, "amount_eur": 5}]})
        assert bad.status_code == 422      # importo o quantità, non entrambi


async def test_scenarios_crud_compare_execute(fake_yahoo):
    async with _env() as (c, auth, ids):
        h = auth(ids["user"])
        payload = {"name": "Più obbligazioni", "items": [
            {"symbol": "X13G.DE", "name": "Xtrackers Eurozone Govt Bond 1-3", "type": "ETF", "amount_eur": 1400}]}
        sc = (await c.post("/api/v1/planning/scenarios", json=payload, headers=h)).json()
        assert sc["status"] == "draft" and len(sc["items"]) == 1
        # un altro utente non lo vede
        assert (await c.get(f"/api/v1/planning/scenarios/{sc['id']}", headers=auth(ids["other"]))).status_code == 404
        full = (await c.get(f"/api/v1/planning/scenarios/{sc['id']}", headers=h)).json()
        assert full["simulation"]["invested_eur"] == pytest.approx(1400)
        sc2 = (await c.post("/api/v1/planning/scenarios", headers=h,
                            json={"name": "Più azioni", "items": [{"asset_id": ids["asset"], "amount_eur": 1000}]})).json()
        cmp = (await c.get("/api/v1/planning/scenarios/compare", params={"ids": f"{sc['id']},{sc2['id']}"}, headers=h)).json()
        assert [x["scenario"]["name"] for x in cmp] == ["Più obbligazioni", "Più azioni"]

        item_id = sc["items"][0]["id"]
        ex = {"account_id": ids["account"], "items": [{"item_id": item_id, "quantity": 10, "price": 140.0, "fee": 1}]}
        r = await c.post(f"/api/v1/planning/scenarios/{sc['id']}/execute", json=ex, headers=h)
        assert r.status_code == 200, r.text
        assert len(r.json()["created"]) == 1
        async with AsyncSessionLocal() as db:
            imported = (await db.execute(select(Asset).where(Asset.yahoo_ticker == "X13G.DE"))).scalar_one()
            assert imported.name.startswith("Xtrackers")
            txs = (await db.execute(select(Transaction).where(Transaction.asset_id == imported.id))).scalars().all()
            assert len(txs) == 1 and txs[0].quantity == 10
        again = await c.post(f"/api/v1/planning/scenarios/{sc['id']}/execute", json=ex, headers=h)
        assert again.status_code == 400
        assert (await c.put(f"/api/v1/planning/scenarios/{sc['id']}", json=payload, headers=h)).status_code == 400
        assert (await c.delete(f"/api/v1/planning/scenarios/{sc2['id']}", headers=h)).status_code == 204
        assert len((await c.get("/api/v1/planning/scenarios", headers=h)).json()) == 1


async def test_execute_rejects_other_users_account(fake_yahoo):
    async with _env() as (c, auth, ids):
        h = auth(ids["user"])
        async with AsyncSessionLocal() as db:
            other_acc = Account(user_id=ids["other"], name="Altrui", currency="EUR")
            db.add(other_acc)
            await db.commit()
            other_id = other_acc.id
        sc = (await c.post("/api/v1/planning/scenarios", headers=h,
                           json={"name": "X", "items": [{"asset_id": ids["asset"], "quantity": 1}]})).json()
        r = await c.post(f"/api/v1/planning/scenarios/{sc['id']}/execute", headers=h, json={
            "account_id": other_id, "items": [{"item_id": sc["items"][0]["id"], "quantity": 1, "price": 100}]})
        assert r.status_code == 400 and "conto" in r.json()["detail"]


# ── 1.14: allocazione obiettivo, versamento, obiettivi, proiezione, FIRE ─────

async def test_targets_drift_and_contribution(fake_yahoo):
    async with _env() as (c, auth, ids):
        h = auth(ids["user"])
        assert (await c.get("/api/v1/planning/targets", headers=h)).json() is None
        assert (await c.get("/api/v1/planning/drift", headers=h)).json()["configured"] is False
        bad = await c.put("/api/v1/planning/targets", headers=h, json={"weights": {"EQUITY": 70, "BOND": 20}})
        assert bad.status_code == 422                               # non somma 100
        body = {"weights": {"EQUITY": 70, "BOND": 30}, "tolerance_pct": 5,
                "preferred": {"BOND": [{"symbol": "X13G.DE", "name": "Govt 1-3", "type": "ETF", "weight": 1}]}}
        assert (await c.put("/api/v1/planning/targets", headers=h, json=body)).status_code == 200
        assert (await c.get("/api/v1/planning/targets", headers=h)).json()["weights"] == {"EQUITY": 70.0, "BOND": 30.0}
        d = (await c.get("/api/v1/planning/drift", headers=h)).json()
        eq = next(r for r in d["classes"] if r["class"] == "EQUITY")
        assert eq["current_pct"] == pytest.approx(100) and d["out_of_band"] is True

        plan = (await c.post("/api/v1/planning/contribution", headers=h, json={"amount_eur": 1400})).json()
        assert [o["name"] for o in plan["orders"]] == ["Govt 1-3"] and plan["orders"][0]["quantity"] == 10
        none = await c.post("/api/v1/planning/contribution", headers=h, json={"from_cash": True})
        assert none.status_code == 400                              # nessuna liquidità registrata


async def test_goals_projection_fire(fake_yahoo):
    async with _env() as (c, auth, ids):
        h = auth(ids["user"])
        target_date = (TODAY.replace(year=TODAY.year + 10)).isoformat()
        g = (await c.post("/api/v1/planning/goals", headers=h, json={
            "name": "Casa", "target_amount": 50_000, "target_date": target_date, "monthly_contribution": 200})).json()
        assert g["id"] and (await c.get("/api/v1/planning/goals", headers=h)).json()[0]["name"] == "Casa"
        assert (await c.get("/api/v1/planning/goals", headers=auth(ids["other"]))).json() == []
        p = (await c.post("/api/v1/planning/projection", headers=h, json={
            "target_amount": 50_000, "target_date": target_date, "monthly_contribution": 200})).json()
        assert p["initial_amount"] == pytest.approx(10_000) and 0 <= p["probability"] <= 1
        assert p["weights_pct"] == {"EQUITY": 100.0} and p["expected_return_pct"] == pytest.approx(7.0)
        past = await c.post("/api/v1/planning/projection", headers=h, json={"target_amount": 1, "target_date": "2020-01-01"})
        assert past.status_code == 400
        f = (await c.post("/api/v1/planning/fire", headers=h, json={"annual_expenses": 24_000})).json()
        assert f["target_capital"] == pytest.approx(24_000 / 0.035, rel=1e-3)
        assert (await c.put(f"/api/v1/planning/goals/{g['id']}", headers=h, json={**g, "target_amount": 60_000})).json()["target_amount"] == 60_000
        assert (await c.delete(f"/api/v1/planning/goals/{g['id']}", headers=auth(ids["other"]))).status_code == 404
        assert (await c.delete(f"/api/v1/planning/goals/{g['id']}", headers=h)).status_code == 204
