"""Paid phone jobs must leave "pending".

Maya's pay-link text and the VA Dispatch Desk both send a Stripe Checkout
link built by routes.vapi._build_checkout_url. Until 2026-09-04 the webhook
ignored those sessions (source != quick-checkout) and the PaymentIntent
carried no job metadata, so a customer could pay and the job never confirmed.
"""
import json
from datetime import datetime, timezone
from unittest import mock

import pytest

from models import Job, Payment, User, WebhookEvent, db, generate_uuid

_seq = iter(range(1, 10000))


def _mk_job(price=134.57, with_payment=True):
    u = User(id=generate_uuid(), name="Phone Customer",
             phone="(561) 555-{:04d}".format(next(_seq)), role="customer")
    db.session.add(u)
    db.session.flush()
    j = Job(id=generate_uuid(), customer_id=u.id, status="pending",
            address="6319 Shadowtree Lane, Lake Worth", total_price=price,
            base_price=price, service_fee=0.0, confirmation_code="T{:05d}".format(next(_seq)),
            scheduled_at=datetime(2026, 9, 10, 13, 0, tzinfo=timezone.utc))
    db.session.add(j)
    db.session.flush()
    if with_payment:
        db.session.add(Payment(id=generate_uuid(), job_id=j.id, amount=price,
                               service_fee=0.0, payment_status="pending"))
    db.session.commit()
    return j


def _session_completed(job_id, pi="pi_test_123", amount=13457, source="maya_phone",
                       paid="paid"):
    return {
        "id": "evt_{}".format(next(_seq)),
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_test_{}".format(next(_seq)),
            "object": "checkout.session",
            "mode": "payment",
            "payment_status": paid,
            "payment_intent": pi,
            "amount_total": amount,
            "client_reference_id": job_id,
            "customer_email": None,
            "customer_details": {"email": None},
            "metadata": {"booking_id": job_id, "source": source} if job_id else {"source": source},
        }},
    }


def _intent_succeeded(job_id, pi="pi_test_123", amount=13457):
    return {
        "id": "evt_{}".format(next(_seq)),
        "type": "payment_intent.succeeded",
        "data": {"object": {
            "id": pi, "object": "payment_intent", "amount": amount, "status": "succeeded",
            "metadata": {"job_id": job_id, "booking_id": job_id, "source": "maya_phone"},
        }},
    }


def _post(client, event):
    return client.post("/api/webhooks/stripe", data=json.dumps(event),
                       content_type="application/json")


@pytest.fixture(autouse=True)
def _quiet_side_effects():
    with mock.patch("dispatcher.auto_assign_job_async"), \
         mock.patch("socket_events.broadcast_job_status"):
        yield


def test_checkout_completed_confirms_phone_booking(client):
    job = _mk_job()
    r = _post(client, _session_completed(job.id))
    assert r.status_code == 200, r.get_json()

    db.session.expire_all()
    job = db.session.get(Job, job.id)
    pay = Payment.query.filter_by(job_id=job.id).first()
    assert job.status == "confirmed"
    assert pay.payment_status == "succeeded"
    assert pay.stripe_payment_intent_id == "pi_test_123"


def test_intent_succeeded_alone_confirms_via_intent_metadata(client):
    # Stripe may deliver payment_intent.succeeded first (or only, on a retry
    # storm). The intent now carries job_id, so the fallback lookup works.
    job = _mk_job()
    r = _post(client, _intent_succeeded(job.id, pi="pi_only_1"))
    assert r.status_code == 200

    db.session.expire_all()
    assert db.session.get(Job, job.id).status == "confirmed"
    assert Payment.query.filter_by(job_id=job.id).first().stripe_payment_intent_id == "pi_only_1"


def test_both_events_are_idempotent(client):
    job = _mk_job()
    _post(client, _session_completed(job.id, pi="pi_both"))
    _post(client, _intent_succeeded(job.id, pi="pi_both"))
    _post(client, _session_completed(job.id, pi="pi_both"))  # Stripe retry

    db.session.expire_all()
    assert db.session.get(Job, job.id).status == "confirmed"
    assert Payment.query.filter_by(job_id=job.id).count() == 1
    assert Payment.query.filter_by(job_id=job.id).first().payment_status == "succeeded"


def test_checkout_without_payment_row_creates_one(client):
    job = _mk_job(with_payment=False)
    _post(client, _session_completed(job.id, pi="pi_norow", amount=25000))

    db.session.expire_all()
    pay = Payment.query.filter_by(job_id=job.id).first()
    assert pay is not None
    assert pay.amount == 250.0
    assert pay.payment_status == "succeeded"
    assert db.session.get(Job, job.id).status == "confirmed"


def test_unpaid_session_does_not_confirm(client):
    job = _mk_job()
    _post(client, _session_completed(job.id, pi="pi_unpaid", paid="unpaid"))
    db.session.expire_all()
    assert db.session.get(Job, job.id).status == "pending"


def test_quick_checkout_invoice_leaves_jobs_alone(client):
    job = _mk_job()
    with mock.patch("notifications.send_email"):
        r = _post(client, _session_completed(None, pi="pi_qc", source="quick-checkout"))
    assert r.status_code == 200
    db.session.expire_all()
    assert db.session.get(Job, job.id).status == "pending"


def test_build_checkout_url_stamps_job_on_intent(client):
    from routes import vapi as vapi_mod
    job = _mk_job(price=200.0)
    fake_session = mock.Mock(url="https://checkout.stripe.com/c/pay/cs_x", payment_intent=None)
    with mock.patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test_x"}), \
         mock.patch("stripe.checkout.Session.create", return_value=fake_session) as create:
        url = vapi_mod._build_checkout_url(job.id, 200.0)

    assert url == "https://checkout.stripe.com/c/pay/cs_x"
    kwargs = create.call_args.kwargs
    assert kwargs["client_reference_id"] == job.id
    assert kwargs["payment_intent_data"]["metadata"]["job_id"] == job.id
    assert kwargs["metadata"]["booking_id"] == job.id
