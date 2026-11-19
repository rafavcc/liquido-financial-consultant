from datetime import date, timedelta
from functools import lru_cache

import pandas as pd
from bizdays import Calendar


class BusinessCalendar:
    """Calendário ANBIMA com índice ordinal O(1). `business_days` é (início, fim]; a contagem segue o bizdays."""

    def __init__(self, calendar: Calendar) -> None:
        self._cal = calendar
        self._first: date = self._to_date(calendar.startdate)
        self._last: date = self._to_date(calendar.enddate)
        holidays = {self._to_date(h) for h in calendar.holidays}
        self._bdays: list[date] = []
        self._count: list[int] = []  # _count[i] = dias úteis em [início, início+i]
        d = self._first
        one = timedelta(days=1)
        while d <= self._last:
            if d.weekday() < 5 and d not in holidays:
                self._bdays.append(d)
            self._count.append(len(self._bdays))
            d += one

    @staticmethod
    def _to_date(d: object) -> date:
        return d if type(d) is date else pd.Timestamp(d).date()

    def _idx(self, d: date) -> int:
        if not (self._first <= d <= self._last):
            raise ValueError(f"data {d} fora do calendário ANBIMA")
        return (d - self._first).days

    def is_business_day(self, d: date) -> bool:
        i = self._idx(d)
        return self._count[i] - (self._count[i - 1] if i else 0) == 1

    def business_days_between(self, start: date, end: date) -> int:
        if end <= start:
            return 0
        # convenção do bizdays: contagem até `end` a partir do primeiro dia útil >= `start`
        # (preservada para não alterar os valores calculados; coincide com (início, fim] se `start` é útil)
        return max(0, self._count[self._idx(end)] - self._count[self._idx(self.adjust_next(start))])

    def business_days(self, start: date, end: date) -> list[date]:
        if end <= start:
            return []
        return self._bdays[self._count[self._idx(start)] : self._count[self._idx(end)]]

    def adjust_next(self, d: date) -> date:
        if self.is_business_day(d):
            return d
        return self._bdays[self._count[self._idx(d)]]

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
