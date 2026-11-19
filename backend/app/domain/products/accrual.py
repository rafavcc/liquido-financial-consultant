from datetime import date
from decimal import Decimal

from app.domain.indexes import IndexPath, ProjecaoIndisponivel
from app.domain.products.base import Indexer, SimContext


def needs_index(indexador: Indexer) -> bool:
    return indexador != Indexer.PRE


def accrual_factor(
    indexador: Indexer, taxa: Decimal, start: date, end: date, ctx: SimContext
) -> Decimal:
    if indexador == Indexer.PRE:
        return IndexPath.pre_factor(taxa, start, end)
    index = ctx.index
    if index is None:
        raise ProjecaoIndisponivel("sem dados de mercado")
    if indexador == Indexer.PCT_CDI:
        return index.cdi_factor(start, end, pct=taxa)
    if indexador == Indexer.CDI_MAIS:
        return index.cdi_factor(start, end, spread=taxa)
    if indexador == Indexer.IPCA_MAIS:
        return index.ipca_factor(start, end) * IndexPath.pre_factor(taxa, start, end)
    return index.selic_factor(start, end) * IndexPath.pre_factor(taxa, start, end)
