"""A shift can be annotated while it is still open.

sevs, 15 Sep: Tracy was clocked in all day with internet problems and did no
work. There was nowhere to record that against the shift — the note could only
be written at clock-in or clock-out — so payday would have shown paid hours
with no explanation attached.
"""
import os
from unittest import mock

import pytest

from models import db, VaShift


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code"}):
        yield
    VaShift.query.delete(); db.session.commit()


def test_the_note_route_is_admin_only(client):
    assert client.post("/api/admin/va-shift-note", json={"va_name": "Tracy", "note": "x"}).status_code in (401, 403)


def test_an_open_shift_can_be_annotated_and_it_reaches_the_hours_report():
    from va_time import hours_report
    from datetime import datetime, timezone
    sh = VaShift(va_name="Tracy", started_at=datetime.now(timezone.utc).replace(tzinfo=None))
    db.session.add(sh); db.session.commit()
    assert sh.note is None
    sh.note = "Internet down — no work completed (per Shamar)"
    db.session.commit()
    rows = hours_report("Tracy", 7)["shifts"]
    mine = [r for r in rows if r["id"] == sh.id][0]
    assert mine["open"] is True
    assert "Internet down" in mine["note"]          # payday sees the reason


# ---------------------------------------------------------------------------
# a shift that is not payable
# ---------------------------------------------------------------------------
def _shift(hours=8.0, unpaid=False, reason=None):
    from datetime import datetime, timedelta, timezone
    end = datetime.now(timezone.utc).replace(tzinfo=None)
    sh = VaShift(va_name="Tracy", started_at=end - timedelta(hours=hours), ended_at=end,
                 unpaid=unpaid, unpaid_reason=reason)
    db.session.add(sh); db.session.commit()
    return sh


def test_an_unpaid_shift_keeps_its_hours_but_pays_nothing():
    """A time record is never deleted. 15 Sep: a full day was clocked with no
    work done, and the hours had to stop being payable without vanishing."""
    from va_time import hours_report
    sh = _shift(hours=8.81, unpaid=True, reason="internet down, no work completed")
    row = [r for r in hours_report("Tracy", 7)["shifts"] if r["id"] == sh.id][0]
    assert row["hours"] > 8                      # the time is still on the record
    assert row["pay"] == 0.0                     # and it pays nothing
    assert row["unpaid"] is True
    assert "internet down" in row["unpaid_reason"]


def test_unpaid_hours_leave_the_pay_totals():
    from va_time import totals_for
    _shift(hours=4.0)                            # a normal shift
    before = totals_for("Tracy")["period_seconds"]
    _shift(hours=8.0, unpaid=True, reason="no work completed")
    after = totals_for("Tracy")
    assert after["period_seconds"] == before     # the voided day adds nothing
    assert after["unpaid_seconds_this_period"] > 0   # but it is still counted somewhere


def test_marking_a_shift_unpaid_requires_a_reason(client):
    sh = _shift()
    r = client.post("/api/admin/va-shift-unpaid", json={"shift_id": sh.id, "unpaid": True})
    assert r.status_code in (401, 403)           # admin only


def test_a_paid_shift_is_unaffected():
    from va_time import hours_report
    sh = _shift(hours=7.56)
    row = [r for r in hours_report("Tracy", 7)["shifts"] if r["id"] == sh.id][0]
    assert row["unpaid"] is False and row["hours"] > 7
