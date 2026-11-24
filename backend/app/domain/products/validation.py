import calendar
from datetime import date
from decimal import Decimal

from app.domain.products.base import Indexer, Liquidity, ProductData, ProductType
from app.domain.settings import Settings

D = Decimal


def _add_months(d: date, months: int) -> date:
    total = d.year * 12 + d.month - 1 + months
    y, m = divmod(total, 12)
    return date(y, m + 1, min(d.day, calendar.monthrange(y, m + 1)[1]))


def validate_product(data: ProductData, settings: Settings, today: date) -> list[str]:
    if data.tipo.value.startswith("TESOURO_"):
        return ["Produtos do Tesouro Direto não são cadastráveis"]

    erros: list[str] = []
    venc = data.data_vencimento
    if data.tipo != ProductType.FUNDO_RF:
        if venc is None:
            erros.append("Vencimento é obrigatório")
        elif venc <= today:
            erros.append("Vencimento deve ser uma data futura")

    if data.tipo in (ProductType.LCI, ProductType.LCA, ProductType.LCD):
        meses = settings.prazo_minimo_meses(data.tipo, data.indexador) or 0
        if data.liquidez == Liquidity.DIARIA:
            erros.append(f"{data.tipo.value} não pode ter liquidez diária")
        else:
            ref = venc if data.liquidez == Liquidity.NO_VENCIMENTO else data.data_carencia
            if ref is not None and ref < _add_months(today, meses):
                erros.append(f"{data.tipo.value} exige prazo mínimo de {meses} meses")

    if data.liquidez == Liquidity.DIARIA_APOS_CARENCIA:
        if data.data_carencia is None:
            erros.append("Liquidez diária após carência exige data de carência")
        elif venc is not None and data.data_carencia >= venc:
            erros.append("A carência deve terminar antes do vencimento")

    if data.indexador == Indexer.PCT_CDI:
        if not (D("0.5") <= data.taxa <= D(2)):
            erros.append("Taxa fora do intervalo plausível (50% a 200% do CDI)")
    elif data.indexador in (Indexer.PRE, Indexer.CDI_MAIS, Indexer.IPCA_MAIS):
        if not (D(0) <= data.taxa <= D("0.5")):
            erros.append("Taxa fora do intervalo plausível (0% a 50% a.a.)")

    if data.tipo == ProductType.FUNDO_RF:
        if data.taxa_adm is None:
            erros.append("Fundo exige taxa de administração")
        if data.prazo_resgate_dias is None:
            erros.append("Fundo exige prazo de resgate em dias")
        if data.classe_tributaria is None:
            erros.append("Fundo exige classe tributária (LONGO ou CURTO)")
        if data.indexador not in (Indexer.PCT_CDI, Indexer.CDI_MAIS):
            erros.append("Fundo exige indexador % do CDI ou CDI + spread")
    return erros
