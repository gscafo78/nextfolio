"""
Contesto del portafoglio in formato testo (tabelle Markdown) per LLM.

Usato sia dal server MCP (app/mcp/server.py) sia dal generatore di prompt
(GET /api/v1/ai/prompt). Ispirato a PortfolioTableService di Ghostfolio:
ogni sezione ha un flag ``with_values``; se False vengono omessi gli importi
in EUR (valori, investito, P&L €, quantità, prezzi di carico) e restano solo
percentuali e dati anagrafici.

Le funzioni riusano i servizi e gli endpoint esistenti (sono normali
``async def``) per non duplicare la logica di calcolo.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.asset import Asset
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.schemas.portfolio import AllocationOut
from app.services.portfolio.allocation import TYPE_LABELS, calculate_allocation
from app.services.portfolio.classification import (
    ASSET_CLASS_LABELS,
    asset_class,
    build_asset_info,
    display_ticker,
    infer_broker,
)
from app.services.cash import latest_balances
from app.services.portfolio.positions import calculate_positions, realized_and_income
from app.services.transaction import get_transactions

logger = logging.getLogger(__name__)

_ALL = 10_000
NA = "n/d"


# ── Formattazione ────────────────────────────────────────────────────────────


def _cell(v) -> str:
    if v is None:
        return NA
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v).replace("|", "/").replace("\n", " ").strip() or NA


def table(headers: list[str], rows: list[list]) -> str:
    """Tabella Markdown. Restituisce una riga di testo se non ci sono righe."""
    if not rows:
        return "_Nessun dato._"
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def _pct(v: float | None) -> str:
    return NA if v is None else f"{v:.2f}%"


def _enum(v) -> str:
    return v.value if hasattr(v, "value") else str(v)


# ── Snapshot posizioni ───────────────────────────────────────────────────────


@dataclass
class Holding:
    asset: Asset
    quantity: float
    pmc_eur: float
    invested_eur: float
    realized_pnl_eur: float
    price: float | None
    price_eur: float | None
    value_eur: float | None
    unrealized_eur: float | None
    unrealized_pct: float | None
    change_pct: float | None
    weight_pct: float | None = None


@dataclass
class Snapshot:
    transactions: list[Transaction]
    holdings: list[Holding]
    accounts: list[Account]
    account_values: dict[str, float]
    allocation: AllocationOut
    realized_pnl_eur: float
    total_value_eur: float
    total_invested_eur: float
    income_eur: float = 0.0          # proventi netti (cedole, dividendi, interessi − costi)
    net_contributed_eur: float = 0.0  # acquisti − vendite (capitale netto versato)
    cash: list = field(default_factory=list)   # list[CashBalance]
    filters: dict = field(default_factory=dict)


async def load_snapshot(
    db: AsyncSession,
    user: User,
    *,
    account_id: int | None = None,
    asset_type: str | None = None,
) -> Snapshot:
    """Calcola posizioni aperte, prezzi correnti e allocazione (filtrabili)."""
    # Import locale: evita import circolare endpoint ↔ servizi
    from app.api.v1.endpoints.portfolio import _fetch_prices_parallel

    txs = await get_transactions(db, user.id, account_id=account_id, limit=_ALL)
    if asset_type:
        txs = [t for t in txs if _enum(t.asset.type) == asset_type]

    positions = calculate_positions(txs)
    realized, income = realized_and_income(txs)
    net_contributed = sum(
        (t.quantity * t.price * t.exchange_rate + t.fee) if t.type == TransactionType.BUY
        else -(t.quantity * t.price * t.exchange_rate - t.fee)
        for t in txs if t.type in (TransactionType.BUY, TransactionType.SELL)
    )

    res = await db.execute(select(Asset).where(Asset.id.in_(list(positions.keys()))))
    asset_map = {a.id: a for a in res.scalars()}
    price_map = await _fetch_prices_parallel(db, asset_map) if asset_map else {}

    holdings: list[Holding] = []
    price_eur: dict[int, float] = {}
    for aid, pos in positions.items():
        asset = asset_map.get(aid)
        if not asset:
            continue
        data = price_map.get(aid) or {}
        price = data.get("price")
        fx = data.get("exchange_rate", 1.0)
        peur = price * fx if price is not None else None
        if peur is not None:
            price_eur[aid] = peur
        value = pos.quantity * peur if peur is not None else None
        cost = pos.quantity * pos.pmc_eur
        unreal = value - cost if value is not None else None
        holdings.append(Holding(
            asset=asset,
            quantity=pos.quantity,
            pmc_eur=pos.pmc_eur,
            invested_eur=cost,
            realized_pnl_eur=pos.realized_pnl_eur,
            price=price,
            price_eur=peur,
            value_eur=value,
            unrealized_eur=unreal,
            unrealized_pct=(unreal / cost * 100) if unreal is not None and cost > 0 else None,
            change_pct=data.get("change_pct"),
        ))

    total_value = sum(h.value_eur or 0 for h in holdings)
    for h in holdings:
        h.weight_pct = (h.value_eur / total_value * 100) if h.value_eur and total_value > 0 else None
    holdings.sort(key=lambda h: h.value_eur or 0, reverse=True)

    acc_res = await db.execute(select(Account).where(Account.user_id == user.id).order_by(Account.name))
    accounts = list(acc_res.scalars())
    account_values: dict[str, float] = {}
    for acc in accounts:
        acc_pos = calculate_positions([t for t in txs if t.account_id == acc.id])
        v = sum(p.quantity * price_eur[a] for a, p in acc_pos.items() if a in price_eur)
        if v > 0:
            account_values[acc.name] = v

    asset_info = {a.id: build_asset_info(a) for a in asset_map.values()}
    # Liquidità: solo senza filtro per tipo di asset (non è uno strumento)
    cash = [] if asset_type else await latest_balances(db, user.id, account_id=account_id)
    allocation = calculate_allocation(positions, asset_info, price_eur, account_values, cash=cash)

    return Snapshot(
        cash=cash,
        transactions=txs,
        holdings=holdings,
        accounts=accounts,
        account_values=account_values,
        allocation=allocation,
        realized_pnl_eur=realized,
        total_value_eur=total_value,
        total_invested_eur=sum(h.invested_eur for h in holdings),
        income_eur=income,
        net_contributed_eur=net_contributed,
        filters={"account_id": account_id, "asset_type": asset_type},
    )


# ── Sezioni ──────────────────────────────────────────────────────────────────


def summary_section(s: Snapshot, with_values: bool) -> str:
    unreal = sum(h.unrealized_eur or 0 for h in s.holdings)
    cost = s.total_invested_eur
    unreal_pct = unreal / cost * 100 if cost > 0 else None
    total_pnl = unreal + s.realized_pnl_eur + s.income_eur
    total_pct = total_pnl / cost * 100 if cost > 0 else None
    cash_eur = sum(b.value_eur for b in s.cash)
    net_worth = s.total_value_eur + cash_eur
    rows = [
        ["Posizioni aperte", len(s.holdings)],
        ["Liquidità sul patrimonio totale %", _pct(cash_eur / net_worth * 100 if net_worth > 0 else None)
         if s.cash else "saldo di cassa non inserito"],
        ["P&L non realizzato % (sul costo delle posizioni aperte)", _pct(unreal_pct)],
        ["P&L totale % (non realizzato + realizzato + proventi, sul costo delle posizioni aperte)", _pct(total_pct)],
    ]
    if not with_values:
        return table(["Voce", "Valore"], rows)
    rows = [
        ["Valore di mercato degli investimenti (EUR)", round(s.total_value_eur, 2)],
        ["Liquidità dei conti (EUR)", round(cash_eur, 2) if s.cash else "non inserita"],
        ["Patrimonio totale: investimenti + liquidità (EUR)", round(net_worth, 2)],
        ["Costo di carico delle posizioni aperte (EUR)", round(cost, 2)],
        ["P&L non realizzato (EUR)", round(unreal, 2)],
        ["P&L realizzato, incluse posizioni chiuse (EUR)", round(s.realized_pnl_eur, 2)],
        ["Proventi incassati: cedole, dividendi, interessi al netto dei costi (EUR)", round(s.income_eur, 2)],
        ["P&L totale (EUR)", round(total_pnl, 2)],
        ["Capitale netto versato: acquisti − vendite (EUR)", round(s.net_contributed_eur, 2)],
    ] + rows
    note = (
        f"\n\nNota: capitale netto versato ({s.net_contributed_eur:.2f}) = costo delle posizioni aperte "
        f"({cost:.2f}) − P&L realizzato ({s.realized_pnl_eur:.2f}); la differenza "
        f"({s.net_contributed_eur - cost:.2f}) è il risultato delle vendite già effettuate. "
        "La liquidità non entra nel P&L né nel TWRR."
    )
    return table(["Voce", "Valore"], rows) + note


def holdings_table(s: Snapshot, with_values: bool) -> str:
    headers = ["Nome", "Ticker", "ISIN", "Strumento", "Asset class", "Valuta", "Peso %", "P&L non realizzato %",
               "Var. giorno %"]
    if with_values:
        headers += ["Quantità", "PMC (EUR)", "Prezzo (valuta asset)", "Valore (EUR)", "Investito (EUR)", "P&L (EUR)"]
    rows = []
    for h in s.holdings:
        a = h.asset
        info = build_asset_info(a)
        r = [
            a.name, display_ticker(info) or "—", a.isin, TYPE_LABELS.get(_enum(a.type), _enum(a.type)),
            ASSET_CLASS_LABELS[asset_class(info)], a.currency,
            _pct(h.weight_pct), _pct(h.unrealized_pct), _pct(h.change_pct),
        ]
        if with_values:
            r += [
                round(h.quantity, 6), round(h.pmc_eur, 4), h.price,
                round(h.value_eur, 2) if h.value_eur is not None else None,
                round(h.invested_eur, 2),
                round(h.unrealized_eur, 2) if h.unrealized_eur is not None else None,
            ]
        rows.append(r)
    return table(headers, rows)


def allocation_section(s: Snapshot, with_values: bool) -> str:
    a = s.allocation
    parts = []
    for title, items in (
        ("Per asset class del sottostante (ETF obbligazionari = Obbligazioni)", a.by_asset_class),
        ("Esposizione valutaria del sottostante (look-through; ETF hedged = EUR)", a.by_currency_exposure),
        ("Per tipo di strumento", a.by_type),
        ("Per valuta di quotazione", a.by_currency),
        ("Per conto", a.by_account),
        ("Per settore (look-through ETF; ETF obbligazionari = Bonds)", a.by_sector),
        ("Area geografica della parte azionaria", a.by_continent_equity),
        ("Area geografica della parte obbligazionaria", a.by_continent_bond),
    ):
        if not items:
            continue
        headers = ["Categoria", "Peso %"] + (["Valore (EUR)"] if with_values else [])
        rows = [[i.label, f"{i.pct:.1f}%"] + ([i.value_eur] if with_values else []) for i in items]
        parts.append(f"#### {title}\n{table(headers, rows)}")
    if a.italy_exposure_pct is not None:
        parts.append(f"Esposizione Italia sul totale (azioni, BTP e quota italiana degli ETF): {a.italy_exposure_pct:.1f}%")
    parts.append(
        "Nota: i pesi per paese degli ETF coprono solo i principali Paesi; la quota restante dell'esposizione "
        "valutaria è indicata come \"Non dettagliata\". Le aree geografiche sono normalizzate sui Paesi noti."
    )
    return "\n\n".join(parts) if parts else "_Nessun dato._"


WEALTH_TAX_RATE = 0.002  # IVAFE (conti esteri) e imposta di bollo (intermediari italiani): 0,2% annuo


def accounts_table(s: Snapshot, with_values: bool) -> str:
    cash = {b.account_id: b for b in s.cash}
    values = {acc.id: s.account_values.get(acc.name, 0.0) + max(cash[acc.id].value_eur, 0.0) if acc.id in cash
              else s.account_values.get(acc.name, 0.0) for acc in s.accounts}
    total = sum(values.values())
    headers = ["ID", "Nome", "Tipo", "Broker", "Valuta", "Regime", "Estero", "Imposta patrimoniale",
               "Saldo cassa aggiornato al", "Peso % (posizioni + cassa)"]
    if with_values:
        headers += ["Valore posizioni (EUR)", "Saldo cassa (valuta conto)", "Imposta patrimoniale stimata su posizioni (EUR/anno)"]
    rows = []
    for acc in s.accounts:
        pos_value = s.account_values.get(acc.name, 0.0)
        b = cash.get(acc.id)
        broker = acc.broker or (f"{infer_broker(acc.name, acc.url)} (dedotto)" if infer_broker(acc.name, acc.url) else None)
        wealth_tax = "IVAFE 0,2% (quadro RW)" if acc.is_foreign else "Imposta di bollo 0,2% (trattenuta dal broker)"
        r = [
            acc.id, acc.name, _enum(acc.type), broker, acc.currency,
            "amministrato" if acc.is_sostituto_imposta else "dichiarativo",
            "sì" if acc.is_foreign else "no",
            wealth_tax,
            b.date.isoformat() if b else "non inserito",
            _pct(values[acc.id] / total * 100 if total > 0 else None),
        ]
        if with_values:
            r += [round(pos_value, 2), round(b.balance, 2) if b else None, round(pos_value * WEALTH_TAX_RATE, 2)]
        rows.append(r)
    note = (
        "\n\nImposta patrimoniale stimata sul valore corrente delle posizioni (il calcolo ufficiale usa il valore al "
        "31/12 o di fine periodo di rendicontazione). Sulla liquidità in conto corrente si applica invece un importo "
        "fisso di 34,20 € l'anno (bollo in Italia, IVAFE all'estero) se la giacenza media supera 5.000 €."
    )
    return table(headers, rows) + note


def transactions_table(txs: list[Transaction], with_values: bool) -> str:
    headers = ["ID", "Data", "Tipo", "Conto", "Asset", "Ticker", "ISIN"]
    if with_values:
        headers += ["Quantità", "Prezzo", "Valuta prezzo", "Cambio EUR", "Commissioni", "Controvalore (EUR)"]
    rows = []
    for t in txs:
        r = [t.id, t.date.isoformat(), _enum(t.type), t.account.name, t.asset.name,
             display_ticker(build_asset_info(t.asset)) or "—", t.asset.isin]
        if with_values:
            r += [
                t.quantity, t.price, t.price_currency, round(t.exchange_rate, 6), t.fee,
                round(t.quantity * t.price * t.exchange_rate, 2),
            ]
        rows.append(r)
    return table(headers, rows)


_LONG_PERIODS = {"1y": 365, "3y": 365 * 3}


async def performance_section(
    db: AsyncSession,
    user: User,
    with_values: bool,
    *,
    account_id: int | None = None,
    periods: tuple[str, ...] = ("ytd", "1y", "3y", "max"),
) -> str:
    from app.api.v1.endpoints.portfolio import get_performance

    headers = ["Periodo", "Dal", "TWRR % (proventi inclusi)", "TWRR annualizzato %"]
    if with_values:
        headers += ["Valore iniziale (EUR)", "Flussi netti (EUR)", "Proventi (EUR)", "P&L (EUR)",
                    "Valore finale (EUR)", "Investito (EUR)"]
    rows = []
    for p in periods:
        try:
            perf = await get_performance(period=p, account_id=account_id, db=db, current_user=user)
        except Exception as e:  # pragma: no cover - dipende dai dati di mercato
            logger.warning("performance %s non disponibile: %s", p, e)
            continue
        if perf.history_truncated and p in _LONG_PERIODS:
            msg = f"n/d (storico dal {perf.start_date})"
            rows.append([p.upper(), perf.start_date, msg, NA] + ([NA] * 6 if with_values else []))
            continue
        r = [p.upper(), perf.start_date, _pct(perf.twrr_pct), _pct(perf.twrr_annualized_pct)]
        if with_values:
            r += [perf.start_value_eur, perf.net_flows_eur, perf.income_eur, perf.pnl_eur,
                  perf.end_value_eur, perf.invested_eur]
        rows.append(r)
    note = (
        "\n\nDefinizioni: P&L = valore finale − valore iniziale − flussi netti + proventi; "
        "Investito = valore iniziale + flussi netti (acquisti − vendite) del periodo. "
        "Il TWRR neutralizza versamenti e prelievi; l'annualizzato è indicato solo per periodi ≥ 1 anno."
        if with_values else
        "\n\nIl TWRR neutralizza versamenti e prelievi; l'annualizzato è indicato solo per periodi ≥ 1 anno."
    )
    return table(headers, rows) + note


async def risk_section(db: AsyncSession, user: User, *, account_id: int | None = None, period: str = "3y") -> str:
    from app.api.v1.endpoints.portfolio import get_risk_metrics

    r = await get_risk_metrics(period=period, account_id=account_id, db=db, current_user=user)
    suspicious = any("sospetti" in w for w in r.warnings)
    mark = (lambda v: f"⚠ {v} (dato sospetto)") if suspicious else (lambda v: v)
    rows = [
        ["Periodo", r.period.upper()],
        ["Giorni di borsa", r.trading_days],
        ["Volatilità annualizzata", mark(_pct(r.annualized_volatility_pct))],
        ["Max drawdown (su indice TWRR)", _pct(r.max_drawdown_pct)],
        ["Periodo max drawdown", f"{r.max_drawdown_start or NA} → {r.max_drawdown_end or NA}"],
        [f"Sharpe ratio (risk-free {r.risk_free_pct:.2f}%)", mark(r.sharpe_ratio)],
        ["Sortino ratio", mark(r.sortino_ratio)],
        ["Calmar ratio", r.calmar_ratio],
        ["TWRR annualizzato", _pct(r.twrr_annualized_pct)],
        ["Miglior giorno", mark(_pct(r.best_day_pct))],
        ["Peggior giorno", mark(_pct(r.worst_day_pct))],
        ["Giorni positivi", _pct(r.positive_days_pct)],
    ]
    out = table(["Metrica", "Valore"], rows)
    out += "\n\nRendimenti giornalieri neutralizzati dai flussi di cassa, solo giorni di borsa; volatilità × √252."
    if r.warnings:
        out += "\n\n" + "\n".join(f"- ⚠ {w}" for w in r.warnings)
    return out


async def xirr_section(db: AsyncSession, user: User) -> str:
    from app.api.v1.endpoints.portfolio import get_xirr

    v = (await get_xirr(db=db, current_user=user)).get("xirr_pct")
    return f"Rendimento annualizzato money-weighted (XIRR) dall'inizio: {_pct(v)}"


async def xray_section(db: AsyncSession, user: User, with_values: bool) -> str:
    from app.api.v1.endpoints.portfolio import get_xray

    x = await get_xray(background_tasks=BackgroundTasks(), db=db, current_user=user)
    rows = []
    for rule in x.rules:
        monetary = rule.unit == "EUR"
        actual = None if (monetary and not with_values) else rule.actual
        rows.append([
            rule.category, rule.name, rule.status.upper(),
            f"{actual:.2f} {rule.unit}" if actual is not None else NA,
            f"{rule.threshold_min if rule.threshold_min is not None else '-'} / "
            f"{rule.threshold_max if rule.threshold_max is not None else '-'}",
            rule.description,
        ])
    head = f"Punteggio: {x.score}/100 ({x.rules_ok}/{x.rules_total} regole superate)\n\n"
    return head + table(["Categoria", "Regola", "Esito", "Valore", "Soglia min / max", "Descrizione"], rows)


async def dividends_section(db: AsyncSession, user: User, with_values: bool) -> str:
    from app.api.v1.endpoints.portfolio import get_dividends

    divs = await get_dividends(db=db, current_user=user)
    by_year: dict[int, dict[str, list]] = {}
    for d in divs:
        y = by_year.setdefault(d.date.year, {})
        y.setdefault(d.type, []).append(d.amount_eur)
    headers = ["Anno", "Tipo", "N. incassi"] + (["Totale netto (EUR)"] if with_values else [])
    rows = []
    for year in sorted(by_year, reverse=True):
        for typ, amounts in sorted(by_year[year].items()):
            rows.append([year, typ, len(amounts)] + ([round(sum(amounts), 2)] if with_values else []))
    return table(headers, rows)


async def watchlist_table(db: AsyncSession, user: User) -> str:
    from app.api.v1.endpoints.watchlist import list_watchlist

    items = await list_watchlist(db=db, current_user=user)
    rows = [
        [i.id, i.asset_id, i.name, i.symbol, TYPE_LABELS.get(i.asset_type, i.asset_type), i.currency,
         i.current_price, _pct(i.change_pct), i.target_price, i.note]
        for i in sorted(items, key=lambda i: i.name.lower())
    ]
    return table(["ID voce", "ID asset", "Nome", "Simbolo", "Tipo", "Valuta", "Prezzo", "Var. giorno %",
                  "Prezzo obiettivo", "Nota"], rows)


_TAX_RULES = (
    "Regole applicate: plusvalenze su azioni, obbligazioni societarie ed ETC sono *redditi diversi* al 26%; "
    "titoli di Stato italiani e white list al 12,5% (imponibili e deducibili al 48,08% nello stesso zainetto); "
    "le plusvalenze da ETF/fondi sono *redditi di capitale* (26%, ridotto per la quota in titoli di Stato) e "
    "NON possono essere compensate con le minusvalenze, mentre le minusvalenze da ETF entrano nello zainetto; "
    "le minusvalenze si usano entro il quarto anno successivo; cripto-attività al 33% dal 2026 con zainetto proprio; "
    "costo fiscale al costo medio ponderato."
)


async def tax_section(db: AsyncSession, user: User, year: int, with_values: bool = True) -> str:
    from app.api.v1.endpoints.tax import get_tax_report

    if not with_values:
        return f"Anno fiscale {year}. {_TAX_RULES}\n\nImporti omessi per riservatezza."
    r = await get_tax_report(year=year, db=db, current_user=user)

    rows = [
        ["Redditi diversi", "Plusvalenze 26% (azioni, obbligazioni societarie, ETC…)", r.gains_standard],
        ["Redditi diversi", "Minusvalenze 26%", r.losses_standard],
        ["Redditi diversi", "Plusvalenze titoli di Stato (al 48,08% → 12,5%)", r.gains_govt],
        ["Redditi diversi", "Minusvalenze titoli di Stato (deducibili al 48,08%)", r.losses_govt],
        ["Redditi diversi", "Minusvalenze da ETF/fondi (nello zainetto)", r.losses_funds],
        ["Redditi diversi", "Plusvalenze imponibili ponderate", r.taxable_gains_standard],
        ["Redditi diversi", "Minusvalenze compensabili ponderate", r.taxable_losses_standard],
        ["Redditi diversi", "Zainetto pregresso utilizzato", r.carryforward_applied_standard],
        ["Redditi diversi", "Imponibile netto 26%", r.net_taxable_standard],
        ["Redditi diversi", "Imposta 26%", r.tax_standard],
        ["Redditi diversi", "Nuove minusvalenze riportabili", r.new_carryforward_standard],
        ["Redditi di capitale", "Plusvalenze da ETF/fondi (non compensabili)", r.gains_funds],
        ["Redditi di capitale", "Imposta su ETF/fondi", r.tax_funds],
        ["Redditi di capitale", "Dividendi", r.dividends_eur],
        ["Redditi di capitale", "Cedole titoli di Stato (12,5%)", r.coupons_govt_eur],
        ["Redditi di capitale", "Cedole altre obbligazioni (26%)", r.coupons_standard_eur],
        ["Redditi di capitale", "Interessi", r.interests_eur],
        ["Cripto-attività", "Plusvalenze", r.gains_crypto],
        ["Cripto-attività", "Minusvalenze", r.losses_crypto],
        ["Cripto-attività", "Zainetto cripto utilizzato", r.carryforward_applied_crypto],
        ["Cripto-attività", f"Imposta {r.crypto_rate * 100:.0f}%", r.tax_crypto],
        ["Totale", "Imposta su plusvalenze dell'anno", r.total_tax_due],
        ["Patrimoniale", "IVAFE stimata (conti esteri)", r.ivafe.ivafe_eur if r.ivafe else 0],
    ]
    rows = [x for x in rows if abs(x[2] or 0) > 0.005 or x[0] == "Totale"]
    out = f"Anno fiscale {year} (importi in EUR)\n\n" + table(["Tipo di reddito", "Voce", "Importo (EUR)"], rows)

    schedule = [
        ["Redditi diversi", e.year, round(e.amount, 2), e.expires_year] for e in r.prior_carryforward_standard
    ] + [["Cripto-attività", e.year, round(e.amount, 2), e.expires_year] for e in r.prior_carryforward_crypto]
    new_rows = []
    if r.new_carryforward_standard > 0.005:
        new_rows.append(["Redditi diversi", year, round(r.new_carryforward_standard, 2), year + 4])
    if r.new_carryforward_crypto > 0.005:
        new_rows.append(["Cripto-attività", year, round(r.new_carryforward_crypto, 2), year + 4])
    out += "\n\n#### Scadenziario minusvalenze (zainetto)\n" + table(
        ["Zainetto", "Anno di realizzo", "Residuo (EUR)", "Utilizzabile fino al"], schedule + new_rows)
    return out + "\n\n" + _TAX_RULES


# ── Prompt per chatbot ───────────────────────────────────────────────────────

_INSTRUCTIONS = {
    "it": {
        "intro": "Sei un assistente finanziario neutrale. Analizza in parole semplici il seguente portafoglio di investimento (valuta di base EUR) di un investitore fiscalmente residente in Italia.",
        "no_values": "Per riservatezza gli importi assoluti sono stati omessi: ragiona solo su pesi e percentuali.",
        "structure": "Struttura la risposta con queste sezioni:",
        "sections": [
            "Panoramica: riassumi brevemente composizione e logica di allocazione del portafoglio.",
            "Valutazione del rischio: individua i rischi potenziali, inclusi volatilità di mercato, concentrazione, esposizione valutaria e squilibri settoriali o geografici.",
            "Punti di forza: evidenzia i vantaggi, come potenziale di crescita, diversificazione, costi o altri benefici.",
            "Punti deboli: segnala le debolezze, come sovraesposizioni o mancanza di asset difensivi.",
            "Profilo dell'investitore: a chi potrebbe adattarsi questo portafoglio (tolleranza al rischio, obiettivi, fase di vita, esperienza).",
            "Idee di ottimizzazione: proponi idee per completare il portafoglio, in modo costruttivo e neutrale, tenendo conto della fiscalità italiana (26% su azioni/ETF/crypto, 12,5% su titoli di Stato, compensazione minusvalenze, IVAFE per conti esteri).",
            "Conclusione: sintesi concisa dei punti chiave.",
        ],
        "disclaimer": "Ricorda che non si tratta di consulenza finanziaria personalizzata.",
        "lang": "Rispondi in italiano.",
    },
    "en": {
        "intro": "You are a neutral financial assistant. Please analyze the following investment portfolio (base currency EUR) of an investor who is tax resident in Italy, in simple words.",
        "no_values": "For privacy, absolute amounts have been omitted: reason only on weights and percentages.",
        "structure": "Structure your answer with these sections:",
        "sections": [
            "Overview: briefly summarize the portfolio's composition and allocation rationale.",
            "Risk Assessment: identify potential risks, including market volatility, concentration, currency exposure and sectoral or geographic imbalances.",
            "Advantages: highlight strengths, focusing on growth potential, diversification, costs or other benefits.",
            "Disadvantages: point out weaknesses, such as overexposure or lack of defensive assets.",
            "Target Group: discuss who this portfolio might suit (risk tolerance, investment goals, life stage, experience).",
            "Optimization Ideas: offer ideas to complement the portfolio, constructive and neutral in tone, considering Italian taxation (26% on stocks/ETFs/crypto, 12.5% on government bonds, capital loss offsetting, IVAFE on foreign accounts).",
            "Conclusion: provide a concise summary highlighting key insights.",
        ],
        "disclaimer": "Remember this is not personalized financial advice.",
        "lang": "Provide your answer in English.",
    },
    "fr": {
        "intro": "Tu es un assistant financier neutre. Analyse en termes simples le portefeuille d'investissement suivant (devise de base EUR) d'un investisseur résident fiscal en Italie.",
        "no_values": "Par confidentialité, les montants absolus ont été omis : raisonne uniquement sur les pondérations et les pourcentages.",
        "structure": "Structure ta réponse avec ces sections :",
        "sections": [
            "Aperçu : résume brièvement la composition et la logique d'allocation du portefeuille.",
            "Évaluation des risques : identifie les risques potentiels, notamment volatilité, concentration, exposition aux devises et déséquilibres sectoriels ou géographiques.",
            "Avantages : souligne les points forts, comme le potentiel de croissance, la diversification, les coûts ou d'autres bénéfices.",
            "Inconvénients : signale les faiblesses, comme une surexposition ou l'absence d'actifs défensifs.",
            "Profil cible : à qui ce portefeuille pourrait convenir (tolérance au risque, objectifs, étape de vie, expérience).",
            "Pistes d'optimisation : propose des idées pour compléter le portefeuille, de manière constructive et neutre, en tenant compte de la fiscalité italienne (26 % actions/ETF/crypto, 12,5 % obligations d'État, compensation des moins-values, IVAFE pour comptes étrangers).",
            "Conclusion : synthèse concise des points clés.",
        ],
        "disclaimer": "Rappelle qu'il ne s'agit pas d'un conseil financier personnalisé.",
        "lang": "Réponds en français.",
    },
    "de": {
        "intro": "Du bist ein neutraler Finanzassistent. Analysiere in einfachen Worten das folgende Anlageportfolio (Basiswährung EUR) eines in Italien steuerlich ansässigen Anlegers.",
        "no_values": "Aus Datenschutzgründen wurden absolute Beträge weggelassen: argumentiere nur mit Gewichtungen und Prozentsätzen.",
        "structure": "Gliedere deine Antwort in diese Abschnitte:",
        "sections": [
            "Überblick: Fasse Zusammensetzung und Allokationslogik des Portfolios kurz zusammen.",
            "Risikobewertung: Identifiziere mögliche Risiken, einschließlich Volatilität, Konzentration, Währungsrisiko und sektoraler oder geografischer Ungleichgewichte.",
            "Vorteile: Hebe Stärken hervor, etwa Wachstumspotenzial, Diversifikation, Kosten oder andere Vorteile.",
            "Nachteile: Zeige Schwächen auf, etwa Übergewichtungen oder fehlende defensive Anlagen.",
            "Zielgruppe: Für wen dieses Portfolio geeignet sein könnte (Risikotoleranz, Ziele, Lebensphase, Erfahrung).",
            "Optimierungsideen: Biete konstruktive und neutrale Ideen zur Ergänzung des Portfolios unter Berücksichtigung der italienischen Besteuerung (26 % auf Aktien/ETF/Krypto, 12,5 % auf Staatsanleihen, Verlustverrechnung, IVAFE auf ausländische Konten).",
            "Fazit: Kurze Zusammenfassung der wichtigsten Erkenntnisse.",
        ],
        "disclaimer": "Weise darauf hin, dass dies keine persönliche Finanzberatung ist.",
        "lang": "Antworte auf Deutsch.",
    },
}

SUPPORTED_LANGUAGES = tuple(_INSTRUCTIONS)


async def _safe(title: str, coro) -> str | None:
    try:
        body = await coro
    except Exception as e:  # una sezione non deve far fallire tutto il prompt
        logger.warning("Sezione '%s' non disponibile: %s", title, e)
        return None
    return f"### {title}\n{body}"


async def build_portfolio_context(
    db: AsyncSession,
    user: User,
    *,
    with_values: bool,
    account_id: int | None = None,
    asset_type: str | None = None,
) -> str:
    """Tutte le sezioni dati del portafoglio, pronte per un LLM."""
    snap = await load_snapshot(db, user, account_id=account_id, asset_type=asset_type)
    filtered = account_id is not None or asset_type is not None

    head = [f"## Portafoglio al {date.today().isoformat()} (valuta di base EUR)"]
    if account_id is not None:
        acc = next((a for a in snap.accounts if a.id == account_id), None)
        head.append(f"Filtro conto: {acc.name if acc else account_id}")
    if asset_type:
        head.append(f"Filtro tipo asset: {TYPE_LABELS.get(asset_type, asset_type)}")

    sections: list[str | None] = [
        f"### Riepilogo\n{summary_section(snap, with_values)}",
        f"### Posizioni aperte\n{holdings_table(snap, with_values)}",
        f"### Allocazione\n{allocation_section(snap, with_values)}",
    ]
    if account_id is None:
        sections.append(f"### Conti\n{accounts_table(snap, with_values)}")
    if asset_type is None:
        # performance e rischio supportano solo il filtro per conto
        sections.append(await _safe("Performance (TWRR, proventi inclusi)",
                                    performance_section(db, user, with_values, account_id=account_id)))
        sections.append(await _safe("Metriche di rischio", risk_section(db, user, account_id=account_id)))
    if not filtered:
        sections.append(await _safe("XIRR", xirr_section(db, user)))
        sections.append(await _safe("Diagnostica X-Ray", xray_section(db, user, with_values)))
        sections.append(await _safe("Dividendi, cedole e interessi per anno", dividends_section(db, user, with_values)))
        sections.append(await _safe("Fiscalità (anno in corso)", tax_section(db, user, date.today().year, with_values)))

    return "\n".join(head) + "\n\n" + "\n\n".join(s for s in sections if s)


async def build_prompt(
    db: AsyncSession,
    user: User,
    *,
    mode: str,
    language: str,
    with_values: bool,
    account_id: int | None = None,
    asset_type: str | None = None,
) -> str:
    """mode='portfolio' → solo dati; mode='analysis' → dati + istruzioni di analisi."""
    context = await build_portfolio_context(
        db, user, with_values=with_values, account_id=account_id, asset_type=asset_type,
    )
    if mode == "portfolio":
        return context

    t = _INSTRUCTIONS.get(language, _INSTRUCTIONS["en"])
    lines = [t["intro"]]
    if not with_values:
        lines.append(t["no_values"])
    lines += ["", context, "", t["structure"]]
    lines += [f"{i}. {s}" for i, s in enumerate(t["sections"], 1)]
    lines += ["", t["disclaimer"], t["lang"]]
    return "\n".join(lines)
