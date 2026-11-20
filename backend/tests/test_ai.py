"""
Test funzioni AI: formattatore Markdown, prompt per chatbot, server MCP.

I test unitari non richiedono il database (dati finti + monkeypatch).
I test di integrazione in fondo usano PostgreSQL come test_api.py e vengono
saltati se il DB non è raggiungibile.
"""
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.mcp import server as mcp_server
from app.schemas.portfolio import AllocationItem, AllocationOut
from app.services.ai import context as ai

BASE = "http://test"
MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
    "MCP-Protocol-Version": "2025-06-18",
}


# ── Dati finti ────────────────────────────────────────────────────────────────


def _asset(**kw):
    base = dict(id=1, name="Vanguard FTSE All-World", symbol="VWCE", isin="IE00BK5BQT80",
                type="ETF", currency="EUR", sectors=None, countries=None)
    return SimpleNamespace(**{**base, **kw})


def _snapshot() -> ai.Snapshot:
    h1 = ai.Holding(asset=_asset(), quantity=10, pmc_eur=100.0, invested_eur=1000.0, realized_pnl_eur=0,
                    price=123.45, price_eur=123.45, value_eur=1234.5, unrealized_eur=234.5,
                    unrealized_pct=23.45, change_pct=0.5, weight_pct=80.0)
    h2 = ai.Holding(asset=_asset(id=2, name="BTP | Italia 2033", symbol="BTP33", isin="IT0005000000", type="BOND"),
                    quantity=3, pmc_eur=99.0, invested_eur=297.0, realized_pnl_eur=0,
                    price=102.9, price_eur=102.9, value_eur=308.7, unrealized_eur=11.7,
                    unrealized_pct=3.94, change_pct=None, weight_pct=20.0)
    alloc = AllocationOut(
        by_type=[AllocationItem(label="ETF", value_eur=1234.5, pct=80.0, count=1),
                 AllocationItem(label="Obbligazioni", value_eur=308.7, pct=20.0, count=1)],
        by_currency=[AllocationItem(label="EUR", value_eur=1543.2, pct=100.0, count=2)],
        by_account=[], total_value_eur=1543.2,
    )
    acc = SimpleNamespace(id=7, name="Fineco", type="BROKERAGE", broker="Fineco", currency="EUR",
                          is_sostituto_imposta=True, is_foreign=False)
    return ai.Snapshot(
        transactions=[], holdings=[h1, h2], accounts=[acc], account_values={"Fineco": 1543.2},
        allocation=alloc, realized_pnl_eur=50.0, total_value_eur=1543.2, total_invested_eur=1297.0,
    )


# ── Formattatore ──────────────────────────────────────────────────────────────


def test_table_escapes_pipes_and_handles_empty():
    assert ai.table(["A"], []) == "_Nessun dato._"
    out = ai.table(["Nome", "Valore"], [["a|b", None], ["c", 1.234]])
    lines = out.splitlines()
    assert lines[0] == "| Nome | Valore |"
    assert lines[2] == "| a/b | n/d |"
    assert lines[3] == "| c | 1.23 |"


def test_holdings_with_values_contains_amounts():
    out = ai.holdings_table(_snapshot(), with_values=True)
    assert "Valore (EUR)" in out
    assert "1234.50" in out
    assert "80.00%" in out
    assert "BTP / Italia 2033" in out  # pipe neutralizzato


def test_holdings_without_values_hides_amounts():
    snap = _snapshot()
    for out in (
        ai.holdings_table(snap, with_values=False),
        ai.summary_section(snap, with_values=False),
        ai.allocation_section(snap, with_values=False),
        ai.accounts_table(snap, with_values=False),
    ):
        assert "EUR)" not in out
        for amount in ("1234.5", "1000.00", "308.7", "1543.2", "234.5"):
            assert amount not in out
    assert "80.00%" in ai.holdings_table(snap, with_values=False)
    assert "23.45%" in ai.holdings_table(snap, with_values=False)


def test_transactions_table_hides_amounts():
    tx = SimpleNamespace(id=1, date=date(2024, 3, 1), type="BUY", account=SimpleNamespace(name="Fineco"),
                         asset=_asset(), quantity=10, price=100.0, price_currency="EUR",
                         exchange_rate=1.0, fee=2.95)
    assert "2.95" in ai.transactions_table([tx], with_values=True)
    hidden = ai.transactions_table([tx], with_values=False)
    assert "2.95" not in hidden and "100.00" not in hidden
    assert "2024-03-01" in hidden and "VWCE" in hidden


# ── Prompt ────────────────────────────────────────────────────────────────────


@pytest.fixture
def fake_context(monkeypatch):
    calls = {}

    async def _ctx(db, user, *, with_values, account_id=None, asset_type=None):
        calls.update(with_values=with_values, account_id=account_id, asset_type=asset_type)
        return "## DATI"

    monkeypatch.setattr(ai, "build_portfolio_context", _ctx)
    return calls


async def test_prompt_portfolio_mode_is_data_only(fake_context):
    out = await ai.build_prompt(None, None, mode="portfolio", language="it", with_values=True)
    assert out == "## DATI"


@pytest.mark.parametrize("lang,needle", [("it", "Rispondi in italiano"), ("en", "in English"),
                                         ("fr", "en français"), ("de", "auf Deutsch")])
async def test_prompt_analysis_mode_localized(fake_context, lang, needle):
    out = await ai.build_prompt(None, None, mode="analysis", language=lang, with_values=True, account_id=3)
    assert "## DATI" in out and needle in out
    assert out.count("\n1. ") == 1 and "\n7. " in out
    assert fake_context["account_id"] == 3


async def test_prompt_without_values_mentions_privacy(fake_context):
    out = await ai.build_prompt(None, None, mode="analysis", language="it", with_values=False)
    assert "importi assoluti sono stati omessi" in out
    assert fake_context["with_values"] is False


# ── Server MCP ────────────────────────────────────────────────────────────────


@asynccontextmanager
async def mcp_client():
    """Client con lifespan attivo (serve al session manager MCP).

    Non è una fixture: il task group di anyio deve aprirsi e chiudersi nello
    stesso task, cosa non garantita dalle fixture asincrone di pytest-asyncio.
    """
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
            yield c


def _rpc(method, params=None, id_=1):
    return {"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}


@pytest.fixture
def fake_access(monkeypatch):
    """Token 'nfmcp_ok' valido per l'utente 42; snapshot finto senza DB."""
    state = {"can_read_values": False}
    user = SimpleNamespace(id=42, is_active=True)

    async def _resolve(db, token):
        if token != "nfmcp_ok":
            return None
        return user, SimpleNamespace(id=1, can_read_values=state["can_read_values"], can_write=False,
                                     can_delete=False)

    async def _user(db, uid):
        return user if uid == 42 else None

    async def _snap(db, u, **kw):
        assert u is user
        return _snapshot()

    monkeypatch.setattr(mcp_server, "resolve_token", _resolve)
    monkeypatch.setattr(mcp_server, "get_user_by_id", _user)
    monkeypatch.setattr(ai, "load_snapshot", _snap)
    return state


async def test_mcp_requires_token():
    async with mcp_client() as mcp_client_:
        r = await mcp_client_.post("/api/mcp", headers=MCP_HEADERS, json=_rpc("tools/list"))
        assert r.status_code == 401
        assert r.headers["www-authenticate"].startswith('Bearer realm="nextfolio-mcp"')
        assert "invalid_token" not in r.headers["www-authenticate"]


async def test_mcp_rejects_invalid_token(fake_access):
    async with mcp_client() as mcp_client_:
        r = await mcp_client_.post("/api/mcp", headers={**MCP_HEADERS, "Authorization": "Bearer nfmcp_bad"},
                                  json=_rpc("tools/list"))
        assert r.status_code == 401
        assert 'error="invalid_token"' in r.headers["www-authenticate"]


async def test_mcp_disabled(monkeypatch):
    async with mcp_client() as mcp_client_:
        monkeypatch.setattr(mcp_server.settings, "ENABLE_MCP", False)
        r = await mcp_client_.post("/api/mcp", headers=MCP_HEADERS, json=_rpc("tools/list"))
        assert r.status_code == 404


async def test_mcp_lists_tools_with_annotations(fake_access):
    async with mcp_client() as mcp_client_:
        h = {**MCP_HEADERS, "Authorization": "Bearer nfmcp_ok"}
        r = await mcp_client_.post("/api/mcp/", headers=h, json=_rpc("initialize", {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "pytest", "version": "1"},
        }))
        assert r.status_code == 200, r.text
        assert r.json()["result"]["serverInfo"]["name"] == "nextfolio"

        r = await mcp_client_.post("/api/mcp", headers=h, json=_rpc("tools/list", id_=2))
        assert r.status_code == 200, r.text
        tools = {t["name"]: t for t in r.json()["result"]["tools"]}
        assert {"get-portfolio", "get-accounts", "get-transactions", "get-performance", "get-allocation",
                "get-risk-metrics", "get-xray", "get-dividends", "get-watchlist", "get-tax-report"} <= set(tools)
        read = {"get-portfolio", "get-accounts", "get-transactions", "get-performance", "get-allocation",
            "get-risk-metrics", "get-xray", "get-dividends", "get-watchlist", "get-tax-report",
            "search-assets", "get-alerts", "search-securities", "simulate-purchase", "get-scenarios",
            "suggest-contribution", "project-goal", "compare-securities", "simulate-sale-tax", "get-bond-monitors"}
    assert all(tools[n]["annotations"]["readOnlyHint"] for n in read)
    deletes = {"delete-transaction", "remove-from-watchlist", "delete-alert"}
    assert all(tools[n]["annotations"]["destructiveHint"] for n in deletes)
    writes = set(tools) - read
    assert {"create-transactions", "update-transaction", "create-asset", "update-asset", "add-to-watchlist",
            "create-alert"} <= writes
    assert not any(tools[n]["annotations"]["readOnlyHint"] for n in writes)


@pytest.mark.parametrize("can_read_values", [False, True])
async def test_mcp_get_portfolio_respects_value_permission(fake_access, can_read_values):
    async with mcp_client() as mcp_client_:
        fake_access["can_read_values"] = can_read_values
        h = {**MCP_HEADERS, "Authorization": "Bearer nfmcp_ok"}
        r = await mcp_client_.post("/api/mcp", headers=h, json=_rpc("tools/call", {"name": "get-portfolio", "arguments": {}}))
        assert r.status_code == 200, r.text
        result = r.json()["result"]
        assert result["isError"] is False
        text = result["content"][0]["text"]
        assert "VWCE" in text and "80.00%" in text
        assert ("1234.50" in text) is can_read_values
        assert ("Valore (EUR)" in text) is can_read_values


async def test_mcp_tax_report_without_values_has_rules_only(fake_access):
    async with mcp_client() as mcp_client_:
        h = {**MCP_HEADERS, "Authorization": "Bearer nfmcp_ok"}
        r = await mcp_client_.post("/api/mcp", headers=h,
                                  json=_rpc("tools/call", {"name": "get-tax-report", "arguments": {"year": 2025}}))
        text = r.json()["result"]["content"][0]["text"]
        assert "Importi omessi" in text and "redditi di capitale" in text


# ── Integrazione (PostgreSQL) ─────────────────────────────────────────────────

_suffix = uuid.uuid4().hex[:8]
_EMAIL = f"pytest_ai_{_suffix}@test.nextfolio"
_PASS = "TestPass123!"


async def _login(c) -> dict:
    try:
        await c.post("/api/v1/auth/register", json={"email": _EMAIL, "password": _PASS, "name": "Pytest AI"})
        login = await c.post("/api/v1/auth/login", json={"email": _EMAIL, "password": _PASS})
    except Exception as e:  # DB non raggiungibile
        pytest.skip(f"Database non disponibile: {e}")
    if login.status_code != 200:
        pytest.skip("Impossibile ottenere un token (registrazione chiusa)")
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def test_integration_prompt_and_tokens():
    async with mcp_client() as mcp_client_:
        auth_headers = await _login(mcp_client_)
        r = await mcp_client_.get("/api/v1/ai/prompt", params={"mode": "analysis", "lang": "en"}, headers=auth_headers)
        assert r.status_code == 200, r.text
        assert "Provide your answer in English." in r.json()["prompt"]

        r = await mcp_client_.post("/api/v1/ai/mcp-tokens", json={"name": "pytest", "can_read_values": False},
                                  headers=auth_headers)
        assert r.status_code == 201, r.text
        created = r.json()
        token = created["token"]
        assert token.startswith("nfmcp_") and created["token_prefix"] == token[:12]

        listed = (await mcp_client_.get("/api/v1/ai/mcp-tokens", headers=auth_headers)).json()
        assert any(t["id"] == created["id"] and "token" not in t for t in listed["tokens"])

        h = {**MCP_HEADERS, "Authorization": f"Bearer {token}"}
        r = await mcp_client_.post("/api/mcp", headers=h, json=_rpc("tools/call", {"name": "get-accounts", "arguments": {}}))
        assert r.status_code == 200, r.text

        assert (await mcp_client_.delete(f"/api/v1/ai/mcp-tokens/{created['id']}", headers=auth_headers)).status_code == 204
        r = await mcp_client_.post("/api/mcp", headers=h, json=_rpc("tools/list"))
        assert r.status_code == 401


# ── Riepilogo: proventi nel P&L totale ────────────────────────────────────────

def test_summary_total_pnl_includes_income():
    snap = _snapshot()
    snap.income_eur = 21.66
    snap.net_contributed_eur = snap.total_invested_eur - snap.realized_pnl_eur
    out = ai.summary_section(snap, with_values=True)
    unreal = sum(h.unrealized_eur for h in snap.holdings)
    assert "Proventi incassati" in out and "21.66" in out
    assert f"{unreal + snap.realized_pnl_eur + 21.66:.2f}" in out
    assert "capitale netto versato" in out.lower()


def test_holdings_show_ticker_not_isin_as_symbol():
    snap = _snapshot()
    snap.holdings[0].asset.symbol = snap.holdings[0].asset.isin
    snap.holdings[0].asset.yahoo_ticker = "VWCE.DE"
    out = ai.holdings_table(snap, with_values=False)
    assert "| VWCE |" in out
    assert "Asset class" in out and "Obbligazioni" in out
