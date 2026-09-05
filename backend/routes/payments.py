"""
Payment API routes for Umuve.
Stripe Connect: customer pays -> platform takes commission -> contractor gets payout.
"""

import os
import time
import logging
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, Job, Payment, Contractor, User, Notification, PromoCode, ReferralPayout, generate_uuid, utcnow
from auth_routes import require_auth
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

    Does not commit; the caller's transaction persists it.
    """
    amount = payment.amount or 0.0
    tip = payment.tip_amount or 0.0
    split_base = max(0.0, round(amount - tip, 2))
    platform_commission = round(split_base * PLATFORM_COMMISSION, 2)
    service_fee = payment.service_fee or 0.0
    driver_gross = round(split_base - platform_commission - service_fee, 2)

    operator_payout = 0.0
    if job is not None and getattr(job, "operator_id", None):
        op = db.session.get(Contractor, job.operator_id)
        if op:
            rate = op.operator_commission_rate or 0.15
            operator_payout = round(driver_gross * rate, 2)

    payment.commission = platform_commission
    payment.operator_payout_amount = operator_payout
    payment.driver_payout_amount = max(0, round(driver_gross - operator_payout + tip, 2))


@payments_bp.route("/create-intent", methods=["POST"])
@limiter.limit("10 per minute")
@require_auth
def create_payment_intent(user_id):
    """
    Create a Stripe PaymentIntent for a job.
    Body JSON: job_id (str), tip_amount (float, optional)
    """
    data = request.get_json() or {}
    job_id = data.get("job_id")
    tip_amount = float(data.get("tip_amount", 0))

    if tip_amount < 0:
        return jsonify({"error": "tip_amount cannot be negative"}), 400

    if not job_id:
        return jsonify({"error": "job_id is required"}), 400

    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    if job.customer_id != user_id:
        return jsonify({"error": "Not authorised for this job"}), 403

    if job.payment and job.payment.payment_status == "succeeded":
        return jsonify({"error": "Job is already paid"}), 409

    # --- Promo code (server-authoritative: re-validate here; never trust a
    # client-supplied discount). A code shown in the funnel must actually
    # reduce the charge, or the discount is cosmetic and the customer overpays.
    discount = 0.0
    promo_message = None
    promo_code = (data.get("promo_code") or data.get("promoCode") or "").strip()
    if promo_code:
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

    discounted_base = max(0.0, round(job.total_price - discount, 2))
    amount = round(discounted_base + tip_amount, 2)
    # Platform take applies to the job amount only — tips pass through to the
    # driver 100%. (Previously the split was computed on amount incl. tip, so
    # the platform skimmed 28% of every tip.)
    commission = round(discounted_base * PLATFORM_COMMISSION, 2)
    service_fee = round(discounted_base * SERVICE_FEE_RATE, 2)
    driver_payout = max(0, round(amount - commission - service_fee, 2))

    stripe = _get_stripe()
    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")

    intent_id = None
    client_secret = None

    if stripe_key:
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(round(amount * 100)),
                currency="usd",
                metadata={"job_id": job_id, "user_id": user_id},
            )
            intent_id = intent.id
            client_secret = intent.client_secret
        except Exception as e:
            return jsonify({"error": "Stripe error: {}".format(str(e))}), 502
    else:
        intent_id = "pi_dev_{}".format(generate_uuid()[:8])
        client_secret = "{}_secret_dev".format(intent_id)

    payment = job.payment
    if not payment:
        payment = Payment(
            id=generate_uuid(),
            job_id=job_id,
        )
        db.session.add(payment)

    # Cancel the superseded intent so a stale client_secret can't double-charge.
    _old_intent = payment.stripe_payment_intent_id
    if (_old_intent and _old_intent != intent_id
            and not _old_intent.startswith("pi_dev_") and stripe_key):
        try:
            stripe.PaymentIntent.cancel(_old_intent)
        except Exception:
            pass

    payment.stripe_payment_intent_id = intent_id
    payment.amount = amount
    payment.service_fee = service_fee
    payment.commission = commission
    payment.driver_payout_amount = driver_payout
    payment.tip_amount = tip_amount
    payment.payment_status = "pending"
    payment.updated_at = utcnow()

    db.session.commit()

    return jsonify({
        "success": True,
        "client_secret": client_secret,
        "payment_intent_id": intent_id,
        "amount": amount,
        "discount": discount,
        "promo_message": promo_message,
        "payment": payment.to_dict(),
    }), 201


@payments_bp.route("/confirm", methods=["POST"])
@require_auth
def confirm_payment(user_id):
    """
    Mark a payment as succeeded.
    Body JSON: payment_intent_id (str)
    """
    data = request.get_json() or {}
    intent_id = data.get("payment_intent_id")

    if not intent_id:
        return jsonify({"error": "payment_intent_id is required"}), 400

    payment = Payment.query.filter_by(stripe_payment_intent_id=intent_id).first()
    if not payment:
        return jsonify({"error": "Payment not found"}), 404

    job = db.session.get(Job, payment.job_id)

    # Ownership: only the customer who owns the job may confirm its payment.
    if job and job.customer_id != user_id:
        return jsonify({"error": "Not authorised for this payment"}), 403

    # Verify against Stripe that the intent actually succeeded. Without this,
    # any client could mark its own payment "succeeded" with no money moving
    # — and the platform would still pay the driver real dollars.
    if not intent_id.startswith("pi_dev_"):
        stripe = _get_stripe()
        if os.environ.get("STRIPE_SECRET_KEY", ""):
            try:
                intent_obj = stripe.PaymentIntent.retrieve(intent_id)
                if intent_obj.status != "succeeded":
                    return jsonify({"error": "Payment intent has not succeeded (status: {})".format(intent_obj.status)}), 400
            except Exception as e:
                return jsonify({"error": "Failed to verify payment with Stripe: {}".format(str(e))}), 502

    was_succeeded = payment.payment_status == "succeeded"
    payment.payment_status = "succeeded"
    payment.updated_at = utcnow()

    if not was_succeeded:
        recompute_payment_split(payment, job)

    # Count a promo redemption once, only on the pending->succeeded transition,
    # so a double-confirm (or webhook + manual confirm) can't over-count uses.
    if job and job.promo_code_id and not was_succeeded:
        promo = db.session.get(PromoCode, job.promo_code_id)
        if promo:
            promo.use_count = (promo.use_count or 0) + 1

    # Advance the job and dispatch, same as confirm-simple — otherwise an
    # honest confirm through this route strands the job in "pending".
    if job and job.status == "pending":
        job.status = "confirmed"
        job.updated_at = utcnow()
        try:
            from socket_events import broadcast_job_status
            broadcast_job_status(job.id, job.status)
        except Exception:
            pass

    if job and job.driver_id:
        contractor = db.session.get(Contractor, job.driver_id)
        if contractor:
            notification = Notification(
                id=generate_uuid(),
                user_id=contractor.user_id,
                type="payment",
                title="Payment Received",
                body="Payment of ${:.2f} confirmed for job.".format(payment.amount),
                data={"job_id": job.id, "amount": payment.amount},
            )
            db.session.add(notification)

    db.session.commit()

    # --- Auto-dispatch best operator in background (mirrors confirm-simple) ---
    if job and job.status == "confirmed" and not job.driver_id:
        try:
            from dispatcher import auto_assign_job_async
            auto_assign_job_async(job.id, current_app._get_current_object())
        except Exception:
            logger.exception("Failed to trigger auto-dispatch for job %s", job.id)

    # --- Cancel abandoned booking recovery SMS ---
    try:
        from sms_service import cancel_abandoned_booking_sms
        cancel_abandoned_booking_sms(payment.job_id)
    except Exception:
        pass

    # --- Send payment receipt email to customer ---
    try:
        if job:
            customer = db.session.get(User, job.customer_id)
            if customer and customer.email:
                from notifications import send_payment_receipt_email
                send_payment_receipt_email(
                    customer.email, customer.name, job.id,
                    job.address, payment.amount,
                )
    except Exception:
        pass  # Notifications must never block the main flow

    return jsonify({"success": True, "payment": payment.to_dict()}), 200


def attempt_payout(job_id):
    """Core Stripe Connect payout for a completed job. Idempotent, never raises.

    Shared by the manual ``/payout/<job_id>`` route and the auto-payout hook
    that fires when a driver marks a job completed. Returns a dict:
        {"ok": bool, "status": str, "message": str, "amount": float}
      status one of: paid | already_paid | not_payable | no_connect | failed | error

    ``no_connect`` (contractor hasn't finished Stripe onboarding) is NOT a hard
    failure — the payout is marked ``pending_connect`` so a later sweep can
    retry once they connect, and the job completion is never blocked.
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
        if payment.payout_status == "paid":
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

        # Safety net: if no confirmation path ever computed the split (race
        # variants, legacy rows), compute it now rather than transfer $0.
        if (payment.driver_payout_amount or 0.0) <= 0 and (payment.amount or 0.0) > 0:
            recompute_payment_split(payment, job)
            db.session.commit()
            logger.warning(
                "attempt_payout recomputed missing split for job %s -> $%.2f",
                job_id, payment.driver_payout_amount or 0.0,
            )

        amount = payment.driver_payout_amount or 0.0
        stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")

        # Contractor hasn't connected a payout account yet — defer, don't fail.
        if not contractor.stripe_connect_id:
            payment.payout_status = "pending_connect"
            payment.updated_at = utcnow()
            db.session.commit()
            logger.info(
                "Payout for job %s deferred: contractor %s has no Stripe Connect account",
                job_id, contractor.id,
            )
            return {"ok": False, "status": "no_connect",
                    "message": "Contractor has not connected a payout account",
                    "amount": amount}

        if stripe_key:
            try:
                stripe = _get_stripe()
                stripe.Transfer.create(
                    amount=int(round(amount * 100)),
                    currency="usd",
                    destination=contractor.stripe_connect_id,
                    metadata={"job_id": job_id},
                    idempotency_key="payout_{}".format(job_id),
                )
            except Exception as e:
                payment.payout_status = "failed"
                payment.updated_at = utcnow()
                db.session.commit()
                logger.exception("Stripe payout failed for job %s", job_id)
                return {"ok": False, "status": "failed",
                        "message": "Stripe payout error: {}".format(e),
                        "amount": amount}

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
        logger.info("Payout of $%.2f sent for job %s -> contractor %s",
                    amount, job_id, contractor.id)
        return {"ok": True, "status": "paid",
                "message": "Payout sent", "amount": amount}
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

    stripe = _get_stripe()
    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")

    if not stripe_key or contractor.stripe_connect_id.startswith("acct_dev_"):
        # Dev/Mock mode
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

    stripe = _get_stripe()
    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")

    if not stripe_key or contractor.stripe_connect_id.startswith("acct_dev_"):
        # Dev/Mock mode
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
    Create a Stripe PaymentIntent without auth (for customer portal / iOS app).
    Body JSON: amount (float, in dollars, required), bookingId (str, optional),
               customerEmail (str, optional)
    """
    data = request.get_json() or {}
    booking_id = data.get("bookingId") or data.get("booking_id")
    customer_email = data.get("customerEmail") or data.get("customer_email")

    try:
        amount = float(data.get("amount", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid amount"}), 400

    # A paid booking must never have its payment reset to pending / its intent
    # re-pointed — this route is public, and the job UUID is discoverable, so
    # without this guard anyone could wipe the paid state of any booking.
    if booking_id:
        existing_payment = Payment.query.filter_by(job_id=booking_id).first()
        if existing_payment and existing_payment.payment_status == "succeeded":
            return jsonify({"error": "This booking is already paid"}), 409

    discount = 0.0
    promo_message = None
    promo_code = (data.get("promoCode") or data.get("promo_code") or "").strip()

    # Server-authoritative charge: when the booking exists, derive the amount
    # from the Job's server-computed total_price (+ any promo validated at
    # booking) instead of trusting the client-sent amount. This closes a hole
    # where a tampered client could pay an arbitrary amount for a real job.
    job_obj = db.session.get(Job, booking_id) if booking_id else None
    if job_obj and job_obj.total_price:
        base = float(job_obj.total_price)
        discount = float(job_obj.discount_amount or 0)
        # Apply a promo passed now only if one wasn't already applied at booking.
        if promo_code and discount <= 0:
            from routes.promos import validate_promo_code
            promo, disc, err = validate_promo_code(promo_code, base)
            if err:
                promo_message = err
            else:
                discount = disc
                job_obj.promo_code_id = promo.id
                job_obj.discount_amount = disc
                promo_message = "Promo {} applied: -${:.2f}".format(promo.code, disc)
        server_amount = max(0.50, round(base - discount, 2))
        if abs(server_amount - amount) > 0.01:
            logger.warning(
                "create-intent-simple amount override: client=%.2f server=%.2f job=%s",
                amount, server_amount, booking_id,
            )
        amount = server_amount
    else:
        # No booking on file (e.g. a pre-booking flow): fall back to the client
        # amount, still applying a validated promo against it if provided.
        if amount <= 0:
            return jsonify({"error": "amount is required and must be positive"}), 400
        if promo_code:
            from routes.promos import validate_promo_code
            promo, disc, err = validate_promo_code(promo_code, amount)
            if err:
                promo_message = err
            else:
                discount = disc
                amount = max(0.50, round(amount - discount, 2))
                promo_message = "Promo {} applied: -${:.2f}".format(promo.code, disc)

    if amount > 10000:
        return jsonify({"error": "amount exceeds maximum allowed ($10,000)"}), 400

    stripe = _get_stripe()
    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")

    intent_id = None
    client_secret = None

    metadata = {}
    if booking_id:
        metadata["booking_id"] = booking_id
    if customer_email:
        metadata["customer_email"] = customer_email

    if stripe_key:
        try:
            intent_kwargs = {
                "amount": int(round(amount * 100)),
                "currency": "usd",
                "metadata": metadata,
            }
            if customer_email:
                intent_kwargs["receipt_email"] = customer_email
            intent = stripe.PaymentIntent.create(**intent_kwargs)
            intent_id = intent.id
            client_secret = intent.client_secret
        except Exception as e:
            return jsonify({"error": "Stripe error: {}".format(str(e))}), 502
    else:
        # Dev mode - return mock intent
        intent_id = "pi_dev_{}".format(generate_uuid()[:8])
        client_secret = "{}_secret_dev".format(intent_id)

    # Link intent to the job's payment record if booking exists
    if booking_id:
        payment = Payment.query.filter_by(job_id=booking_id).first()
        if payment:
            # Cancel the superseded intent (e.g. user re-opened checkout) so a
            # stale client_secret can't produce a second live charge later.
            old_intent = payment.stripe_payment_intent_id
            if (old_intent and old_intent != intent_id
                    and not old_intent.startswith("pi_dev_") and stripe_key):
                try:
                    stripe.PaymentIntent.cancel(old_intent)
                except Exception:
                    pass  # already confirmed/cancelled — Stripe refuses, fine
            payment.stripe_payment_intent_id = intent_id
            payment.amount = amount
            payment.payment_status = "pending"
            payment.updated_at = utcnow()
        db.session.commit()  # persists the payment link AND any promo fields set on the job

    # --- Meta CAPI: server-side InitiateCheckout (mid-funnel signal, deduped
    # with the browser pixel via event_id checkout_<job_id>). Reaching payment
    # is the conversion event Meta optimizes toward; firing server-side keeps it
    # measurable through ad-blockers / iOS. No-op if CAPI unconfigured.
    if booking_id:
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
        "clientSecret": client_secret,
        "paymentIntentId": intent_id,
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
    Body JSON: paymentIntentId (str, required), paymentMethodType (str, optional)
    """
    data = request.get_json() or {}
    intent_id = data.get("paymentIntentId") or data.get("payment_intent_id")

    if not intent_id:
        return jsonify({"error": "paymentIntentId is required"}), 400

    # Validate against Stripe that the intent actually succeeded (skip for dev intents)
    if not intent_id.startswith("pi_dev_"):
        stripe = _get_stripe()
        stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")
        if stripe_key:
            try:
                intent_obj = stripe.PaymentIntent.retrieve(intent_id)
                if intent_obj.status != "succeeded":
                    return jsonify({"error": "Payment intent has not succeeded (status: {})".format(intent_obj.status)}), 400
            except Exception as e:
                return jsonify({"error": "Failed to verify payment with Stripe: {}".format(str(e))}), 502

    # Look up existing payment record
    payment = Payment.query.filter_by(stripe_payment_intent_id=intent_id).first()

    if not payment:
        return jsonify({"error": "Payment not found"}), 404

    was_succeeded = payment.payment_status == "succeeded"
    payment.payment_status = "succeeded"
    payment.updated_at = utcnow()

    job = db.session.get(Job, payment.job_id)

    # Compute the commission/payout split NOW. This path usually beats the
    # Stripe webhook (whose already-succeeded guard then no-ops), and bookings
    # create the Payment with driver_payout_amount=0 — without this the hauler
    # would be paid $0 for the job.
    if not was_succeeded:
        recompute_payment_split(payment, job)

    # Count a promo redemption once, on the pending->succeeded transition.
    if job and job.promo_code_id and not was_succeeded:
        _promo = db.session.get(PromoCode, job.promo_code_id)
        if _promo:
            _promo.use_count = (_promo.use_count or 0) + 1

    if job and job.status == "pending":
        job.status = "confirmed"
        job.updated_at = utcnow()

        # Broadcast status update via SocketIO
        from socket_events import broadcast_job_status
        broadcast_job_status(job.id, job.status)

    db.session.commit()

    # --- Auto-dispatch best operator in background ---
    if job and job.status == "confirmed" and not job.driver_id:
        try:
            from dispatcher import auto_assign_job_async
            auto_assign_job_async(job.id, current_app._get_current_object())
        except Exception:
            logger.exception("Failed to trigger auto-dispatch for job %s", job.id)

    # --- Cancel abandoned booking recovery SMS ---
    try:
        from sms_service import cancel_abandoned_booking_sms
        cancel_abandoned_booking_sms(payment.job_id)
    except Exception:
        pass

    # --- Send payment receipt email to customer ---
    try:
        if job:
            customer = db.session.get(User, job.customer_id)
            if customer and customer.email:
                from notifications import send_payment_receipt_email
                send_payment_receipt_email(
                    customer.email, customer.name, job.id,
                    job.address, payment.amount,
                )
    except Exception:
        pass  # Notifications must never block the main flow

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

    now = utcnow()
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)

    all_payments = (
        Payment.query
        .join(Job, Payment.job_id == Job.id)
        .filter(Job.driver_id == contractor.id, Payment.payment_status == "succeeded")
        .all()
    )

    total_earnings = sum(p.driver_payout_amount for p in all_payments)
    total_tips = sum(p.tip_amount for p in all_payments)
    earnings_30d = sum(p.driver_payout_amount for p in all_payments if p.created_at and p.created_at >= thirty_days_ago)
    earnings_7d = sum(p.driver_payout_amount for p in all_payments if p.created_at and p.created_at >= seven_days_ago)

    pending_payout = sum(
        p.driver_payout_amount for p in all_payments if p.payout_status == "pending"
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


@webhook_bp.route("/stripe", methods=["POST"])
def stripe_webhook():
    """
    Handle Stripe webhook events with signature verification.
    Events: payment_intent.succeeded, payment_intent.payment_failed,
            charge.refunded, charge.dispute.created
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
    elif os.environ.get("FLASK_ENV") == "development":
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

    # Durable idempotency: Stripe retries webhooks, and gunicorn runs multiple
    # workers — the in-row status guards alone can race. Record each event id
    # once (unique index on stripe_event_id) and skip replays.
    if event_id:
        from models import WebhookEvent
        try:
            db.session.add(WebhookEvent(
                id=generate_uuid(),
                stripe_event_id=event_id,
                event_type=event_type or "unknown",
                status="processing",
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.info("Stripe webhook replay skipped: %s (%s)", event_id, event_type)
            return jsonify({"received": True, "duplicate": True}), 200

    if event_type == "payment_intent.succeeded":
        _handle_payment_succeeded(data_object)

    elif event_type == "payment_intent.payment_failed":
        _handle_payment_failed(data_object)

    elif event_type == "charge.refunded":
        _handle_charge_refunded(data_object)

    elif event_type == "charge.dispute.created":
        _handle_dispute_created(data_object)

    elif event_type == "account.updated":
        _handle_account_updated(data_object)

    elif event_type == "checkout.session.completed":
        _handle_checkout_completed(event)

    return jsonify({"received": True}), 200


def _handle_payment_succeeded(intent):
    """Mark payment as succeeded, update job to confirmed, and trigger auto-assignment."""
    intent_id = intent.get("id", "")
    payment = Payment.query.filter_by(stripe_payment_intent_id=intent_id).first()

    # Fallback: if the intent id on file was superseded (client re-opened
    # checkout) or the webhook raced create-intent's commit, find the payment
    # via the job id we stamped into the intent metadata — and adopt this
    # intent as the one that actually charged.
    if not payment:
        meta = intent.get("metadata") or {}
        meta_job_id = meta.get("job_id") or meta.get("booking_id")
        if meta_job_id:
            payment = Payment.query.filter_by(job_id=meta_job_id).first()
            if payment and payment.payment_status != "succeeded":
                payment.stripe_payment_intent_id = intent_id
    if not payment:
        logger.warning("Stripe webhook: no payment found for intent %s", intent_id)
        return

    # Idempotency: Stripe retries this webhook (and the client may have already
    # hit /confirm-simple). If it's already reconciled, do nothing — otherwise
    # we'd resend confirmation emails, re-notify, and double-count promo uses.
    if payment.payment_status == "succeeded":
        return

    payment.payment_status = "succeeded"
    payment.updated_at = utcnow()

    job = db.session.get(Job, payment.job_id)

    # Commission/operator/driver split — the single shared computation used by
    # every confirmation path (tips pass through 100% to the driver).
    recompute_payment_split(payment, job)

    # Promo redemption count — idempotent via the already-succeeded guard above,
    # so this fires once whether confirm-simple or this webhook reconciles first.
    if job and job.promo_code_id:
        _promo = db.session.get(PromoCode, job.promo_code_id)
        if _promo:
            _promo.use_count = (_promo.use_count or 0) + 1

    if job:
        # Move job from pending to confirmed now that payment succeeded
        if job.status == "pending":
            job.status = "confirmed"
            job.updated_at = utcnow()

        # Notify assigned contractor if one exists
        if job.driver_id:
            contractor = db.session.get(Contractor, job.driver_id)
            if contractor:
                notification = Notification(
                    id=generate_uuid(),
                    user_id=contractor.user_id,
                    type="payment",
                    title="Payment Confirmed",
                    body="Payment of ${:.2f} confirmed for job at {}.".format(
                        payment.amount, job.address or "address"
                    ),
                    data={"job_id": job.id, "amount": payment.amount},
                )
                db.session.add(notification)

        # Send customer confirmation
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

    # --- Meta Conversions API: server-side Purchase (deduped vs browser pixel) ---
    # Fires only if META_PIXEL_ID + META_CAPI_ACCESS_TOKEN are set; otherwise a
    # silent no-op. event_id 'purchase_<job_id>' matches the browser pixel's id
    # so Meta counts the conversion once with clean attribution. Never raises.
    if job:
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
    """Mark payment as failed."""
    intent_id = intent.get("id", "")
    payment = Payment.query.filter_by(stripe_payment_intent_id=intent_id).first()
    if not payment:
        return

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
    """Mark payment as refunded."""
    intent_id = charge.get("payment_intent", "")
    if not intent_id:
        return

    payment = Payment.query.filter_by(stripe_payment_intent_id=intent_id).first()
    if not payment:
        return

    refund_amount = charge.get("amount_refunded", 0) / 100.0
    payment.payment_status = "refunded"
    payment.updated_at = utcnow()

    job = db.session.get(Job, payment.job_id)
    if job:
        customer = db.session.get(User, job.customer_id)
        if customer:
            notification = Notification(
                id=generate_uuid(),
                user_id=customer.id,
                type="payment",
                title="Refund Processed",
                body="A refund of ${:.2f} has been issued.".format(refund_amount),
                data={"job_id": job.id, "amount": refund_amount},
            )
            db.session.add(notification)
        # If the job still has a hauler moving on it, the refund means the
        # trip may be dead — tell the admin so nobody drives to a refunded job.
        if job.status in ("assigned", "accepted", "en_route", "arrived", "started"):
            try:
                admin_phone = os.environ.get("OPERATOR_PHONE") or os.environ.get("ADMIN_PHONE", "")
                if admin_phone:
                    from notifications import send_sms as _admin_sms
                    _admin_sms(admin_phone,
                               "⚠️ REFUND ${:.2f} on job {} while status={}. "
                               "Hauler may still be en route — cancel/redirect them.".format(
                                   refund_amount,
                                   job.confirmation_code or str(job.id)[:8],
                                   job.status))
            except Exception:
                logger.exception("refund admin SMS failed")

    db.session.commit()


def _handle_dispute_created(dispute):
    """Log dispute and notify admin."""
    intent_id = dispute.get("payment_intent", "")
    if not intent_id:
        return

    payment = Payment.query.filter_by(stripe_payment_intent_id=intent_id).first()
    if not payment:
        return

    payment.payment_status = "disputed"
    payment.updated_at = utcnow()
    db.session.commit()


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
