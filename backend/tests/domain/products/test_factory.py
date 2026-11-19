import pytest

from app.domain.products.bank import LCA
from app.domain.products.base import ProductType
from app.domain.products.factory import build_product
from app.domain.products.fund import FundoRendaFixa
from product_helpers import make


def test_factory():
    assert isinstance(build_product(make(tipo=ProductType.LCA)), LCA)
    assert isinstance(build_product(make(tipo=ProductType.FUNDO_RF)), FundoRendaFixa)
    with pytest.raises(ValueError):
        build_product(make(tipo=ProductType.TESOURO_SELIC))
