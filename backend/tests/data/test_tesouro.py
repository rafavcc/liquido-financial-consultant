from datetime import date
from decimal import Decimal as D
from pathlib import Path

from app.data.tesouro import TesouroQuote, decode_csv, parse_latest

FIX = Path(__file__).parent.parent / "fixtures" / "market"

TESOURO_CSV = """Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manha;Taxa Venda Manha;PU Compra Manha;PU Venda Manha;PU Base Manha
Tesouro Prefixado;01/01/2028;18/11/2026;14,38;14,50;861,32;859,85;859,85
Tesouro Prefixado;01/01/2028;17/11/2026;14,30;14,42;862,00;860,50;860,50
Tesouro IGPM+ com Juros Semestrais;01/01/2031;18/11/2026;7,63;7,75;8110,14;8076,03;8076,03
Tesouro Selic;01/03/2029;18/11/2026;0,05;0,06;20310,33;20295,34;20295,34"""


def test_tesouro_parse_latest():
    q = parse_latest(TESOURO_CSV)
    assert [x.tipo for x in q] == ["Tesouro Prefixado", "Tesouro Selic"]
    assert q[0] == TesouroQuote(tipo="Tesouro Prefixado", vencimento=date(2028, 1, 1), data_base=date(2026, 11, 18),
        taxa_compra=D("0.1438"), taxa_venda=D("0.1450"), pu_compra=D("861.32"), pu_venda=D("859.85"))


def test_tesouro_drops_zero_pu_and_handles_bom_and_unsorted():
    csv_text = "﻿" + TESOURO_CSV.replace(
        "Tesouro Selic;01/03/2029;18/11/2026;0,05;0,06;20310,33",
        "Tesouro Selic;01/03/2029;18/11/2026;0,05;0,06;0,00",
    )
    assert [x.tipo for x in parse_latest(csv_text)] == ["Tesouro Prefixado"]


def test_decode_csv_utf8_bom_and_latin1():
    assert decode_csv("﻿Título".encode("utf-8")) == "Título"
    assert decode_csv("Título".encode("latin-1")) == "Título"


def test_tesouro_recorded_fixture():
    q = parse_latest((FIX / "tesouro.csv").read_text(encoding="utf-8"))
    assert q and len({x.data_base for x in q}) == 1
    assert all(x.pu_compra > 0 for x in q)
    assert (FIX / "tesouro.csv").stat().st_size < 50_000


def test_tesouro_drops_rows_with_empty_rate_or_pu():
    csv_text = TESOURO_CSV.replace("14,38;14,50;861,32", "14,38;;861,32").replace(
        "0,05;0,06;20310,33", "0,05;0,06;"
    )
    assert parse_latest(csv_text) == []
