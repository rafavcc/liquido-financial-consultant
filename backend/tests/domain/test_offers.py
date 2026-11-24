from datetime import date, timedelta
from decimal import Decimal as D

import pytest

from app.domain.offers import (
    is_expired,
    offer_age_days,
    offer_alerts,
    offer_key,
)
from app.domain.products.base import AlertCode
from app.domain.settings import Settings
from tests.domain.products.product_helpers import make

T = date(2026, 11, 23)


def codes(alerts):
    return {a.code for a in alerts}


def p(d):
    return make(data_registro=T - timedelta(days=d))


def test_age_boundaries():
    s = Settings()
    assert not offer_alerts(p(13), s, T)
    assert codes(offer_alerts(p(14), s, T)) == {AlertCode.OFERTA_ANTIGA}
    assert not is_expired(p(27), s, T)
    assert is_expired(p(28), s, T)


def test_disponivel_ate_expires_earlier():
    assert is_expired(make(data_registro=T, disponivel_ate=T - timedelta(days=1)), Settings(), T)
    assert not is_expired(make(data_registro=T, disponivel_ate=T), Settings(), T)


def test_examples_and_no_date_never_age():
    assert not is_expired(make(exemplo=True, data_registro=T - timedelta(days=99)), Settings(), T)
    assert offer_age_days(make(data_registro=None), T) is None
    assert not is_expired(make(data_registro=None), Settings(), T)


def test_simplified_alert_for_coupons():
    alerts = offer_alerts(make(juros_periodicos="SEMESTRAL"), Settings(), T)
    assert AlertCode.MODELO_SIMPLIFICADO in codes(alerts)
    assert "semestrais" in alerts[0].message


def test_simplified_alert_for_amortization_only():
    a = offer_alerts(make(amortizacao={"periodicidade": "MENSAL", "inicio": "2028-01-01"}), Settings(), T)
    assert a[0].message.startswith("Amortiza em parcelas")


def test_imported_alert():
    assert AlertCode.IMPORTADO_IA in codes(offer_alerts(make(origem="IA"), Settings(), T))


def test_offer_key_normalizes():
    a = make(emissor="BANCO COOPERATIVO SIC...", plataforma="BTG Pactual")
    b = make(emissor="Banco Cooperativo Sic", plataforma="BTG")
    assert offer_key(a) == offer_key(b)
    assert offer_key(make(taxa=D("0.90"))) == offer_key(make(taxa=D("0.9000")))


def test_settings_validation_alert_before_expiry():
    with pytest.raises(ValueError):
        Settings(oferta_alerta_dias=28, oferta_expira_dias=28)
    with pytest.raises(ValueError):
        Settings(oferta_alerta_dias=0)
