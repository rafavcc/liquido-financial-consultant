from bisect import bisect_right
from datetime import date, timedelta
from decimal import Decimal

from app.data.market import MarketSnapshot
from app.domain.calendar import BusinessCalendar, get_calendar
from app.domain.settings import Settings

D = Decimal

_DAYS_YEAR = D(252)
_ONE = D(1)


class IndexPath:
    """Projeção de Selic/CDI/IPCA: âncoras anuais interpoladas por dia corrido (design 7.4)."""

    def __init__(
        self,
        anchors: list[tuple[date, Decimal]],
        ipca_monthly: dict[str, Decimal],
        ipca_annual: dict[int, Decimal],
        spread_cdi_selic: Decimal,
        fonte: str,
        cal: BusinessCalendar,
        today: date,
    ) -> None:
        self._anchors = sorted(anchors)
        self._anchor_dates = [d for d, _ in self._anchors]
        self._ipca_monthly = ipca_monthly
        self._ipca_annual = ipca_annual
        self._spread_cdi_selic = spread_cdi_selic
        self.fonte = fonte
        self._cal = cal
        self._today = today
        self._selic_cache: dict[date, Decimal] = {}
        self._cdi_d_cache: dict[date, Decimal] = {}
        self._selic_d_cache: dict[date, Decimal] = {}
        self._ipca_day_cache: dict[tuple[int, int], Decimal] = {}

    @classmethod
    def build(
        cls, snapshot: MarketSnapshot, settings: Settings, cal: BusinessCalendar, today: date
    ) -> "IndexPath | None":
        manual = settings.projection_mode == "manual"
        anchors: list[tuple[date, Decimal]] = []
        if snapshot.selic_meta is not None:
            anchors.append((today, snapshot.selic_meta))
        elif not manual:
            return None

        if manual:
            selic_by_year = settings.manual_selic_by_year
            ipca_annual = dict(settings.manual_ipca_by_year)
            ipca_monthly: dict[str, Decimal] = {}
            fonte = "Cenário manual"
        else:
            selic_by_year = snapshot.focus_selic_anual
            ipca_annual = dict(snapshot.focus_ipca_anual)
            ipca_monthly = dict(snapshot.focus_ipca_mensal)
            fonte = "Focus " + (snapshot.focus_data.strftime("%d/%m/%Y") if snapshot.focus_data else "—")

        for year, value in selic_by_year.items():
            end = date(year, 12, 31)
            if end > today:
                anchors.append((end, value))
        if not anchors:
            return None
        return cls(anchors, ipca_monthly, ipca_annual, settings.spread_cdi_selic, fonte, cal, today)

    # --- Selic / CDI -------------------------------------------------------------------------

    def selic_aa(self, d: date) -> Decimal:
        cached = self._selic_cache.get(d)
        if cached is not None:
            return cached
        dates, anchors = self._anchor_dates, self._anchors
        i = bisect_right(dates, d)
        if i == 0:
            value = anchors[0][1]
        elif i == len(anchors):
            value = anchors[-1][1]
        else:
            (d0, v0), (d1, v1) = anchors[i - 1], anchors[i]
            value = v0 + (v1 - v0) * D((d - d0).days) / D((d1 - d0).days)
        self._selic_cache[d] = value
        return value

    def cdi_aa(self, d: date) -> Decimal:
        return self.selic_aa(d) - self._spread_cdi_selic

    def _daily(self, cache: dict[date, Decimal], d: date, annual: Decimal) -> Decimal:
        value = cache.get(d)
        if value is None:
            value = (_ONE + annual) ** (_ONE / _DAYS_YEAR) - _ONE
            cache[d] = value
        return value

    def _cdi_d(self, d: date) -> Decimal:
        return self._daily(self._cdi_d_cache, d, self.cdi_aa(d))

    def _selic_d(self, d: date) -> Decimal:
        return self._daily(self._selic_d_cache, d, self.selic_aa(d))

    def cdi_factor(
        self, start: date, end: date, pct: Decimal = _ONE, spread: Decimal = D(0)
    ) -> Decimal:
        spread_d = (_ONE + spread) ** (_ONE / _DAYS_YEAR) if spread else _ONE
        factor = _ONE
        for d in self._cal.business_days(start, end):
            factor *= (_ONE + pct * self._cdi_d(d)) * spread_d
        return factor

    def selic_factor(self, start: date, end: date) -> Decimal:
        factor = _ONE
        for d in self._cal.business_days(start, end):
            factor *= _ONE + self._selic_d(d)
        return factor

    # --- IPCA --------------------------------------------------------------------------------

    def ipca_month(self, year: int, month: int) -> Decimal:
        monthly = self._ipca_monthly.get(f"{year}-{month:02d}")
        if monthly is not None:
            return monthly
        if not self._ipca_annual:
            raise ValueError("sem projeção de IPCA")
        annual = self._ipca_annual.get(year)
        if annual is None:
            annual = self._ipca_annual[max(self._ipca_annual)]
        return (_ONE + annual) ** (_ONE / D(12)) - _ONE

    def _ipca_day(self, year: int, month: int) -> Decimal:
        key = (year, month)
        value = self._ipca_day_cache.get(key)
        if value is None:
            first = date(year, month, 1)
            last = (first + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            du = self._cal.business_days_between(first - timedelta(days=1), last)
            value = (_ONE + self.ipca_month(year, month)) ** (_ONE / D(du))
            self._ipca_day_cache[key] = value
        return value

    def ipca_factor(self, start: date, end: date) -> Decimal:
        factor = _ONE
        for d in self._cal.business_days(start, end):
            factor *= self._ipca_day(d.year, d.month)
        return factor

    @staticmethod
    def pre_factor(rate: Decimal, start: date, end: date) -> Decimal:
        du = get_calendar().business_days_between(start, end)
        return (_ONE + rate) ** (D(du) / _DAYS_YEAR)

    # --- Tela Mercado ------------------------------------------------------------------------

    def yearly_table(self) -> list[tuple[int, Decimal, Decimal]]:
        years = {d.year for d in self._anchor_dates if d >= self._today} | set(self._ipca_annual)
        years |= {int(k[:4]) for k in self._ipca_monthly}
        years = {y for y in years if y >= self._today.year}
        rows = []
        for year in range(self._today.year, max(years, default=self._today.year) + 1):
            ipca = _ONE
            for month in range(1, 13):
                ipca *= _ONE + self.ipca_month(year, month)
            rows.append((year, self.selic_aa(date(year, 12, 31)), ipca - _ONE))
        return rows
