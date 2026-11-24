from datetime import date
from decimal import Decimal as D

import pytest

from app.domain.products.base import Coverage, Indexer, Liquidity, ProductType
from app.domain.products.factory import build_product
from app.domain.products.validation import validate_product
from app.domain.settings import Settings
from product_helpers import TODAY, ctx, make

S = Settings()


def v(**kw):
    return validate_product(make(**kw), S, TODAY)


def test_valid_cdb_has_no_errors():
    assert v() == []


def test_vencimento_required_and_future():
    assert "Vencimento é obrigatório" in v(data_vencimento=None)
    assert "Vencimento deve ser uma data futura" in v(data_vencimento=TODAY)
    assert v(tipo=ProductType.FUNDO_RF, data_vencimento=None, taxa_adm=D("0.01"),
             prazo_resgate_dias=1, classe_tributaria="LONGO") == []


def test_lci_lca_rules():
    assert "LCI não pode ter liquidez diária" in v(tipo=ProductType.LCI, liquidez=Liquidity.DIARIA)
    assert "LCI exige prazo mínimo de 6 meses" in v(
        tipo=ProductType.LCI, data_vencimento=date(2027, 4, 1))
    assert "LCA exige prazo mínimo de 6 meses" in v(
        tipo=ProductType.LCA, data_vencimento=date(2027, 4, 1))
    assert v(tipo=ProductType.LCA, data_vencimento=date(2027, 5, 19)) == []
    assert "LCI exige prazo mínimo de 6 meses" in v(
        tipo=ProductType.LCI, liquidez=Liquidity.DIARIA_APOS_CARENCIA,
        data_carencia=date(2027, 4, 1), data_vencimento=date(2029, 1, 1))


def test_lci_ipca_needs_36_months():
    e = v(tipo=ProductType.LCI, indexador=Indexer.IPCA_MAIS, taxa=D("0.06"),
          data_vencimento=date(2029, 11, 18))
    assert "LCI exige prazo mínimo de 36 meses" in e


def test_lca_ipca_needs_12_months():
    e = v(tipo=ProductType.LCA, indexador=Indexer.IPCA_MAIS, taxa=D("0.06"),
          data_vencimento=date(2027, 8, 1))
    assert "LCA exige prazo mínimo de 12 meses" in e


def test_lcd_rules():
    assert make(tipo=ProductType.LCD).cobertura == Coverage.FGC
    assert "LCD exige prazo mínimo de 12 meses" in v(
        tipo=ProductType.LCD, data_vencimento=date(2027, 6, 1))
    assert "LCD não pode ter liquidez diária" in v(
        tipo=ProductType.LCD, liquidez=Liquidity.DIARIA, data_vencimento=date(2030, 1, 2))
    assert ProductType.LCD in S.ir_exempt_types and ProductType.LCD in S.iof_exempt_types


def test_lcd_simulates_tax_free():
    r = build_product(make(
        tipo=ProductType.LCD, indexador=Indexer.PCT_CDI, taxa=D("0.90"),
        data_vencimento=date(2030, 3, 15))).simulate(D("10000"), date(2031, 1, 1), ctx)
    assert r.ir == 0 and r.iof == 0


def test_old_settings_keys_ignored():
    s = Settings.model_validate({"carencia_min_meses_lca": 9})
    assert s.prazo_min_meses_lca == 6


def test_negative_prazo_rejected():
    with pytest.raises(ValueError):
        Settings(prazo_min_meses_lcd=-1)


def test_prazo_minimo_meses_lookup():
    assert S.prazo_minimo_meses(ProductType.CDB, Indexer.PCT_CDI) is None
    assert S.prazo_minimo_meses(ProductType.LCI, Indexer.IPCA_MAIS) == 36
    assert S.prazo_minimo_meses(ProductType.LCD, Indexer.PRE) == 12


def test_carencia_rules():
    assert "Liquidez diária após carência exige data de carência" in v(
        liquidez=Liquidity.DIARIA_APOS_CARENCIA)
    assert "A carência deve terminar antes do vencimento" in v(
        liquidez=Liquidity.DIARIA_APOS_CARENCIA, data_carencia=date(2028, 11, 16))


def test_plausible_rates():
    assert "Taxa fora do intervalo plausível (50% a 200% do CDI)" in v(taxa=D("2.5"))
    assert "Taxa fora do intervalo plausível (50% a 200% do CDI)" in v(taxa=D("0.1"))
    assert "Taxa fora do intervalo plausível (0% a 50% a.a.)" in v(indexador=Indexer.PRE, taxa=D("14.2"))
    assert "Taxa fora do intervalo plausível (0% a 50% a.a.)" in v(indexador=Indexer.IPCA_MAIS, taxa=D("-0.01"))


def test_fundo_rules():
    erros = v(tipo=ProductType.FUNDO_RF, indexador=Indexer.PRE, taxa=D("0.1"))
    assert "Fundo exige taxa de administração" in erros
    assert "Fundo exige prazo de resgate em dias" in erros
    assert "Fundo exige classe tributária (LONGO ou CURTO)" in erros
    assert "Fundo exige indexador % do CDI ou CDI + spread" in erros


def test_tesouro_not_registrable():
    assert v(tipo=ProductType.TESOURO_IPCA) == ["Produtos do Tesouro Direto não são cadastráveis"]
