from datetime import date
from decimal import Decimal as D

from app.domain.products.base import AlertCode, Indexer, Liquidity, Section
from app.domain.products.factory import build_product
from app.domain.horizon import anos_a_frente
from app.domain.simulation import simulate_all, simulate_sem_data
from tests.domain.products.product_helpers import TODAY, cal, ctx, make

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


class Broken:
    data = make(id="quebrado", nome="Quebrado")

    def simulate(self, valor, data_alvo, ctx):
        raise RuntimeError("boom")


def test_one_broken_product_does_not_break_all():
    ok = _p("ok")
    ate, depois, indisp = simulate_all([Broken(), ok], D("50000"), ALVO, ctx)
    assert [r.product.id for r in ate] == ["ok"]
    assert [r.product.id for r in indisp] == ["quebrado"]
    assert indisp[0].secao == Section.INDISPONIVEL
    assert indisp[0].alertas[0].code == AlertCode.ERRO_CALCULO
    assert indisp[0].alertas[0].message == "Erro ao calcular este produto"


def test_simulate_all_preenche_prazo_saida():
    diaria = _p("d", liquidez=Liquidity.DIARIA, data_vencimento=date(2031, 11, 14))
    presa = _p("p", data_vencimento=date(2028, 11, 16))
    abaixo = _p("z", valor_minimo=D("999999"))
    ate, depois, indisp = simulate_all([diaria, presa, abaixo], D("50000"), ALVO, ctx)
    por_id = {r.product.id: r for r in ate + depois + indisp}
    assert por_id["d"].prazo_saida_dias == 0
    assert por_id["p"].prazo_saida_dias == (cal.adjust_next(date(2028, 11, 16)) - TODAY).days
    assert por_id["z"].prazo_saida_dias is None


def test_sem_data_simula_cada_um_ate_o_seu_horizonte():
    longo = _p("longo", indexador=Indexer.PRE, taxa=D("0.13"), data_vencimento=date(2031, 11, 17))
    curto = _p("curto", indexador=Indexer.PRE, taxa=D("0.12"), data_vencimento=date(2027, 11, 22))
    diaria = _p("diaria", liquidez=Liquidity.DIARIA, data_vencimento=date(2031, 11, 17))
    ate, depois, indisp = simulate_sem_data([curto, diaria, longo], D("50000"), ctx)
    assert depois == [] and indisp == []
    por_id = {r.product.id: r for r in ate}
    assert por_id["longo"].data_saida == cal.adjust_next(date(2031, 11, 17))
    assert por_id["diaria"].data_saida == anos_a_frente(TODAY, 1, cal)
    taxas = [r.taxa_liquida_aa for r in ate]
    assert taxas == sorted(taxas, reverse=True)
    assert ate[0].product.id == "longo"  # pré 13% com IR 15% supera os demais
    assert all(r.prazo_saida_dias is not None for r in ate)


def test_sem_data_produto_quebrado_vai_para_indisponiveis():
    ate, depois, indisp = simulate_sem_data([Broken(), _p("ok")], D("50000"), ctx)
    assert [r.product.id for r in ate] == ["ok"] and [r.product.id for r in indisp] == ["quebrado"]
