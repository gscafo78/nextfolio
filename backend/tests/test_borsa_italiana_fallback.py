"""Borsa Italiana: fallback sul codice di mercato quando quello previsto non ha i grafici del titolo."""
import httpx
import pytest

from app.models.asset import Exchange
from app.services.market_data import borsa_italiana as bi

ISIN = "IT0005619546"
REAL_CLIENT = httpx.AsyncClient   # prima di qualsiasi monkeypatch
HISTORY = {"history": {"historyDt": [
    {"dt": "20241025", "openPx": 101.1, "closePx": 100.15, "highPx": 101.5, "lowPx": 100.0, "tradedQty": 10},
    {"dt": "20261119", "openPx": 96.7, "closePx": 96.8, "highPx": 96.9, "lowPx": 96.6, "tradedQty": 5},
]}}


def _install(monkeypatch, handler):
    async def jwt(isin, mic):
        return f"tok-{mic}"

    monkeypatch.setattr(bi, "_get_jwt", jwt)
    monkeypatch.setattr(bi.httpx, "AsyncClient", lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(handler)))
    bi._WORKING_MIC.clear()


def _mic(request: httpx.Request) -> str:
    return request.url.path.split(",")[1]


async def test_history_falls_back_to_working_market(monkeypatch):
    calls = []

    def handler(request):
        mic = _mic(request)
        calls.append(mic)
        if mic == "XMIL":
            return httpx.Response(200, json=HISTORY)
        if mic == "MOTX":     # caso reale: chiave non valida
            return httpx.Response(400, json={"message": "'IT0005619546,MOTX,ISIN' is not a correct value for 'InstrumentKey'"})
        return httpx.Response(200, json={"status": 2304, "view": "HISTORY"})   # ETLX: nessun dato

    _install(monkeypatch, handler)
    records = await bi.get_history(ISIN, Exchange.MOT, fill_gaps=False)
    assert [r["date"] for r in records] == ["2024-10-25", "2026-11-19"]
    assert calls == ["MOTX", "XMIL"]
    # il mercato funzionante viene ricordato: la chiamata successiva parte da XMIL
    calls.clear()
    await bi.get_history(ISIN, Exchange.MOT, fill_gaps=False)
    assert calls == ["XMIL"]


async def test_history_without_data_anywhere_returns_empty_or_raises(monkeypatch):
    _install(monkeypatch, lambda request: httpx.Response(200, json={"status": 2304, "view": "HISTORY"}))
    assert await bi.get_history(ISIN, Exchange.MOT, fill_gaps=False) == []
    _install(monkeypatch, lambda request: httpx.Response(400, json={"message": "bad"}))
    with pytest.raises(httpx.HTTPStatusError):
        await bi.get_history(ISIN, Exchange.MOT, fill_gaps=False)


async def test_current_price_falls_back_to_history_last_close(monkeypatch):
    def handler(request):
        if request.url.path.endswith("/price"):
            return httpx.Response(404, json={"status": 404})
        return httpx.Response(200, json=HISTORY) if _mic(request) == "XMIL" else httpx.Response(400, json={})

    _install(monkeypatch, handler)
    price = await bi.get_current_price(ISIN, Exchange.MOT)
    assert price["price"] == 96.8 and price["prev_close"] == 100.15
