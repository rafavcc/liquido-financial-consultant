from app.domain.products.bank import CDB, CRA, CRI, LCA, LCI
from app.domain.products.base import Product, ProductData, ProductType
from app.domain.products.fund import FundoRendaFixa

_BUILDERS: dict[ProductType, type[Product]] = {
    ProductType.CDB: CDB,
    ProductType.LCI: LCI,
    ProductType.LCA: LCA,
    ProductType.CRI: CRI,
    ProductType.CRA: CRA,
    ProductType.FUNDO_RF: FundoRendaFixa,
}


def build_product(data: ProductData) -> Product:
    try:
        return _BUILDERS[data.tipo](data)
    except KeyError:
        raise ValueError(f"tipo não suportado pela fábrica: {data.tipo}") from None
