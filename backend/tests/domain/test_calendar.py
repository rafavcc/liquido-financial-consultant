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


def test_adjust_next_and_offset_return_plain_dates():
    from datetime import date
    cal = get_calendar()
    assert type(cal.adjust_next(date(2027, 1, 1))) is date
    assert cal.adjust_next(date(2027, 1, 1)) == date(2027, 1, 4)
    assert type(cal.add_business_days(date(2026, 11, 19), 5)) is date


def test_index_matches_bizdays_library():
    import random
    from datetime import timedelta

    from bizdays import Calendar

    ref = Calendar.load(name="ANBIMA")
    rng = random.Random(1)
    for _ in range(3000):
        a = date(2026, 1, 1) + timedelta(days=rng.randint(0, 9000))
        b = a + timedelta(days=rng.randint(1, 3000))
        assert cal.business_days_between(a, b) == ref.bizdays(a, b)
        assert cal.adjust_next(a) == ref.adjust_next(a)
        assert cal.is_business_day(a) == bool(ref.isbizday(a))
        assert cal.business_days(a, a + timedelta(days=30)) == [
            d for d in (a + timedelta(days=i) for i in range(1, 31)) if ref.isbizday(d)
        ]
