from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field, model_validator

from app.domain.calendar import BusinessCalendar

if TYPE_CHECKING:  # settings importa ProductType deste módulo; evita ciclo
    from app.domain.indexes import IndexPath
    from app.domain.settings import Settings

_ZERO = Decimal(0)


class ProductType(StrEnum):
    CDB = "CDB"
    LCI = "LCI"
    LCA = "LCA"
    CRI = "CRI"
    CRA = "CRA"
    TESOURO_SELIC = "TESOURO_SELIC"
    TESOURO_PREFIXADO = "TESOURO_PREFIXADO"
    TESOURO_PREFIXADO_JUROS = "TESOURO_PREFIXADO_JUROS"
    TESOURO_IPCA = "TESOURO_IPCA"
    TESOURO_IPCA_JUROS = "TESOURO_IPCA_JUROS"
    TESOURO_RENDA_MAIS = "TESOURO_RENDA_MAIS"
    TESOURO_EDUCA_MAIS = "TESOURO_EDUCA_MAIS"
    FUNDO_RF = "FUNDO_RF"


class Indexer(StrEnum):
    PRE = "PRE"
    PCT_CDI = "PCT_CDI"
    CDI_MAIS = "CDI_MAIS"
    IPCA_MAIS = "IPCA_MAIS"
    SELIC = "SELIC"


class Liquidity(StrEnum):
    NO_VENCIMENTO = "NO_VENCIMENTO"
    DIARIA = "DIARIA"
    DIARIA_APOS_CARENCIA = "DIARIA_APOS_CARENCIA"


class Coverage(StrEnum):
    FGC = "FGC"
    TESOURO = "TESOURO"
    NENHUMA = "NENHUMA"


class Section(StrEnum):
    VENCE_ATE_DATA = "VENCE_ATE_DATA"
    VENCE_DEPOIS = "VENCE_DEPOIS"
    INDISPONIVEL = "INDISPONIVEL"


class AlertCode(StrEnum):
    PROJECAO = "PROJECAO"
    FGC_LIMITE = "FGC_LIMITE"
    SEM_FGC = "SEM_FGC"
    ESTIMATIVA_MERCADO = "ESTIMATIVA_MERCADO"
    FUNDO_SEM_GARANTIA = "FUNDO_SEM_GARANTIA"
    PARADO = "PARADO"
    EXEMPLO = "EXEMPLO"
    MODELO_SIMPLIFICADO = "MODELO_SIMPLIFICADO"
    ABAIXO_MINIMO = "ABAIXO_MINIMO"
    NAO_RESGATAVEL = "NAO_RESGATAVEL"
    SEM_DADOS_MERCADO = "SEM_DADOS_MERCADO"
    RESGATE_DN = "RESGATE_DN"
    ERRO_CALCULO = "ERRO_CALCULO"


_DEFAULT_COVERAGE = {
    ProductType.CDB: Coverage.FGC,
    ProductType.LCI: Coverage.FGC,
    ProductType.LCA: Coverage.FGC,
    ProductType.CRI: Coverage.NENHUMA,
    ProductType.CRA: Coverage.NENHUMA,
    ProductType.FUNDO_RF: Coverage.NENHUMA,
}


class ProductData(BaseModel):
    id: str
    tipo: ProductType
    nome: str
    emissor: str
    plataforma: str
    indexador: Indexer
    taxa: Decimal
    data_vencimento: date | None = None
    valor_minimo: Decimal = _ZERO
    liquidez: Liquidity = Liquidity.NO_VENCIMENTO
    data_carencia: date | None = None
    cobertura: Coverage | None = None
    ativo: bool = True
    exemplo: bool = False
    observacoes: str = ""
    taxa_adm: Decimal | None = None
    prazo_resgate_dias: int | None = None
    classe_tributaria: Literal["LONGO", "CURTO"] | None = None

    @model_validator(mode="after")
    def _fill_coverage(self) -> ProductData:
        if self.cobertura is None:
            self.cobertura = (
                Coverage.TESOURO
                if self.tipo.value.startswith("TESOURO_")
                else _DEFAULT_COVERAGE[self.tipo]
            )
        return self


class Alert(BaseModel):
    code: AlertCode
    message: str


class SeriePoint(BaseModel):
    data: date
    valor_bruto: Decimal


class SimulationResult(BaseModel):
    product: ProductData
    secao: Section
    resgatavel: bool
    estimativa_mercado: bool = False
    data_saida: date | None = None
    dias_parado: int = 0
    valor_investido: Decimal = _ZERO
    valor_bruto: Decimal | None = None
    iof: Decimal = _ZERO
    ir: Decimal = _ZERO
    custodia: Decimal = _ZERO
    come_cotas: Decimal = _ZERO
    taxa_adm: Decimal = _ZERO
    valor_liquido: Decimal | None = None
    rentab_liquida: Decimal | None = None
    taxa_liquida_aa: Decimal | None = None
    data_solicitacao_resgate: date | None = None
    alertas: list[Alert] = Field(default_factory=list)
    serie: list[SeriePoint] = Field(default_factory=list)


@dataclass
class SimContext:
    today: date
    cal: BusinessCalendar
    settings: Settings
    index: IndexPath | None


def brl(value: Decimal) -> str:
    """R$ 1.234,56 (sem centavos quando inteiro)."""
    places = 0 if value == value.to_integral_value() else 2
    text = f"{value:,.{places}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {text}"


class Product(ABC):
    def __init__(self, data: ProductData) -> None:
        self.data = data

    @abstractmethod
    def simulate(self, valor: Decimal, data_alvo: date, ctx: SimContext) -> SimulationResult: ...

    def _unavailable(
        self, valor: Decimal, code: AlertCode, message: str, ctx: SimContext
    ) -> SimulationResult:
        alertas = [Alert(code=code, message=message)]
        if self.data.exemplo:
            alertas.append(Alert(code=AlertCode.EXEMPLO, message="Produto fictício (exemplo)"))
        return SimulationResult(
            product=self.data,
            secao=Section.INDISPONIVEL,
            resgatavel=False,
            valor_investido=valor,
            alertas=alertas,
        )

    def _common_alerts(
        self, valor: Decimal, ctx: SimContext, projecao: bool = True
    ) -> list[Alert]:
        from app.domain.products.accrual import needs_index

        d = self.data
        alertas: list[Alert] = []
        if projecao and needs_index(d.indexador) and ctx.index is not None:
            nome = {"PCT_CDI": "CDI", "CDI_MAIS": "CDI", "IPCA_MAIS": "IPCA", "SELIC": "Selic"}[
                d.indexador.value
            ]
            alertas.append(
                Alert(
                    code=AlertCode.PROJECAO,
                    message=f"Depende de projeção de {nome} ({ctx.index.fonte})",
                )
            )
        limite = ctx.settings.fgc_limite
        if d.cobertura == Coverage.FGC and valor > limite:
            alertas.append(
                Alert(
                    code=AlertCode.FGC_LIMITE,
                    message=f"Valor acima do limite do FGC ({brl(limite)})",
                )
            )
        if d.cobertura == Coverage.NENHUMA:
            alertas.append(Alert(code=AlertCode.SEM_FGC, message="Sem cobertura do FGC"))
        if d.exemplo:
            alertas.append(Alert(code=AlertCode.EXEMPLO, message="Produto fictício (exemplo)"))
        return alertas

    @staticmethod
    def _net_annual_rate(
        valor: Decimal, liquido: Decimal, start: date, end: date, cal: BusinessCalendar
    ) -> Decimal | None:
        du = cal.business_days_between(start, end)
        if du == 0 or valor <= 0:
            return None
        return (liquido / valor) ** (Decimal(252) / Decimal(du)) - 1

    @staticmethod
    def _series_dates(start: date, end: date, cal: BusinessCalendar) -> list[date]:
        """Último dia útil de cada mês em (start, end) e, ao final, `end`."""
        pontos: list[date] = []
        y, m = start.year, start.month
        while True:
            eom = cal.last_business_day_of_month(y, m)
            if eom >= end:
                break
            if eom > start:
                pontos.append(eom)
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        pontos.append(end)
        return pontos
