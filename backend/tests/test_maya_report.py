"""Why isn't Maya closing? Roll up the calls that are already stored."""
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from models import db, CallLog, generate_uuid
import maya_report


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code"}):
        yield
    CallLog.query.filter(CallLog.call_id.like("mr_%")).delete(synchronize_session=False)
    db.session.commit()


def _call(tools, booked=False, seconds=90, ended="customer-ended-call", summary="", days_ago=0):
    c = CallLog(id=generate_uuid(), call_id="mr_" + generate_uuid()[:8], phone_number="+15615550100",
                duration_seconds=seconds, status=ended, tools_used=tools, booking_created=booked,
                summary=summary, sentiment="neutral",
                created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago))
    db.session.add(c); db.session.commit()
    return c


def test_close_rate_is_bookings_over_quotes_and_lost_calls_are_sampled():
    _call(["get_price_estimate", "create_booking"], booked=True)
    _call(["get_price_estimate"], summary="Caller wanted a Saturday slot, none offered, hung up.")
    _call(["get_price_estimate"], summary="Price felt high, said they'd think about it.")
    _call([], seconds=8, ended="silence-timed-out")
    _call(["schedule_callback"])
    rep = maya_report.report(days=30)
    assert rep["calls"] == 5 and rep["quoted"] == 3 and rep["booked"] == 1
    assert rep["close_rate"] == pytest.approx(33.3, abs=0.1)
    assert rep["lost_after_quote"] == 2
    assert {s["summary"][:12] for s in rep["lost_samples"]} == {"Caller wante", "Price felt h"}
    assert rep["under_20s"] == 1 and rep["callbacks"] == 1
    assert ("silence-timed-out", 1) in rep["ended_reasons"]


def test_no_quotes_means_no_close_rate_rather_than_a_division_error():
    _call([], seconds=5)
    rep = maya_report.report(days=30)
    assert rep["close_rate"] is None and rep["quote_rate"] == 0.0


def test_report_is_manager_only(client):
    _call(["get_price_estimate"], summary="private customer conversation")
    r = client.post("/api/va/maya/report", json={"code": "test-code", "va_name": "Tracy"})
    assert r.status_code == 403, "summaries are customer conversations — not for the shared passcode"
    from desk_auth import create_desk_user
    from models import User
    create_desk_user("mayaboss@goumuve.com", "Boss", "manager", "pw-mayaboss")
    tok = client.post("/api/desk/login", json={"email": "mayaboss@goumuve.com",
                                               "password": "pw-mayaboss"}).get_json()["token"]
    r = client.post("/api/va/maya/report", json={"days": 30}, headers={"Authorization": "Bearer " + tok})
    assert r.status_code == 200 and r.get_json()["calls"] >= 1
    User.query.filter_by(email="mayaboss@goumuve.com").delete(); db.session.commit()
