from datetime import date
from decimal import Decimal as D

import pytest

from app.domain.products.base import Amortizacao
from app.domain.products.base import Indexer as I
from app.imports.parsing import (
    parse_amortizacao,
    parse_carencia,
    parse_date,
    parse_money,
    parse_periodicidade,
    parse_rate,
)


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("95% do CDI", (I.PCT_CDI, D("0.95"))),
        ("102,5% CDI", (I.PCT_CDI, D("1.025"))),
        ("90,00%\ndo CDI", (I.PCT_CDI, D("0.9"))),
        ("CDI + 1,900%", (I.CDI_MAIS, D("0.019"))),
        ("CDI+1,2%", (I.CDI_MAIS, D("0.012"))),
        ("IPC-A + 7,800%", (I.IPCA_MAIS, D("0.078"))),
        ("IPCA + 12,04%", (I.IPCA_MAIS, D("0.1204"))),
        ("IPCA+ 7%", (I.IPCA_MAIS, D("0.07"))),
        ("IPC + 12,04%", (I.IPCA_MAIS, D("0.1204"))),  # o 9B lê "IPCA +" do BTG assim
        ("15,100%", (I.PRE, D("0.151"))),
        ("18,26% a.a.", (I.PRE, D("0.1826"))),
        ("Pré 14,2%", (I.PRE, D("0.142"))),
        ("109% do CDI · 18 NOV 2031", (I.PCT_CDI, D("1.09"))),
        ("abc", None),
        ("R$ 500,00", None),
    ],
)
def test_parse_rate(texto, esperado):
    assert parse_rate(texto) == esperado


def test_parse_dates():
    assert parse_date("18 NOV 2031") == date(2031, 11, 18)
    assert parse_date("5 mai 2030") == date(2030, 5, 5)
    assert parse_date("18/11/2031") == date(2031, 11, 18)
    assert parse_date("18/11/31") == date(2031, 11, 18)
    assert parse_date("365 dias | 23/11/2027") == date(2027, 11, 23)
    assert parse_date("mai/2028") is None
    assert parse_date("31/02/2028") is None


def test_parse_money():
    assert parse_money("R$ 1.093,03") == D("1093.03")
    assert parse_money("R$ 500,00") == D("500.00")
    assert parse_money("mínimo R$ 13.032,67 hoje") == D("13032.67")
    assert parse_money("sem valor") is None


def test_parse_carencia():
    assert parse_carencia("D+90", date(2026, 11, 23)) == date(2027, 2, 21)
    assert parse_carencia("90 dias", date(2026, 11, 23)) == date(2027, 2, 21)
    assert parse_carencia("01/03/2027", date(2026, 11, 23)) == date(2027, 3, 1)
    with pytest.raises(ValueError):
        parse_carencia("após o 3º mês", date(2026, 11, 23))


def test_parse_periodicidade():
    assert parse_periodicidade("Mensal") == "MENSAL"
    assert parse_periodicidade("Mensais") == "MENSAL"
    assert parse_periodicidade("Trimestral") == "TRIMESTRAL"
    assert parse_periodicidade("semestral") == "SEMESTRAL"
    assert parse_periodicidade("Anual") == "ANUAL"
    for vazio in ("No Vencimento", "-", "", None):
        assert parse_periodicidade(vazio) is None


def test_parse_amortizacao():
    assert parse_amortizacao("Anual a partir de 15/03/2032") == Amortizacao(
        periodicidade="ANUAL", inicio=date(2032, 3, 15)
    )
    assert parse_amortizacao("No Vencimento") is None
    assert parse_amortizacao("-") is None
    assert parse_amortizacao(None) is None


def test_parse_money_without_cents_and_mil():
    assert parse_money("R$ 1.000") == D("1000")
    assert parse_money("R$ 250.000") == D("250000")
    assert parse_money("R$ 5.000.000") == D("5000000")
    assert parse_money("R$ 100") == D("100")
    assert parse_money("R$ 1.000,5") == D("1000.5")
    assert parse_money("R$ 250 mil") == D("250000")
    assert parse_money("1,5 mil") == D("1500")
    assert parse_money("R$ 1 milhão") == D("1000000")
    assert parse_money("R$ 2 mi") == D("2000000")
    assert parse_money("sem valor") is None
    assert parse_money("5 dias") is None


def test_parse_rate_other_indexes_are_never_pre():
    for t in ("IGP-M + 5%", "IGPM + 5,5%", "IGP-DI + 4%", "Selic + 0,10%", "100% da Selic",
              "DI + 2%", "INPC + 6%", "TR + 8%", "Poupança 70%", "USD + 5%", "Dólar + 4%", "IPCA 5%"):
        assert parse_rate(t) is None, t
    assert parse_rate("CDI 105%") == (I.PCT_CDI, D("1.05"))
    assert parse_rate("12% a.a.") == (I.PRE, D("0.12"))


def test_parse_money_mil_with_decimals_is_not_read_as_cents():
    assert parse_money("R$ 1,25 milhão") == D("1250000")
    assert parse_money("R$ 1,50 mil") == D("1500")
    assert parse_money("R$ 1.000,00") == D("1000.00")
