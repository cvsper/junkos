"""Business-timezone helpers.

These pin the contract that every scheduled_at writer and renderer relies on:
people type Florida wall-clock, the database holds UTC, and both DST halves
of the year round-trip cleanly.
"""
from datetime import datetime, timezone

import pytest

import timeutils as tu


# --- parsing ---------------------------------------------------------------

@pytest.mark.parametrize("date_str,time_str,expected_utc", [
    ("2026-07-15", "8-10", "2026-07-15T12:00:00+00:00"),      # EDT (UTC-4), slot range
    ("2026-07-15", "16-18", "2026-07-15T20:00:00+00:00"),
    ("2026-01-15", "09:00", "2026-01-15T14:00:00+00:00"),     # EST (UTC-5)
    ("2026-01-15", "2:30pm", "2026-01-15T19:30:00+00:00"),
    ("2026-07-15", "9 AM", "2026-07-15T13:00:00+00:00"),
    ("2026-07-15", None, "2026-07-15T13:00:00+00:00"),        # default 09:00
    ("2026-07-15", "garbage", "2026-07-15T13:00:00+00:00"),   # unreadable -> default
    ("2026-07-15T00:00:00", "10:00", "2026-07-15T14:00:00+00:00"),  # ISO date prefix tolerated
])
def test_parse_local_returns_true_utc(date_str, time_str, expected_utc):
    got = tu.parse_local(date_str, time_str)
    assert got.tzinfo is not None
    assert got.isoformat() == expected_utc


def test_parse_local_rejects_bad_date():
    with pytest.raises(ValueError):
        tu.parse_local("not-a-date", "09:00")
    with pytest.raises(ValueError):
        tu.parse_local("", "09:00")


def test_parse_local_iso_from_datetime_local_picker():
    # <input type=datetime-local> shape, typed in Florida time
    assert tu.parse_local_iso("2026-07-15T09:00").isoformat() == "2026-07-15T13:00:00+00:00"
    # an explicit offset or Z is honored as-is
    assert tu.parse_local_iso("2026-07-15T13:00:00Z").isoformat() == "2026-07-15T13:00:00+00:00"
    assert tu.parse_local_iso("2026-07-15T09:00:00-04:00").isoformat() == "2026-07-15T13:00:00+00:00"


def test_dst_transition_days_do_not_drift():
    # DST starts 2026-03-08 02:00 local; 9 AM that morning is UTC-4 already.
    assert tu.parse_local("2026-03-08", "09:00").isoformat() == "2026-03-08T13:00:00+00:00"
    # Day before is still UTC-5.
    assert tu.parse_local("2026-03-07", "09:00").isoformat() == "2026-03-07T14:00:00+00:00"
    # DST ends 2026-11-01.
    assert tu.parse_local("2026-11-01", "09:00").isoformat() == "2026-11-01T14:00:00+00:00"


# --- rendering -------------------------------------------------------------

def test_fmt_local_reads_naive_db_value_as_utc_and_prints_florida():
    stored = datetime(2026, 7, 15, 12, 0)  # what Postgres hands back for the 8-10 slot
    assert tu.fmt_local(stored, "%b %d at %I:%M %p") == "Jul 15 at 08:00 AM"
    assert tu.fmt_local(None, "%b %d", "ASAP") == "ASAP"


def test_local_date_str_uses_the_florida_calendar_day():
    # 9 PM Florida on the 15th is 01:00Z on the 16th; the customer booked "the 15th".
    stored = datetime(2026, 7, 16, 1, 0)
    assert tu.local_date_str(stored) == "2026-07-15"


def test_iso_utc_shape_is_what_every_client_parses():
    stored = datetime(2026, 7, 15, 12, 0)
    assert tu.iso_utc(stored) == "2026-07-15T12:00:00.000Z"
    aware = datetime(2026, 7, 15, 8, 0, tzinfo=tu.BUSINESS_TZ)
    assert tu.iso_utc(aware) == "2026-07-15T12:00:00.000Z"
    assert tu.iso_utc(None) is None


def test_round_trip_slot_to_words():
    for slot, words in [("8-10", "08:00 AM"), ("12-14", "12:00 PM"), ("14-16", "02:00 PM")]:
        stored = tu.parse_local("2026-07-15", slot).replace(tzinfo=None)  # as the DB returns it
        assert tu.fmt_local(stored, "%I:%M %p") == words


def test_local_naive_to_utc_for_callback_phrases():
    # dateutil gives a naive "today at 15:00"; that is 3 PM Florida.
    naive = datetime(2026, 7, 15, 15, 0)
    assert tu.local_naive_to_utc(naive).isoformat() == "2026-07-15T19:00:00+00:00"
    already = datetime(2026, 7, 15, 19, 0, tzinfo=timezone.utc)
    assert tu.local_naive_to_utc(already) == already
