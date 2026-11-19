from datetime import date
from decimal import Decimal as D

from app.data.market import MarketSnapshot
from app.data.tesouro import TesouroQuote
from app.domain.sources import TesouroSource
from tests.domain.products.product_helpers import ctx


def _q(tipo, venc=date(2028, 1, 1)):
    return TesouroQuote(
        tipo=tipo, vencimento=venc, data_base=date(2026, 11, 18), taxa_compra=D("0.14"),
        taxa_venda=D("0.141"), pu_compra=D("861.32"), pu_venda=D("859.85"),
    )


def test_unknown_tesouro_type_is_skipped_not_fatal(caplog):
    snap = MarketSnapshot.empty().model_copy(
        update={"tesouro": [_q("Tesouro Prefixado"), _q("Tesouro Novo Futuro"), _q("Tesouro Selic", date(2029, 3, 1))]}
    )
    products = TesouroSource().load(ctx, snap)
    assert [p.data.tipo.value for p in products] == ["TESOURO_PREFIXADO", "TESOURO_SELIC"]
    assert "Tesouro Novo Futuro" in caplog.text
