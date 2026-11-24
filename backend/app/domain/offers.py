from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import TYPE_CHECKING

from app.domain.products.base import Alert, AlertCode, ProductData

if TYPE_CHECKING:
    from app.domain.settings import Settings

_JUROS = {"MENSAL": "mensais", "TRIMESTRAL": "trimestrais", "SEMESTRAL": "semestrais", "ANUAL": "anuais"}
_EMISSOR_TOKENS = {"s.a.", "s.a", "s/a", "sa", "banco", "ltda"}


def ages(data: ProductData) -> bool:
    """O produto envelhece? Exemplos e Tesouro nunca envelhecem."""
    return not data.exemplo and not data.tipo.value.startswith("TESOURO_")


def offer_age_days(data: ProductData, today: date) -> int | None:
    if not ages(data) or data.data_registro is None:
        return None
    return (today - data.data_registro).days


def is_expired(data: ProductData, settings: Settings, today: date) -> bool:
    if not ages(data):
        return False
    if data.disponivel_ate is not None and today > data.disponivel_ate:
        return True
    idade = offer_age_days(data, today)
    return idade is not None and idade >= settings.oferta_expira_dias


def offer_alerts(data: ProductData, settings: Settings, today: date) -> list[Alert]:
    alertas: list[Alert] = []
    if data.juros_periodicos is not None:
        alertas.append(
            Alert(
                code=AlertCode.MODELO_SIMPLIFICADO,
                message=(
                    f"Paga juros {_JUROS[data.juros_periodicos]}; "
                    "calculado como se pagasse tudo no vencimento"
                ),
            )
        )
    elif data.amortizacao is not None:
        alertas.append(
            Alert(
                code=AlertCode.MODELO_SIMPLIFICADO,
                message="Amortiza em parcelas; calculado como se pagasse tudo no vencimento",
            )
        )
    idade = offer_age_days(data, today)
    if idade is not None and idade >= settings.oferta_alerta_dias:
        alertas.append(
            Alert(
                code=AlertCode.OFERTA_ANTIGA,
                message=f"Oferta registrada há {idade} dias — confira se ainda está disponível",
            )
        )
    if data.origem == "IA":
        alertas.append(Alert(code=AlertCode.IMPORTADO_IA, message="Importado por IA de um print"))
    return alertas


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch)).lower()


def normalize_emissor(s: str) -> str:
    s = _fold(s).replace("…", " ").replace("...", " ")
    tokens = [t for t in s.split() if t not in _EMISSOR_TOKENS]
    tokens = [t.strip(".,;:-") for t in tokens]
    return re.sub(r"\s+", " ", " ".join(t for t in tokens if t)).strip()


def normalize_plataforma(s: str) -> str:
    s = re.sub(r"\s+", " ", _fold(s)).strip()
    return "btg" if s == "btg pactual" else s


def offer_key(data: ProductData) -> tuple:
    return (
        data.tipo,
        normalize_plataforma(data.plataforma),
        data.indexador,
        data.taxa.normalize(),
        data.data_vencimento,
        normalize_emissor(data.emissor),
    )


__all__ = [
    "ages", "is_expired", "normalize_emissor", "normalize_plataforma",
    "offer_age_days", "offer_alerts", "offer_key",
]
