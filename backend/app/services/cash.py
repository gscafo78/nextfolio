"""Saldi di cassa dei conti (liquidità).

Ogni conto ha uno storico di saldi per data (``AccountBalance``); il saldo
corrente è quello con la data più recente. I saldi sono nella valuta del conto
e vengono convertiti in EUR al cambio corrente.

La liquidità entra nel valore totale, nell'allocazione (classe "Monetario") e
nella regola X-Ray sulla riserva di liquidità, ma non nel TWRR: servirebbero
versamenti e prelievi sul conto, che Nextfolio non registra.
"""
from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.account_balance import AccountBalance

logger = logging.getLogger(__name__)


@dataclass
class CashBalance:
    account_id: int
    account_name: str
    currency: str
    balance: float            # valuta del conto
    date: datetime.date
    value_eur: float          # convertito al cambio corrente


async def _eur_rate(currency: str) -> float | None:
    if (currency or "EUR").upper() == "EUR":
        return 1.0
    try:
        from app.services.market_data.updater import _cached_eur_rate
        return await _cached_eur_rate(currency)
    except Exception as e:  # pragma: no cover - dipende dalla rete
        logger.warning("Cambio %s→EUR non disponibile per il saldo di cassa: %s", currency, e)
        return None


async def latest_balances(db: AsyncSession, user_id: int, account_id: int | None = None) -> list[CashBalance]:
    """Saldo più recente di ogni conto dell'utente che ne ha almeno uno."""
    latest = (
        select(AccountBalance.account_id, func.max(AccountBalance.date).label("d"))
        .join(Account, Account.id == AccountBalance.account_id)
        .where(Account.user_id == user_id)
        .group_by(AccountBalance.account_id)
        .subquery()
    )
    stmt = (
        select(AccountBalance, Account)
        .join(latest, (latest.c.account_id == AccountBalance.account_id) & (latest.c.d == AccountBalance.date))
        .join(Account, Account.id == AccountBalance.account_id)
        .order_by(Account.name)
    )
    if account_id is not None:
        stmt = stmt.where(Account.id == account_id)
    out: list[CashBalance] = []
    for bal, acc in (await db.execute(stmt)).all():
        rate = await _eur_rate(acc.currency)
        if rate is None:
            continue
        out.append(CashBalance(acc.id, acc.name, acc.currency, bal.balance, bal.date, bal.balance * rate))
    return out


def total_cash_eur(balances: list[CashBalance]) -> float:
    return sum(b.value_eur for b in balances)


async def set_balance(db: AsyncSession, account: Account, date: datetime.date, balance: float) -> AccountBalance:
    """Inserisce o sostituisce il saldo del conto alla data (commit incluso)."""
    if date > datetime.date.today():
        raise ValueError("La data del saldo non può essere futura")
    row = (await db.execute(
        select(AccountBalance).where(AccountBalance.account_id == account.id, AccountBalance.date == date)
    )).scalar_one_or_none()
    if row is None:
        row = AccountBalance(account_id=account.id, date=date, balance=balance)
        db.add(row)
    else:
        row.balance = balance
    await db.commit()
    await db.refresh(row)
    return row


async def balance_history(db: AsyncSession, account_id: int) -> list[AccountBalance]:
    return list((await db.execute(
        select(AccountBalance).where(AccountBalance.account_id == account_id).order_by(AccountBalance.date.desc())
    )).scalars())
