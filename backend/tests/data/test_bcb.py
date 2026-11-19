from datetime import date
from decimal import Decimal as D
from pathlib import Path

from app.data.bcb import SgsPoint, latest_until, parse_sgs

FIX = Path(__file__).parent.parent / "fixtures" / "market"


def test_sgs_future_point_ignored():
    pts = parse_sgs('[{"data":"18/11/2026","valor":"13.75"},{"data":"09/12/2026","valor":"13.75"}]')
    assert latest_until(pts, date(2026, 11, 19)) == SgsPoint(data=date(2026, 11, 18), valor=D("13.75"))
    assert latest_until(pts[1:], date(2026, 11, 19)).data == date(2026, 12, 9)


def test_sgs_recorded_fixture_parses_percent_raw():
    pts = parse_sgs((FIX / "sgs_432.json").read_text(encoding="utf-8"))
    assert pts and all(isinstance(p.valor, D) for p in pts)
    assert latest_until(pts, date(2026, 11, 19)).data <= date(2026, 11, 19)
