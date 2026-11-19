from typing import Protocol

from app.data.market import MarketSnapshot
from app.data.repositories import ProductRepository
from app.domain.products.base import Product, SimContext
from app.domain.products.factory import build_product
from app.domain.products.treasury import build_treasury


class ProductSource(Protocol):
    name: str

    def load(self, ctx: SimContext, snapshot: MarketSnapshot) -> list[Product]: ...


class ManualSource:
    name = "manual"

    def __init__(self, repo: ProductRepository) -> None:
        self._repo = repo

    def load(self, ctx: SimContext, snapshot: MarketSnapshot) -> list[Product]:
        return [build_product(d) for d in self._repo.list() if d.ativo]


class TesouroSource:
    name = "tesouro"

    def load(self, ctx: SimContext, snapshot: MarketSnapshot) -> list[Product]:
        return [build_treasury(q) for q in snapshot.tesouro]
