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


def parse_csv(content: str, broker: BrokerFormat) -> list[dict[str, Any]]:
    parsers = {
        BrokerFormat.FINECO: parse_fineco,
        BrokerFormat.DIRECTA: parse_directa,
        BrokerFormat.DEGIRO: parse_degiro,
    }
    parser = parsers.get(broker)
    if not parser:
        raise ValueError(f"Formato broker non supportato: {broker}")
    return parser(content)
