import csv
import io
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

EXCLUDED_TYPES = {"Tesouro IGPM+ com Juros Semestrais"}


class TesouroQuote(BaseModel):
    tipo: str
    vencimento: date
    data_base: date
    taxa_compra: Decimal  # fração
    taxa_venda: Decimal  # fração
    pu_compra: Decimal
    pu_venda: Decimal


def decode_csv(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _date(text: str) -> date:
    return datetime.strptime(text.strip(), "%d/%m/%Y").date()


def _num(text: str) -> Decimal:
    cleaned = text.strip().replace(".", "").replace(",", ".")
    return Decimal(cleaned) if cleaned else Decimal(0)


def parse_latest(csv_text: str) -> list[TesouroQuote]:
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("﻿")), delimiter=";")
    rows = [r for r in reader if r.get("Tipo Titulo")]
    if not rows:
        return []
    latest = max(_date(r["Data Base"]) for r in rows)
    quotes: list[TesouroQuote] = []
    for r in rows:
        if _date(r["Data Base"]) != latest or r["Tipo Titulo"].strip() in EXCLUDED_TYPES:
            continue
        pu_compra = _num(r["PU Compra Manha"])
        if pu_compra <= 0:
            continue
        quotes.append(
            TesouroQuote(
                tipo=r["Tipo Titulo"].strip(),
                vencimento=_date(r["Data Vencimento"]),
                data_base=latest,
                taxa_compra=_num(r["Taxa Compra Manha"]) / 100,
                taxa_venda=_num(r["Taxa Venda Manha"]) / 100,
                pu_compra=pu_compra,
                pu_venda=_num(r["PU Venda Manha"]),
            )
        )
    return quotes
