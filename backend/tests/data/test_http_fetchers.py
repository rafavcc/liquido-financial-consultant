from datetime import date
from decimal import Decimal as D
from pathlib import Path

import httpx

from app.data.market import HttpFetchers, TESOURO_URL, focus_url, sgs_url

FIX = Path(__file__).parent.parent / "fixtures" / "market"
TODAY = date(2026, 11, 19)


def _fetchers(responses: dict[str, str]):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        for prefix, fixture in responses.items():
            if str(request.url).startswith(prefix):
                return httpx.Response(200, content=(FIX / fixture).read_bytes())
        return httpx.Response(404)

    return HttpFetchers(httpx.Client(transport=httpx.MockTransport(handler))), seen


def test_sgs_url_date_window():
    assert sgs_url(432, TODAY) == (
        "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados"
        "?formato=json&dataInicial=22/07/2026&dataFinal=19/12/2026"
    )


def test_focus_url_manual_encoding():
    assert focus_url("ExpectativasMercadoAnuais", "Selic", 100) == (
        "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais"
        "?$format=json&$filter=Indicador%20eq%20%27Selic%27%20and%20baseCalculo%20eq%200"
        "&$orderby=Data%20desc&$top=100"
    )


def test_fetch_bcb_requests_and_parses():
    f, seen = _fetchers({sgs_url(432, TODAY): "sgs_432.json", sgs_url(13522, TODAY): "sgs_13522.json"})
    out = f.fetch_bcb(TODAY)
    assert [str(r.url) for r in seen] == [sgs_url(432, TODAY), sgs_url(13522, TODAY)]
    assert out["selic_meta"] == D("0.1375")
    assert out["ipca_12m_ref"] <= TODAY


def test_fetch_focus_requests_and_parses():
    urls = {
        focus_url("ExpectativasMercadoAnuais", "Selic", 100): "focus_anual_selic.json",
        focus_url("ExpectativasMercadoAnuais", "IPCA", 100): "focus_anual_ipca.json",
        focus_url("ExpectativaMercadoMensais", "IPCA", 200): "focus_mensal_ipca.json",
    }
    f, seen = _fetchers(urls)
    out = f.fetch_focus()
    assert [str(r.url) for r in seen] == list(urls)
    assert out["focus_data"] == date(2026, 11, 13)
    assert out["focus_selic_anual"][2026] == D("0.1375")
    assert out["focus_ipca_mensal"]


def test_fetch_tesouro_requests_and_parses():
    f, seen = _fetchers({TESOURO_URL: "tesouro.csv"})
    out = f.fetch_tesouro()
    assert str(seen[0].url) == TESOURO_URL
    assert out["tesouro"] and out["tesouro_data_base"] == out["tesouro"][0].data_base


def test_explicit_timeouts_per_request():
    f, seen = _fetchers({TESOURO_URL: "tesouro.csv", "https://api.bcb.gov.br": "sgs_432.json"})
    f.fetch_tesouro()
    assert seen[0].extensions["timeout"]["read"] == 90.0
    f.fetch_bcb(TODAY)
    assert seen[1].extensions["timeout"]["read"] == 15.0
