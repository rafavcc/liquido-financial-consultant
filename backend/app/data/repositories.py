import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime


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
