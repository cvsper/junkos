"""Customer texts must link the public tracking page.

/track/<code> renders the logged-in customer page (auth'd job-by-UUID API),
so phone customers who tapped it got nothing. /track/code/<CODE> is the
guest page. Job.tracking_url is the one place that decides.
"""
import os
from unittest import mock

from models import Contractor, Job, User, db, generate_uuid
from routes.drivers import apply_job_status_transition

_seq = iter(range(1, 10000))


def _mk_user(role="customer", phone=True):
    u = User(id=generate_uuid(), name="Pat Customer",
             phone="(561) 555-{:04d}".format(next(_seq)) if phone else None,
             email="{}@test.local".format(generate_uuid()[:8]), role=role)
    db.session.add(u)
    db.session.flush()
    return u


def test_tracking_url_uses_public_code_page(client):
    job = Job(id=generate_uuid(), customer_id=_mk_user().id, status="pending",
              address="1 Main St", total_price=100.0, confirmation_code="ABC12345")
    assert job.tracking_url() == "https://app.goumuve.com/track/code/ABC12345"


def test_tracking_url_honors_frontend_url_env(client):
    job = Job(id=generate_uuid(), customer_id=_mk_user().id, status="pending",
              address="1 Main St", total_price=100.0, confirmation_code="ABC12345")
    with mock.patch.dict(os.environ, {"FRONTEND_URL": "https://staging.goumuve.com/"}):
        assert job.tracking_url() == "https://staging.goumuve.com/track/code/ABC12345"


def test_tracking_url_falls_back_to_uuid_page_without_code(client):
    job = Job(id="11111111-2222-3333-4444-555555555555", customer_id=_mk_user().id,
              status="pending", address="1 Main St", total_price=100.0, confirmation_code=None)
    assert job.tracking_url() == "https://app.goumuve.com/track/11111111-2222-3333-4444-555555555555"


def test_hauler_confirmed_sms_links_public_page(client):
    customer = _mk_user()
    driver_user = _mk_user(role="driver")
    contractor = Contractor(id=generate_uuid(), user_id=driver_user.id,
                            approval_status="approved")
    db.session.add(contractor)
    job = Job(id=generate_uuid(), customer_id=customer.id, status="assigned",
              address="1 Main St", total_price=100.0, confirmation_code="TRK99999",
              driver_id=contractor.id)
    db.session.add(job)
    db.session.commit()

    with mock.patch("sms_service.send_sms") as sms, \
         mock.patch("notifications.send_push_notification"), \
         mock.patch("socket_events.broadcast_job_status"):
        ok, payload, code = apply_job_status_transition(job, contractor, "accepted")

    assert ok, payload
    bodies = [c.args[1] for c in sms.call_args_list]
    assert any("https://app.goumuve.com/track/code/TRK99999" in b for b in bodies), bodies
    assert not any("/track/TRK99999" in b for b in bodies)
