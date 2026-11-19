import logging
from typing import Protocol

from app.data.market import MarketSnapshot
from app.data.repositories import ProductRepository
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
            if not d.ativo:
                continue
            try:
                out.append(build_product(d))
            except Exception:  # noqa: BLE001 - um produto inválido não derruba a simulação
                log.exception("Produto %s não pôde ser construído e foi ignorado", d.id)
        return out


class TesouroSource:
    name = "tesouro"

    def load(self, ctx: SimContext, snapshot: MarketSnapshot) -> list[Product]:
        return [build_treasury(q) for q in snapshot.tesouro]
