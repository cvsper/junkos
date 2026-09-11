"""Two payment rules ported from Codex's iOS-continuity branch onto main's
own payment-attempt and payout tables, rather than merging its parallel ones."""
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from models import db, Payment, generate_uuid
from models_payments import Payout, PaymentAttempt
from tests.test_audit_payments import _job, _hauler, _stripe_mock, _quiet  # noqa: F401


def test_a_tip_moves_as_its_own_transfer_and_never_blocks_the_base_payout():
    hauler = _hauler(connect="acct_real_tip")
    job = _job(price=200.0, status="completed", pay_status="succeeded", intent="pi_tip", driver=hauler)
    p = Payment.query.filter_by(job_id=job.id).one()
    p.driver_payout_amount = 164.0        # 144 base + 20 tip, as recompute_payment_split stores it
    p.tip_amount = 20.0
    db.session.commit()
    s = _stripe_mock()
    with mock.patch("routes.payments._get_stripe", return_value=s), \
         mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_x"}), \
         mock.patch("sameday_pay.instant_after_transfer", return_value={"method": "standard"}):
        from routes.payments import attempt_payout
        r = attempt_payout(job.id)
    assert r["status"] == "paid"
    legs = {(c.kwargs["idempotency_key"], c.kwargs["amount"]) for c in s.Transfer.create.call_args_list}
    assert ("payout_" + job.id, 14400) in legs, "base leg excludes the tip"
    assert ("tip_" + job.id, 2000) in legs, "the tip is its own transfer"
    rows = {r.recipient_type: r for r in Payout.query.filter_by(job_id=job.id).all()}
    assert rows["driver"].amount_cents == 14400 and rows["tip"].amount_cents == 2000
    assert rows["tip"].status == "transferred"


def test_a_failed_tip_is_retried_by_the_sweep_not_lost():
    hauler = _hauler(connect="acct_real_tip2")
    job = _job(price=100.0, status="completed", pay_status="succeeded", intent="pi_tip2", driver=hauler)
    p = Payment.query.filter_by(job_id=job.id).one()
    p.driver_payout_amount = 82.0; p.tip_amount = 10.0
    db.session.commit()
    s = _stripe_mock()
    def create(**kw):
        if kw["idempotency_key"].startswith("tip_"):
            raise RuntimeError("stripe blip")
        return mock.MagicMock(id="tr_" + kw["idempotency_key"])
    s.Transfer.create.side_effect = create
    with mock.patch("routes.payments._get_stripe", return_value=s), \
         mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_x"}), \
         mock.patch("sameday_pay.instant_after_transfer", return_value={"method": "standard"}), \
         mock.patch("routes.payments._alert") as alert:
        from routes.payments import attempt_payout
        r = attempt_payout(job.id)
    assert r["status"] == "paid", "the base payout succeeded — a tip blip must not fail it"
    tip = Payout.query.filter_by(job_id=job.id, recipient_type="tip").one()
    assert tip.status == "failed" and alert.call_count == 1
    # the sweep retries the tip on its own
    s.Transfer.create.side_effect = None
    s.Transfer.create.return_value = mock.MagicMock(id="tr_tip_retry")
    from scheduler import _sweep_pending_payouts
    from flask import current_app
    with mock.patch("routes.payments._get_stripe", return_value=s), \
         mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_x"}):
        _sweep_pending_payouts(current_app._get_current_object())
    db.session.refresh(tip)
    assert tip.status == "transferred" and tip.stripe_transfer_id == "tr_tip_retry"


def test_an_unresolved_attempt_older_than_23h_is_handed_to_a_person_not_retried(client):
    from routes.payments import checkout_token
    job = _job(price=120.0)
    old = PaymentAttempt(id=generate_uuid(), job_id=job.id, client_submission_key="sub-stale-1",
                         amount_cents=12000, currency="usd", status="created",
                         created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=25))
    db.session.add(old); db.session.commit()
    with mock.patch("routes.payments._alert") as alert:
        r = client.post("/api/payments/create-intent-simple",
                        json={"bookingId": job.id, "amount": 120.0, "submission_key": "sub-stale-1",
                              "checkout_token": checkout_token(job.id)})
    assert r.status_code == 409 and r.get_json()["code"] == "attempt_needs_reconciliation"
    db.session.refresh(old)
    assert old.status == "needs_reconciliation" and alert.call_count == 1
    # a stale-but-younger one still resumes with the same key (the safe case)
    fresh = PaymentAttempt(id=generate_uuid(), job_id=job.id, client_submission_key="sub-stale-2",
                           amount_cents=12000, currency="usd", status="created",
                           created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2))
    db.session.add(fresh); db.session.commit()
    r2 = client.post("/api/payments/create-intent-simple",
                     json={"bookingId": job.id, "amount": 120.0, "submission_key": "sub-stale-2",
                           "checkout_token": checkout_token(job.id)})
    assert r2.status_code in (200, 201), r2.get_json()
