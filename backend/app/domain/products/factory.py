from app.domain.products.bank import CDB, CRA, CRI, LCA, LCD, LCI
from app.domain.products.base import Product, ProductData, ProductType
from app.domain.products.fund import FundoRendaFixa

_BUILDERS: dict[ProductType, type[Product]] = {
    ProductType.CDB: CDB,
    ProductType.LCI: LCI,
    ProductType.LCA: LCA,
    ProductType.LCD: LCD,
    ProductType.CRI: CRI,
    ProductType.CRA: CRA,
    ProductType.FUNDO_RF: FundoRendaFixa,
}


def build_product(data: ProductData) -> Product:
    cls = _BUILDERS.get(data.tipo)
    if cls is None:
        raise ValueError(f"tipo não suportado pela fábrica: {data.tipo}")
    return cls(data)
