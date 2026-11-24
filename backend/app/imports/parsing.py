"""Parsers de texto de print (borda): % vira fração aqui e só aqui."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta
from decimal import Decimal

from app.domain.products.base import Amortizacao, Indexer, Periodicidade

_NUM = r"(\d+(?:[.,]\d+)?)"
_PCT_CDI = re.compile(_NUM + r"\s*%\s*(?:do\s+)?CDI\b", re.I)
_CDI_MAIS = re.compile(r"\bCDI\s*\+\s*" + _NUM + r"\s*%", re.I)
_IPCA_MAIS = re.compile(r"\bIPC(?:-?A)?\s*\+\s*" + _NUM + r"\s*%", re.I)
_PRE = re.compile(_NUM + r"\s*%")

_MESES = {m: i + 1 for i, m in enumerate(
    ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"])}
_DATE_NUM = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?![\d/])")
_DATE_TXT = re.compile(r"(?<!\d)(\d{1,2})\s+([A-Za-zç]{3})\.?\s+(\d{4})(?!\d)")
_MONEY = re.compile(r"(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})(?!\d)")
_D_MAIS = re.compile(r"\bD\s*\+\s*(\d+)\b", re.I)
_N_DIAS = re.compile(r"\b(\d+)\s*dias?\b", re.I)


def _fraction(num: str) -> Decimal:
    return (Decimal(num.replace(",", ".")) / 100).normalize()


def plain(texto: str | None) -> str:
    """Sem acento, minúsculo e sem espaços nas pontas; None vira vazio."""
    nfd = unicodedata.normalize("NFD", (texto or "").strip())
    return "".join(c for c in nfd if not unicodedata.combining(c)).lower()


def parse_rate(texto: str) -> tuple[Indexer, Decimal] | None:
    if m := _CDI_MAIS.search(texto):
        return Indexer.CDI_MAIS, _fraction(m.group(1))
    if m := _IPCA_MAIS.search(texto):
        return Indexer.IPCA_MAIS, _fraction(m.group(1))
    if m := _PCT_CDI.search(texto):
        return Indexer.PCT_CDI, _fraction(m.group(1))
    if m := _PRE.search(texto):
        return Indexer.PRE, _fraction(m.group(1))
    return None


def parse_date(texto: str) -> date | None:
    try:
        if m := _DATE_NUM.search(texto):
            dia, mes, ano = int(m.group(1)), int(m.group(2)), m.group(3)
            return date(int(ano) + (2000 if len(ano) == 2 else 0), mes, dia)
        if m := _DATE_TXT.search(texto):
            mes = _MESES.get(plain(m.group(2)))
            if mes:
                return date(int(m.group(3)), mes, int(m.group(1)))
    except ValueError:
        return None
    return None


def parse_money(texto: str) -> Decimal | None:
    m = _MONEY.search(texto)
    if not m:
        return None
    return Decimal(m.group(1).replace(".", "") + "." + m.group(2))


def parse_carencia(texto: str, registro: date) -> date:
    if (d := parse_date(texto)) is not None:
        return d
    m = _D_MAIS.search(texto) or _N_DIAS.search(texto)
    if m:
        return registro + timedelta(days=int(m.group(1)))
    raise ValueError(f"Carência não reconhecida: {texto}")


def parse_periodicidade(texto: str | None) -> Periodicidade | None:
    t = plain(texto or "")
    for prefixo, valor in (
        ("mensa", "MENSAL"), ("trimestral", "TRIMESTRAL"),
        ("semestral", "SEMESTRAL"), ("anual", "ANUAL"),
    ):
        if prefixo in t:
            return valor  # type: ignore[return-value]
    return None


def parse_amortizacao(texto: str | None) -> Amortizacao | None:
    if not texto:
        return None
    periodicidade = parse_periodicidade(texto)
    inicio = parse_date(texto)
    if periodicidade is None or inicio is None:
        return None
    return Amortizacao(periodicidade=periodicidade, inicio=inicio)
