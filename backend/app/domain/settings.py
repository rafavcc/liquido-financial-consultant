from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

from app.domain.products.base import Indexer, ProductType

D = Decimal

_ISENTOS = {ProductType.LCI, ProductType.LCA, ProductType.LCD, ProductType.CRI, ProductType.CRA}


def _default_ir_brackets() -> list["IrBracket"]:
    return [
        IrBracket(max_days=180, rate=D("0.225")),
        IrBracket(max_days=360, rate=D("0.20")),
        IrBracket(max_days=720, rate=D("0.175")),
        IrBracket(max_days=None, rate=D("0.15")),
    ]


_IOF_TABLE = [
    D(x) for x in (
        "0.96 0.93 0.90 0.86 0.83 0.80 0.76 0.73 0.70 0.66 "
        "0.63 0.60 0.56 0.53 0.50 0.46 0.43 0.40 0.36 0.33 "
        "0.30 0.26 0.23 0.20 0.16 0.13 0.10 0.06 0.03"
    ).split()
]


def _check_rate(value: Decimal, name: str) -> None:
    if not (D(0) <= value <= D(1)):
        raise ValueError(f"{name} deve estar entre 0 e 1")


class IrBracket(BaseModel):
    max_days: int | None
    rate: Decimal


class Settings(BaseModel):
    ir_brackets: list[IrBracket] = Field(default_factory=_default_ir_brackets)
    iof_table: list[Decimal] = Field(default_factory=lambda: list(_IOF_TABLE))
    ir_exempt_types: set[ProductType] = Field(default_factory=lambda: set(_ISENTOS))
    iof_exempt_types: set[ProductType] = Field(default_factory=lambda: set(_ISENTOS))
    come_cotas_longo: Decimal = D("0.15")
    come_cotas_curto: Decimal = D("0.20")
    ir_fundo_curto_ate_180: Decimal = D("0.225")  # fundos de curto prazo: 22,5% até 180 dias
    ir_fundo_curto_acima_180: Decimal = D("0.20")  # e 20% depois
    custodia_b3_aa: Decimal = D("0.0020")
    tesouro_selic_isencao_custodia: Decimal = D("10000")
    spread_cdi_selic: Decimal = D("0.0010")
    projection_mode: Literal["focus", "manual"] = "focus"
    manual_selic_by_year: dict[int, Decimal] = Field(default_factory=dict)
    manual_ipca_by_year: dict[int, Decimal] = Field(default_factory=dict)
    market_cache_ttl_hours: int = 6
    fgc_limite: Decimal = D("250000")
    prazo_min_meses_lci: int = 6
    prazo_min_meses_lci_ipca: int = 36
    prazo_min_meses_lca: int = 6
    prazo_min_meses_lca_ipca: int = 12
    prazo_min_meses_lcd: int = 12
    # expira antes de alerta: o validador de alerta precisa ver a expiração já validada.
    oferta_expira_dias: int = 28
    oferta_alerta_dias: int = 14

    @field_validator("oferta_alerta_dias")
    @classmethod
    def _alerta_antes_da_expiracao(cls, v: int, info: ValidationInfo) -> int:
        expira = info.data.get("oferta_expira_dias")
        if v < 1 or (expira is not None and v >= expira):
            raise ValueError("o alerta de oferta antiga deve vir antes da expiração")
        return v

    @model_validator(mode="after")
    def _validate(self) -> "Settings":
        for b in self.ir_brackets:
            _check_rate(b.rate, "alíquota de IR")
        days = [b.max_days for b in self.ir_brackets]
        if not days or days[-1] is not None:
            raise ValueError("a última faixa de IR deve ter max_days nulo")
        finite = days[:-1]
        if any(d is None for d in finite) or any(a >= b for a, b in zip(finite, finite[1:])):
            raise ValueError("max_days das faixas de IR deve ser estritamente crescente")

        if len(self.iof_table) != 29:
            raise ValueError("iof_table deve ter exatamente 29 itens")
        for r in self.iof_table:
            _check_rate(r, "alíquota de IOF")
        if any(a < b for a, b in zip(self.iof_table, self.iof_table[1:])):
            raise ValueError("iof_table deve ser não crescente")

        for name in (
            "come_cotas_longo", "come_cotas_curto", "ir_fundo_curto_ate_180", "ir_fundo_curto_acima_180", "custodia_b3_aa", "spread_cdi_selic",
        ):
            _check_rate(getattr(self, name), name)

        for name in (
            "prazo_min_meses_lci", "prazo_min_meses_lci_ipca", "prazo_min_meses_lca",
            "prazo_min_meses_lca_ipca", "prazo_min_meses_lcd",
        ):
            if getattr(self, name) < 0:
                raise ValueError("prazo mínimo não pode ser negativo")

        if self.market_cache_ttl_hours < 1:
            raise ValueError("market_cache_ttl_hours deve ser >= 1")
        if self.projection_mode == "manual" and not (self.manual_selic_by_year and self.manual_ipca_by_year):
            raise ValueError("modo manual exige ao menos um ano de Selic e de IPCA")
        return self

    def prazo_minimo_meses(self, tipo: ProductType, indexador: Indexer) -> int | None:
        ipca = indexador == Indexer.IPCA_MAIS
        if tipo == ProductType.LCI:
            return self.prazo_min_meses_lci_ipca if ipca else self.prazo_min_meses_lci
        if tipo == ProductType.LCA:
            return self.prazo_min_meses_lca_ipca if ipca else self.prazo_min_meses_lca
        if tipo == ProductType.LCD:
            return self.prazo_min_meses_lcd
        return None
