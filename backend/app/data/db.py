import sqlite3
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS products (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS market_cache (
    source TEXT PRIMARY KEY, payload TEXT, fetched_at TEXT, error TEXT, failed_at TEXT
);
"""


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.executescript(_SCHEMA)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(market_cache)")}
    if "failed_at" not in columns:  # bancos criados antes do cooldown
        conn.execute("ALTER TABLE market_cache ADD COLUMN failed_at TEXT")
    conn.commit()
    return conn
