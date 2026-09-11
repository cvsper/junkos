"""One list of what needs a human, and who has it.

Every operational failure this desk has had was the same shape: detected, then
unowned. A $307 job sat assigned 18 days. A hauler finished and went unpaid. A
call rang and was never returned. The detectors worked; nothing turned "this
needs a person" into "this is mine".
"""
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from models import db, User, Job, Payment, Contractor, generate_uuid
from models_work import WorkItemState
import work_queue


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code"}):
        yield
    WorkItemState.query.delete()
    for j in Job.query.filter(Job.address.like("e2e-work%")).all():
        Payment.query.filter_by(job_id=j.id).delete()
        db.session.delete(j)
    for c in Contractor.query.all():
        db.session.delete(c)
    User.query.filter(User.email.like("%@work.test")).delete(synchronize_session=False)
    db.session.commit()


def _cx():
    u = User.query.filter_by(email="cx@work.test").first()
    if not u:
        u = User(id=generate_uuid(), email="cx@work.test", name="Work Cx",
                 phone="+15615550700", role="customer")
        db.session.add(u); db.session.commit()
    return u


def _paid_job(code, driver=None, status="confirmed", hours_ahead=6):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    j = Job(id=generate_uuid(), customer_id=_cx().id, driver_id=driver,
            address="e2e-work 12 Clematis St, West Palm Beach FL", status=status,
            scheduled_at=now + timedelta(hours=hours_ahead), total_price=307.80,
            confirmation_code=code)
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


def test_a_paid_job_with_no_hauler_is_the_top_of_the_queue():
    _paid_job("WORKPAID")
    q = work_queue.build(va_name="Tracy")
    top = q["items"][0]
    assert top["kind"] == "unassigned_paid"
    assert "WORKPAID" in top["detail"] and "307.80" in top["detail"]
    assert "paid" in top["why"].lower() and "nobody" in top["why"].lower()
    assert q["unclaimed"] == q["total"] >= 1


def test_urgency_ranks_by_cost_then_age():
    """A paid job with nobody coming outranks a due callback, and an old item
    of the same kind outranks a fresh one."""
    fresh = {"kind": "unassigned_paid", "age_hours": 1}
    stale = {"kind": "unassigned_paid", "age_hours": 100}
    callback = {"kind": "callback_due", "age_hours": 1}
    assert work_queue.urgency(stale) > work_queue.urgency(fresh)
    assert work_queue.urgency(fresh) > work_queue.urgency(callback)


def test_claiming_makes_it_mine_and_blocks_someone_else(client):
    _paid_job("WORKCLAIM")
    item = work_queue.build()["items"][0]
    r = _va(client, "/api/va/work/claim", {"kind": item["kind"], "ref_id": item["ref_id"]})
    assert r.status_code == 200
    mine = next(i for i in r.get_json()["queue"]["items"] if i["ref_id"] == item["ref_id"])
    assert mine["claimed_by"] == "Tracy" and mine["mine"] is True

    clash = _va(client, "/api/va/work/claim",
                {"kind": item["kind"], "ref_id": item["ref_id"], "va_name": "Damian"})
    assert clash.status_code == 409 and "Tracy" in clash.get_json()["error"]


def test_a_claim_expires_so_nothing_hides_forever(client):
    _paid_job("WORKSTALE")
    item = work_queue.build()["items"][0]
    _va(client, "/api/va/work/claim", {"kind": item["kind"], "ref_id": item["ref_id"]})
    row = WorkItemState.query.filter_by(kind=item["kind"], ref_id=item["ref_id"]).one()
    row.claimed_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
        hours=work_queue.CLAIM_HOURS + 1)
    db.session.commit()
    again = work_queue.build(va_name="Someone")
    row2 = next(i for i in again["items"] if i["ref_id"] == item["ref_id"])
    assert row2["claimed_by"] is None and row2["claim_stale"] is True
    assert again["unclaimed"] >= 1


def test_done_requires_saying_what_happened(client):
    _paid_job("WORKDONE")
    item = work_queue.build()["items"][0]
    blank = _va(client, "/api/va/work/done", {"kind": item["kind"], "ref_id": item["ref_id"]})
    assert blank.status_code == 400 and "what you did" in blank.get_json()["error"]

    ok = _va(client, "/api/va/work/done",
             {"kind": item["kind"], "ref_id": item["ref_id"], "note": "Called Rob, he takes it at 2."})
    assert ok.status_code == 200
    assert all(i["ref_id"] != item["ref_id"] for i in ok.get_json()["queue"]["items"])
    saved = WorkItemState.query.filter_by(ref_id=item["ref_id"]).one()
    assert saved.done_by == "Tracy" and "Rob" in saved.note


def test_snoozing_hides_it_then_brings_it_back(client):
    _paid_job("WORKSNOOZ")
    item = work_queue.build()["items"][0]
    r = _va(client, "/api/va/work/snooze",
            {"kind": item["kind"], "ref_id": item["ref_id"], "minutes": 30})
    assert r.status_code == 200
    assert all(i["ref_id"] != item["ref_id"] for i in r.get_json()["queue"]["items"])

    row = WorkItemState.query.filter_by(ref_id=item["ref_id"]).one()
    row.snoozed_until = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    db.session.commit()
    assert any(i["ref_id"] == item["ref_id"] for i in work_queue.build()["items"])


def test_snooze_is_bounded():
    """An unbounded snooze is just deletion with extra steps."""
    from work_queue import MAX_SNOOZE_MINUTES
    assert MAX_SNOOZE_MINUTES <= 60 * 24


def test_one_broken_source_does_not_empty_the_queue():
    _paid_job("WORKLIVE")
    with mock.patch("work_queue._haulers_owed", side_effect=RuntimeError("stripe down")):
        q = work_queue.build()
    assert q["total"] >= 1
    assert "haulers_owed" in q["sources_failed"]


def test_the_queue_needs_a_signed_in_desk(client):
    assert client.post("/api/va/work/list", json={}).status_code == 401
    assert client.post("/api/va/work/claim", json={"kind": "stranded_job", "ref_id": "x"}).status_code == 401


def test_ancient_and_synthetic_jobs_stay_out_of_the_queue():
    """The first live run put a February seed row at the very top. A queue
    whose worst item is junk is a queue people learn to ignore."""
    from models import Job, Payment
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    live = _paid_job("WORKREAL")
    old = _paid_job("WORKOLD", hours_ahead=-24 * 200)      # scheduled ~200 days ago
    synth = _paid_job("WORKSYN")
    synth.notes = "SYNTHETIC load-test row"
    db.session.commit()

    codes = {i["ref_id"] for i in work_queue.build()["items"]}
    assert live.id in codes
    assert old.id not in codes, "a 200-day-old row is abandoned, not work waiting"
    assert synth.id not in codes, "synthetic rows must never reach the queue"
