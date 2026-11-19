from datetime import date
from decimal import Decimal as D

from app.domain.products.base import AlertCode, Indexer, Liquidity, ProductType, Section
from app.domain.products.fund import FundoRendaFixa, come_cotas_dates
from product_helpers import TODAY, cal, codes, ctx, ctx_sem_indice, make

ALVO_1ANO = cal.add_business_days(TODAY, 252)


def fundo(taxa=D("1.0"), taxa_adm=D("0.003"), classe="LONGO", prazo=0, indexador=Indexer.PCT_CDI):
    return FundoRendaFixa(make(
        tipo=ProductType.FUNDO_RF, indexador=indexador, taxa=taxa, taxa_adm=taxa_adm,
        prazo_resgate_dias=prazo, classe_tributaria=classe, data_vencimento=None,
        liquidez=Liquidity.DIARIA,
    ))


def test_fund_admin_fee_reduces_return():
    a = fundo(taxa=D("1.0"), taxa_adm=D("0")).simulate(D("10000"), ALVO_1ANO, ctx)
    b = fundo(taxa=D("1.0"), taxa_adm=D("0.01")).simulate(D("10000"), ALVO_1ANO, ctx)
    assert b.valor_bruto < a.valor_bruto and b.taxa_adm > 0
    assert a.taxa_adm == 0


def test_come_cotas_total_tax_equals_regressive():
    r = fundo(taxa=D("1.0"), taxa_adm=D("0"), classe="LONGO").simulate(D("10000"), date(2029, 1, 15), ctx)
    ganho = r.valor_bruto + r.come_cotas - 10000
    assert r.come_cotas > 0
    assert abs((r.come_cotas + r.ir) - ganho * D("0.15")) < D("0.05")


def test_come_cotas_dates():
    assert come_cotas_dates(cal, TODAY, date(2027, 6, 15)) == [date(2026, 11, 30), date(2027, 5, 31)]


def test_redemption_request_date():
    r = fundo(prazo=30).simulate(D("10000"), date(2027, 6, 15), ctx)
    assert r.data_solicitacao_resgate == date(2027, 5, 16) and AlertCode.RESGATE_DN in codes(r)
    assert {AlertCode.PROJECAO, AlertCode.FUNDO_SEM_GARANTIA, AlertCode.SEM_FGC} <= codes(r)
    assert r.secao == Section.VENCE_ATE_DATA
    assert r.serie[-1].data == date(2027, 6, 15) and r.serie[-1].valor_bruto == r.valor_bruto


def test_cdi_mais_and_unavailable():
    r = fundo(taxa=D("0.02"), indexador=Indexer.CDI_MAIS).simulate(D("10000"), ALVO_1ANO, ctx)
    assert r.valor_bruto > D("10000")
    assert fundo().simulate(D("10000"), ALVO_1ANO, ctx_sem_indice).secao == Section.INDISPONIVEL


ALVO_CURTO = date(2026, 11, 27)  # antes do primeiro come-cotas (30/11/2026)


def test_pct_cdi_gross_pinned_to_cdi_factor():
    r = fundo(taxa=D("0.9"), taxa_adm=D("0")).simulate(D("10000"), ALVO_CURTO, ctx)
    assert r.valor_bruto == D("10000") * ctx.index.cdi_factor(TODAY, ALVO_CURTO, D("0.9"))
    assert r.come_cotas == 0


def test_cdi_mais_gross_pinned_to_cdi_factor():
    r = fundo(taxa=D("0.02"), taxa_adm=D("0"), indexador=Indexer.CDI_MAIS).simulate(
        D("10000"), ALVO_CURTO, ctx
    )
    esperado = D("10000") * ctx.index.cdi_factor(TODAY, ALVO_CURTO, spread=D("0.02"))
    assert r.valor_bruto == esperado


def test_curto_come_cotas_uses_20_percent():
    alvo = date(2026, 12, 15)  # um come-cotas em 30/11/2026
    r = fundo(taxa_adm=D("0"), classe="CURTO").simulate(D("10000"), alvo, ctx)
    cc_date = date(2026, 11, 30)
    antes = D("10000") * ctx.index.cdi_factor(TODAY, cc_date)
    esperado = (D("0.20") * (antes - 10000)).quantize(D("0.01"))
    assert r.come_cotas == esperado
    longo = fundo(taxa_adm=D("0"), classe="LONGO").simulate(D("10000"), alvo, ctx)
    assert longo.come_cotas == (D("0.15") * (antes - 10000)).quantize(D("0.01"))


def test_iof_under_30_days():
    r = fundo(taxa_adm=D("0")).simulate(D("10000"), ALVO_CURTO, ctx)
    assert r.iof > 0


def test_unavailable_codes():
    r = FundoRendaFixa(make(
        tipo=ProductType.FUNDO_RF, indexador=Indexer.PCT_CDI, taxa=D("1.0"), taxa_adm=D("0"),
        valor_minimo=D("5000"), data_vencimento=None, liquidez=Liquidity.DIARIA,
    )).simulate(D("1000"), ALVO_1ANO, ctx)
    assert r.secao == Section.INDISPONIVEL and AlertCode.ABAIXO_MINIMO in codes(r)
    r = fundo().simulate(D("10000"), ALVO_1ANO, ctx_sem_indice)
    assert AlertCode.SEM_DADOS_MERCADO in codes(r)


def test_d0_fund_has_no_resgate_alert():
    r = fundo(prazo=0).simulate(D("10000"), date(2027, 6, 15), ctx)
    assert AlertCode.RESGATE_DN not in codes(r) and r.data_solicitacao_resgate == date(2027, 6, 15)


def test_admin_fee_exponent_pinned():
    du = cal.business_days_between(TODAY, ALVO_CURTO)
    r = fundo(taxa=D("1.0"), taxa_adm=D("0.01")).simulate(D("10000"), ALVO_CURTO, ctx)
    esperado = D("10000") * ctx.index.cdi_factor(TODAY, ALVO_CURTO) * (D("0.99") ** (D(du) / 252))
    assert abs(r.valor_bruto - esperado) < D("0.000001")
