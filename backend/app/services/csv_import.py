"""
Parser CSV per i principali broker italiani.
Ogni parser restituisce una lista di dict pronti per creare TransactionCreate.
"""

import csv
import io
from datetime import date, datetime
from enum import Enum
from typing import Any

from app.models.transaction import TransactionType


class BrokerFormat(str, Enum):
    FINECO = "fineco"
    DIRECTA = "directa"
    DEGIRO = "degiro"
    IBKR = "ibkr"
    GENERIC = "generic"


def _parse_date(s: str, fmt: str) -> date:
    return datetime.strptime(s.strip(), fmt).date()


def _parse_float(s: str) -> float:
    return float(s.strip().replace(".", "").replace(",", ".").replace("€", "").strip() or "0")


def parse_fineco(content: str) -> list[dict[str, Any]]:
    """
    Formato Fineco (estratto conto CSV):
    Data;Descrizione;Divisa;Importo;Tipo;Titolo;ISIN;Quantità;Prezzo;Commissioni
    """
    rows = []
    reader = csv.DictReader(io.StringIO(content), delimiter=";")
    for row in reader:
        tipo = row.get("Tipo", "").upper()
        tx_type = {
            "BUY": TransactionType.BUY,
            "ACQUISTO": TransactionType.BUY,
            "SELL": TransactionType.SELL,
            "VENDITA": TransactionType.SELL,
            "DIVIDEND": TransactionType.DIVIDEND,
            "DIVIDENDO": TransactionType.DIVIDEND,
            "CEDOLA": TransactionType.COUPON,
        }.get(tipo)
        if not tx_type:
            continue

        rows.append({
            "date": _parse_date(row["Data"], "%d/%m/%Y"),
            "type": tx_type,
            "isin": row.get("ISIN", "").strip() or None,
            "symbol": row.get("Titolo", "").strip(),
            "quantity": abs(_parse_float(row.get("Quantità", "0"))),
            "price": _parse_float(row.get("Prezzo", "0")),
            "fee": abs(_parse_float(row.get("Commissioni", "0"))),
            "currency": row.get("Divisa", "EUR").strip(),
            "notes": row.get("Descrizione", "").strip(),
        })
    return rows


def parse_directa(content: str) -> list[dict[str, Any]]:
    """
    Formato Directa Plus:
    Data,Ora,Operazione,Titolo,ISIN,Quantità,Prezzo,Importo,Commissione,Valuta
    """
    rows = []
    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        op = row.get("Operazione", "").upper()
        tx_type = {
            "ACQUISTO": TransactionType.BUY,
            "VENDITA": TransactionType.SELL,
            "DIVIDENDO": TransactionType.DIVIDEND,
        }.get(op)
        if not tx_type:
            continue

        rows.append({
            "date": _parse_date(row["Data"], "%d/%m/%Y"),
            "type": tx_type,
            "isin": row.get("ISIN", "").strip() or None,
            "symbol": row.get("Titolo", "").strip(),
            "quantity": abs(_parse_float(row.get("Quantità", "0"))),
            "price": _parse_float(row.get("Prezzo", "0")),
            "fee": abs(_parse_float(row.get("Commissione", "0"))),
            "currency": row.get("Valuta", "EUR").strip(),
            "notes": None,
        })
    return rows


def parse_degiro(content: str) -> list[dict[str, Any]]:
    """
    Formato Degiro (transazioni.csv):
    Data,Ora,Prodotto,ISIN,Borsa,Numero,Prezzo,,,Valore locale,,,Valore,,Commissioni,,Totale,,ID ordine
    """
    rows = []
    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        quantity_raw = _parse_float(row.get("Numero", "0"))
        if quantity_raw == 0:
            continue
        tx_type = TransactionType.BUY if quantity_raw > 0 else TransactionType.SELL

        rows.append({
            "date": _parse_date(row["Data"], "%d-%m-%Y"),
            "type": tx_type,
            "isin": row.get("ISIN", "").strip() or None,
            "symbol": row.get("Prodotto", "").strip(),
            "quantity": abs(quantity_raw),
            "price": _parse_float(row.get("Prezzo", "0")),
            "fee": abs(_parse_float(row.get("Commissioni", "0"))),
            "currency": "EUR",
            "notes": None,
        })
    return rows


def parse_ibkr(content: str) -> list[dict[str, Any]]:
    """
    Interactive Brokers — Activity Statement CSV (Flex Query).

    Sezione attesa: "Trades" con header:
    DataDiscriminator,Asset Category,Currency,Symbol,Date/Time,Quantity,T. Price,
    C. Price,Proceeds,Comm/Fee,Basis,Realized P/L,MTM P/L,Code

    Oppure formato semplificato Flex Query con colonne:
    Symbol,Date/Time,Quantity,T. Price,C. Price,Proceeds,Comm/Fee,Code

    IBKR usa il campo "Code" per distinguere apertura (O) e chiusura (C).
    Dividendi sono nella sezione "Dividends":
    Currency,Date,Description,Amount
    """
    rows: list[dict[str, Any]] = []
    lines = content.splitlines()

    # IBKR Activity Statement ha sezioni separate da "Section,..."
    # oppure ogni riga inizia con il nome della sezione
    in_trades = False
    in_dividends = False
    trade_header: list[str] = []
    div_header: list[str] = []

    for line in lines:
        if not line.strip():
            continue

        parts = list(csv.reader([line]))[0]
        if not parts:
            continue

        first = parts[0].strip()

        # Rilevamento sezione
        if first == "Trades":
            if len(parts) > 1 and parts[1].strip().lower() == "header":
                trade_header = [p.strip() for p in parts[2:]]
                in_trades = True
                in_dividends = False
            elif in_trades and len(parts) > 1 and parts[1].strip().lower() == "data":
                data = dict(zip(trade_header, [p.strip() for p in parts[2:]]))
                try:
                    qty_raw = float(data.get("Quantity", "0").replace(",", ""))
                    price_raw = float(data.get("T. Price", data.get("T.Price", "0")).replace(",", ""))
                    comm_raw = abs(float(data.get("Comm/Fee", data.get("Comm.", "0")).replace(",", "")))
                    date_raw = data.get("Date/Time", data.get("DateTime", "")).split(",")[0].strip()
                    symbol = data.get("Symbol", "").strip()
                    currency = data.get("Currency", "USD").strip()

                    if not symbol or price_raw == 0:
                        continue

                    # Formato data IBKR: "2023-03-15" oppure "2023-03-15, 10:30:00"
                    tx_date = datetime.strptime(date_raw[:10], "%Y-%m-%d").date()
                    tx_type = TransactionType.BUY if qty_raw > 0 else TransactionType.SELL

                    rows.append({
                        "date": tx_date,
                        "type": tx_type,
                        "isin": None,
                        "symbol": symbol,
                        "quantity": abs(qty_raw),
                        "price": abs(price_raw),
                        "fee": comm_raw,
                        "currency": currency,
                        "notes": f"IBKR import",
                    })
                except (ValueError, KeyError):
                    continue
            continue

        if first == "Dividends":
            if len(parts) > 1 and parts[1].strip().lower() == "header":
                div_header = [p.strip() for p in parts[2:]]
                in_dividends = True
                in_trades = False
            elif in_dividends and len(parts) > 1 and parts[1].strip().lower() == "data":
                data = dict(zip(div_header, [p.strip() for p in parts[2:]]))
                try:
                    date_raw = data.get("Date", "").strip()
                    desc = data.get("Description", "").strip()
                    amount = float(data.get("Amount", "0").replace(",", ""))
                    currency = data.get("Currency", "USD").strip()

                    if amount <= 0 or not date_raw or date_raw == "Total":
                        continue

                    tx_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
                    # Symbol is extracted from description: "AAPL (US0378331005) Cash Dividend"
                    symbol = desc.split("(")[0].strip() if "(" in desc else desc.split()[0]

                    rows.append({
                        "date": tx_date,
                        "type": TransactionType.DIVIDEND,
                        "isin": None,
                        "symbol": symbol,
                        "quantity": 1.0,
                        "price": amount,
                        "fee": 0.0,
                        "currency": currency,
                        "notes": desc[:100],
                    })
                except (ValueError, KeyError):
                    continue
            continue

        # Reset su nuova sezione
        if first not in ("Trades", "Dividends"):
            if in_trades or in_dividends:
                in_trades = False
                in_dividends = False

    return rows


def parse_csv(content: str, broker: BrokerFormat) -> list[dict[str, Any]]:
    parsers = {
        BrokerFormat.FINECO: parse_fineco,
        BrokerFormat.DIRECTA: parse_directa,
        BrokerFormat.DEGIRO: parse_degiro,
        BrokerFormat.IBKR: parse_ibkr,
    }
    parser = parsers.get(broker)
    if not parser:
        raise ValueError(f"Formato broker non supportato: {broker}")
    return parser(content)
