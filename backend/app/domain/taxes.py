from decimal import ROUND_HALF_EVEN, Decimal

from pydantic import BaseModel

from app.domain.products.base import ProductType
from app.domain.settings import Settings

_CENT = Decimal("0.01")


class TaxBreakdown(BaseModel):
    iof: Decimal
    ir: Decimal


def ir_rate(days: int, s: Settings) -> Decimal:
    for b in s.ir_brackets:
        if b.max_days is None or days <= b.max_days:
            return b.rate
    return s.ir_brackets[-1].rate


def iof_rate(days: int, s: Settings) -> Decimal:
    d = max(days, 1)
    if d >= 30:
        return Decimal(0)
    return s.iof_table[d - 1]


def _q(v: Decimal) -> Decimal:
    return v.quantize(_CENT, rounding=ROUND_HALF_EVEN)


def apply_taxes(gain: Decimal, days: int, tipo: ProductType, s: Settings) -> TaxBreakdown:
    if gain <= 0:
        return TaxBreakdown(iof=Decimal(0), ir=Decimal(0))
    iof = Decimal(0) if tipo in s.iof_exempt_types else _q(gain * iof_rate(days, s))
    ir = Decimal(0) if tipo in s.ir_exempt_types else _q((gain - iof) * ir_rate(days, s))
    return TaxBreakdown(iof=iof, ir=ir)
