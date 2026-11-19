from datetime import date
from decimal import Decimal as D
from pathlib import Path

from app.data.tesouro import TesouroQuote, decode_csv, parse_latest
from app.domain.products.base import AlertCode, Indexer, ProductType, Section
from app.domain.products.treasury import (
    TIPO_MAP,
    build_treasury,
    cash_flow_dates,
    flows,
    pv_factor,
)
from tests.domain.products.product_helpers import TODAY, cal, codes, ctx, ctx_sem_indice

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "market" / "tesouro.csv"

q_ltn_2032 = TesouroQuote(
    tipo="Tesouro Prefixado", vencimento=date(2032, 1, 1), data_base=date(2026, 11, 18),
    taxa_compra=D("0.1528"), taxa_venda=D("0.1540"), pu_compra=D("485.38"), pu_venda=D("482.54"),
)
q_ntnb_juros_2035 = TesouroQuote(
    tipo="Tesouro IPCA+ com Juros Semestrais", vencimento=date(2035, 5, 15),
    data_base=date(2026, 11, 18), taxa_compra=D("0.0773"), taxa_venda=D("0.0785"),
    pu_compra=D("4301.32"), pu_venda=D("4267.89"),
)
q_selic_2029 = TesouroQuote(
    tipo="Tesouro Selic", vencimento=date(2029, 3, 1), data_base=date(2026, 11, 18),
    taxa_compra=D("0.0005"), taxa_venda=D("0.0006"),
    pu_compra=D("20310.33"), pu_venda=D("20295.34"),
)


def test_ltn_and_ntnf_pricing_matches_published_pu():
    quotes = parse_latest(decode_csv(FIXTURE.read_bytes()))
    checked = 0
    for q in quotes:
        if q.tipo in ("Tesouro Prefixado", "Tesouro Prefixado com Juros Semestrais"):
            f = flows(TIPO_MAP[q.tipo], q.vencimento, q.data_base)
            assert abs(1000 * pv_factor(f, q.taxa_compra, q.data_base, cal) - q.pu_compra) < D("0.10"), q
            checked += 1
    assert checked > 0


def test_coupon_dates_backwards():
    assert cash_flow_dates(date(2035, 5, 15), 6, date(2026, 11, 19))[:2] == [date(2027, 5, 15), date(2027, 11, 15)]
    assert cash_flow_dates(date(2032, 8, 15), 6, date(2026, 11, 19))[0] == date(2027, 2, 15)


def test_flows_shapes():
    assert flows(ProductType.TESOURO_PREFIXADO, date(2030, 1, 1), TODAY) == [(date(2030, 1, 1), D(1))]
    ntnf = flows(ProductType.TESOURO_PREFIXADO_JUROS, date(2030, 1, 1), TODAY)
    assert ntnf[0][1] == D("1.10") ** D("0.5") - 1 and ntnf[-1][1] == 1 + (D("1.10") ** D("0.5") - 1)
    renda = flows(ProductType.TESOURO_RENDA_MAIS, date(2060, 1, 1), TODAY)
    assert len(renda) == 240 and abs(sum(f for _, f in renda) - 1) < D('1e-20') and renda[-1][0] == date(2060, 1, 1)
    educa = flows(ProductType.TESOURO_EDUCA_MAIS, date(2033, 1, 1), TODAY)
    assert len(educa) == 60 and educa[-1][0] == date(2033, 1, 1)


def test_ltn_held_to_maturity():
    q = TesouroQuote(
        tipo="Tesouro Prefixado", vencimento=date(2028, 1, 1), data_base=TODAY,
        taxa_compra=D("0.1438"), taxa_venda=D("0.1450"),
        pu_compra=D("861.32"), pu_venda=D("859.85"),
    )
    r = build_treasury(q).simulate(D("10000"), date(2028, 6, 1), ctx)
    assert r.secao == Section.VENCE_ATE_DATA and r.valor_investido == D("11.61") * D("861.32")
    assert r.valor_bruto == D("11610.00") and AlertCode.PROJECAO not in codes(r)
    assert r.ir > 0 and r.valor_liquido == r.valor_bruto - r.iof - r.ir - r.custodia + r.sobra
    assert r.serie[-1].valor_bruto == r.valor_bruto and r.serie[-1].data == r.data_saida


def test_early_exit_is_market_estimate():
    r = build_treasury(q_ltn_2032).simulate(D("10000"), date(2028, 6, 1), ctx)
    assert r.secao == Section.VENCE_DEPOIS and r.estimativa_mercado and AlertCode.ESTIMATIVA_MERCADO in codes(r)
    assert r.resgatavel and r.data_saida == date(2028, 6, 1)
    assert AlertCode.PROJECAO not in codes(r)


def test_ntnb_coupons_idle_and_taxed():
    r = build_treasury(q_ntnb_juros_2035).simulate(D("10000"), date(2035, 6, 1), ctx)
    # cupons de 2027..2035 recebidos e parados; IR descontado em cada um; dias_parado > 0
    assert r.secao == Section.VENCE_ATE_DATA and r.ir > 0 and AlertCode.PROJECAO in codes(r)
    assert r.dias_parado == 17
    # 2027-05-15 .. 2035-05-15 (inclui o cupom do vencimento) = 17 cupons
    assert len(flows(ProductType.TESOURO_IPCA_JUROS, date(2035, 5, 15), TODAY)) == 17
    # cupons tributados cheios (sem abater custo): IR acima de 15% sobre todo o ganho bruto
    assert r.ir > D("0.15") * (r.valor_bruto - r.valor_investido)


def test_selic_custody_exemption():
    # 8000 -> posição média (investido + saída)/2 ~ 9.3k, abaixo da isenção de 10k
    small = build_treasury(q_selic_2029).simulate(D("8000"), date(2029, 3, 5), ctx)
    big = build_treasury(q_selic_2029).simulate(D("100000"), date(2029, 3, 5), ctx)
    assert small.custodia == 0 and big.custodia > 0


def test_indexed_without_projection_is_unavailable_but_prefixado_is_not():
    r = build_treasury(q_ntnb_juros_2035).simulate(D("10000"), date(2035, 6, 1), ctx_sem_indice)
    assert r.secao == Section.INDISPONIVEL and AlertCode.SEM_DADOS_MERCADO in codes(r)
    r = build_treasury(q_ltn_2032).simulate(D("10000"), date(2028, 6, 1), ctx_sem_indice)
    assert r.secao == Section.VENCE_DEPOIS


def test_build_treasury_metadata_and_minimum():
    p = build_treasury(q_selic_2029)
    assert p.data.id == "tesouro-selic-2029-03-01" and p.data.nome == "Tesouro Selic 2029"
    assert p.data.indexador == Indexer.SELIC and p.data.valor_minimo == D("203.1033")
    assert build_treasury(q_ltn_2032).data.valor_minimo == D("30")
    r = p.simulate(D("100"), date(2029, 3, 5), ctx)
    assert r.secao == Section.INDISPONIVEL and AlertCode.ABAIXO_MINIMO in codes(r)


def test_renda_mais_flags_simplified_model():
    q = TesouroQuote(
        tipo="Tesouro Renda+ Aposentadoria Extra", vencimento=date(2050, 1, 1),
        data_base=TODAY, taxa_compra=D("0.0700"), taxa_venda=D("0.0710"),
        pu_compra=D("1000"), pu_venda=D("990"),
    )
    r = build_treasury(q).simulate(D("10000"), date(2040, 1, 2), ctx)
    assert AlertCode.MODELO_SIMPLIFICADO in codes(r) and AlertCode.PROJECAO in codes(r)


def _installment_quote(tipo, venc):
    return TesouroQuote(
        tipo=tipo, vencimento=venc, data_base=TODAY, taxa_compra=D("0.0700"),
        taxa_venda=D("0.0710"), pu_compra=D("1000"), pu_venda=D("990"),
    )


def test_renda_mais_ir_deducts_pro_rata_cost_basis():
    q = _installment_quote("Tesouro Renda+ Aposentadoria Extra", date(2050, 1, 1))
    r = build_treasury(q).simulate(D("10000"), date(2040, 1, 2), ctx)  # saída antecipada em plena fase de pagamento
    assert r.secao == Section.VENCE_DEPOIS
    assert 0 < r.ir < D("0.225") * (r.valor_bruto - r.valor_investido)


def test_educa_mais_to_maturity_ir_deducts_cost_basis():
    q = _installment_quote("Tesouro Educa+", date(2033, 1, 1))
    r = build_treasury(q).simulate(D("10000"), date(2033, 3, 1), ctx)
    assert r.secao == Section.VENCE_ATE_DATA
    assert 0 < r.ir < D("0.225") * (r.valor_bruto - r.valor_investido)


def test_expired_quote_is_unavailable_not_a_crash():
    q = q_selic_2029.model_copy(update={"vencimento": date(2026, 11, 10)})
    r = build_treasury(q).simulate(D("10000"), date(2027, 3, 5), ctx)
    assert r.secao == Section.INDISPONIVEL and AlertCode.SEM_DADOS_MERCADO in codes(r)


def test_leftover_cash_is_kept_idle_and_counted_in_net_value():
    # R$ 2.000 em Tesouro Selic (PU 20.310,33): qtd 0,09 -> investe 1.827,93 e sobram 172,07 parados
    r = build_treasury(q_selic_2029).simulate(D("2000"), date(2026, 12, 10), ctx)
    assert r.valor_investido == D("0.09") * D("20310.33")
    assert r.sobra == D("2000") - r.valor_investido and r.sobra > D("172")
    assert r.valor_liquido == r.valor_bruto - r.iof - r.ir - r.custodia + r.sobra
    assert r.valor_liquido > D("1990")  # o dinheiro parado não some do total
    assert r.rentab_liquida == r.valor_liquido / D("2000") - 1


def test_no_leftover_when_amount_is_exact_multiple():
    r = build_treasury(q_ltn_2032).simulate(D("485.38"), date(2028, 6, 1), ctx)
    assert r.sobra == 0
