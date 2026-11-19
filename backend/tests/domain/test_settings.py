from decimal import Decimal as D

import pytest
from pydantic import ValidationError

from app.domain.settings import IrBracket, Settings


def test_defaults():
    s = Settings()
    assert len(s.iof_table) == 29
    assert s.ir_brackets[-1].max_days is None
    assert s.fgc_limite == D("250000")


def test_settings_validation():
    with pytest.raises(ValidationError):
        Settings(custodia_b3_aa=D("-0.01"))
    with pytest.raises(ValidationError):
        Settings(ir_brackets=[IrBracket(max_days=360, rate=D("0.2")), IrBracket(max_days=180, rate=D("0.2")), IrBracket(max_days=None, rate=D("0.15"))])
    with pytest.raises(ValidationError):
        Settings(ir_brackets=[IrBracket(max_days=180, rate=D("0.2"))])
    with pytest.raises(ValidationError):
        Settings(iof_table=[D("0.5")] * 28)
    with pytest.raises(ValidationError):
        Settings(iof_table=[D("0.1"), D("0.2")] + [D("0.1")] * 27)
    with pytest.raises(ValidationError):
        Settings(market_cache_ttl_hours=0)
    with pytest.raises(ValidationError):
        Settings(projection_mode="manual")
    with pytest.raises(ValidationError):
        Settings(come_cotas_curto=D("1.5"))
    ok = Settings(projection_mode="manual", manual_selic_by_year={2027: D("0.12")}, manual_ipca_by_year={2027: D("0.04")})
    assert ok.projection_mode == "manual"


def test_json_roundtrip_decimals_as_strings():
    s = Settings()
    assert Settings.model_validate_json(s.model_dump_json()) == s
    assert '"0.225"' in s.model_dump_json()


def test_curto_fund_ir_rates_default_and_validation():
    s = Settings()
    assert s.ir_fundo_curto_ate_180 == D("0.225") and s.ir_fundo_curto_acima_180 == D("0.20")
    for campo in ("ir_fundo_curto_ate_180", "ir_fundo_curto_acima_180"):
        with pytest.raises(ValueError):
            Settings(**{campo: D("1.5")})
