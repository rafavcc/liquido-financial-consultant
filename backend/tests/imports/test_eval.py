from datetime import date

from app.domain.settings import Settings
from app.imports.eval import compare, expected_fields_from

T = date(2026, 11, 23)

RAW = {
    "plataforma": "BTG",
    "ofertas": [
        {"tipo": "LCI", "emissor": "Banco BTG Pactual",
         "taxas": [{"rotulo": "Taxa", "texto": "90,00% do CDI"}, {"rotulo": "Taxa eq. CDB", "texto": "108,46% do CDI"}],
         "vencimento": "23/11/2027", "aplicacao_minima": "R$ 500,00"},
        {"tipo": "LCI", "emissor": "Banco BTG Pactual", "taxas": [], "cortada": True},
    ],
}


def test_expected_raw_extraction_is_interpreted_and_cut_offers_skipped():
    exp = expected_fields_from(RAW, Settings(), T)
    assert exp == [{"tipo": "LCI", "emissor": "banco btg pactual", "taxa": "0.9",
                    "vencimento": "2027-11-23", "minimo": "500"}]


def test_expected_plain_list_still_supported():
    exp = expected_fields_from([{"tipo": "cdb", "emissor": "X", "taxa": "1.1", "vencimento": "2028-01-01",
                                 "valor_minimo": "1000"}], Settings(), T)
    assert exp[0]["tipo"] == "CDB" and exp[0]["minimo"] == "1000"


def test_compare_counts_missing_offers_as_errors():
    exp = [{"tipo": "LCI", "emissor": "a", "taxa": "0.9", "vencimento": "2027-11-23", "minimo": "500"}] * 2
    res = compare(exp, [exp[0]])
    assert res["tipo"] == (1, 2)


def test_compare_matches_by_tipo_and_vencimento_not_position():
    a = {"tipo": "LCI", "emissor": "a", "taxa": "0.9", "vencimento": "2027-11-23", "minimo": "500"}
    b = {"tipo": "LCI", "emissor": "a", "taxa": "0.88", "vencimento": "2028-05-23", "minimo": "500"}
    res = compare([a, b], [b])  # a falhou na interpretação: b não pode ser comparado com a
    assert res["taxa"] == (1, 2) and res["vencimento"] == (1, 2)


def test_taxa_compared_numerically():
    exp = expected_fields_from([{"tipo": "CDB", "emissor": "X", "taxa": "0.1120", "vencimento": "2028-01-01",
                                 "valor_minimo": "1000.00"}], Settings(), T)
    assert exp[0]["taxa"] == "0.112" and exp[0]["minimo"] == "1000"


def test_main_aborts_whole_run_on_multi_model(tmp_path, monkeypatch, capsys):
    import httpx

    from app.imports import eval as ev
    from app.imports.llm import MULTI_MODEL_AVISO

    for n in ("a.png", "b.png"):
        (tmp_path / n).write_bytes(b"\x89PNG\r\n\x1a\n" + n.encode())
    monkeypatch.setenv("LLM_BASE_URL", "http://llm/v1")
    monkeypatch.setenv("CASA_LLM_MODEL", "m")
    seen = []

    def handler(request):
        seen.append(request.url.path)
        return httpx.Response(200, json={"enabled": True, "mode": "on"})

    real = httpx.Client
    monkeypatch.setattr(ev.httpx, "Client", lambda *a, **k: real(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(ev, "BACKEND_DIR", tmp_path)
    assert ev.main([str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert MULTI_MODEL_AVISO in out and "b.png" not in out
    assert seen == ["/api/settings/multi-model"]
