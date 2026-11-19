from datetime import date
from decimal import Decimal as D

from fastapi.testclient import TestClient

from app.data import db
from app.data.repositories import ProductRepository
from app.domain.products.base import ProductData
from app.domain.products.validation import validate_product
from app.domain.settings import Settings
from app.main import create_app
from tests.api.conftest import TODAY

BODY = {"valor": "50000", "data_alvo": "2029-06-15"}


class AlwaysFailFetchers:
    def fetch_bcb(self, today):
        raise RuntimeError("sem rede")

    def fetch_focus(self):
        raise RuntimeError("sem rede")

    def fetch_tesouro(self):
        raise RuntimeError("sem rede")


def test_api_simulate_offline(client_fixtures):
    r = client_fixtures.post("/api/simulate", json=BODY)
    body = r.json()
    assert r.status_code == 200
    assert body["vence_ate_data"] and isinstance(body["vence_ate_data"][0]["valor_liquido"], str)
    liq = [D(x["valor_liquido"]) for x in body["vence_ate_data"]]
    assert liq == sorted(liq, reverse=True)
    assert any(
        x["product"]["tipo"].startswith("TESOURO")
        for x in body["vence_depois"] + body["vence_ate_data"]
    )
    m = body["mercado"]
    assert D(m["cdi_aa"]) == D(m["selic_meta"]) - D("0.0010")
    assert m["fonte_projecao"].startswith("Focus") and m["projecao"]


def test_api_validation(client_fixtures):
    r = client_fixtures.post("/api/simulate", json={"valor": "0", "data_alvo": "2029-06-15"})
    assert r.status_code == 422 and r.json()["detail"] == ["O valor deve ser maior que zero"]
    r = client_fixtures.post("/api/simulate", json={"valor": "100", "data_alvo": "2020-01-01"})
    assert r.status_code == 422
    assert r.json()["detail"] == ["A data de resgate deve ser posterior a hoje"]
    r = client_fixtures.post("/api/simulate", json={"valor": "abc", "data_alvo": "2029-06-15"})
    assert r.status_code == 422 and all(isinstance(x, str) for x in r.json()["detail"])


def test_first_run_no_network_no_cache(tmp_path):
    client = TestClient(
        create_app(tmp_path / "db.sqlite", fetchers=AlwaysFailFetchers(), today_fn=lambda: TODAY)
    )
    body = client.post("/api/simulate", json=BODY).json()
    assert set(body["mercado"]["errors"]) == {"bcb", "focus", "tesouro"}
    assert body["mercado"]["fonte_projecao"] is None and body["mercado"]["projecao"] == []
    assert any(x["product"]["indexador"] == "PRE" for x in body["vence_ate_data"])
    assert body["indisponiveis"]
    assert all(
        any(a["code"] == "SEM_DADOS_MERCADO" for a in x["alertas"])
        for x in body["indisponiveis"]
        if x["product"]["indexador"] != "PRE"
    )


def _novo(**kw):
    base = {
        "id": "", "tipo": "CDB", "nome": "CDB Teste", "emissor": "Banco Teste", "plataforma": "XP",
        "indexador": "PCT_CDI", "taxa": "1.10", "data_vencimento": "2028-11-16",
        "valor_minimo": "1000", "liquidez": "NO_VENCIMENTO",
    }
    base.update(kw)
    return base


def test_products_crud_and_validation(client_fixtures):
    c = client_fixtures
    assert len(c.get("/api/products").json()) == 13
    r = c.post("/api/products", json=_novo())
    assert r.status_code == 200
    novo = r.json()
    assert novo["id"] and novo["exemplo"] is False
    assert any(p["id"] == novo["id"] for p in c.get("/api/products").json())

    novo["nome"] = "CDB Editado"
    r = c.put(f"/api/products/{novo['id']}", json=novo)
    assert r.status_code == 200 and r.json()["nome"] == "CDB Editado"
    assert r.json()["id"] == novo["id"]

    r = c.post(f"/api/products/{novo['id']}/duplicate")
    dup = r.json()
    assert r.status_code == 200 and dup["id"] != novo["id"]
    assert dup["nome"] == "CDB Editado (cópia)" and dup["exemplo"] is False

    assert c.delete(f"/api/products/{dup['id']}").status_code == 204
    assert c.delete(f"/api/products/{dup['id']}").status_code == 404
    assert c.put("/api/products/nao-existe", json=_novo()).status_code == 404
    assert c.post("/api/products/nao-existe/duplicate").status_code == 404

    r = c.post(
        "/api/products",
        json=_novo(tipo="LCI", data_vencimento="2027-05-19", nome="LCI curta"),
    )
    assert r.status_code == 422
    assert any("carência mínima" in m for m in r.json()["detail"])

    tesouro = c.get("/api/products/tesouro").json()
    assert tesouro and all(p["tipo"].startswith("TESOURO_") for p in tesouro)


def test_settings_roundtrip_and_reset(client_fixtures):
    c = client_fixtures
    s = c.get("/api/settings").json()
    assert D(s["custodia_b3_aa"]) == D("0.0020")
    s["custodia_b3_aa"] = "0.0025"
    assert c.put("/api/settings", json=s).status_code == 200
    assert D(c.get("/api/settings").json()["custodia_b3_aa"]) == D("0.0025")

    s["custodia_b3_aa"] = "5"
    r = c.put("/api/settings", json=s)
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], list) and "custodia_b3_aa" in r.json()["detail"][0]
    assert D(c.get("/api/settings").json()["custodia_b3_aa"]) == D("0.0025")

    r = c.post("/api/settings/reset")
    assert r.status_code == 200 and D(r.json()["custodia_b3_aa"]) == D("0.0020")
    assert D(c.get("/api/settings").json()["custodia_b3_aa"]) == D("0.0020")


def test_seed_once(tmp_path):
    path = tmp_path / "db.sqlite"
    c = TestClient(create_app(path, fetchers=AlwaysFailFetchers(), today_fn=lambda: TODAY))
    produtos = c.get("/api/products").json()
    assert [p["id"] for p in produtos] == [f"exemplo-{i:02d}" for i in range(1, 14)]
    assert all(p["exemplo"] for p in produtos)
    for p in produtos:
        assert c.delete(f"/api/products/{p['id']}").status_code == 204
    c2 = TestClient(create_app(path, fetchers=AlwaysFailFetchers(), today_fn=lambda: TODAY))
    assert c2.get("/api/products").json() == []


def test_seed_items_pass_validation(tmp_path):
    TestClient(create_app(tmp_path / "db.sqlite", fetchers=AlwaysFailFetchers(), today_fn=lambda: TODAY))
    repo = ProductRepository(db.connect(tmp_path / "db.sqlite"))
    produtos = repo.list()
    assert len(produtos) == 13
    for p in produtos:
        assert validate_product(p, Settings(), date(2026, 11, 19)) == [], p.id
    by_id = {p.id: p for p in produtos}
    assert by_id["exemplo-08"].data_carencia == date(2027, 11, 19)
    assert by_id["exemplo-03"].data_vencimento == date(2027, 11, 16)
    assert by_id["exemplo-13"].prazo_resgate_dias == 30
    assert isinstance(by_id["exemplo-01"], ProductData)


def test_health(client_fixtures):
    assert client_fixtures.get("/api/health").json() == {"status": "ok"}
