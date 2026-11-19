from datetime import date, datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path

import pytest

from app.data.db import connect
from app.data.market import FixtureFetchers, MarketService, MarketSnapshot
from app.data.repositories import MarketCacheRepository

FIX = Path(__file__).parent.parent / "fixtures" / "market"
T0 = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)


class CountingFetchers:
    def __init__(self, inner):
        self.inner = inner
        self.calls = {"bcb": 0, "focus": 0, "tesouro": 0}
        self.fail: set[str] = set()

    def _go(self, name, fn, *args):
        self.calls[name] += 1
        if name in self.fail:
            raise RuntimeError(f"{name} fora do ar")
        return fn(*args)

    def fetch_bcb(self, today):
        return self._go("bcb", self.inner.fetch_bcb, today)

    def fetch_focus(self):
        return self._go("focus", self.inner.fetch_focus)

    def fetch_tesouro(self):
        return self._go("tesouro", self.inner.fetch_tesouro)


class Clock:
    def __init__(self):
        self.t = T0

    def __call__(self):
        return self.t


@pytest.fixture
def env(tmp_path):
    fetchers = CountingFetchers(FixtureFetchers(FIX))
    clock = Clock()
    cache = MarketCacheRepository(connect(tmp_path / "t.db"))
    return MarketService(cache, fetchers, clock), fetchers, clock


def test_first_call_fetches_all_and_builds_snapshot(env):
    svc, f, _ = env
    snap = svc.get_snapshot(ttl_hours=6)
    assert f.calls == {"bcb": 1, "focus": 1, "tesouro": 1}
    assert snap.selic_meta == D("0.1375")
    assert snap.ipca_12m is not None and snap.ipca_12m_ref <= date(2026, 11, 19)
    assert snap.focus_data == date(2026, 11, 13) and snap.focus_selic_anual[2027] > 0
    assert snap.tesouro and snap.tesouro_data_base == snap.tesouro[0].data_base
    assert set(snap.fetched_at) == {"bcb", "focus", "tesouro"} and snap.errors == {}


def test_within_ttl_uses_cache_after_ttl_refetches_force_ignores_ttl(env):
    svc, f, clock = env
    svc.get_snapshot(6)
    clock.t = T0 + timedelta(hours=5, minutes=59)
    snap = svc.get_snapshot(6)
    assert f.calls == {"bcb": 1, "focus": 1, "tesouro": 1}
    assert snap.focus_selic_anual  # veio do cache, tipos restaurados
    assert isinstance(next(iter(snap.focus_selic_anual)), int)
    clock.t = T0 + timedelta(hours=6, minutes=1)
    svc.get_snapshot(6)
    assert f.calls == {"bcb": 2, "focus": 2, "tesouro": 2}
    svc.get_snapshot(6, force=True)
    assert f.calls == {"bcb": 3, "focus": 3, "tesouro": 3}


def test_failure_keeps_previous_payload_and_records_error(env):
    svc, f, clock = env
    first = svc.get_snapshot(6)
    clock.t = T0 + timedelta(hours=7)
    f.fail.add("focus")
    snap = svc.get_snapshot(6)
    assert snap.focus_selic_anual == first.focus_selic_anual
    assert "focus" in snap.errors and "fora do ar" in snap.errors["focus"]
    assert snap.fetched_at["focus"] == T0  # carimbo antigo preservado
    assert snap.fetched_at["bcb"] == clock.t and "bcb" not in snap.errors
    # falha não renova o TTL: tenta de novo na próxima chamada
    svc.get_snapshot(6)
    assert f.calls["focus"] == 3


def test_empty_cache_and_failure_gives_empty_fields_and_error(env):
    svc, f, _ = env
    f.fail.add("focus")
    snap = svc.get_snapshot(6)
    assert snap.focus_selic_anual == {} and snap.focus_data is None
    assert "focus" in snap.errors and "focus" not in snap.fetched_at
    assert snap.selic_meta == D("0.1375")  # outras fontes seguem


def test_all_sources_down_equals_empty_plus_errors(env):
    svc, f, _ = env
    f.fail.update({"bcb", "focus", "tesouro"})
    snap = svc.get_snapshot(6)
    assert snap.model_copy(update={"errors": {}}) == MarketSnapshot.empty()
    assert set(snap.errors) == {"bcb", "focus", "tesouro"}


def test_empty_snapshot():
    s = MarketSnapshot.empty()
    assert s.selic_meta is None and s.focus_selic_anual == {} and s.tesouro == [] and s.errors == {}
