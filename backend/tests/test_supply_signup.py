"""A hauler who signed up must never come back around the call queue.

sevs, 14 Sep: "make sure the haulers that sign up dont get put back into the
call list" — Tracy was recruiting people who had already joined.
"""
import os
from unittest import mock

import pytest

from models import db, CallProspect, Contractor, User, generate_uuid
import supply_signup


@pytest.fixture(autouse=True)
def env(app):
    supply_signup._invalidate()
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code"}):
        yield
    from models_crm import ProspectStage
    from models import CallAttempt
    ProspectStage.query.delete(); CallAttempt.query.delete()
    CallProspect.query.delete(); Contractor.query.delete(); User.query.delete()
    db.session.commit()
    supply_signup._invalidate()


def _prospect(company="Hank's Hauling", digits="5615550142", direct=None, status="queued"):
    p = CallProspect(id=generate_uuid(), tier=1, category="junk removal", company=company,
                     phone="({}) {}-{}".format(digits[:3], digits[3:6], digits[6:]),
                     phone_digits=digits, city="Lake Worth", direct_phone=direct, status=status)
    db.session.add(p); db.session.commit(); return p


def _hauler(phone="+15615550142"):
    u = User(id=generate_uuid(), name="Hank", phone=phone,
             email="{}@t.local".format(generate_uuid()[:8]), role="driver")
    db.session.add(u); db.session.flush()
    c = Contractor(id=generate_uuid(), user_id=u.id, approval_status="approved")
    db.session.add(c); db.session.commit(); return c


def test_signing_up_retires_the_card_as_a_win():
    p = _prospect()
    c = _hauler()
    assert supply_signup.retire_for_phone("+15615550142", c.id) == 1
    db.session.refresh(p)
    assert p.status == "converted" and p.next_followup_at is None and p.last_outcome == "converted"
    assert "signed up" in (p.last_note or "")
    from models import CallAttempt
    assert CallAttempt.query.filter_by(prospect_id=p.id, outcome="converted").count() == 1
    from crm import current_stage
    assert current_stage(p.id) == "won"
    # and it is idempotent — a second signup event changes nothing
    assert supply_signup.retire_for_phone("+15615550142", c.id) == 0


def test_the_queue_never_hands_out_a_hauler_who_joined():
    joined = _prospect("Already In", "5615550142")
    fresh = _prospect("Still To Call", "5615550199")
    _hauler("+15615550142")
    from crm import next_unclaimed
    got = next_unclaimed("Tracy")
    assert got is not None and got.id == fresh.id, "the queue offered a hauler who already signed up"
    db.session.refresh(joined)
    assert joined.status == "converted"            # retired on the way past


def test_a_direct_cell_counts_too():
    """She often captures the decision maker's cell; they sign up from that."""
    p = _prospect("Office Line Co", "5615550100", direct="(561) 555-0142")
    _hauler("+15615550142")
    assert supply_signup.matches(p) is not None
    from crm import next_unclaimed
    assert next_unclaimed("Tracy") is None
    db.session.refresh(p); assert p.status == "converted"


def test_sweep_cleans_the_backlog_and_leaves_everyone_else():
    a = _prospect("Joined A", "5615550142")
    b = _prospect("Joined B", "5615550143", status="interested")
    keep = _prospect("Not A Hauler", "5615550188")
    dead = _prospect("Old Dead", "5615550144", status="dead")
    _hauler("+15615550142"); _hauler("+15615550143"); _hauler("+15615550144")
    out = supply_signup.sweep()
    assert out["retired"] == 2 and out["checked"] >= 3
    for p in (a, b):
        db.session.refresh(p); assert p.status == "converted"
    db.session.refresh(keep); assert keep.status == "queued"
    db.session.refresh(dead); assert dead.status == "dead"      # untouched, already out


def test_a_customer_account_is_not_a_hauler():
    p = _prospect("Palm Coast PM", "5615550142")
    u = User(id=generate_uuid(), name="Dana", phone="+15615550142",
             email="d@t.local", role="customer")
    db.session.add(u); db.session.commit()
    supply_signup._invalidate()
    assert supply_signup.matches(p) is None
    from crm import next_unclaimed
    assert next_unclaimed("Tracy").id == p.id


def test_nothing_blows_up_without_a_phone():
    p = _prospect("No Phone Co", "5615550142")
    assert supply_signup.retire_for_phone(None) == 0
    assert supply_signup.retire_for_phone("") == 0
    assert supply_signup.retire_for_phone("555") == 0
    db.session.refresh(p); assert p.status == "queued"


def test_admin_sweep_route_is_gated(client):
    assert client.get("/api/admin/supply/signed-up-sweep").status_code == 401
    assert client.post("/api/admin/supply/signed-up-sweep").status_code == 401
