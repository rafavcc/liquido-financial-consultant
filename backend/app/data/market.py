import logging
from collections.abc import Callable
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

import httpx
from pydantic import BaseModel
from pydantic_core import to_jsonable_python

from app.data import bcb, focus, tesouro
from app.data.repositories import MarketCacheRepository
from app.data.tesouro import TesouroQuote

log = logging.getLogger(__name__)

FAILURE_COOLDOWN = timedelta(minutes=15)
HTTP_TIMEOUT = httpx.Timeout(15.0)
TESOURO_TIMEOUT = httpx.Timeout(90.0)

SOURCES = ("bcb", "focus", "tesouro")

# "ultimos/N" não serve: a 432 é diária, traz ~20 dias futuros (N<=20 só devolve futuro, N>=25 dá 400,
# N=5 dá 304 sem corpo). Usa-se janela de datas; latest_until escolhe o ponto <= hoje.
SGS_PAST_DAYS = 120  # 13522 é mensal: precisa de folga para achar o último ponto
SGS_FUTURE_DAYS = 30
SGS_URL = (
    "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
    "?formato=json&dataInicial={inicio}&dataFinal={fim}"
)
FOCUS_BASE = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
TESOURO_URL = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3"
    "/resource/796d2059-14e9-44e3-80c9-2d9e30b405c1/download/PrecoTaxaTesouroDireto.csv"
)

FIXTURE_FILES = {
    "sgs_432": "sgs_432.json",
    "sgs_13522": "sgs_13522.json",
    "focus_selic": "focus_anual_selic.json",
    "focus_ipca": "focus_anual_ipca.json",
    "focus_ipca_mensal": "focus_mensal_ipca.json",
    "tesouro": "tesouro.csv",
}


def sgs_url(codigo: int, today: date) -> str:
    # dataFinal = hoje + folga: a série pode ter pontos futuros, que latest_until ignora
    fmt = "%d/%m/%Y"
    return SGS_URL.format(
        codigo=codigo,
        inicio=(today - timedelta(days=SGS_PAST_DAYS)).strftime(fmt),
        fim=(today + timedelta(days=SGS_FUTURE_DAYS)).strftime(fmt),
    )


class MarketSnapshot(BaseModel):
    selic_meta: Decimal | None = None
    selic_meta_data: date | None = None
    ipca_12m: Decimal | None = None
    ipca_12m_ref: date | None = None
    focus_data: date | None = None
    focus_selic_anual: dict[int, Decimal] = {}
    focus_ipca_anual: dict[int, Decimal] = {}
    focus_ipca_mensal: dict[str, Decimal] = {}
    tesouro: list[TesouroQuote] = []
    tesouro_data_base: date | None = None
    fetched_at: dict[str, datetime] = {}
    errors: dict[str, str] = {}

    @classmethod
    def empty(cls) -> "MarketSnapshot":
        return cls()


class MarketFetchers(Protocol):
    def fetch_bcb(self, today: date) -> dict: ...
    def fetch_focus(self) -> dict: ...
    def fetch_tesouro(self) -> dict: ...


# --- construção dos pedaços de snapshot a partir dos textos brutos ---


def build_bcb(sgs_432: str, sgs_13522: str, today: date) -> dict:
    selic = bcb.latest_until(bcb.parse_sgs(sgs_432), today)
    ipca = bcb.latest_until(bcb.parse_sgs(sgs_13522), today)
    return {
        "selic_meta": selic.valor / 100,
        "selic_meta_data": selic.data,
        "ipca_12m": ipca.valor / 100,
        "ipca_12m_ref": ipca.data,
    }


def build_focus(selic_anual: str, ipca_anual: str, ipca_mensal: str) -> dict:
    data, selic = focus.parse_annual(selic_anual)
    _, ipca = focus.parse_annual(ipca_anual)
    _, mensal = focus.parse_monthly(ipca_mensal)
    return {
        "focus_data": data,
        "focus_selic_anual": selic,
        "focus_ipca_anual": ipca,
        "focus_ipca_mensal": mensal,
    }


def build_tesouro(csv_text: str) -> dict:
    quotes = tesouro.parse_latest(csv_text)
    if not quotes:
        raise ValueError("CSV do Tesouro sem cotações")
    return {"tesouro": quotes, "tesouro_data_base": quotes[0].data_base}


def focus_url(resource: str, indicador: str, top: int) -> str:
    """URL OData montada à mão: o Olinda rejeita `$` e espaços codificados pelo httpx (%24, +)."""
    filt = quote(f"Indicador eq '{indicador}' and baseCalculo eq 0", safe="")
    return f"{FOCUS_BASE}{resource}?$format=json&$filter={filt}&$orderby=Data%20desc&$top={top}"


class HttpFetchers:
    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def _get(self, url: str, timeout: httpx.Timeout = HTTP_TIMEOUT) -> httpx.Response:
        resp = self._client.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp

    def _sgs(self, codigo: int, today: date) -> str:
        return self._get(sgs_url(codigo, today)).text

    def _focus(self, resource: str, indicador: str, top: int) -> str:
        return self._get(focus_url(resource, indicador, top)).text

    def fetch_bcb(self, today: date) -> dict:
        return build_bcb(self._sgs(432, today), self._sgs(13522, today), today)

    def fetch_focus(self) -> dict:
        return build_focus(
            self._focus("ExpectativasMercadoAnuais", "Selic", 100),
            self._focus("ExpectativasMercadoAnuais", "IPCA", 100),
            self._focus("ExpectativaMercadoMensais", "IPCA", 200),
        )

    def fetch_tesouro(self) -> dict:
        return build_tesouro(tesouro.decode_csv(self._get(TESOURO_URL, TESOURO_TIMEOUT).content))


class FixtureFetchers:
    def __init__(self, dir: Path) -> None:
        self._dir = dir

    def _read(self, key: str) -> str:
        return (self._dir / FIXTURE_FILES[key]).read_text(encoding="utf-8")

    def fetch_bcb(self, today: date) -> dict:
        return build_bcb(self._read("sgs_432"), self._read("sgs_13522"), today)

    def fetch_focus(self) -> dict:
        return build_focus(
            self._read("focus_selic"), self._read("focus_ipca"), self._read("focus_ipca_mensal")
        )

    def fetch_tesouro(self) -> dict:
        return build_tesouro(self._read("tesouro"))


def describe_error(exc: Exception) -> str:
    """Mensagem curta em pt-BR para a UI; o texto cru da exceção fica só nos logs."""
    if isinstance(exc, httpx.TimeoutException):
        return "Tempo esgotado"
    if isinstance(exc, httpx.HTTPStatusError):
        return f"A fonte respondeu com erro ({exc.response.status_code})"
    if isinstance(exc, httpx.TransportError):
        return "Sem conexão com a fonte"
    if isinstance(exc, (ValueError, KeyError, TypeError, InvalidOperation)):  # inclui JSONDecodeError
        return "Resposta inválida da fonte"
    return "Erro inesperado ao atualizar"


class MarketService:
    def __init__(
        self,
        cache: MarketCacheRepository,
        fetchers: MarketFetchers,
        now: Callable[[], datetime],
    ) -> None:
        self._cache = cache
        self._fetchers = fetchers
        self._now = now

    def _fetch(self, source: str, now: datetime) -> dict:
        if source == "bcb":
            return self._fetchers.fetch_bcb(now.date())
        if source == "focus":
            return self._fetchers.fetch_focus()
        return self._fetchers.fetch_tesouro()

    def get_snapshot(self, ttl_hours: int, force: bool = False) -> MarketSnapshot:
        now = self._now()
        fields: dict = {}
        fetched_at: dict[str, datetime] = {}
        errors: dict[str, str] = {}
        for source in SOURCES:
            entry = self._cache.load(source)
            fresh = (
                entry is not None
                and entry.payload is not None
                and entry.fetched_at is not None
                and (now - entry.fetched_at).total_seconds() < ttl_hours * 3600
            )
            payload = entry.payload if entry else None
            stamp = entry.fetched_at if entry else None
            cooling = (
                not force
                and entry is not None
                and entry.failed_at is not None
                and now - entry.failed_at < FAILURE_COOLDOWN
            )
            if cooling:
                errors[source] = entry.error or "falha recente"
            elif force or not fresh:
                try:
                    payload = to_jsonable_python(self._fetch(source, now))
                    stamp = now
                    self._cache.save(source, payload, now)
                except Exception as exc:  # noqa: BLE001 - qualquer falha de fonte vira erro registrado
                    log.warning("Falha ao atualizar a fonte %s: %s: %s", source, type(exc).__name__, exc)
                    message = describe_error(exc)
                    self._cache.save_error(source, message, now)
                    errors[source] = message
            if payload is not None:
                fields.update(payload)
                if stamp is not None:
                    fetched_at[source] = stamp
        return MarketSnapshot(**fields, fetched_at=fetched_at, errors=errors)
