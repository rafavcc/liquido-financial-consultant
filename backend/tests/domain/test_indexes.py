from datetime import date
from decimal import Decimal as D

import pytest

from app.data.market import MarketSnapshot
from app.domain.calendar import get_calendar
from app.domain.indexes import IndexPath
from app.domain.settings import Settings

TODAY = date(2026, 11, 19)
cal = get_calendar()


def flat_snapshot(selic="0.1375", ipca_anual="0.045"):
    return MarketSnapshot.empty().model_copy(update=dict(
        selic_meta=D(selic),
        focus_data=date(2026, 11, 13),
        focus_selic_anual={2026: D(selic), 2027: D(selic)},
        focus_ipca_anual={2026: D(ipca_anual), 2027: D(ipca_anual)},
        focus_ipca_mensal={},
    ))


def test_flat_cdi_one_year():
    p = IndexPath.build(flat_snapshot(), Settings(), cal, TODAY)
    end = cal.add_business_days(TODAY, 252)
    assert abs(p.cdi_factor(TODAY, end) - D("1.1365")) < D("1e-9")
    d = (D("1.1365") ** (D(1) / 252)) - 1
    assert abs(p.cdi_factor(TODAY, end, pct=D("1.10")) - (1 + D("1.10") * d) ** 252) < D("1e-9")


def test_cdi_spread_and_selic_factor():
    p = IndexPath.build(flat_snapshot(), Settings(), cal, TODAY)
    end = cal.add_business_days(TODAY, 252)
    assert abs(p.cdi_factor(TODAY, end, spread=D("0.02")) - D("1.1365") * D("1.02")) < D("1e-9")
    assert abs(p.selic_factor(TODAY, end) - D("1.1375")) < D("1e-9")
    assert p.cdi_aa(TODAY) == D("0.1365")
    assert IndexPath.pre_factor(D("0.10"), TODAY, end) == D("1.10")


def test_interpolation():
    snap = flat_snapshot().model_copy(update={"focus_selic_anual": {2026: D("0.1375"), 2027: D("0.1275")}})
    p = IndexPath.build(snap, Settings(), cal, TODAY)
    assert p.selic_aa(date(2027, 12, 31)) == D("0.1275")
    assert D("0.1275") < p.selic_aa(date(2027, 7, 1)) < D("0.1375")
    assert p.selic_aa(date(2045, 1, 1)) == D("0.1275")  # Review Focus 3
    assert p.selic_aa(date(2020, 1, 1)) == D("0.1375")


def test_ipca_monthly_overrides_annual():
    snap = flat_snapshot().model_copy(update={"focus_ipca_mensal": {"2026-12": D("0.0050")}})
    p = IndexPath.build(snap, Settings(), cal, TODAY)
    assert p.ipca_month(2026, 12) == D("0.0050")
    assert abs(p.ipca_month(2027, 3) - (D("1.045") ** (D(1) / 12) - 1)) < D("1e-12")
    assert abs(p.ipca_month(2040, 3) - (D("1.045") ** (D(1) / 12) - 1)) < D("1e-12")
    assert abs(p.ipca_factor(date(2026, 11, 30), date(2026, 12, 31)) - D("1.0050")) < D("1e-9")


def test_manual_mode_and_missing():
    s = Settings(projection_mode="manual", manual_selic_by_year={2027: D("0.10")}, manual_ipca_by_year={2027: D("0.04")})
    p = IndexPath.build(flat_snapshot(), s, cal, TODAY)
    assert p.fonte == "Cenário manual"
    assert p.selic_aa(date(2027, 12, 31)) == D("0.10")
    assert abs(p.ipca_month(2027, 1) - (D("1.04") ** (D(1) / 12) - 1)) < D("1e-12")
    assert IndexPath.build(MarketSnapshot.empty(), s, cal, TODAY) is not None
    assert IndexPath.build(MarketSnapshot.empty(), Settings(), cal, TODAY) is None


def test_fonte_and_yearly_table():
    p = IndexPath.build(flat_snapshot(), Settings(), cal, TODAY)
    assert p.fonte == "Focus 13/11/2026"
    table = p.yearly_table()
    assert [r[0] for r in table] == [2026, 2027]
    assert table[0][1] == D("0.1375")
    assert abs(table[0][2] - D("0.045")) < D("1e-9")


def test_no_ipca_data_raises():
    snap = flat_snapshot().model_copy(update={"focus_ipca_anual": {}})
    p = IndexPath.build(snap, Settings(), cal, TODAY)
    with pytest.raises(ValueError, match="sem projeção de IPCA"):
        p.ipca_month(2027, 1)
