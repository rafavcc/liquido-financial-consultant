"""Escolha da taxa de uma oferta entre as células de taxa lidas do print (spec §6.4)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.domain.products.base import Indexer, ProductType
from app.domain.settings import Settings
from app.domain.taxes import ir_rate
from app.imports.parsing import parse_rate
from app.imports.schema import RawRate

EXCLUDED_LABEL = re.compile(r"equival|equiv|\beq\b|bruto|gross|riscad|\bir\b", re.I)
_GROSS_UP_TOLERANCE = Decimal("0.03")


@dataclass
class RateChoice:
    indexador: Indexer
    taxa: Decimal
    ignoradas: list[str] = field(default_factory=list)


@dataclass
class RateAmbiguous:
    textos: list[str]


def _plain(texto: str) -> str:
    nfd = unicodedata.normalize("NFD", texto)
    return "".join(c for c in nfd if not unicodedata.combining(c))


def _describe(valor: str, rotulo: str) -> str:
    valor, rotulo = valor.strip(), rotulo.strip()
    return f"{valor} ({rotulo})" if rotulo else valor


def choose_rate(
    taxas: list[RawRate],
    tipo: ProductType,
    vencimento: date | None,
    settings: Settings,
    today: date,
) -> RateChoice | RateAmbiguous:
    ignoradas: list[str] = []
    kept: list[tuple[str, Indexer, Decimal]] = []  # (texto do valor, indexador, taxa)
    for t in taxas:
        # o modelo às vezes troca texto e rótulo: o valor é o campo com % interpretável
        for valor, rotulo in ((t.texto, t.rotulo), (t.rotulo, t.texto)):
            parsed = parse_rate(valor) if "%" in valor else None
            if parsed:
                break
        else:
            continue
        if EXCLUDED_LABEL.search(_plain(valor)) or EXCLUDED_LABEL.search(_plain(rotulo)):
            ignoradas.append(_describe(valor, rotulo))
            continue
        if any(k[1:] == parsed for k in kept):
            continue
        kept.append((valor.strip(), *parsed))

    if (
        tipo in settings.ir_exempt_types
        and vencimento is not None
        and len(kept) == 2
        and kept[0][1] == kept[1][1]
    ):
        menor, maior = sorted(kept, key=lambda k: k[2])
        aliquota = ir_rate((vencimento - today).days, settings)
        esperado = menor[2] / (1 - aliquota)
        if abs(maior[2] - esperado) <= esperado * _GROSS_UP_TOLERANCE:
            ignoradas.append(f"{maior[0]} (equivalente bruto)")
            kept = [menor]

    if len(kept) == 1:
        return RateChoice(indexador=kept[0][1], taxa=kept[0][2], ignoradas=ignoradas)
    return RateAmbiguous(textos=[k[0] for k in kept])
