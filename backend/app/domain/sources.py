import logging
from typing import Protocol

from app.data.market import MarketSnapshot
from app.data.repositories import ProductRepository
from app.domain.offers import is_expired
from app.domain.products.base import Product, SimContext
from app.domain.products.factory import build_product
from app.domain.products.treasury import build_treasury

log = logging.getLogger(__name__)


class ProductSource(Protocol):
    name: str

    def load(self, ctx: SimContext, snapshot: MarketSnapshot) -> list[Product]: ...


class ManualSource:
    name = "manual"

    def __init__(self, repo: ProductRepository) -> None:
        self._repo = repo

    def load(self, ctx: SimContext, snapshot: MarketSnapshot) -> list[Product]:
        out: list[Product] = []
        for d in self._repo.list():
            if not d.ativo or is_expired(d, ctx.settings, ctx.today):
                continue
            try:
                out.append(build_product(d))
            except Exception:  # noqa: BLE001 - um produto inválido não derruba a simulação
                log.exception("Produto %s não pôde ser construído e foi ignorado", d.id)
        return out


class TesouroSource:
    name = "tesouro"

    def load(self, ctx: SimContext, snapshot: MarketSnapshot) -> list[Product]:
        out: list[Product] = []
        for q in snapshot.tesouro:
            try:
                out.append(build_treasury(q))
            except Exception:  # noqa: BLE001 - tipo novo ou cotação inválida não derruba a simulação
                log.exception("Título do Tesouro desconhecido ou inválido ignorado: %s %s", q.tipo, q.vencimento)
        return out
