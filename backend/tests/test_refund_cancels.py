"""A full refund on unfinished work IS a cancellation.

Job AFB22IMO: the owner refunded the customer from the Stripe dashboard after
the haul never happened. Stripe told us, the payment flipped to "refunded" —
and the job stayed "assigned" to a hauler, at the top of the work queue as a
customer still waiting. Money and status disagreed, and only someone with
admin access could reconcile them.
"""
from unittest import mock

import pytest

from models import db, Job, Payment, Refund, Notification
from tests.test_audit_payments import _job, _hauler, _event, _post_webhook, _quiet  # noqa: F401
import cancellation


def _full_refund_event(intent, cents):
    return _event("charge.refunded", {
        "id": "ch_" + intent, "payment_intent": intent, "amount": cents, "amount_refunded": cents,
        "refunds": {"data": [{"id": "re_" + intent, "amount": cents, "status": "succeeded",
                              "reason": "requested_by_customer"}]},
    })


def test_full_refund_cancels_an_assigned_job_and_releases_the_hauler(client):
    hauler = _hauler()
    job = _job(price=307.80, status="assigned", pay_status="succeeded", intent="pi_afb", driver=hauler)
    assert _post_webhook(client, _full_refund_event("pi_afb", 30780)).status_code == 200

    db.session.refresh(job)
    p = Payment.query.filter_by(job_id=job.id).one()
    assert p.payment_status == "refunded" and p.refunded_amount == 307.80
    assert job.status == "cancelled", "refunded in full while assigned must cancel"
    assert job.cancelled_at is not None
    # the hauler is told, so nobody drives to a refunded job
    assert Notification.query.filter_by(user_id=hauler.user_id, type="job_cancelled").count() == 1


def test_it_never_issues_a_second_refund(client):
    job = _job(price=100.0, status="confirmed", pay_status="succeeded", intent="pi_once")
    s = mock.MagicMock()
    with mock.patch("routes.payments._get_stripe", return_value=s), \
         mock.patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test_x"}):
        assert _post_webhook(client, _full_refund_event("pi_once", 10000)).status_code == 200
    assert s.Refund.create.call_count == 0, "the money already went back — cancelling must not refund again"
    assert Refund.query.filter_by(payment_id=Payment.query.filter_by(job_id=job.id).one().id).count() == 1
    db.session.refresh(job)
    assert job.status == "cancelled"


def test_a_partial_refund_is_a_judgement_call_not_a_cancellation(client):
    hauler = _hauler()
    job = _job(price=200.0, status="assigned", pay_status="succeeded", intent="pi_part", driver=hauler)
    partial = _event("charge.refunded", {
        "id": "ch_pi_part", "payment_intent": "pi_part", "amount": 20000, "amount_refunded": 5000,
        "refunds": {"data": [{"id": "re_part", "amount": 5000, "status": "succeeded"}]},
    })
    with mock.patch("ops_contacts.alert_sms") as alert:
        assert _post_webhook(client, partial).status_code == 200
    db.session.refresh(job)
    assert job.status == "assigned"
    assert Payment.query.filter_by(job_id=job.id).one().payment_status == "partially_refunded"
    assert alert.call_count == 1, "a person is told about a partial refund on a moving job"


def test_a_refund_on_finished_work_is_a_money_decision_not_a_status_change(client):
    hauler = _hauler()
    job = _job(price=150.0, status="completed", pay_status="succeeded", intent="pi_done", driver=hauler)
    assert _post_webhook(client, _full_refund_event("pi_done", 15000)).status_code == 200
    db.session.refresh(job)
    assert job.status == "completed", "the haul happened; refunding it does not un-happen it"


def test_the_sweep_closes_jobs_refunded_before_the_rule_existed(client):
    """AFB22IMO's exact shape: payment already 'refunded', job still 'assigned'."""
    hauler = _hauler()
    stale = _job(price=307.80, status="assigned", pay_status="refunded", intent="pi_old", driver=hauler)
    fine = _job(price=120.0, status="assigned", pay_status="succeeded", intent="pi_fine", driver=hauler)

    closed = cancellation.reconcile_refunded_jobs()
    assert stale.confirmation_code in closed
    assert fine.confirmation_code not in closed
    db.session.refresh(stale); db.session.refresh(fine)
    assert stale.status == "cancelled" and fine.status == "assigned"
    # idempotent
    assert cancellation.reconcile_refunded_jobs() == []


def test_guard_is_quiet_on_garbage():
    assert cancellation.cancel_if_fully_refunded(None) is False
    assert cancellation.cancel_if_fully_refunded(mock.MagicMock(payment=None)) is False
