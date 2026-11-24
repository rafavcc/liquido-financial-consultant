from decimal import Decimal as D

from app.domain.calendar import get_calendar
from app.domain.horizon import anos_a_frente
from tests.api.conftest import TODAY


def _post(client, **body):
    return client.post("/api/simulate", json={"valor": "50000", **body})


def test_um_e_dois_anos_resolvem_a_data(client_fixtures):
    cal = get_calendar()
    for h, anos in (("UM_ANO", 1), ("DOIS_ANOS", 2)):
        body = _post(client_fixtures, horizonte=h, data_alvo="2020-01-01").json()
        esperado = anos_a_frente(TODAY, anos, cal)
        assert body["horizonte"] == h and body["data_alvo"] == esperado.isoformat()
        direto = _post(client_fixtures, data_alvo=esperado.isoformat()).json()
        assert [r["valor_liquido"] for r in body["vence_ate_data"]] == [
            r["valor_liquido"] for r in direto["vence_ate_data"]
        ]


def test_sem_data(client_fixtures):
    body = _post(client_fixtures, horizonte="SEM_DATA").json()
    assert body["horizonte"] == "SEM_DATA" and body["data_alvo"] is None
    assert body["vence_ate_data"] and body["vence_depois"] == []
    assert all(r["prazo_saida_dias"] is not None for r in body["vence_ate_data"])
    taxas = [D(r["taxa_liquida_aa"]) for r in body["vence_ate_data"] if r["taxa_liquida_aa"] is not None]
    assert taxas == sorted(taxas, reverse=True)
    um_ano = anos_a_frente(TODAY, 1, get_calendar()).isoformat()
    # Selic que vence dentro do horizonte natural (1 ano) não é vendida antes: sem estimativa.
    selic = [
        r
        for r in body["vence_ate_data"]
        if r["product"]["tipo"] == "TESOURO_SELIC" and r["product"]["data_vencimento"] > um_ano
    ]
    assert selic and all("ESTIMATIVA_MERCADO" in {a["code"] for a in r["alertas"]} for r in selic)


def test_cliente_antigo_e_validacao(client_fixtures):
    antigo = _post(client_fixtures, data_alvo="2029-06-15").json()
    assert antigo["horizonte"] == "DATA" and antigo["data_alvo"] == "2029-06-15"
    r = _post(client_fixtures, horizonte="DATA")
    assert r.status_code == 422 and r.json()["detail"] == ["Informe a data de resgate"]
    r = _post(client_fixtures, horizonte="DATA", data_alvo="2026-11-19")
    assert r.status_code == 422 and r.json()["detail"] == ["A data de resgate deve ser posterior a hoje"]
