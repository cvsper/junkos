"""Tests for the VA Dispatch Desk.

Born from the first real Maya phone close (Aug 2026): phone customers
never touch the app, so Tracy needs a passcode-gated board to put haulers
on booked jobs, and a form to log jobs closed by a human on a call.
"""

import os
from datetime import datetime
from unittest import mock

import pytest

from models import (
    Contractor, Job, Payment, User, VaDispatchAction, db, generate_uuid,
)
import va_dispatch


@pytest.fixture(autouse=True)
def passcode_env():
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code"}):
        yield


_phone_seq = iter(range(1000, 9999))


def _unique_phone():
    return "(561) 555-{}".format(next(_phone_seq))


def _mk_user(name="Pat Customer", phone=None, email=None, role="customer"):
    u = User(id=generate_uuid(), name=name, phone=phone or _unique_phone(),
             email=email, role=role)
    db.session.add(u)
    db.session.flush()
    return u


def _mk_contractor(name="Hank Hauler", approved=True, concierge=False, operator=False,
                   online=False):
    u = _mk_user(name=name,
                 email="{}@test.local".format(generate_uuid()[:8]), role="driver")
    c = Contractor(
        id=generate_uuid(), user_id=u.id,
        approval_status="approved" if approved else "pending",
        is_concierge=concierge, is_operator=operator, is_online=online,
    )
    db.session.add(c)
    db.session.flush()
    return c

def _mk_job(status="pending", notes=None, created=None, price=400.0,
            address="123 Palm Way, Lake Worth"):
    customer = _mk_user()
    j = Job(
        id=generate_uuid(), customer_id=customer.id, status=status,
        address=address, total_price=price, notes=notes,
        created_at=created or datetime(2026, 8, 30, 12, 0),
    )
    db.session.add(j)
    db.session.commit()
    return j


@pytest.fixture(autouse=True)
def clean_tables(app):
    yield
    VaDispatchAction.query.delete()
    Payment.query.delete()
    Job.query.delete()
    Contractor.query.delete()
    User.query.delete()
    db.session.commit()


def _post(client, path, **payload):
    payload.setdefault("code", "test-code")
    payload.setdefault("va_name", "Tracy")
    return client.post(path, json=payload)


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------

def test_wrong_passcode_is_rejected(client):
    r = client.post("/api/va/dispatch/board", json={"code": "nope"})
    assert r.status_code == 401


def test_missing_env_passcode_fails_closed(client):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": ""}):
        r = client.post("/api/va/dispatch/board", json={"code": ""})
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Board
# ---------------------------------------------------------------------------

def test_board_lists_open_jobs_with_null_notes(client):
    job = _mk_job(notes=None)
    r = _post(client, "/api/va/dispatch/board")
    assert r.status_code == 200
    ids = [j["id"] for j in r.get_json()["jobs"]]
    assert job.id in ids


def test_board_screens_out_synthetic_and_pre_cutoff_rows(client):
    real = _mk_job()
    synth = _mk_job(notes="SYNTHETIC load test row")
    ancient = _mk_job(created=datetime(2026, 2, 10))
    r = _post(client, "/api/va/dispatch/board")
    ids = [j["id"] for j in r.get_json()["jobs"]]
    assert real.id in ids
    assert synth.id not in ids
    assert ancient.id not in ids


def test_board_hides_assigned_jobs(client):
    job = _mk_job()
    hauler = _mk_contractor()
    job.driver_id = hauler.id
    job.status = "assigned"
    db.session.commit()
    r = _post(client, "/api/va/dispatch/board")
    assert job.id not in [j["id"] for j in r.get_json()["jobs"]]


# ---------------------------------------------------------------------------
# Assign
# ---------------------------------------------------------------------------

def test_assign_puts_driver_on_job_and_audits(client):
    job = _mk_job()
    hauler = _mk_contractor()
    r = _post(client, "/api/va/dispatch/assign",
              job_id=job.id, contractor_id=hauler.id)
    assert r.status_code == 200, r.get_json()
    db.session.refresh(job)
    assert job.driver_id == hauler.id
    assert job.status == "assigned"
    act = VaDispatchAction.query.filter_by(job_id=job.id).one()
    assert act.action == "assign"
    assert act.va_name == "Tracy"
    assert act.contractor_id == hauler.id


def test_assign_operator_sets_delegating(client):
    job = _mk_job()
    op = _mk_contractor(operator=True)
    r = _post(client, "/api/va/dispatch/assign",
              job_id=job.id, contractor_id=op.id)
    assert r.status_code == 200, r.get_json()
    db.session.refresh(job)
    assert job.operator_id == op.id
    assert job.status == "delegating"


def test_assign_refuses_already_assigned_job(client):
    job = _mk_job()
    first = _mk_contractor()
    second = _mk_contractor(name="Second Hauler")
    _post(client, "/api/va/dispatch/assign", job_id=job.id, contractor_id=first.id)
    r = _post(client, "/api/va/dispatch/assign", job_id=job.id, contractor_id=second.id)
    assert r.status_code == 409
    db.session.refresh(job)
    assert job.driver_id == first.id


def test_assign_refuses_unapproved_hauler(client):
    job = _mk_job()
    pending = _mk_contractor(approved=False)
    r = _post(client, "/api/va/dispatch/assign",
              job_id=job.id, contractor_id=pending.id)
    assert r.status_code == 403
    db.session.refresh(job)
    assert job.driver_id is None


def test_haulers_ranks_online_first_and_labels_kinds(client):
    job = _mk_job()
    _mk_contractor(name="Offline App", online=False)
    _mk_contractor(name="Online Concierge", online=True, concierge=True)
    r = _post(client, "/api/va/dispatch/haulers", job_id=job.id)
    assert r.status_code == 200
    haulers = r.get_json()["haulers"]
    assert haulers[0]["name"] == "Online Concierge"
    assert haulers[0]["kind"] == "text"
    assert haulers[1]["kind"] == "app"


# ---------------------------------------------------------------------------
# Log a phone job
# ---------------------------------------------------------------------------

def test_log_job_creates_pending_job_on_the_board(client):
    r = _post(client, "/api/va/dispatch/log-job",
              customer_name="Jane Rivera", customer_phone="(561) 555-0142",
              address="42 Ocean Ave, WPB", price="400",
              items_text="Sofa + loveseat", notes="Gate code 4411")
    assert r.status_code == 200, r.get_json()
    card = r.get_json()["job"]
    assert card["total_price"] == 400.0
    assert card["lead_source"] == "phone"

    job = db.session.get(Job, card["id"])
    assert job.status == "pending"
    assert "Sofa + loveseat" in job.notes
    assert "Tracy" in job.notes
    assert job.payment is not None and job.payment.payment_status == "pending"
    assert VaDispatchAction.query.filter_by(job_id=job.id, action="log_job").count() == 1

    board = _post(client, "/api/va/dispatch/board")
    assert card["id"] in [j["id"] for j in board.get_json()["jobs"]]


def test_log_job_reuses_existing_customer_by_phone(client):
    existing = _mk_user(name="Repeat Customer", phone="561-555-0177")
    r = _post(client, "/api/va/dispatch/log-job",
              customer_name="Repeat Customer", customer_phone="(561) 555-0177",
              address="9 Pine St", price=250)
    assert r.status_code == 200
    job = db.session.get(Job, r.get_json()["job"]["id"])
    assert job.customer_id == existing.id


def test_log_job_validates_inputs(client):
    bad_phone = _post(client, "/api/va/dispatch/log-job",
                      customer_phone="123", address="9 Pine St", price=250)
    assert bad_phone.status_code == 400
    no_addr = _post(client, "/api/va/dispatch/log-job",
                    customer_phone="(561) 555-0100", address="", price=250)
    assert no_addr.status_code == 400
    bad_price = _post(client, "/api/va/dispatch/log-job",
                      customer_phone="(561) 555-0100", address="9 Pine St", price="lots")
    assert bad_price.status_code == 400
