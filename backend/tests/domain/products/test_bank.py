from datetime import date, timedelta
from decimal import Decimal as D

from app.domain.products.base import AlertCode, Coverage, Indexer, Liquidity, ProductType, Section
from app.domain.products.bank import CDB, CRI, LCA, LCI
from product_helpers import TODAY, cal, codes, ctx, ctx_sem_indice, make

PCT_CDI, PRE, IPCA_MAIS = Indexer.PCT_CDI, Indexer.PRE, Indexer.IPCA_MAIS
DIARIA, NO_VENCIMENTO = Liquidity.DIARIA, Liquidity.NO_VENCIMENTO
DIARIA_APOS_CARENCIA = Liquidity.DIARIA_APOS_CARENCIA


def test_cdb_matures_before_target():
    p = CDB(make(tipo=ProductType.CDB, indexador=PCT_CDI, taxa=D("1.10"),
                 data_vencimento=cal.add_business_days(TODAY, 252)))
    r = p.simulate(D("10000"), date(2028, 6, 1), ctx)
    assert r.secao == Section.VENCE_ATE_DATA and r.dias_parado > 0
    assert abs(r.valor_bruto - D("11511")) < D("1")
    assert r.ir == ((r.valor_bruto - 10000) * D("0.175")).quantize(D("0.01"))
    assert {a.code for a in r.alertas} >= {AlertCode.PROJECAO, AlertCode.PARADO}
    assert r.serie[-1].data == r.data_saida and r.serie[-1].valor_bruto == r.valor_bruto
    assert r.serie[0].data == date(2026, 11, 30)


def test_lci_92_equals_cdb_110_roughly():
    lci = LCI(make(tipo=ProductType.LCI, taxa=D("0.92"),
                   data_vencimento=cal.add_business_days(TODAY, 252)))
    assert abs(lci.simulate(D("10000"), date(2028, 1, 1), ctx).valor_liquido - D("11249")) < D("2")


def test_short_target_iof_and_unredeemable():
    alvo = TODAY + timedelta(days=10)
    cdb = CDB(make(tipo=ProductType.CDB, liquidez=DIARIA, taxa=D("1.0"),
                   data_vencimento=date(2030, 1, 2)))
    r = cdb.simulate(D("10000"), alvo, ctx)
    assert r.secao == Section.VENCE_DEPOIS and r.resgatavel and r.iof > 0
    lca = LCA(make(tipo=ProductType.LCA, liquidez=NO_VENCIMENTO, data_vencimento=date(2028, 1, 3)))
    r2 = lca.simulate(D("10000"), alvo, ctx)
    assert not r2.resgatavel and r2.valor_liquido is None and AlertCode.NAO_RESGATAVEL in codes(r2)


def test_grace_then_daily():
    lci = LCI(make(tipo=ProductType.LCI, liquidez=DIARIA_APOS_CARENCIA,
                   data_carencia=date(2027, 11, 19), data_vencimento=date(2029, 1, 15)))
    assert lci.simulate(D("10000"), date(2028, 3, 1), ctx).resgatavel
    assert not lci.simulate(D("10000"), date(2027, 6, 1), ctx).resgatavel


def test_holiday_maturity_adjusted():
    r = CDB(make(data_vencimento=date(2027, 1, 1))).simulate(D("10000"), date(2027, 1, 2), ctx)
    assert r.secao == Section.VENCE_DEPOIS
    r2 = CDB(make(data_vencimento=date(2027, 1, 1))).simulate(D("10000"), date(2027, 1, 4), ctx)
    assert r2.data_saida == date(2027, 1, 4)


def test_below_minimum_and_no_market():
    r0 = CDB(make(valor_minimo=D("5000"))).simulate(D("1000"), date(2028, 1, 1), ctx)
    assert r0.secao == Section.INDISPONIVEL and AlertCode.ABAIXO_MINIMO in codes(r0)
    assert r0.alertas[0].message == "Valor abaixo do mínimo de R$ 5.000"
    r = CDB(make(indexador=PCT_CDI)).simulate(D("10000"), date(2028, 1, 1), ctx_sem_indice)
    assert r.secao == Section.INDISPONIVEL and AlertCode.SEM_DADOS_MERCADO in codes(r)
    pre = CDB(make(indexador=PRE, taxa=D("0.142"))).simulate(D("10000"), date(2028, 1, 1), ctx_sem_indice)
    assert pre.secao != Section.INDISPONIVEL


def test_missing_ipca_projection_is_unavailable():
    from app.domain.indexes import IndexPath
    from app.domain.products.base import SimContext
    from app.domain.settings import Settings
    from app.data.market import MarketSnapshot
    from decimal import Decimal as D2
    snap = MarketSnapshot.empty().model_copy(update=dict(selic_meta=D2("0.1375")))
    c = SimContext(TODAY, cal, Settings(), IndexPath.build(snap, Settings(), cal, TODAY))
    r = CDB(make(indexador=IPCA_MAIS, taxa=D("0.06"), data_vencimento=date(2027, 12, 1))).simulate(D("10000"), date(2028, 1, 1), c)
    assert r.secao == Section.INDISPONIVEL and AlertCode.SEM_DADOS_MERCADO in codes(r)


def test_cri_no_fgc_and_fgc_limit():
    assert AlertCode.SEM_FGC in codes(CRI(make(tipo=ProductType.CRI)).simulate(D("10000"), date(2033, 1, 1), ctx))
    r = CDB(make()).simulate(D("300000"), date(2033, 1, 1), ctx)
    assert AlertCode.FGC_LIMITE in codes(r)
    assert "R$ 250.000" in next(a.message for a in r.alertas if a.code == AlertCode.FGC_LIMITE)


def test_coverage_filled_and_projection_message():
    assert make(tipo=ProductType.CRA).cobertura == Coverage.NENHUMA
    assert make(tipo=ProductType.TESOURO_IPCA).cobertura == Coverage.TESOURO
    r = CDB(make(exemplo=True)).simulate(D("10000"), date(2033, 1, 1), ctx)
    msgs = {a.code: a.message for a in r.alertas}
    assert msgs[AlertCode.PROJECAO] == "Depende de projeção de CDI (Focus 13/11/2026)"
    assert msgs[AlertCode.EXEMPLO] == "Produto fictício (exemplo)"
    assert AlertCode.PROJECAO not in codes(
        CDB(make(indexador=PRE, taxa=D("0.14"))).simulate(D("10000"), date(2033, 1, 1), ctx))


def test_non_projection_value_error_propagates(monkeypatch):
    import pytest
    from app.domain.products import bank

    def boom(*a, **k):
        raise ValueError("boom")

    monkeypatch.setattr(bank, "accrual_factor", boom)
    with pytest.raises(ValueError, match="boom"):
        CDB(make(data_vencimento=date(2027, 12, 1))).simulate(D("10000"), date(2028, 1, 1), ctx)
