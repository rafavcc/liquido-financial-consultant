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

    def snapshot(self, force: bool = False) -> tuple[Settings, MarketSnapshot]:
        with self.lock:  # single-flight: uma busca de rede por vez
            settings = self.settings.get()
            return settings, self.market.get_snapshot(settings.market_cache_ttl_hours, force=force)

    def context(self, settings: Settings, snapshot: MarketSnapshot) -> SimContext:
        today = self.today_fn()
        cal = get_calendar()
        return SimContext(
            today=today, cal=cal, settings=settings, index=IndexPath.build(snapshot, settings, cal, today)
        )


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
    market = MarketService(MarketCacheRepository(conn), fetchers, lambda: datetime.now(UTC))
    return Container(products, settings, market, today_fn, static_dir)


def get_container(request: Request) -> Container:
    return request.app.state.container
