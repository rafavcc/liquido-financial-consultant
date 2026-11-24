import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.data.market import FixtureFetchers
from app.main import create_app
from tests.api.conftest import FIXTURES, TODAY

PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 20
FIX = "xp-app-cdb-lista"


@pytest.fixture
def fixtures_dir(tmp_path):
    d = tmp_path / "llm"
    d.mkdir()
    src = FIXTURES.parent / "imports" / f"{FIX}.json"
    (d / "default.json").write_text(src.read_text("utf-8"), "utf-8")
    return d


def build(tmp_path, monkeypatch, fixtures_dir=None):
    monkeypatch.setenv("LIQUIDO_IMPORT_WORKER", "0")
    for v in ("LLM_BASE_URL", "CASA_LLM_MODEL", "LIQUIDO_LLM_FIXTURES"):
        monkeypatch.delenv(v, raising=False)
    if fixtures_dir:
        monkeypatch.setenv("LIQUIDO_LLM_FIXTURES", str(fixtures_dir))
    app = create_app(tmp_path / "db.sqlite", fetchers=FixtureFetchers(FIXTURES), today_fn=lambda: TODAY)
    return TestClient(app), app


@pytest.fixture
def client(tmp_path, monkeypatch, fixtures_dir):
    return build(tmp_path, monkeypatch, fixtures_dir)


@pytest.fixture
def client_sem_llm(tmp_path, monkeypatch):
    return build(tmp_path, monkeypatch)[0]


def test_upload_mixed_files(client):
    c, app = client
    files = [
        ("arquivos", ("a.png", PNG, "image/png")),
        ("arquivos", ("b.txt", b"texto", "text/plain")),
        ("arquivos", ("grande.png", b"\x89PNG" + b"0" * (21 * 1024 * 1024), "image/png")),
    ]
    r = c.post("/api/imports", files=files)
    assert r.status_code == 201
    body = r.json()
    assert len(body["lote"]["itens"]) == 1
    assert body["lote"]["itens"][0]["nome_arquivo"] == "a.png"
    assert body["lote"]["pendentes"] == 1
    assert len(body["recusados"]) == 2
    assert any("grande.png: maior que 20 MB" == m for m in body["recusados"])
    assert any("b.txt" in m for m in body["recusados"]) and any("grande.png" in m for m in body["recusados"])
    assert app.state.container.import_wake.is_set()
    assert c.get(f"/api/imports/{body['lote']['id']}").json()["id"] == body["lote"]["id"]
    assert len(c.get("/api/imports").json()) == 1
    assert c.get("/api/imports/nao-existe").status_code == 404


def test_upload_all_refused_is_422(client):
    r = client[0].post("/api/imports", files=[("arquivos", ("b.txt", b"t", "text/plain"))])
    assert r.status_code == 422
    assert "b.txt" in json.dumps(r.json()["detail"])


def test_upload_503_when_not_configured(client_sem_llm):
    r = client_sem_llm.post("/api/imports", files=[("arquivos", ("a.png", PNG, "image/png"))])
    assert r.status_code == 503
    assert "LLM_BASE_URL" in r.json()["detail"]


def test_status_endpoint(client, client_sem_llm):
    assert client[0].get("/api/imports/status").json() == {
        "configurado": True, "alcancavel": True, "modelo": "fixtures",
    }
    assert client_sem_llm.get("/api/imports/status").json() == {
        "configurado": False, "alcancavel": None, "modelo": None,
    }


def process_all(app):
    svc = app.state.container.imports
    while svc.process_next():
        pass


def test_retry_unknown_item_is_404(client):
    assert client[0].post("/api/imports/items/x/retry").status_code == 404


def _upload_with_failure(c, app):
    r = c.post("/api/imports", files=[("arquivos", ("a.png", PNG, "image/png"))])
    process_all(app)
    cont = app.state.container
    item_id = r.json()["lote"]["itens"][0]["id"]
    with cont.lock:
        fid = cont.imports._repo.add_failure(item_id, {"nome": "x"}, ["vencimento ausente"])
    return item_id, fid


def test_retry_conflict_when_not_error(client):
    c, app = client
    item_id, _ = _upload_with_failure(c, app)
    assert c.post(f"/api/imports/items/{item_id}/retry").status_code == 409


def test_failure_resolve_and_discard(client):
    c, app = client
    item_id, fid = _upload_with_failure(c, app)
    falhas = c.get("/api/imports/failures").json()
    f = next(x for x in falhas if x["id"] == fid)
    assert f["nome_arquivo"] == "a.png" and f["erros"] == ["vencimento ausente"] and f["parcial"] == {"nome": "x"}
    assert c.post(f"/api/imports/failures/{fid}/discard").status_code == 204
    assert c.post(f"/api/imports/failures/{fid}/discard").status_code == 409
    assert c.post("/api/imports/failures/nao/discard").status_code == 404
    assert all(x["id"] != fid for x in c.get("/api/imports/failures").json())
    assert c.get("/api/imports/failures?status=DESCARTADA").json()[0]["id"] == fid


def test_resolve_failure_validation_and_success(client):
    c, app = client
    _, fid = _upload_with_failure(c, app)
    bad = c.post(f"/api/imports/failures/{fid}/resolve", json={"tipo": "CDB", "nome": "x"})
    assert bad.status_code == 422
    ok = {
        "tipo": "CDB", "nome": "CDB Teste", "emissor": "Banco X", "plataforma": "XP",
        "data_vencimento": "2030-01-01", "indexador": "PRE", "taxa": "0.13",
        "liquidez": "NO_VENCIMENTO", "valor_minimo": "1000",
    }
    res = c.post(f"/api/imports/failures/{fid}/resolve", json=ok)
    assert res.status_code == 201, res.text
    assert res.json()["origem"] == "IA"
    assert c.post(f"/api/imports/failures/{fid}/resolve", json=ok).status_code == 409
    assert c.post("/api/imports/failures/nao/resolve", json=ok).status_code == 404


def test_print_served_with_mime(client):
    c, app = client
    c.post("/api/imports", files=[("arquivos", ("a.png", PNG, "image/png"))])
    cont = app.state.container
    print_id = cont.imports._repo.list_batches()[0].itens[0].print_id
    r = c.get(f"/api/prints/{print_id}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.headers["cache-control"] == "private, max-age=31536000, immutable"
    assert r.content == PNG
    assert c.get("/api/prints/nao").status_code == 404


def test_oversize_not_stored_and_all_oversize_is_422(client):
    c, app = client
    big = b"\x89PNG" + b"0" * (21 * 1024 * 1024)
    r = c.post("/api/imports", files=[("arquivos", ("grande.png", big, "image/png"))])
    assert r.status_code == 422 and r.json()["detail"] == ["grande.png: maior que 20 MB"]
    assert not list((app.state.container.imports._prints._dir).glob("*")) if (app.state.container.imports._prints._dir).exists() else True


def test_lifespan_worker_processes_and_stops(tmp_path, monkeypatch, fixtures_dir):
    import time

    monkeypatch.delenv("LIQUIDO_IMPORT_WORKER", raising=False)
    for v in ("LLM_BASE_URL", "CASA_LLM_MODEL"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("LIQUIDO_LLM_FIXTURES", str(fixtures_dir))
    app = create_app(tmp_path / "db.sqlite", fetchers=FixtureFetchers(FIXTURES), today_fn=lambda: TODAY)
    threads_before = {t for t in __import__("threading").enumerate() if t.name == "import-worker"}
    with TestClient(app) as c:
        workers = [t for t in __import__("threading").enumerate() if t.name == "import-worker" and t not in threads_before]
        assert len(workers) == 1
        r = c.post("/api/imports", files=[("arquivos", ("a.png", PNG, "image/png"))])
        lote = r.json()["lote"]["id"]
        deadline = time.monotonic() + 5
        status = None
        while time.monotonic() < deadline:
            status = c.get(f"/api/imports/{lote}").json()["itens"][0]["status"]
            if status == "CONCLUIDO":
                break
            time.sleep(0.05)
        assert status == "CONCLUIDO"
    assert not workers[0].is_alive()
