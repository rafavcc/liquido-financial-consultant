import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CacheEntry:
    payload: dict | None
    fetched_at: datetime | None
    error: str | None


class MarketCacheRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def load(self, source: str) -> CacheEntry | None:
        row = self._conn.execute(
            "SELECT payload, fetched_at, error FROM market_cache WHERE source = ?", (source,)
        ).fetchone()
        if row is None:
            return None
        payload, fetched_at, error = row
        return CacheEntry(
            payload=json.loads(payload) if payload is not None else None,
            fetched_at=datetime.fromisoformat(fetched_at) if fetched_at else None,
            error=error,
        )

    def save(self, source: str, payload: dict, fetched_at: datetime) -> None:
        self._conn.execute(
            "INSERT INTO market_cache (source, payload, fetched_at, error) VALUES (?, ?, ?, NULL) "
            "ON CONFLICT(source) DO UPDATE SET payload = excluded.payload, "
            "fetched_at = excluded.fetched_at, error = NULL",
            (source, json.dumps(payload), fetched_at.isoformat()),
        )
        self._conn.commit()

    def save_error(self, source: str, error: str) -> None:
        self._conn.execute(
            "INSERT INTO market_cache (source, payload, fetched_at, error) VALUES (?, NULL, NULL, ?) "
            "ON CONFLICT(source) DO UPDATE SET error = excluded.error",
            (source, error),
        )
        self._conn.commit()
