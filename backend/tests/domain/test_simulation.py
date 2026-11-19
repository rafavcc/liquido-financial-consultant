from datetime import date
from decimal import Decimal as D

from app.domain.products.base import AlertCode, Indexer, Liquidity, Section
from app.domain.products.factory import build_product
from app.domain.simulation import simulate_all
from tests.domain.products.product_helpers import ctx, make

ALVO = date(2029, 6, 15)


def _p(id, **kw):
    return build_product(make(id=id, nome=f"Produto {id}", **kw))


def test_sections_and_ordering():
    verdes = [
        _p("a", indexador=Indexer.PCT_CDI, taxa=D("0.95"), data_vencimento=date(2028, 11, 16)),
        _p("b", indexador=Indexer.PCT_CDI, taxa=D("1.15"), data_vencimento=date(2028, 11, 16)),
        _p("c", indexador=Indexer.PCT_CDI, taxa=D("1.05"), data_vencimento=date(2028, 11, 16)),
    ]
    resgatavel = _p("r", liquidez=Liquidity.DIARIA, data_vencimento=date(2031, 11, 14))
    nao_resg_tarde = _p("n2", data_vencimento=date(2032, 11, 16))
    nao_resg_cedo = _p("n1", data_vencimento=date(2030, 11, 14))
    abaixo = _p("z", valor_minimo=D("999999"))
    produtos = [nao_resg_tarde, verdes[0], abaixo, nao_resg_cedo, verdes[1], resgatavel, verdes[2]]

    ate, depois, indisp = simulate_all(produtos, D("50000"), ALVO, ctx)

    assert [r.product.id for r in ate] == ["b", "c", "a"]
    liq = [r.valor_liquido for r in ate]
    assert liq == sorted(liq, reverse=True)
    assert all(r.secao == Section.VENCE_ATE_DATA for r in ate)
    assert [r.product.id for r in depois] == ["r", "n1", "n2"]
    assert depois[0].resgatavel and not depois[1].resgatavel
    assert [r.product.id for r in indisp] == ["z"]


def test_one_broken_product_does_not_break_all():
    class Broken:
        data = make(id="quebrado", nome="Quebrado")

        def simulate(self, valor, data_alvo, ctx):
            raise RuntimeError("boom")

    ok = _p("ok")
    ate, depois, indisp = simulate_all([Broken(), ok], D("50000"), ALVO, ctx)
    assert [r.product.id for r in ate] == ["ok"]
    assert [r.product.id for r in indisp] == ["quebrado"]
    assert indisp[0].secao == Section.INDISPONIVEL
    assert indisp[0].alertas[0].code == AlertCode.ERRO_CALCULO
    assert indisp[0].alertas[0].message == "Erro ao calcular este produto"
