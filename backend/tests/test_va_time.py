"""VA time clock: clock in/out, totals by day/week/pay period, auto-close, report."""
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from models import db, VaShift, CallAttempt, CallProspect
from va_time import period_bounds, totals_for


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code",
                                      "VA_PAY_PERIOD_ANCHOR": "2026-08-06"}):
        yield
    CallAttempt.query.delete(); CallProspect.query.delete(); VaShift.query.delete(); db.session.commit()


def _va(client, path, payload, name="Tracy"):
    base = {"code": "test-code", "va_name": name}
    base.update(payload)
    return client.post(path, json=base)


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def test_period_bounds_are_two_weeks_from_anchor():
    start, end, label = period_bounds(datetime(2026, 9, 9, 15, 0, tzinfo=timezone.utc))
    # 2026-08-06 + 14 + 14 = 2026-09-03 → period Sep 3 – Sep 16
    assert start.date() == datetime(2026, 9, 3).date() + timedelta(days=0) or start.date() == datetime(2026, 9, 3).date()
    assert (end - start).days == 14
    assert label == "Sep 3 – Sep 16"


def test_clock_in_out_and_totals(client):
    r = _va(client, "/api/va/time/clock", {"action": "in"})
    assert r.status_code == 200 and r.get_json()["on_clock"] is True
    sh = VaShift.query.one()
    assert sh.va_name == "Tracy" and sh.ended_at is None
    # clocking in twice doesn't open a second shift
    r = _va(client, "/api/va/time/clock", {"action": "in"}).get_json()
    assert r["already"] is True and VaShift.query.count() == 1
    # pretend 90 minutes passed
    sh.started_at = _now() - timedelta(minutes=90); db.session.commit()
    st = _va(client, "/api/va/time/status", {}).get_json()
    assert st["on_clock"] and 89 * 60 <= st["today_seconds"] <= 91 * 60
    assert st["period_seconds"] >= st["today_seconds"] - 5
    r = _va(client, "/api/va/time/clock", {"action": "out", "note": "great day"}).get_json()
    assert r["on_clock"] is False and 89 * 60 <= r["closed"]["seconds"] <= 91 * 60
    assert VaShift.query.one().note == "great day"


def test_stale_shift_auto_closes_at_12h(client):
    db.session.add(VaShift(va_name="Tracy", started_at=_now() - timedelta(hours=20)))
    db.session.commit()
    st = _va(client, "/api/va/time/status", {}).get_json()
    assert st["on_clock"] is False
    sh = VaShift.query.one()
    assert sh.auto_closed and sh.seconds == 12 * 3600


def test_hours_report_lists_shifts_with_calls(client):
    p = CallProspect(tier=1, category="storage", company="X", phone="5615550100", phone_digits="5615550100")
    db.session.add(p); db.session.commit()
    start = _now() - timedelta(hours=3)
    db.session.add(VaShift(va_name="Tracy", started_at=start, ended_at=start + timedelta(hours=2)))
    db.session.add_all([
        CallAttempt(prospect_id=p.id, outcome="voicemail", va_name="Tracy", created_at=start + timedelta(minutes=10)),
        CallAttempt(prospect_id=p.id, outcome="interested", va_name="Tracy", created_at=start + timedelta(minutes=50)),
        CallAttempt(prospect_id=p.id, outcome="skip", va_name="Tracy", created_at=start + timedelta(minutes=55)),
        CallAttempt(prospect_id=p.id, outcome="no_answer", va_name="Tracy", created_at=start + timedelta(hours=2, minutes=30)),
    ])
    db.session.commit()
    rep = _va(client, "/api/va/time/hours", {}).get_json()
    assert len(rep["shifts"]) == 1
    s = rep["shifts"][0]
    assert s["calls"] == 2 and s["seconds"] == 7200 and s["end_local"] and s["day"]
    assert rep["today_seconds"] >= 7200 - 5


def test_needs_a_name(client):
    assert _va(client, "/api/va/time/clock", {"action": "in"}, name="").status_code == 400
    assert _va(client, "/api/va/time/hours", {}, name="").status_code == 400
    st = _va(client, "/api/va/time/status", {}, name="").get_json()
    assert st["on_clock"] is False
    assert client.post("/api/va/time/clock", json={"code": "wrong", "action": "in"}).status_code == 401


def test_other_va_hours_are_separate(client):
    db.session.add(VaShift(va_name="Trixie", started_at=_now() - timedelta(hours=1), ended_at=_now()))
    db.session.commit()
    assert totals_for("Tracy")["today_seconds"] == 0
    assert totals_for("Trixie")["today_seconds"] >= 3595
