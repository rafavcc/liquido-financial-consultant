"""Persistência da importação: prints em disco e fila/lotes/falhas no SQLite (spec §7.4)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
_UNSET = object()


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ImportItem(BaseModel):
    id: str
    batch_id: str
    print_id: str
    nome_arquivo: str
    status: str
    tentativas: int
    proxima_tentativa: str | None
    erro: str | None
    resposta_bruta: str | None
    criados: int
    renovados: int
    ignorados: int
    falhas: int
    iniciado_em: str | None
    concluido_em: str | None


class ImportBatch(BaseModel):
    id: str
    criado_em: str
    itens: list[ImportItem] = []


class ImportFailure(BaseModel):
    id: str
    item_id: str
    print_id: str | None = None
    parcial: dict
    erros: list[str]
    status: str


class PrintStore:
    def __init__(self, dir: Path, conn: sqlite3.Connection) -> None:
        self._dir, self._conn = dir, conn

    def save(self, content: bytes, mime: str) -> str:
        sha = hashlib.sha256(content).hexdigest()
        row = self._conn.execute("SELECT id FROM prints WHERE sha256 = ?", (sha,)).fetchone()
        if row:
            return row[0]
        self._dir.mkdir(parents=True, exist_ok=True)
        file = self._dir / f"{sha}.{_EXT[mime]}"
        file.write_bytes(content)
        pid = str(uuid.uuid4())
        self._conn.execute(
            "INSERT INTO prints (id, sha256, mime, caminho, criado_em) VALUES (?, ?, ?, ?, ?)",
            (pid, sha, mime, str(file), _now()),
        )
        self._conn.commit()
        return pid

    def path(self, print_id: str) -> tuple[Path, str] | None:
        row = self._conn.execute("SELECT caminho, mime FROM prints WHERE id = ?", (print_id,)).fetchone()
        return (Path(row[0]), row[1]) if row else None


_ITEM_COLS = (
    "id, batch_id, print_id, nome_arquivo, status, tentativas, proxima_tentativa, erro, resposta_bruta, "
    "criados, renovados, ignorados, falhas, iniciado_em, concluido_em"
)
_SETTABLE = {
    "tentativas", "proxima_tentativa", "erro", "resposta_bruta", "criados", "renovados", "ignorados",
    "falhas", "iniciado_em", "concluido_em",
}


class ImportRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create_batch(self) -> str:
        bid = str(uuid.uuid4())
        self._conn.execute("INSERT INTO import_batches (id, criado_em) VALUES (?, ?)", (bid, _now()))
        self._conn.commit()
        return bid

    def add_item(self, batch_id: str, print_id: str, nome_arquivo: str) -> str:
        iid = str(uuid.uuid4())
        self._conn.execute(
            "INSERT INTO import_items (id, batch_id, print_id, nome_arquivo, seq) "
            "VALUES (?, ?, ?, ?, (SELECT COALESCE(MAX(seq), 0) + 1 FROM import_items))",
            (iid, batch_id, print_id, nome_arquivo),
        )
        self._conn.commit()
        return iid

    def _item(self, row) -> ImportItem:
        return ImportItem(**dict(zip(_ITEM_COLS.split(", "), row, strict=True)))

    def get_item(self, item_id: str) -> ImportItem | None:
        row = self._conn.execute(f"SELECT {_ITEM_COLS} FROM import_items WHERE id = ?", (item_id,)).fetchone()
        return self._item(row) if row else None

    def next_ready(self, now: datetime) -> ImportItem | None:
        # proxima_tentativa é ISO em UTC; a comparação lexicográfica equivale à cronológica
        row = self._conn.execute(
            f"SELECT {_ITEM_COLS} FROM import_items WHERE status = 'NA_FILA' "
            "AND (proxima_tentativa IS NULL OR proxima_tentativa <= ?) ORDER BY seq LIMIT 1",
            (now.isoformat(),),
        ).fetchone()
        return self._item(row) if row else None

    def set_status(self, item_id: str, status: str, **fields) -> None:
        bad = set(fields) - _SETTABLE
        if bad:
            raise ValueError(f"campos inválidos: {sorted(bad)}")
        sets = ", ".join(["status = ?", *(f"{k} = ?" for k in fields)])
        self._conn.execute(
            f"UPDATE import_items SET {sets} WHERE id = ?", (status, *fields.values(), item_id)
        )
        self._conn.commit()

    def requeue_reading(self) -> int:
        cur = self._conn.execute("UPDATE import_items SET status = 'NA_FILA' WHERE status = 'LENDO'")
        self._conn.commit()
        return cur.rowcount

    def get_batch(self, batch_id: str) -> ImportBatch | None:
        row = self._conn.execute(
            "SELECT id, criado_em FROM import_batches WHERE id = ?", (batch_id,)
        ).fetchone()
        if row is None:
            return None
        rows = self._conn.execute(
            f"SELECT {_ITEM_COLS} FROM import_items WHERE batch_id = ? ORDER BY seq", (batch_id,)
        ).fetchall()
        return ImportBatch(id=row[0], criado_em=row[1], itens=[self._item(r) for r in rows])

    def list_batches(self, limit: int = 20) -> list[ImportBatch]:
        ids = [
            r[0]
            for r in self._conn.execute(
                "SELECT id FROM import_batches ORDER BY rowid DESC LIMIT ?", (limit,)
            )
        ]
        return [b for i in ids if (b := self.get_batch(i)) is not None]

    def add_failure(self, item_id: str, parcial: dict, erros: list[str]) -> str:
        fid = str(uuid.uuid4())
        self._conn.execute(
            "INSERT INTO import_failures (id, item_id, dados_parciais, erros) VALUES (?, ?, ?, ?)",
            (fid, item_id, json.dumps(parcial), json.dumps(erros)),
        )
        self._conn.commit()
        return fid

    _FAIL_SQL = (
        "SELECT f.id, f.item_id, i.print_id, f.dados_parciais, f.erros, f.status "
        "FROM import_failures f JOIN import_items i ON i.id = f.item_id"
    )

    @staticmethod
    def _failure(r) -> ImportFailure:
        return ImportFailure(
            id=r[0], item_id=r[1], print_id=r[2], parcial=json.loads(r[3]), erros=json.loads(r[4]), status=r[5]
        )

    def list_failures(self, status: str | None = "ABERTA") -> list[ImportFailure]:
        if status is None:
            rows = self._conn.execute(f"{self._FAIL_SQL} ORDER BY f.rowid").fetchall()
        else:
            rows = self._conn.execute(
                f"{self._FAIL_SQL} WHERE f.status = ? ORDER BY f.rowid", (status,)
            ).fetchall()
        return [self._failure(r) for r in rows]

    def get_failure(self, failure_id: str) -> ImportFailure | None:
        row = self._conn.execute(f"{self._FAIL_SQL} WHERE f.id = ?", (failure_id,)).fetchone()
        return self._failure(row) if row else None

    def delete_open_failures(self, item_id: str) -> int:
        cur = self._conn.execute(
            "DELETE FROM import_failures WHERE item_id = ? AND status = 'ABERTA'", (item_id,)
        )
        self._conn.commit()
        return cur.rowcount

    def set_failure_status(self, failure_id: str, status: str) -> None:
        self._conn.execute("UPDATE import_failures SET status = ? WHERE id = ?", (status, failure_id))
        self._conn.commit()
