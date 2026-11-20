"""Monitor convenienza vendita: endpoint e task giornaliero (PostgreSQL + Redis, email simulata). Saltati senza DB."""
import datetime
import uuid
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete as sa_delete
from sqlalchemy import select, update

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.account import Account
from app.models.asset import Asset, PriceHistory
from app.models.bond_detail import BondDetail
from app.models.bond_monitor import BondMonitor
from app.models.transaction import Transaction
from app.models.user import User
from app.tasks.bond_monitor import process_bond_monitors

TODAY = datetime.date.today()


@asynccontextmanager
async def _env(with_bond_detail=True):
    sfx = uuid.uuid4().hex[:8]
    try:
        async with AsyncSessionLocal() as db:
            user = User(email=f"bm_{sfx}@test.nextfolio", password_hash=hash_password("x" * 12), name="B")
            other = User(email=f"bm_o_{sfx}@test.nextfolio", password_hash=hash_password("x" * 12), name="O")
            db.add_all([user, other])
            await db.flush()
            acc = Account(user_id=user.id, name="Broker", currency="EUR")
            bond = Asset(symbol=f"B{sfx}".upper(), name=f"BTP Test {sfx}", type="BOND", exchange="MOT", currency="EUR",
                         isin=None)
            etf = Asset(symbol=f"E{sfx}".upper(), name=f"ETF {sfx}", type="ETF", exchange="OTHER", currency="EUR")
            db.add_all([acc, bond, etf])
            await db.flush()
            db.add(Transaction(account_id=acc.id, asset_id=bond.id, type="BUY", date=TODAY - datetime.timedelta(days=900),
                               quantity=10, price=94, price_currency="EUR", exchange_rate=1, fee=0))
            for i in range(2):   # due cedole già incassate (1,25 a quota)
                db.add(Transaction(account_id=acc.id, asset_id=bond.id, type="COUPON",
                                   date=TODAY - datetime.timedelta(days=500 - i * 182), quantity=10, price=1.25,
                                   price_currency="EUR", exchange_rate=1, fee=0))
            db.add(PriceHistory(asset_id=bond.id, date=TODAY, open=120, high=120, low=120, close=120.0, volume=0))
            if with_bond_detail:
                db.add(BondDetail(asset_id=bond.id, face_value=100.0, coupon_rate=0.025, coupon_frequency="SEMI_ANNUAL",
                                  first_coupon_date=TODAY + datetime.timedelta(days=60),
                                  maturity_date=TODAY.replace(year=TODAY.year + 5)))
            await db.commit()
            ids = dict(user=user.id, other=other.id, bond=bond.id, etf=etf.id)
    except OSError as e:
        pytest.skip(f"Database non disponibile: {e}")

    auth = lambda uid: {"Authorization": f"Bearer {create_access_token(str(uid))}"}  # noqa: E731
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        try:
            yield c, auth, ids
        finally:
            async with AsyncSessionLocal() as db:
                await db.execute(sa_delete(User).where(User.id.in_([ids["user"], ids["other"]])))
                await db.execute(sa_delete(Asset).where(Asset.id.in_([ids["bond"], ids["etf"]])))
                await db.commit()


@pytest.fixture
def smtp_on(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(settings, "SMTP_USER", "u")
    monkeypatch.setattr(settings, "EMAILS_FROM", "noreply@test")


async def _set_price(asset_id, price):
    async with AsyncSessionLocal() as db:
        await db.execute(update(PriceHistory).where(PriceHistory.asset_id == asset_id).values(close=price))
        await db.commit()


async def test_enable_get_disable_and_validation():
    async with _env() as (c, auth, ids):
        h = auth(ids["user"])
        url = f"/api/v1/bonds/assets/{ids['bond']}/monitor"
        before = (await c.get(url, headers=h)).json()
        assert before["enabled"] is False and before["evaluation"]["status"] == "ok"
        assert before["evaluation"]["should_sell"] is True and before["evaluation"]["future_coupons"] >= 8

        on = (await c.put(url, json={"enabled": True}, headers=h)).json()
        assert on["enabled"] is True and on["active"] is False
        assert [m["asset_id"] for m in (await c.get("/api/v1/bonds/monitors", headers=h)).json()] == [ids["bond"]]
        assert (await c.put(url, json={"enabled": False}, headers=h)).json()["enabled"] is False

        # non è un'obbligazione / l'altro utente non ha una posizione
        assert (await c.put(f"/api/v1/bonds/assets/{ids['etf']}/monitor", json={"enabled": True}, headers=h)).status_code == 400
        other = await c.put(url, json={"enabled": True}, headers=auth(ids["other"]))
        assert other.status_code == 400 and "posizione" in other.json()["detail"]
        assert (await c.get("/api/v1/bonds/monitors", headers=auth(ids["other"]))).json() == []


async def test_enable_requires_coupon_configuration():
    async with _env(with_bond_detail=False) as (c, auth, ids):
        r = await c.put(f"/api/v1/bonds/assets/{ids['bond']}/monitor", json={"enabled": True}, headers=auth(ids["user"]))
        assert r.status_code == 400 and "Cedole non configurate" in r.json()["detail"]


async def test_daily_task_sends_one_email_then_rearms(smtp_on):
    async with _env() as (c, auth, ids):
        await c.put(f"/api/v1/bonds/assets/{ids['bond']}/monitor", json={"enabled": True}, headers=auth(ids["user"]))
        sent = []

        async def fake_send(**kw):
            sent.append(kw)

        async def run():
            async with AsyncSessionLocal() as db:
                return await process_bond_monitors(db, send_signal=fake_send)

        r1 = await run()
        assert r1["notified"] == 1 and len(sent) == 1
        assert sent[0]["ev"]["should_sell"] is True and sent[0]["ev"]["advantage_eur"] > 0
        assert (await run())["notified"] == 0 and len(sent) == 1                  # stessa condizione: niente ripetizioni

        await _set_price(ids["bond"], 99.0)                                       # rientra: conviene tenere
        assert (await run())["notified"] == 0
        async with AsyncSessionLocal() as db:
            m = (await db.execute(select(BondMonitor).where(BondMonitor.asset_id == ids["bond"]))).scalar_one()
            assert m.active is False and m.last_result["should_sell"] is False and m.last_notified_at is not None

        await _set_price(ids["bond"], 125.0)                                      # risale: nuova email
        assert (await run())["notified"] == 1 and len(sent) == 2


async def test_task_disables_monitor_when_position_closed_and_survives_mail_failure(smtp_on):
    async with _env() as (c, auth, ids):
        await c.put(f"/api/v1/bonds/assets/{ids['bond']}/monitor", json={"enabled": True}, headers=auth(ids["user"]))

        async def failing(**kw):
            raise RuntimeError("smtp down")

        async with AsyncSessionLocal() as db:
            assert (await process_bond_monitors(db, send_signal=failing))["notified"] == 0
        async with AsyncSessionLocal() as db:   # invio fallito: si riprova al controllo successivo
            m = (await db.execute(select(BondMonitor).where(BondMonitor.asset_id == ids["bond"]))).scalar_one()
            assert m.active is False and m.last_notified_at is None

        async with AsyncSessionLocal() as db:   # vendita totale → il monitor si spegne da solo
            acc = (await db.execute(select(Account).where(Account.user_id == ids["user"]))).scalar_one()
            db.add(Transaction(account_id=acc.id, asset_id=ids["bond"], type="SELL", date=TODAY, quantity=10, price=120,
                               price_currency="EUR", exchange_rate=1, fee=0))
            await db.commit()
        async with AsyncSessionLocal() as db:
            r = await process_bond_monitors(db, send_signal=failing)
            assert r["disabled"] == 1
        async with AsyncSessionLocal() as db:
            m = (await db.execute(select(BondMonitor).where(BondMonitor.asset_id == ids["bond"]))).scalar_one()
            assert m.enabled is False
