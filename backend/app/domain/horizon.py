"""Datas de horizonte da simulação e prazo de saída (dias corridos)."""

from datetime import date, timedelta

from app.domain.calendar import BusinessCalendar
from app.domain.products.base import Liquidity, ProductData, ProductType


def anos_a_frente(today: date, anos: int, cal: BusinessCalendar) -> date:
    """Mesmo dia/mês `anos` à frente (29/02 vira 28/02), ajustado ao próximo dia útil."""
    try:
        alvo = today.replace(year=today.year + anos)
    except ValueError:
        alvo = today.replace(year=today.year + anos, day=28)
    return cal.adjust_next(alvo)


def _venc(d: ProductData, cal: BusinessCalendar) -> date:
    assert d.data_vencimento is not None
    return cal.adjust_next(d.data_vencimento)


def prazo_saida_dias(d: ProductData, today: date, cal: BusinessCalendar) -> int:
    """Dias corridos até poder sacar sem perda."""
    if d.tipo == ProductType.FUNDO_RF:
        return d.prazo_resgate_dias or 0
    if d.tipo == ProductType.TESOURO_SELIC:
        return 0
    if d.tipo.value.startswith("TESOURO_"):
        return (_venc(d, cal) - today).days
    if d.liquidez == Liquidity.DIARIA:
        return 0
    if d.liquidez == Liquidity.DIARIA_APOS_CARENCIA and d.data_carencia is not None:
        return max(0, (d.data_carencia - today).days)
    return (_venc(d, cal) - today).days


def horizonte_natural(d: ProductData, today: date, cal: BusinessCalendar) -> date:
    """Data em que o produto é simulado quando o usuário não informa data."""
    um_ano = anos_a_frente(today, 1, cal)
    if d.tipo == ProductType.FUNDO_RF:
        resgate = cal.adjust_next(today + timedelta(days=(d.prazo_resgate_dias or 0) + 1))
        return max(um_ano, resgate)
    venc = _venc(d, cal)
    if d.tipo == ProductType.TESOURO_SELIC:
        return min(venc, um_ano)
    if d.tipo.value.startswith("TESOURO_"):
        return venc
    if d.liquidez == Liquidity.DIARIA:
        return min(venc, um_ano)
    if d.liquidez == Liquidity.DIARIA_APOS_CARENCIA and d.data_carencia is not None:
        return min(venc, max(d.data_carencia, um_ano))
    return venc
