import csv
import io
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel

log = logging.getLogger(__name__)

EXCLUDED_TYPES = {"Tesouro IGPM+ com Juros Semestrais"}

NUMERIC_COLUMNS = ("Taxa Compra Manha", "Taxa Venda Manha", "PU Compra Manha", "PU Venda Manha")


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
    return Decimal(text.strip().replace(".", "").replace(",", "."))


def _safe_date(text: str | None) -> date | None:
    try:
        return _date(text or "")
    except ValueError:
        return None


def parse_latest(csv_text: str) -> list[TesouroQuote]:
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")), delimiter=";")
    rows = []
    for r in reader:
        if not r.get("Tipo Titulo"):
            continue
        base = _safe_date(r.get("Data Base"))
        if base is None:
            log.warning("Tesouro: linha com Data Base inválida ignorada: %s", r)
            continue
        rows.append((base, r))
    if not rows:
        return []
    latest = max(b for b, _ in rows)
    quotes: list[TesouroQuote] = []
    for base, r in rows:
        if base != latest or r["Tipo Titulo"].strip() in EXCLUDED_TYPES:
            continue
        if any(not (r.get(c) or "").strip() for c in NUMERIC_COLUMNS):
            continue  # linha sem taxa/PU: descarta em vez de virar 0
        try:
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
        except (ValueError, InvalidOperation, KeyError):
            log.warning("Tesouro: linha malformada ignorada: %s", r)
    return quotes
