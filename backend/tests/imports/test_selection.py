from datetime import date
from decimal import Decimal as D

from app.domain.products.base import Indexer, ProductType
from app.domain.settings import Settings
from app.imports.schema import RawRate
from app.imports.selection import RateAmbiguous, choose_rate

T = date(2026, 11, 23)
CDB, LCI = ProductType.CDB, ProductType.LCI
PCT_CDI = Indexer.PCT_CDI


def test_btg_eq_cdb_label_discarded():
    c = choose_rate(
        [
            RawRate(texto="90,00% do CDI", rotulo="Taxa"),
            RawRate(texto="108,46% do CDI", rotulo="Taxa eq. CDB"),
        ],
        LCI, date(2027, 11, 23), Settings(), T,
    )
    assert (c.indexador, c.taxa) == (PCT_CDI, D("0.9"))
    assert "108,46% do CDI (Taxa eq. CDB)" in c.ignoradas


def test_gross_up_without_label():
    c = choose_rate(
        [RawRate(texto="90% do CDI"), RawRate(texto="107,93% do CDI")],
        LCI, date(2028, 5, 24), Settings(), T,
    )
    assert c.taxa == D("0.9")
    assert len(c.ignoradas) == 1


def test_gross_up_not_applied_to_taxed_type():
    r = choose_rate(
        [RawRate(texto="90% do CDI"), RawRate(texto="107,93% do CDI")],
        CDB, date(2028, 5, 24), Settings(), T,
    )
    assert isinstance(r, RateAmbiguous)


def test_strikethrough_and_ir_discarded():
    c = choose_rate(
        [
            RawRate(texto="107% do CDI", rotulo="riscada"),
            RawRate(texto="108% do CDI", rotulo=""),
            RawRate(texto="15%", rotulo="IR"),
        ],
        CDB, date(2028, 11, 18), Settings(), T,
    )
    assert c.taxa == D("1.08")
    assert len(c.ignoradas) == 2


def test_swapped_fields_and_junk_cells():  # comportamento real do Qwen3.5-9B
    taxas = [
        RawRate(rotulo="90,00% do CDI", texto="Taxa"),
        RawRate(rotulo="108,46% do CDI", texto="Taxa eq. CDB"),
        RawRate(rotulo="R$ 500,00", texto="Aplicação mínima"),
        RawRate(texto="22/11/2028", rotulo="Vencimento"),
        RawRate(texto="2", rotulo="Risco"),
    ]
    assert choose_rate(taxas, LCI, date(2027, 11, 23), Settings(), T).taxa == D("0.9")


def test_equal_rates_collapse():
    c = choose_rate(
        [RawRate(texto="95% do CDI"), RawRate(texto="95,0% CDI", rotulo="Taxa")],
        CDB, date(2028, 1, 3), Settings(), T,
    )
    assert c.taxa == D("0.95")


def test_two_unrelated_rates_are_ambiguous():
    r = choose_rate(
        [RawRate(texto="95% do CDI"), RawRate(texto="99% do CDI")],
        CDB, date(2028, 1, 3), Settings(), T,
    )
    assert isinstance(r, RateAmbiguous)
    assert r.textos == ["95% do CDI", "99% do CDI"]


def test_no_rate_is_ambiguous():
    assert isinstance(choose_rate([], CDB, date(2028, 1, 3), Settings(), T), RateAmbiguous)


def test_btg_cdb_table_eq_cdb_is_the_rate_itself():
    """Tabela de CDB do site do BTG: "Taxa" = "103,75%" (CDI implícito) e "Taxa Eq. do CDB" = "103,75% do CDI".
    Num CDB o equivalente CDB é a própria taxa; o número solto igual a ela é a mesma taxa sem indexador."""
    taxas = [RawRate(rotulo="Taxa Eq. do CDB", texto="103,75% do CDI"), RawRate(rotulo="Taxa", texto="103,75%")]
    r = choose_rate(taxas, ProductType.CDB, date(2028, 11, 23), Settings(), T)
    assert (r.indexador, r.taxa) == (Indexer.PCT_CDI, D("1.0375"))


def test_eq_cdb_still_discarded_for_exempt_types():
    taxas = [RawRate(rotulo="Taxa", texto="90,00% do CDI"), RawRate(rotulo="Taxa eq. CDB", texto="108,46% do CDI")]
    r = choose_rate(taxas, ProductType.LCI, date(2027, 11, 23), Settings(), T)
    assert r.taxa == D("0.9")


def test_bare_number_dropped_as_same_rate_is_reported():
    taxas = [RawRate(rotulo="Taxa Eq. do CDB", texto="103,75% do CDI"), RawRate(rotulo="Taxa", texto="103,75%")]
    r = choose_rate(taxas, ProductType.CDB, date(2028, 11, 23), Settings(), T)
    assert "103,75% (mesma taxa sem indexador)" in r.ignoradas
