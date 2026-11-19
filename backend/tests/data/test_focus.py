from datetime import date
from decimal import Decimal as D
from pathlib import Path

from app.data.focus import parse_annual, parse_monthly

FIX = Path(__file__).parent.parent / "fixtures" / "market"

FOCUS_SELIC_SAMPLE = """{"value":[
{"Indicador":"Selic","Data":"2026-11-06","DataReferencia":"2027","Mediana":13.0000,"baseCalculo":0},
{"Indicador":"Selic","Data":"2026-11-13","DataReferencia":"2027","Mediana":12.7500,"baseCalculo":0},
{"Indicador":"Selic","Data":"2026-11-13","DataReferencia":"2028","Mediana":11.5000,"baseCalculo":0},
{"Indicador":"Selic","Data":"2026-11-06","DataReferencia":"2029","Mediana":10.0000,"baseCalculo":0}]}"""


def test_focus_annual():
    data, anual = parse_annual(FOCUS_SELIC_SAMPLE)
    assert data == date(2026, 11, 13) and anual[2027] == D("0.1275")
    assert anual == {2027: D("0.1275"), 2028: D("0.115")}


def test_focus_monthly():
    _, mensal = parse_monthly(
        '{"value":[{"Indicador":"IPCA","Data":"2026-11-13","DataReferencia":"11/2028","Mediana":0.3200,"baseCalculo":0}]}'
    )
    assert mensal == {"2028-11": D("0.0032")}


def test_focus_recorded_fixtures():
    data, selic = parse_annual((FIX / "focus_anual_selic.json").read_text(encoding="utf-8"))
    _, mensal = parse_monthly((FIX / "focus_mensal_ipca.json").read_text(encoding="utf-8"))
    assert data == date(2026, 11, 13)
    assert selic[2026] == D("0.1375")
    assert all(len(k) == 7 and k[4] == "-" for k in mensal)
