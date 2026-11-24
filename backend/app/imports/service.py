"""Serviço de importação: fila, interpretação, renovação e falhas (spec §5, §7.3)."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

from app.data.imports_repo import ImportItem, ImportRepository, PrintStore
from app.data.repositories import ProductRepository, SettingsRepository
from app.domain.offers import offer_key
from app.domain.products.base import ProductData
from app.domain.products.validation import validate_product
from app.imports.interpret import Created, Failed, Ignored, interpret_offer, resolve_platform
from app.imports.parsing import parse_amortizacao, parse_periodicidade
from app.imports.llm import LlmBadResponse, LlmClient, LlmRejected, LlmUnavailable

log = logging.getLogger(__name__)

MAX_BYTES = 20 * 1024 * 1024
MAX_ATTEMPTS = 3
_FORMATO = "{nome}: formato não suportado (use PNG, JPEG ou WEBP)"


@dataclass
class UploadedFile:
    nome: str
    content: bytes


def detect_mime(content: bytes) -> str | None:
    if content.startswith(b"\x89PNG"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


class ImportService:
    def __init__(
        self,
        products: ProductRepository,
        settings: SettingsRepository,
        repo: ImportRepository,
        prints: PrintStore,
        llm: LlmClient | None,
        lock: threading.RLock,
        today_fn: Callable[[], date],
        now_fn: Callable[[], datetime],
        retry_waits_s: tuple[int, int] = (5, 30),
    ) -> None:
        self._products, self._settings, self._repo, self._prints = products, settings, repo, prints
        self._llm, self._lock = llm, lock
        self._today, self._now = today_fn, now_fn
        self._waits = retry_waits_s

    # --- entrada -----------------------------------------------------------------------------

    def enqueue(self, files: list[UploadedFile]) -> tuple[str, list[str]]:
        recusas: list[str] = []
        ok: list[tuple[UploadedFile, str]] = []
        for f in files:
            mime = detect_mime(f.content)
            if mime is None:
                recusas.append(_FORMATO.format(nome=f.nome))
            elif len(f.content) > MAX_BYTES:
                recusas.append(f"{f.nome}: maior que 20 MB")
            else:
                ok.append((f, mime))
        if not ok:
            raise ValueError(recusas)
        with self._lock:
            batch = self._repo.create_batch()
            for f, mime in ok:
                self._repo.add_item(batch, self._prints.save(f.content, mime), f.nome)
        return batch, recusas

    def requeue_reading(self) -> int:
        with self._lock:
            return self._repo.requeue_reading()

    def retry_item(self, item_id: str) -> None:
        with self._lock:
            item = self._repo.get_item(item_id)
            if item is None:
                raise KeyError(item_id)
            if item.status != "ERRO":
                raise ValueError("Só é possível tentar de novo um item com erro")
            # reprocessar é idempotente nos produtos (offer_key); as falhas abertas são refeitas do zero
            self._repo.delete_open_failures(item_id)
            self._repo.set_status(
                item_id, "NA_FILA", tentativas=0, proxima_tentativa=None, erro=None, concluido_em=None,
                iniciado_em=None, criados=0, renovados=0, ignorados=0, falhas=0,
            )

    # --- processamento -----------------------------------------------------------------------

    def process_next(self) -> bool:
        with self._lock:
            item = self._repo.next_ready(self._now())
            if item is None:
                return False
            self._repo.set_status(item.id, "LENDO", iniciado_em=self._now().isoformat(), erro=None)
        try:
            self._process(item)
        except Exception as exc:  # o item nunca fica LENDO
            log.exception("Falha inesperada ao importar %s", item.id)
            try:
                self._fail(item, str(exc) or exc.__class__.__name__)
            except Exception:
                log.exception("Não foi possível marcar %s como ERRO; recolocando na fila", item.id)
                try:
                    with self._lock:
                        self._repo.set_status(item.id, "NA_FILA")
                except Exception:
                    log.exception("Não foi possível recolocar %s na fila", item.id)
        return True

    def _fail(self, item: ImportItem, erro: str, **fields) -> None:
        with self._lock:
            self._repo.set_status(item.id, "ERRO", erro=erro, concluido_em=self._now().isoformat(), **fields)

    def _process(self, item: ImportItem) -> None:
        if self._llm is None:
            return self._fail(item, "Importação não configurada")
        with self._lock:
            found = self._prints.path(item.print_id)
        if found is None:
            return self._fail(item, "Print não encontrado")
        path, mime = found
        try:
            extraction = self._llm.extract(path.read_bytes(), mime)  # fora do lock
        except LlmUnavailable as exc:
            return self._unavailable(item, str(exc))
        except LlmRejected as exc:
            return self._fail(item, str(exc))
        except LlmBadResponse:
            return self._fail(item, "Resposta do modelo ilegível")
        with self._lock:
            self._apply(item, extraction)

    def _unavailable(self, item: ImportItem, detalhe: str) -> None:
        tentativas = item.tentativas + 1
        if tentativas >= MAX_ATTEMPTS:
            return self._fail(item, f"Servidor LLM indisponível: {detalhe}", tentativas=tentativas)
        espera = self._waits[tentativas - 1]
        with self._lock:
            self._repo.set_status(
                item.id,
                "NA_FILA",
                tentativas=tentativas,
                proxima_tentativa=(self._now() + timedelta(seconds=espera)).isoformat(),
                erro=f"Servidor LLM indisponível: {detalhe}",
            )

    def _apply(self, item: ImportItem, extraction) -> None:
        settings, today = self._settings.get(), self._today()
        batch = self._repo.get_batch(item.batch_id)
        batch_prints = {i.print_id for i in batch.itens} if batch else {item.print_id}
        counts = {"criados": 0, "renovados": 0, "ignorados": 0, "falhas": 0}
        plataforma = resolve_platform(extraction)
        for raw in extraction.ofertas:
            res = interpret_offer(raw, plataforma, settings, today)
            if isinstance(res, Created):
                data = res.data.model_copy(update={"print_id": item.print_id})
                counts["criados" if self.upsert_offer(data, batch_prints, res.minimo_desconhecido) == "criado" else "renovados"] += 1
            elif isinstance(res, Failed):
                self._repo.add_failure(item.id, res.parcial, res.erros)
                counts["falhas"] += 1
            elif isinstance(res, Ignored):
                counts["ignorados"] += 1
        self._repo.set_status(
            item.id,
            "CONCLUIDO",
            resposta_bruta=extraction.model_dump_json(),
            concluido_em=self._now().isoformat(),
            proxima_tentativa=None,
            **counts,
        )

    # --- produtos ----------------------------------------------------------------------------

    def upsert_offer(
        self, data: ProductData, batch_print_ids: set[str], minimo_desconhecido: bool = False
    ) -> Literal["criado", "renovado"]:
        with self._lock:
            key = offer_key(data)
            found = next((p for p in self._products.list() if not p.exemplo and offer_key(p) == key), None)
            if found is None:
                self._products.create(data)
                return "criado"
            update: dict = {"data_registro": self._today(), "print_id": data.print_id}
            if data.disponivel_ate is not None:
                update["disponivel_ate"] = data.disponivel_ate
            if not minimo_desconhecido and found.valor_minimo == 0 and data.valor_minimo > 0:
                # 0 é "mínimo desconhecido" (o modelo não leu): preenche quando um print traz o valor
                update["valor_minimo"] = data.valor_minimo
                notas = [n for n in (found.observacoes or "").splitlines() if "Importado: mínimo n" not in n]
                update["observacoes"] = "\n".join(notas)
            elif not minimo_desconhecido and found.print_id is not None and found.print_id in batch_print_ids:
                update["valor_minimo"] = min(found.valor_minimo, data.valor_minimo)
            # valida: model_copy não valida e um campo errado tornaria o registro ilegível na listagem
            self._products.update(found.id, ProductData.model_validate({**found.model_dump(), **update}))
            return "renovado"

    # --- falhas ------------------------------------------------------------------------------

    def _open_failure(self, failure_id: str):
        failure = self._repo.get_failure(failure_id)
        if failure is None:
            raise KeyError(failure_id)
        if failure.status != "ABERTA":
            raise ValueError("Esta falha já foi resolvida ou descartada")
        return failure

    def resolve_failure(self, failure_id: str, data: ProductData) -> ProductData:
        with self._lock:
            failure = self._open_failure(failure_id)
            today = self._today()
            erros = validate_product(data, self._settings.get(), today)
            if erros:
                raise ValueError(erros)
            update: dict = {"origem": "IA", "print_id": failure.print_id, "data_registro": today}
            raw = failure.parcial.get("raw") or {}
            if data.juros_periodicos is None and (j := parse_periodicidade(raw.get("juros"))):
                update["juros_periodicos"] = j
            if data.amortizacao is None and (a := parse_amortizacao(raw.get("amortizacao"))):
                update["amortizacao"] = a
            data = data.model_copy(update=update)
            item = self._repo.get_item(failure.item_id)
            batch = self._repo.get_batch(item.batch_id) if item else None
            batch_prints = {i.print_id for i in batch.itens} if batch else set()
            self.upsert_offer(data, batch_prints)
            self._repo.set_failure_status(failure_id, "RESOLVIDA")
            return data

    def discard_failure(self, failure_id: str) -> None:
        with self._lock:
            self._open_failure(failure_id)
            self._repo.set_failure_status(failure_id, "DESCARTADA")

    # --- leitura (para a API; cada método segura o lock) ---------------------------------------

    def get_batch(self, batch_id: str):
        with self._lock:
            return self._repo.get_batch(batch_id)

    def list_batches(self, limit: int = 20):
        with self._lock:
            return self._repo.list_batches(limit)

    def get_item(self, item_id: str):
        with self._lock:
            return self._repo.get_item(item_id)

    def list_failures(self, status: str | None = "ABERTA") -> list[tuple]:
        """Pares (falha, nome do arquivo do item)."""
        with self._lock:
            out = []
            for f in self._repo.list_failures(status):
                item = self._repo.get_item(f.item_id)
                out.append((f, item.nome_arquivo if item else None))
            return out

    def get_failure(self, failure_id: str):
        with self._lock:
            return self._repo.get_failure(failure_id)

    def print_file(self, print_id: str):
        with self._lock:
            return self._prints.path(print_id)
