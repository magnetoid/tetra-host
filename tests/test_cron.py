from datetime import UTC, datetime, timedelta

from app.services.cron import cron_matches, is_valid_cron


def dt(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=UTC)


def test_wildcard_matches_every_minute():
    assert cron_matches("* * * * *", dt(2026, 7, 10, 3, 4))


def test_specific_minute_and_hour():
    assert cron_matches("30 2 * * *", dt(2026, 7, 10, 2, 30))
    assert not cron_matches("30 2 * * *", dt(2026, 7, 10, 2, 31))
    assert not cron_matches("30 2 * * *", dt(2026, 7, 10, 3, 30))


def test_step_values():
    assert cron_matches("*/15 * * * *", dt(2026, 7, 10, 0, 0))
    assert cron_matches("*/15 * * * *", dt(2026, 7, 10, 0, 15))
    assert not cron_matches("*/15 * * * *", dt(2026, 7, 10, 0, 16))


def test_lists_and_ranges():
    assert cron_matches("0 9-17 * * *", dt(2026, 7, 10, 9, 0))
    assert cron_matches("0 9-17 * * *", dt(2026, 7, 10, 17, 0))
    assert not cron_matches("0 9-17 * * *", dt(2026, 7, 10, 8, 0))
    assert cron_matches("0 0 1,15 * *", dt(2026, 7, 15, 0, 0))
    assert not cron_matches("0 0 1,15 * *", dt(2026, 7, 16, 0, 0))


def test_day_of_week_derived():
    d = dt(2026, 7, 10, 9, 0)
    cron_dow = d.isoweekday() % 7
    assert cron_matches(f"0 9 * * {cron_dow}", d)
    assert not cron_matches(f"0 9 * * {(cron_dow + 1) % 7}", d)


def test_sunday_accepts_0_and_7():
    sunday = dt(2026, 7, 12, 0, 0)
    while sunday.isoweekday() != 7:
        sunday = sunday + timedelta(days=1)
    assert cron_matches("0 0 * * 0", sunday)
    assert cron_matches("0 0 * * 7", sunday)


def test_validity():
    assert not cron_matches("bad", dt(2026, 7, 10, 0, 0))
    assert not is_valid_cron("* * *")
    assert not is_valid_cron("* * * * abc")
    assert is_valid_cron("*/5 0-12 1,15 * 1-5")
