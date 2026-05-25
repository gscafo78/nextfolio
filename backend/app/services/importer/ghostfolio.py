"""
Parser e executor per il formato di esportazione Ghostfolio v3.x.

Flusso:
  1. preview(raw_json, db, user_id) → GhostfolioPreview
     Analizza il file senza scrivere nulla; rileva account/asset da risolvere.
  2. execute(raw_json, resolutions, db, user_id) → ImportResult
     Crea account/asset/transazioni/storico-prezzi in base alle decisioni utente.
"""
import re
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account, AccountType
from app.models.asset import Asset, AssetType, Exchange, PriceHistory
from app.models.transaction import Transaction, TransactionType
from app.services.fx import get_exchange_rate

# ── helpers ──────────────────────────────────────────────────────────────────

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

NULL_ACCOUNT_KEY = "__null__"


def _is_uuid(s: str) -> bool:
    return bool(_UUID_RE.match(s))


def _detect_type(profile: dict, symbol: str) -> str:
    ac = (profile.get("assetClass") or "").upper()
    sc = (profile.get("assetSubClass") or "").upper()
    if ac == "FIXED_INCOME" or sc == "BOND":
        return AssetType.BOND.value
    if ac == "CRYPTOCURRENCY":
        return AssetType.CRYPTO.value
    if ac == "COMMODITY":
        return AssetType.COMMODITY.value
    if sc in ("ETF", "MUTUALFUND"):
        return AssetType.ETF.value
    if ac == "EQUITY":
        return AssetType.STOCK.value
    # Euristica dal suffisso del ticker
    sym = symbol.upper()
    for suf in (".MI", ".DE", ".PA", ".L", ".AX", ".TO"):
        if sym.endswith(suf):
            return AssetType.ETF.value
    return AssetType.OTHER.value


def _detect_exchange(symbol: str) -> str:
    sym = symbol.upper()
    if sym.endswith(".MI"):
        return Exchange.MIL.value
    if sym.endswith(".DE"):
        return Exchange.XETRA.value
    if sym.endswith(".PA"):
        return Exchange.OTHER.value
    if sym.endswith(".L"):
        return Exchange.OTHER.value
    return Exchange.OTHER.value


def _gf_to_tx_type(gf_type: str) -> TransactionType | None:
    mapping = {
        "BUY": TransactionType.BUY,
        "SELL": TransactionType.SELL,
        "DIVIDEND": TransactionType.DIVIDEND,
        "INTEREST": TransactionType.INTEREST,
        "FEE": TransactionType.FEE,
        "ITEM": None,  # ignorato
    }
    return mapping.get(gf_type.upper())


def _parse_date(s: str) -> date:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).date()


# ── Preview ───────────────────────────────────────────────────────────────────

async def preview(raw: dict, db: AsyncSession, user_id: int) -> dict:
    """
    Analizza il Ghostfolio JSON e restituisce un piano di risoluzione.
    Nulla viene scritto nel DB.
    """
    activities: list[dict] = raw.get("activities", [])
    asset_profiles: dict[str, dict] = {
        p["symbol"]: p for p in raw.get("assetProfiles", [])
    }
    gf_accounts: list[dict] = raw.get("accounts", [])
    platforms: dict[str, dict] = {p["id"]: p for p in raw.get("platforms", [])}

    # ── account presenti nel file ──────────────────────────────────────────
    gf_account_map: dict[str, dict] = {a["id"]: a for a in gf_accounts}

    # Carica account esistenti dell'utente
    res = await db.execute(select(Account).where(Account.user_id == user_id))
    existing_accounts = list(res.scalars())
    existing_by_name = {a.name.lower(): a for a in existing_accounts}

    # Quante transazioni per account (incluso null)
    tx_by_account: dict[str, int] = {}
    for act in activities:
        key = act.get("accountId") or NULL_ACCOUNT_KEY
        tx_by_account[key] = tx_by_account.get(key, 0) + 1

    account_items = []
    seen_accounts: set[str] = set()
    for act in activities:
        key = act.get("accountId") or NULL_ACCOUNT_KEY
        if key in seen_accounts:
            continue
        seen_accounts.add(key)

        if key == NULL_ACCOUNT_KEY:
            account_items.append({
                "ghostfolio_id": NULL_ACCOUNT_KEY,
                "name": "(nessun conto)",
                "currency": "EUR",
                "broker": None,
                "is_null": True,
                "transaction_count": tx_by_account[key],
                "existing_match": None,
            })
        else:
            gf_acc = gf_account_map.get(key, {})
            name = gf_acc.get("name", key)
            currency = gf_acc.get("currency", "EUR")
            platform_id = gf_acc.get("platformId")
            broker = platforms.get(platform_id, {}).get("name") if platform_id else None

            match = existing_by_name.get(name.lower())
            account_items.append({
                "ghostfolio_id": key,
                "name": name,
                "currency": currency,
                "broker": broker,
                "is_null": False,
                "transaction_count": tx_by_account.get(key, 0),
                "existing_match": {"id": match.id, "name": match.name} if match else None,
            })

    # ── asset nel file ────────────────────────────────────────────────────
    # Carica asset esistenti nel DB
    res2 = await db.execute(select(Asset))
    db_assets = list(res2.scalars())
    db_by_symbol = {a.symbol.upper(): a for a in db_assets}

    tx_by_symbol: dict[str, int] = {}
    types_by_symbol: dict[str, set] = {}
    for act in activities:
        sym = act.get("symbol", "")
        tx_by_symbol[sym] = tx_by_symbol.get(sym, 0) + 1
        types_by_symbol.setdefault(sym, set()).add(act.get("type", ""))

    asset_items = []
    seen_symbols: set[str] = set()
    for act in activities:
        sym = act.get("symbol", "")
        if sym in seen_symbols:
            continue
        seen_symbols.add(sym)

        profile = asset_profiles.get(sym, {})
        is_uuid = _is_uuid(sym)
        name = profile.get("name") or profile.get("comment") or sym
        currency = profile.get("currency") or act.get("currency", "EUR")
        data_source = profile.get("dataSource") or act.get("dataSource", "YAHOO")
        price_history = profile.get("marketData", [])

        suggested_type = _detect_type(profile, sym)
        suggested_exchange = _detect_exchange(sym)
        if is_uuid and (profile.get("assetClass") == "FIXED_INCOME" or
                        profile.get("assetSubClass") == "BOND"):
            suggested_exchange = Exchange.MOT.value

        db_match = db_by_symbol.get(sym.upper())
        # Cerca anche per nome se uuid
        if not db_match and is_uuid and name:
            for a in db_assets:
                if a.name.lower() == name.lower():
                    db_match = a
                    break

        # Suggerimenti di ricerca (max 3)
        suggestions = []
        if not db_match and not is_uuid:
            q = sym.split(".")[0].upper()
            suggestions = [
                {"id": a.id, "symbol": a.symbol, "name": a.name, "type": a.type.value}
                for a in db_assets
                if q in a.symbol.upper() or q in a.name.upper()
            ][:3]

        asset_items.append({
            "ghostfolio_symbol": sym,
            "name": name,
            "currency": currency,
            "data_source": data_source,
            "is_uuid": is_uuid,
            "has_price_history": bool(price_history),
            "price_history_count": len(price_history),
            "transaction_count": tx_by_symbol[sym],
            "tx_types": list(types_by_symbol[sym]),
            "suggested_type": suggested_type,
            "suggested_exchange": suggested_exchange,
            "db_match": {"id": db_match.id, "symbol": db_match.symbol, "name": db_match.name, "type": db_match.type.value} if db_match else None,
            "suggestions": suggestions,
        })

    return {
        "accounts": account_items,
        "assets": asset_items,
        "total_transactions": len(activities),
    }


# ── Execute ───────────────────────────────────────────────────────────────────

async def execute(raw: dict, resolutions: dict, db: AsyncSession, user_id: int) -> dict:
    """
    Esegue l'import: crea/mappa account, asset, storico prezzi e transazioni.

    resolutions = {
      "accounts": [{"ghostfolio_id", "action": "create"|"use_existing", "existing_id", "name", "broker", "currency"}],
      "assets":   [{"ghostfolio_symbol", "action": "create"|"use_existing"|"skip", "existing_id",
                    "name", "symbol", "type", "exchange", "currency", "isin", "import_price_history"}]
    }
    """
    activities: list[dict] = raw.get("activities", [])
    asset_profiles: dict[str, dict] = {p["symbol"]: p for p in raw.get("assetProfiles", [])}

    # ── 1. Risolvi account ────────────────────────────────────────────────
    account_id_map: dict[str, int] = {}  # ghostfolio_id → nextfolio account id

    for ar in resolutions.get("accounts", []):
        gf_id = ar["ghostfolio_id"]
        if ar["action"] == "use_existing":
            account_id_map[gf_id] = int(ar["existing_id"])
        elif ar["action"] == "create":
            acc = Account(
                user_id=user_id,
                name=ar["name"],
                type=AccountType.BROKERAGE,
                broker=ar.get("broker"),
                currency=ar.get("currency", "EUR"),
            )
            db.add(acc)
            await db.flush()
            account_id_map[gf_id] = acc.id

    accounts_created = sum(1 for ar in resolutions.get("accounts", []) if ar["action"] == "create")

    # ── 2. Risolvi asset e importa price history ──────────────────────────
    asset_id_map: dict[str, int] = {}   # ghostfolio_symbol → nextfolio asset id
    skipped_symbols: set[str] = set()
    assets_created = 0
    price_history_inserted = 0

    for ar in resolutions.get("assets", []):
        sym = ar["ghostfolio_symbol"]
        if ar["action"] == "skip":
            skipped_symbols.add(sym)
            continue
        if ar["action"] == "use_existing":
            asset_id_map[sym] = int(ar["existing_id"])
            continue
        # create — usa ISIN come symbol di fallback se non c'è un ticker
        explicit_symbol = (ar.get("symbol") or "").strip()
        isin = (ar.get("isin") or "").strip() or None
        wkn = (ar.get("wkn") or "").strip() or None
        derived_symbol = explicit_symbol or isin or wkn or sym
        asset = Asset(
            symbol=derived_symbol,
            name=ar["name"],
            type=AssetType(ar["type"]),
            exchange=Exchange(ar.get("exchange", Exchange.OTHER.value)),
            currency=ar.get("currency", "EUR"),
            isin=isin,
            wkn=wkn,
        )
        db.add(asset)
        await db.flush()
        asset_id_map[sym] = asset.id
        assets_created += 1

        # Importa storico prezzi se richiesto
        if ar.get("import_price_history", False):
            profile = asset_profiles.get(sym, {})
            market_data = profile.get("marketData", [])
            for entry in market_data:
                try:
                    d = _parse_date(entry["date"])
                    price = float(entry["marketPrice"])
                    ph = PriceHistory(asset_id=asset.id, date=d, close=price)
                    db.add(ph)
                    price_history_inserted += 1
                except Exception:
                    continue
            await db.flush()

    # ── 3. Crea transazioni ───────────────────────────────────────────────
    # Cache FX rates per (currency, date) per evitare chiamate ripetute
    fx_cache: dict[tuple, float] = {}

    async def get_fx(currency: str, on_date: date) -> float:
        if currency == "EUR":
            return 1.0
        key = (currency, on_date)
        if key not in fx_cache:
            try:
                fx_cache[key] = await get_exchange_rate(currency, "EUR", on_date)
            except Exception:
                fx_cache[key] = 1.0
        return fx_cache[key]

    transactions_created = 0
    transactions_skipped = 0
    errors: list[str] = []

    for act in activities:
        sym = act.get("symbol", "")
        if sym in skipped_symbols:
            transactions_skipped += 1
            continue

        asset_id = asset_id_map.get(sym)
        if asset_id is None:
            transactions_skipped += 1
            errors.append(f"Asset non risolto per symbol '{sym}' ({act.get('type')})")
            continue

        gf_account_id = act.get("accountId") or NULL_ACCOUNT_KEY
        account_id = account_id_map.get(gf_account_id)
        if account_id is None:
            transactions_skipped += 1
            errors.append(f"Conto non risolto per account_id '{gf_account_id}'")
            continue

        tx_type = _gf_to_tx_type(act.get("type", ""))
        if tx_type is None:
            transactions_skipped += 1
            continue

        try:
            tx_date = _parse_date(act["date"])
            quantity = float(act.get("quantity", 1))
            price = float(act.get("unitPrice", 0))
            currency = act.get("currency", "EUR")
            fee = float(act.get("fee", 0))
            comment = act.get("comment") or None

            exchange_rate = await get_fx(currency, tx_date)

            tx = Transaction(
                account_id=account_id,
                asset_id=asset_id,
                type=tx_type,
                date=tx_date,
                quantity=quantity,
                price=price,
                price_currency=currency,
                exchange_rate=exchange_rate,
                fee=fee,
                fee_currency="EUR",
                notes=comment,
            )
            db.add(tx)
            transactions_created += 1
        except Exception as e:
            errors.append(f"Errore transazione {act.get('type')} {sym} {act.get('date')}: {e}")
            transactions_skipped += 1

    await db.commit()

    return {
        "accounts_created": accounts_created,
        "assets_created": assets_created,
        "price_history_inserted": price_history_inserted,
        "transactions_created": transactions_created,
        "transactions_skipped": transactions_skipped,
        "errors": errors[:20],  # max 20 errori
    }
