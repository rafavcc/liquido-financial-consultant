import sqlite3
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS products (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS market_cache (
    source TEXT PRIMARY KEY, payload TEXT, fetched_at TEXT, error TEXT, failed_at TEXT
);
CREATE TABLE IF NOT EXISTS prints (
    id TEXT PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE, mime TEXT NOT NULL, caminho TEXT NOT NULL,
    criado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS import_batches (id TEXT PRIMARY KEY, criado_em TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS import_items (
    id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, print_id TEXT NOT NULL, nome_arquivo TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'NA_FILA', tentativas INTEGER NOT NULL DEFAULT 0,
    proxima_tentativa TEXT, erro TEXT, resposta_bruta TEXT,
    criados INTEGER NOT NULL DEFAULT 0, renovados INTEGER NOT NULL DEFAULT 0,
    ignorados INTEGER NOT NULL DEFAULT 0, falhas INTEGER NOT NULL DEFAULT 0,
    iniciado_em TEXT, concluido_em TEXT, seq INTEGER
);
CREATE TABLE IF NOT EXISTS import_failures (
    id TEXT PRIMARY KEY, item_id TEXT NOT NULL, dados_parciais TEXT NOT NULL, erros TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ABERTA'
);
"""


def connect(path: Path, check_same_thread: bool = True) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), check_same_thread=check_same_thread)
    conn.executescript(_SCHEMA)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(market_cache)")}
    if "failed_at" not in columns:  # bancos criados antes do cooldown
        conn.execute("ALTER TABLE market_cache ADD COLUMN failed_at TEXT")
    conn.commit()
    return conn
