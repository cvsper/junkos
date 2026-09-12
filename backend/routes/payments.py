"""
Payment API routes for Umuve.
Stripe Connect: customer pays -> platform takes commission -> contractor gets payout.
"""

import os
import re
import time
import hmac
import hashlib
import base64
import logging
from functools import wraps
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import event as sa_event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import get_history

from models import (db, Job, Payment, Contractor, User, Notification, PromoCode, ReferralPayout,
                    Refund, WebhookEvent, generate_uuid, utcnow)
# Registers payment_attempts / payouts with db.metadata before create_all()
# (server.py imports this blueprint module first) — same trick as models_sameday.
from models_payments import PaymentAttempt, Payout, ATTEMPT_OPEN
from app_config import is_production
from auth_routes import require_auth, verify_token, JWT_SECRET
from extensions import limiter
from timeutils import fmt_local, local_date_str

payments_bp = Blueprint("payments", __name__, url_prefix="/api/payments")

_stripe = None

# Platform economics live in one place (pricing_config) so the operator's
# payout preview and their actual pay can't drift, and so the take rate is
# env-tunable for a launch (PLATFORM_COMMISSION_RATE / SERVICE_FEE_RATE).
from pricing_config import commission_rate as _commission_rate
from pricing_config import service_fee_rate as _service_fee_rate

PLATFORM_COMMISSION = _commission_rate()  # default 0.20, env PLATFORM_COMMISSION_RATE
SERVICE_FEE_RATE = _service_fee_rate()  # default 0.08, env SERVICE_FEE_RATE

# Payment.payout_status values that mean the hauler is still OWED the money.
PAYOUT_OWED_STATUSES = ("pending", "failed", "pending_connect")


def _get_stripe():
    global _stripe
    if _stripe is None:
        import stripe
        stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
        _stripe = stripe
    return _stripe


def recompute_payment_split(payment, job):
    """Compute commission / operator cut / driver payout on a Payment, in place.

    This is THE split. It must run on every path that marks a payment
    succeeded (webhook, /confirm, /confirm-simple) — bookings create the
    Payment with driver_payout_amount=0, and whichever confirmation path wins
    the race must fill it in, or the hauler gets paid $0. Tips are excluded
    from the split base and pass through 100% to the driver.

    Audit F13: the fleet share depends on job.operator_id, which is usually
    set at assignment — AFTER payment success. The split is therefore
    recomputed when assignment changes (see _payments_before_flush) and once
    more in attempt_payout if operator_id moved since; split_operator_id
    records which operator the numbers on the row were computed for.

    Does not commit; the caller's transaction persists it.
    """
    amount = payment.amount or 0.0
    tip = payment.tip_amount or 0.0
    # Dump fees are the hauler's out-of-pocket cost at the scale: like tips
    # they sit outside the split and pass through 100%.
    disposal = min(max(0.0, payment.disposal_fee or 0.0), max(0.0, amount - tip))
    split_base = max(0.0, round(amount - tip - disposal, 2))
    platform_commission = round(split_base * PLATFORM_COMMISSION, 2)
    service_fee = payment.service_fee or 0.0
    driver_gross = round(split_base - platform_commission - service_fee + disposal, 2)

    operator_payout = 0.0
    operator_id = getattr(job, "operator_id", None) if job is not None else None
    if operator_id:
        op = db.session.get(Contractor, operator_id)
        if op:
            rate = op.operator_commission_rate or 0.15
            operator_payout = round(driver_gross * rate, 2)

    payment.commission = platform_commission
    payment.operator_payout_amount = operator_payout
    payment.driver_payout_amount = max(0, round(driver_gross - operator_payout + tip, 2))
    payment.split_operator_id = operator_id or None


# ---------------------------------------------------------------------------
# Readiness / fail-closed (audit F08)
# ---------------------------------------------------------------------------
def _stripe_key():
    return os.environ.get("STRIPE_SECRET_KEY", "")


def payments_ready():
    """True when real money can move: a Stripe secret key is configured.

    Health/readiness should call this (server.py: ``payments.payments_ready()``)
    and report money movement as unavailable when it is False. In production
    every create-intent / confirm / payout path returns 503 in that state
    instead of fabricating pi_dev_/acct_dev_/po_mock success.
    """
    return bool(_stripe_key())


def payments_status():
    """Richer readiness detail for the health endpoint."""
    key = _stripe_key()
    return {
        "ready": bool(key),
        "stripe_key": bool(key),
        "webhook_secret": bool(os.environ.get("STRIPE_WEBHOOK_SECRET", "")),
        "mode": ("live" if key.startswith("sk_live") else "test" if key else "dev"),
        "fail_closed": is_production(),
    }


def _payments_unavailable():
    """Return a 503 response tuple when money must not move, else None.

    Production + no STRIPE_SECRET_KEY = fail closed. Outside production the
    dev branches (pi_dev_ intents, dev transfers) keep working for tests.
    """
    if is_production() and not payments_ready():
        logger.error("payments unavailable: STRIPE_SECRET_KEY is not set in production "
                     "(%s %s) — refusing to fabricate success", request.method if request else "",
                     request.path if request else "")
        return jsonify({"error": "payments unavailable", "code": "payments_unavailable"}), 503
    return None


def _money_unavailable():
    """Non-request variant of _payments_unavailable for attempt_payout & co."""
    return is_production() and not payments_ready()


def _alert(subject, body):
    """Ops alert via desk_health (email + Slack + admin notifications). Never raises."""
    try:
        from desk_health import _send_alert
        _send_alert(subject, body)
    except Exception:
        logger.warning("payments alert (desk_health unavailable): %s — %s", subject, body)


# ---------------------------------------------------------------------------
# Checkout capability (audit F06): a signed token scoped to one booking.
# Returned by POST /api/booking and POST /api/jobs; accepted by the public
# create-intent route in place of the owner's JWT so a third party holding a
# pending booking UUID can't replace or cancel its payable attempt.
# ---------------------------------------------------------------------------
def _checkout_secret():
    secret = os.environ.get("CHECKOUT_TOKEN_SECRET") or JWT_SECRET or ""
    if not secret:
        try:
            secret = current_app.config.get("SECRET_KEY", "") or ""
        except Exception:
            secret = ""
    return secret.encode() if isinstance(secret, str) else secret


def checkout_token(job_id):
    """HMAC capability for one booking. Stateless, no expiry (dies when paid)."""
    sig = hmac.new(_checkout_secret(), b"checkout:" + str(job_id).encode(), hashlib.sha256).digest()
    return "ck_" + base64.urlsafe_b64encode(sig).rstrip(b"=").decode()


def verify_checkout_token(job_id, token):
    if not token or not job_id:
        return False
    return hmac.compare_digest(str(token), checkout_token(job_id))


def _checkout_actor(job, data):
    """Who is allowed to create/replace payment attempts for this job?

    Returns (actor, user_id) — actor in {"owner", "checkout_token"} — or
    (None, None) when neither the owner JWT nor a valid checkout token is
    presented.
    """
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if token:
        uid = verify_token(token)
        if uid and job.customer_id == uid:
            return "owner", uid
        if uid:
            user = db.session.get(User, uid)
            if user and user.role == "admin":
                return "owner", uid
    ck = (data.get("checkout_token") or data.get("checkoutToken")
          or request.headers.get("X-Checkout-Token", ""))
    if verify_checkout_token(job.id, ck):
        return "checkout_token", None
    return None, None


_SUBMISSION_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
IN_FLIGHT_SECONDS = 30
RECONCILE_AFTER_SECONDS = 23 * 3600   # Stripe idempotency keys can expire at 24h


def _valid_submission_key(key):
    return bool(key) and bool(_SUBMISSION_KEY_RE.match(str(key)))


def _naive_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _is_dev_intent(intent_id):
    return bool(intent_id) and str(intent_id).startswith("pi_dev_")


def _cancel_intent(intent_id):
    """Best-effort Stripe cancel of a superseded intent. True when the intent
    is provably dead (cancelled, or a dev intent that never existed)."""
    if not intent_id or _is_dev_intent(intent_id):
        return True
    if not _stripe_key():
        return not is_production()
    try:
        _get_stripe().PaymentIntent.cancel(intent_id)
        return True
    except Exception as e:
        logger.warning("could not cancel superseded intent %s: %s", intent_id, str(e)[:200])
        return False


def _lock_job(job_id):
    """Row-lock the job (real on Postgres, no-op on SQLite) so two concurrent
    create-intent calls serialize on the read-check-insert below."""
    return Job.query.filter(Job.id == job_id).with_for_update().first()


def create_attempt_for_job(job_id, submission_key, amount, *, actor, user_id=None,
                           currency="usd", metadata=None, receipt_email=None,
                           payment_fields=None):
    """Create (or return) THE payable attempt for a job. Audit F06.

    Rules:
      * the PaymentAttempt row is committed BEFORE Stripe is called; the
        Stripe idempotency key is ``pi_<attempt.id>``;
      * the same submission_key returns the same intent (or 409 in_progress
        while the first call is still talking to Stripe);
      * a different submission_key supersedes every other open attempt via a
        conditional UPDATE; the old intent is cancelled — if Stripe refuses,
        the row is marked ``cancel_failed`` and both ids are retained;
      * Payment.stripe_payment_intent_id is "the current one"; history lives
        in payment_attempts.

    Returns (result_dict, None) or (None, (response, status)).
    """
    unavailable = _payments_unavailable()
    if unavailable:
        return None, unavailable
    if not _valid_submission_key(submission_key):
        return None, (jsonify({"error": "submission_key is required (8-64 chars, uuid recommended)",
                               "code": "submission_key_required"}), 400)
    cents = int(round(float(amount) * 100))
    if cents <= 0:
        return None, (jsonify({"error": "amount must be positive"}), 400)

    job = _lock_job(job_id)
    if not job:
        return None, (jsonify({"error": "Job not found"}), 404)
    if job.status in ("cancelled", "canceled"):
        return None, (jsonify({"error": "This booking was cancelled", "code": "booking_cancelled"}), 409)

    payment = Payment.query.filter_by(job_id=job.id).first()
    if payment and payment.payment_status in ("succeeded", "refunded", "partially_refunded"):
        return None, (jsonify({"error": "This booking is already paid", "code": "already_paid"}), 409)
    if not payment:
        payment = Payment(id=generate_uuid(), job_id=job.id, amount=round(cents / 100.0, 2),
                          service_fee=float(job.service_fee or 0), payment_status="pending")
        db.session.add(payment)
        db.session.flush()

    now = _naive_now()
    existing = PaymentAttempt.query.filter_by(job_id=job.id, client_submission_key=submission_key).first()
    attempt = None
    if existing is not None:
        if existing.status == "succeeded":
            return None, (jsonify({"error": "This booking is already paid", "code": "already_paid"}), 409)
        if existing.is_open and existing.stripe_intent_id:
            if existing.amount_cents != cents or existing.currency != currency:
                return None, (jsonify({"error": "Amount changed since this attempt was created; "
                                                "start a new attempt with a new submission_key",
                                       "code": "amount_changed",
                                       "attempt_id": existing.id}), 409)
            if payment.stripe_payment_intent_id != existing.stripe_intent_id:
                payment.stripe_payment_intent_id = existing.stripe_intent_id
                payment.payment_status = "pending"
            db.session.commit()
            return {"intent_id": existing.stripe_intent_id, "client_secret": existing.client_secret,
                    "attempt": existing, "payment": payment, "reused": True}, None
        if existing.status == "created" and not existing.stripe_intent_id:
            age = (now - (existing.created_at or now)).total_seconds()
            if age < IN_FLIGHT_SECONDS:
                db.session.rollback()
                return None, (jsonify({"error": "A payment attempt for this submission is in progress",
                                       "code": "attempt_in_progress", "retry_after": IN_FLIGHT_SECONDS,
                                       "attempt_id": existing.id}), 409)
            # Stripe may drop an idempotency key after 24 hours. Re-running an
            # unresolved attempt older than that with the same key could mint a
            # SECOND intent — a fresh charge dressed as a retry. Stop and hand it
            # to a person to reconcile against Stripe first.
            if age > RECONCILE_AFTER_SECONDS:
                existing.status = "needs_reconciliation"
                existing.last_error = "unresolved for {:.0f}h — reconcile against Stripe before retrying".format(age / 3600)
                db.session.commit()
                _alert("Payment attempt needs reconciliation",
                       "Job {} attempt {} has been unresolved for {:.0f}h. Look it up in Stripe by "
                       "idempotency key pi_{} before anyone retries.".format(job.id, existing.id, age / 3600, existing.id))
                return None, (jsonify({"error": "This payment attempt is too old to retry safely; "
                                                "support is reconciling it",
                                       "code": "attempt_needs_reconciliation", "attempt_id": existing.id}), 409)
            # The earlier request died mid-Stripe. Re-running with the same
            # idempotency key is safe: Stripe returns the same intent if it exists.
            attempt = existing
            attempt.amount_cents = cents
            attempt.currency = currency
            attempt.created_at = now
        else:
            return None, (jsonify({"error": "This submission_key was already used ({}); "
                                            "generate a new one".format(existing.status),
                                   "code": "submission_key_used"}), 409)

    if attempt is None:
        attempt = PaymentAttempt(id=generate_uuid(), job_id=job.id, payment_id=payment.id,
                                 client_submission_key=submission_key, amount_cents=cents,
                                 currency=currency, status="created", actor=actor, user_id=user_id)
        db.session.add(attempt)
    try:
        db.session.commit()          # durable BEFORE the external call (releases the row lock)
    except IntegrityError:
        db.session.rollback()        # lost the race on (job_id, submission_key)
        return None, (jsonify({"error": "A payment attempt for this submission is in progress",
                               "code": "attempt_in_progress", "retry_after": IN_FLIGHT_SECONDS}), 409)

    # Supersede every OTHER open attempt for this job (conditional update, so a
    # concurrent settle can't be overwritten), then cancel its intent.
    others = (PaymentAttempt.query
              .filter(PaymentAttempt.job_id == job.id, PaymentAttempt.id != attempt.id,
                      PaymentAttempt.status.in_(ATTEMPT_OPEN)).all())
    for old in others:
        res = db.session.execute(
            PaymentAttempt.__table__.update()
            .where(PaymentAttempt.id == old.id)
            .where(PaymentAttempt.status.in_(ATTEMPT_OPEN))
            .values(status="superseded", superseded_by=attempt.id, updated_at=now))
        if res.rowcount != 1:
            continue
        if old.stripe_intent_id and not _cancel_intent(old.stripe_intent_id):
            db.session.execute(
                PaymentAttempt.__table__.update()
                .where(PaymentAttempt.id == old.id)
                .values(status="cancel_failed", superseded_by=attempt.id,
                        last_error="Stripe refused to cancel; intent retained", updated_at=now))
            _alert("Payment intent cancel failed",
                   "job {} attempt {} intent {} could not be cancelled while attempt {} replaced it. "
                   "If it charges, the webhook settles it and the newer intent must be refunded."
                   .format(job.id, old.id, old.stripe_intent_id, attempt.id))
    db.session.commit()

    # --- external call ---
    intent_id = client_secret = None
    if _stripe_key():
        stripe = _get_stripe()
        kwargs = {"amount": cents, "currency": currency,
                  "metadata": dict(metadata or {}, job_id=job.id, attempt_id=attempt.id),
                  "idempotency_key": "pi_{}".format(attempt.id)}
        if receipt_email:
            kwargs["receipt_email"] = receipt_email
        try:
            intent = stripe.PaymentIntent.create(**kwargs)
            intent_id, client_secret = intent.id, intent.client_secret
        except Exception as e:
            db.session.execute(PaymentAttempt.__table__.update()
                               .where(PaymentAttempt.id == attempt.id)
                               .values(status="failed", last_error=str(e)[:500], updated_at=_naive_now()))
            db.session.commit()
            return None, (jsonify({"error": "Stripe error: {}".format(str(e))}), 502)
    else:
        intent_id = "pi_dev_{}".format(attempt.id[:8])
        client_secret = "{}_secret_dev".format(intent_id)

    # CAS: only publish the intent if nobody superseded us while Stripe was slow.
    res = db.session.execute(
        PaymentAttempt.__table__.update()
        .where(PaymentAttempt.id == attempt.id)
        .where(PaymentAttempt.status == "created")
        .values(stripe_intent_id=intent_id, client_secret=client_secret, updated_at=_naive_now()))
    if res.rowcount != 1:
        db.session.commit()
        _cancel_intent(intent_id)
        return None, (jsonify({"error": "This payment attempt was replaced by a newer one",
                               "code": "attempt_superseded"}), 409)

    payment.stripe_payment_intent_id = intent_id
    payment.amount = round(cents / 100.0, 2)
    for k, v in (payment_fields or {}).items():
        setattr(payment, k, v)
    payment.payment_status = "pending"
    payment.updated_at = utcnow()
    db.session.commit()
    db.session.refresh(attempt)
    return {"intent_id": intent_id, "client_secret": client_secret, "attempt": attempt,
            "payment": payment, "reused": False}, None


def cancel_open_attempts(job, reason="cancelled"):
    """Cancel every unsettled attempt/intent for a job (audit F14). Does not
    commit. Returns the number of attempts closed. Safe to call repeatedly."""
    job_id = job if isinstance(job, str) else job.id
    n = 0
    for att in PaymentAttempt.query.filter(PaymentAttempt.job_id == job_id,
                                           PaymentAttempt.status.in_(ATTEMPT_OPEN)).all():
        if att.stripe_intent_id and not _cancel_intent(att.stripe_intent_id):
            att.status = "cancel_failed"
            att.last_error = "cancel on {} refused by Stripe".format(reason)
            _alert("Payment intent cancel failed on cancellation",
                   "job {} attempt {} intent {} is still live after {}. If it charges, the "
                   "webhook auto-refunds it.".format(job_id, att.id, att.stripe_intent_id, reason))
        else:
            att.status = "canceled"
            att.last_error = reason
        att.updated_at = _naive_now()
        n += 1
    return n


# ---------------------------------------------------------------------------
# The single pending -> succeeded transition (confirm, confirm-simple, webhook)
# ---------------------------------------------------------------------------
_SETTLED_STATUSES = ("succeeded", "refunded", "partially_refunded")


def _settle_payment_success(payment, job, intent_id=None):
    """Apply the business effects of a successful charge exactly once.

    Returns {"transitioned": bool, "refund_required": bool}. Never overwrites
    a refunded status (a late success event after a refund is a no-op).
    Does not commit.
    """
    if payment.payment_status in _SETTLED_STATUSES:
        return {"transitioned": False, "refund_required": False}
    payment.payment_status = "succeeded"
    payment.updated_at = utcnow()
    recompute_payment_split(payment, job)

    intent_id = intent_id or payment.stripe_payment_intent_id
    now = _naive_now()
    for att in PaymentAttempt.query.filter_by(job_id=payment.job_id).all():
        if att.stripe_intent_id and att.stripe_intent_id == intent_id:
            att.status = "succeeded"
            att.updated_at = now
        elif att.status in ATTEMPT_OPEN:
            # A second live intent after success is a double-charge waiting to happen.
            if att.stripe_intent_id and not _cancel_intent(att.stripe_intent_id):
                att.status = "cancel_failed"
                att.last_error = "still live after another attempt succeeded"
            else:
                att.status = "superseded"
            att.updated_at = now

    # Count a promo redemption once, only on the pending->succeeded transition.
    if job and job.promo_code_id:
        promo = db.session.get(PromoCode, job.promo_code_id)
        if promo:
            promo.use_count = (promo.use_count or 0) + 1

    refund_required = False
    if job:
        if job.status in ("cancelled", "canceled"):
            # Money arrived for a dead job: keep the truth (succeeded) and
            # schedule the compensating refund — never work it, never keep it.
            refund_required = True
        elif job.status == "pending":
            job.status = "confirmed"
            job.updated_at = utcnow()
    return {"transitioned": True, "refund_required": refund_required}


def _after_settle(job, settle):
    """Post-commit follow-up of _settle_payment_success."""
    if settle.get("refund_required") and job is not None:
        try:
            refund_job(job, reason="paid_after_cancellation", actor="system")
        except Exception:
            logger.exception("automatic refund for cancelled job %s failed", job.id)
        return
    # Money is captured: real work is now owed to somebody. Announce it, so a
    # paid job can never sit unnoticed the way AFB22IMO did for 18 days.
    if job is not None and settle.get("transitioned"):
        try:
            from booking_alerts import notify_booking
            payment = Payment.query.filter_by(job_id=job.id).first()
            notify_booking(job, "paid", payment)
        except Exception:
            logger.exception("paid-booking announcement failed for job %s", job.id)


# ---------------------------------------------------------------------------
# Refunds (audit F14): a ledger, not a label
# ---------------------------------------------------------------------------
def _apply_refund_amount(payment, cumulative_refunded):
    payment.refunded_amount = round(max(payment.refunded_amount or 0.0, cumulative_refunded), 2)
    charged = round(payment.amount or 0.0, 2)
    if charged > 0 and payment.refunded_amount + 0.005 >= charged:
        payment.payment_status = "refunded"
    elif payment.refunded_amount > 0:
        payment.payment_status = "partially_refunded"
    payment.updated_at = utcnow()


def _flag_payout_reversals(job_id, why):
    """A customer refund does NOT reverse a Connect transfer automatically —
    flag the obligation for a human decision and alert (audit F14)."""
    flagged = []
    for p in Payout.query.filter_by(job_id=job_id).all():
        if p.status == "transferred" and not p.reversal_required:
            p.reversal_required = True
            p.updated_at = _naive_now()
            flagged.append(p)
    if flagged:
        _alert("Payout reversal decision needed",
               "Job {}: {}. {} transferred payout(s) flagged reversal_required — decide whether the "
               "hauler/fleet keeps it (work done?) and reverse in Stripe manually if not: {}"
               .format(job_id, why, len(flagged),
                       ", ".join("{} {} ${:.2f}".format(p.recipient_type, p.stripe_transfer_id or "-",
                                                         p.amount_cents / 100.0) for p in flagged)))
    return len(flagged)


def refund_job(job, amount=None, reason="", actor=None):
    """THE refund helper. Refund `amount` dollars (default: everything not yet
    refunded) of the job's succeeded charge, record it in the refunds ledger,
    keep Payment.refunded_amount / payment_status honest, and flag transferred
    payouts for a reversal decision. Idempotent per (payment, reason, amount)
    while a refund with that shape is pending/succeeded. Commits.

    Returns {"ok", "status", "amount", "refund_id", "stripe_refund_id",
             "payment_status", "message"}.
    """
    payment = job.payment if job is not None else None
    if payment is None:
        return {"ok": False, "status": "not_refundable", "amount": 0.0, "message": "No payment record"}
    if payment.payment_status == "refunded":
        return {"ok": False, "status": "nothing_to_refund", "amount": 0.0,
                "payment_status": "refunded", "message": "Already fully refunded"}
    if payment.payment_status not in ("succeeded", "partially_refunded", "disputed"):
        return {"ok": False, "status": "not_refundable", "amount": 0.0,
                "message": "Payment is {}, nothing to refund".format(payment.payment_status)}
    charged = round(payment.amount or 0.0, 2)
    remaining = round(charged - (payment.refunded_amount or 0.0), 2)
    amount = remaining if amount is None else round(min(float(amount), remaining), 2)
    if amount <= 0:
        return {"ok": False, "status": "nothing_to_refund", "amount": 0.0,
                "payment_status": payment.payment_status, "message": "Already fully refunded"}

    reason = (reason or "refund")[:200]
    existing = (Refund.query.filter_by(payment_id=payment.id, reason=reason)
                .filter(Refund.status.in_(("pending", "succeeded")))
                .filter(Refund.amount == amount).first())
    if existing:
        return {"ok": existing.status == "succeeded", "status": existing.status, "amount": existing.amount,
                "refund_id": existing.id, "stripe_refund_id": existing.stripe_refund_id,
                "payment_status": payment.payment_status, "message": "Refund already recorded"}

    row = Refund(id=generate_uuid(), payment_id=payment.id, amount=amount, reason=reason, status="pending")
    db.session.add(row)
    db.session.flush()
    intent_id = payment.stripe_payment_intent_id or ""

    if _money_unavailable():
        row.status = "failed"
        row.reason = "{} | payments unavailable (no STRIPE_SECRET_KEY in production)".format(reason)
        db.session.commit()
        logger.error("refund_job: payments unavailable — refund %s for job %s NOT issued", row.id, job.id)
        _alert("Refund NOT issued: payments unavailable",
               "Job {} refund ${:.2f} ({}) could not be sent: STRIPE_SECRET_KEY unset.".format(job.id, amount, reason))
        return {"ok": False, "status": "unavailable", "amount": amount, "refund_id": row.id,
                "payment_status": payment.payment_status, "message": "payments unavailable"}

    if not _stripe_key() or _is_dev_intent(intent_id):
        row.status = "succeeded"                         # dev: no real charge existed
    else:
        try:
            sr = _get_stripe().Refund.create(
                payment_intent=intent_id,
                amount=int(round(amount * 100)),
                reason="requested_by_customer",
                metadata={"job_id": job.id, "refund_id": row.id, "why": reason},
                idempotency_key="refund_{}_{}".format(job.id, row.id),
            )
            row.stripe_refund_id = getattr(sr, "id", None)
            row.status = "succeeded"
        except Exception as e:
            row.status = "failed"
            row.reason = "{} | stripe_error: {}".format(reason, str(e)[:200])
            db.session.commit()
            logger.error("refund_job: Stripe refund failed for job %s ($%.2f): %s", job.id, amount, e)
            _alert("Refund FAILED", "Job {} refund ${:.2f} ({}) failed in Stripe: {} — issue manually."
                   .format(job.id, amount, reason, str(e)[:200]))
            return {"ok": False, "status": "failed", "amount": amount, "refund_id": row.id,
                    "payment_status": payment.payment_status, "message": str(e)[:200]}

    _apply_refund_amount(payment, (payment.refunded_amount or 0.0) + amount)
    _flag_payout_reversals(job.id, "refund ${:.2f} ({}) by {}".format(amount, reason, actor or "system"))
    if job.customer_id:
        db.session.add(Notification(
            id=generate_uuid(), user_id=job.customer_id, type="payment", title="Refund Processed",
            body="A refund of ${:.2f} has been issued.".format(amount),
            data={"job_id": job.id, "amount": amount, "refund_id": row.id}))
    db.session.commit()
    logger.info("refund_job: $%.2f refunded for job %s (%s) -> %s", amount, job.id, reason, payment.payment_status)
    return {"ok": True, "status": "succeeded", "amount": amount, "refund_id": row.id,
            "stripe_refund_id": row.stripe_refund_id, "payment_status": payment.payment_status,
            "message": "Refund issued"}


# ---------------------------------------------------------------------------
# Assignment / cancellation hooks (audit F13 / F14) without touching the
# dispatcher: an ORM flush listener re-snapshots the split when the final
# operator/driver becomes known, and closes open attempts on cancellation.
# The Core-UPDATE accept path (routes/drivers.py) bypasses ORM events; that
# case is caught by attempt_payout's operator_id check before money moves.
# ---------------------------------------------------------------------------
def sync_split_for_job(job, payment=None):
    """Recompute the split if assignment moved since it was computed. No commit."""
    payment = payment or (job.payment if job else None)
    if not job or not payment or payment.payment_status != "succeeded":
        return False
    if payment.payout_status in ("paid", "paid_manual"):
        return False
    if (payment.split_operator_id or None) == (job.operator_id or None) and (payment.driver_payout_amount or 0) > 0:
        return False
    recompute_payment_split(payment, job)
    return True


@sa_event.listens_for(db.session, "before_flush")
def _payments_before_flush(session, flush_context, instances):
    for obj in list(session.dirty):
        if not isinstance(obj, Job):
            continue
        try:
            if get_history(obj, "operator_id").has_changes() or get_history(obj, "driver_id").has_changes():
                payment = session.query(Payment).filter_by(job_id=obj.id).first()
                if payment is not None:
                    sync_split_for_job(obj, payment)
            st = get_history(obj, "status")
            if st.has_changes() and obj.status in ("cancelled", "canceled"):
                cancel_open_attempts(obj, reason="job cancelled")
        except Exception:
            logger.exception("payments flush hook failed for job %s", getattr(obj, "id", "?"))


@payments_bp.route("/create-intent", methods=["POST"])
@limiter.limit("10 per minute")
@require_auth
def create_payment_intent(user_id):
    """
    Create a Stripe PaymentIntent for a job (authenticated owner).
    Body JSON: job_id (str), submission_key (str, uuid per booking attempt),
               tip_amount (float, optional), promo_code (optional)

    Idempotent: the same submission_key returns the same intent; a new
    submission_key supersedes (and cancels) the previous open attempt.
    """
    data = request.get_json() or {}
    job_id = data.get("job_id")
    tip_amount = float(data.get("tip_amount", 0))
    submission_key = data.get("submission_key") or data.get("submissionKey")

    if tip_amount < 0:
        return jsonify({"error": "tip_amount cannot be negative"}), 400
    if not job_id:
        return jsonify({"error": "job_id is required"}), 400

    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    if job.customer_id != user_id:
        return jsonify({"error": "Not authorised for this job"}), 403
    if job.payment and job.payment.payment_status in _SETTLED_STATUSES:
        return jsonify({"error": "Job is already paid"}), 409

    # --- Promo code (server-authoritative: re-validate here; never trust a
    # client-supplied discount). A code shown in the funnel must actually
    # reduce the charge, or the discount is cosmetic and the customer overpays.
    discount = float(job.discount_amount or 0.0)
    promo_message = None
    promo_code = (data.get("promo_code") or data.get("promoCode") or "").strip()
    if promo_code and discount <= 0:
        from routes.promos import validate_promo_code
        promo, disc, err = validate_promo_code(promo_code, job.total_price)
        if err:
            # Don't block payment — just charge full price and tell the client.
            promo_message = err
        else:
            discount = disc
            job.promo_code_id = promo.id
            job.discount_amount = discount
            promo_message = "Promo {} applied: -${:.2f}".format(promo.code, discount)
            db.session.commit()

    discounted_base = max(0.0, round(job.total_price - discount, 2))
    amount = round(discounted_base + tip_amount, 2)
    # Platform take applies to the job amount only — tips and dump fees pass
    # through to the driver 100%. (Previously the split was computed on
    # amount incl. tip, so the platform skimmed 28% of every tip.)
    disposal_fee = min(max(0.0, float(getattr(job, "disposal_fee", 0.0) or 0.0)), discounted_base)
    split_base = round(discounted_base - disposal_fee, 2)
    commission = round(split_base * PLATFORM_COMMISSION, 2)
    service_fee = round(split_base * SERVICE_FEE_RATE, 2)
    driver_payout = max(0, round(amount - commission - service_fee, 2))

    result, err = create_attempt_for_job(
        job_id, submission_key, amount, actor="owner", user_id=user_id,
        metadata={"user_id": user_id},
        payment_fields={"service_fee": service_fee, "commission": commission, "disposal_fee": disposal_fee,
                        "driver_payout_amount": driver_payout, "tip_amount": tip_amount},
    )
    if err:
        return err

    return jsonify({
        "success": True,
        "client_secret": result["client_secret"],
        "payment_intent_id": result["intent_id"],
        "attempt_id": result["attempt"].id,
        "reused": result["reused"],
        "amount": amount,
        "discount": discount,
        "promo_message": promo_message,
        "payment": result["payment"].to_dict(),
    }), 201


def _locate_payment_for_intent(intent_id, hint_job_id=None, stripe_obj=None):
    """Find the Payment an intent belongs to, adopting the intent when the
    job was created after it (audit F05): by intent id, then by attempt, then
    by the intent's metadata.job_id / booking_id, then by the client's hint.
    Returns (payment, job) or (None, None)."""
    payment = Payment.query.filter_by(stripe_payment_intent_id=intent_id).first()
    if payment:
        return payment, db.session.get(Job, payment.job_id)
    job_id = None
    att = PaymentAttempt.query.filter_by(stripe_intent_id=intent_id).first()
    if att:
        job_id = att.job_id
    if not job_id and stripe_obj is not None:
        meta = stripe_obj.get("metadata") if hasattr(stripe_obj, "get") else getattr(stripe_obj, "metadata", None)
        meta = meta or {}
        job_id = meta.get("job_id") or meta.get("booking_id")
    if not job_id and hint_job_id:
        job_id = hint_job_id
    if not job_id:
        return None, None
    job = db.session.get(Job, job_id)
    if not job:
        return None, None
    payment = Payment.query.filter_by(job_id=job.id).first()
    if not payment:
        payment = Payment(id=generate_uuid(), job_id=job.id, amount=float(job.total_price or 0),
                          service_fee=float(job.service_fee or 0), payment_status="pending")
        db.session.add(payment)
        db.session.flush()
    if payment.payment_status not in _SETTLED_STATUSES and payment.stripe_payment_intent_id != intent_id:
        clash = Payment.query.filter_by(stripe_payment_intent_id=intent_id).first()
        if clash is None:
            payment.stripe_payment_intent_id = intent_id
            db.session.flush()
    return payment, job


def _verify_intent_succeeded(intent_id):
    """Ask Stripe whether the intent really succeeded. Returns
    (intent_obj_or_None, error_response_or_None)."""
    if _is_dev_intent(intent_id):
        if is_production():
            return None, (jsonify({"error": "Development payment ids are not accepted in production"}), 400)
        return None, None
    if not _stripe_key():
        if is_production():
            return None, _payments_unavailable()
        return None, None
    try:
        intent_obj = _get_stripe().PaymentIntent.retrieve(intent_id)
    except Exception as e:
        return None, (jsonify({"error": "Failed to verify payment with Stripe: {}".format(str(e))}), 502)
    if intent_obj.status != "succeeded":
        return None, (jsonify({"error": "Payment intent has not succeeded (status: {})".format(intent_obj.status)}), 400)
    return intent_obj, None


def _post_settle_side_effects(payment, job, settle, receipt=True):
    """Auto-dispatch, recovery-SMS cancel, receipt email — after commit."""
    _after_settle(job, settle)
    if job and settle.get("transitioned"):
        try:
            from socket_events import broadcast_job_status
            broadcast_job_status(job.id, job.status)
        except Exception:
            pass
    if job and job.status == "confirmed" and not job.driver_id:
        try:
            from dispatcher import auto_assign_job_async
            auto_assign_job_async(job.id, current_app._get_current_object())
        except Exception:
            logger.exception("Failed to trigger auto-dispatch for job %s", job.id)
    try:
        from sms_service import cancel_abandoned_booking_sms
        cancel_abandoned_booking_sms(payment.job_id)
    except Exception:
        pass
    if receipt and job and settle.get("transitioned"):
        try:
            customer = db.session.get(User, job.customer_id)
            if customer and customer.email:
                from notifications import send_payment_receipt_email
                send_payment_receipt_email(customer.email, customer.name, job.id,
                                           job.address, payment.amount)
        except Exception:
            pass  # Notifications must never block the main flow


@payments_bp.route("/confirm", methods=["POST"])
@require_auth
def confirm_payment(user_id):
    """
    Mark a payment as succeeded (owner). Body JSON: payment_intent_id (str),
    job_id (str, optional hint when the job was created after the intent).
    """
    data = request.get_json() or {}
    intent_id = data.get("payment_intent_id")
    if not intent_id:
        return jsonify({"error": "payment_intent_id is required"}), 400

    unavailable = _payments_unavailable()
    if unavailable:
        return unavailable

    # Verify against Stripe that the intent actually succeeded. Without this,
    # any client could mark its own payment "succeeded" with no money moving
    # — and the platform would still pay the driver real dollars.
    intent_obj, err = _verify_intent_succeeded(intent_id)
    if err:
        return err

    payment, job = _locate_payment_for_intent(
        intent_id, hint_job_id=data.get("job_id") or data.get("bookingId") or data.get("booking_id"),
        stripe_obj=intent_obj)
    if not payment:
        return jsonify({"error": "Payment not found"}), 404

    # Ownership: only the customer who owns the job may confirm its payment.
    if job and job.customer_id != user_id:
        return jsonify({"error": "Not authorised for this payment"}), 403

    settle = _settle_payment_success(payment, job, intent_id=intent_id)

    if settle["transitioned"] and job and job.driver_id:
        contractor = db.session.get(Contractor, job.driver_id)
        if contractor:
            db.session.add(Notification(
                id=generate_uuid(), user_id=contractor.user_id, type="payment",
                title="Payment Received",
                body="Payment of ${:.2f} confirmed for job.".format(payment.amount),
                data={"job_id": job.id, "amount": payment.amount}))

    db.session.commit()
    _post_settle_side_effects(payment, job, settle)
    return jsonify({"success": True, "payment": payment.to_dict()}), 200


def _upsert_payout(job, payment, recipient_type, amount, contractor_id=None, operator_id=None,
                   idempotency_key=None):
    """One Payout row per (job, recipient). Never downgrades a transferred row."""
    row = Payout.query.filter_by(job_id=job.id, recipient_type=recipient_type).first()
    if row is None:
        row = Payout(id=generate_uuid(), job_id=job.id, payment_id=payment.id,
                     recipient_type=recipient_type, status="pending")
        db.session.add(row)
    if row.status in ("transferred", "paid_manual"):
        return row
    row.contractor_id = contractor_id
    row.operator_id = operator_id
    row.amount_cents = int(round(amount * 100))
    row.idempotency_key = idempotency_key or row.idempotency_key
    row.updated_at = _naive_now()
    return row


def _transfer_leg(row, destination, job_id):
    """Move one Payout row's money to a Connect account. Returns
    (status, message) with status in transferred | pending_connect | failed."""
    if row.status in ("transferred", "paid_manual"):
        return row.status, "already settled"
    if row.amount_cents <= 0:
        row.status = "transferred"
        row.method = "none"
        return "transferred", "nothing owed"
    if not destination:
        row.status = "pending_connect"
        return "pending_connect", "no payout account"
    if not _stripe_key():
        # dev only (production is fail-closed before we get here)
        row.status = "transferred"
        row.method = "dev"
        return "transferred", "dev transfer"
    try:
        tr = _get_stripe().Transfer.create(
            amount=row.amount_cents, currency=row.currency or "usd", destination=destination,
            metadata={"job_id": job_id, "recipient": row.recipient_type, "payout_id": row.id},
            idempotency_key=row.idempotency_key,
        )
        row.stripe_transfer_id = getattr(tr, "id", None)
        row.status = "transferred"
        row.method = "transfer"
        row.last_error = None
        return "transferred", "transfer sent"
    except Exception as e:
        row.status = "failed"
        row.last_error = str(e)[:500]
        logger.exception("Stripe transfer failed for job %s (%s)", job_id, row.recipient_type)
        return "failed", "Stripe payout error: {}".format(e)


def attempt_payout(job_id):
    """Core Stripe Connect payout for a completed job. Idempotent, never raises.

    Shared by the manual ``/payout/<job_id>`` route and the auto-payout hook
    that fires when a driver marks a job completed. Returns a dict:
        {"ok": bool, "status": str, "message": str, "amount": float}
      status one of: paid | already_paid | not_payable | no_connect | failed |
                     unavailable | error

    ``no_connect`` (contractor hasn't finished Stripe onboarding) is NOT a hard
    failure — the payout is marked ``pending_connect`` so a later sweep can
    retry once they connect, and the job completion is never blocked.

    Audit F13: every recipient gets its own Payout row (driver + fleet
    operator + referral elsewhere) with the Stripe transfer id persisted; the
    fleet operator is transferred its share too (idempotency key
    ``payout_<job>_operator``; the driver keeps the historical ``payout_<job>``).
    Payment.payout_status mirrors the DRIVER leg for existing readers
    (sameday_pay.owed_rows, manager UI, driver earnings).
    """
    try:
        job = db.session.get(Job, job_id)
        if not job:
            return {"ok": False, "status": "not_payable",
                    "message": "Job not found", "amount": 0.0}

        # Never pay before the work is done — payment success alone is not
        # payout eligibility. (Completion is what flips this gate.)
        if job.status != "completed":
            return {"ok": False, "status": "not_payable",
                    "message": "Job is not completed", "amount": 0.0}

        # Row-lock the payment so a concurrent completion hook / scheduler
        # sweep / manual trigger can't both read payout_status=="pending" and
        # double-transfer. (No-op on SQLite dev; real lock on Postgres.)
        payment = (Payment.query.filter_by(job_id=job_id)
                   .with_for_update().first())
        if not payment:
            return {"ok": False, "status": "not_payable",
                    "message": "No payment record", "amount": 0.0}
        if payment.payment_status != "succeeded":
            return {"ok": False, "status": "not_payable",
                    "message": "Payment has not succeeded", "amount": 0.0}
        if payment.payout_status in ("paid", "paid_manual"):
            return {"ok": True, "status": "already_paid",
                    "message": "Payout already completed",
                    "amount": payment.driver_payout_amount or 0.0}
        if not job.driver_id:
            return {"ok": False, "status": "not_payable",
                    "message": "No driver assigned", "amount": 0.0}

        contractor = db.session.get(Contractor, job.driver_id)
        if not contractor:
            return {"ok": False, "status": "not_payable",
                    "message": "Contractor not found", "amount": 0.0}

        # Snapshot the commercial split against the FINAL assignment: if no
        # confirmation path computed it, or the fleet operator changed since
        # (delegation after payment), recompute before any money moves.
        if (((payment.driver_payout_amount or 0.0) <= 0 and (payment.amount or 0.0) > 0)
                or (payment.split_operator_id or None) != (job.operator_id or None)):
            recompute_payment_split(payment, job)
            db.session.commit()
            logger.warning(
                "attempt_payout recomputed split for job %s -> driver $%.2f operator $%.2f",
                job_id, payment.driver_payout_amount or 0.0, payment.operator_payout_amount or 0.0,
            )

        # A tip is the customer's money for the hauler, 100% pass-through. It
        # moves as its OWN transfer with its own retry: a tip that arrives after
        # the base payout, or fails while the base succeeds, must never block or
        # be blocked by the base leg. driver_payout_amount still includes it
        # (the earnings ledger and the owed list read that), so the base leg
        # carries everything except the tip.
        tip_amount = round(float(payment.tip_amount or 0.0), 2)
        amount = max(0.0, round((payment.driver_payout_amount or 0.0) - tip_amount, 2))
        op_amount = payment.operator_payout_amount or 0.0

        # Fail closed: production without a Stripe key must never mark paid.
        if _money_unavailable():
            logger.error("attempt_payout: payments unavailable (no STRIPE_SECRET_KEY in production); "
                         "job %s left pending", job_id)
            return {"ok": False, "status": "unavailable",
                    "message": "payments unavailable", "amount": amount}

        driver_row = _upsert_payout(job, payment, "driver", amount, contractor_id=contractor.id,
                                    idempotency_key="payout_{}".format(job_id))

        # --- Fleet operator leg (independent of the driver leg) ---
        op_status = None
        if op_amount > 0 and job.operator_id:
            operator = db.session.get(Contractor, job.operator_id)
            op_row = _upsert_payout(job, payment, "operator", op_amount,
                                    contractor_id=operator.id if operator else None,
                                    operator_id=job.operator_id,
                                    idempotency_key="payout_{}_operator".format(job_id))
            op_status, _ = _transfer_leg(op_row, getattr(operator, "stripe_connect_id", None), job_id)
            if op_status == "transferred" and op_row.method == "transfer" and operator:
                db.session.add(Notification(
                    id=generate_uuid(), user_id=operator.user_id, type="payment",
                    title="Fleet Commission Sent",
                    body="${:.2f} fleet commission has been sent to your account.".format(op_amount),
                    data={"job_id": job_id, "amount": op_amount}))
            elif op_status == "failed":
                _alert("Fleet operator transfer failed",
                       "Job {} operator {} ${:.2f}: {}".format(job_id, job.operator_id, op_amount,
                                                                op_row.last_error))

        # --- Driver leg ---
        # Contractor hasn't connected a payout account yet — defer, don't fail.
        if not contractor.stripe_connect_id:
            driver_row.status = "pending_connect"
            payment.payout_status = "pending_connect"
            payment.updated_at = utcnow()
            db.session.commit()
            logger.info(
                "Payout for job %s deferred: contractor %s has no Stripe Connect account",
                job_id, contractor.id,
            )
            return {"ok": False, "status": "no_connect",
                    "message": "Contractor has not connected a payout account",
                    "amount": amount, "operator": op_status}

        status, message = _transfer_leg(driver_row, contractor.stripe_connect_id, job_id)

        # --- Tip leg (independent; never changes the base outcome) ---
        tip_status = None
        if tip_amount > 0:
            tip_row = _upsert_payout(job, payment, "tip", tip_amount, contractor_id=contractor.id,
                                     idempotency_key="tip_{}".format(job_id))
            tip_status, _tip_msg = _transfer_leg(tip_row, contractor.stripe_connect_id, job_id)
            if tip_status == "failed":
                _alert("Tip transfer failed (base payout unaffected)",
                       "Job {} tip ${:.2f} to contractor {}: {}. The payout sweep retries it."
                       .format(job_id, tip_amount, contractor.id, tip_row.last_error))
        if status == "failed":
            payment.payout_status = "failed"
            payment.updated_at = utcnow()
            db.session.commit()
            return {"ok": False, "status": "failed", "message": message,
                    "amount": amount, "operator": op_status}

        payment.payout_status = "paid"
        payment.updated_at = utcnow()
        db.session.add(Notification(
            id=generate_uuid(),
            user_id=contractor.user_id,
            type="payment",
            title="Payout Sent",
            body="${:.2f} has been sent to your account.".format(amount),
            data={"job_id": job_id, "amount": amount},
        ))
        db.session.commit()
        logger.info("Payout of $%.2f sent for job %s -> contractor %s (transfer %s)",
                    amount, job_id, contractor.id, driver_row.stripe_transfer_id)
        # Same-day pay: push it from the connected account to the hauler's
        # debit card right now (falls back to standard + a text). Never raises.
        try:
            from sameday_pay import instant_after_transfer
            instant = instant_after_transfer(payment, contractor, amount)
        except Exception:
            logger.exception("instant payout step crashed for job %s", job_id)
            instant = {"method": "standard", "reason": "instant step crashed"}
        return {"ok": True, "status": "paid",
                "message": "Payout sent", "amount": amount, "instant": instant,
                "transfer_id": driver_row.stripe_transfer_id, "operator": op_status}
    except Exception:
        logger.exception("attempt_payout crashed for job %s", job_id)
        try:
            db.session.rollback()
        except Exception:
            pass
        return {"ok": False, "status": "error",
                "message": "Internal payout error", "amount": 0.0}


def pay_referral_bonus(referral):
    """Auto-pay the contractor referral bonus to BOTH haulers via Stripe Connect.

    Called from the job-completion hook when a referred hauler finishes their
    first job. Idempotent (Stripe idempotency_key per party + a status guard),
    never raises, and does NOT commit — the caller's transaction persists it.

    - Each party with a connected payout account is paid a Transfer of
      reward_amount and gets a "paid" notification.
    - A party without a Connect account (or if STRIPE_SECRET_KEY is unset, or
      REFERRAL_AUTO_PAYOUT=false) is left as an earned credit + notification;
      re-running this is safe and will pay them once they're connected.
    - status flips to 'rewarded' only once every party has actually been paid.
    """
    try:
        if referral is None or getattr(referral, "referral_type", None) != "contractor":
            return
        if referral.status == "rewarded":
            return
        bonus = float(referral.reward_amount or 0.0)
        if bonus <= 0:
            return

        auto = os.environ.get("REFERRAL_AUTO_PAYOUT", "true").lower() == "true"
        stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")
        can_pay = bool(auto and stripe_key)
        stripe = _get_stripe() if can_pay else None
        cents = int(round(bonus * 100))

        def _notify(uid, title, body):
            if not uid:
                return
            db.session.add(Notification(
                id=generate_uuid(), user_id=uid, type="payment",
                title=title, body=body,
                data={"referral_id": referral.id, "amount": bonus},
            ))

        def _ledger(uid, role, status, transfer_id=None):
            """Upsert the one (referral, role) ledger row. Never downgrades a
            row already marked paid."""
            row = ReferralPayout.query.filter_by(
                referral_id=referral.id, role=role).first()
            if row and row.status == "paid":
                return row
            if not row:
                row = ReferralPayout(
                    id=generate_uuid(), referral_id=referral.id, role=role)
                db.session.add(row)
            row.user_id = uid
            row.amount = bonus
            row.status = status
            if transfer_id:
                row.stripe_transfer_id = transfer_id
            return row

        paid_all = True
        for role, uid in (("referrer", referral.referrer_id),
                          ("referee", referral.referee_id)):
            if not uid:
                continue
            # Already paid this party (idempotent re-run) — skip Stripe entirely.
            done = ReferralPayout.query.filter_by(
                referral_id=referral.id, role=role, status="paid").first()
            if done:
                continue
            contractor = Contractor.query.filter_by(user_id=uid).first()
            connect = getattr(contractor, "stripe_connect_id", None) if contractor else None
            if can_pay and connect:
                try:
                    tr = stripe.Transfer.create(
                        amount=cents,
                        currency="usd",
                        destination=connect,
                        metadata={"referral_id": referral.id, "role": role,
                                  "kind": "referral_bonus"},
                        idempotency_key="refbonus_{}_{}".format(referral.id, role),
                    )
                    _ledger(uid, role, "paid", getattr(tr, "id", None))
                    _notify(uid, "Referral Bonus Paid",
                            "${:.2f} referral bonus has been sent to your account.".format(bonus))
                    logger.info("Referral bonus $%.2f paid to %s (%s) ref=%s",
                                bonus, uid, role, referral.id)
                except Exception:
                    paid_all = False
                    _ledger(uid, role, "failed")
                    logger.exception("Referral bonus transfer failed ref=%s role=%s",
                                     referral.id, role)
                    _notify(uid, "Referral Bonus Earned",
                            "Your ${:.2f} referral bonus is earned — we'll send it shortly.".format(bonus))
            else:
                paid_all = False
                _ledger(uid, role, "deferred")
                _notify(uid, "Referral Bonus Earned",
                        "Your ${:.2f} referral bonus is earned — we'll send it once your payout account is ready.".format(bonus))

        if paid_all:
            referral.status = "rewarded"
    except Exception:
        logger.exception("pay_referral_bonus crashed for referral %s",
                         getattr(referral, "id", "?"))


@payments_bp.route("/payout/<job_id>", methods=["POST"])
@require_auth
def trigger_payout(user_id, job_id):
    """Trigger Stripe Connect payout to the contractor for a completed job.

    Only an admin or the job's assigned driver may trigger this — any other
    authenticated account gets 403 (payouts move real money).
    """
    caller = db.session.get(User, user_id)
    is_admin = bool(caller and caller.role == "admin")
    if not is_admin:
        job_row = db.session.get(Job, job_id)
        if not job_row or not job_row.driver_id:
            return jsonify({"error": "Not authorised"}), 403
        contractor = Contractor.query.filter_by(user_id=user_id).first()
        if not contractor or contractor.id != job_row.driver_id:
            return jsonify({"error": "Not authorised"}), 403

    result = attempt_payout(job_id)
    if result["ok"]:
        job = db.session.get(Job, job_id)
        return jsonify({
            "success": True,
            "status": result["status"],
            "payment": job.payment.to_dict() if job and job.payment else None,
        }), 200

    code = {
        "no_connect": 409,
        "failed": 502,
        "unavailable": 503,
        "error": 500,
    }.get(result["status"], 409)
    return jsonify({"error": result["message"], "status": result["status"]}), code


@payments_bp.route("/payout/eligibility", methods=["GET"])
@limiter.limit("5 per minute")
@require_auth
def get_payout_eligibility(user_id):
    """Check balance available for instant payout on the contractor's Connect account."""
    contractor = Contractor.query.filter_by(user_id=user_id).first()
    if not contractor:
        return jsonify({"error": "Contractor not found"}), 404
    
    if not contractor.stripe_connect_id:
        return jsonify({
            "eligible": False, 
            "reason": "no_connect_account",
            "available_amount": 0,
            "currency": "usd"
        })

    unavailable = _payments_unavailable()
    if unavailable:
        return unavailable
    stripe = _get_stripe()
    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")

    if contractor.stripe_connect_id.startswith("acct_dev_") and is_production():
        # A dev mock account id in production is a stale artifact, not a payout destination.
        return jsonify({"eligible": False, "reason": "no_connect_account",
                        "available_amount": 0, "currency": "usd"})
    if not stripe_key or contractor.stripe_connect_id.startswith("acct_dev_"):
        # Dev/Mock mode (never reached in production: fail-closed above)
        return jsonify({
            "eligible": True,
            "available_amount": 125.50,
            "currency": "usd",
            "is_mock": True
        })

    try:
        # Fetch balance from the CONNECT account
        balance = stripe.Balance.retrieve(stripe_account=contractor.stripe_connect_id)
        
        # Instant payout pulls from 'available' balance
        available = next((b.amount for b in balance.available if b.currency == 'usd'), 0)
        
        return jsonify({
            "eligible": available >= 500, # Min $5 to payout
            "available_amount": round(available / 100, 2),
            "currency": "usd"
        })
    except Exception as e:
        logger.exception("Failed to fetch Stripe balance for contractor %s", contractor.id)
        return jsonify({"error": "Payment processing failed. Please try again."}), 502


@payments_bp.route("/payout/instant", methods=["POST"])
@limiter.limit("5 per minute")
@require_auth
def trigger_instant_payout(user_id):
    """Trigger an instant payout from the Connect account to the contractor's external account."""
    contractor = Contractor.query.filter_by(user_id=user_id).first()
    if not contractor:
        return jsonify({"error": "Contractor not found"}), 404

    if not contractor.stripe_connect_id:
        return jsonify({"error": "No Stripe Connect account found"}), 400

    unavailable = _payments_unavailable()
    if unavailable:
        return unavailable
    stripe = _get_stripe()
    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")

    if contractor.stripe_connect_id.startswith("acct_dev_") and is_production():
        logger.error("instant payout refused: contractor %s has a dev mock Connect id in production",
                     contractor.id)
        return jsonify({"error": "payments unavailable", "code": "payments_unavailable"}), 503
    if not stripe_key or contractor.stripe_connect_id.startswith("acct_dev_"):
        # Dev/Mock mode (never reached in production: fail-closed above)
        return jsonify({"success": True, "payout_id": "po_mock_123", "is_mock": True})

    try:
        # 1. Get available balance
        balance = stripe.Balance.retrieve(stripe_account=contractor.stripe_connect_id)
        available = next((b.amount for b in balance.available if b.currency == 'usd'), 0)
        
        if available < 500:
            return jsonify({"error": "Insufficient balance for instant payout (Min $5.00)"}), 400

        MAX_INSTANT_PAYOUT = 500000  # $5,000
        if available > MAX_INSTANT_PAYOUT:
            available = MAX_INSTANT_PAYOUT

        # 2. Trigger Payout
        payout = stripe.Payout.create(
            amount=available,
            currency="usd",
            method="instant",
            stripe_account=contractor.stripe_connect_id,
            idempotency_key=f"payout_{contractor.id}_{int(time.time() // 60)}"
        )
        
        logger.info("Instant payout triggered for contractor %s: %s", contractor.id, payout.id)
        
        return jsonify({
            "success": True, 
            "payout_id": payout.id,
            "amount": round(available / 100, 2)
        })
    except Exception as e:
        logger.exception("Stripe instant payout failed for contractor %s", contractor.id)
        return jsonify({"error": "Payment processing failed. Please try again."}), 502


@payments_bp.route("/create-intent-simple", methods=["POST"])
@limiter.limit("10 per minute")
def create_simple_payment_intent():
    """
    Create a Stripe PaymentIntent for an existing booking (customer portal /
    iOS app). Public route, but every call must prove it may pay for THIS
    booking: the owner's JWT, or the ``checkout_token`` returned by
    POST /api/booking / POST /api/jobs.

    Body JSON: bookingId (str, required), submission_key (str, required —
               uuid generated once per booking by the client and persisted),
               checkout_token (str, unless Authorization JWT of the owner),
               amount (float, advisory — the server charges the job's total),
               customerEmail (str, optional), promoCode (str, optional)

    An unknown bookingId is a 404 — this route no longer creates standalone
    service payments (audit F06).
    """
    data = request.get_json() or {}
    booking_id = data.get("bookingId") or data.get("booking_id") or data.get("job_id")
    customer_email = data.get("customerEmail") or data.get("customer_email")
    submission_key = data.get("submission_key") or data.get("submissionKey")

    if not booking_id:
        return jsonify({"error": "bookingId is required", "code": "booking_required"}), 400
    try:
        amount = float(data.get("amount", 0) or 0)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid amount"}), 400

    job_obj = db.session.get(Job, booking_id)
    if not job_obj:
        return jsonify({"error": "Booking not found"}), 404

    actor, actor_user_id = _checkout_actor(job_obj, data)
    if actor is None:
        return jsonify({"error": "Not authorised to pay for this booking",
                        "code": "checkout_token_required"}), 403

    # A paid booking must never have its payment reset to pending / its intent
    # re-pointed — the job UUID is discoverable.
    existing_payment = Payment.query.filter_by(job_id=booking_id).first()
    if existing_payment and existing_payment.payment_status in _SETTLED_STATUSES:
        return jsonify({"error": "This booking is already paid", "code": "already_paid"}), 409

    discount = 0.0
    promo_message = None
    promo_code = (data.get("promoCode") or data.get("promo_code") or "").strip()

    # Server-authoritative charge: derive the amount from the Job's
    # server-computed total_price (+ any promo validated at booking) instead
    # of trusting the client-sent amount.
    base = float(job_obj.total_price or 0)
    if base <= 0:
        return jsonify({"error": "Booking has no price yet"}), 409
    # audit F09: booking already netted discount_amount into total_price —
    # subtracting it again here charged $150 on a $175 job.
    discount = 0.0
    # Apply a promo passed now only if one wasn't already applied at booking.
    if promo_code and not job_obj.promo_code_id:
        from routes.promos import validate_promo_code
        promo, disc, err = validate_promo_code(promo_code, base)
        if err:
            promo_message = err
        else:
            discount = disc
            job_obj.promo_code_id = promo.id
            job_obj.discount_amount = disc
            promo_message = "Promo {} applied: -${:.2f}".format(promo.code, disc)
            db.session.commit()
    server_amount = max(0.50, round(base - discount, 2))
    if amount and abs(server_amount - amount) > 0.01:
        logger.warning(
            "create-intent-simple amount override: client=%.2f server=%.2f job=%s",
            amount, server_amount, booking_id,
        )
    amount = server_amount
    if amount > 10000:
        return jsonify({"error": "amount exceeds maximum allowed ($10,000)"}), 400

    metadata = {"booking_id": booking_id}
    if customer_email:
        metadata["customer_email"] = customer_email

    result, err = create_attempt_for_job(
        booking_id, submission_key, amount, actor=actor, user_id=actor_user_id,
        metadata=metadata, receipt_email=customer_email,
    )
    if err:
        return err

    # --- Meta CAPI: server-side InitiateCheckout (mid-funnel signal, deduped
    # with the browser pixel via event_id checkout_<job_id>). No-op if
    # unconfigured; skipped on a reused attempt so a retry isn't a new signal.
    if not result["reused"]:
        try:
            from meta_capi import track_initiate_checkout
            track_initiate_checkout(
                job_id=booking_id,
                value=amount,
                currency="USD",
                email=customer_email,
                event_source_url="https://app.goumuve.com/book",
            )
        except Exception:
            logger.exception("Meta CAPI InitiateCheckout hook failed for %s", booking_id)

    return jsonify({
        "success": True,
        "clientSecret": result["client_secret"],
        "paymentIntentId": result["intent_id"],
        "attemptId": result["attempt"].id,
        "reused": result["reused"],
        "amount": amount,
        "discount": discount,
        "promo_message": promo_message,
    }), 201


@payments_bp.route("/confirm-simple", methods=["POST"])
@limiter.limit("10 per minute")
def confirm_simple_payment():
    """
    Confirm / mark a payment as succeeded (for customer portal / iOS app).
    Validates the PaymentIntent status against Stripe before marking as paid.
    Body JSON: paymentIntentId (str, required), bookingId (str, optional hint
               for an intent created before its job — audit F05)
    """
    data = request.get_json() or {}
    intent_id = data.get("paymentIntentId") or data.get("payment_intent_id")
    if not intent_id:
        return jsonify({"error": "paymentIntentId is required"}), 400

    unavailable = _payments_unavailable()
    if unavailable:
        return unavailable

    intent_obj, err = _verify_intent_succeeded(intent_id)
    if err:
        return err

    payment, job = _locate_payment_for_intent(
        intent_id, hint_job_id=data.get("bookingId") or data.get("booking_id") or data.get("job_id"),
        stripe_obj=intent_obj)
    if not payment:
        return jsonify({"error": "Payment not found"}), 404

    settle = _settle_payment_success(payment, job, intent_id=intent_id)
    db.session.commit()
    _post_settle_side_effects(payment, job, settle)

    return jsonify({
        "success": True,
        "payment": payment.to_dict(),
        "job": job.to_dict() if job else None,
    }), 200


@payments_bp.route("/earnings", methods=["GET"])
@require_auth
def get_earnings(user_id):
    """Return earnings summary for a contractor."""
    contractor = Contractor.query.filter_by(user_id=user_id).first()
    if not contractor:
        return jsonify({"error": "Contractor profile not found"}), 404

    now = _naive_now()  # created_at is stored naive UTC
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)

    all_payments = (
        Payment.query
        .join(Job, Payment.job_id == Job.id)
        .filter(Job.driver_id == contractor.id, Payment.payment_status == "succeeded")
        .all()
    )

    def _created(p):
        c = p.created_at
        return c.replace(tzinfo=None) if c is not None and c.tzinfo is not None else c

    total_earnings = sum((p.driver_payout_amount or 0.0) for p in all_payments)
    total_tips = sum((p.tip_amount or 0.0) for p in all_payments)
    earnings_30d = sum((p.driver_payout_amount or 0.0) for p in all_payments if _created(p) and _created(p) >= thirty_days_ago)
    earnings_7d = sum((p.driver_payout_amount or 0.0) for p in all_payments if _created(p) and _created(p) >= seven_days_ago)

    # Owed = anything not yet settled: pending, a failed transfer, or waiting
    # on Stripe onboarding (audit F13 — failed/pending_connect are still owed).
    pending_payout = sum(
        (p.driver_payout_amount or 0.0) for p in all_payments
        if p.payout_status in PAYOUT_OWED_STATUSES
    )

    return jsonify({
        "success": True,
        "earnings": {
            "total_earnings": round(total_earnings, 2),
            "total_tips": round(total_tips, 2),
            "earnings_30d": round(earnings_30d, 2),
            "earnings_7d": round(earnings_7d, 2),
            "pending_payout": round(pending_payout, 2),
            "total_jobs": contractor.total_jobs or 0,
        },
    }), 200


# ---------------------------------------------------------------------------
# Stripe Connect
# ---------------------------------------------------------------------------

@payments_bp.route("/connect/create-account", methods=["POST"])
@require_auth
def create_connect_account(user_id):
    """Create a Stripe Connect Express account for the authenticated driver."""
    contractor = Contractor.query.filter_by(user_id=user_id).first()
    if not contractor:
        return jsonify({"error": "Contractor profile not found"}), 404

    # Idempotent — return existing account if already created. Skip dev mock ids
    # ("acct_dev_…"), which aren't real connected accounts, so a real one is made.
    if contractor.stripe_connect_id and not contractor.stripe_connect_id.startswith("acct_dev_"):
        return jsonify({
            "success": True,
            "account_id": contractor.stripe_connect_id,
        }), 200

    unavailable = _payments_unavailable()
    if unavailable:
        return unavailable
    stripe = _get_stripe()
    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")
    account_id = None

    if stripe_key:
        try:
            account = stripe.Account.create(
                type="express",
                country="US",
                capabilities={
                    "card_payments": {"requested": True},
                    "transfers": {"requested": True},
                },
            )
            account_id = account.id
        except Exception as e:
            return jsonify({"error": "Stripe error: {}".format(str(e))}), 502
    else:
        # Dev mode — generate mock account ID
        account_id = "acct_dev_{}".format(generate_uuid()[:8])

    contractor.stripe_connect_id = account_id
    db.session.commit()

    return jsonify({
        "success": True,
        "account_id": account_id,
    }), 201


@payments_bp.route("/connect/account-link", methods=["POST"])
@require_auth
def create_account_link(user_id):
    """Generate a fresh Stripe Connect account onboarding link (expires in 5 minutes)."""
    contractor = Contractor.query.filter_by(user_id=user_id).first()
    if not contractor:
        return jsonify({"error": "Contractor profile not found"}), 404

    # Livemode Stripe rejects non-HTTPS redirect URLs, so the fallback must be
    # the real backend origin, not localhost.
    base_url = os.environ.get("APP_BASE_URL", "https://junkos-backend.onrender.com")
    refresh_url = "{}/api/payments/connect/refresh".format(base_url)
    return_url = "{}/api/payments/connect/return".format(base_url)

    stripe = _get_stripe()
    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")

    if stripe_key:
        def _fresh_account():
            """Create a real Express account + persist it."""
            acct = stripe.Account.create(
                type="express", country="US",
                capabilities={"card_payments": {"requested": True},
                              "transfers": {"requested": True}},
            )
            contractor.stripe_connect_id = acct.id
            db.session.commit()
            return acct.id

        def _make_link(aid):
            return stripe.AccountLink.create(
                account=aid, refresh_url=refresh_url, return_url=return_url,
                type="account_onboarding",
            )

        # Whole flow is guarded so a Stripe failure returns a readable 502, never
        # an opaque 500 (and never a half-set state that dead-ends the operator).
        try:
            # Heal a stale/mock id up front: a dev mock ("acct_dev_…") or an empty
            # id is never a real connected account, so make a real one first.
            acct_id = contractor.stripe_connect_id
            if not acct_id or acct_id.startswith("acct_dev_"):
                acct_id = _fresh_account()
            try:
                account_link = _make_link(acct_id)
            except Exception as e:
                # The stored account isn't a connected account of this platform
                # (different key / test↔live / deleted) — recreate once and retry.
                msg = str(e).lower()
                if "connected" in msg or "no such account" in msg or "does not exist" in msg:
                    account_link = _make_link(_fresh_account())
                else:
                    raise
            return jsonify({
                "success": True,
                "url": account_link.url,
                "expires_at": account_link.expires_at,
            }), 200
        except Exception as e:
            return jsonify({"error": "Stripe error: {}".format(str(e))}), 502
    else:
        unavailable = _payments_unavailable()
        if unavailable:
            return unavailable
        if not contractor.stripe_connect_id:
            return jsonify({"error": "No Stripe Connect account found. Call /connect/create-account first."}), 400
        # Dev mode — return mock URL
        return jsonify({
            "success": True,
            "url": "https://connect.stripe.com/setup/e/mock",
            "expires_at": int((utcnow() + timedelta(minutes=5)).timestamp()),
        }), 200


@payments_bp.route("/connect/status", methods=["GET"])
@require_auth
def get_connect_status(user_id):
    """Get the Stripe Connect onboarding status for the authenticated driver."""
    contractor = Contractor.query.filter_by(user_id=user_id).first()
    if not contractor:
        return jsonify({"error": "Contractor profile not found"}), 404

    if not contractor.stripe_connect_id:
        return jsonify({
            "success": True,
            "status": "not_set_up",
            "charges_enabled": False,
            "payouts_enabled": False,
            "details_submitted": False,
        }), 200

    stripe = _get_stripe()
    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")

    charges_enabled = False
    payouts_enabled = False
    details_submitted = False

    if stripe_key:
        try:
            account = stripe.Account.retrieve(contractor.stripe_connect_id)
            charges_enabled = account.get("charges_enabled", False)
            payouts_enabled = account.get("payouts_enabled", False)
            details_submitted = account.get("details_submitted", False)
        except Exception:
            pass  # Fall back to stored values or False

    # Determine status
    if charges_enabled and payouts_enabled:
        status = "active"
    elif contractor.stripe_connect_id:
        status = "pending_verification"
    else:
        status = "not_set_up"

    return jsonify({
        "success": True,
        "status": status,
        "charges_enabled": charges_enabled,
        "payouts_enabled": payouts_enabled,
        "details_submitted": details_submitted,
    }), 200


@payments_bp.route("/connect/return", methods=["GET"])
def connect_return():
    """Stripe calls this URL after successful onboarding completion."""
    return """
    <html>
    <head><title>Setup Complete</title></head>
    <body style="font-family: sans-serif; text-align: center; padding: 50px;">
        <h1>Setup complete!</h1>
        <p>Return to the Umuve Pro app.</p>
    </body>
    </html>
    """, 200


@payments_bp.route("/connect/refresh", methods=["GET"])
def connect_refresh():
    """Stripe calls this URL if the onboarding link expires."""
    return """
    <html>
    <head><title>Link Expired</title></head>
    <body style="font-family: sans-serif; text-align: center; padding: 50px;">
        <h1>Link expired</h1>
        <p>Please return to the app and try again.</p>
    </body>
    </html>
    """, 200


@payments_bp.route("/earnings/history", methods=["GET"])
@require_auth
def get_earnings_history(user_id):
    """Return detailed earnings history with per-job payout status (driver's 80% take only)."""
    contractor = Contractor.query.filter_by(user_id=user_id).first()
    if not contractor:
        return jsonify({"error": "Contractor profile not found"}), 404

    now = utcnow().replace(tzinfo=None)  # Make timezone-naive for DB comparison
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    # Query all succeeded payments for this driver
    payments = (
        Payment.query
        .join(Job, Payment.job_id == Job.id)
        .filter(Job.driver_id == contractor.id, Payment.payment_status == "succeeded")
        .order_by(Payment.created_at.desc())
        .all()
    )

    # Build entries
    entries = []
    for payment in payments:
        job = db.session.get(Job, payment.job_id)
        payout = payment.driver_payout_amount or 0.0
        entries.append({
            "id": payment.id,
            "job_id": payment.job_id,
            "address": job.address if job else None,
            "amount": round(payout, 2),
            "date": payment.created_at.isoformat() if payment.created_at else None,
            "payout_status": payment.payout_status,
        })

    # Compute summary (handle None values)
    today_earnings = sum(
        (p.driver_payout_amount or 0.0) for p in payments
        if p.created_at and p.created_at >= today_start
    )
    week_earnings = sum(
        (p.driver_payout_amount or 0.0) for p in payments
        if p.created_at and p.created_at >= seven_days_ago
    )
    month_earnings = sum(
        (p.driver_payout_amount or 0.0) for p in payments
        if p.created_at and p.created_at >= thirty_days_ago
    )
    all_time_earnings = sum((p.driver_payout_amount or 0.0) for p in payments)

    return jsonify({
        "success": True,
        "entries": entries,
        "summary": {
            "today": round(today_earnings, 2),
            "week": round(week_earnings, 2),
            "month": round(month_earnings, 2),
            "all_time": round(all_time_earnings, 2),
        },
    }), 200


# ---------------------------------------------------------------------------
# Stripe Webhook
# ---------------------------------------------------------------------------
webhook_bp = Blueprint("webhooks", __name__, url_prefix="/api/webhooks")


WEBHOOK_MAX_ATTEMPTS = int(os.environ.get("WEBHOOK_MAX_ATTEMPTS", "8") or 8)
WEBHOOK_LEASE_SECONDS = int(os.environ.get("WEBHOOK_LEASE_SECONDS", "120") or 120)


def _dispatch_stripe_event(event_type, data_object, event):
    """Run the business handler. Returns "processed" or "orphan". Raises on
    unexpected failure so the inbox marks the event failed and Stripe retries."""
    if event_type == "payment_intent.succeeded":
        return _handle_payment_succeeded(data_object) or "processed"
    if event_type == "payment_intent.payment_failed":
        return _handle_payment_failed(data_object) or "processed"
    if event_type == "charge.refunded":
        return _handle_charge_refunded(data_object) or "processed"
    if event_type == "charge.dispute.created":
        return _handle_dispute_created(data_object) or "processed"
    if event_type == "account.updated":
        _handle_account_updated(data_object)
        return "processed"
    if event_type == "checkout.session.completed":
        _handle_checkout_completed(event)
        return "processed"
    return "processed"  # event types we don't act on are acknowledged


def _inbox_claim(event_id, event_type, payload):
    """Durable inbox (audit F07). Returns (row, action) with action in
    process | duplicate | inflight | exhausted. Raises on a DB outage so the
    caller answers 500 and Stripe retries (a lost insert must not be a 200)."""
    now = _naive_now()
    lease = now + timedelta(seconds=WEBHOOK_LEASE_SECONDS)
    row = WebhookEvent.query.filter_by(stripe_event_id=event_id).first()
    if row is None:
        row = WebhookEvent(id=generate_uuid(), stripe_event_id=event_id,
                           event_type=event_type or "unknown", payload=payload,
                           status="processing", attempts=1, leased_until=lease)
        db.session.add(row)
        try:
            db.session.commit()
            return row, "process"
        except IntegrityError:
            # Uniqueness race with a sibling worker: fall through to the
            # existing row instead of treating "already exists" as processed.
            db.session.rollback()
            row = WebhookEvent.query.filter_by(stripe_event_id=event_id).first()
            if row is None:
                raise
        except Exception:
            db.session.rollback()
            raise
    if row.status in ("processed", "orphan"):
        return row, "duplicate"
    if row.status == "processing" and row.leased_until and row.leased_until > now:
        return row, "inflight"
    if row.status == "failed" and (row.attempts or 0) >= WEBHOOK_MAX_ATTEMPTS:
        return row, "exhausted"
    row.status = "processing"
    row.attempts = (row.attempts or 0) + 1
    row.leased_until = lease
    if payload and not row.payload:
        row.payload = payload
    db.session.commit()
    return row, "process"


def _inbox_finish(row_id, status, error=None):
    """Terminal bookkeeping for an inbox row in a fresh transaction."""
    try:
        db.session.rollback()
    except Exception:
        pass
    row = db.session.get(WebhookEvent, row_id)
    if row is None:
        return None
    row.status = status
    row.leased_until = None
    if status in ("processed", "orphan"):
        row.processed_at = _naive_now()
    if error is not None:
        row.last_error = str(error)[:2000]
        row.error_message = str(error)[:2000]
    db.session.commit()
    return row


def _run_inbox_event(row, event_type, data_object, event):
    """Process one leased inbox row; returns (http_status, body)."""
    try:
        result = _dispatch_stripe_event(event_type, data_object, event)
    except Exception as e:
        logger.exception("Stripe webhook handler failed: %s (%s)", row.stripe_event_id, event_type)
        row = _inbox_finish(row.id, "failed", error=e) or row
        if (row.attempts or 0) >= WEBHOOK_MAX_ATTEMPTS:
            _alert("Stripe webhook gave up after {} attempts".format(row.attempts),
                   "{} {} — last error: {}. Retry from the admin webhook-events endpoint."
                   .format(row.stripe_event_id, event_type, str(e)[:300]))
        return 500, {"received": False, "error": "handler failed; retry", "attempts": row.attempts}
    if isinstance(result, str) and result.startswith("orphan"):
        reason = result.partition(":")[2].strip() or "no matching payment/attempt for this event"
        _inbox_finish(row.id, "orphan", error=reason)
        _alert("Orphan Stripe event",
               "{} {}: {}. Reconcile in Stripe; replay from the admin webhook-events endpoint once fixed."
               .format(row.stripe_event_id, event_type, reason))
        return 200, {"received": True, "orphan": True, "reason": reason}
    _inbox_finish(row.id, "processed")
    return 200, {"received": True}


@webhook_bp.route("/stripe", methods=["POST"])
def stripe_webhook():
    """
    Handle Stripe webhook events with signature verification.
    Events: payment_intent.succeeded, payment_intent.payment_failed,
            charge.refunded, charge.dispute.created, account.updated,
            checkout.session.completed

    Durable inbox (audit F07): each provider event id is stored once with a
    lease + attempt count; a handler crash returns 500 so Stripe retries the
    same event until it processes (or WEBHOOK_MAX_ATTEMPTS, then it stays
    ``failed`` for the admin retry endpoint). A DB outage on the insert is a
    500, never a "duplicate" 200.
    """
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature", "")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    stripe = _get_stripe()

    # Verify webhook signature when secret is configured
    if webhook_secret:
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except stripe.error.SignatureVerificationError:
            return jsonify({"error": "Invalid signature"}), 400
        except ValueError:
            return jsonify({"error": "Invalid payload"}), 400
    elif not is_production():
        # Dev mode only — parse without verification
        import json
        try:
            event = json.loads(payload)
        except Exception:
            return jsonify({"error": "Invalid JSON"}), 400
    else:
        # Fail CLOSED in production: without the webhook secret we cannot tell
        # a real Stripe event from a forged one that marks jobs paid for free.
        logger.error("STRIPE_WEBHOOK_SECRET is not set — rejecting webhook")
        return jsonify({"error": "Webhook not configured"}), 500

    event_type = event.get("type") if isinstance(event, dict) else event["type"]
    data_object = event.get("data", {}).get("object", {}) if isinstance(event, dict) else event["data"]["object"]
    event_id = event.get("id") if isinstance(event, dict) else getattr(event, "id", None)

    if not event_id:
        # No provider id to dedupe on — process best-effort (dev payloads).
        try:
            _dispatch_stripe_event(event_type, data_object, event)
        except Exception:
            logger.exception("Stripe webhook (no event id) handler failed")
            return jsonify({"received": False, "error": "handler failed"}), 500
        return jsonify({"received": True}), 200

    try:
        import json as _json
        stored = _json.loads(payload) if payload else None
    except Exception:
        stored = None
    try:
        row, action = _inbox_claim(event_id, event_type, stored)
    except Exception:
        logger.exception("Stripe webhook inbox unavailable for %s", event_id)
        return jsonify({"received": False, "error": "inbox unavailable; retry"}), 500

    if action == "duplicate":
        logger.info("Stripe webhook replay skipped: %s (%s)", event_id, event_type)
        return jsonify({"received": True, "duplicate": True}), 200
    if action == "inflight":
        return jsonify({"received": True, "in_flight": True}), 200
    if action == "exhausted":
        return jsonify({"received": True, "failed": True, "attempts": row.attempts}), 200

    code, body = _run_inbox_event(row, event_type, data_object, event)
    return jsonify(body), code


def _require_admin(f):
    @wraps(f)
    @require_auth
    def wrapper(user_id, *args, **kwargs):
        user = db.session.get(User, user_id)
        if not user or user.role != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(user_id=user_id, *args, **kwargs)
    return wrapper


@payments_bp.route("/admin/webhook-events", methods=["GET"])
@_require_admin
def admin_list_webhook_events(user_id):
    """List inbox rows needing attention. ?status=failed,orphan (default) &limit=100"""
    statuses = [s.strip() for s in (request.args.get("status") or "failed,orphan").split(",") if s.strip()]
    limit = min(int(request.args.get("limit") or 100), 500)
    rows = (WebhookEvent.query.filter(WebhookEvent.status.in_(statuses))
            .order_by(WebhookEvent.created_at.desc()).limit(limit).all())
    return jsonify({"success": True, "events": [r.to_dict() for r in rows], "count": len(rows)}), 200


@payments_bp.route("/admin/webhook-events/<event_row_id>/retry", methods=["POST"])
@_require_admin
def admin_retry_webhook_event(user_id, event_row_id):
    """Re-run a failed/orphan event from its stored payload."""
    row = db.session.get(WebhookEvent, event_row_id)
    if row is None:
        row = WebhookEvent.query.filter_by(stripe_event_id=event_row_id).first()
    if row is None:
        return jsonify({"error": "Event not found"}), 404
    if not row.payload:
        return jsonify({"error": "No stored payload for this event; nothing to replay"}), 409
    event = row.payload
    event_type = event.get("type") or row.event_type
    data_object = (event.get("data") or {}).get("object") or {}
    row.status = "processing"
    row.attempts = (row.attempts or 0) + 1
    row.leased_until = _naive_now() + timedelta(seconds=WEBHOOK_LEASE_SECONDS)
    db.session.commit()
    code, body = _run_inbox_event(row, event_type, data_object, event)
    row = db.session.get(WebhookEvent, row.id)
    return jsonify({"success": code == 200, "result": body, "event": row.to_dict()}), (200 if code == 200 else 502)


@payments_bp.route("/admin/jobs/<job_id>/ledger", methods=["GET"])
@_require_admin
def admin_job_ledger(user_id, job_id):
    """Every attempt, payout and refund for a job — the money history."""
    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    payment = Payment.query.filter_by(job_id=job_id).first()
    return jsonify({
        "success": True,
        "payment": payment.to_dict() if payment else None,
        "attempts": [a.to_dict() for a in PaymentAttempt.query.filter_by(job_id=job_id)
                     .order_by(PaymentAttempt.created_at.asc()).all()],
        "payouts": [p.to_dict() for p in Payout.query.filter_by(job_id=job_id).all()],
        "refunds": [r.to_dict() for r in (Refund.query.filter_by(payment_id=payment.id).all() if payment else [])],
    }), 200


def _handle_payment_succeeded(intent):
    """Mark payment as succeeded, update job to confirmed, and trigger auto-assignment.

    Returns "orphan" when the intent matches nothing we know (recorded +
    alerted by the inbox, never silently acknowledged), "processed" otherwise.
    Verifies amount/currency against the immutable PaymentAttempt before
    settling (audit F07).
    """
    intent_id = intent.get("id", "")
    amount_cents = intent.get("amount")
    currency = (intent.get("currency") or "").lower() or None

    payment, job = _locate_payment_for_intent(intent_id, stripe_obj=intent)
    if not payment:
        logger.warning("Stripe webhook: no payment found for intent %s", intent_id)
        return "orphan"

    # Idempotency: Stripe retries this webhook (and the client may have already
    # hit /confirm-simple). If it's already reconciled — or refunded — do
    # nothing: we'd resend emails, re-notify, double-count promo uses, or
    # overwrite a refund with "succeeded".
    if payment.payment_status in _SETTLED_STATUSES:
        return "processed"

    attempt = PaymentAttempt.query.filter_by(stripe_intent_id=intent_id).first() if intent_id else None
    if attempt is not None:
        if amount_cents is not None and int(amount_cents) != int(attempt.amount_cents or 0):
            msg = "amount mismatch: Stripe {} vs attempt {} ({})".format(amount_cents, attempt.amount_cents, attempt.id)
            attempt.last_error = msg
            db.session.commit()
            logger.error("Stripe webhook %s: %s", intent_id, msg)
            return "orphan:" + msg
        if currency and currency != (attempt.currency or "usd"):
            msg = "currency mismatch: Stripe {} vs attempt {}".format(currency, attempt.currency)
            attempt.last_error = msg
            db.session.commit()
            return "orphan:" + msg
    elif amount_cents is not None:
        # No immutable attempt (Checkout-session / legacy flows): the charge is
        # real, so keep the truth on the row and flag drift for a human.
        charged = round(int(amount_cents) / 100.0, 2)
        if payment.amount and abs(charged - float(payment.amount)) > 0.01:
            logger.warning("intent %s charged $%.2f but payment %s expected $%.2f — adopting charged amount",
                           intent_id, charged, payment.id, payment.amount)
            _alert("Charged amount differs from booking",
                   "job {} intent {}: charged ${:.2f}, booking ${:.2f}".format(payment.job_id, intent_id,
                                                                              charged, payment.amount or 0))
            payment.amount = charged
        if currency and currency != "usd":
            return "orphan:non-USD charge ({}) for job {}".format(currency, payment.job_id)

    settle = _settle_payment_success(payment, job, intent_id=intent_id)

    if job:
        # Notify assigned contractor if one exists
        if job.driver_id:
            contractor = db.session.get(Contractor, job.driver_id)
            if contractor:
                db.session.add(Notification(
                    id=generate_uuid(),
                    user_id=contractor.user_id,
                    type="payment",
                    title="Payment Confirmed",
                    body="Payment of ${:.2f} confirmed for job at {}.".format(
                        payment.amount, job.address or "address"
                    ),
                    data={"job_id": job.id, "amount": payment.amount},
                ))

        # Send customer confirmation
        if not settle["refund_required"]:
            customer = db.session.get(User, job.customer_id)
            if customer and customer.email:
                from notifications import send_booking_confirmation_email
                send_booking_confirmation_email(
                    to_email=customer.email,
                    customer_name=customer.name or "",
                    booking_id=job.id,
                    address=job.address or "",
                    scheduled_date=local_date_str(job.scheduled_at),
                    scheduled_time=fmt_local(job.scheduled_at, "%H:%M", ""),
                    total_amount=payment.amount,
                )

        # Broadcast status update via SocketIO
        from socket_events import broadcast_job_status
        broadcast_job_status(job.id, job.status)

        # Cancel abandoned booking recovery SMS
        try:
            from sms_service import cancel_abandoned_booking_sms
            cancel_abandoned_booking_sms(job.id)
        except Exception:
            pass

    db.session.commit()
    _after_settle(job, settle)

    # --- Meta Conversions API: server-side Purchase (deduped vs browser pixel) ---
    # Fires only if META_PIXEL_ID + META_CAPI_ACCESS_TOKEN are set; otherwise a
    # silent no-op. event_id 'purchase_<job_id>' matches the browser pixel's id
    # so Meta counts the conversion once with clean attribution. Never raises.
    if job and not settle["refund_required"]:
        try:
            from meta_capi import track_purchase
            cust = db.session.get(User, job.customer_id)
            track_purchase(
                job_id=job.id,
                value=payment.amount,
                currency="USD",
                email=cust.email if cust else None,
                phone=cust.phone if cust else None,
                event_source_url="https://app.goumuve.com/book",
            )
        except Exception:
            logger.exception("Meta CAPI purchase hook failed for job %s", job.id)

    # --- Auto-dispatch best operator in background ---
    if job and not job.driver_id and job.status in ("confirmed", "assigned"):
        try:
            from dispatcher import auto_assign_job_async
            auto_assign_job_async(job.id, current_app._get_current_object())
        except Exception:
            logger.exception("Failed to trigger auto-dispatch for job %s", job.id)
    return "processed"


def _auto_assign_driver(job):
    """Find the nearest online approved contractor and assign the job."""
    from math import radians, cos, sin, asin, sqrt

    EARTH_RADIUS_KM = 6371.0
    AUTO_ASSIGN_RADIUS_KM = 50.0

    def haversine(lat1, lng1, lat2, lng2):
        lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
        return 2 * EARTH_RADIUS_KM * asin(sqrt(a))

    query = Contractor.query.filter_by(
        is_online=True, approval_status="approved", is_operator=False
    )

    # If job belongs to an operator, only assign to that operator's fleet
    if job.operator_id:
        query = query.filter_by(operator_id=job.operator_id)
    else:
        # Only independent contractors (not in any fleet)
        query = query.filter(Contractor.operator_id.is_(None))

    contractors = query.all()

    if not contractors:
        return

    # If job has location, sort by distance; otherwise pick first available
    best = None
    best_dist = float("inf")

    for c in contractors:
        # Skip contractors already handling active jobs
        active = Job.query.filter(
            Job.driver_id == c.id,
            Job.status.in_(["accepted", "en_route", "arrived", "started"]),
        ).first()
        if active:
            continue

        if job.lat is not None and job.lng is not None and c.current_lat is not None and c.current_lng is not None:
            dist = haversine(job.lat, job.lng, c.current_lat, c.current_lng)
            if dist <= AUTO_ASSIGN_RADIUS_KM and dist < best_dist:
                best = c
                best_dist = dist
        elif best is None:
            best = c

    if best:
        job.driver_id = best.id
        job.status = "assigned"
        job.updated_at = utcnow()

        # Notify driver
        notification = Notification(
            id=generate_uuid(),
            user_id=best.user_id,
            type="job_assigned",
            title="New Job Assigned",
            body="You've been assigned a job at {}.".format(job.address or "an address"),
            data={"job_id": job.id, "address": job.address, "total_price": job.total_price},
        )
        db.session.add(notification)

        # Notify customer
        notification_cust = Notification(
            id=generate_uuid(),
            user_id=job.customer_id,
            type="job_update",
            title="Driver Assigned",
            body="A driver has been assigned to your job.",
            data={"job_id": job.id, "status": "assigned"},
        )
        db.session.add(notification_cust)

        # Email customer about driver assignment
        try:
            customer = db.session.get(User, job.customer_id)
            if customer and customer.email:
                from notifications import send_driver_assigned_email
                send_driver_assigned_email(
                    customer.email, customer.name,
                    best.user.name if best.user else "Your driver",
                    job.address,
                    truck_type=best.truck_type,
                )
        except Exception:
            pass  # Notifications must never block the main flow

        # Emit SocketIO events
        from socket_events import socketio
        socketio.emit("job:assigned", {
            "job_id": job.id,
            "contractor_id": best.id,
            "contractor_name": best.user.name if best.user else None,
        }, room="driver:{}".format(best.id))

        socketio.emit("job:status", {
            "job_id": job.id,
            "status": "assigned",
            "driver_id": best.id,
        }, room=job.id)


def _handle_payment_failed(intent):
    """Mark payment as failed (the intent stays confirmable with a new card,
    so the attempt remains open; the error is recorded on it)."""
    intent_id = intent.get("id", "")
    attempt = PaymentAttempt.query.filter_by(stripe_intent_id=intent_id).first() if intent_id else None
    if attempt is not None:
        err = (intent.get("last_payment_error") or {})
        attempt.last_error = (err.get("message") if hasattr(err, "get") else str(err) or "payment_failed")[:500]
        attempt.updated_at = _naive_now()
    payment = Payment.query.filter_by(stripe_payment_intent_id=intent_id).first()
    if not payment and attempt is not None and attempt.payment_id:
        payment = db.session.get(Payment, attempt.payment_id)
    if not payment:
        db.session.commit()
        return "orphan" if attempt is None else "processed"
    if payment.payment_status in _SETTLED_STATUSES:
        db.session.commit()
        return "processed"   # a stale failure after success/refund never downgrades

    payment.payment_status = "failed"
    payment.updated_at = utcnow()

    job = db.session.get(Job, payment.job_id)
    if job:
        customer = db.session.get(User, job.customer_id)
        if customer:
            notification = Notification(
                id=generate_uuid(),
                user_id=customer.id,
                type="payment",
                title="Payment Failed",
                body="Your payment of ${:.2f} could not be processed.".format(payment.amount),
                data={"job_id": job.id},
            )
            db.session.add(notification)
            # Guests have no app to see the in-app row — reach them directly
            # so the job doesn't get worked unpaid.
            try:
                if getattr(customer, "phone", None):
                    from sms_service import send_sms as _sms
                    _sms(customer.phone,
                         "Umuve: your payment for job {} didn't go through. "
                         "Please update your card so we can keep your booking: "
                         "{}".format(
                             job.confirmation_code or str(job.id)[:8],
                             job.tracking_url()))
            except Exception:
                logger.exception("payment-failed customer SMS failed")
        # A failed charge on a live job is money walking out the door.
        try:
            admin_phone = os.environ.get("OPERATOR_PHONE") or os.environ.get("ADMIN_PHONE", "")
            if admin_phone:
                from notifications import send_sms as _admin_sms
                _admin_sms(admin_phone,
                           "⚠️ PAYMENT FAILED ${:.2f} on job {} (status {}). "
                           "Job is still live — decide before dispatch works it free.".format(
                               payment.amount,
                               job.confirmation_code or str(job.id)[:8],
                               job.status))
        except Exception:
            logger.exception("payment-failed admin SMS failed")

    db.session.commit()


def _handle_charge_refunded(charge):
    """Record a Stripe-side refund in the ledger (audit F14).

    ``amount_refunded`` on the charge is cumulative; the payment is
    ``refunded`` only when it covers the whole charge, else
    ``partially_refunded``. Each Stripe refund object becomes a Refund row
    (upserted by stripe_refund_id) so refunds issued from the Stripe
    dashboard show up exactly like ours. Transferred payouts get
    ``reversal_required`` — a Connect transfer is never auto-reversed.
    """
    intent_id = charge.get("payment_intent", "")
    if not intent_id:
        return "processed"
    if not isinstance(intent_id, str):
        intent_id = intent_id.get("id", "") if hasattr(intent_id, "get") else ""

    payment = Payment.query.filter_by(stripe_payment_intent_id=intent_id).first()
    if not payment:
        att = PaymentAttempt.query.filter_by(stripe_intent_id=intent_id).first()
        payment = db.session.get(Payment, att.payment_id) if att and att.payment_id else None
    if not payment:
        return "orphan"

    cumulative = round((charge.get("amount_refunded") or 0) / 100.0, 2)
    charged = round((charge.get("amount") or 0) / 100.0, 2)
    if charged and abs(charged - float(payment.amount or 0)) > 0.01:
        payment.amount = charged  # the charge is the truth of what was collected
    previously = round(payment.refunded_amount or 0.0, 2)

    # Ledger rows: one per Stripe refund object when the event carries them.
    refunds_data = (charge.get("refunds") or {})
    refunds_data = refunds_data.get("data") if hasattr(refunds_data, "get") else None
    ledger_total = 0.0
    seen_any = False
    for r in (refunds_data or []):
        rid = r.get("id")
        if not rid:
            continue
        seen_any = True
        amt = round((r.get("amount") or 0) / 100.0, 2)
        row = Refund.query.filter_by(stripe_refund_id=rid).first()
        if row is None:
            row = Refund(id=generate_uuid(), payment_id=payment.id, amount=amt,
                         reason="stripe:{}".format(r.get("reason") or "charge.refunded"),
                         stripe_refund_id=rid, status="pending")
            db.session.add(row)
        row.amount = amt
        row.status = {"succeeded": "succeeded", "failed": "failed", "canceled": "cancelled"}.get(
            r.get("status") or "succeeded", "pending")
        if row.status == "succeeded":
            ledger_total += amt
    if not seen_any and cumulative > previously:
        db.session.add(Refund(id=generate_uuid(), payment_id=payment.id,
                              amount=round(cumulative - previously, 2),
                              reason="stripe:charge.refunded", status="succeeded"))

    _apply_refund_amount(payment, cumulative)
    newly_refunded = round(cumulative - previously, 2)

    job = db.session.get(Job, payment.job_id)
    if job:
        if newly_refunded > 0:
            _flag_payout_reversals(job.id, "Stripe charge.refunded ${:.2f} (cumulative ${:.2f})"
                                   .format(newly_refunded, cumulative))
            customer = db.session.get(User, job.customer_id)
            if customer:
                db.session.add(Notification(
                    id=generate_uuid(),
                    user_id=customer.id,
                    type="payment",
                    title="Refund Processed",
                    body="A refund of ${:.2f} has been issued.".format(newly_refunded),
                    data={"job_id": job.id, "amount": newly_refunded,
                          "partial": payment.payment_status == "partially_refunded"},
                ))
        # A FULL refund on unfinished work is a cancellation: close the job,
        # release the hauler, drop it from the work queue. Money and status
        # must not disagree (job AFB22IMO sat "assigned" after its refund).
        auto_cancelled = False
        if payment.payment_status == "refunded":
            from cancellation import cancel_if_fully_refunded
            auto_cancelled = cancel_if_fully_refunded(job, payment, reason="refunded_in_full")
        # A PARTIAL refund while a hauler is moving is a judgement call — tell
        # a person, through the private alert line, never a hardcoded number.
        if newly_refunded > 0 and not auto_cancelled and job.status in (
                "assigned", "accepted", "en_route", "arrived", "started"):
            try:
                from ops_contacts import alert_sms
                alert_sms("REFUND ${:.2f} on job {} while status={}. Hauler may still be "
                          "en route — cancel or redirect them.".format(
                              newly_refunded, job.confirmation_code or str(job.id)[:8], job.status),
                          why="partial refund on a moving job")
            except Exception:
                logger.exception("refund admin SMS failed")

    db.session.commit()
    return "processed"


def _handle_dispute_created(dispute):
    """Log dispute and notify admin."""
    intent_id = dispute.get("payment_intent", "")
    if not intent_id:
        return

    payment = Payment.query.filter_by(stripe_payment_intent_id=intent_id).first()
    if not payment:
        return "orphan"

    payment.payment_status = "disputed"
    payment.updated_at = utcnow()
    db.session.commit()
    _alert("Stripe dispute opened", "job {} intent {} — respond in the Stripe dashboard."
           .format(payment.job_id, intent_id))
    return "processed"


def _handle_account_updated(account):
    """Handle Stripe Connect account.updated webhook event."""
    import logging
    logger = logging.getLogger(__name__)

    account_id = account.get("id")
    if not account_id:
        return

    contractor = Contractor.query.filter_by(stripe_connect_id=account_id).first()
    if not contractor:
        logger.info("account.updated webhook for unknown account: %s", account_id)
        return

    charges_enabled = account.get("charges_enabled", False)
    payouts_enabled = account.get("payouts_enabled", False)

    logger.info(
        "Stripe Connect account updated: %s (contractor: %s, charges_enabled: %s, payouts_enabled: %s)",
        account_id, contractor.id, charges_enabled, payouts_enabled
    )

    # Status is derived from Stripe API calls in /connect/status endpoint
    # No model changes needed here — just log for debugging
    db.session.commit()


# ---------------------------------------------------------------------------
# POST /api/payments/quick-checkout  (PUBLIC — for sending payment links to customers)
# ---------------------------------------------------------------------------
@payments_bp.route("/quick-checkout", methods=["POST"])
@limiter.limit("20 per hour")
def quick_checkout():
    """Create a Stripe Checkout Session for a quick invoice/payment link.

    Public endpoint — no auth required. Rate-limited.
    Used when operators send payment links to customers (e.g., phone bookings).
    """
    stripe = _get_stripe()
    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not stripe_key:
        return jsonify({"error": "Payments not configured"}), 503

    data = request.get_json() or {}
    amount_dollars = data.get("amount")
    description = data.get("description", "Junk Removal Service")
    customer_email = data.get("email")
    customer_name = data.get("name", "")
    customer_company = data.get("company", "")
    customer_address = data.get("address", "")

    if not amount_dollars or not isinstance(amount_dollars, (int, float)) or amount_dollars < 1:
        return jsonify({"error": "Valid amount required (minimum $1)"}), 400

    amount_cents = int(round(float(amount_dollars) * 100))

    try:
        session_params = {
            "payment_method_types": ["card"],
            "line_items": [{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": description,
                        "description": f"Umuve — Hauling Made Simple | ${amount_dollars:.2f}",
                    },
                    "unit_amount": amount_cents,
                },
                "quantity": 1,
            }],
            "mode": "payment",
            "success_url": "https://goumuve.com/pay/success",
            "cancel_url": "https://goumuve.com/pay/",
            "metadata": {
                "source": "quick-checkout",
                "description": description,
                "customer_name": customer_name[:200] if customer_name else "",
                "customer_company": customer_company[:200] if customer_company else "",
                "customer_address": customer_address[:500] if customer_address else "",
            },
        }

        if customer_email:
            session_params["customer_email"] = customer_email

        session = stripe.checkout.Session.create(**session_params)

        return jsonify({
            "success": True,
            "checkout_url": session.url,
            "session_id": session.id,
        }), 200

    except Exception as e:
        logger.error("Quick checkout error: %s", str(e))
        return jsonify({"error": "Failed to create checkout session"}), 500


def _reconcile_booking_checkout(session, job_id):
    """A Checkout Session tied to a Job was paid (Maya pay-link texts, the VA
    Dispatch Desk's pay links). Link the intent to the job's Payment row and
    run the standard confirm path.

    Before 2026-09-04 these sessions were ignored here (source != quick-
    checkout) and payment_intent.succeeded couldn't find them either (no
    metadata on the intent), so every paid phone job sat in "pending".
    """
    if session.get("payment_status") not in (None, "paid"):
        logger.info("Checkout for job %s completed but payment_status=%s — waiting",
                    job_id, session.get("payment_status"))
        return

    job = db.session.get(Job, job_id)
    if not job:
        logger.warning("Checkout completed for unknown job %s", job_id)
        return

    pi_id = session.get("payment_intent") or ""
    if not isinstance(pi_id, str):  # expanded object
        pi_id = pi_id.get("id", "") if hasattr(pi_id, "get") else ""

    payment = Payment.query.filter_by(job_id=job.id).first()
    if not payment:
        amount_total = session.get("amount_total") or 0
        payment = Payment(
            id=generate_uuid(),
            job_id=job.id,
            amount=round(amount_total / 100.0, 2) if amount_total else float(job.total_price or 0),
            service_fee=float(job.service_fee or 0),
            payment_status="pending",
        )
        db.session.add(payment)
        db.session.flush()

    if pi_id and payment.stripe_payment_intent_id != pi_id:
        clash = Payment.query.filter_by(stripe_payment_intent_id=pi_id).first()
        if clash and clash.id != payment.id:
            logger.warning("Intent %s already belongs to payment %s; not relinking to job %s",
                           pi_id, clash.id, job.id)
        else:
            payment.stripe_payment_intent_id = pi_id
            db.session.flush()

    _handle_payment_succeeded({"id": pi_id or payment.stripe_payment_intent_id or "",
                               "metadata": {"job_id": job.id}})


def _handle_checkout_completed(event):
    """Process a completed checkout session.

    Booking sessions (metadata booking_id / job_id, or client_reference_id)
    confirm the job. Quick-checkout invoices get a receipt email.
    """
    try:
        session = event.get("data", {}).get("object", {}) if isinstance(event, dict) else event.data.object
        metadata = session.get("metadata", {}) if isinstance(session, dict) else (session.metadata or {})
        metadata = metadata or {}

        job_id = (metadata.get("booking_id") or metadata.get("job_id")
                  or session.get("client_reference_id"))
        if job_id:
            _reconcile_booking_checkout(session, job_id)
            return

        source = metadata.get("source", "")
        if source != "quick-checkout":
            return  # Not a session shape we know how to settle

        customer_email = session.get("customer_email") or session.get("customer_details", {}).get("email", "")
        if not customer_email:
            logger.warning("Checkout completed but no customer email — skipping receipt")
            return

        amount_total = session.get("amount_total", 0)  # in cents
        amount_dollars = amount_total / 100.0 if amount_total else 0

        customer_name = metadata.get("customer_name", "")
        customer_company = metadata.get("customer_company", "")
        customer_address = metadata.get("customer_address", "")
        description = metadata.get("description", "Junk Removal Service")
        payment_intent_id = session.get("payment_intent", "")

        # Send branded receipt email
        from notifications import send_email
        from email_templates import quick_checkout_receipt_html

        html = quick_checkout_receipt_html(
            customer_name=customer_name,
            customer_email=customer_email,
            amount=amount_dollars,
            description=description,
            customer_company=customer_company,
            customer_address=customer_address,
            payment_intent_id=payment_intent_id,
        )

        subject = "Umuve Payment Receipt — ${:.2f}".format(amount_dollars)
        send_email(customer_email, subject, html)
        logger.info("Quick-checkout receipt sent to %s ($%.2f)", customer_email, amount_dollars)

    except Exception:
        logger.exception("Error handling checkout.session.completed")
