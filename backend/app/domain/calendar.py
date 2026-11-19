from datetime import date, timedelta
from functools import lru_cache

import pandas as pd
from bizdays import Calendar


class BusinessCalendar:
    """Thin wrapper over the bizdays ANBIMA calendar. Ranges are (start, end]."""

    def __init__(self, calendar: Calendar) -> None:
        self._cal = calendar

    @staticmethod
    def _to_date(d: object) -> date:
        return d if type(d) is date else pd.Timestamp(d).date()

    @lru_cache(maxsize=65536)  # noqa: B019 - o calendário é singleton; chamadas repetidas dominam o custo
    def is_business_day(self, d: date) -> bool:
        return bool(self._cal.isbizday(d))

    @lru_cache(maxsize=65536)  # noqa: B019
    def business_days_between(self, start: date, end: date) -> int:
        if end <= start:
            return 0
        return int(self._cal.bizdays(start, end))

    def business_days(self, start: date, end: date) -> list[date]:
        if end <= start:
            return []
        return [
            d
            for d in (start + timedelta(days=i) for i in range(1, (end - start).days + 1))
            if self.is_business_day(d)
        ]

    def adjust_next(self, d: date) -> date:
        return self._to_date(self._cal.adjust_next(d))

    def add_business_days(self, d: date, n: int) -> date:
        return self._to_date(self._cal.offset(d, n))

    def last_business_day_of_month(self, year: int, month: int) -> date:
        first_next = date(year + (month == 12), month % 12 + 1, 1)
        d = first_next - timedelta(days=1)
        while not self.is_business_day(d):
            d -= timedelta(days=1)
        return d


@lru_cache(maxsize=1)
def get_calendar() -> BusinessCalendar:
    return BusinessCalendar(Calendar.load(name="ANBIMA"))
