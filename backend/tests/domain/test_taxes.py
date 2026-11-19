from decimal import Decimal as D

from app.domain.products.base import ProductType
from app.domain.settings import Settings
from app.domain.taxes import TaxBreakdown, apply_taxes, iof_rate, ir_rate


def test_ir_brackets():
    s = Settings()
    assert [ir_rate(d, s) for d in (1, 180, 181, 360, 361, 720, 721, 5000)] == \
        [D("0.225"), D("0.225"), D("0.20"), D("0.20"), D("0.175"), D("0.175"), D("0.15"), D("0.15")]


def test_iof():
    s = Settings()
    assert iof_rate(1, s) == D("0.96") and iof_rate(29, s) == D("0.03") and iof_rate(30, s) == 0
    assert iof_rate(0, s) == D("0.96")


def test_apply_taxes_cdb_and_exempt():
    s = Settings()
    assert apply_taxes(D("1000"), 10, ProductType.CDB, s) == TaxBreakdown(iof=D("660.00"), ir=D("76.50"))
    assert apply_taxes(D("1511.00"), 365, ProductType.CDB, s) == TaxBreakdown(iof=D("0.00"), ir=D("264.42"))
    assert apply_taxes(D("1000"), 10, ProductType.LCI, s) == TaxBreakdown(iof=D("0"), ir=D("0"))
    assert apply_taxes(D("-5"), 400, ProductType.CDB, s) == TaxBreakdown(iof=D("0"), ir=D("0"))
    assert apply_taxes(D("0"), 400, ProductType.CDB, s) == TaxBreakdown(iof=D("0"), ir=D("0"))


def test_apply_taxes_rounds_half_even():
    s = Settings()
    # dias=800 -> IR 15%: 0.50*0.15=0.075 -> 0.08 (half-even)
    assert apply_taxes(D("0.50"), 800, ProductType.CDB, s).ir == D("0.08")
    # 0.30*0.15 = 0.045 -> 0.04 (half-even)
    assert apply_taxes(D("0.30"), 800, ProductType.CDB, s).ir == D("0.04")
