"""Duration math, range clipping, midnight split, DST and display formatting."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.reports.timecalc import (
    bucket_totals,
    clip_seconds,
    day_bounds,
    duration_seconds,
    format_decimal_hours,
    format_hm_long,
    format_hm_short,
    intervals_overlap,
    preset_range,
    split_by_local_day,
    week_start_date,
)

NY = ZoneInfo("America/New_York")


def ny(*args) -> datetime:
    return datetime(*args, tzinfo=NY)


# ---------- duration ----------


def test_duration_is_whole_seconds_from_timestamps():
    assert duration_seconds(ny(2026, 10, 22, 18, 30), ny(2026, 10, 22, 21, 45)) == 3 * 3600 + 15 * 60


def test_duration_floors_fractional_seconds():
    start = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    assert duration_seconds(start, start + timedelta(seconds=59, microseconds=999_999)) == 59


def test_duration_negative_when_end_before_start():
    assert duration_seconds(ny(2026, 1, 2, 10), ny(2026, 1, 2, 9)) == -3600


def test_naive_datetimes_are_treated_as_utc():
    assert duration_seconds(datetime(2026, 1, 1, 0, 0), datetime(2026, 1, 1, 1, 0, tzinfo=UTC)) == 3600


# ---------- range clipping ----------


@pytest.mark.parametrize(
    "start,end,a,b,expected_minutes",
    [
        ((9, 0), (11, 0), (8, 0), (12, 0), 120),  # fully inside
        ((7, 0), (9, 0), (8, 0), (12, 0), 60),  # starts before range
        ((11, 0), (13, 0), (8, 0), (12, 0), 60),  # ends after range
        ((7, 0), (13, 0), (8, 0), (12, 0), 240),  # covers range
        ((5, 0), (7, 0), (8, 0), (12, 0), 0),  # entirely before
        ((12, 0), (13, 0), (8, 0), (12, 0), 0),  # starts exactly at range end (half-open)
    ],
)
def test_clip_seconds(start, end, a, b, expected_minutes):
    d = (2026, 10, 22)
    assert clip_seconds(ny(*d, *start), ny(*d, *end), ny(*d, *a), ny(*d, *b)) == expected_minutes * 60


def test_clip_with_open_bounds():
    s, e = ny(2026, 10, 22, 9), ny(2026, 10, 22, 10)
    assert clip_seconds(s, e, None, None) == 3600
    assert clip_seconds(s, e, ny(2026, 10, 22, 9, 30), None) == 1800
    assert clip_seconds(s, e, None, ny(2026, 10, 22, 9, 15)) == 900


def test_adjacent_ranges_never_double_count():
    s, e = ny(2026, 10, 18, 20, 15), ny(2026, 10, 19, 0, 45)
    a1, b1 = day_bounds(date(2026, 10, 18), NY)
    a2, b2 = day_bounds(date(2026, 10, 19), NY)
    assert clip_seconds(s, e, a1, b1) + clip_seconds(s, e, a2, b2) == duration_seconds(s, e)


# ---------- midnight split ----------


def test_session_crossing_midnight_is_split_across_days():
    # Mockup: Oct 18 8:15 PM – 12:45 AM → 3h 45m on Oct 18 and 45m on Oct 19.
    split = split_by_local_day(ny(2026, 10, 18, 20, 15), ny(2026, 10, 19, 0, 45), NY)
    assert split == {date(2026, 10, 18): 3 * 3600 + 45 * 60, date(2026, 10, 19): 45 * 60}


def test_session_within_one_day_has_one_key():
    split = split_by_local_day(ny(2026, 10, 22, 18, 30), ny(2026, 10, 22, 21, 45), NY)
    assert split == {date(2026, 10, 22): 3 * 3600 + 15 * 60}


def test_session_ending_exactly_at_midnight_stays_on_one_day():
    split = split_by_local_day(ny(2026, 10, 22, 22, 0), ny(2026, 10, 23, 0, 0), NY)
    assert split == {date(2026, 10, 22): 7200}


def test_multi_day_split_sums_to_duration():
    s, e = ny(2026, 10, 20, 22, 0), ny(2026, 10, 22, 2, 0)
    split = split_by_local_day(s, e, NY)
    assert split == {date(2026, 10, 20): 7200, date(2026, 10, 21): 86400, date(2026, 10, 22): 7200}
    assert sum(split.values()) == duration_seconds(s, e)


def test_split_uses_local_midnight_not_utc_midnight():
    # 7 PM – 9 PM New York (EDT) is 23:00 – 01:00 UTC, but it's all one local day.
    split = split_by_local_day(datetime(2026, 10, 22, 23, tzinfo=UTC), datetime(2026, 10, 23, 1, tzinfo=UTC), NY)
    assert split == {date(2026, 10, 22): 7200}


def test_bucket_totals_by_day_week_month():
    sessions = [
        (ny(2026, 10, 17, 20, 15), ny(2026, 10, 18, 0, 45)),  # Sat → Sun, crosses week boundary
        (ny(2026, 10, 31, 23, 0), ny(2026, 11, 1, 1, 0)),  # Sat → Sun, crosses month and week boundary
    ]
    days = bucket_totals(sessions, NY, "day")
    assert days[date(2026, 10, 17)] == 13500 and days[date(2026, 10, 18)] == 2700
    weeks = bucket_totals(sessions, NY, "week", week_start_weekday=6)
    assert weeks == {date(2026, 10, 11): 13500, date(2026, 10, 18): 2700, date(2026, 10, 25): 3600, date(2026, 11, 1): 3600}
    months = bucket_totals(sessions, NY, "month")
    assert months == {date(2026, 10, 1): 13500 + 2700 + 3600, date(2026, 11, 1): 3600}


def test_bucket_totals_clip_to_range_first():
    sessions = [(ny(2026, 10, 18, 20, 15), ny(2026, 10, 19, 0, 45))]
    a, b = day_bounds(date(2026, 10, 19), NY)
    assert bucket_totals(sessions, NY, "day", a, b) == {date(2026, 10, 19): 2700}


# ---------- DST ----------


def test_spring_forward_day_is_23_hours():
    a, b = day_bounds(date(2026, 3, 8), NY)
    assert duration_seconds(a, b) == 23 * 3600


def test_fall_back_day_is_25_hours():
    a, b = day_bounds(date(2026, 11, 1), NY)
    assert duration_seconds(a, b) == 25 * 3600


def test_session_across_fall_back_counts_real_elapsed_time():
    # 12:30 AM EDT → 3:30 AM EST on Nov 1 2026 is 4 real hours (the 1 AM hour happens twice).
    start = datetime(2026, 11, 1, 4, 30, tzinfo=UTC)  # 00:30 EDT
    end = datetime(2026, 11, 1, 8, 30, tzinfo=UTC)  # 03:30 EST
    assert duration_seconds(start, end) == 4 * 3600
    assert split_by_local_day(start, end, NY) == {date(2026, 11, 1): 4 * 3600}


def test_session_across_spring_forward_counts_real_elapsed_time():
    # 1:00 AM EST → 4:00 AM EDT on Mar 8 2026 is 2 real hours.
    start = datetime(2026, 3, 8, 6, 0, tzinfo=UTC)
    end = datetime(2026, 3, 8, 8, 0, tzinfo=UTC)
    assert start.astimezone(NY).hour == 1 and end.astimezone(NY).hour == 4
    assert split_by_local_day(start, end, NY) == {date(2026, 3, 8): 7200}


def test_overnight_session_across_dst_split_at_local_midnight():
    # Sat Oct 31 10 PM EDT → Sun Nov 1 2 AM EST = 5 real hours: 2h on Oct 31, 3h on Nov 1.
    start = ny(2026, 10, 31, 22, 0)
    end = datetime(2026, 11, 1, 7, 0, tzinfo=UTC)  # 2 AM EST
    assert split_by_local_day(start, end, NY) == {date(2026, 10, 31): 7200, date(2026, 11, 1): 3 * 3600}


# ---------- presets and weeks ----------


def test_week_starts_sunday_by_default():
    assert week_start_date(date(2026, 10, 23), 6) == date(2026, 10, 18)  # Fri → Sun
    assert week_start_date(date(2026, 10, 18), 6) == date(2026, 10, 18)  # Sunday itself
    assert week_start_date(date(2026, 10, 23), 0) == date(2026, 10, 19)  # Monday start


def test_presets_use_local_calendar():
    now = datetime(2026, 10, 24, 2, 0, tzinfo=UTC)  # still Oct 23, 10 PM in New York
    a, b = preset_range("today", now, NY)
    assert a == ny(2026, 10, 23).astimezone(UTC) and b == ny(2026, 10, 24).astimezone(UTC)
    a, b = preset_range("week", now, NY)
    assert a == ny(2026, 10, 18).astimezone(UTC) and b == ny(2026, 10, 25).astimezone(UTC)
    a, b = preset_range("month", now, NY)
    assert a == ny(2026, 10, 1).astimezone(UTC) and b == ny(2026, 11, 1).astimezone(UTC)


def test_december_month_preset_rolls_year():
    a, b = preset_range("month", ny(2026, 12, 15, 12), NY)
    assert b == ny(2027, 1, 1).astimezone(UTC)


# ---------- overlap ----------


@pytest.mark.parametrize(
    "a,b,expected",
    [
        (((16, 0), (20, 30)), ((19, 45), (21, 0)), True),  # mockup: 4:00–8:30 overlaps 7:45–9:00
        (((9, 0), (13, 0)), ((12, 30), (14, 0)), True),
        (((9, 0), (12, 0)), ((12, 0), (14, 0)), False),  # touching is not overlapping
        (((9, 0), (10, 0)), ((11, 0), (12, 0)), False),
        (((9, 0), (17, 0)), ((10, 0), (11, 0)), True),  # containment
    ],
)
def test_intervals_overlap(a, b, expected):
    d = (2026, 10, 22)
    (a1, a2), (b1, b2) = a, b
    assert intervals_overlap(ny(*d, *a1), ny(*d, *a2), ny(*d, *b1), ny(*d, *b2)) is expected
    assert intervals_overlap(ny(*d, *b1), ny(*d, *b2), ny(*d, *a1), ny(*d, *a2)) is expected


# ---------- formatting ----------


@pytest.mark.parametrize(
    "seconds,short,long,dec",
    [
        (9000, "2h 30m", "2 hours 30 minutes", "2.5 h"),
        (672300, "186h 45m", "186 hours 45 minutes", "186.75 h"),
        (3600, "1h 0m", "1 hour", "1 h"),
        (60, "1m", "1 minute", "0.02 h"),
        (0, "0m", "0 minutes", "0 h"),
        (8442, "2h 20m", "2 hours 20 minutes", "2.35 h"),  # 2.345 h rounds half-up; minutes floor
        (3599, "59m", "59 minutes", "1 h"),
        (18, "0m", "0 minutes", "0.01 h"),  # 0.005 h rounds half-up to 0.01
    ],
)
def test_formats(seconds, short, long, dec):
    assert format_hm_short(seconds) == short
    assert format_hm_long(seconds) == long
    assert format_decimal_hours(seconds) == dec
