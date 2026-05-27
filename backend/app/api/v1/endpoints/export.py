import json
import uuid
from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.services.portfolio.positions import calculate_positions

router = APIRouter(prefix="/portfolio", tags=["export"])

_HDR_FILL = PatternFill("solid", fgColor="1D4ED8")
_HDR_FONT = Font(color="FFFFFF", bold=True)
_ALT_FILL = PatternFill("solid", fgColor="EFF6FF")


def _style_header(ws) -> None:
    for cell in ws[1]:
        cell.fill = _HDR_FILL
        cell.font = _HDR_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 18


def _autowidth(ws, max_col_width: int = 42) -> None:
    for col in ws.columns:
        width = max((len(str(cell.value or "")) for cell in col), default=8)
        ws.column_dimensions[col[0].column_letter].width = min(width + 2, max_col_width)


def _zebra(ws, start_row: int = 2) -> None:
    for i, row in enumerate(ws.iter_rows(min_row=start_row)):
        if i % 2 == 0:
            for cell in row:
                cell.fill = _ALT_FILL


@router.get("/export")
async def export_portfolio(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Esporta posizioni e transazioni in formato Excel (.xlsx)."""
    stmt = (
        select(Transaction)
        .join(Transaction.account)
        .where(Transaction.account.has(user_id=current_user.id))
        .options(
            selectinload(Transaction.asset),
            selectinload(Transaction.account),
        )
        .order_by(Transaction.date.asc(), Transaction.id.asc())
    )
    result = await db.execute(stmt)
    transactions = result.scalars().all()

    wb = openpyxl.Workbook()

    # ── Sheet 1: Transazioni ─────────────────────────────────────────────────
    ws_tx = wb.active
    ws_tx.title = "Transazioni"
    ws_tx.append([
        "Data", "Tipo", "Simbolo", "Nome asset", "ISIN",
        "Quantità", "Prezzo", "Valuta", "Tasso cambio",
        "Commissioni", "Totale EUR", "Conto", "Note",
    ])
    _style_header(ws_tx)

    asset_map: dict[int, object] = {}
    for tx in transactions:
        asset_map[tx.asset_id] = tx.asset
        total_eur = round(tx.quantity * tx.price * tx.exchange_rate + tx.fee, 2)
        ws_tx.append([
            tx.date.isoformat(),
            tx.type.value,
            tx.asset.symbol,
            tx.asset.name,
            tx.asset.isin or "",
            round(tx.quantity, 6),
            round(tx.price, 6),
            tx.price_currency,
            round(tx.exchange_rate, 6),
            round(tx.fee, 2),
            total_eur,
            tx.account.name,
            tx.notes or "",
        ])

    _zebra(ws_tx)
    _autowidth(ws_tx)

    # ── Sheet 2: Posizioni aperte ────────────────────────────────────────────
    ws_pos = wb.create_sheet("Posizioni")
    ws_pos.append([
        "Simbolo", "Nome", "Tipo", "ISIN", "Borsa",
        "Quantità", "PMC (EUR)", "Totale investito (EUR)", "P&L realizzato (EUR)",
    ])
    _style_header(ws_pos)

    positions = calculate_positions(list(transactions))
    for asset_id, pos in sorted(positions.items(), key=lambda kv: kv[0]):
        asset = asset_map.get(asset_id)
        if not asset:
            continue
        ws_pos.append([
            asset.symbol,
            asset.name,
            asset.type.value if hasattr(asset.type, "value") else str(asset.type),
            asset.isin or "",
            asset.exchange.value if hasattr(asset.exchange, "value") else str(asset.exchange),
            round(pos.quantity, 6),
            round(pos.pmc_eur, 4),
            round(pos.total_invested_eur, 2),
            round(pos.realized_pnl_eur, 2),
        ])

    _zebra(ws_pos)
    _autowidth(ws_pos)

    # ── Sheet 3: Info ────────────────────────────────────────────────────────
    ws_info = wb.create_sheet("Info")
    ws_info.append(["Campo", "Valore"])
    _style_header(ws_info)
    ws_info.append(["Data esportazione", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    ws_info.append(["Utente", current_user.email])
    ws_info.append(["Transazioni totali", len(transactions)])
    ws_info.append(["Posizioni aperte", len(positions)])
    ws_info.column_dimensions["A"].width = 26
    ws_info.column_dimensions["B"].width = 32

    # Return as streaming xlsx
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"nextfolio_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/ghostfolio")
async def export_ghostfolio(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Esporta il portafoglio in formato Ghostfolio v3.x (JSON).
    Compatibile con Ghostfolio import → Activities.
    """
    from app.models.account import Account

    stmt = (
        select(Transaction)
        .join(Transaction.account)
        .where(Transaction.account.has(user_id=current_user.id))
        .options(
            selectinload(Transaction.asset),
            selectinload(Transaction.account),
        )
        .order_by(Transaction.date.asc(), Transaction.id.asc())
    )
    result = await db.execute(stmt)
    transactions = list(result.scalars())

    accounts_result = await db.execute(
        select(Account).where(Account.user_id == current_user.id)
    )
    accounts = {a.id: a for a in accounts_result.scalars()}

    # Mappa tipo transazione → Ghostfolio type
    TX_TYPE_MAP = {
        TransactionType.BUY: "BUY",
        TransactionType.SELL: "SELL",
        TransactionType.DIVIDEND: "DIVIDEND",
        TransactionType.COUPON: "DIVIDEND",
        TransactionType.INTEREST: "INTEREST",
        TransactionType.FEE: "FEE",
    }

    # Costruisci la lista activities
    activities = []
    asset_profiles: dict[str, dict] = {}
    gf_accounts: dict[int, dict] = {}

    for tx in transactions:
        asset = tx.asset
        acc = accounts.get(tx.account_id)
        if not asset or not acc:
            continue

        gf_type = TX_TYPE_MAP.get(tx.type)
        if gf_type is None:
            continue

        # Aggiungi account se non già presente
        if tx.account_id not in gf_accounts:
            acc_gf_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"nextfolio-account-{tx.account_id}"))
            gf_accounts[tx.account_id] = {
                "id": acc_gf_id,
                "name": acc.name,
                "currency": acc.currency or "EUR",
                "platformId": None,
            }

        acc_gf_id = gf_accounts[tx.account_id]["id"]

        # Aggiungi asset profile se non già presente
        sym = asset.symbol
        if sym not in asset_profiles:
            asset_profiles[sym] = {
                "symbol": sym,
                "name": asset.name,
                "currency": asset.currency,
                "comment": asset.isin or "",
                "assetClass": {
                    "STOCK": "EQUITY",
                    "ETF": "EQUITY",
                    "BOND": "FIXED_INCOME",
                    "CRYPTO": "CRYPTOCURRENCY",
                    "COMMODITY": "COMMODITY",
                    "REIT": "REAL_ESTATE",
                }.get(asset.type.value if hasattr(asset.type, "value") else str(asset.type), "EQUITY"),
                "assetSubClass": {
                    "ETF": "ETF",
                    "STOCK": "STOCK",
                    "BOND": "BOND",
                }.get(asset.type.value if hasattr(asset.type, "value") else str(asset.type), "STOCK"),
                "dataSource": "YAHOO",
                "marketData": [],
            }

        activities.append({
            "accountId": acc_gf_id,
            "comment": tx.notes or "",
            "currency": tx.price_currency or asset.currency,
            "dataSource": "YAHOO",
            "date": datetime.combine(tx.date, datetime.min.time()).replace(tzinfo=timezone.utc).isoformat(),
            "fee": tx.fee,
            "quantity": tx.quantity,
            "symbol": sym,
            "type": gf_type,
            "unitPrice": tx.price,
        })

    gf_export = {
        "meta": {
            "date": datetime.now(timezone.utc).isoformat(),
            "version": "v3",
        },
        "accounts": list(gf_accounts.values()),
        "activities": activities,
        "assetProfiles": list(asset_profiles.values()),
    }

    filename = f"nextfolio_ghostfolio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    content = json.dumps(gf_export, ensure_ascii=False, indent=2)
    return StreamingResponse(
        iter([content]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/nextfolio")
async def export_nextfolio(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Esporta tutti i dati in formato Nextfolio JSON.
    Il file è asettico: non contiene email, user_id o altri dati personali.
    Gli ID interni sono sostituiti con riferimenti posizionali autosufficienti.
    """
    from app.models.account import Account

    accounts_result = await db.execute(
        select(Account).where(Account.user_id == current_user.id).order_by(Account.id)
    )
    accounts = list(accounts_result.scalars())

    stmt = (
        select(Transaction)
        .join(Transaction.account)
        .where(Transaction.account.has(user_id=current_user.id))
        .options(
            selectinload(Transaction.asset),
            selectinload(Transaction.account),
        )
        .order_by(Transaction.date.asc(), Transaction.id.asc())
    )
    result = await db.execute(stmt)
    transactions = list(result.scalars())

    # Raccoglie gli asset unici nell'ordine in cui compaiono
    assets_seen: dict[int, object] = {}
    for tx in transactions:
        if tx.asset_id not in assets_seen:
            assets_seen[tx.asset_id] = tx.asset

    # Mappa DB id → id posizionale nel file (1-based)
    account_id_map = {a.id: idx + 1 for idx, a in enumerate(accounts)}
    asset_id_map = {a_id: idx + 1 for idx, a_id in enumerate(assets_seen)}

    def _val(obj, attr: str) -> str:
        v = getattr(obj, attr, None)
        return v.value if hasattr(v, "value") else (str(v) if v is not None else "")

    payload = {
        "meta": {
            "version": "1",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "app": "nextfolio",
        },
        "accounts": [
            {
                "id": account_id_map[a.id],
                "name": a.name,
                "type": _val(a, "type"),
                "broker": a.broker or "",
                "currency": a.currency or "EUR",
                "url": a.url or "",
            }
            for a in accounts
        ],
        "assets": [
            {
                "id": asset_id_map[a_id],
                "symbol": asset.symbol,
                "name": asset.name,
                "isin": asset.isin or "",
                "type": _val(asset, "type"),
                "exchange": _val(asset, "exchange"),
                "currency": asset.currency,
                "sector": asset.sector or "",
            }
            for a_id, asset in assets_seen.items()
        ],
        "transactions": [
            {
                "account_id": account_id_map[tx.account_id],
                "asset_id": asset_id_map[tx.asset_id],
                "type": _val(tx, "type"),
                "date": tx.date.isoformat(),
                "quantity": float(tx.quantity),
                "price": float(tx.price),
                "fee": float(tx.fee),
                "price_currency": tx.price_currency,
                "exchange_rate": float(tx.exchange_rate),
                "fee_currency": tx.fee_currency,
                "notes": tx.notes or "",
            }
            for tx in transactions
            if tx.account_id in account_id_map and tx.asset_id in asset_id_map
        ],
    }

    filename = f"nextfolio_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    return StreamingResponse(
        iter([content]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
