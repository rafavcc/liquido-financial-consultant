from fastapi.testclient import TestClient

from app.data.market import FixtureFetchers
from app.main import create_app
from tests.api.conftest import FIXTURES, TODAY


def make_client(tmp_path, with_static=True):
    static = tmp_path / "dist"
    if with_static:
        (static / "assets").mkdir(parents=True)
        (static / "index.html").write_text("<html>SPA</html>", encoding="utf-8")
        (static / "sw.js").write_text("// sw", encoding="utf-8")
        (static / "assets" / "app-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "segredo.txt").write_text("segredo", encoding="utf-8")
    app = create_app(
        tmp_path / "db.sqlite", fetchers=FixtureFetchers(FIXTURES), static_dir=static, today_fn=lambda: TODAY
    )
    return TestClient(app)


def test_spa_route_returns_index(tmp_path):
    r = make_client(tmp_path).get("/produtos")
    assert r.status_code == 200
    assert "SPA" in r.text
    assert r.headers["cache-control"] == "no-cache"


def test_root_returns_index(tmp_path):
    assert "SPA" in make_client(tmp_path).get("/").text


def test_existing_file_served_with_cache_headers(tmp_path):
    c = make_client(tmp_path)
    asset = c.get("/assets/app-abc123.js")
    assert asset.status_code == 200
    assert "immutable" in asset.headers["cache-control"]
    sw = c.get("/sw.js")
    assert sw.status_code == 200
    assert sw.headers["cache-control"] == "no-cache"


def test_unknown_api_is_json_404(tmp_path):
    r = make_client(tmp_path).get("/api/nao-existe")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")
    assert "SPA" not in r.text


def test_api_still_works(tmp_path):
    assert make_client(tmp_path).get("/api/health").json() == {"status": "ok"}


def test_path_traversal_does_not_leak(tmp_path):
    c = make_client(tmp_path)
    # caminhos percent-encoded crus: o httpx não os normaliza, então chegam ao servidor como escritos
    for path in ("/%2e%2e/segredo.txt", "/..%2fsegredo.txt", "/assets/..%2f..%2fsegredo.txt", "/%2e%2e%2fsegredo.txt"):
        r = c.get(path)
        assert "segredo" not in r.text, path


def test_missing_asset_is_404_not_index(tmp_path):
    r = make_client(tmp_path).get("/assets/missing.js")
    assert r.status_code == 404
    assert "SPA" not in r.text


def test_nul_path_is_404(tmp_path):
    c = make_client(tmp_path)
    assert c.get("/%00").status_code == 404
    assert c.get("/assets/%00.js").status_code == 404


def test_unknown_api_any_method_is_json_404(tmp_path):
    c = make_client(tmp_path)
    for method in ("post", "put", "delete"):
        r = getattr(c, method)("/api/nao-existe")
        assert r.status_code == 404, method
        assert r.headers["content-type"].startswith("application/json")


def test_without_static_dir_no_catch_all(tmp_path):
    c = make_client(tmp_path, with_static=False)
    assert c.get("/produtos").status_code == 404
    assert c.get("/api/health").status_code == 200
