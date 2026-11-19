"""Motore X-Ray — valuta 11 regole di rischio sul portafoglio e restituisce XRayResponse.

Categorie e regole:
  Concentrazione      → concentration_single_asset, concentration_single_account, concentration_crypto
  Asset Class         → asset_class_equity, asset_class_fixed_income, asset_class_currency_eur
  Fee                 → fee_ratio
  Diversif. geografica → geo_diversification, geo_home_bias, geo_italy_exposure
  Liquidità           → liquidity_emergency_fund

Le regole usano la classificazione per sottostante (``classification``):
ETF obbligazionari = obbligazioni, valute look-through, geografia della sola
parte azionaria. La concentrazione per titolo esclude ETF e fondi.
"""

from __future__ import annotations

from datetime import date

from app.schemas.portfolio import XRayResponse, XRayRule
from app.services.portfolio.classification import (
    MONEY_MARKET,
    asset_class_weights,
    is_diversified_fund,
    maturity_from_name,
    residual_months,
)
from app.services.portfolio.allocation import TYPE_LABELS as _TL


def _lbl(raw: str) -> str:
    """Converte un tipo raw (es. 'BOND') nel label usato da by_type (es. 'Obbligazioni')."""
    return _TL.get(raw, raw)

# ── Soglie di default ─────────────────────────────────────────────────────────

_DEF = {
    "concentration_single_asset":   {"max": 0.20},
    "concentration_single_account": {"max": 0.80},
    "concentration_crypto":         {"max": 0.10},
    "asset_class_equity":           {"min": 0.50, "max": 0.80},
    "asset_class_fixed_income":     {"min": 0.05, "max": 0.30},
    "asset_class_currency_eur":     {"min": 0.30},
    "fee_ratio":                    {"max": 0.015},
    "geo_diversification":          {"max": 0.70},
    "geo_home_bias":                {"max": 0.50},
    "geo_italy_exposure":           {"max": 0.40},
    "liquidity_emergency_fund":     {"min": 0.02, "max_maturity_months": 12},
}


def _pct(v: float | None) -> float | None:
    return round(v * 100, 1) if v is not None else None


def compute_xray(
    *,
    positions: list,           # list[PositionOut]
    allocation: object,        # AllocationOut
    transactions: list,        # list[Transaction] con .fee e .total_eur
    total_value: float,
    asset_info: dict[int, dict] | None = None,      # build_asset_info per asset_id
    maturities: dict[int, date] | None = None,      # scadenze obbligazioni (bond_details)
    today: date | None = None,
) -> XRayResponse:
    asset_info = asset_info or {}
    maturities = maturities or {}
    today = today or date.today()
    rules: list[XRayRule] = []

    # ── helpers allocation lookup ─────────────────────────────────────────────

    def _alloc_pct(items, label: str) -> float | None:
        for item in items:
            if item.label.upper() == label.upper():
                return item.pct / 100 if item.pct is not None else None
        return None

    def _max_alloc_pct(items) -> float | None:
        if not items:
            return None
        return max((item.pct or 0) for item in items) / 100

    # ── CATEGORIA: Concentrazione ─────────────────────────────────────────────

    # 1. Concentrazione singolo titolo — solo azioni e obbligazioni singole (no ETF/fondi)
    thr = _DEF["concentration_single_asset"]["max"]
    singles = [
        p for p in positions
        if not is_diversified_fund(asset_info.get(p.asset_id, {"type": p.asset_type}))
        and p.asset_type in ("STOCK", "REIT", "BOND")
    ]
    desc = (
        "Nessuna singola azione od obbligazione dovrebbe superare il 20% del portafoglio: un peso eccessivo "
        "espone al rischio del singolo emittente. ETF e fondi sono esclusi perché già diversificati."
    )
    if total_value > 0 and positions:
        top = max(singles, key=lambda p: p.current_value_eur or 0, default=None)
        max_weight = (top.current_value_eur or 0) / total_value if top else 0.0
        status = "ok" if max_weight <= thr else ("warn" if max_weight <= thr * 1.5 else "error")
        rules.append(XRayRule(
            key="concentration_single_asset",
            name="Concentrazione singolo titolo",
            category="Concentrazione",
            description=desc + (f" Titolo più pesante: {top.name}." if top else " Nessun titolo singolo in portafoglio."),
            status=status,
            actual=_pct(max_weight),
            threshold_max=_pct(thr),
            unit="%",
        ))
    else:
        rules.append(XRayRule(
            key="concentration_single_asset",
            name="Concentrazione singolo titolo",
            category="Concentrazione",
            description=desc,
            status="info",
            unit="%",
        ))

    # 2. Concentrazione per conto/broker
    by_account = getattr(allocation, "by_account", [])
    if by_account and total_value > 0:
        max_acc = _max_alloc_pct(by_account)
        thr = _DEF["concentration_single_account"]["max"]
        status = "ok" if (max_acc or 0) <= thr else "warn"
        rules.append(XRayRule(
            key="concentration_single_account",
            name="Concentrazione per conto / broker",
            category="Concentrazione",
            description=(
                "Avere oltre l'80% del portafoglio su un unico broker aumenta il rischio "
                "operativo (fallimento broker, blocco temporaneo dei conti)."
            ),
            status=status,
            actual=_pct(max_acc),
            threshold_max=_pct(thr),
            unit="%",
        ))
    else:
        rules.append(XRayRule(
            key="concentration_single_account",
            name="Concentrazione per conto / broker",
            category="Concentrazione",
            description="Avere oltre l'80% su un unico broker aumenta il rischio operativo.",
            status="info",
            unit="%",
        ))

    # 3. Esposizione crypto
    by_type = getattr(allocation, "by_type", [])
    crypto_pct_val = _alloc_pct(by_type, _lbl("CRYPTO"))
    thr = _DEF["concentration_crypto"]["max"]
    if crypto_pct_val is not None:
        status = "ok" if crypto_pct_val <= thr else ("warn" if crypto_pct_val <= thr * 2 else "error")
        rules.append(XRayRule(
            key="concentration_crypto",
            name="Esposizione criptovalute",
            category="Concentrazione",
            description=(
                "Le criptovalute sono asset ad alta volatilità. "
                "Una quota superiore al 10% del portafoglio introduce rischio significativo."
            ),
            status=status,
            actual=_pct(crypto_pct_val),
            threshold_max=_pct(thr),
            unit="%",
        ))
    else:
        rules.append(XRayRule(
            key="concentration_crypto",
            name="Esposizione criptovalute",
            category="Concentrazione",
            description="Una quota di crypto > 10% introduce rischio significativo.",
            status="ok",
            actual=0.0,
            threshold_max=_pct(thr),
            unit="%",
        ))

    # ── CATEGORIA: Asset Class ────────────────────────────────────────────────

    # 4. Azioni + ETF (equity)
    by_class = getattr(allocation, "by_asset_class", []) or []
    if by_class:
        equity_pct = _alloc_pct(by_class, "Azioni") or 0.0
    else:  # allocazione senza classi (compatibilità): azioni + ETF
        equity_pct = None
        for label in (_lbl("STOCK"), _lbl("ETF")):
            v = _alloc_pct(by_type, label)
            if v is not None:
                equity_pct = (equity_pct or 0) + v
    cfg = _DEF["asset_class_equity"]
    if equity_pct is not None:
        ok = cfg["min"] <= equity_pct <= cfg["max"]
        status = "ok" if ok else "warn"
        rules.append(XRayRule(
            key="asset_class_equity",
            name="Allocazione azioni + ETF azionari",
            category="Asset Class",
            description=(
                "Un portafoglio bilanciato mantiene l'esposizione azionaria (azioni ed ETF azionari, "
                f"esclusi gli ETF obbligazionari) tra il {int(cfg['min']*100)}% e il {int(cfg['max']*100)}% del totale."
            ),
            status=status,
            actual=_pct(equity_pct),
            threshold_min=_pct(cfg["min"]),
            threshold_max=_pct(cfg["max"]),
            unit="%",
        ))
    else:
        rules.append(XRayRule(
            key="asset_class_equity",
            name="Allocazione azioni + ETF azionari",
            category="Asset Class",
            description=f"Target: tra {int(cfg['min']*100)}% e {int(cfg['max']*100)}% del portafoglio.",
            status="info",
            threshold_min=_pct(cfg["min"]),
            threshold_max=_pct(cfg["max"]),
            unit="%",
        ))

    # 5. Obbligazioni (fixed income — inclusi BTP)
    bond_pct = (_alloc_pct(by_class, "Obbligazioni") or 0.0) if by_class else _alloc_pct(by_type, _lbl("BOND"))
    cfg = _DEF["asset_class_fixed_income"]
    if bond_pct is not None:
        ok = cfg["min"] <= bond_pct <= cfg["max"]
        status = "ok" if ok else "warn"
        rules.append(XRayRule(
            key="asset_class_fixed_income",
            name="Allocazione obbligazioni (inclusi BTP)",
            category="Asset Class",
            description=(
                "Le obbligazioni (titoli singoli ed ETF obbligazionari) ammortizzano la volatilità del portafoglio. "
                f"Target: tra {int(cfg['min']*100)}% e {int(cfg['max']*100)}%. "
                "I BTP beneficiano dell'aliquota agevolata al 12,5%."
            ),
            status=status,
            actual=_pct(bond_pct),
            threshold_min=_pct(cfg["min"]),
            threshold_max=_pct(cfg["max"]),
            unit="%",
        ))
    else:
        rules.append(XRayRule(
            key="asset_class_fixed_income",
            name="Allocazione obbligazioni (inclusi BTP)",
            category="Asset Class",
            description=f"Target: tra {int(cfg['min']*100)}% e {int(cfg['max']*100)}% del portafoglio.",
            status="info",
            threshold_min=_pct(cfg["min"]),
            threshold_max=_pct(cfg["max"]),
            unit="%",
        ))

    # 6. Valuta EUR
    by_fx = getattr(allocation, "by_currency_exposure", []) or []
    by_currency = by_fx or getattr(allocation, "by_currency", [])
    eur_pct = _alloc_pct(by_currency, "EUR")
    if eur_pct is None and by_currency:
        eur_pct = 0.0
    unknown_fx = _alloc_pct(by_fx, "Non dettagliata") if by_fx else None
    thr = _DEF["asset_class_currency_eur"]["min"]
    if eur_pct is not None:
        status = "ok" if eur_pct >= thr else "warn"
        rules.append(XRayRule(
            key="asset_class_currency_eur",
            name="Copertura valuta EUR",
            category="Asset Class",
            description=(
                "Per un investitore italiano, mantenere almeno il 30% in EUR riduce il rischio di cambio. "
                "Calcolata sulla valuta del sottostante (un ETF MSCI World quotato in EUR è esposto al dollaro), "
                "ETF con copertura valutaria contati in EUR."
                + (f" Quota non dettagliata dal look-through: {unknown_fx*100:.1f}%." if unknown_fx else "")
            ),
            status=status,
            actual=_pct(eur_pct),
            threshold_min=_pct(thr),
            unit="%",
        ))
    else:
        rules.append(XRayRule(
            key="asset_class_currency_eur",
            name="Copertura valuta EUR",
            category="Asset Class",
            description="Almeno il 30% del portafoglio dovrebbe essere in EUR.",
            status="info",
            threshold_min=_pct(thr),
            unit="%",
        ))

    # ── CATEGORIA: Fee ────────────────────────────────────────────────────────

    # 7. Rapporto commissioni
    total_fees = sum(
        t.fee for t in transactions
        if hasattr(t, "fee") and t.fee is not None
    )
    total_invested = sum(
        abs(t.quantity * t.price * t.exchange_rate)
        for t in transactions
        if hasattr(t, "type") and str(t.type).upper() in ("BUY", "SELL")
    )
    thr = _DEF["fee_ratio"]["max"]
    if total_invested > 0:
        ratio = total_fees / total_invested
        status = "ok" if ratio <= thr else ("warn" if ratio <= thr * 2 else "error")
        rules.append(XRayRule(
            key="fee_ratio",
            name="Rapporto commissioni / capitale",
            category="Fee",
            description=(
                "Le commissioni di negoziazione erodono il rendimento. "
                f"Un rapporto superiore al {thr*100:.1f}% indica costi eccessivi."
            ),
            status=status,
            actual=round(ratio * 100, 2),
            threshold_max=round(thr * 100, 2),
            unit="%",
        ))
    else:
        rules.append(XRayRule(
            key="fee_ratio",
            name="Rapporto commissioni / capitale",
            category="Fee",
            description=f"Le commissioni non dovrebbero superare il {thr*100:.1f}% del capitale negoziato.",
            status="info",
            unit="%",
        ))

    # ── CATEGORIA: Diversificazione geografica ────────────────────────────────

    # Geografia della sola parte azionaria (le obbligazioni in euro non sono "home bias")
    by_continent = getattr(allocation, "by_continent_equity", []) or getattr(allocation, "by_continent", [])

    # 8. Concentrazione per continente
    thr = _DEF["geo_diversification"]["max"]
    if by_continent:
        max_cont = _max_alloc_pct(by_continent)
        status = "ok" if (max_cont or 0) <= thr else "warn"
        rules.append(XRayRule(
            key="geo_diversification",
            name="Diversificazione geografica",
            category="Diversificazione geografica",
            description=(
                "Nessun continente dovrebbe rappresentare più del 70% della parte azionaria "
                "(look-through ETF incluso). Alta concentrazione = rischio paese/regione."
            ),
            status=status,
            actual=_pct(max_cont),
            threshold_max=_pct(thr),
            unit="%",
        ))
    else:
        rules.append(XRayRule(
            key="geo_diversification",
            name="Diversificazione geografica",
            category="Diversificazione geografica",
            description="Abilita l'enrichment degli asset per calcolare la distribuzione geografica.",
            status="info",
            unit="%",
        ))

    # 9. Home bias (Europa)
    thr = _DEF["geo_home_bias"]["max"]
    europe_pct = _alloc_pct(by_continent, "Europa")
    if europe_pct is not None:
        status = "ok" if europe_pct <= thr else "warn"
        rules.append(XRayRule(
            key="geo_home_bias",
            name="Home bias — Europa",
            category="Diversificazione geografica",
            description=(
                "Gli investitori tendono a sovrappesare il mercato domestico (home bias). "
                f"Una quota europea > {int(thr*100)}% dell'azionario potrebbe ridurre la diversificazione globale."
            ),
            status=status,
            actual=_pct(europe_pct),
            threshold_max=_pct(thr),
            unit="%",
        ))
    else:
        rules.append(XRayRule(
            key="geo_home_bias",
            name="Home bias — Europa",
            category="Diversificazione geografica",
            description=f"Quota Europa consigliata ≤ {int(thr*100)}% per evitare home bias.",
            status="info",
            threshold_max=_pct(thr),
            unit="%",
        ))

    # 10. Esposizione Italia (tutte le classi, BTP inclusi)
    thr = _DEF["geo_italy_exposure"]["max"]
    italy = getattr(allocation, "italy_exposure_pct", None)
    if italy is not None:
        italy_ratio = italy / 100
        rules.append(XRayRule(
            key="geo_italy_exposure",
            name="Esposizione Italia (BTP inclusi)",
            category="Diversificazione geografica",
            description=(
                "Peso dell'Italia sul totale del portafoglio: azioni, BTP e quota italiana degli ETF. "
                f"Oltre il {int(thr*100)}% il patrimonio è legato al rischio Paese a cui si è già esposti con "
                "reddito e immobili."
            ),
            status="ok" if italy_ratio <= thr else "warn",
            actual=_pct(italy_ratio),
            threshold_max=_pct(thr),
            unit="%",
        ))
    else:
        rules.append(XRayRule(
            key="geo_italy_exposure",
            name="Esposizione Italia (BTP inclusi)",
            category="Diversificazione geografica",
            description="Abilita l'enrichment degli asset per calcolare il peso dell'Italia.",
            status="info",
            threshold_max=_pct(thr),
            unit="%",
        ))

    # ── CATEGORIA: Liquidità ──────────────────────────────────────────────────

    # 11. Riserva di liquidità: monetario + obbligazioni con vita residua < 12 mesi
    cfg = _DEF["liquidity_emergency_fund"]
    thr_min = cfg["min"]
    liquid_value = 0.0
    for p in positions:
        info = asset_info.get(p.asset_id, {"type": p.asset_type, "name": p.name})
        value = p.current_value_eur or 0.0
        liquid_value += value * asset_class_weights(info).get(MONEY_MARKET, 0.0)
        if p.asset_type == "BOND":
            months = residual_months(maturities.get(p.asset_id) or maturity_from_name(p.name), today)
            if months is not None and 0 <= months <= cfg["max_maturity_months"]:
                liquid_value += value
    liquid_ratio = liquid_value / total_value if total_value > 0 else 0.0
    desc = (
        f"Almeno il {thr_min*100:.0f}% in strumenti liquidi e a basso rischio: fondi monetari e obbligazioni con "
        f"vita residua inferiore a {cfg['max_maturity_months']} mesi (es. BOT). Un BTP a lunga scadenza non è "
        "liquidità. Il saldo di cassa dei conti non è ancora tracciato."
    )
    if total_value > 0:
        rules.append(XRayRule(
            key="liquidity_emergency_fund",
            name="Riserva di liquidità / fondo emergenza",
            category="Liquidità",
            description=desc,
            status="ok" if liquid_ratio >= thr_min else "warn",
            actual=_pct(liquid_ratio),
            threshold_min=_pct(thr_min),
            unit="%",
        ))
    else:
        rules.append(XRayRule(
            key="liquidity_emergency_fund",
            name="Riserva di liquidità / fondo emergenza",
            category="Liquidità",
            description=desc,
            status="info",
            unit="%",
        ))

    # ── Score ─────────────────────────────────────────────────────────────────
    ok_count = sum(1 for r in rules if r.status == "ok")
    total = len(rules)
    score = round(ok_count / total * 100) if total > 0 else 0

    return XRayResponse(
        rules=rules,
        score=score,
        rules_total=total,
        rules_ok=ok_count,
    )
