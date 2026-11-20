"""Dettaglio titolo: lo storico prezzi non si limita alla data del primo acquisto (PostgreSQL + Redis, saltato senza DB)."""
import datetime
import uuid
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete as sa_delete

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.account import Account
from app.models.asset import Asset, PriceHistory
from app.models.transaction import Transaction
from app.models.user import User

TODAY = datetime.date.today()


@asynccontextmanager
async def _env(buy_days_ago: int):
    sfx = uuid.uuid4().hex[:8]
    try:
        async with AsyncSessionLocal() as db:
            user = User(email=f"hist_{sfx}@test.nextfolio", password_hash=hash_password("x" * 12), name="H")
            db.add(user)
            await db.flush()
            acc = Account(user_id=user.id, name="Broker", currency="EUR")
            asset = Asset(symbol=f"B{sfx}".upper(), name=f"Bond {sfx}", type="BOND", exchange="MOT", currency="EUR")
            db.add_all([acc, asset])
            await db.flush()
            db.add(Transaction(account_id=acc.id, asset_id=asset.id, type="BUY", date=TODAY - datetime.timedelta(days=buy_days_ago),
                               quantity=10, price=97, price_currency="EUR", exchange_rate=1, fee=0))
            for i in range(0, 800):   # circa 2 anni di storico
                db.add(PriceHistory(asset_id=asset.id, date=TODAY - datetime.timedelta(days=i), open=96, high=97, low=95,
                                    close=96.0 + (i % 5) * 0.1, volume=0))
            await db.commit()
            ids = dict(user=user.id, asset=asset.id)
    except OSError as e:
        pytest.skip(f"Database non disponibile: {e}")
    headers = {"Authorization": f"Bearer {create_access_token(str(ids['user']))}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        try:
            yield c, headers, ids
        finally:
            async with AsyncSessionLocal() as db:
                await db.execute(sa_delete(User).where(User.id == ids["user"]))
                await db.execute(sa_delete(Asset).where(Asset.id == ids["asset"]))
                await db.commit()


async def test_recently_bought_asset_still_has_a_chart():
    """Comprato oggi: il grafico mostra l'ultimo anno, non un solo punto."""
    async with _env(buy_days_ago=0) as (c, h, ids):
        d = (await c.get(f"/api/v1/portfolio/holding/{ids['asset']}", headers=h)).json()
        dates = [p["date"] for p in d["price_history"]]
        assert 360 <= len(dates) <= 370
        assert dates[0] >= (TODAY - datetime.timedelta(days=366)).isoformat() and dates[-1] == TODAY.isoformat()


async def test_old_purchase_keeps_history_since_purchase():
    async with _env(buy_days_ago=600) as (c, h, ids):
        d = (await c.get(f"/api/v1/portfolio/holding/{ids['asset']}", headers=h)).json()
        assert len(d["price_history"]) == 601                      # dal giorno dell'acquisto, non oltre
        assert d["price_history"][0]["date"] == (TODAY - datetime.timedelta(days=600)).isoformat()
