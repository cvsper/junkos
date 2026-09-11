"""Who actually shows up.

Twenty-one haulers read "online"; the one handed a real job had zero
completed jobs and never turned up. "Approved" was being treated as
"reliable". The tier is advisory everywhere except silent auto-assignment.
"""
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from models import db, User, Contractor, Job, JobOffer, generate_uuid
import hauler_reliability as hr


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code"}):
        yield
    JobOffer.query.delete()
    Job.query.filter(Job.address.like("e2e-rel%")).delete(synchronize_session=False)
    for c in Contractor.query.all():
        db.session.delete(c)
    User.query.filter(User.email.like("%@rel.test")).delete(synchronize_session=False)
    db.session.commit()


def _cx():
    u = User.query.filter_by(email="cx@rel.test").first()
    if not u:
        u = User(id=generate_uuid(), email="cx@rel.test", name="Rel Cx", phone="+15615550650", role="customer")
        db.session.add(u); db.session.commit()
    return u


def _hauler(name):
    u = User(id=generate_uuid(), email=name.lower().replace(" ", "") + "@rel.test", name=name,
             phone="+1561555" + str(abs(hash(name)) % 10000).zfill(4), role="driver")
    db.session.add(u); db.session.flush()
    c = Contractor(user_id=u.id, is_online=True, approval_status="approved",
                   current_lat=26.6, current_lng=-80.1, truck_capacity=12.0,
                   last_heartbeat_at=datetime.now(timezone.utc).replace(tzinfo=None))
    db.session.add(c); db.session.commit()
    return c


def _job(hauler, status, noshow_by=None):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    j = Job(id=generate_uuid(), customer_id=_cx().id, driver_id=hauler.id if hauler else None,
            address="e2e-rel 1 Test St, Lake Worth FL", status=status,
            scheduled_at=now + timedelta(hours=3), total_price=150.0,
            completed_at=now if status == "completed" else None, lat=26.6, lng=-80.1)
    if noshow_by:
        j.noshow_contractor_id = noshow_by.id
    db.session.add(j); db.session.commit()
    return j


def test_tiers_from_evidence():
    fresh = _hauler("Fresh Face")
    assert hr.tier(fresh.id) == hr.TIER_NEW

    steady = _hauler("Steady Eddie")
    _job(steady, "completed")
    assert hr.tier(steady.id) == hr.TIER_PROVEN

    ghost = _hauler("Ghost Truck")
    _job(None, "confirmed", noshow_by=ghost)
    assert hr.tier(ghost.id) == hr.TIER_FLAGGED, "one no-show with nothing completed is a flag"

    veteran = _hauler("Vet Hauling")
    _job(veteran, "completed")
    _job(None, "confirmed", noshow_by=veteran)
    assert hr.tier(veteran.id) == hr.TIER_PROVEN, "one slip against a completed record is not a flag"
    _job(None, "confirmed", noshow_by=veteran)
    assert hr.tier(veteran.id) == hr.TIER_FLAGGED, "two no-shows is a pattern"


def test_profile_is_desk_safe_and_never_raises():
    c = _hauler("Profile Guy")
    p = hr.profile(c)
    assert p["tier"] == "new" and p["label"] == "First job" and p["completed"] == 0
    assert hr.stats(None)["completed"] == 0


def test_silent_auto_assignment_does_not_hand_a_first_job_to_an_unproven_hauler():
    from assignment import eligibility
    c = _hauler("First Timer")
    j = _job(None, "confirmed")
    auto = eligibility(j, c, mode="auto")
    assert "first_job_needs_call" in auto.reasons, "auto mode must not silently assign a first-timer"
    offer = eligibility(j, c, mode="offer")
    assert "first_job_needs_call" in offer.warnings and "first_job_needs_call" not in offer.reasons, \
        "offer waves still reach them, flagged — an all-new pool must still get work"
    manual = eligibility(j, c, mode="manual")
    assert "first_job_needs_call" not in manual.reasons


def test_a_no_show_history_blocks_strict_modes_and_warns_elsewhere():
    from assignment import eligibility
    c = _hauler("Ghost Again")
    _job(None, "confirmed", noshow_by=c)
    j = _job(None, "confirmed")
    assert "no_show_history" in eligibility(j, c, mode="offer").reasons
    assert "no_show_history" in eligibility(j, c, mode="manual").warnings


def test_roster_orders_proven_first_then_new_then_flagged():
    a = _hauler("Alpha Proven"); _job(a, "completed")
    b = _hauler("Beta New")
    g = _hauler("Gamma Ghost"); _job(None, "confirmed", noshow_by=g)
    names = [r["name"] for r in hr.roster()]
    assert names.index("Alpha Proven") < names.index("Beta New") < names.index("Gamma Ghost")
