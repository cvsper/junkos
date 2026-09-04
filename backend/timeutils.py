"""Business-timezone helpers.

Umuve operates in Florida. Customers, haulers, Maya, and the VA desk all
think in local wall-clock time; the database stores UTC. Every place that
turns a person's date/time into a stored datetime, or turns a stored
datetime back into words, goes through this module so the two never drift.

History: before 2026-09-02 every writer stamped the Florida wall-clock with
tzinfo=UTC. Rendering printed the raw value back, so messages looked right,
but every comparison against real UTC (no-show watchdog, reminders, cancel
fee windows, the broadcast sweep) ran four to five hours early.
"""
import os
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BUSINESS_TZ_NAME = os.environ.get("BUSINESS_TZ", "America/New_York")
BUSINESS_TZ = ZoneInfo(BUSINESS_TZ_NAME)
UTC = timezone.utc

DEFAULT_SLOT_TIME = "09:00"

_SLOT_RANGE = re.compile(r"^\s*(\d{1,2})\s*-\s*\d{1,2}\s*$")      # "8-10"
_HHMM = re.compile(r"^\s*(\d{1,2}):(\d{2})(?::\d{2})?\s*$")      # "09:00", "9:00:00"
_H_AMPM = re.compile(r"^\s*(\d{1,2})(?::(\d{2}))?\s*([AaPp])\.?[Mm]?\.?\s*$")  # "9 AM", "2:30pm"


def to_utc(dt):
    """Return an aware UTC datetime. Naive input is assumed to already be UTC
    (that is how DateTime columns round-trip from Postgres and SQLite)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_local(dt):
    """Return an aware datetime in the business timezone."""
    if dt is None:
        return None
    return to_utc(dt).astimezone(BUSINESS_TZ)


def local_now():
    return datetime.now(BUSINESS_TZ)


def local_naive_to_utc(naive_dt):
    """Interpret a naive datetime as business wall-clock and return aware UTC."""
    if naive_dt.tzinfo is not None:
        return naive_dt.astimezone(UTC)
    return naive_dt.replace(tzinfo=BUSINESS_TZ).astimezone(UTC)


def normalize_slot(time_str):
    """Coerce the time formats we receive into 'HH:MM' (24h).

    Accepts slot ranges ("8-10", "14-16"), "HH:MM", "H:MM:SS", and
    "9 AM" / "2:30pm". Anything unreadable falls back to DEFAULT_SLOT_TIME.
    """
    if not time_str:
        return DEFAULT_SLOT_TIME
    s = str(time_str)
    m = _SLOT_RANGE.match(s)
    if m:
        return "{:02d}:00".format(int(m.group(1)))
    m = _HHMM.match(s)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return "{:02d}:{:02d}".format(h, mi)
        return DEFAULT_SLOT_TIME
    m = _H_AMPM.match(s)
    if m:
        h = int(m.group(1)) % 12
        mi = int(m.group(2) or 0)
        if m.group(3).lower() == "p":
            h += 12
        return "{:02d}:{:02d}".format(h, mi)
    return DEFAULT_SLOT_TIME


def parse_local(date_str, time_str=None):
    """Parse a business-local date ('YYYY-MM-DD') plus time/slot into aware UTC.

    ``time_str`` may be a slot ("8-10"), "HH:MM", or "9 AM"; missing or
    unreadable times default to 09:00. Raises ValueError on a bad date.
    """
    if not date_str:
        raise ValueError("date is required")
    date_part = str(date_str).strip()[:10]
    naive = datetime.strptime(
        "{} {}".format(date_part, normalize_slot(time_str)), "%Y-%m-%d %H:%M"
    )
    return local_naive_to_utc(naive)


def parse_local_iso(value):
    """Parse 'YYYY-MM-DDTHH:MM[:SS]' typed in business-local time (the shape a
    <input type=datetime-local> produces) into aware UTC. If the string carries
    its own offset or 'Z', honor it."""
    s = str(value).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    parsed = datetime.fromisoformat(s)
    if parsed.tzinfo is not None:
        return parsed.astimezone(UTC)
    return local_naive_to_utc(parsed)


def fmt_local(dt, fmt, default="TBD"):
    """strftime a stored datetime in business-local time."""
    if not dt:
        return default
    return to_local(dt).strftime(fmt)


def local_date_str(dt, default="TBD"):
    """'YYYY-MM-DD' of the business-local calendar day."""
    if not dt:
        return default
    return to_local(dt).date().isoformat()


def iso_utc(dt):
    """ISO-8601 in UTC with milliseconds and a trailing Z. This exact shape is
    parsed by the platform (new Date), the driver app (ISO8601DateFormatter),
    and the customer app (which insists on fractional seconds)."""
    if not dt:
        return None
    return to_utc(dt).strftime("%Y-%m-%dT%H:%M:%S.000Z")
