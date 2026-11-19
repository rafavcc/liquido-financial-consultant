from datetime import date

from app.domain.calendar import get_calendar

cal = get_calendar()


def test_holidays_and_weekends():
    assert not cal.is_business_day(date(2026, 2, 17))  # Carnaval
    assert not cal.is_business_day(date(2026, 4, 21))  # Tiradentes
    assert not cal.is_business_day(date(2026, 11, 20))  # Consciência Negra
    assert not cal.is_business_day(date(2026, 11, 21))  # sábado
    assert cal.is_business_day(date(2026, 11, 19))


def test_between_excludes_start_includes_end():
    assert cal.business_days_between(date(2026, 12, 24), date(2026, 12, 28)) == 1
    assert cal.business_days_between(date(2026, 11, 19), date(2026, 11, 19)) == 0
    assert cal.business_days(date(2026, 11, 18), date(2026, 11, 23)) == [
        date(2026, 11, 19),
        date(2026, 11, 23),
    ]


def test_adjust_and_month_end():
    assert cal.adjust_next(date(2027, 1, 1)) == date(2027, 1, 4)
    assert cal.adjust_next(date(2026, 11, 19)) == date(2026, 11, 19)
    assert cal.last_business_day_of_month(2027, 5) == date(2027, 5, 31)
    assert cal.last_business_day_of_month(2026, 5) == date(2026, 5, 29)
    assert cal.add_business_days(date(2026, 11, 19), 1) == date(2026, 11, 23)
