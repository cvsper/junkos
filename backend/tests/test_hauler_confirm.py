"""Confirm the hauler before the job; re-dispatch when they go quiet.

Job AFB22IMO: assigned to a hauler with zero completed jobs, and nobody asked
him whether he was coming. He wasn't. Every safety net fired after the slot;
none fired before it, and none re-dispatched.
"""
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from models import db, User, Contractor, Job, Payment, generate_uuid
import hauler_confirm
import hauler_reliability
import work_queue


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code"}):
        yield
    from models_work import WorkItemState
    WorkItemState.query.delete()
    for j in Job.query.filter(Job.address.like("e2e-confirm%")).all():
        Payment.query.filter_by(job_id=j.id).delete()
        db.session.delete(j)
    for c in Contractor.query.all():
        db.session.delete(c)
    User.query.filter(User.email.like("%@confirm.test")).delete(synchronize_session=False)
    db.session.commit()


def _cx():
    u = User.query.filter_by(email="cx@confirm.test").first()
    if not u:
        u = User(id=generate_uuid(), email="cx@confirm.test", name="Cary Example",
                 phone="+15615550600", role="customer")
        db.session.add(u); db.session.commit()
    return u


def _hauler(name, phone):
    u = User(id=generate_uuid(), email=name.lower().replace(" ", "") + "@confirm.test",
             name=name, phone=phone, role="driver")
    db.session.add(u); db.session.flush()
    c = Contractor(user_id=u.id, is_online=True, approval_status="approved",
                   current_lat=26.6, current_lng=-80.1, truck_capacity=12.0,
                   last_heartbeat_at=datetime.now(timezone.utc).replace(tzinfo=None))
    db.session.add(c); db.session.commit()
    return c


def _job(hauler, hours_ahead, code, status="assigned", confirmed=False):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    j = Job(id=generate_uuid(), customer_id=_cx().id, driver_id=hauler.id if hauler else None,
            address="e2e-confirm 5370 South University Dr, Davie FL", status=status,
            scheduled_at=now + timedelta(hours=hours_ahead), total_price=307.80,
            confirmation_code=code, lat=26.07, lng=-80.25)
    if confirmed:
        j.hauler_confirmed_at = now
        j.hauler_confirmed_by = "Tracy"
    db.session.add(j); db.session.flush()
    db.session.add(Payment(id=generate_uuid(), job_id=j.id, amount=307.80,
                           driver_payout_amount=230.0, payment_status="succeeded",
                           payout_status="pending"))
    db.session.commit()
    return j


def _va(client, path, payload=None):
    base = {"code": "test-code", "va_name": "Tracy"}
    base.update(payload or {})
    return client.post(path, json=base)


# ---------------------------------------------------------------------------
def test_tomorrows_jobs_appear_in_the_queue_until_a_person_confirms(client):
    w = _hauler("Wiscaton Bertho", "+15615550301")
    j = _job(w, hours_ahead=20, code="CONFTMRW")
    q = work_queue.build()
    item = next(i for i in q["items"] if i["ref_id"] == j.id)
    assert item["kind"] == "hauler_unconfirmed"
    assert item["phone"] == "(561) 555-0301", "the item must carry the hauler's number — the action is a call"
    assert "never completed a job" in item["why"], "a first-timer is called out as one"
    assert {a["key"] for a in item["actions"]} == {"confirm", "cant_make_it"}

    r = _va(client, "/api/va/confirm/mark", {"job_id": j.id, "confirmed": True, "note": "said 11am"})
    assert r.status_code == 200
    db.session.refresh(j)
    assert j.hauler_confirmed_by == "Tracy" and j.hauler_confirm_note == "said 11am"
    assert all(i["ref_id"] != j.id for i in work_queue.build()["items"]), "confirmed → off the queue"


def test_cant_make_it_releases_and_redispatches_without_a_strike(client):
    w = _hauler("Wiscaton Bertho", "+15615550301")
    _hauler("Rob Hauls", "+15615550302")
    j = _job(w, hours_ahead=20, code="CONFCANT")
    with mock.patch("sameday.wave", return_value={"sent": [{"name": "Rob"}]}) as wave:
        r = _va(client, "/api/va/confirm/mark", {"job_id": j.id, "confirmed": False})
    assert r.status_code == 200 and r.get_json()["redispatch"]["waved"] == 1
    db.session.refresh(j)
    assert j.driver_id is None and j.hauler_confirmed_at is None
    assert j.noshow_contractor_id is None, "declining honestly the day before is not a no-show"
    assert wave.call_count == 1


def test_t30_unconfirmed_hauler_is_released_counted_and_waved(client):
    w = _hauler("Wiscaton Bertho", "+15615550301")
    j = _job(w, hours_ahead=0.5, code="CONFT30U")
    with mock.patch("sameday.wave", return_value={"sent": [{"name": "Rob"}, {"name": "Sam"}]}), \
         mock.patch("hauler_confirm._page") as page:
        acted = hauler_confirm.preslot_check()
    assert ("CONFT30U", "redispatched") in acted
    db.session.refresh(j)
    assert j.driver_id is None
    assert j.noshow_contractor_id == w.id and j.noshow_redispatched_at is not None
    assert page.call_count == 1 and "never confirmed" in page.call_args[0][0]
    # and it counts against him
    assert hauler_reliability.tier(w.id) == hauler_reliability.TIER_FLAGGED
    # idempotent: the next tick does not act on it again
    with mock.patch("sameday.wave") as wave2, mock.patch("hauler_confirm._page"):
        assert ("CONFT30U", "redispatched") not in hauler_confirm.preslot_check()
    assert wave2.call_count == 0


def test_t30_confirmed_hauler_is_paged_not_dropped(client):
    w = _hauler("Wiscaton Bertho", "+15615550301")
    j = _job(w, hours_ahead=0.5, code="CONFT30C", confirmed=True)
    with mock.patch("sameday.wave") as wave, mock.patch("hauler_confirm._page") as page:
        acted = hauler_confirm.preslot_check()
    assert ("CONFT30C", "paged") in acted
    db.session.refresh(j)
    assert j.driver_id == w.id, "a confirmed hauler running late is a judgement, not an automatic drop"
    assert j.noshow_contractor_id is None
    assert wave.call_count == 0 and page.call_count == 1
    # and it sits at the very top of the queue with a one-tap re-dispatch
    q = work_queue.build()
    top = q["items"][0]
    assert top["kind"] == "hauler_not_moving" and top["ref_id"] == j.id
    assert top["actions"][0]["key"] == "redispatch"
    with mock.patch("sameday.wave", return_value={"sent": []}):
        r = _va(client, "/api/va/confirm/redispatch", {"job_id": j.id})
    assert r.status_code == 200
    db.session.refresh(j)
    assert j.driver_id is None and j.noshow_contractor_id == w.id


def test_t30_ignores_jobs_already_moving_and_outside_the_window(client):
    w = _hauler("Wiscaton Bertho", "+15615550301")
    moving = _job(w, hours_ahead=0.5, code="CONFMOVE", status="en_route")
    far = _job(w, hours_ahead=5, code="CONFFAR")
    with mock.patch("sameday.wave") as wave, mock.patch("hauler_confirm._page"):
        acted = hauler_confirm.preslot_check()
    assert acted == [] and wave.call_count == 0


def test_redispatch_refuses_a_hauler_who_is_already_on_the_way(client):
    w = _hauler("Wiscaton Bertho", "+15615550301")
    j = _job(w, hours_ahead=0.5, code="CONFENRT", status="en_route")
    r = _va(client, "/api/va/confirm/redispatch", {"job_id": j.id})
    assert r.status_code == 409 and "call them" in r.get_json()["error"]


def test_the_list_needs_a_signed_in_desk(client):
    assert client.post("/api/va/confirm/list", json={}).status_code == 401
