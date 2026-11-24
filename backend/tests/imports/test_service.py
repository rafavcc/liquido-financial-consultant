import json
import threading
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from app.data import db
from app.data.imports_repo import ImportRepository, PrintStore
from app.data.repositories import ProductRepository, SettingsRepository
from app.domain.offers import is_expired
from app.imports.llm import LlmBadResponse, LlmUnavailable
from app.imports.schema import RawExtraction
from app.imports.service import ImportService, UploadedFile

FIX = Path(__file__).parent.parent / "fixtures" / "imports"
PNG = b"\x89PNG\r\n\x1a\n"


def fixture(nome: str) -> RawExtraction:
    return RawExtraction.model_validate(json.loads((FIX / f"{nome}.json").read_text("utf-8")))


class StubLlm:
    """Devolve a extração conforme o conteúdo do arquivo (PNG + nome da fixture)."""

    def __init__(self):
        self.calls = 0
        self.error: Exception | None = None

    def extract(self, image, mime):
        self.calls += 1
        if self.error:
            raise self.error
        return fixture(image[len(PNG):].decode())

    def ping(self):
        return True


class Clock:
    def __init__(self):
        self.now = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)

    def advance(self, **kw):
        self.now += timedelta(**kw)


def shot(nome: str) -> UploadedFile:
    return UploadedFile(nome=f"{nome}.png", content=PNG + nome.encode())


class Env:
    def __init__(self, tmp_path, llm="stub"):
        self.conn = db.connect(tmp_path / "t.db")
        self.products = ProductRepository(self.conn)
        self.repo = ImportRepository(self.conn)
        self.llm = StubLlm()
        self.clock = Clock()
        self.svc = ImportService(
            self.products, SettingsRepository(self.conn), self.repo, PrintStore(tmp_path / "prints", self.conn),
            self.llm if llm == "stub" else None, threading.RLock(),
            today_fn=lambda: self.clock.now.date(), now_fn=lambda: self.clock.now,
        )

    def items(self, batch):
        return self.repo.get_batch(batch).itens


@pytest.fixture
def env(tmp_path):
    return Env(tmp_path)


def test_process_creates_products_and_counts(env):
    batch, recusas = env.svc.enqueue([shot("btg-app-lci-eq-cdb")])
    assert recusas == []
    assert env.svc.process_next() is True
    item = env.items(batch)[0]
    assert item.status == "CONCLUIDO" and item.criados == 2 and item.renovados == 0
    assert item.resposta_bruta and item.concluido_em
    prods = env.products.list()
    assert len(prods) == 2 and all(p.tipo.value == "LCI" and p.origem == "IA" for p in prods)
    assert all(p.print_id == item.print_id for p in prods)
    assert env.svc.process_next() is False


def test_same_offer_repeated_in_print_keeps_lowest_min(env):
    batch, _ = env.svc.enqueue([shot("xp-web-tabela-lcd")])
    env.svc.process_next()
    item = env.items(batch)[0]
    lcd = [p for p in env.products.list() if p.tipo.value == "LCD" and p.data_vencimento == date(2030, 3, 15)]
    assert len(lcd) == 1
    raw = [o for o in fixture("xp-web-tabela-lcd").ofertas if o.emissor == "BNDES" and o.vencimento == "15/03/2030"]
    assert len(raw) == 4 and item.renovados == 3
    from app.imports.parsing import parse_money

    minimos = [parse_money(o.aplicacao_minima) for o in raw if o.aplicacao_minima]
    assert lcd[0].valor_minimo == min(minimos)


def test_reupload_renews_expired_and_keeps_manual_edits(env):
    env.svc.enqueue([shot("btg-app-lci-eq-cdb")])
    env.svc.process_next()
    settings = SettingsRepository(env.conn).get()
    first = env.products.list()[0]
    env.products.update(first.id, first.model_copy(update={"nome": "Meu nome", "observacoes": "minha nota"}))
    env.clock.advance(days=30)
    assert is_expired(env.products.get(first.id), settings, env.clock.now.date())

    batch, _ = env.svc.enqueue([shot("btg-app-lci-eq-cdb")])
    env.svc.process_next()
    item = env.items(batch)[0]
    assert item.criados == 0 and item.renovados == 2
    got = env.products.get(first.id)
    assert len(env.products.list()) == 2
    assert got.data_registro == env.clock.now.date()
    assert got.nome == "Meu nome" and got.observacoes == "minha nota"
    assert not is_expired(got, settings, env.clock.now.date())
    assert got.print_id == item.print_id


def _failing_extraction() -> RawExtraction:
    base = fixture("btg-app-lci-eq-cdb")
    raw = base.ofertas[0].model_copy(update={"vencimento": None})
    return RawExtraction(plataforma="BTG", ofertas=[raw])


def test_failures_recorded_and_resolved(env, monkeypatch):
    monkeypatch.setattr(env.llm, "extract", lambda image, mime: _failing_extraction())
    batch, _ = env.svc.enqueue([shot("x")])
    env.svc.process_next()
    item = env.items(batch)[0]
    assert item.status == "CONCLUIDO" and item.falhas == 1 and item.criados == 0
    (fail,) = env.repo.list_failures("ABERTA")
    assert "Vencimento não visível" in fail.erros

    ok = fixture("btg-app-lci-eq-cdb")
    from app.imports.interpret import Created, interpret_offer

    res = interpret_offer(ok.ofertas[0], "BTG", SettingsRepository(env.conn).get(), env.clock.now.date())
    assert isinstance(res, Created)
    bad = res.data.model_copy(update={"data_vencimento": date(2020, 1, 1)})
    with pytest.raises(ValueError):
        env.svc.resolve_failure(fail.id, bad)
    assert env.repo.get_failure(fail.id).status == "ABERTA"

    out = env.svc.resolve_failure(fail.id, res.data)
    assert out.origem == "IA" and out.print_id == item.print_id and out.data_registro == env.clock.now.date()
    assert env.repo.get_failure(fail.id).status == "RESOLVIDA"
    assert len(env.products.list()) == 1


def test_discard_failure(env, monkeypatch):
    monkeypatch.setattr(env.llm, "extract", lambda image, mime: _failing_extraction())
    env.svc.enqueue([shot("x")])
    env.svc.process_next()
    (fail,) = env.repo.list_failures("ABERTA")
    env.svc.discard_failure(fail.id)
    assert env.repo.get_failure(fail.id).status == "DESCARTADA"


def test_print_dedup_by_hash(env):
    batch, _ = env.svc.enqueue([shot("btg-app-lci-eq-cdb"), shot("btg-app-lci-eq-cdb")])
    a, b = env.items(batch)
    assert a.print_id == b.print_id and len(env.items(batch)) == 2


def test_enqueue_rejects_bad_files_but_keeps_good(env):
    big = UploadedFile("grande.png", PNG + b"0" * (20 * 1024 * 1024))
    txt = UploadedFile("nota.txt", b"hello")
    jpg = UploadedFile("a.jpg", b"\xff\xd8\xff\xe0abc")
    webp = UploadedFile("b.webp", b"RIFF\x00\x00\x00\x00WEBPxx")
    batch, recusas = env.svc.enqueue([shot("btg-app-lci-eq-cdb"), txt, big, jpg, webp])
    assert recusas == [
        "nota.txt: formato não suportado (use PNG, JPEG ou WEBP)",
        "grande.png: maior que 20 MB",
    ]
    assert [i.nome_arquivo for i in env.items(batch)] == ["btg-app-lci-eq-cdb.png", "a.jpg", "b.webp"]
    with pytest.raises(ValueError) as exc:
        env.svc.enqueue([txt])
    assert exc.value.args[0] == ["nota.txt: formato não suportado (use PNG, JPEG ou WEBP)"]
    assert len(env.repo.list_batches()) == 1


def test_requeue_reading_on_start(env):
    batch, _ = env.svc.enqueue([shot("btg-app-lci-eq-cdb")])
    item = env.items(batch)[0]
    env.repo.set_status(item.id, "LENDO")
    assert env.svc.requeue_reading() == 1
    assert env.items(batch)[0].status == "NA_FILA"


def test_three_failures_then_error_then_retry(env):
    env.llm.error = LlmUnavailable("No model loaded")
    batch, _ = env.svc.enqueue([shot("btg-app-lci-eq-cdb")])
    # segundo item do lote, que o servidor atende depois
    batch2_item = env.repo.add_item(batch, env.items(batch)[0].print_id, "outro.png")
    assert env.svc.process_next() is True
    it = env.items(batch)[0]
    assert it.status == "NA_FILA" and it.tentativas == 1 and it.proxima_tentativa
    # o item em espera não bloqueia o seguinte
    env.llm.error = None
    assert env.svc.process_next() is True
    assert env.repo.get_item(batch2_item).status == "CONCLUIDO"
    env.llm.error = LlmUnavailable("No model loaded")
    assert env.svc.process_next() is False  # ainda dentro da espera
    env.clock.advance(seconds=6)
    env.svc.process_next()
    assert env.items(batch)[0].tentativas == 2 and env.items(batch)[0].status == "NA_FILA"
    env.clock.advance(seconds=31)
    env.svc.process_next()
    it = env.items(batch)[0]
    assert it.status == "ERRO" and it.erro == "Servidor LLM indisponível: No model loaded"
    assert not any(i.status == "LENDO" for i in env.items(batch))
    env.svc.retry_item(it.id)
    it = env.items(batch)[0]
    assert it.status == "NA_FILA" and it.tentativas == 0 and it.erro is None


def test_bad_response_errors_immediately(env):
    env.llm.error = LlmBadResponse("lixo")
    batch, _ = env.svc.enqueue([shot("btg-app-lci-eq-cdb")])
    env.svc.process_next()
    it = env.items(batch)[0]
    assert it.status == "ERRO" and it.erro == "Resposta do modelo ilegível" and env.llm.calls == 1


def test_llm_not_configured(tmp_path):
    e = Env(tmp_path, llm=None)
    batch, _ = e.svc.enqueue([shot("btg-app-lci-eq-cdb")])
    e.svc.process_next()
    it = e.items(batch)[0]
    assert it.status == "ERRO" and it.erro == "Importação não configurada"


def test_unexpected_exception_never_leaves_reading(env):
    env.llm.error = RuntimeError("boom")
    batch, _ = env.svc.enqueue([shot("btg-app-lci-eq-cdb")])
    env.svc.process_next()
    it = env.items(batch)[0]
    assert it.status == "ERRO" and "boom" in it.erro


def test_lock_not_held_during_llm_call(env):
    held = []

    def extract(image, mime):
        def probe():  # outra thread: um RLock reentra na mesma
            ok = env.svc._lock.acquire(timeout=0.5)
            held.append(ok)
            if ok:
                env.svc._lock.release()

        t = threading.Thread(target=probe)
        t.start()
        t.join()
        return fixture("btg-app-lci-eq-cdb")

    env.llm.extract = extract
    env.svc.enqueue([shot("btg-app-lci-eq-cdb")])
    env.svc.process_next()
    assert held == [True]


def test_repeated_offer_with_different_minimums_keeps_lowest(env, monkeypatch):
    base = fixture("xp-web-tabela-lcd")
    dup = [o for o in base.ofertas if o.emissor == "BNDES" and o.vencimento == "15/03/2030"]
    mins = ["R$ 20.000,00", "R$ 13.032,67", "R$ 50.000,00", "R$ 15.000,00"]
    ext = base.model_copy(
        update={"ofertas": [o.model_copy(update={"aplicacao_minima": m}) for o, m in zip(dup, mins)]}
    )
    monkeypatch.setattr(env.llm, "extract", lambda image, mime: ext)
    batch, _ = env.svc.enqueue([shot("x")])
    env.svc.process_next()
    (prod,) = env.products.list()
    assert str(prod.valor_minimo) == "13032.67"
    item = env.items(batch)[0]
    assert (item.criados, item.renovados) == (1, 3)


def test_retry_item_only_acts_on_erro(env):
    batch, _ = env.svc.enqueue([shot("btg-app-lci-eq-cdb")])
    item = env.items(batch)[0]
    env.repo.set_status(item.id, "LENDO")
    with pytest.raises(ValueError, match="Só é possível tentar de novo um item com erro"):
        env.svc.retry_item(item.id)
    assert env.items(batch)[0].status == "LENDO"
    env.repo.set_status(item.id, "CONCLUIDO")
    with pytest.raises(ValueError):
        env.svc.retry_item(item.id)
    assert env.items(batch)[0].status == "CONCLUIDO"


def test_resolve_and_discard_require_open_failure(env, monkeypatch):
    monkeypatch.setattr(env.llm, "extract", lambda image, mime: _failing_extraction())
    env.svc.enqueue([shot("x")])
    env.svc.process_next()
    (fail,) = env.repo.list_failures("ABERTA")
    env.svc.discard_failure(fail.id)
    with pytest.raises(ValueError, match="Esta falha já foi resolvida ou descartada"):
        env.svc.discard_failure(fail.id)
    ok = fixture("btg-app-lci-eq-cdb")
    from app.imports.interpret import interpret_offer

    data = interpret_offer(ok.ofertas[0], "BTG", SettingsRepository(env.conn).get(), env.clock.now.date()).data
    with pytest.raises(ValueError, match="Esta falha já foi resolvida ou descartada"):
        env.svc.resolve_failure(fail.id, data)
    assert env.products.list() == []
    with pytest.raises(KeyError):
        env.svc.discard_failure("inexistente")


def test_process_next_survives_status_write_failure(env):
    env.llm.error = RuntimeError("boom")
    batch, _ = env.svc.enqueue([shot("btg-app-lci-eq-cdb")])
    real = env.repo.set_status
    state = {"fail": True}

    def flaky(item_id, status, **kw):
        if status == "ERRO" and state["fail"]:
            state["fail"] = False
            raise RuntimeError("disco cheio")
        return real(item_id, status, **kw)

    env.repo.set_status = flaky
    assert env.svc.process_next() is True
    assert env.items(batch)[0].status == "NA_FILA"


def test_retry_after_error_does_not_duplicate_failures(env, monkeypatch):
    monkeypatch.setattr(env.llm, "extract", lambda image, mime: _failing_extraction())
    batch, _ = env.svc.enqueue([shot("x")])
    env.svc.process_next()
    item = env.items(batch)[0]
    assert item.falhas == 1
    env.repo.set_status(item.id, "ERRO", erro="queda")
    env.svc.retry_item(item.id)
    it = env.items(batch)[0]
    assert (it.falhas, it.criados, it.erro, it.tentativas, it.iniciado_em) == (0, 0, None, 0, None)
    env.svc.process_next()
    assert len(env.repo.list_failures("ABERTA")) == 1
    assert env.items(batch)[0].falhas == 1
