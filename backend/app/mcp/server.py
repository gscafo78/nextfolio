"""
Server MCP (Model Context Protocol) di Nextfolio — sola lettura.

Ispirato a Ghostfolio (apps/api/src/app/endpoints/mcp): ogni tool restituisce
testo (tabelle Markdown) e omette gli importi in EUR se il token non ha il
permesso ``can_read_values``.

Trasporto: Streamable HTTP, stateless, risposte JSON, esposto su ``/api/mcp``.
Autenticazione: ``Authorization: Bearer nfmcp_…`` (token creati dalla pagina AI).

Esempio (Claude Code):
    claude mcp add --transport http nextfolio https://<host>/api/mcp \
        --header "Authorization: Bearer nfmcp_..."
"""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated, Literal

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp_types import ToolAnnotations
from pydantic import Field

from app.core.config import APP_VERSION, settings
from app.core.database import AsyncSessionLocal
from app.mcp.tokens import resolve_token
from app.models.transaction import TransactionType
from app.services.ai import context as ai
from app.services.user import get_user_by_id

logger = logging.getLogger(__name__)

MCP_PATH = "/api/mcp"
MCP_REALM = "nextfolio-mcp"
MAX_TRANSACTIONS = 100
_STATE_KEY = "nextfolio_mcp"
_INNER_PATH = "/mcp"

mcp = MCPServer(
    name="nextfolio",
    title="Nextfolio",
    version=APP_VERSION,
    instructions=(
        "Server in sola lettura del portafoglio Nextfolio di un investitore italiano. "
        "Tutti gli importi sono in EUR. Usa get-portfolio per una panoramica, poi gli altri "
        "tool per approfondire. Se il token non può leggere gli importi, i tool restituiscono "
        "solo pesi e percentuali."
    ),
)

_READ_ONLY = dict(readOnlyHint=True, openWorldHint=False, destructiveHint=False, idempotentHint=True)

AssetTypeParam = Annotated[
    Literal["STOCK", "ETF", "BOND", "CRYPTO", "COMMODITY", "REIT", "OTHER"] | None,
    Field(description="Limita ai soli asset di questo tipo"),
]
AccountIdParam = Annotated[
    int | None, Field(description="Identificativo del conto (vedi get-accounts) a cui limitare il risultato"),
]
PeriodParam = Literal["ytd", "mtd", "1m", "3m", "6m", "1y", "3y", "max"]


# ── Accesso ──────────────────────────────────────────────────────────────────


def _access(ctx: Context) -> dict:
    request = ctx.request_context.request
    state = request.scope.get("state", {}) if request is not None else {}
    access = state.get(_STATE_KEY)
    if not access:  # il middleware garantisce l'autenticazione: qui non dovrebbe mai mancare
        raise PermissionError("Accesso MCP non autenticato")
    return access


class _Session:
    """Sessione DB + utente dell'accesso corrente."""

    def __init__(self, ctx: Context):
        self.access = _access(ctx)
        self.with_values: bool = self.access["can_read_values"]

    async def __aenter__(self):
        self.db = AsyncSessionLocal()
        self.user = await get_user_by_id(self.db, self.access["user_id"])
        if not self.user or not self.user.is_active:
            await self.db.close()
            raise PermissionError("Utente non trovato o disabilitato")
        return self

    async def __aexit__(self, *exc):
        await self.db.close()


# ── Tool ─────────────────────────────────────────────────────────────────────


@mcp.tool(
    name="get-portfolio",
    title="Get portfolio",
    annotations=ToolAnnotations(title="Get portfolio", **_READ_ONLY),
    structured_output=False,
    description=(
        "Riepilogo del portafoglio e posizioni aperte, ordinate per valore. Colonne: nome, simbolo, ISIN, tipo, "
        "valuta, peso %, P&L non realizzato %, variazione giornaliera %. Se l'accesso legge gli importi anche: "
        "quantità, PMC (prezzo medio di carico in EUR), prezzo corrente nella valuta dell'asset, valore, investito "
        "e P&L in EUR. Il peso è relativo alle posizioni del risultato, quindi i filtri lo cambiano."
    ),
)
async def get_portfolio(ctx: Context, account_id: AccountIdParam = None, asset_type: AssetTypeParam = None) -> str:
    async with _Session(ctx) as s:
        snap = await ai.load_snapshot(s.db, s.user, account_id=account_id, asset_type=asset_type)
        return (
            f"## Riepilogo al {date.today().isoformat()}\n{ai.summary_section(snap, s.with_values)}\n\n"
            f"## Posizioni aperte\n{ai.holdings_table(snap, s.with_values)}"
        )


@mcp.tool(
    name="get-allocation",
    title="Get allocation",
    annotations=ToolAnnotations(title="Get allocation", **_READ_ONLY),
    structured_output=False,
    description=(
        "Allocazione delle posizioni aperte per tipo di asset, valuta, conto, settore e area geografica "
        "(settori e aree con look-through degli ETF). Se l'accesso legge gli importi anche il valore in EUR."
    ),
)
async def get_allocation(ctx: Context, account_id: AccountIdParam = None, asset_type: AssetTypeParam = None) -> str:
    async with _Session(ctx) as s:
        snap = await ai.load_snapshot(s.db, s.user, account_id=account_id, asset_type=asset_type)
        return ai.allocation_section(snap, s.with_values)


@mcp.tool(
    name="get-accounts",
    title="Get accounts",
    annotations=ToolAnnotations(title="Get accounts", **_READ_ONLY),
    structured_output=False,
    description=(
        "Conti dell'utente: ID, nome, tipo, broker, valuta, regime amministrato (il broker fa da sostituto "
        "d'imposta) o dichiarativo, conto estero soggetto a IVAFE, peso % sul valore delle posizioni. "
        "Se l'accesso legge gli importi anche il valore delle posizioni in EUR."
    ),
)
async def get_accounts(ctx: Context) -> str:
    async with _Session(ctx) as s:
        snap = await ai.load_snapshot(s.db, s.user)
        return ai.accounts_table(snap, s.with_values)


@mcp.tool(
    name="get-transactions",
    title="Get transactions",
    annotations=ToolAnnotations(title="Get transactions", **_READ_ONLY),
    structured_output=False,
    description=(
        "Transazioni (acquisti, vendite, dividendi, cedole, commissioni, interessi), le più recenti prima. "
        "Colonne: data, tipo, conto, asset, simbolo, ISIN. Se l'accesso legge gli importi anche: quantità, prezzo, "
        "valuta del prezzo, cambio verso EUR, commissioni e controvalore in EUR. "
        f"Al massimo {MAX_TRANSACTIONS} righe per chiamata: usa i filtri o il parametro skip per le successive."
    ),
)
async def get_transactions(
    ctx: Context,
    account_id: AccountIdParam = None,
    asset: Annotated[str | None, Field(description="Simbolo o ISIN dell'asset")] = None,
    type: Annotated[
        Literal["BUY", "SELL", "DIVIDEND", "COUPON", "FEE", "INTEREST"] | None,
        Field(description="Tipo di transazione"),
    ] = None,
    year: Annotated[int | None, Field(ge=1970, le=2100, description="Anno solare, es. 2024")] = None,
    skip: Annotated[int, Field(ge=0, description="Numero di transazioni da saltare")] = 0,
    take: Annotated[int, Field(ge=1, le=MAX_TRANSACTIONS, description="Numero di transazioni")] = MAX_TRANSACTIONS,
) -> str:
    from app.services.transaction import get_transactions as _get

    async with _Session(ctx) as s:
        txs = await _get(
            s.db, s.user.id,
            account_id=account_id,
            type=TransactionType(type) if type else None,
            date_from=date(year, 1, 1) if year else None,
            date_to=date(year, 12, 31) if year else None,
            limit=10_000,
        )
        if asset:
            q = asset.strip().upper()
            txs = [t for t in txs if t.asset.symbol.upper() == q or (t.asset.isin or "").upper() == q]
        page = txs[skip: skip + take]
        more = len(txs) - skip - len(page)
        footer = f"\n\nMostrate {len(page)} di {len(txs)} transazioni" + (
            f" (altre {more}: usa skip={skip + len(page)})." if more > 0 else "."
        )
        return ai.transactions_table(page, s.with_values) + footer


@mcp.tool(
    name="get-performance",
    title="Get performance",
    annotations=ToolAnnotations(title="Get performance", **_READ_ONLY),
    structured_output=False,
    description=(
        "Rendimento time-weighted (TWRR, dividendi inclusi) del portafoglio nel periodo. Senza filtro per conto "
        "include anche lo XIRR (money-weighted) dall'inizio. Se l'accesso legge gli importi anche valore finale, "
        "capitale investito e P&L in EUR alla fine del periodo."
    ),
)
async def get_performance(ctx: Context, period: PeriodParam = "1y", account_id: AccountIdParam = None) -> str:
    async with _Session(ctx) as s:
        out = await ai.performance_section(s.db, s.user, s.with_values, account_id=account_id, periods=(period,))
        if account_id is None:
            out += "\n\n" + await ai.xirr_section(s.db, s.user)
        return out


@mcp.tool(
    name="get-risk-metrics",
    title="Get risk metrics",
    annotations=ToolAnnotations(title="Get risk metrics", **_READ_ONLY),
    structured_output=False,
    description="Metriche di rischio dalla serie storica: volatilità annualizzata, max drawdown, Sharpe, Sortino, Calmar, giorni migliori/peggiori.",
)
async def get_risk_metrics(
    ctx: Context,
    period: Literal["1m", "3m", "6m", "1y", "3y", "max"] = "3y",
    account_id: AccountIdParam = None,
) -> str:
    async with _Session(ctx) as s:
        return await ai.risk_section(s.db, s.user, account_id=account_id, period=period)


@mcp.tool(
    name="get-xray",
    title="Get X-Ray",
    annotations=ToolAnnotations(title="Get X-Ray", **_READ_ONLY),
    structured_output=False,
    description=(
        "Diagnostica X-Ray del portafoglio: regole su concentrazione, classi di asset, area geografica, costi e "
        "liquidità, con esito (OK/WARN/ERROR/INFO), valore attuale e soglie, più un punteggio 0-100."
    ),
)
async def get_xray(ctx: Context) -> str:
    async with _Session(ctx) as s:
        return await ai.xray_section(s.db, s.user, s.with_values)


@mcp.tool(
    name="get-dividends",
    title="Get dividends",
    annotations=ToolAnnotations(title="Get dividends", **_READ_ONLY),
    structured_output=False,
    description="Dividendi, cedole e interessi raggruppati per anno e tipo: numero di incassi e, se l'accesso legge gli importi, totale netto in EUR.",
)
async def get_dividends(ctx: Context) -> str:
    async with _Session(ctx) as s:
        return await ai.dividends_section(s.db, s.user, s.with_values)


@mcp.tool(
    name="get-watchlist",
    title="Get watchlist",
    annotations=ToolAnnotations(title="Get watchlist", **_READ_ONLY),
    structured_output=False,
    description="Watchlist dell'utente ordinata per nome: asset osservati ma non necessariamente posseduti, con prezzo corrente, variazione giornaliera, prezzo obiettivo e nota.",
)
async def get_watchlist(ctx: Context) -> str:
    async with _Session(ctx) as s:
        return await ai.watchlist_table(s.db, s.user)


@mcp.tool(
    name="get-tax-report",
    title="Get tax report",
    annotations=ToolAnnotations(title="Get tax report", **_READ_ONLY),
    structured_output=False,
    description=(
        "Riepilogo fiscale italiano dell'anno: plusvalenze/minusvalenze al 26% (titoli di Stato ponderati al 48,08%), "
        "ETF/fondi (plusvalenze come redditi di capitale), cripto-attività, zainetto applicato e generato, imposte, "
        "dividendi, cedole, interessi e IVAFE. "
        "Richiede un accesso che legge gli importi."
    ),
)
async def get_tax_report(
    ctx: Context,
    year: Annotated[int | None, Field(ge=2000, le=2100, description="Anno fiscale (default: anno corrente)")] = None,
) -> str:
    async with _Session(ctx) as s:
        return await ai.tax_section(s.db, s.user, year or date.today().year, s.with_values)


# ── ASGI ─────────────────────────────────────────────────────────────────────

_mcp_app = None


@asynccontextmanager
async def mcp_lifespan():
    """Avvia il trasporto MCP; da usare nel lifespan di FastAPI.

    Il session manager si può avviare una sola volta per istanza, quindi l'app
    ASGI viene ricreata a ogni avvio (utile anche nei test).
    """
    global _mcp_app
    # Protezione DNS-rebinding disattivata: l'accesso richiede un bearer token
    # (nessun cookie), e TrustedHostMiddleware di FastAPI filtra già l'header Host.
    asgi_app = mcp.streamable_http_app(
        streamable_http_path=_INNER_PATH,
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    async with mcp.session_manager.run():
        _mcp_app = asgi_app
        try:
            yield
        finally:
            _mcp_app = None


async def _send_json(send, status: int, body: dict, headers: list[tuple[bytes, bytes]] | None = None) -> None:
    payload = json.dumps(body).encode()
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode())]
        + (headers or []),
    })
    await send({"type": "http.response.body", "body": payload})


class McpMiddleware:
    """Instrada ``/api/mcp`` al server MCP dopo aver verificato il bearer token.

    Come in Ghostfolio, la risposta 401 con ``WWW-Authenticate`` deve arrivare
    prima che il trasporto legga il messaggio, quindi l'autenticazione sta qui
    e non dentro i tool.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"].rstrip("/") != MCP_PATH:
            return await self.app(scope, receive, send)

        if not settings.ENABLE_MCP:
            return await _send_json(send, 404, {"detail": "Server MCP disabilitato"})
        if _mcp_app is None:
            return await _send_json(send, 503, {"detail": "Server MCP non avviato"})

        if scope["method"] == "OPTIONS":  # preflight CORS gestito dal middleware CORS esterno
            return await self.app(scope, receive, send)

        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        auth = headers.get("authorization", "")
        token = auth[7:].strip() if auth.lower().startswith("bearer ") else None

        async with AsyncSessionLocal() as db:
            resolved = await resolve_token(db, token)

        if not resolved:
            challenge = f'Bearer realm="{MCP_REALM}"'
            if token:
                challenge += ', error="invalid_token", error_description="Il token non è valido o è stato revocato"'
            return await _send_json(
                send, 401,
                {"error": "Unauthorized", "message": "È richiesto un token MCP valido come bearer token"},
                [(b"www-authenticate", challenge.encode())],
            )

        user, access = resolved
        scope = dict(scope)
        scope["state"] = {**scope.get("state", {}), _STATE_KEY: {
            "user_id": user.id,
            "token_id": access.id,
            "can_read_values": access.can_read_values,
        }}
        scope["path"] = _INNER_PATH
        scope["raw_path"] = _INNER_PATH.encode()
        await _mcp_app(scope, receive, send)
