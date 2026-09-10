"""Money-path audit remediation (2026-09-10 audit F05/F06/F07/F08/F13/F14).

Every scenario the audit called out, reproduced against the fixed code:
idempotent payment attempts, the durable webhook inbox, fail-closed
production, per-recipient payouts (fleet operator included), the refund
ledger, and the customer app's POST /api/jobs.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest
from sqlalchemy.exc import OperationalError

from models import db, User, Contractor, Job, Payment, Refund, WebhookEvent, generate_uuid
from models_payments import PaymentAttempt, Payout

_seq = iter(range(1, 100000))


@pytest.fixture(autouse=True)
def _quiet(client):
    with mock.patch("dispatcher.auto_assign_job_async"), \
         mock.patch("socket_events.broadcast_job_status"), \
         mock.patch("routes.payments._alert") as alert, \
         mock.patch("sameday_pay.instant_enabled", return_value=False):
        yield alert


def _customer(email=None):
    u = User(id=generate_uuid(), name="Audit Cx", role="customer",
             email=email or "cx{}@audit.test".format(next(_seq)),
             phone="(561) 555-{:04d}".format(next(_seq) % 10000))
    db.session.add(u)
    db.session.flush()
    return u


def _job(price=200.0, status="pending", with_payment=True, intent=None, pay_status="pending",
         customer=None, driver=None, operator_id=None):
    customer = customer or _customer()
    j = Job(id=generate_uuid(), customer_id=customer.id, status=status, total_price=price,
            base_price=price, service_fee=0.0, address="1 Audit Way, Lake Worth",
            confirmation_code="A{:05d}".format(next(_seq)),
            scheduled_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=3),
            driver_id=driver.id if driver else None, operator_id=operator_id)
    db.session.add(j)
    db.session.flush()
    if with_payment:
        db.session.add(Payment(id=generate_uuid(), job_id=j.id, amount=price, service_fee=0.0,
                               payment_status=pay_status, stripe_payment_intent_id=intent))
    db.session.commit()
    return j


def _token(user_id):
    from auth_routes import generate_token
    return {"Authorization": "Bearer " + generate_token(user_id)}


def _hauler(connect=None, operator_id=None, is_operator=False):
    u = User(id=generate_uuid(), email="h{}@audit.test".format(next(_seq)), name="Hauler", role="driver")
    db.session.add(u)
    db.session.flush()
    c = Contractor(user_id=u.id, is_online=True, approval_status="approved", stripe_connect_id=connect,
                   operator_id=operator_id, is_operator=is_operator)
    db.session.add(c)
    db.session.commit()
    return c


def _stripe_mock(cancel_ok=True):
    s = mock.MagicMock()
    n = iter(range(1, 1000))

    def create(**kw):
        i = next(n)
        return mock.MagicMock(id="pi_real_{}".format(i), client_secret="pi_real_{}_secret".format(i))
    s.PaymentIntent.create.side_effect = create
    if not cancel_ok:
        s.PaymentIntent.cancel.side_effect = RuntimeError("This PaymentIntent has already succeeded")
    s.Transfer.create.side_effect = lambda **kw: mock.MagicMock(id="tr_{}".format(next(n)))
    s.Refund.create.side_effect = lambda **kw: mock.MagicMock(id="re_{}".format(next(n)))
    return s


def _event(kind, obj):
    return {"id": "evt_{}".format(next(_seq)), "type": kind, "data": {"object": obj}}


def _post_webhook(client, event):
    return client.post("/api/webhooks/stripe", data=json.dumps(event), content_type="application/json")


# ---------------------------------------------------------------------------
# F06 — idempotent attempts bound to a checkout capability
# ---------------------------------------------------------------------------
def test_checkout_token_or_owner_required_and_unknown_booking_404(client):
    from routes.payments import checkout_token
    job = _job()
    body = {"bookingId": job.id, "amount": 200, "submission_key": generate_uuid()}
    assert client.post("/api/payments/create-intent-simple", json=body).status_code == 403
    assert client.post("/api/payments/create-intent-simple",
                       json=dict(body, checkout_token="ck_bogus")).status_code == 403
    assert client.post("/api/payments/create-intent-simple",
                       json=dict(body, bookingId=generate_uuid(), checkout_token=checkout_token(job.id))
                       ).status_code == 404
    assert client.post("/api/payments/create-intent-simple",
                       json={"amount": 200, "submission_key": generate_uuid()}).status_code == 400
    # missing submission_key is rejected even with a valid capability
    r = client.post("/api/payments/create-intent-simple",
                    json={"bookingId": job.id, "amount": 200, "checkout_token": checkout_token(job.id)})
    assert r.status_code == 400 and r.get_json()["code"] == "submission_key_required"
    # the owner's JWT works without a token
    r = client.post("/api/payments/create-intent-simple", json=body, headers=_token(job.customer_id))
    assert r.status_code == 201, r.get_json()
    assert r.get_json()["paymentIntentId"].startswith("pi_dev_")
    att = PaymentAttempt.query.filter_by(job_id=job.id).one()
    assert att.actor == "owner" and att.user_id == job.customer_id and att.amount_cents == 20000


def test_duplicate_submission_key_returns_same_intent(client):
    from routes.payments import checkout_token
    job = _job(price=150.0)
    key = generate_uuid()
    body = {"bookingId": job.id, "amount": 150, "submission_key": key, "checkout_token": checkout_token(job.id)}
    s = _stripe_mock()
    with mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_x"}), \
         mock.patch("routes.payments._get_stripe", return_value=s):
        r1 = client.post("/api/payments/create-intent-simple", json=body)
        r2 = client.post("/api/payments/create-intent-simple", json=body)
        r3 = client.post("/api/payments/create-intent-simple", json=body)
    assert r1.status_code == 201 and r2.status_code == 201 and r3.status_code == 201
    j1, j2 = r1.get_json(), r2.get_json()
    assert j1["paymentIntentId"] == j2["paymentIntentId"] == r3.get_json()["paymentIntentId"]
    assert j1["clientSecret"] == j2["clientSecret"]
    assert j1["reused"] is False and j2["reused"] is True
    assert s.PaymentIntent.create.call_count == 1
    assert PaymentAttempt.query.filter_by(job_id=job.id).count() == 1
    att = PaymentAttempt.query.filter_by(job_id=job.id).one()
    kw = s.PaymentIntent.create.call_args.kwargs
    assert kw["idempotency_key"] == "pi_" + att.id and kw["amount"] == 15000
    assert kw["metadata"]["job_id"] == job.id and kw["metadata"]["attempt_id"] == att.id
    assert Payment.query.filter_by(job_id=job.id).one().stripe_payment_intent_id == j1["paymentIntentId"]


def test_concurrent_create_intent_calls_do_not_create_two_attempts(client, app):
    """The second caller arrives while the first is still talking to Stripe:
    the attempt row is already durable, so it sees the in-flight attempt and
    backs off instead of minting a second payable intent."""
    from routes.payments import checkout_token
    job = _job(price=120.0)
    key = generate_uuid()
    body = {"bookingId": job.id, "amount": 120, "submission_key": key, "checkout_token": checkout_token(job.id)}
    s = _stripe_mock()
    inner = {}

    def create_while_racing(**kw):
        with app.test_client() as c2:
            inner["resp"] = c2.post("/api/payments/create-intent-simple", json=body)
        return mock.MagicMock(id="pi_real_race", client_secret="pi_real_race_secret")
    s.PaymentIntent.create.side_effect = create_while_racing

    with mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_x"}), \
         mock.patch("routes.payments._get_stripe", return_value=s):
        r = client.post("/api/payments/create-intent-simple", json=body)
    assert r.status_code == 201 and r.get_json()["paymentIntentId"] == "pi_real_race"
    assert inner["resp"].status_code == 409
    assert inner["resp"].get_json()["code"] == "attempt_in_progress"
    assert s.PaymentIntent.create.call_count == 1
    assert PaymentAttempt.query.filter_by(job_id=job.id).count() == 1
    # once the first call finished, the same key gets the same intent
    with mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_x"}), \
         mock.patch("routes.payments._get_stripe", return_value=s):
        again = client.post("/api/payments/create-intent-simple", json=body)
    assert again.status_code == 201 and again.get_json()["reused"] is True
    assert s.PaymentIntent.create.call_count == 1


def test_new_submission_key_supersedes_and_cancels_old_intent(client):
    from routes.payments import checkout_token
    job = _job(price=99.0)
    ck = checkout_token(job.id)
    s = _stripe_mock()
    with mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_x"}), \
         mock.patch("routes.payments._get_stripe", return_value=s):
        a = client.post("/api/payments/create-intent-simple",
                        json={"bookingId": job.id, "submission_key": generate_uuid(), "checkout_token": ck}).get_json()
        b = client.post("/api/payments/create-intent-simple",
                        json={"bookingId": job.id, "submission_key": generate_uuid(), "checkout_token": ck}).get_json()
    assert a["paymentIntentId"] != b["paymentIntentId"]
    s.PaymentIntent.cancel.assert_called_once_with(a["paymentIntentId"])
    old = PaymentAttempt.query.filter_by(stripe_intent_id=a["paymentIntentId"]).one()
    new = PaymentAttempt.query.filter_by(stripe_intent_id=b["paymentIntentId"]).one()
    assert old.status == "superseded" and old.superseded_by == new.id and new.status == "created"
    assert Payment.query.filter_by(job_id=job.id).one().stripe_payment_intent_id == b["paymentIntentId"]


def test_cancel_failure_keeps_both_intent_ids(client, _quiet):
    from routes.payments import checkout_token
    job = _job(price=99.0)
    ck = checkout_token(job.id)
    s = _stripe_mock(cancel_ok=False)
    with mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_x"}), \
         mock.patch("routes.payments._get_stripe", return_value=s):
        a = client.post("/api/payments/create-intent-simple",
                        json={"bookingId": job.id, "submission_key": generate_uuid(), "checkout_token": ck}).get_json()
        b = client.post("/api/payments/create-intent-simple",
                        json={"bookingId": job.id, "submission_key": generate_uuid(), "checkout_token": ck}).get_json()
    old = PaymentAttempt.query.filter_by(stripe_intent_id=a["paymentIntentId"]).one()
    assert old.status == "cancel_failed" and old.stripe_intent_id == a["paymentIntentId"]
    assert PaymentAttempt.query.filter_by(stripe_intent_id=b["paymentIntentId"]).one().status == "created"
    assert _quiet.call_count == 1 and "cancel failed" in _quiet.call_args[0][0].lower()


def test_paid_booking_refuses_new_attempts(client):
    from routes.payments import checkout_token
    job = _job(pay_status="succeeded", intent="pi_paid_1")
    r = client.post("/api/payments/create-intent-simple",
                    json={"bookingId": job.id, "submission_key": generate_uuid(),
                          "checkout_token": checkout_token(job.id)})
    assert r.status_code == 409 and r.get_json()["code"] == "already_paid"
    assert Payment.query.filter_by(job_id=job.id).one().stripe_payment_intent_id == "pi_paid_1"


def test_authenticated_create_intent_uses_attempts_too(client):
    job = _job(price=100.0)
    key = generate_uuid()
    r = client.post("/api/payments/create-intent", headers=_token(job.customer_id),
                    json={"job_id": job.id, "submission_key": key, "tip_amount": 10})
    assert r.status_code == 201, r.get_json()
    assert r.get_json()["amount"] == 110.0
    r2 = client.post("/api/payments/create-intent", headers=_token(job.customer_id),
                     json={"job_id": job.id, "submission_key": key, "tip_amount": 10})
    assert r2.get_json()["payment_intent_id"] == r.get_json()["payment_intent_id"] and r2.get_json()["reused"]
    r3 = client.post("/api/payments/create-intent", headers=_token(job.customer_id),
                     json={"job_id": job.id, "tip_amount": 10})
    assert r3.status_code == 400
    p = Payment.query.filter_by(job_id=job.id).one()
    assert p.tip_amount == 10.0 and p.amount == 110.0


# ---------------------------------------------------------------------------
# F07 — durable webhook inbox
# ---------------------------------------------------------------------------
def test_handler_exception_returns_500_and_retry_processes(client):
    job = _job(price=134.57, intent="pi_inbox_1")
    ev = _event("payment_intent.succeeded", {"id": "pi_inbox_1", "amount": 13457, "currency": "usd",
                                             "metadata": {"job_id": job.id}})
    with mock.patch("routes.payments._handle_payment_succeeded", side_effect=RuntimeError("db hiccup")):
        r = _post_webhook(client, ev)
    assert r.status_code == 500
    row = WebhookEvent.query.filter_by(stripe_event_id=ev["id"]).one()
    assert row.status == "failed" and row.attempts == 1 and "db hiccup" in row.last_error
    assert db.session.get(Job, job.id).status == "pending"
    # Stripe retries the SAME event id → it is processed, not "duplicate"
    r = _post_webhook(client, ev)
    assert r.status_code == 200 and r.get_json() == {"received": True}
    db.session.expire_all()
    row = WebhookEvent.query.filter_by(stripe_event_id=ev["id"]).one()
    assert row.status == "processed" and row.attempts == 2 and row.processed_at is not None
    assert db.session.get(Job, job.id).status == "confirmed"
    assert Payment.query.filter_by(job_id=job.id).one().payment_status == "succeeded"
    # a third delivery is a genuine duplicate
    assert _post_webhook(client, ev).get_json()["duplicate"] is True


def test_db_outage_on_inbox_insert_is_500_not_200(client):
    job = _job(price=50.0, intent="pi_outage")
    ev = _event("payment_intent.succeeded", {"id": "pi_outage", "amount": 5000, "currency": "usd"})
    boom = OperationalError("INSERT", {}, Exception("connection lost"))
    with mock.patch.object(db.session, "commit", side_effect=boom):
        r = _post_webhook(client, ev)
    assert r.status_code == 500
    db.session.rollback()
    assert WebhookEvent.query.filter_by(stripe_event_id=ev["id"]).count() == 0
    assert Payment.query.filter_by(job_id=job.id).one().payment_status == "pending"
    # once the DB is back, the retried event processes normally
    assert _post_webhook(client, ev).status_code == 200
    assert Payment.query.filter_by(job_id=job.id).one().payment_status == "succeeded"


def test_exhausted_event_stops_retrying_and_alerts(client, _quiet):
    job = _job(price=50.0, intent="pi_exhaust")
    ev = _event("payment_intent.succeeded", {"id": "pi_exhaust", "amount": 5000, "currency": "usd"})
    with mock.patch("routes.payments.WEBHOOK_MAX_ATTEMPTS", 2), \
         mock.patch("routes.payments._handle_payment_succeeded", side_effect=RuntimeError("still broken")):
        assert _post_webhook(client, ev).status_code == 500
        assert _post_webhook(client, ev).status_code == 500
        r = _post_webhook(client, ev)
    assert r.status_code == 200 and r.get_json()["failed"] is True
    assert any("gave up" in c.args[0] for c in _quiet.call_args_list)
    assert WebhookEvent.query.filter_by(stripe_event_id=ev["id"]).one().attempts == 2


def test_unknown_intent_is_recorded_as_orphan_and_alerted(client, _quiet):
    ev = _event("payment_intent.succeeded", {"id": "pi_nobody", "amount": 5000, "currency": "usd", "metadata": {}})
    r = _post_webhook(client, ev)
    assert r.status_code == 200 and r.get_json()["orphan"] is True
    assert WebhookEvent.query.filter_by(stripe_event_id=ev["id"]).one().status == "orphan"
    assert "Orphan" in _quiet.call_args[0][0]


def test_amount_mismatch_against_attempt_does_not_settle(client, _quiet):
    from routes.payments import checkout_token
    job = _job(price=200.0)
    r = client.post("/api/payments/create-intent-simple",
                    json={"bookingId": job.id, "submission_key": generate_uuid(),
                          "checkout_token": checkout_token(job.id)}).get_json()
    ev = _event("payment_intent.succeeded", {"id": r["paymentIntentId"], "amount": 5000, "currency": "usd"})
    res = _post_webhook(client, ev).get_json()
    assert res["orphan"] is True and "mismatch" in res["reason"]
    assert Payment.query.filter_by(job_id=job.id).one().payment_status == "pending"
    assert "mismatch" in WebhookEvent.query.filter_by(stripe_event_id=ev["id"]).one().last_error
    assert "mismatch" in _quiet.call_args[0][1].lower()
    ok = _event("payment_intent.succeeded", {"id": r["paymentIntentId"], "amount": 20000, "currency": "usd"})
    assert _post_webhook(client, ok).get_json() == {"received": True}
    assert Payment.query.filter_by(job_id=job.id).one().payment_status == "succeeded"
    assert PaymentAttempt.query.filter_by(job_id=job.id).one().status == "succeeded"


def test_admin_can_list_and_retry_failed_events(client):
    admin = User(id=generate_uuid(), email="admin{}@audit.test".format(next(_seq)), name="Admin", role="admin")
    db.session.add(admin)
    db.session.commit()
    job = _job(price=60.0, intent="pi_admin_retry")
    ev = _event("payment_intent.succeeded", {"id": "pi_admin_retry", "amount": 6000, "currency": "usd"})
    with mock.patch("routes.payments._handle_payment_succeeded", side_effect=RuntimeError("boom")):
        _post_webhook(client, ev)
    assert client.get("/api/payments/admin/webhook-events", headers=_token(job.customer_id)).status_code == 403
    lst = client.get("/api/payments/admin/webhook-events", headers=_token(admin.id)).get_json()
    assert lst["count"] == 1 and lst["events"][0]["stripe_event_id"] == ev["id"]
    row_id = lst["events"][0]["id"]
    r = client.post("/api/payments/admin/webhook-events/{}/retry".format(row_id), headers=_token(admin.id))
    assert r.status_code == 200 and r.get_json()["event"]["status"] == "processed"
    assert Payment.query.filter_by(job_id=job.id).one().payment_status == "succeeded"
    ledger = client.get("/api/payments/admin/jobs/{}/ledger".format(job.id), headers=_token(admin.id)).get_json()
    assert ledger["payment"]["payment_status"] == "succeeded"


# ---------------------------------------------------------------------------
# F08 — fail closed in production
# ---------------------------------------------------------------------------
def test_production_without_stripe_key_is_503_everywhere(client):
    from routes.payments import checkout_token, payments_ready, payments_status, attempt_payout
    job = _job(price=80.0)
    hauler = _hauler(connect="acct_dev_1")
    done = _job(price=80.0, status="completed", pay_status="succeeded", intent="pi_done", driver=hauler)
    prod = {"FLASK_ENV": "production", "STRIPE_SECRET_KEY": ""}
    with mock.patch.dict(os.environ, prod):
        assert payments_ready() is False and payments_status()["fail_closed"] is True
        r = client.post("/api/payments/create-intent-simple",
                        json={"bookingId": job.id, "submission_key": generate_uuid(),
                              "checkout_token": checkout_token(job.id)})
        assert r.status_code == 503 and r.get_json()["code"] == "payments_unavailable"
        r = client.post("/api/payments/create-intent", headers=_token(job.customer_id),
                        json={"job_id": job.id, "submission_key": generate_uuid()})
        assert r.status_code == 503
        assert client.post("/api/payments/confirm-simple", json={"paymentIntentId": "pi_dev_abc"}).status_code == 503
        assert client.post("/api/payments/confirm-simple", json={"paymentIntentId": "pi_real_abc"}).status_code == 503
        assert client.post("/api/payments/confirm", headers=_token(job.customer_id),
                           json={"payment_intent_id": "pi_real_abc"}).status_code == 503
        res = attempt_payout(done.id)
        assert res["status"] == "unavailable" and res["ok"] is False
        r = client.post("/api/payments/payout/{}".format(done.id), headers=_token(hauler.user_id))
        assert r.status_code == 503
        r = client.post("/api/payments/payout/instant", headers=_token(hauler.user_id))
        assert r.status_code == 503
        assert client.post("/api/payments/connect/create-account", headers=_token(hauler.user_id)).status_code == 503
        from sameday_pay import instant_after_transfer
        with mock.patch("sameday_pay.instant_enabled", return_value=True):
            inst = instant_after_transfer(Payment.query.filter_by(job_id=done.id).one(), hauler, 50.0)
        assert inst["method"] == "standard" and "unavailable" in inst["reason"]
    # nothing fabricated
    assert PaymentAttempt.query.filter_by(job_id=job.id).count() == 0
    assert Payment.query.filter_by(job_id=job.id).one().stripe_payment_intent_id is None
    p = Payment.query.filter_by(job_id=done.id).one()
    assert p.payout_status == "pending" and p.instant_payout_id is None
    assert Payout.query.filter_by(job_id=done.id).count() == 0
    # development keeps the dev branch for tests
    with mock.patch.dict(os.environ, {"FLASK_ENV": "development", "STRIPE_SECRET_KEY": ""}):
        r = client.post("/api/payments/create-intent-simple",
                        json={"bookingId": job.id, "submission_key": generate_uuid(),
                              "checkout_token": checkout_token(job.id)})
        assert r.status_code == 201 and r.get_json()["paymentIntentId"].startswith("pi_dev_")


# ---------------------------------------------------------------------------
# F13 — per-recipient payouts, fleet operator transfer
# ---------------------------------------------------------------------------
def test_fleet_operator_gets_its_own_transfer_and_payout_rows(client):
    from routes.payments import attempt_payout
    operator = _hauler(connect="acct_op", is_operator=True)
    driver = _hauler(connect="acct_drv", operator_id=operator.id)
    job = _job(price=200.0, status="completed", pay_status="succeeded", intent="pi_fleet",
               driver=driver, operator_id=operator.id)
    s = _stripe_mock()
    with mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_x"}), \
         mock.patch("routes.payments._get_stripe", return_value=s):
        r = attempt_payout(job.id)
    assert r["ok"] and r["status"] == "paid" and r["operator"] == "transferred"
    # split snapshotted at payout against the final assignment: 200 - 20% = 160 gross,
    # operator 15% of that = 24, driver 136
    p = Payment.query.filter_by(job_id=job.id).one()
    assert p.driver_payout_amount == 136.0 and p.operator_payout_amount == 24.0
    assert p.split_operator_id == operator.id and p.payout_status == "paid"
    calls = {c.kwargs["destination"]: c.kwargs for c in s.Transfer.create.call_args_list}
    assert calls["acct_drv"]["amount"] == 13600 and calls["acct_drv"]["idempotency_key"] == "payout_" + job.id
    assert calls["acct_op"]["amount"] == 2400 and calls["acct_op"]["idempotency_key"] == "payout_{}_operator".format(job.id)
    rows = {x.recipient_type: x for x in Payout.query.filter_by(job_id=job.id).all()}
    assert rows["driver"].status == "transferred" and rows["driver"].stripe_transfer_id.startswith("tr_")
    assert rows["operator"].status == "transferred" and rows["operator"].operator_id == operator.id
    assert rows["operator"].amount_cents == 2400 and rows["driver"].contractor_id == driver.id
    # idempotent re-run: no second transfer for either leg
    with mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_x"}), \
         mock.patch("routes.payments._get_stripe", return_value=s):
        assert attempt_payout(job.id)["status"] == "already_paid"
    assert s.Transfer.create.call_count == 2


def test_operator_without_connect_is_parked_not_lost(client):
    from routes.payments import attempt_payout
    operator = _hauler(connect=None, is_operator=True)
    driver = _hauler(connect="acct_drv2", operator_id=operator.id)
    job = _job(price=100.0, status="completed", pay_status="succeeded", intent="pi_fleet2",
               driver=driver, operator_id=operator.id)
    s = _stripe_mock()
    with mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_x"}), \
         mock.patch("routes.payments._get_stripe", return_value=s):
        r = attempt_payout(job.id)
    assert r["status"] == "paid" and r["operator"] == "pending_connect"
    assert s.Transfer.create.call_count == 1
    op_row = Payout.query.filter_by(job_id=job.id, recipient_type="operator").one()
    assert op_row.status == "pending_connect" and op_row.amount_cents == 1200


def test_split_recomputed_when_operator_assigned_after_payment(client):
    operator = _hauler(connect="acct_op3", is_operator=True)
    driver = _hauler(connect="acct_drv3", operator_id=operator.id)
    job = _job(price=200.0, status="confirmed", pay_status="succeeded", intent="pi_split")
    p = Payment.query.filter_by(job_id=job.id).one()
    from routes.payments import recompute_payment_split
    recompute_payment_split(p, job)
    db.session.commit()
    assert p.operator_payout_amount == 0.0 and p.driver_payout_amount == 160.0
    # ORM assignment (dispatcher / manual assign) → flush hook re-snapshots the split
    job.driver_id = driver.id
    job.operator_id = operator.id
    job.status = "assigned"
    db.session.commit()
    db.session.refresh(p)
    assert p.operator_payout_amount == 24.0 and p.driver_payout_amount == 136.0 and p.split_operator_id == operator.id


def test_driver_pending_total_includes_failed_and_pending_connect(client):
    driver = _hauler(connect="acct_drv4")
    for st, amt in (("pending", 10.0), ("failed", 20.0), ("pending_connect", 30.0), ("paid", 40.0)):
        j = _job(price=100.0, status="completed", pay_status="succeeded", intent="pi_pend_{}".format(next(_seq)),
                 driver=driver)
        p = Payment.query.filter_by(job_id=j.id).one()
        p.driver_payout_amount = amt
        p.payout_status = st
        db.session.commit()
    r = client.get("/api/driver/earnings", headers=_token(driver.user_id))
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["earnings"]["pending_payout"] == 60.0
    r2 = client.get("/api/payments/earnings", headers=_token(driver.user_id))
    assert r2.get_json()["earnings"]["pending_payout"] == 60.0


# ---------------------------------------------------------------------------
# F14 — refunds as a ledger
# ---------------------------------------------------------------------------
def test_partial_refund_then_full_refund_via_charge_refunded(client):
    job = _job(price=200.0, pay_status="succeeded", intent="pi_refund")
    partial = _event("charge.refunded", {"id": "ch_1", "payment_intent": "pi_refund", "amount": 20000,
                                         "amount_refunded": 5000,
                                         "refunds": {"data": [{"id": "re_a", "amount": 5000, "status": "succeeded",
                                                               "reason": "requested_by_customer"}]}})
    assert _post_webhook(client, partial).status_code == 200
    p = Payment.query.filter_by(job_id=job.id).one()
    assert p.payment_status == "partially_refunded" and p.refunded_amount == 50.0
    assert Refund.query.filter_by(stripe_refund_id="re_a").one().amount == 50.0
    # replay of the same charge state is idempotent
    assert _post_webhook(client, dict(partial, id="evt_replay_{}".format(next(_seq)))).status_code == 200
    assert Refund.query.filter_by(payment_id=p.id).count() == 1
    full = _event("charge.refunded", {"id": "ch_1", "payment_intent": "pi_refund", "amount": 20000,
                                      "amount_refunded": 20000,
                                      "refunds": {"data": [{"id": "re_a", "amount": 5000, "status": "succeeded"},
                                                           {"id": "re_b", "amount": 15000, "status": "succeeded"}]}})
    assert _post_webhook(client, full).status_code == 200
    db.session.refresh(p)
    assert p.payment_status == "refunded" and p.refunded_amount == 200.0
    assert Refund.query.filter_by(payment_id=p.id).count() == 2
    # a late success event never overwrites the refund
    late = _event("payment_intent.succeeded", {"id": "pi_refund", "amount": 20000, "currency": "usd"})
    assert _post_webhook(client, late).status_code == 200
    db.session.refresh(p)
    assert p.payment_status == "refunded"


def test_success_event_for_cancelled_job_auto_refunds(client):
    job = _job(price=120.0, status="cancelled", intent="pi_late_cancel")
    ev = _event("payment_intent.succeeded", {"id": "pi_late_cancel", "amount": 12000, "currency": "usd",
                                             "metadata": {"job_id": job.id}})
    assert _post_webhook(client, ev).status_code == 200
    p = Payment.query.filter_by(job_id=job.id).one()
    assert p.payment_status == "refunded" and p.refunded_amount == 120.0
    row = Refund.query.filter_by(payment_id=p.id).one()
    assert row.reason == "paid_after_cancellation" and row.status == "succeeded" and row.amount == 120.0
    assert db.session.get(Job, job.id).status == "cancelled"
    # idempotent: a replayed success is a no-op, no second refund
    ev2 = _event("payment_intent.succeeded", {"id": "pi_late_cancel", "amount": 12000, "currency": "usd"})
    assert _post_webhook(client, ev2).status_code == 200
    assert Refund.query.filter_by(payment_id=p.id).count() == 1


def test_refund_job_helper_ledger_and_reversal_flag(client, _quiet):
    from routes.payments import refund_job
    driver = _hauler(connect="acct_drv5")
    job = _job(price=200.0, status="completed", pay_status="succeeded", intent="pi_rev", driver=driver)
    p = Payment.query.filter_by(job_id=job.id).one()
    db.session.add(Payout(id=generate_uuid(), job_id=job.id, payment_id=p.id, recipient_type="driver",
                          contractor_id=driver.id, amount_cents=13600, status="transferred",
                          stripe_transfer_id="tr_done"))
    db.session.commit()
    s = _stripe_mock()
    with mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_x"}), \
         mock.patch("routes.payments._get_stripe", return_value=s):
        r = refund_job(job, amount=50.0, reason="damage_credit", actor="admin")
        again = refund_job(job, amount=50.0, reason="damage_credit", actor="admin")
    assert r["ok"] and r["status"] == "succeeded" and r["amount"] == 50.0 and r["payment_status"] == "partially_refunded"
    assert again["refund_id"] == r["refund_id"] and s.Refund.create.call_count == 1
    kw = s.Refund.create.call_args.kwargs
    assert kw["payment_intent"] == "pi_rev" and kw["amount"] == 5000
    assert kw["idempotency_key"] == "refund_{}_{}".format(job.id, r["refund_id"])
    payout = Payout.query.filter_by(job_id=job.id).one()
    assert payout.reversal_required is True and payout.status == "transferred"   # never auto-reversed
    assert any("reversal" in c.args[0].lower() for c in _quiet.call_args_list)
    with mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_x"}), \
         mock.patch("routes.payments._get_stripe", return_value=s):
        rest = refund_job(job, reason="customer_cancelled")
    assert rest["amount"] == 150.0 and rest["payment_status"] == "refunded"
    assert refund_job(job, reason="more")["status"] == "nothing_to_refund"
    assert refund_job(_job(price=10.0), reason="x")["status"] == "not_refundable"


def test_refund_job_stripe_failure_is_recorded_not_hidden(client, _quiet):
    from routes.payments import refund_job
    job = _job(price=80.0, pay_status="succeeded", intent="pi_rf")
    s = _stripe_mock()
    s.Refund.create.side_effect = RuntimeError("charge already refunded")
    with mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_x"}), \
         mock.patch("routes.payments._get_stripe", return_value=s):
        r = refund_job(job, reason="cancel")
    assert r["ok"] is False and r["status"] == "failed"
    row = Refund.query.filter_by(payment_id=Payment.query.filter_by(job_id=job.id).one().id).one()
    assert row.status == "failed" and "stripe_error" in row.reason
    assert Payment.query.filter_by(job_id=job.id).one().payment_status == "succeeded"
    assert "Refund FAILED" in _quiet.call_args[0][0]


def test_cancellation_cancels_every_open_attempt(client):
    from routes.payments import checkout_token, cancel_open_attempts
    job = _job(price=70.0)
    ck = checkout_token(job.id)
    s = _stripe_mock()
    with mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_x"}), \
         mock.patch("routes.payments._get_stripe", return_value=s):
        a = client.post("/api/payments/create-intent-simple",
                        json={"bookingId": job.id, "submission_key": generate_uuid(), "checkout_token": ck}).get_json()
        # ORM status change to cancelled → flush hook closes the live intent
        job = db.session.get(Job, job.id)
        job.status = "cancelled"
        db.session.commit()
    att = PaymentAttempt.query.filter_by(stripe_intent_id=a["paymentIntentId"]).one()
    assert att.status == "canceled"
    s.PaymentIntent.cancel.assert_called_once_with(a["paymentIntentId"])
    assert cancel_open_attempts(job) == 0
    # and no new attempt can be minted for a cancelled booking
    r = client.post("/api/payments/create-intent-simple",
                    json={"bookingId": job.id, "submission_key": generate_uuid(), "checkout_token": ck})
    assert r.status_code == 409 and r.get_json()["code"] == "booking_cancelled"


# ---------------------------------------------------------------------------
# F05 — POST /api/jobs and confirm for a job created after its intent
# ---------------------------------------------------------------------------
def test_post_api_jobs_creates_job_and_full_ios_checkout_flow(client, auth_headers):
    payload = {
        "service_type": "furniture", "address": "6319 Shadowtree Lane, Lake Worth, FL 33463",
        "lat": 26.61, "lng": -80.11, "photo_urls": [], "scheduled_date": "2026-09-20",
        "scheduled_time": "10:00", "estimated_price": 120.0, "volume_tier": "medium",
    }
    with mock.patch("routes.booking.is_in_service_area", return_value=True), \
         mock.patch("dispatcher.has_active_coverage", return_value=True):
        r = client.post("/api/jobs", json=payload, headers={"Authorization": auth_headers["Authorization"]})
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body["success"] and body["job_id"] and body["checkout_token"].startswith("ck_")
    job = db.session.get(Job, body["job_id"])
    assert job is not None and job.customer_id == auth_headers["_user"]["id"] and job.status == "pending"
    assert job.items[0]["category"] == "furniture" and job.lead_source == "ios_app"
    assert Payment.query.filter_by(job_id=job.id).one().payment_status == "pending"
    # the app then pays with the token it was handed (no JWT needed on the payment routes)
    r = client.post("/api/payments/create-intent-simple",
                    json={"bookingId": job.id, "submission_key": generate_uuid(),
                          "checkout_token": body["checkout_token"], "amount": 120.0})
    assert r.status_code == 201, r.get_json()
    pi = r.get_json()["paymentIntentId"]
    r = client.post("/api/payments/confirm-simple", json={"paymentIntentId": pi, "bookingId": job.id})
    assert r.status_code == 200 and r.get_json()["payment"]["payment_status"] == "succeeded"
    assert db.session.get(Job, job.id).status == "confirmed"
    # validation failures keep the app's {success, message} shape
    bad = client.post("/api/jobs", json={"service_type": "x"}, headers={"Authorization": auth_headers["Authorization"]})
    assert bad.status_code == 400 and bad.get_json()["success"] is False and bad.get_json()["message"]


def test_confirm_adopts_intent_created_before_its_job(client):
    """iOS created the intent first (legacy wizard), then the job. Confirming
    with the intent id + booking hint links them instead of 404."""
    job = _job(price=90.0)
    r = client.post("/api/payments/confirm-simple", json={"paymentIntentId": "pi_dev_early1", "bookingId": job.id})
    assert r.status_code == 200, r.get_json()
    p = Payment.query.filter_by(job_id=job.id).one()
    assert p.stripe_payment_intent_id == "pi_dev_early1" and p.payment_status == "succeeded"
    assert db.session.get(Job, job.id).status == "confirmed"
    # owner route: same adoption, via Stripe metadata when the client has no hint
    job2 = _job(price=90.0)
    s = _stripe_mock()
    s.PaymentIntent.retrieve.return_value = mock.MagicMock(status="succeeded",
                                                          metadata={"job_id": job2.id}, **{"get.side_effect": None})
    s.PaymentIntent.retrieve.return_value.get = lambda k, d=None: {"metadata": {"job_id": job2.id}}.get(k, d)
    with mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_x"}), \
         mock.patch("routes.payments._get_stripe", return_value=s):
        r = client.post("/api/payments/confirm", headers=_token(job2.customer_id),
                        json={"payment_intent_id": "pi_real_meta"})
    assert r.status_code == 200, r.get_json()
    assert Payment.query.filter_by(job_id=job2.id).one().stripe_payment_intent_id == "pi_real_meta"
    assert client.post("/api/payments/confirm-simple", json={"paymentIntentId": "pi_dev_ghost"}).status_code == 404
