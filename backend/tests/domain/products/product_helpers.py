from datetime import date
from decimal import Decimal as D

from app.data.market import MarketSnapshot
from app.domain.calendar import get_calendar
from app.domain.indexes import IndexPath
from app.domain.products.base import (
    Indexer,
    Liquidity,
    ProductData,
    ProductType,
    SimContext,
)
from app.domain.settings import Settings

TODAY = date(2026, 11, 19)
cal = get_calendar()


def _snapshot() -> MarketSnapshot:
    anos = range(2026, 2036)
    return MarketSnapshot.empty().model_copy(update=dict(
        selic_meta=D("0.1375"),
        focus_data=date(2026, 11, 13),
        focus_selic_anual={y: D("0.1375") for y in anos},
        focus_ipca_anual={y: D("0.045") for y in anos},
        focus_ipca_mensal={},
    ))


ctx = SimContext(
    today=TODAY, cal=cal, settings=Settings(),
    index=IndexPath.build(_snapshot(), Settings(), cal, TODAY),
)
ctx_sem_indice = SimContext(today=TODAY, cal=cal, settings=Settings(), index=None)


def make(**overrides) -> ProductData:
    base = dict(
        id="t", tipo=ProductType.CDB, nome="Produto Teste", emissor="Banco Teste",
        plataforma="XP", indexador=Indexer.PCT_CDI, taxa=D("1.0"),
        data_vencimento=date(2028, 11, 16), valor_minimo=D("0"),
        liquidez=Liquidity.NO_VENCIMENTO, data_carencia=None,
    )
    base.update(overrides)
    return ProductData(**base)


def codes(r) -> set:
    return {a.code for a in r.alertas}
