"""A slot is only real if a hauler who passes dispatch's own gate could take it."""
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from models import db, User, Contractor, Job, generate_uuid
import availability


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code"}):
        yield
    Job.query.filter(Job.address.like("e2e-avail%")).delete(synchronize_session=False)
    for c in Contractor.query.all():
        db.session.delete(c)
    User.query.filter(User.email.like("%@avail.test")).delete(synchronize_session=False)
    db.session.commit()


def _hauler(name, proven=True):
    u = User(id=generate_uuid(), email=name.lower().replace(" ", "") + "@avail.test", name=name,
             phone="+1561555" + str(abs(hash(name)) % 10000).zfill(4), role="driver")
    db.session.add(u); db.session.flush()
    c = Contractor(user_id=u.id, is_online=True, approval_status="approved",
                   current_lat=26.62, current_lng=-80.05, truck_capacity=12.0,
                   last_heartbeat_at=datetime.now(timezone.utc).replace(tzinfo=None))
    db.session.add(c); db.session.commit()
    if proven:
        cx = User.query.filter_by(email="cx@avail.test").first()
        if not cx:
            cx = User(id=generate_uuid(), email="cx@avail.test", name="Avail Cx", phone="+15615550990", role="customer")
            db.session.add(cx); db.session.commit()
        db.session.add(Job(id=generate_uuid(), customer_id=cx.id, driver_id=c.id, status="completed",
                           address="e2e-avail done", total_price=150.0,
                           completed_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=5),
                           scheduled_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=5)))
        db.session.commit()
    return c


def _tomorrow():
    from timeutils import to_local
    return (to_local(datetime.now(timezone.utc)) + timedelta(days=1)).strftime("%Y-%m-%d")


def test_no_haulers_means_no_slot_is_promised(client):
    r = client.get("/api/booking/availability?date={}&lat=26.62&lng=-80.05".format(_tomorrow()))
    assert r.status_code == 200
    body = r.get_json()
    assert body["any_available"] is False
    assert all(s["available"] is False and s["crews"] == 0 for s in body["slots"])


def test_an_eligible_hauler_opens_the_slots(client):
    _hauler("Ready Rita")
    body = client.get("/api/booking/availability?date={}&lat=26.62&lng=-80.05".format(_tomorrow())).get_json()
    assert body["any_available"] is True
    assert [s["slot"] for s in body["slots"]] == list(availability.SLOTS)
    assert all(s["crews"] == 1 for s in body["slots"])
    assert body["slots"][0]["label"] == "8am–10am"


def test_bad_date_is_rejected_and_far_dates_are_not_promised(client):
    assert client.get("/api/booking/availability?date=nope").status_code == 400
    _hauler("Ready Rita")
    from timeutils import to_local
    far = (to_local(datetime.now(timezone.utc)) + timedelta(days=40)).strftime("%Y-%m-%d")
    body = client.get("/api/booking/availability?date={}&lat=26.62&lng=-80.05".format(far)).get_json()
    assert body["any_available"] is False and body["slots"][0]["reason"] == "too_far"


def test_a_hauler_out_of_radius_does_not_count():
    _hauler("Far Fred")
    Contractor.query.first().current_lat = 27.95   # Tampa
    Contractor.query.first().current_lng = -82.46
    db.session.commit()
    slots = availability.slots_for(_tomorrow(), 26.62, -80.05)
    assert all(not s["available"] for s in slots)
