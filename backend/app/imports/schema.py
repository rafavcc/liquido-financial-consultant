from __future__ import annotations

from pydantic import BaseModel, Field


class RawRate(BaseModel):
    rotulo: str = Field("", description="rótulo ou cabeçalho da coluna, ex.: Taxa, Taxa eq. CDB")
    texto: str = Field(description="o valor como aparece, ex.: 90,00% do CDI")


class RawOffer(BaseModel):
    tipo: str
    emissor: str | None = None
    nome_exibido: str | None = None
    taxas: list[RawRate] = []
    vencimento: str | None = None
    aplicacao_minima: str | None = None
    liquidez: str | None = None
    carencia: str | None = None
    disponivel_ate: str | None = None
    codigo: str | None = None
    juros: str | None = None
    amortizacao: str | None = None
    cortada: bool = False


class RawExtraction(BaseModel):
    plataforma: str = "DESCONHECIDA"
    ofertas: list[RawOffer] = []


EXTRACTION_JSON_SCHEMA: dict = RawExtraction.model_json_schema()
