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
