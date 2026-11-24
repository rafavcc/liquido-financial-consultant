from datetime import UTC, datetime, timedelta

from app.data import db
from app.data.imports_repo import ImportRepository, PrintStore


def _repo(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    return conn, ImportRepository(conn), PrintStore(tmp_path / "prints", conn)


def test_print_store_dedups_by_hash_and_resolves_path(tmp_path):
    _, _, store = _repo(tmp_path)
    a = store.save(b"abc", "image/png")
    assert store.save(b"abc", "image/png") == a
    assert store.save(b"abd", "image/png") != a
    path, mime = store.path(a)
    assert path.read_bytes() == b"abc" and mime == "image/png" and path.parent == tmp_path / "prints"
    assert store.path("nope") is None


def test_queue_order_backoff_and_requeue(tmp_path):
    _, repo, store = _repo(tmp_path)
    p = store.save(b"x", "image/png")
    b = repo.create_batch()
    i1, i2 = repo.add_item(b, p, "a.png"), repo.add_item(b, p, "b.png")
    now = datetime(2026, 11, 23, tzinfo=UTC)
    assert repo.next_ready(now).id == i1
    repo.set_status(i1, "NA_FILA", proxima_tentativa=(now + timedelta(seconds=5)).isoformat())
    assert repo.next_ready(now).id == i2
    repo.set_status(i2, "LENDO")
    assert repo.next_ready(now) is None
    assert repo.next_ready(now + timedelta(seconds=5)).id == i1
    assert repo.requeue_reading() == 1
    assert repo.get_batch(b).itens[1].status == "NA_FILA"
    assert repo.list_batches()[0].id == b


def test_failures_roundtrip(tmp_path):
    _, repo, store = _repo(tmp_path)
    p = store.save(b"x", "image/png")
    i = repo.add_item(repo.create_batch(), p, "a.png")
    f = repo.add_failure(i, {"raw": {"a": 1}}, ["Vencimento não visível"])
    got = repo.get_failure(f)
    assert got.parcial == {"raw": {"a": 1}} and got.erros == ["Vencimento não visível"]
    assert got.status == "ABERTA" and got.print_id == p
    repo.set_failure_status(f, "DESCARTADA")
    assert repo.list_failures("ABERTA") == []
    assert [x.id for x in repo.list_failures("DESCARTADA")] == [f]
