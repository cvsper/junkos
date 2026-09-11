"""Cancellation policy engine (audit F18).

One policy function — :func:`cancellation_outcome` — decides, for every
actor, whether a cancellation is allowed, what fee applies and what is
refunded. Every cancel path (customer, admin, operator, safety, change-order
decline) must go through :func:`execute_cancellation` so the refund, the
offer void and the notifications never diverge again.

Policy:
  * platform never assigned a hauler  -> always allowed, $0 fee, full refund
  * customer cancels after assignment but before en-route -> allowed, time fee
  * en_route / arrived / in progress   -> a cancellation REQUEST with the fee
    disclosed up front (``requires_confirmation``) instead of a hard block
  * operator / admin / safety / system -> never a customer fee, full refund

Guests act on their booking with a scoped manage token (HMAC of job id +
email + expiry) instead of a full JWT — see :func:`make_manage_token`.
"""

import base64
import hashlib
import hmac
import logging
import os
import time
from collections import namedtuple
from datetime import datetime, timedelta, timezone

from models import db, Contractor, Notification, Refund, User, generate_uuid, utcnow
from timeutils import to_utc

logger = logging.getLogger(__name__)

CancellationOutcome = namedtuple(
    "CancellationOutcome",
    "allowed fee refund_amount reason_code requires_confirmation message",
)

TERMINAL_STATUSES = ("completed", "cancelled")
# Hauler is physically committed / on the way — cancellation becomes a request.
ON_THE_WAY_STATUSES = ("en_route", "arrived", "started", "in_progress")
CUSTOMER_ACTORS = ("customer", "guest")
NO_FEE_ACTORS = ("admin", "operator", "driver", "platform", "safety", "system")

FEE_UNDER_24H = 25.0
FEE_UNDER_2H = 50.0

MANAGE_TOKEN_TTL_DAYS = 120


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------
def _time_fee(job, now):
    """Existing time rule: <2h $50, <24h $25, else free."""
    if not job.scheduled_at:
        return 0.0
    time_until = to_utc(job.scheduled_at) - to_utc(now)
    if time_until < timedelta(hours=2):
        return FEE_UNDER_2H
    if time_until < timedelta(hours=24):
        return FEE_UNDER_24H
    return 0.0


def _paid_amount(job):
    payment = getattr(job, "payment", None)
    if payment and payment.payment_status in ("succeeded", "partially_refunded"):
        return float(payment.amount or 0.0)
    return 0.0


def cancellation_outcome(job, actor, now=None):
    """Return a :class:`CancellationOutcome` for ``actor`` cancelling ``job``.

    ``actor`` is one of customer|guest|admin|operator|driver|platform|safety|system.
    ``refund_amount`` is what the customer gets back if the job is paid.
    """
    now = now or datetime.now(timezone.utc)
    actor = (actor or "customer").lower()
    paid = _paid_amount(job)

    if job.status in TERMINAL_STATUSES:
        return CancellationOutcome(False, 0.0, 0.0, "already_" + job.status, False,
                                   "Job cannot be cancelled in its current status")

    if actor in NO_FEE_ACTORS:
        code = {"safety": "safety_cancelled", "system": "platform_cancelled",
                "platform": "platform_cancelled"}.get(actor, actor + "_cancelled")
        return CancellationOutcome(True, 0.0, round(paid, 2), code, False,
                                   "Cancelled by Umuve — no fee, full refund.")

    # Customer / guest
    if not job.driver_id:
        # Platform never fulfilled: the customer must never pay for our miss.
        return CancellationOutcome(True, 0.0, round(paid, 2), "unfulfilled_no_hauler", False,
                                   "No hauler was assigned — no fee, full refund.")

    fee = _time_fee(job, now)
    if paid:
        fee = min(fee, paid)
    refund = round(max(0.0, paid - fee), 2)

    if job.status in ON_THE_WAY_STATUSES:
        return CancellationOutcome(
            True, fee, refund, "customer_after_dispatch", True,
            "Your hauler is already on the way. Cancelling now carries a ${:.2f} "
            "fee; ${:.2f} would be refunded.".format(fee, refund),
        )

    return CancellationOutcome(
        True, fee, refund, "customer_after_assignment", False,
        ("A ${:.2f} cancellation fee applies.".format(fee) if fee > 0
         else "Free cancellation — full refund."),
    )


# ---------------------------------------------------------------------------
# Refund (extracted from the old inline block in routes/jobs.py — the only
# refund implementation in the codebase; payments.py has none to import)
# ---------------------------------------------------------------------------
def issue_refund(job, payment, refund_amount, fee, reason, notify_user_id=None):
    """Refund ``refund_amount`` of a succeeded payment. Records a Refund row
    whatever happens; a Stripe failure never blocks the cancel — it leaves a
    ``failed`` row for the admin sweep and alerts admin. Does not commit."""
    from routes import payments as _payments

    refund_amount = round(max(0.0, refund_amount), 2)
    refund_row = Refund(
        id=generate_uuid(),
        payment_id=payment.id,
        amount=refund_amount,
        reason="{} (fee ${:.2f})".format(reason, fee),
        status="pending",
    )
    db.session.add(refund_row)

    intent_id = payment.stripe_payment_intent_id or ""
    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")
    full = fee <= 0
    if refund_amount <= 0:
        refund_row.status = "cancelled"  # fee consumed the full amount
    elif intent_id.startswith("pi_dev_") or not intent_id or not stripe_key:
        refund_row.status = "succeeded"  # dev mode — no real charge existed
        payment.payment_status = "refunded" if full else "partially_refunded"
        payment.updated_at = utcnow()
    else:
        try:
            stripe = _payments._get_stripe()
            sr = stripe.Refund.create(
                payment_intent=intent_id,
                amount=int(round(refund_amount * 100)),
                reason="requested_by_customer",
                idempotency_key="refund_{}".format(job.id),
            )
            refund_row.stripe_refund_id = sr.id
            refund_row.status = "succeeded"
            payment.payment_status = "refunded" if full else "partially_refunded"
            payment.updated_at = utcnow()
        except Exception as e:  # noqa: BLE001
            refund_row.status = "failed"
            refund_row.reason = "{} | stripe_error: {}".format(refund_row.reason, str(e)[:200])
            if notify_user_id:
                db.session.add(Notification(
                    id=generate_uuid(), user_id=notify_user_id, type="refund_pending",
                    title="Refund Processing",
                    body="Your refund of ${:.2f} is being processed and may take a little "
                         "longer than usual.".format(refund_amount),
                    data={"job_id": job.id, "amount": refund_amount},
                ))
            try:
                from sms_service import send_sms
                send_sms(os.environ.get("ADMIN_PHONE", ""),
                         "UMUVE ALERT: refund FAILED for cancelled job {} (${:.2f}) — issue "
                         "manually in Stripe.".format(str(job.id)[:8], refund_amount))
            except Exception:
                pass
            logger.error("Refund failed for job %s ($%.2f) — manual Stripe action needed",
                         job.id, refund_amount)
    return refund_row


# ---------------------------------------------------------------------------
# Execution (shared by every cancel path)
# ---------------------------------------------------------------------------
def execute_cancellation(job, actor, actor_user_id=None, now=None, reason=None, confirmed=False):
    """Apply :func:`cancellation_outcome` to ``job``.

    Returns ``(outcome, result_dict)``; ``result_dict["applied"]`` is False when
    the policy refused or when an on-the-way cancellation still needs the
    customer's explicit confirmation. Does not commit.
    """
    now = now or datetime.now(timezone.utc)
    outcome = cancellation_outcome(job, actor, now)
    result = {
        "allowed": outcome.allowed,
        "cancellation_fee": outcome.fee,
        "refund_amount": outcome.refund_amount,
        "reason_code": outcome.reason_code,
        "requires_confirmation": outcome.requires_confirmation,
        "message": outcome.message,
        "applied": False,
        "refund_status": None,
    }
    if not outcome.allowed:
        return outcome, result
    if outcome.requires_confirmation and not confirmed:
        return outcome, result

    had_driver = job.driver_id
    job.status = "cancelled"
    job.cancelled_at = utcnow()
    job.cancellation_fee = outcome.fee
    job.volume_adjustment_proposed = False
    job.updated_at = utcnow()

    # Void outstanding dispatch offers so a stale accept-link can't resurrect it.
    try:
        from models import JobOffer
        JobOffer.query.filter_by(job_id=job.id, status="sent").update(
            {"status": "expired"}, synchronize_session=False)
    except Exception:
        pass

    # Expire any open change orders.
    try:
        from models import ChangeOrder
        ChangeOrder.query.filter_by(job_id=job.id, status="proposed").update(
            {"status": "expired", "decided_at": utcnow()}, synchronize_session=False)
    except Exception:
        pass

    payment = getattr(job, "payment", None)
    if payment and payment.payment_status == "succeeded":
        row = issue_refund(job, payment, outcome.refund_amount, outcome.fee,
                           reason or outcome.reason_code, notify_user_id=job.customer_id)
        result["refund_status"] = row.status

    # Notify the assigned hauler.
    if had_driver:
        driver = db.session.get(Contractor, had_driver)
        if driver:
            body = "Job #{} has been cancelled{}.".format(
                str(job.id)[:8],
                " by the customer" if actor in CUSTOMER_ACTORS else " by Umuve")
            try:
                from notifications import send_push_notification
                send_push_notification(driver.user_id, "Job Cancelled", body,
                                       {"job_id": job.id, "status": "cancelled"})
            except Exception:
                pass
            db.session.add(Notification(
                id=generate_uuid(), user_id=driver.user_id, type="job_cancelled",
                title="Job Cancelled", body=body, data={"job_id": job.id},
            ))

    # Customer record.
    fee_msg = ""
    if outcome.fee > 0:
        fee_msg = " A cancellation fee of ${:.2f} applies.".format(outcome.fee)
    elif actor not in CUSTOMER_ACTORS:
        fee_msg = " No fee applies."
    if outcome.refund_amount > 0:
        fee_msg += " ${:.2f} will be refunded to your card.".format(outcome.refund_amount)
    db.session.add(Notification(
        id=generate_uuid(), user_id=job.customer_id, type="job_cancelled",
        title="Job Cancelled",
        body="Your job #{} has been cancelled.{}".format(str(job.id)[:8], fee_msg),
        data={"job_id": job.id, "cancellation_fee": outcome.fee,
              "refund_amount": outcome.refund_amount, "reason_code": outcome.reason_code},
    ))

    result["applied"] = True
    return outcome, result


def notify_customer_cancelled(job):
    """Best-effort cancellation email (after commit)."""
    try:
        customer = db.session.get(User, job.customer_id)
        if customer and customer.email:
            from notifications import send_job_status_update_email
            send_job_status_update_email(customer.email, customer.name, job.id, "cancelled")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Guest manage-booking token
# ---------------------------------------------------------------------------
def _secret():
    secret = (os.environ.get("MANAGE_TOKEN_SECRET") or os.environ.get("JWT_SECRET") or "")
    if not secret:
        try:
            from app_config import Config
            secret = Config.SECRET_KEY
        except Exception:
            secret = "dev-only-secret"
    return secret.encode("utf-8")


def _sign(job_id, email, exp):
    msg = "{}|{}|{}".format(job_id, (email or "").strip().lower(), exp).encode("utf-8")
    return hmac.new(_secret(), msg, hashlib.sha256).hexdigest()[:32]


def make_manage_token(job_id, email, ttl_days=MANAGE_TOKEN_TTL_DAYS):
    """Scoped capability: lets the booker cancel/reschedule THIS job without a JWT."""
    exp = int(time.time()) + int(ttl_days) * 86400
    raw = "{}.{}.{}".format(job_id, exp, _sign(job_id, email, exp))
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def verify_manage_token(job, token):
    """True if ``token`` was minted for this job + its customer's email and is unexpired."""
    if not token or job is None:
        return False
    try:
        padded = str(token) + "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        job_id, exp, sig = raw.split(".", 2)
        exp = int(exp)
    except Exception:
        return False
    if job_id != job.id or exp < int(time.time()):
        return False
    customer = db.session.get(User, job.customer_id)
    email = customer.email if customer else ""
    return hmac.compare_digest(_sign(job.id, email, exp), sig)


def customer_may_act(job, user_id, token):
    """Authorization for customer self-service: owner JWT or a valid manage token."""
    if job is None:
        return False
    if user_id and job.customer_id == user_id:
        return True
    return verify_manage_token(job, token)


# ---------------------------------------------------------------------------
# A full refund on unfinished work IS a cancellation
# ---------------------------------------------------------------------------
# Job AFB22IMO: the owner refunded the customer from the Stripe dashboard after
# the haul never happened. Stripe told us (charge.refunded), the payment row
# flipped to "refunded" — and the job stayed "assigned" to a hauler, at the top
# of the work queue as a customer still waiting. Money and status disagreed,
# and only a human with admin access could reconcile them.
#
# Rule: when the customer has been refunded in full and the job has not been
# completed, the job is cancelled. No second refund can happen —
# execute_cancellation only refunds a payment still in "succeeded", and
# _paid_amount is zero for a refunded one.
OPEN_FOR_REFUND_CANCEL = ("pending", "confirmed", "assigned", "accepted",
                          "en_route", "arrived", "started", "in_progress")


def cancel_if_fully_refunded(job, payment=None, reason="refunded_in_full"):
    """Cancel ``job`` if its payment was refunded in full and work never finished.

    Returns True when a cancellation was applied. Never raises; does not commit.
    """
    try:
        payment = payment or getattr(job, "payment", None)
        if not job or not payment:
            return False
        if (payment.payment_status or "") != "refunded":
            return False
        if job.status not in OPEN_FOR_REFUND_CANCEL:
            return False
        had_driver = job.driver_id
        outcome, result = execute_cancellation(job, "admin", reason=reason)
        if not result.get("applied"):
            return False
        # execute_cancellation voids offers and change orders; the dispatch
        # reservation is the assignment module's to release.
        if had_driver:
            try:
                from assignment import release_reservation
                release_reservation(job.id, had_driver)
            except Exception:
                logger.exception("reservation release failed for refunded job %s", job.id)
        logger.info("job %s cancelled: payment refunded in full while status was open",
                    job.confirmation_code or job.id)
        return True
    except Exception:
        logger.exception("cancel_if_fully_refunded failed for job %s", getattr(job, "id", "?"))
        return False


def reconcile_refunded_jobs(limit=200):
    """Sweep: every open job whose payment is already fully refunded gets
    cancelled. Idempotent. Catches refunds that landed before this rule
    existed, or whose webhook never reached us. Commits per job so one bad
    row cannot roll back the rest. Returns the codes it closed."""
    from models import Job, Payment
    closed = []
    rows = (db.session.query(Job, Payment)
            .join(Payment, Payment.job_id == Job.id)
            .filter(Payment.payment_status == "refunded",
                    Job.status.in_(OPEN_FOR_REFUND_CANCEL))
            .limit(limit).all())
    for job, payment in rows:
        if cancel_if_fully_refunded(job, payment, reason="refunded_in_full_reconcile"):
            try:
                db.session.commit()
                closed.append(job.confirmation_code or str(job.id)[:8])
                try:
                    notify_customer_cancelled(job)
                except Exception:
                    logger.exception("customer cancel notice failed for %s", job.id)
            except Exception:
                logger.exception("commit failed cancelling refunded job %s", job.id)
                db.session.rollback()
    return closed
