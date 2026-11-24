from datetime import date, timedelta

import pytest

from app.domain.horizon import anos_a_frente, horizonte_natural, prazo_saida_dias
from app.domain.products.base import Indexer, Liquidity, ProductType
from tests.domain.products.product_helpers import TODAY, cal, make


def test_anos_a_frente_mesmo_dia_ajustado():
    assert anos_a_frente(TODAY, 1, cal) == cal.adjust_next(date(2027, 11, 19))
    d2 = anos_a_frente(TODAY, 2, cal)  # 19/11/2028 é domingo e 20/11 é feriado
    assert d2 == cal.adjust_next(date(2028, 11, 19)) and d2 > date(2028, 11, 20)


def test_anos_a_frente_29_fev_e_faixas_ir():
    hoje = date(2028, 2, 29)
    um, dois = anos_a_frente(hoje, 1, cal), anos_a_frente(hoje, 2, cal)
    assert um == cal.adjust_next(date(2029, 2, 28)) and (um - hoje).days > 360
    assert dois == cal.adjust_next(date(2030, 2, 28)) and (dois - hoje).days > 720


@pytest.mark.parametrize("hoje", [date(2026, 11, 19), date(2026, 12, 24), date(2027, 1, 2), date(2028, 2, 29)])
def test_anos_a_frente_sempre_dia_util_e_acima_das_faixas(hoje):
    um, dois = anos_a_frente(hoje, 1, cal), anos_a_frente(hoje, 2, cal)
    assert cal.is_business_day(um) and cal.is_business_day(dois)
    assert (um - hoje).days > 360 and (dois - hoje).days > 720


def test_prazo_saida():
    venc = date(2030, 11, 18)
    dias_venc = (cal.adjust_next(venc) - TODAY).days
    assert prazo_saida_dias(make(liquidez=Liquidity.DIARIA, data_vencimento=venc), TODAY, cal) == 0
    assert prazo_saida_dias(make(data_vencimento=venc), TODAY, cal) == dias_venc
    car = make(liquidez=Liquidity.DIARIA_APOS_CARENCIA, data_vencimento=venc, data_carencia=date(2027, 5, 19))
    assert prazo_saida_dias(car, TODAY, cal) == (date(2027, 5, 19) - TODAY).days
    car_passada = car.model_copy(update={"data_carencia": date(2026, 1, 1)})
    assert prazo_saida_dias(car_passada, TODAY, cal) == 0
    fundo = make(tipo=ProductType.FUNDO_RF, data_vencimento=None, liquidez=Liquidity.DIARIA, prazo_resgate_dias=30)
    assert prazo_saida_dias(fundo, TODAY, cal) == 30
    selic = make(tipo=ProductType.TESOURO_SELIC, indexador=Indexer.SELIC, data_vencimento=venc)
    assert prazo_saida_dias(selic, TODAY, cal) == 0
    ipca = make(tipo=ProductType.TESOURO_IPCA, indexador=Indexer.IPCA_MAIS, data_vencimento=venc)
    assert prazo_saida_dias(ipca, TODAY, cal) == dias_venc


def test_horizonte_natural():
    um_ano = anos_a_frente(TODAY, 1, cal)
    longe, perto = date(2031, 11, 17), date(2027, 3, 15)
    assert horizonte_natural(make(data_vencimento=longe), TODAY, cal) == cal.adjust_next(longe)
    assert horizonte_natural(make(liquidez=Liquidity.DIARIA, data_vencimento=longe), TODAY, cal) == um_ano
    assert horizonte_natural(make(liquidez=Liquidity.DIARIA, data_vencimento=perto), TODAY, cal) == cal.adjust_next(perto)
    car = make(liquidez=Liquidity.DIARIA_APOS_CARENCIA, data_vencimento=longe, data_carencia=date(2028, 6, 1))
    assert horizonte_natural(car, TODAY, cal) == date(2028, 6, 1)  # carência depois de 1 ano
    fundo = make(tipo=ProductType.FUNDO_RF, data_vencimento=None, liquidez=Liquidity.DIARIA, prazo_resgate_dias=30)
    assert horizonte_natural(fundo, TODAY, cal) == um_ano
    fundo_longo = fundo.model_copy(update={"prazo_resgate_dias": 400})
    assert horizonte_natural(fundo_longo, TODAY, cal) == cal.adjust_next(TODAY + timedelta(days=401))
    selic = make(tipo=ProductType.TESOURO_SELIC, indexador=Indexer.SELIC, data_vencimento=longe)
    assert horizonte_natural(selic, TODAY, cal) == um_ano
