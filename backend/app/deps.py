import json
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

from fastapi import Request

from app.data import db
from app.data.market import FixtureFetchers, HttpFetchers, MarketFetchers, MarketService, MarketSnapshot
from app.data.repositories import MarketCacheRepository, ProductRepository, SettingsRepository
from app.domain.calendar import get_calendar
from app.domain.indexes import IndexPath
from app.domain.products.base import ProductData, SimContext
from app.domain.settings import Settings

BACKEND_DIR = Path(__file__).resolve().parents[1]
SEED_FILE = Path(__file__).parent / "seed" / "products_example.json"


@dataclass
class Container:
    products: ProductRepository
    settings: SettingsRepository
    market: MarketService
    today_fn: Callable[[], date]
    static_dir: Path | None
    # uma conexão SQLite compartilhada entre threads: todo acesso (inclusive o do MarketService) sob este lock
    lock: threading.RLock = field(default_factory=threading.RLock)
    # single-flight da busca de rede; nunca é segurado junto com `lock` durante I/O de rede
    snapshot_lock: threading.Lock = field(default_factory=threading.Lock)

    def snapshot(self, force: bool = False) -> tuple[Settings, MarketSnapshot]:
        with self.snapshot_lock:
            with self.lock:
                settings = self.settings.get()
            return settings, self.market.get_snapshot(settings.market_cache_ttl_hours, force=force)

    def context(self, settings: Settings, snapshot: MarketSnapshot) -> SimContext:
        today = self.today_fn()
        cal = get_calendar()
        return SimContext(
            today=today, cal=cal, settings=settings, index=IndexPath.build(snapshot, settings, cal, today)
        )


class LockedMarketCache:
    """Serializa o acesso do MarketService à conexão compartilhada, sem segurar o lock na rede."""

    def __init__(self, inner: MarketCacheRepository, lock: threading.RLock) -> None:
        self._inner, self._lock = inner, lock

    def load(self, source: str):
        with self._lock:
            return self._inner.load(source)

    def save(self, source: str, payload: dict, fetched_at: datetime) -> None:
        with self._lock:
            self._inner.save(source, payload, fetched_at)

    def save_error(self, source: str, error: str, failed_at: datetime) -> None:
        with self._lock:
            self._inner.save_error(source, error, failed_at)


def _seed(products: ProductRepository, settings: SettingsRepository) -> None:
    if settings.is_seeded() or products.count() > 0:
        return
    for item in json.loads(SEED_FILE.read_text(encoding="utf-8")):
        products.create(ProductData.model_validate(item))
    settings.mark_seeded()


def build_container(
    db_path: Path | None,
    fetchers: MarketFetchers | None,
    static_dir: Path | None,
    today_fn: Callable[[], date],
) -> Container:
    db_path = db_path or Path(os.environ.get("LIQUIDO_DB", BACKEND_DIR / "data" / "liquido.db"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = db.connect(db_path, check_same_thread=False)
    if fetchers is None:
        fixtures = os.environ.get("LIQUIDO_MARKET_FIXTURES")
        if fixtures:
            fetchers = FixtureFetchers(Path(fixtures))
        else:
            import httpx

            fetchers = HttpFetchers(httpx.Client())
    if static_dir is None:
        static_dir = Path(os.environ.get("LIQUIDO_STATIC_DIR", BACKEND_DIR.parent / "frontend" / "dist"))
    products, settings = ProductRepository(conn), SettingsRepository(conn)
    _seed(products, settings)
    lock = threading.RLock()
    cache = LockedMarketCache(MarketCacheRepository(conn), lock)
    market = MarketService(cache, fetchers, lambda: datetime.now(UTC))
    return Container(products, settings, market, today_fn, static_dir, lock=lock)


def get_container(request: Request) -> Container:
    return request.app.state.container
