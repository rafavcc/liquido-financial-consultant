import json

import httpx
import pytest

from app.imports.llm import LlmBadResponse, LlmConfig, LlmUnavailable, OpenAICompatClient

PNG = b"\x89PNG\r\n\x1a\n"
OK = {"plataforma": "XP", "ofertas": []}


def completion(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def make(handler) -> tuple[OpenAICompatClient, list[dict]]:
    bodies: list[dict] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content) if request.content else {})
        return handler(request, len(bodies))

    cfg = LlmConfig("http://llm/v1", "m", "test-key", 5.0)
    return OpenAICompatClient(cfg, httpx.Client(transport=httpx.MockTransport(wrapped))), bodies


def test_sends_schema_image_and_parses():
    client, bodies = make(lambda r, n: completion(json.dumps(OK)))
    assert client.extract(PNG, "image/png").plataforma == "XP"
    b = bodies[0]
    assert b["response_format"]["type"] == "json_schema"
    assert b["response_format"]["json_schema"]["strict"] is True
    assert b["chat_template_kwargs"] == {"enable_thinking": False}
    assert b["temperature"] == 0 and b["model"] == "m"
    assert b["messages"][0]["role"] == "system"
    assert "data:image/png;base64," in json.dumps(b["messages"][1])


def test_falls_back_without_response_format():
    def handler(r, n):
        if n == 1:
            return httpx.Response(400, text="response_format not supported")
        return completion(json.dumps(OK))

    client, bodies = make(handler)
    client.extract(PNG, "image/png")
    assert len(bodies) == 2 and "response_format" not in bodies[1]
    client.extract(PNG, "image/png")
    assert len(bodies) == 3 and "response_format" not in bodies[2]


def test_strips_think_and_fences():
    text = "<think>hmm {x}</think>\n```json\n" + json.dumps(OK) + "\n```"
    client, _ = make(lambda r, n: completion(text))
    assert client.extract(PNG, "image/png").plataforma == "XP"


def test_invalid_json_retries_once_then_bad_response():
    client, bodies = make(lambda r, n: completion("nada de json"))
    with pytest.raises(LlmBadResponse):
        client.extract(PNG, "image/png")
    assert len(bodies) == 2
    assert "Sua resposta anterior não era JSON válido" in json.dumps(bodies[1], ensure_ascii=False)


def test_invalid_json_then_valid():
    client, bodies = make(lambda r, n: completion("x" if n == 1 else json.dumps(OK)))
    assert client.extract(PNG, "image/png").plataforma == "XP"


def test_no_model_loaded_is_unavailable():
    client, _ = make(lambda r, n: httpx.Response(400, text="No model loaded. Load one first"))
    with pytest.raises(LlmUnavailable):
        client.extract(PNG, "image/png")


def test_5xx_and_network_errors_are_unavailable():
    client, _ = make(lambda r, n: httpx.Response(503, text="boom"))
    with pytest.raises(LlmUnavailable):
        client.extract(PNG, "image/png")

    def boom(r, n):
        raise httpx.ConnectError("refused")

    client, _ = make(boom)
    with pytest.raises(LlmUnavailable):
        client.extract(PNG, "image/png")
    assert client.ping() is False


def test_ping():
    client, _ = make(lambda r, n: httpx.Response(200, json={"data": []}))
    assert client.ping() is True


def test_from_env_none_without_vars(monkeypatch):
    for v in ("LLM_BASE_URL", "CASA_LLM_MODEL", "LLM_API_KEY", "LLM_TIMEOUT_S"):
        monkeypatch.delenv(v, raising=False)
    assert LlmConfig.from_env() is None
    monkeypatch.setenv("LLM_BASE_URL", "http://x/v1/")
    assert LlmConfig.from_env() is None
    monkeypatch.setenv("CASA_LLM_MODEL", "m")
    cfg = LlmConfig.from_env()
    assert cfg is not None and cfg.base_url == "http://x/v1" and cfg.timeout_s == 300 and cfg.api_key is None
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_TIMEOUT_S", "10")
    cfg = LlmConfig.from_env()
    assert cfg.api_key == "test-key" and cfg.timeout_s == 10


def test_fake_client(tmp_path):
    import hashlib

    from app.imports.llm import FakeLlmClient

    (tmp_path / "default.json").write_text(json.dumps({"plataforma": "D"}))
    (tmp_path / f"{hashlib.sha256(PNG).hexdigest()}.json").write_text(json.dumps({"plataforma": "S"}))
    fake = FakeLlmClient(tmp_path)
    assert fake.extract(PNG, "image/png").plataforma == "S"
    assert fake.extract(PNG + b"1", "image/png").plataforma == "D"
    assert fake.ping() is True


def test_auth_and_not_found_are_distinct_non_retryable_errors():
    from app.imports.llm import LlmRejected

    for status, msg in ((401, "Servidor LLM recusou a chave (HTTP 401)"),
                        (403, "Servidor LLM recusou a chave (HTTP 403)"),
                        (404, "Endereço ou modelo do LLM não encontrado (HTTP 404)")):
        client, bodies = make(lambda r, n, s=status: httpx.Response(s, text="x"))
        with pytest.raises(LlmRejected, match=msg.replace("(", r"\(").replace(")", r"\)")):
            client.extract(PNG, "image/png")
        assert len(bodies) == 1
