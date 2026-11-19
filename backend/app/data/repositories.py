import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime

from pydantic import ValidationError

from app.domain.products.base import ProductData
from app.domain.settings import Settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CacheEntry:
    payload: dict | None
    fetched_at: datetime | None
    error: str | None
    failed_at: datetime | None = None


class MarketCacheRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def load(self, source: str) -> CacheEntry | None:
        row = self._conn.execute(
            "SELECT payload, fetched_at, error, failed_at FROM market_cache WHERE source = ?", (source,)
        ).fetchone()
        if row is None:
            return None
        payload, fetched_at, error, failed_at = row
        return CacheEntry(
            payload=json.loads(payload) if payload is not None else None,
            fetched_at=datetime.fromisoformat(fetched_at) if fetched_at else None,
            error=error,
            failed_at=datetime.fromisoformat(failed_at) if failed_at else None,
        )

    def save(self, source: str, payload: dict, fetched_at: datetime) -> None:
        self._conn.execute(
            "INSERT INTO market_cache (source, payload, fetched_at, error, failed_at) VALUES (?, ?, ?, NULL, NULL) "
            "ON CONFLICT(source) DO UPDATE SET payload = excluded.payload, "
            "fetched_at = excluded.fetched_at, error = NULL, failed_at = NULL",
            (source, json.dumps(payload), fetched_at.isoformat()),
        )
        self._conn.commit()

    def save_error(self, source: str, error: str, failed_at: datetime) -> None:
        self._conn.execute(
            "INSERT INTO market_cache (source, payload, fetched_at, error, failed_at) "
            "VALUES (?, NULL, NULL, ?, ?) "
            "ON CONFLICT(source) DO UPDATE SET error = excluded.error, failed_at = excluded.failed_at",
            (source, error, failed_at.isoformat()),
        )
        self._conn.commit()


class ProductRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list(self) -> list[ProductData]:
        rows = self._conn.execute("SELECT id, payload FROM products ORDER BY rowid").fetchall()
        out = []
        for id, payload in rows:
            try:
                out.append(ProductData.model_validate_json(payload))
            except ValidationError:  # um registro corrompido não pode derrubar a listagem
                log.exception("Produto %s com dados inválidos foi ignorado", id)
        return out

    def get(self, id: str) -> ProductData | None:
        row = self._conn.execute("SELECT payload FROM products WHERE id = ?", (id,)).fetchone()
        return ProductData.model_validate_json(row[0]) if row else None

    def create(self, data: ProductData) -> ProductData:
        data = data if data.id else data.model_copy(update={"id": str(uuid.uuid4())})
        self._conn.execute(
            "INSERT INTO products (id, payload) VALUES (?, ?)", (data.id, data.model_dump_json())
        )
        self._conn.commit()
        return data

    def update(self, id: str, data: ProductData) -> ProductData:
        data = data.model_copy(update={"id": id})
        self._conn.execute("UPDATE products SET payload = ? WHERE id = ?", (data.model_dump_json(), id))
        self._conn.commit()
        return data

    def delete(self, id: str) -> None:
        self._conn.execute("DELETE FROM products WHERE id = ?", (id,))
        self._conn.commit()

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]


class SettingsRepository:
    _KEY = "settings"

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def _kv_get(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def _kv_set(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO kv (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self._conn.commit()

    def get(self) -> Settings:
        raw = self._kv_get(self._KEY)
        return Settings.model_validate_json(raw) if raw else Settings()

    def save(self, s: Settings) -> None:
        self._kv_set(self._KEY, s.model_dump_json())

    def reset(self) -> Settings:
        s = Settings()
        self.save(s)
        return s

    def is_seeded(self) -> bool:
        return self._kv_get("seeded") == "1"

    def mark_seeded(self) -> None:
        self._kv_set("seeded", "1")
