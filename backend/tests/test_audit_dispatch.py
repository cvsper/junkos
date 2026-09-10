"""Audit F15/F16/F17: one atomic assignment op, one eligibility rule set,
versioned transitions with proof.

Races are simulated deterministically (two sequential calls where the second
must lose the conditional UPDATE) — the compare-and-set is what makes the
concurrent case safe, so exercising the CAS is what matters, not the threads.
"""
from datetime import datetime, timedelta, timezone

import pytest

import assignment
from assignment import assign_job, eligibility, reassign_job, transition_job
from models import (
    Contractor, ContractorReservation, Job, JobEvent, JobOffer, Payment, User,
    db, generate_uuid,
)


# --------------------------------------------------------------------------- fixtures
@pytest.fixture(autouse=True)
def clean(app):
    yield
    JobEvent.query.delete()
    ContractorReservation.query.delete()
    JobOffer.query.delete()
    Payment.query.delete()
    Job.query.filter(Job.address.like("audit-%")).delete(synchronize_session=False)
    for c in Contractor.query.all():
        db.session.delete(c)
    User.query.filter(User.email.like("%@audit.test")).delete(synchronize_session=False)
    db.session.commit()


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hauler(name, lat=26.63, lng=-80.05, online=True, approved="approved",
            capacity=600.0, concierge=False, operator_id=None):
    u = User(id=generate_uuid(), email=name.lower().replace(" ", "") + "@audit.test",
             name=name, phone="+1561555%04d" % (abs(hash(name)) % 10000), role="driver")
    db.session.add(u)
    db.session.flush()
    c = Contractor(id=generate_uuid(), user_id=u.id, is_online=online,
                   approval_status=approved, current_lat=lat, current_lng=lng,
                   avg_rating=4.8, truck_capacity=capacity, is_concierge=concierge,
                   operator_id=operator_id,
                   last_heartbeat_at=_now() if online else None)
    db.session.add(c)
    db.session.commit()
    return c


def _customer():
    u = User.query.filter_by(email="cx@audit.test").first()
    if not u:
        u = User(id=generate_uuid(), email="cx@audit.test", name="Audit Cx",
                 phone="+15619991234", role="customer")
        db.session.add(u)
        db.session.commit()
    return u


def _job(status="confirmed", when=None, lat=26.62, lng=-80.05, paid=True, driver=None):
    j = Job(id=generate_uuid(), customer_id=_customer().id,
            address="audit-1 200 Lake Ave, Lake Worth FL", lat=lat, lng=lng, status=status,
            scheduled_at=when if when is not None else _now() + timedelta(hours=3),
            total_price=199.0, driver_id=driver)
    db.session.add(j)
    db.session.flush()
    db.session.add(Payment(id=generate_uuid(), job_id=j.id, amount=199.0,
                           driver_payout_amount=150.0,
                           payment_status="succeeded" if paid else "pending"))
    db.session.commit()
    return j


ADMIN = {"user_id": "admin-1", "role": "admin", "name": "Admin"}


def _driver_actor(c):
    return {"user_id": c.user_id, "role": "driver", "name": c.user.name}


def _advance(job, contractor, target, data=None):
    return transition_job(job, target, _driver_actor(contractor), data or {}, contractor=contractor)


def _to_started(job, contractor):
    for step in ("accepted", "en_route", "arrived", "started"):
        ok, payload, code = _advance(job, contractor, step)
        assert ok, (step, payload)
    return job


# =========================================================================== F15
def test_second_assign_of_same_job_conflicts():
    a, b = _hauler("Alpha One"), _hauler("Bravo Two")
    job = _job()

    first = assign_job(job.id, a.id, ADMIN, "admin")
    assert first.ok and first.code == "assigned"

    # Second writer still holds the pre-assignment view of the row: its
    # conditional UPDATE matches zero rows and it loses cleanly.
    second = assign_job(job.id, b.id, ADMIN, "admin")
    assert not second.ok and second.code == "taken" and second.http_status == 409

    db.session.refresh(job)
    assert job.driver_id == a.id and job.status == "assigned"
    assert ContractorReservation.query.filter_by(job_id=job.id, status="active").count() == 1


def test_stale_version_is_rejected_on_assignment():
    a = _hauler("Version Vic")
    job = _job()
    stale_version = job.version
    assert assign_job(job.id, a.id, ADMIN, "admin", expected_version=stale_version).ok
    db.session.refresh(job)
    assert job.version == stale_version + 1

    job.status = "confirmed"
    job.driver_id = None
    db.session.commit()
    b = _hauler("Version Val")
    res = assign_job(job.id, b.id, ADMIN, "admin", expected_version=stale_version)
    assert not res.ok and res.code == "version_conflict" and res.http_status == 409


def test_overlapping_reservation_for_same_truck_is_rejected():
    c = _hauler("Solo Sam")
    slot = _now() + timedelta(hours=4)
    job1 = _job(when=slot)
    job2 = _job(when=slot + timedelta(minutes=30))     # inside the 2h reservation window

    assert assign_job(job1.id, c.id, ADMIN, "admin").ok
    res = assign_job(job2.id, c.id, ADMIN, "admin")
    assert not res.ok
    assert res.code == "ineligible"
    assert "reservation_conflict" in res.reasons

    # A job well outside the window is fine — the truck is only held for its slot.
    job3 = _job(when=slot + timedelta(hours=6))
    assert assign_job(job3.id, c.id, ADMIN, "admin").ok


def test_cancelled_and_completed_jobs_can_never_be_assigned():
    c = _hauler("Terminal Tina")
    for status in ("cancelled", "completed", "paid"):
        job = _job(status=status)
        res = assign_job(job.id, c.id, ADMIN, "admin")
        assert not res.ok, status
        assert res.code in ("cancelled", "terminal"), (status, res.code)
        db.session.refresh(job)
        assert job.driver_id is None and job.status == status

    # A terminal job is not correctable through reassign_job either — its
    # assignment and payout recipient are history, not state to overwrite.
    done = _job(status="completed")
    res = reassign_job(done.id, c.id, ADMIN, "customer called back")
    assert not res.ok and res.code == "terminal"


def test_reassign_requires_a_reason_and_is_audited():
    a, b = _hauler("Swap Ann"), _hauler("Swap Ben")
    job = _job()
    assert assign_job(job.id, a.id, ADMIN, "admin").ok

    assert reassign_job(job.id, b.id, ADMIN, "  ").code == "reason_required"

    res = reassign_job(job.id, b.id, ADMIN, "hauler truck broke down")
    assert res.ok and res.code == "assigned"
    db.session.refresh(job)
    assert job.driver_id == b.id

    # Old reservation released, new one live — the first truck is free again.
    assert ContractorReservation.query.filter_by(job_id=job.id, contractor_id=a.id).one().status == "released"
    assert ContractorReservation.query.filter_by(job_id=job.id, contractor_id=b.id).one().status == "active"

    kinds = [(e.meta or {}).get("kind") for e in assignment.job_events(job.id)]
    assert "reassign_release" in kinds and "assigned" in kinds
    assert any(e.reason == "hauler truck broke down" for e in assignment.job_events(job.id))


def test_every_path_writes_a_job_event():
    c = _hauler("Evented Eve")
    job = _job()
    assert assign_job(job.id, c.id, ADMIN, "admin").ok
    _to_started(job, c)
    assert _advance(job, c, "completed", {"after_photos": ["https://x/after.jpg"]})[0]

    events = assignment.job_events(job.id)
    assert [(e.from_status, e.to_status) for e in events] == [
        ("confirmed", "assigned"), ("assigned", "accepted"), ("accepted", "en_route"),
        ("en_route", "arrived"), ("arrived", "started"), ("started", "completed"),
    ]
    assert events[0].actor_role == "admin"
    assert events[1].actor_user_id == c.user_id and events[1].actor_role == "driver"


def test_offer_acceptance_goes_through_the_same_guard():
    from dispatcher import accept_offer
    a, b = _hauler("Offer Amy"), _hauler("Offer Bob")
    job = _job(status="broadcasting")
    offers = {}
    for c in (a, b):
        o = JobOffer(id=generate_uuid(), job_id=job.id, contractor_id=c.id, status="sent",
                     accept_token=generate_uuid(),
                     expires_at=_now() + timedelta(minutes=20))
        db.session.add(o)
        offers[c.id] = o
    db.session.commit()

    first = accept_offer(offers[a.id].accept_token)
    assert first["ok"] and first["status"] == "accepted"
    second = accept_offer(offers[b.id].accept_token)
    assert not second["ok"] and second["status"] == "taken"

    db.session.refresh(job)
    assert job.driver_id == a.id
    assert JobOffer.query.filter_by(id=offers[b.id].id).one().status == "superseded"
    # Re-tapping your own link is idempotent, not an error.
    assert accept_offer(offers[a.id].accept_token)["status"] == "already_yours"


def test_expired_offer_cannot_claim_the_job():
    from dispatcher import accept_offer
    c = _hauler("Late Larry")
    job = _job(status="broadcasting")
    o = JobOffer(id=generate_uuid(), job_id=job.id, contractor_id=c.id, status="sent",
                 accept_token=generate_uuid(), expires_at=_now() - timedelta(minutes=5))
    db.session.add(o)
    db.session.commit()

    res = accept_offer(o.accept_token)
    assert not res["ok"] and res["status"] == "expired"
    db.session.refresh(job)
    assert job.driver_id is None
    assert JobOffer.query.filter_by(id=o.id).one().status == "expired"


def test_driver_accept_endpoint_uses_the_domain_op(client):
    from auth_routes import generate_token
    a, b = _hauler("Api Ann"), _hauler("Api Bob")
    job = _job()
    hdr = lambda c: {"Authorization": "Bearer " + generate_token(c.user_id)}  # noqa: E731

    r1 = client.post("/api/drivers/jobs/{}/accept".format(job.id), json={}, headers=hdr(a))
    assert r1.status_code == 200, r1.get_json()
    r2 = client.post("/api/drivers/jobs/{}/accept".format(job.id), json={}, headers=hdr(b))
    assert r2.status_code == 409 and r2.get_json()["code"] == "taken"

    db.session.refresh(job)
    assert job.driver_id == a.id and job.status == "accepted"

    # An unpaid job can't be self-claimed in the app — payment makes it claimable.
    unpaid = _job(paid=False, status="pending")
    r3 = client.post("/api/drivers/jobs/{}/accept".format(unpaid.id), json={}, headers=hdr(b))
    assert r3.status_code == 409 and r3.get_json()["code"] == "payment_pending"


# =========================================================================== F16
def test_eligibility_reason_codes():
    job = _job()
    now = _now()

    pending = _hauler("Not Approved Ned", approved="pending")
    assert "not_approved" in eligibility(job, pending, now, mode="auto").reasons

    small = _hauler("Small Truck Sal", capacity=10.0)
    job.volume_estimate = 400.0
    db.session.commit()
    assert "truck_too_small" in eligibility(job, small, now, mode="auto").reasons

    # Unknown volume is a WARNING, never a blocker — normal bookings don't
    # populate volume_estimate and must still dispatch (audit F16).
    job.volume_estimate = None
    db.session.commit()
    ok_v = eligibility(job, small, now, mode="auto")
    assert ok_v.ok and "volume_unknown" in ok_v.warnings

    stale = _hauler("Stale Stan")
    stale.last_heartbeat_at = now - timedelta(hours=48)
    db.session.commit()
    assert "stale_heartbeat" in eligibility(job, stale, now, mode="auto").reasons
    # ...but a hauler tapping accept isn't turned away for a stale ping.
    assert eligibility(job, stale, now, mode="accept").ok

    expired = _hauler("Expired Ella")
    expired.insurance_expiry = now - timedelta(days=1)
    db.session.commit()
    for mode in ("auto", "offer", "accept", "manual"):
        assert "documents_expired" in eligibility(job, expired, now, mode=mode).reasons

    concierge = _hauler("Concierge Cal", concierge=True)
    assert "concierge_needs_offer" in eligibility(job, concierge, now, mode="auto").reasons
    assert eligibility(job, concierge, now, mode="accept").ok

    far = _hauler("Far Fred", lat=27.95, lng=-82.46)
    assert "out_of_radius" in eligibility(job, far, now, mode="auto").reasons
    assert "out_of_radius" in eligibility(job, far, now, mode="accept").warnings


def test_declined_contractor_is_excluded_from_the_next_wave(client):
    from auth_routes import generate_token
    import sameday
    from unittest import mock

    decliner = _hauler("Decline Dan", lat=26.631)
    backup = _hauler("Backup Bea", lat=26.632)
    job = _job()

    assert assign_job(job.id, decliner.id, ADMIN, "admin").ok
    with mock.patch("dispatcher.auto_assign_job_async"):
        r = client.post("/api/drivers/jobs/{}/decline".format(job.id), json={"reason": "too far"},
                        headers={"Authorization": "Bearer " + generate_token(decliner.user_id)})
    assert r.status_code == 200, r.get_json()

    offer = JobOffer.query.filter_by(job_id=job.id, contractor_id=decliner.id).one()
    assert offer.status == "declined" and offer.declined_at and offer.exclude_until > _now()
    assert offer.decline_reason == "too far"

    db.session.refresh(job)
    assert job.driver_id is None and job.status == "confirmed"
    # Their truck is free again, but they are excluded from re-dispatch of THIS job.
    assert ContractorReservation.query.filter_by(job_id=job.id, contractor_id=decliner.id).one().status == "released"
    assert "declined_recently" in eligibility(job, decliner, _now(), mode="auto").reasons
    assert assign_job(job.id, decliner.id, ADMIN, "auto").code == "ineligible"

    # The next wave reaches the backup hauler instead.
    with mock.patch("dispatcher._sms_broadcast_offer"):
        sent = sameday.wave(job, limit=3)
    assert [s["name"] for s in sent["sent"]] == ["Backup Bea"]

    # A human dispatcher can still put them back on deliberately — the
    # exclusion is a blocker for automatic dispatch, a flag for manual.
    forced = assign_job(job.id, decliner.id, ADMIN, "admin", reason="customer asked for Dan")
    assert forced.ok and "declined_recently" in forced.warnings


def test_coverage_count_equals_assignable_count():
    import sameday
    from assignment import assignable_contractors, point_job

    live = _hauler("Coverage Cara", lat=26.63)
    stale = _hauler("Coverage Carl", lat=26.633)
    stale.last_heartbeat_at = _now() - timedelta(hours=48)
    expired = _hauler("Coverage Cliff", lat=26.634)
    expired.license_expiry = _now() - timedelta(days=2)
    db.session.commit()

    cap = sameday.capacity(26.62, -80.05)
    names = {h["name"] for h in cap["haulers"]}
    assert names == {"Coverage Cara"}

    probe = point_job(26.62, -80.05, scheduled_at=_now())
    assignable = assignable_contractors(probe, mode="auto", radius_miles=sameday.RADIUS_MILES)
    assert cap["count"] == len(assignable) == 1
    assert {e["contractor"].id for e in assignable} == {live.id}
    # The one whose documents lapsed is not counted as coverage at all —
    # "we have coverage" and "we can assign" agree (audit F16).
    assert expired.id not in {e["contractor"].id for e in assignable}
    assert cap["unconfirmed"] == 1        # the stale-heartbeat hauler, still unconfirmed


def test_busy_truck_is_not_offered_a_second_overlapping_job():
    import sameday
    from unittest import mock

    busy = _hauler("Busy Bee", lat=26.63)
    slot = _now() + timedelta(hours=4)
    first = _job(when=slot)
    assert assign_job(first.id, busy.id, ADMIN, "admin").ok

    overlapping = _job(when=slot + timedelta(minutes=45))
    with mock.patch("dispatcher._sms_broadcast_offer"):
        res = sameday.wave(overlapping, limit=3)
    assert res["sent"] == []
    assert "reservation_conflict" in eligibility(overlapping, busy, _now(), mode="offer").reasons
    # ...but the same truck is still free for a slot outside the reservation.
    later = _job(when=slot + timedelta(hours=8))
    assert eligibility(later, busy, _now(), mode="offer").ok


# =========================================================================== F17
def test_completion_without_after_photo_is_422_unless_excepted():
    c = _hauler("Proof Pam")
    job = _job()
    assert assign_job(job.id, c.id, ADMIN, "admin").ok
    _to_started(job, c)

    ok, payload, code = _advance(job, c, "completed")
    assert not ok and code == 422 and payload["code"] == "proof_required"
    db.session.refresh(job)
    assert job.status == "started" and job.completed_at is None

    ok, payload, code = _advance(job, c, "completed", {"exception_reason": "customer took the photos"})
    assert ok and code == 200
    db.session.refresh(job)
    assert job.status == "completed"
    assert job.completion_exception_reason == "customer took the photos"
    ev = assignment.job_events(job.id)[-1]
    assert ev.to_status == "completed" and ev.meta["exception_reason"] == "customer took the photos"


def test_completion_accepts_the_customer_handoff_pin_as_proof():
    c = _hauler("Pin Pete")
    job = _job()
    result = assign_job(job.id, c.id, ADMIN, "admin")
    assert result.ok and result.pin and len(result.pin) == 4 and result.pin.isdigit()
    db.session.refresh(job)
    # Only the hash is stored; the plaintext PIN goes out in the customer's text.
    assert job.completion_pin_hash and result.pin not in (job.completion_pin_hash or "")
    assert assignment.current_pin(job) == result.pin

    _to_started(job, c)
    ok, payload, code = _advance(job, c, "completed", {"handoff_pin": "0000" if result.pin != "0000" else "1111"})
    assert not ok and code == 422 and payload["code"] == "pin_invalid"

    ok, payload, code = _advance(job, c, "completed", {"handoff_pin": result.pin})
    assert ok, payload
    db.session.refresh(job)
    assert job.status == "completed" and job.completion_pin_verified_at is not None


def test_completion_pin_required_flag_off_by_default(app):
    from flags import FLAGS, flag
    assert FLAGS["completion_pin_required"]["default"] is False
    assert flag("completion_pin_required") is False

    from models import DeskSetting
    c = _hauler("Flagged Fran")
    job = _job()
    assert assign_job(job.id, c.id, ADMIN, "admin").ok
    _to_started(job, c)
    DeskSetting.put("flag:completion_pin_required", "on")
    try:
        ok, payload, code = _advance(job, c, "completed", {"after_photos": ["https://x/a.jpg"]})
        assert not ok and code == 422 and payload["code"] == "pin_required"
    finally:
        DeskSetting.put("flag:completion_pin_required", None)
    ok, _, _ = _advance(job, c, "completed", {"after_photos": ["https://x/a.jpg"]})
    assert ok


def test_completion_blocked_by_open_change_order_and_unsettled_payment():
    c = _hauler("Order Olly")
    job = _job()
    assert assign_job(job.id, c.id, ADMIN, "admin").ok
    _to_started(job, c)

    job.has_open_change_order = True
    db.session.commit()
    ok, payload, code = _advance(job, c, "completed", {"after_photos": ["https://x/a.jpg"]})
    assert not ok and code == 409 and payload["code"] == "change_order_open"

    job.has_open_change_order = False
    job.payment.payment_status = "pending"
    db.session.commit()
    ok, payload, code = _advance(job, c, "completed", {"after_photos": ["https://x/a.jpg"]})
    assert not ok and code == 409 and payload["code"] == "payment_not_settled"

    # An admin may still close it out — with a recorded reason.
    ok, payload, code = transition_job(job, "completed", ADMIN,
                                       {"after_photos": ["https://x/a.jpg"],
                                        "exception_reason": "cash job, settled offline",
                                        "override_reason": "manual settlement"},
                                       contractor=c)
    assert ok, payload
    assert assignment.job_events(job.id)[-1].meta["payment_exception"] == "pending"


def test_start_requires_arrival_acknowledgment():
    c = _hauler("Rush Rita")
    job = _job()
    assert assign_job(job.id, c.id, ADMIN, "admin").ok
    assert _advance(job, c, "accepted")[0]
    assert _advance(job, c, "en_route")[0]

    # en_route -> started isn't even a legal edge; arriving is what unlocks it.
    ok, payload, code = _advance(job, c, "started")
    assert not ok and code == 409 and payload["code"] == "invalid_transition"

    assert _advance(job, c, "arrived")[0]
    db.session.refresh(job)
    assert job.arrived_at is not None
    job.arrived_at = None                      # simulate a lost arrival ack
    db.session.commit()
    ok, payload, code = _advance(job, c, "started")
    assert not ok and code == 422 and payload["code"] == "arrival_required"

    ok, payload, code = _advance(job, c, "started", {"exception_reason": "gps failed at the curb"})
    assert ok and code == 200
    assert assignment.job_events(job.id)[-1].meta["exception"] == "arrival_not_acknowledged"


def test_stale_version_transition_is_409():
    c = _hauler("Racer Rex")
    job = _job()
    assert assign_job(job.id, c.id, ADMIN, "admin").ok
    stale = job.version

    assert _advance(job, c, "accepted")[0]
    db.session.refresh(job)
    assert job.version == stale + 1

    # A second request built from the stale view loses the compare-and-set.
    ok, payload, code = transition_job(job, "en_route", _driver_actor(c), {},
                                       contractor=c, expected_version=stale)
    assert not ok and code == 409 and payload["code"] == "stale_version"

    # The same guard through the driver route (the app sends its cached version).
    from routes.drivers import apply_job_status_transition
    ok, payload, code = apply_job_status_transition(job, c, "en_route", {"version": stale})
    assert not ok and code == 409 and payload["code"] == "stale_version"
    db.session.refresh(job)
    assert job.status == "accepted"


def test_non_assigned_contractor_cannot_transition(client):
    from auth_routes import generate_token
    owner, stranger = _hauler("Owner Ora"), _hauler("Stranger Stu")
    job = _job()
    assert assign_job(job.id, owner.id, ADMIN, "admin").ok
    _to_started(job, owner)

    ok, payload, code = _advance(job, stranger, "completed", {"after_photos": ["https://x/a.jpg"]})
    assert not ok and code == 403 and payload["code"] == "not_assigned"

    r = client.put("/api/drivers/jobs/{}/status".format(job.id),
                   json={"status": "completed", "after_photos": ["https://x/a.jpg"]},
                   headers={"Authorization": "Bearer " + generate_token(stranger.user_id)})
    assert r.status_code == 403
    db.session.refresh(job)
    assert job.status == "started"

    # An admin override needs a reason on the record.
    ok, payload, code = transition_job(job, "completed", ADMIN,
                                       {"after_photos": ["https://x/a.jpg"]}, contractor=None)
    assert not ok and code == 400 and payload["code"] == "override_reason_required"
    ok, payload, code = transition_job(job, "completed", ADMIN,
                                       {"after_photos": ["https://x/a.jpg"],
                                        "override_reason": "hauler phone died"}, contractor=None)
    assert ok, payload
    assert assignment.job_events(job.id)[-1].meta["override_reason"] == "hauler phone died"


def test_completed_job_releases_the_truck_and_does_not_pay_out_on_refusal(client):
    from unittest import mock
    c = _hauler("Payout Polly")
    job = _job()
    assert assign_job(job.id, c.id, ADMIN, "admin").ok
    _to_started(job, c)

    from routes.drivers import apply_job_status_transition
    with mock.patch("routes.payments.attempt_payout") as payout:
        ok, payload, code = apply_job_status_transition(job, c, "completed", {})
        assert not ok and code == 422
        payout.assert_not_called()

        ok, payload, code = apply_job_status_transition(
            job, c, "completed", {"after_photos": ["https://x/a.jpg"]})
        assert ok, payload
        payout.assert_called_once_with(job.id)

    db.session.refresh(job)
    assert job.status == "completed"
    assert ContractorReservation.query.filter_by(job_id=job.id).one().status == "released"


def test_auto_assign_uses_the_domain_op_and_records_the_source():
    """dispatcher.auto_assign_job no longer writes driver_id itself (audit F15)."""
    from unittest import mock
    import dispatcher

    winner = _hauler("Auto Ada", lat=26.625)
    _hauler("Auto Far", lat=27.95, lng=-82.46)          # out of radius
    stale = _hauler("Auto Stale", lat=26.626)
    stale.last_heartbeat_at = _now() - timedelta(hours=48)
    db.session.commit()
    job = _job()

    with mock.patch("dispatcher._sms_operator_assigned"), \
         mock.patch("notifications.send_push_notification"), \
         mock.patch("dispatcher.broadcast_job") as broadcast:
        dispatcher.auto_assign_job(job.id)
        broadcast.assert_not_called()

    db.session.refresh(job)
    assert job.driver_id == winner.id and job.status == "assigned"
    assert ContractorReservation.query.filter_by(job_id=job.id, status="active").count() == 1
    ev = assignment.job_events(job.id)[0]
    assert ev.to_status == "assigned" and ev.meta["source"] == "auto"
    assert job.completion_pin_hash          # the customer's handoff PIN is minted here

    # Nobody eligible -> the wave, never a silent drop.
    lonely = _job(lat=41.88, lng=-87.63)
    with mock.patch("dispatcher.broadcast_job") as broadcast:
        dispatcher.auto_assign_job(lonely.id)
        broadcast.assert_called_once_with(lonely.id)


def test_concierge_console_completes_with_the_customer_pin(client):
    """The phone-only hauler's /w/ console runs the same gated transition."""
    from unittest import mock
    c = _hauler("Console Cody", concierge=True)
    job = _job()
    result = assign_job(job.id, c.id, ADMIN, "concierge")
    assert result.ok and result.pin

    offer = JobOffer(id=generate_uuid(), job_id=job.id, contractor_id=c.id, status="accepted",
                     accept_token=generate_uuid())
    db.session.add(offer)
    db.session.commit()
    url = "/w/{}/advance".format(offer.accept_token)

    with mock.patch("routes.payments.attempt_payout"), \
         mock.patch("notifications.send_push_notification"), \
         mock.patch("sms_service.send_sms_async"):
        for step in ("accepted", "en_route", "arrived", "started"):
            assert client.post(url, data={"to": step}).status_code == 302

        # No proof -> bounced back to the console with a readable reason.
        r = client.post(url, data={"to": "completed"})
        assert r.status_code == 302 and "err=proof_required" in r.headers["Location"]
        db.session.refresh(job)
        assert job.status == "started"

        r = client.post(url, data={"to": "completed", "handoff_pin": result.pin})
        assert r.status_code == 302 and "err=" not in r.headers["Location"]

    db.session.refresh(job)
    assert job.status == "completed" and job.completion_pin_verified_at is not None
