"""
Pagina Pianifica — ricerca titoli, scheda titolo, simulazione d'acquisto, scenari.

  GET    /planning/search?q=&type=           ricerca unificata (Nextfolio + Yahoo), min 3 caratteri
  GET    /planning/security?asset_id=|symbol= scheda titolo (prezzo, grafico, metriche, look-through)
  POST   /planning/security/import           crea in Nextfolio un titolo trovato su Yahoo
  POST   /planning/simulate                  effetto di acquisti ipotetici (prima/dopo)
  GET    /planning/scenarios                 scenari salvati
  POST   /planning/scenarios                 crea scenario
  GET    /planning/scenarios/{id}            scenario + simulazione
  PUT    /planning/scenarios/{id}            sostituisce nome/note/acquisti
  DELETE /planning/scenarios/{id}
  GET    /planning/scenarios/compare?ids=1,2 simulazioni affiancate
  POST   /planning/scenarios/{id}/execute    registra gli acquisti come transazioni reali
"""
from __future__ import annotations

import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.asset import Asset, AssetType, Exchange, PriceHistory
from app.models.bond_detail import BondDetail
from app.models.planning import PlanningScenario, PlanningScenarioItem
from app.models.transaction import TransactionType
from app.models.user import User
from app.models.watchlist import WatchlistItem
from app.schemas.asset import AssetCreate, AssetUpdate
from app.schemas.portfolio import AllocationOut, XRayResponse
from app.schemas.transaction import TransactionCreate
from app.services.asset import get_asset_by_id, get_or_create_asset, search_assets, update_asset
from app.services.audit import log_action
from app.services.market_data import external
from app.services.market_data.updater import invalidate_perf_cache
from app.services.planning.metrics import price_metrics
from app.services.planning.simulate import SimItem, simulate
from app.services.portfolio.classification import (
    ASSET_CLASS_LABELS,
    asset_class,
    asset_class_weights,
    build_asset_info,
    currency_exposure,
    display_ticker,
)
from app.services.portfolio.snapshot import load_snapshot
from app.services.transaction import BatchError, create_transactions_batch

router = APIRouter(prefix="/planning", tags=["planning"])

EXECUTE_SCENARIO = "EXECUTE_SCENARIO"
AssetTypeLit = Literal["STOCK", "ETF", "BOND", "CRYPTO", "COMMODITY", "REIT", "OTHER"]


def _enum(v) -> str:
    return v.value if hasattr(v, "value") else str(v)


# ── Ricerca ──────────────────────────────────────────────────────────────────


class SearchResult(BaseModel):
    source: Literal["local", "yahoo"]
    asset_id: int | None = None
    symbol: str | None = None          # ticker Yahoo (per i titoli esterni o con yahoo_ticker)
    ticker: str | None = None          # ticker leggibile
    name: str
    isin: str | None = None
    type: str
    exchange: str | None = None
    exchange_label: str | None = None
    currency: str | None = None
    in_portfolio: bool = False
    in_watchlist: bool = False


async def _held_and_watched(db: AsyncSession, user: User) -> tuple[set[int], set[int]]:
    from app.services.portfolio.positions import calculate_positions
    from app.services.transaction import get_transactions

    held = set(calculate_positions(await get_transactions(db, user.id, limit=10_000)).keys())
    watched = set((await db.execute(
        select(WatchlistItem.asset_id).where(WatchlistItem.user_id == user.id)
    )).scalars())
    return held, watched


@router.get("/search", response_model=list[SearchResult])
async def search(
    q: str = Query(..., min_length=3, max_length=100),
    type: AssetTypeLit | None = Query(None),
    external_search: bool = Query(True, alias="external"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = q.strip()
    held, watched = await _held_and_watched(db, current_user)
    local = await search_assets(db, q, limit=15, asset_type=type)
    out = [SearchResult(
        source="local", asset_id=a.id, symbol=a.yahoo_ticker, ticker=display_ticker(build_asset_info(a)) or None,
        name=a.name, isin=a.isin, type=_enum(a.type), exchange=_enum(a.exchange), currency=a.currency,
        in_portfolio=a.id in held, in_watchlist=a.id in watched,
    ) for a in local]
    # i titoli in portafoglio prima
    out.sort(key=lambda r: (not r.in_portfolio, not r.in_watchlist, r.name.lower()))

    if external_search:
        known = {(r.symbol or "").upper() for r in out} | {(r.isin or "").upper() for r in out}
        for y in await external.search_yahoo(q, limit=10):
            if type and y["type"] != type:
                continue
            if y["symbol"].upper() in known:
                continue
            out.append(SearchResult(**y))
    return out[:25]


# ── Scheda titolo ─────────────────────────────────────────────────────────────


class SecurityCard(BaseModel):
    source: Literal["local", "yahoo"]
    asset_id: int | None
    symbol: str | None
    ticker: str | None
    name: str
    isin: str | None
    type: str
    currency: str | None
    price: float | None
    price_eur: float | None
    change_pct: float | None
    asset_class: str
    asset_class_weights: dict[str, float]
    currency_exposure: dict[str, float]
    sectors: list[dict] = []
    countries: list[dict] = []
    holdings: list[dict] = []
    history: list[dict] = []           # [{date, close}] in EUR, ultimi 3 anni
    metrics: dict = {}
    in_portfolio: bool = False
    in_watchlist: bool = False


async def _local_history(db: AsyncSession, asset_id: int, days: int = 365 * 5) -> list[dict]:
    since = datetime.date.today() - datetime.timedelta(days=days)
    rows = (await db.execute(
        select(PriceHistory.date, PriceHistory.close)
        .where(PriceHistory.asset_id == asset_id, PriceHistory.date >= since)
        .order_by(PriceHistory.date)
    )).all()
    return [{"date": d.isoformat(), "close": c} for d, c in rows if c is not None and c == c]


async def _local_price(db: AsyncSession, asset: Asset) -> dict | None:
    from app.api.v1.endpoints.portfolio import _fetch_prices_parallel

    data = (await _fetch_prices_parallel(db, {asset.id: asset})).get(asset.id)
    if not data or data.get("price") is None:
        return None
    return {"price": data["price"], "price_eur": data["price"] * data.get("exchange_rate", 1.0),
            "currency": data.get("currency") or asset.currency, "change_pct": data.get("change_pct")}


async def _external_info(symbol: str, type_: str, name: str | None = None, isin: str | None = None) -> dict:
    prof = await external.profile(symbol, type_)
    return {
        "type": type_, "name": name or symbol, "symbol": symbol.split(".")[0], "isin": isin,
        "yahoo_ticker": symbol, "currency": None, "sectors": prof.get("sectors"), "countries": prof.get("countries"),
        "sectors_override": None, "countries_override": None, "asset_class_override": None,
        "holdings": prof.get("holdings"),
    }


@router.get("/security", response_model=SecurityCard)
async def security(
    asset_id: int | None = Query(None),
    symbol: str | None = Query(None, max_length=50),
    type: AssetTypeLit | None = Query(None),
    name: str | None = Query(None, max_length=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if asset_id is None and not symbol:
        raise HTTPException(400, "Indica asset_id oppure symbol")
    held, watched = await _held_and_watched(db, current_user)

    if asset_id is not None:
        asset = await get_asset_by_id(db, asset_id)
        if not asset:
            raise HTTPException(404, "Asset non trovato")
        info = build_asset_info(asset)
        price = await _local_price(db, asset) or {}
        history = await _local_history(db, asset.id)
        if not history and asset.yahoo_ticker:
            history = await external.history_eur(asset.yahoo_ticker, "5y")
        card = dict(source="local", asset_id=asset.id, symbol=asset.yahoo_ticker, ticker=display_ticker(info) or None,
                    name=asset.name, isin=asset.isin, type=_enum(asset.type), currency=asset.currency,
                    holdings=(asset.holdings_override or asset.holdings or [])[:10],
                    in_portfolio=asset.id in held, in_watchlist=asset.id in watched)
    else:
        type_ = type or "ETF"
        info = await _external_info(symbol, type_, name)
        price = await external.quote_eur(symbol) or {}
        info["currency"] = price.get("currency") or "EUR"
        history = await external.history_eur(symbol, "5y")
        card = dict(source="yahoo", asset_id=None, symbol=symbol, ticker=symbol.split(".")[0], name=name or symbol,
                    isin=None, type=type_, currency=price.get("currency"), holdings=(info.get("holdings") or [])[:10])

    eff = lambda k: info.get(f"{k}_override") or info.get(k) or []  # noqa: E731
    weights = asset_class_weights(info)
    three_years = (datetime.date.today() - datetime.timedelta(days=365 * 3)).isoformat()
    return SecurityCard(
        **card,
        price=price.get("price"), price_eur=price.get("price_eur"), change_pct=price.get("change_pct"),
        asset_class=ASSET_CLASS_LABELS[asset_class(info)],
        asset_class_weights={ASSET_CLASS_LABELS[k]: round(v, 4) for k, v in weights.items()},
        currency_exposure={k: round(v, 4) for k, v in currency_exposure(info).items()},
        sectors=eff("sectors"), countries=eff("countries"),
        history=[h for h in history if h["date"] >= three_years],
        metrics=price_metrics(history),
    )


class ImportIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    type: AssetTypeLit
    isin: str | None = None
    currency: str | None = Field(None, min_length=3, max_length=3)


async def import_external_asset(db: AsyncSession, symbol: str, name: str, type_: str,
                                isin: str | None = None, currency: str | None = None) -> Asset:
    """Crea (o ritrova per ISIN / ticker Yahoo) un titolo trovato su Yahoo."""
    existing = (await db.execute(select(Asset).where(Asset.yahoo_ticker == symbol))).scalars().first()
    if existing:
        return existing
    if not currency:
        currency = ((await external.quote_eur(symbol)) or {}).get("currency") or "EUR"
    asset = await get_or_create_asset(db, AssetCreate(
        isin=isin, symbol=symbol.split(".")[0].upper(), name=name, type=AssetType(type_),
        exchange=Exchange.OTHER, currency=currency,
    ))
    if not asset.yahoo_ticker:
        asset = await update_asset(db, asset, AssetUpdate(yahoo_ticker=symbol))
    try:
        from app.services.market_data.enricher import enrich_asset
        await enrich_asset(db, asset)
    except Exception:
        pass  # i dati di look-through si possono arricchire anche dopo
    return asset


@router.post("/security/import", status_code=201)
async def import_security(
    body: ImportIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = await import_external_asset(db, body.symbol, body.name, body.type, body.isin, body.currency)
    return {"asset_id": asset.id, "name": asset.name}


# ── Simulazione ──────────────────────────────────────────────────────────────


class SimItemIn(BaseModel):
    asset_id: int | None = None
    symbol: str | None = Field(None, max_length=50)
    name: str | None = Field(None, max_length=200)
    type: AssetTypeLit | None = None
    isin: str | None = None
    amount_eur: float | None = Field(None, gt=0)
    quantity: float | None = Field(None, gt=0)
    price_eur: float | None = Field(None, gt=0, description="Prezzo ipotizzato; default: prezzo corrente")
    fee_eur: float = Field(0.0, ge=0)
    account_id: int | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.asset_id is None and not self.symbol:
            raise ValueError("Indica asset_id oppure symbol")
        if (self.amount_eur is None) == (self.quantity is None):
            raise ValueError("Indica l'importo in EUR oppure la quantità")
        return self


class SimulateIn(BaseModel):
    items: list[SimItemIn] = Field(min_length=1, max_length=30)
    use_cash: bool = False


class RuleChange(BaseModel):
    key: str
    name: str
    category: str
    before_status: str | None
    after_status: str
    before_actual: float | None
    after_actual: float | None
    changed: bool


class ResolvedItem(BaseModel):
    name: str
    asset_id: int | None
    symbol: str | None
    price_eur: float
    quantity: float
    amount_eur: float
    fee_eur: float
    account_id: int | None
    asset_class: str


class SimulateOut(BaseModel):
    items: list[ResolvedItem]
    allocation_before: AllocationOut
    allocation_after: AllocationOut
    xray_before: XRayResponse
    xray_after: XRayResponse
    rule_changes: list[RuleChange]
    weights: list[dict]
    total_before_eur: float
    total_after_eur: float
    invested_eur: float
    fees_eur: float
    cash_before_eur: float
    cash_after_eur: float
    warnings: list[str]


async def _resolve(db: AsyncSession, snapshot, items: list[SimItemIn]) -> tuple[list[SimItem], list[str]]:
    out: list[SimItem] = []
    warnings: list[str] = []
    for it in items:
        if it.asset_id is not None:
            asset = await get_asset_by_id(db, it.asset_id)
            if not asset:
                raise HTTPException(404, f"Asset {it.asset_id} non trovato")
            info = build_asset_info(asset)
            price = it.price_eur or snapshot.price_eur.get(asset.id) or ((await _local_price(db, asset)) or {}).get("price_eur")
            name, symbol = asset.name, asset.yahoo_ticker
        else:
            type_ = it.type or "ETF"
            info = await _external_info(it.symbol, type_, it.name, it.isin)
            quote = (await external.quote_eur(it.symbol)) or {}
            info["currency"] = quote.get("currency") or "EUR"
            price = it.price_eur or quote.get("price_eur")
            name, symbol = it.name or it.symbol, it.symbol
        if not price:
            warnings.append(f"{name}: prezzo non disponibile, indica un prezzo per simulare l'acquisto.")
            continue
        qty = it.quantity if it.quantity is not None else it.amount_eur / price
        out.append(SimItem(name=name, info=info, price_eur=price, quantity=qty, asset_id=it.asset_id,
                           symbol=symbol, fee_eur=it.fee_eur, account_id=it.account_id))
    return out, warnings


async def run_simulation(db: AsyncSession, user: User, body: SimulateIn) -> SimulateOut:
    snapshot = await load_snapshot(db, user)
    accounts = {a.id: a.name for a in snapshot.accounts}
    for it in body.items:
        if it.account_id is not None and it.account_id not in accounts:
            raise HTTPException(404, f"Conto {it.account_id} non trovato")
    sim_items, warnings = await _resolve(db, snapshot, body.items)
    ids = [i for i in list(snapshot.positions) + [x.asset_id for x in sim_items] if i is not None and i > 0]
    maturities = {a: m for a, m in (await db.execute(
        select(BondDetail.asset_id, BondDetail.maturity_date).where(BondDetail.asset_id.in_(ids))
    )).all() if m is not None}
    res = simulate(snapshot, sim_items, use_cash=body.use_cash, accounts=accounts, maturities=maturities)
    return SimulateOut(
        items=[ResolvedItem(name=i.name, asset_id=i.asset_id, symbol=i.symbol, price_eur=round(i.price_eur, 6),
                            quantity=round(i.quantity, 6), amount_eur=round(i.amount_eur, 2), fee_eur=i.fee_eur,
                            account_id=i.account_id, asset_class=ASSET_CLASS_LABELS[asset_class(i.info)])
               for i in sim_items],
        allocation_before=res.allocation_before, allocation_after=res.allocation_after,
        xray_before=res.xray_before, xray_after=res.xray_after,
        rule_changes=[RuleChange(**r) for r in res.rule_changes], weights=res.weights,
        total_before_eur=res.total_before_eur, total_after_eur=res.total_after_eur,
        invested_eur=res.invested_eur, fees_eur=res.fees_eur,
        cash_before_eur=res.cash_before_eur, cash_after_eur=res.cash_after_eur,
        warnings=warnings + res.warnings,
    )


@router.post("/simulate", response_model=SimulateOut)
async def simulate_endpoint(
    body: SimulateIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await run_simulation(db, current_user, body)


# ── Scenari ──────────────────────────────────────────────────────────────────


class ScenarioItemIO(SimItemIn):
    id: int | None = None


class ScenarioIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    notes: str | None = Field(None, max_length=2000)
    use_cash: bool = False
    items: list[ScenarioItemIO] = Field(default_factory=list, max_length=30)


class ScenarioOut(BaseModel):
    id: int
    name: str
    notes: str | None
    use_cash: bool
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    executed_at: datetime.datetime | None
    items: list[ScenarioItemIO]


def _scenario_out(s: PlanningScenario) -> ScenarioOut:
    return ScenarioOut(
        id=s.id, name=s.name, notes=s.notes, use_cash=s.use_cash, status=s.status, created_at=s.created_at,
        updated_at=s.updated_at, executed_at=s.executed_at,
        items=[ScenarioItemIO(id=i.id, asset_id=i.asset_id, symbol=i.symbol, name=i.name, type=i.type, isin=i.isin,
                              amount_eur=i.amount_eur, quantity=i.quantity, price_eur=i.price_eur, fee_eur=i.fee_eur,
                              account_id=i.account_id) for i in s.items],
    )


async def _get_scenario(db: AsyncSession, user: User, scenario_id: int) -> PlanningScenario:
    s = await db.get(PlanningScenario, scenario_id)
    if not s or s.user_id != user.id:
        raise HTTPException(404, "Scenario non trovato")
    return s


async def _items_from(db: AsyncSession, user: User, items: list[ScenarioItemIO]) -> list[PlanningScenarioItem]:
    from app.services.account import get_account

    rows = []
    for it in items:
        if it.account_id is not None and not await get_account(db, it.account_id, user.id):
            raise HTTPException(404, f"Conto {it.account_id} non trovato")
        if it.asset_id is not None:
            asset = await get_asset_by_id(db, it.asset_id)
            if not asset:
                raise HTTPException(404, f"Asset {it.asset_id} non trovato")
            name, type_, isin, currency, exchange, symbol = (asset.name, _enum(asset.type), asset.isin, asset.currency,
                                                             _enum(asset.exchange), asset.yahoo_ticker)
        else:
            name, type_, isin, currency, exchange, symbol = (it.name or it.symbol, it.type or "ETF", it.isin, None,
                                                             None, it.symbol)
        rows.append(PlanningScenarioItem(
            asset_id=it.asset_id, symbol=symbol, isin=isin, name=name, type=type_, currency=currency,
            exchange=exchange, amount_eur=it.amount_eur, quantity=it.quantity, price_eur=it.price_eur,
            fee_eur=it.fee_eur, account_id=it.account_id,
        ))
    return rows


@router.get("/scenarios", response_model=list[ScenarioOut])
async def list_scenarios(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = (await db.execute(
        select(PlanningScenario).where(PlanningScenario.user_id == current_user.id)
        .order_by(PlanningScenario.updated_at.desc())
    )).scalars()
    return [_scenario_out(s) for s in rows]


@router.post("/scenarios", response_model=ScenarioOut, status_code=201)
async def create_scenario(body: ScenarioIn, db: AsyncSession = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    s = PlanningScenario(user_id=current_user.id, name=body.name.strip(), notes=body.notes, use_cash=body.use_cash)
    s.items = await _items_from(db, current_user, body.items)
    db.add(s)
    await db.commit()
    await db.refresh(s, ["items"])
    return _scenario_out(s)


def _sim_input(s: PlanningScenario) -> SimulateIn:
    return SimulateIn(use_cash=s.use_cash, items=[SimItemIn(
        asset_id=i.asset_id, symbol=None if i.asset_id else i.symbol, name=i.name, type=i.type, isin=i.isin,
        amount_eur=i.amount_eur, quantity=i.quantity, price_eur=i.price_eur, fee_eur=i.fee_eur, account_id=i.account_id,
    ) for i in s.items])


@router.get("/scenarios/compare")
async def compare_scenarios(
    ids: str = Query(..., description="ID separati da virgola, max 4"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        id_list = [int(x) for x in ids.split(",") if x.strip()][:4]
    except ValueError:
        raise HTTPException(400, "ids non validi")
    out = []
    for sid in id_list:
        s = await _get_scenario(db, current_user, sid)
        sim = await run_simulation(db, current_user, _sim_input(s)) if s.items else None
        out.append({"scenario": _scenario_out(s), "simulation": sim})
    return out


@router.get("/scenarios/{scenario_id}")
async def get_scenario(scenario_id: int, db: AsyncSession = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    s = await _get_scenario(db, current_user, scenario_id)
    sim = await run_simulation(db, current_user, _sim_input(s)) if s.items else None
    return {"scenario": _scenario_out(s), "simulation": sim}


@router.put("/scenarios/{scenario_id}", response_model=ScenarioOut)
async def update_scenario(scenario_id: int, body: ScenarioIn, db: AsyncSession = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    s = await _get_scenario(db, current_user, scenario_id)
    if s.status == "executed":
        raise HTTPException(400, "Scenario già eseguito: duplicalo per modificarlo")
    s.name, s.notes, s.use_cash = body.name.strip(), body.notes, body.use_cash
    s.items = await _items_from(db, current_user, body.items)
    s.updated_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()
    await db.refresh(s, ["items"])
    return _scenario_out(s)


@router.delete("/scenarios/{scenario_id}", status_code=204)
async def delete_scenario(scenario_id: int, db: AsyncSession = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    s = await _get_scenario(db, current_user, scenario_id)
    await db.delete(s)
    await db.commit()


class ExecuteItem(BaseModel):
    item_id: int
    quantity: float = Field(gt=0)
    price: float = Field(gt=0, description="Prezzo unitario effettivo nella valuta price_currency")
    price_currency: str = Field("EUR", min_length=3, max_length=3)
    exchange_rate: float = Field(1.0, gt=0, description="EUR per 1 unità di price_currency")
    fee: float = Field(0.0, ge=0)
    account_id: int | None = None


class ExecuteIn(BaseModel):
    account_id: int = Field(description="Conto predefinito per gli acquisti senza conto")
    date: datetime.date = Field(default_factory=datetime.date.today)
    items: list[ExecuteItem] = Field(min_length=1)


@router.post("/scenarios/{scenario_id}/execute")
async def execute_scenario(scenario_id: int, body: ExecuteIn, db: AsyncSession = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    """Registra gli acquisti dello scenario come transazioni BUY (tutto o niente)."""
    s = await _get_scenario(db, current_user, scenario_id)
    if s.status == "executed":
        raise HTTPException(400, "Scenario già eseguito")
    by_id = {i.id: i for i in s.items}
    rows: list[TransactionCreate] = []
    for ex in body.items:
        item = by_id.get(ex.item_id)
        if not item:
            raise HTTPException(404, f"Voce {ex.item_id} non presente nello scenario")
        asset_id = item.asset_id
        if asset_id is None:
            asset = await import_external_asset(db, item.symbol, item.name, item.type, item.isin, item.currency)
            asset_id = item.asset_id = asset.id
        rows.append(TransactionCreate(
            account_id=ex.account_id or item.account_id or body.account_id, asset_id=asset_id, type=TransactionType.BUY,
            date=body.date, quantity=ex.quantity, price=ex.price, price_currency=ex.price_currency,
            exchange_rate=ex.exchange_rate, fee=ex.fee, notes=f"Scenario: {s.name}",
        ))
    try:
        created, skipped = await create_transactions_batch(db, current_user.id, rows)
    except BatchError as e:
        await db.rollback()
        raise HTTPException(400, "Nessuna transazione registrata. " + "; ".join(e.errors))
    s.status = "executed"
    s.executed_at = datetime.datetime.now(datetime.timezone.utc)
    await log_action(db, user_id=current_user.id, action=EXECUTE_SCENARIO, entity_type="planning_scenario",
                     entity_id=s.id, detail={"created": [t.id for t in created], "skipped_rows": skipped})
    await db.commit()
    await invalidate_perf_cache(current_user.id)
    return {"created": [t.id for t in created], "skipped_rows": skipped}
