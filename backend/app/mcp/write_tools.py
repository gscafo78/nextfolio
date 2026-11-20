"""
Tool MCP di ricerca, scrittura e cancellazione.

Permessi (vedi ``server._Session``):
  - ``search-assets``, ``get-alerts``: lettura
  - creazione e modifica: ``can_write``
  - cancellazione: ``can_write`` + ``can_delete`` (destructiveHint=True, così i
    client chiedono conferma all'utente)

Regole comuni:
  - si riusano servizi ed endpoint esistenti (stesse validazioni della UI);
  - ``create-transactions`` è tutto-o-niente: se una riga non è valida non viene
    scritto nulla; le righe uguali a una transazione già presente sono saltate;
  - ogni scrittura va nel log di audit con ``via: mcp`` e l'id del token;
  - dopo ogni modifica alle transazioni la cache della performance è invalidata.
"""
from __future__ import annotations

import datetime
from typing import Annotated, Literal

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.mcp.server import _Session, mcp
from app.models.asset import Asset, AssetType, Exchange
from app.models.transaction import Transaction, TransactionType
from app.schemas.asset import AssetCreate, AssetUpdate
from app.schemas.transaction import TransactionCreate, TransactionUpdate
from app.services.account import get_account
from app.services.ai.context import table
from app.services.asset import get_asset_by_id, get_or_create_asset, search_assets, update_asset
from app.services.audit import log_action
from app.services.market_data.updater import invalidate_perf_cache
from app.services.portfolio.classification import build_asset_info, display_ticker
from app.services.transaction import BatchError, create_transactions_batch, get_transaction

MAX_BATCH = 100

_READ = dict(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
_WRITE = dict(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
_UPDATE = dict(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
_DELETE = dict(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)

# Azioni di audit
MCP_CREATE_ASSET = "MCP_CREATE_ASSET"
MCP_UPDATE_ASSET = "MCP_UPDATE_ASSET"
MCP_CREATE_TRANSACTIONS = "MCP_CREATE_TRANSACTIONS"
MCP_UPDATE_TRANSACTION = "MCP_UPDATE_TRANSACTION"
MCP_DELETE_TRANSACTION = "MCP_DELETE_TRANSACTION"
MCP_WATCHLIST = "MCP_WATCHLIST"
MCP_ALERT = "MCP_ALERT"
MCP_ACCOUNT_BALANCE = "MCP_ACCOUNT_BALANCE"


async def _audit(s: _Session, action: str, entity_type: str, entity_id: int | None, detail: dict) -> None:
    await log_action(
        s.db, user_id=s.user.id, action=action, entity_type=entity_type, entity_id=entity_id,
        detail={**detail, "via": "mcp", "token_id": s.access.get("token_id")},
    )
    await s.db.commit()


def _enum(v) -> str:
    return v.value if hasattr(v, "value") else str(v)


async def _asset_or_error(s: _Session, asset_id: int) -> Asset:
    asset = await get_asset_by_id(s.db, asset_id)
    if not asset:
        raise ToolError(f"Asset {asset_id} non trovato: usa search-assets o create-asset.")
    return asset


# ── Ricerca (lettura) ─────────────────────────────────────────────────────────


@mcp.tool(
    name="search-assets",
    title="Search assets",
    annotations=ToolAnnotations(title="Search assets", **_READ),
    structured_output=False,
    description=(
        "Cerca strumenti finanziari nell'anagrafica di Nextfolio per nome, ticker o ISIN e restituisce l'ID asset "
        "da usare con create-transactions, add-to-watchlist, create-alert e update-asset. Se lo strumento non "
        "c'è, crealo con create-asset."
    ),
)
async def search_assets_tool(
    ctx: Context,
    query: Annotated[str, Field(min_length=2, max_length=100, description="Nome, ticker o ISIN, es. MSCI World, SWDA, IE00B4L5Y983")],
) -> str:
    async with _Session(ctx) as s:
        assets = await search_assets(s.db, query.strip(), limit=20)
        rows = [[a.id, a.name, display_ticker(build_asset_info(a)) or "—", a.isin, _enum(a.type),
                 _enum(a.exchange), a.currency] for a in assets]
        return table(["ID asset", "Nome", "Ticker", "ISIN", "Tipo", "Borsa", "Valuta"], rows)


@mcp.tool(
    name="get-alerts",
    title="Get alerts",
    annotations=ToolAnnotations(title="Get alerts", **_READ),
    structured_output=False,
    description="Alert di prezzo dell'utente: ID, asset, tipo (PRICE_ABOVE, PRICE_BELOW, CHANGE_PCT_UP, CHANGE_PCT_DOWN), soglia, stato.",
)
async def get_alerts(ctx: Context) -> str:
    from app.api.v1.endpoints.alerts import list_alerts

    async with _Session(ctx) as s:
        alerts = await list_alerts(db=s.db, current_user=s.user)
        rows = [[a.id, a.asset_id, a.asset_name, a.alert_type, a.threshold, "attivo" if a.is_active else "disattivo",
                 a.last_triggered_at.date().isoformat() if a.last_triggered_at else "—"] for a in alerts]
        return table(["ID alert", "ID asset", "Asset", "Tipo", "Soglia", "Stato", "Ultimo scatto"], rows)


# ── Asset ─────────────────────────────────────────────────────────────────────


@mcp.tool(
    name="create-asset",
    title="Create asset",
    annotations=ToolAnnotations(title="Create asset", **_UPDATE),
    structured_output=False,
    description=(
        "Crea uno strumento nell'anagrafica (richiede il permesso di scrittura). Se esiste già un asset con lo "
        "stesso ISIN restituisce quello. Usalo solo dopo che search-assets non l'ha trovato."
    ),
)
async def create_asset_tool(
    ctx: Context,
    name: Annotated[str, Field(min_length=1, max_length=200, description="Nome completo dello strumento")],
    symbol: Annotated[str, Field(min_length=1, max_length=50, description="Ticker, es. SWDA; se non noto usa l'ISIN")],
    type: Annotated[Literal["STOCK", "ETF", "BOND", "CRYPTO", "COMMODITY", "REIT", "OTHER"], Field(description="Tipo di strumento")],
    currency: Annotated[str, Field(min_length=3, max_length=3, description="Valuta di quotazione ISO 4217, es. EUR")] = "EUR",
    isin: Annotated[str | None, Field(description="ISIN (12 caratteri), consigliato")] = None,
    exchange: Annotated[
        Literal["MIL", "EuroTLX", "MOT", "XETRA", "NYSE", "NASDAQ", "CRYPTO", "OTHER"], Field(description="Borsa")
    ] = "OTHER",
) -> str:
    async with _Session(ctx, require="write") as s:
        data = AssetCreate(isin=isin, symbol=symbol.strip().upper(), name=name.strip(), type=AssetType(type),
                           exchange=Exchange(exchange), currency=currency.upper())
        existing = data.isin and (await s.db.execute(select(Asset).where(Asset.isin == data.isin))).scalar_one_or_none()
        asset = await get_or_create_asset(s.db, data)
        if not existing:
            await _audit(s, MCP_CREATE_ASSET, "asset", asset.id, {"isin": asset.isin, "name": asset.name})
        state = "già presente" if existing else "creato"
        return f"Asset {state}: ID {asset.id} — {asset.name} ({asset.isin or asset.symbol})."


@mcp.tool(
    name="update-asset",
    title="Update asset classification",
    annotations=ToolAnnotations(title="Update asset classification", **_UPDATE),
    structured_output=False,
    description=(
        "Modifica la classificazione di uno strumento (richiede il permesso di scrittura): asset class del "
        "sottostante, trattamento fiscale da titolo di Stato (solo BOND), quota in titoli di Stato white list "
        "(solo ETF), look-through per settori e paesi. Attenzione: l'anagrafica asset è condivisa da tutti gli "
        "utenti dell'istanza. 'AUTO' ripristina il riconoscimento automatico."
    ),
)
async def update_asset_tool(
    ctx: Context,
    asset_id: Annotated[int, Field(description="ID asset (vedi search-assets)")],
    asset_class: Annotated[
        Literal["EQUITY", "BOND", "MONEY_MARKET", "CRYPTO", "OTHER", "AUTO"] | None,
        Field(description="Asset class del sottostante; AUTO = automatica"),
    ] = None,
    government_bond: Annotated[
        Literal["YES", "NO", "AUTO"] | None,
        Field(description="Solo BOND: YES = titolo di Stato o equiparato (12,5%), NO = 26%, AUTO = dal nome"),
    ] = None,
    govt_bond_share_pct: Annotated[
        float | None, Field(ge=-1, le=100, description="Solo ETF: % in titoli di Stato white list (0-100); -1 per cancellare"),
    ] = None,
    sectors: Annotated[
        list[dict] | None,
        Field(description='Look-through settori, es. [{"name": "Technology", "weight": 0.3}]; lista vuota per cancellare'),
    ] = None,
    countries: Annotated[
        list[dict] | None,
        Field(description='Look-through paesi, es. [{"code": "US", "name": "United States", "weight": 0.7}]; lista vuota per cancellare'),
    ] = None,
) -> str:
    async with _Session(ctx, require="write") as s:
        asset = await _asset_or_error(s, asset_id)
        changes: dict = {}
        if asset_class is not None:
            changes["asset_class_override"] = None if asset_class == "AUTO" else asset_class
        if government_bond is not None:
            if _enum(asset.type) != "BOND":
                raise ToolError("government_bond si applica solo agli asset di tipo BOND.")
            changes["govt_bond_override"] = {"YES": True, "NO": False, "AUTO": None}[government_bond]
        if govt_bond_share_pct is not None:
            if _enum(asset.type) != "ETF":
                raise ToolError("govt_bond_share_pct si applica solo agli ETF.")
            changes["govt_bond_share"] = None if govt_bond_share_pct < 0 else govt_bond_share_pct / 100
        for key, value in (("sectors_override", sectors), ("countries_override", countries)):
            if value is not None:
                for item in value:
                    w = item.get("weight")
                    if not isinstance(w, (int, float)) or not 0 <= w <= 1:
                        raise ToolError(f"{key}: ogni voce deve avere 'weight' tra 0 e 1.")
                changes[key] = value or None
        if not changes:
            raise ToolError("Nessuna modifica indicata.")
        await update_asset(s.db, asset, AssetUpdate(**changes))
        await _audit(s, MCP_UPDATE_ASSET, "asset", asset.id, {"changes": changes})
        return f"Asset {asset.id} ({asset.name}) aggiornato: " + ", ".join(f"{k}={v}" for k, v in changes.items())


# ── Saldo di cassa ────────────────────────────────────────────────────────────


@mcp.tool(
    name="update-account-balance",
    title="Update account balance",
    annotations=ToolAnnotations(title="Update account balance", **_UPDATE),
    structured_output=False,
    description=(
        "Imposta il saldo di cassa (liquidità) di un conto a una data, nella valuta del conto (richiede il "
        "permesso di scrittura). Un saldo già presente alla stessa data viene sostituito; il saldo con la data più "
        "recente è quello corrente. La liquidità entra nel patrimonio totale, nell'allocazione e nella regola "
        "X-Ray sulla riserva di liquidità. Date future rifiutate."
    ),
)
async def update_account_balance(
    ctx: Context,
    account_id: Annotated[int, Field(description="ID conto (vedi get-accounts)")],
    balance: Annotated[float, Field(description="Saldo di cassa nella valuta del conto")],
    date: Annotated[datetime.date | None, Field(description="Data del saldo, ISO 8601 (default: oggi)")] = None,
) -> str:
    from app.services.cash import set_balance

    async with _Session(ctx, require="write") as s:
        account = await get_account(s.db, account_id, s.user.id)
        if not account:
            raise ToolError(f"Conto {account_id} non trovato: usa get-accounts per l'identificativo.")
        d = date or datetime.date.today()
        row = await set_balance(s.db, account, d, balance)
        await _audit(s, MCP_ACCOUNT_BALANCE, "account", account.id, {"date": d.isoformat(), "balance": balance})
        return f"Saldo di cassa del conto {account.name} al {row.date}: {row.balance:.2f} {account.currency}."


# ── Transazioni ───────────────────────────────────────────────────────────────


class TransactionInput(BaseModel):
    account_id: int = Field(description="ID conto (vedi get-accounts)")
    asset_id: int = Field(description="ID asset (vedi search-assets / create-asset)")
    type: Literal["BUY", "SELL", "DIVIDEND", "COUPON", "FEE", "INTEREST"]
    date: datetime.date = Field(description="Data ISO 8601, es. 2026-03-15")
    quantity: float = Field(gt=0, description="Quantità; per dividendi/cedole/interessi di solito 1")
    price: float = Field(ge=0, description="Prezzo unitario nella valuta price_currency; per proventi l'importo")
    price_currency: str = Field("EUR", min_length=3, max_length=3)
    exchange_rate: float = Field(1.0, gt=0, description="EUR per 1 unità di price_currency (1 se EUR)")
    fee: float = Field(0.0, ge=0, description="Commissioni in EUR")
    notes: str | None = Field(None, max_length=500)


@mcp.tool(
    name="create-transactions",
    title="Create transactions",
    annotations=ToolAnnotations(title="Create transactions", **_WRITE),
    structured_output=False,
    description=(
        f"Registra fino a {MAX_BATCH} transazioni (richiede il permesso di scrittura). Tutto o niente: se una "
        "riga non è valida non viene scritto nulla e l'errore indica la riga. Una riga uguale a una transazione "
        "già presente (stesso conto, asset, tipo, data, quantità, prezzo e commissione) viene saltata, quindi "
        "la chiamata si può ripetere senza creare doppioni. Restituisce gli ID creati."
    ),
)
async def create_transactions(
    ctx: Context,
    transactions: Annotated[list[TransactionInput], Field(min_length=1, max_length=MAX_BATCH)],
) -> str:
    async with _Session(ctx, require="write") as s:
        errors: list[str] = []
        validated: list[TransactionCreate] = []
        for i, row in enumerate(transactions, 1):
            try:
                validated.append(TransactionCreate(**{**row.model_dump(), "type": TransactionType(row.type)}))
            except ValidationError as e:
                errors.append(f"riga {i}: {e.errors()[0]['msg']}")
        if errors:
            raise ToolError("Nessuna transazione registrata. " + "; ".join(errors))
        try:
            created, skipped = await create_transactions_batch(s.db, s.user.id, validated)
        except BatchError as e:
            raise ToolError("Nessuna transazione registrata. " + "; ".join(e.errors)) from e
        names = {a.id: a.name for a in (await s.db.execute(
            select(Asset).where(Asset.id.in_({t.asset_id for t in created}))
        )).scalars()}
        await _audit(s, MCP_CREATE_TRANSACTIONS, "transaction", None,
                     {"created": [t.id for t in created], "skipped_rows": skipped})
        await invalidate_perf_cache(s.user.id)

        rows = [[t.id, t.date.isoformat(), _enum(t.type), names.get(t.asset_id, t.asset_id), t.quantity, t.price,
                 t.price_currency, t.fee] for t in created]
        out = f"Transazioni registrate: {len(created)}; saltate perché già presenti: {len(skipped)}"
        out += f" (righe {', '.join(map(str, skipped))})." if skipped else "."
        if rows:
            out += "\n\n" + table(["ID", "Data", "Tipo", "Asset", "Quantità", "Prezzo", "Valuta", "Commissioni"], rows)
        return out


@mcp.tool(
    name="update-transaction",
    title="Update transaction",
    annotations=ToolAnnotations(title="Update transaction", **_UPDATE),
    structured_output=False,
    description=(
        "Modifica una transazione esistente (richiede il permesso di scrittura). Indica solo i campi da "
        "cambiare; l'ID è in get-transactions."
    ),
)
async def update_transaction_tool(
    ctx: Context,
    transaction_id: Annotated[int, Field(description="ID transazione (vedi get-transactions)")],
    account_id: int | None = None,
    type: Literal["BUY", "SELL", "DIVIDEND", "COUPON", "FEE", "INTEREST"] | None = None,
    date: datetime.date | None = None,
    quantity: Annotated[float | None, Field(gt=0)] = None,
    price: Annotated[float | None, Field(ge=0)] = None,
    price_currency: Annotated[str | None, Field(min_length=3, max_length=3)] = None,
    exchange_rate: Annotated[float | None, Field(gt=0)] = None,
    fee: Annotated[float | None, Field(ge=0)] = None,
    notes: Annotated[str | None, Field(max_length=500)] = None,
) -> str:
    async with _Session(ctx, require="write") as s:
        tx = await get_transaction(s.db, transaction_id, s.user.id)
        if not tx:
            raise ToolError(f"Transazione {transaction_id} non trovata.")
        if account_id is not None and not await get_account(s.db, account_id, s.user.id):
            raise ToolError(f"Conto {account_id} non trovato.")
        if date is not None and date > datetime.date.today():
            raise ToolError("La data non può essere futura.")
        changes = {k: v for k, v in dict(
            account_id=account_id, type=TransactionType(type) if type else None, date=date, quantity=quantity,
            price=price, price_currency=price_currency.upper() if price_currency else None,
            exchange_rate=exchange_rate, fee=fee, notes=notes,
        ).items() if v is not None}
        if not changes:
            raise ToolError("Nessuna modifica indicata.")
        before = {k: (_enum(getattr(tx, k)) if k == "type" else getattr(tx, k)) for k in changes}
        for k, v in changes.items():
            setattr(tx, k, v)
        await s.db.flush()
        await _audit(s, MCP_UPDATE_TRANSACTION, "transaction", tx.id, {
            "before": {k: str(v) for k, v in before.items()},
            "after": {k: str(_enum(v)) for k, v in changes.items()},
        })
        await invalidate_perf_cache(s.user.id)
        return f"Transazione {tx.id} aggiornata: " + ", ".join(f"{k} {before[k]} → {_enum(v)}" for k, v in changes.items())


@mcp.tool(
    name="delete-transaction",
    title="Delete transaction",
    annotations=ToolAnnotations(title="Delete transaction", **_DELETE),
    structured_output=False,
    description=(
        "Cancella definitivamente una transazione (richiede i permessi di scrittura e cancellazione). "
        "Chiedi sempre conferma all'utente prima di usarlo."
    ),
)
async def delete_transaction_tool(
    ctx: Context,
    transaction_id: Annotated[int, Field(description="ID transazione (vedi get-transactions)")],
) -> str:
    async with _Session(ctx, require="delete") as s:
        result = await s.db.execute(
            select(Transaction).where(Transaction.id == transaction_id)
            .join(Transaction.account).where(Transaction.account.has(user_id=s.user.id))
            .options(selectinload(Transaction.asset))
        )
        tx = result.scalar_one_or_none()
        if not tx:
            raise ToolError(f"Transazione {transaction_id} non trovata.")
        detail = {"asset": tx.asset.name, "type": _enum(tx.type), "date": tx.date.isoformat(),
                  "quantity": tx.quantity, "price": tx.price, "account_id": tx.account_id}
        await s.db.delete(tx)
        await s.db.flush()
        await _audit(s, MCP_DELETE_TRANSACTION, "transaction", transaction_id, detail)
        await invalidate_perf_cache(s.user.id)
        return (f"Transazione {transaction_id} cancellata: {detail['type']} {detail['quantity']} × {detail['asset']} "
                f"del {detail['date']}.")


# ── Watchlist ─────────────────────────────────────────────────────────────────


@mcp.tool(
    name="add-to-watchlist",
    title="Add to watchlist",
    annotations=ToolAnnotations(title="Add to watchlist", **_WRITE),
    structured_output=False,
    description="Aggiunge uno strumento alla watchlist con nota e prezzo obiettivo opzionali (richiede il permesso di scrittura).",
)
async def add_to_watchlist_tool(
    ctx: Context,
    asset_id: Annotated[int, Field(description="ID asset (vedi search-assets)")],
    note: Annotated[str | None, Field(max_length=500)] = None,
    target_price: Annotated[float | None, Field(gt=0, description="Prezzo obiettivo nella valuta dell'asset")] = None,
) -> str:
    from app.api.v1.endpoints.watchlist import WatchlistCreate, add_to_watchlist

    async with _Session(ctx, require="write") as s:
        item = await add_to_watchlist(body=WatchlistCreate(asset_id=asset_id, note=note, target_price=target_price),
                                      db=s.db, current_user=s.user)
        await _audit(s, MCP_WATCHLIST, "watchlist", item.id, {"op": "add", "asset_id": asset_id})
        return f"Aggiunto alla watchlist: voce {item.id} — {item.name}."


@mcp.tool(
    name="update-watchlist-item",
    title="Update watchlist item",
    annotations=ToolAnnotations(title="Update watchlist item", **_UPDATE),
    structured_output=False,
    description="Modifica nota e prezzo obiettivo di una voce della watchlist (richiede il permesso di scrittura). L'ID voce è in get-watchlist.",
)
async def update_watchlist_item_tool(
    ctx: Context,
    item_id: Annotated[int, Field(description="ID voce (vedi get-watchlist)")],
    note: Annotated[str | None, Field(max_length=500)] = None,
    target_price: Annotated[float | None, Field(ge=0, description="Nuovo prezzo obiettivo; 0 per rimuoverlo")] = None,
) -> str:
    from app.api.v1.endpoints.watchlist import WatchlistUpdate, update_watchlist_item

    async with _Session(ctx, require="write") as s:
        fields: dict = {}
        if note is not None:
            fields["note"] = note
        if target_price is not None:
            fields["target_price"] = None if target_price == 0 else target_price
        if not fields:
            raise ToolError("Nessuna modifica indicata.")
        item = await update_watchlist_item(item_id=item_id, body=WatchlistUpdate(**fields), db=s.db, current_user=s.user)
        await _audit(s, MCP_WATCHLIST, "watchlist", item_id, {"op": "update", **{k: str(v) for k, v in fields.items()}})
        return f"Voce {item_id} della watchlist aggiornata ({item.name})."


@mcp.tool(
    name="remove-from-watchlist",
    title="Remove from watchlist",
    annotations=ToolAnnotations(title="Remove from watchlist", **_DELETE),
    structured_output=False,
    description="Rimuove una voce dalla watchlist (richiede i permessi di scrittura e cancellazione).",
)
async def remove_from_watchlist_tool(
    ctx: Context,
    item_id: Annotated[int, Field(description="ID voce (vedi get-watchlist)")],
) -> str:
    from app.api.v1.endpoints.watchlist import remove_from_watchlist

    async with _Session(ctx, require="delete") as s:
        await remove_from_watchlist(item_id=item_id, db=s.db, current_user=s.user)
        await _audit(s, MCP_WATCHLIST, "watchlist", item_id, {"op": "remove"})
        return f"Voce {item_id} rimossa dalla watchlist."


# ── Alert ─────────────────────────────────────────────────────────────────────

AlertTypeParam = Annotated[
    Literal["PRICE_ABOVE", "PRICE_BELOW", "CHANGE_PCT_UP", "CHANGE_PCT_DOWN"],
    Field(description="PRICE_ABOVE/BELOW: soglia di prezzo; CHANGE_PCT_UP/DOWN: variazione giornaliera % oltre la soglia"),
]


@mcp.tool(
    name="create-alert",
    title="Create alert",
    annotations=ToolAnnotations(title="Create alert", **_WRITE),
    structured_output=False,
    description="Crea un alert di prezzo su uno strumento (richiede il permesso di scrittura).",
)
async def create_alert_tool(
    ctx: Context,
    asset_id: Annotated[int, Field(description="ID asset (vedi search-assets)")],
    alert_type: AlertTypeParam,
    threshold: Annotated[float, Field(gt=0, description="Prezzo o percentuale")],
) -> str:
    from app.api.v1.endpoints.alerts import create_alert
    from app.models.alert import AlertType
    from app.schemas.alert import AlertCreate

    async with _Session(ctx, require="write") as s:
        await _asset_or_error(s, asset_id)
        alert = await create_alert(body=AlertCreate(asset_id=asset_id, alert_type=AlertType(alert_type), threshold=threshold),
                                   db=s.db, current_user=s.user)
        await _audit(s, MCP_ALERT, "alert", alert.id, {"op": "create", "type": alert_type, "threshold": threshold})
        return f"Alert {alert.id} creato: {alert.asset_name} {alert_type} {threshold}."


@mcp.tool(
    name="update-alert",
    title="Update alert",
    annotations=ToolAnnotations(title="Update alert", **_UPDATE),
    structured_output=False,
    description="Modifica soglia o stato (attivo/disattivo) di un alert (richiede il permesso di scrittura). L'ID è in get-alerts.",
)
async def update_alert_tool(
    ctx: Context,
    alert_id: Annotated[int, Field(description="ID alert (vedi get-alerts)")],
    threshold: Annotated[float | None, Field(gt=0)] = None,
    is_active: bool | None = None,
) -> str:
    from app.api.v1.endpoints.alerts import update_alert
    from app.schemas.alert import AlertUpdate

    async with _Session(ctx, require="write") as s:
        if threshold is None and is_active is None:
            raise ToolError("Nessuna modifica indicata.")
        alert = await update_alert(alert_id=alert_id, body=AlertUpdate(threshold=threshold, is_active=is_active),
                                   db=s.db, current_user=s.user)
        await _audit(s, MCP_ALERT, "alert", alert_id, {"op": "update", "threshold": threshold, "is_active": is_active})
        return f"Alert {alert_id} aggiornato: soglia {alert.threshold}, {'attivo' if alert.is_active else 'disattivo'}."


@mcp.tool(
    name="delete-alert",
    title="Delete alert",
    annotations=ToolAnnotations(title="Delete alert", **_DELETE),
    structured_output=False,
    description="Cancella un alert di prezzo (richiede i permessi di scrittura e cancellazione).",
)
async def delete_alert_tool(
    ctx: Context,
    alert_id: Annotated[int, Field(description="ID alert (vedi get-alerts)")],
) -> str:
    from app.api.v1.endpoints.alerts import delete_alert

    async with _Session(ctx, require="delete") as s:
        await delete_alert(alert_id=alert_id, db=s.db, current_user=s.user)
        await _audit(s, MCP_ALERT, "alert", alert_id, {"op": "delete"})
        return f"Alert {alert_id} cancellato."
