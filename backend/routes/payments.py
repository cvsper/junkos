"""
Payment API routes for JunkOS.
Stripe Connect: customer pays -> platform takes commission -> contractor gets payout.
"""

import os
from flask import Blueprint, request, jsonify
from datetime import datetime, timezone, timedelta

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, Job, Payment, Contractor, User, Notification, generate_uuid, utcnow
from auth_routes import require_auth

payments_bp = Blueprint("payments", __name__, url_prefix="/api/payments")

_stripe = None

PLATFORM_COMMISSION = 0.20
SERVICE_FEE = 15.00


def _get_stripe():
    global _stripe
    if _stripe is None:
        import stripe
        stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
        _stripe = stripe
    return _stripe


@payments_bp.route("/create-intent", methods=["POST"])
@require_auth
def create_payment_intent(user_id):
    """
    Create a Stripe PaymentIntent for a job.
    Body JSON: job_id (str), tip_amount (float, optional)
    """
    data = request.get_json() or {}
    job_id = data.get("job_id")
    tip_amount = float(data.get("tip_amount", 0))

    if not job_id:
        return jsonify({"error": "job_id is required"}), 400

    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    if job.customer_id != user_id:
        return jsonify({"error": "Not authorised for this job"}), 403

    if job.payment and job.payment.payment_status == "succeeded":
        return jsonify({"error": "Job is already paid"}), 409

    amount = round(job.total_price + tip_amount, 2)
    commission = round(amount * PLATFORM_COMMISSION, 2)
    driver_payout = round(amount - commission - SERVICE_FEE, 2)

    stripe = _get_stripe()
    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")

    intent_id = None
    client_secret = None

    if stripe_key:
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),
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

    payment.stripe_payment_intent_id = intent_id
    payment.amount = amount
    payment.service_fee = SERVICE_FEE
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

    payment.payment_status = "succeeded"
    payment.updated_at = utcnow()

    job = db.session.get(Job, payment.job_id)
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
    return jsonify({"success": True, "payment": payment.to_dict()}), 200


@payments_bp.route("/payout/<job_id>", methods=["POST"])
@require_auth
def trigger_payout(user_id, job_id):
    """Trigger Stripe Connect payout to the contractor for a completed job."""
    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    payment = job.payment
    if not payment:
        return jsonify({"error": "No payment record for this job"}), 404
    if payment.payment_status != "succeeded":
        return jsonify({"error": "Payment has not succeeded yet"}), 409
    if payment.payout_status == "paid":
        return jsonify({"error": "Payout already completed"}), 409

    if not job.driver_id:
        return jsonify({"error": "No driver assigned to this job"}), 400

    contractor = db.session.get(Contractor, job.driver_id)
    if not contractor:
        return jsonify({"error": "Contractor not found"}), 404

    stripe = _get_stripe()
    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")

    if stripe_key and contractor.stripe_connect_id:
        try:
            stripe.Transfer.create(
                amount=int(payment.driver_payout_amount * 100),
                currency="usd",
                destination=contractor.stripe_connect_id,
                metadata={"job_id": job_id},
            )
        except Exception as e:
            payment.payout_status = "failed"
            db.session.commit()
            return jsonify({"error": "Stripe payout error: {}".format(str(e))}), 502

    payment.payout_status = "paid"
    payment.updated_at = utcnow()

    notification = Notification(
        id=generate_uuid(),
        user_id=contractor.user_id,
        type="payment",
        title="Payout Sent",
        body="${:.2f} has been sent to your account.".format(payment.driver_payout_amount),
        data={"job_id": job_id, "amount": payment.driver_payout_amount},
    )
    db.session.add(notification)
    db.session.commit()

    return jsonify({"success": True, "payment": payment.to_dict()}), 200


@payments_bp.route("/create-intent-simple", methods=["POST"])
def create_simple_payment_intent():
    """
    Create a Stripe PaymentIntent without auth (for customer portal).
    Body JSON: bookingId (str), amount (float)
    """
    data = request.get_json() or {}
    booking_id = data.get("bookingId") or data.get("booking_id")
    amount = float(data.get("amount", 0))

    if not booking_id or amount <= 0:
        return jsonify({"error": "bookingId and amount are required"}), 400

    stripe = _get_stripe()
    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")

    intent_id = None
    client_secret = None

    if stripe_key:
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),
                currency="usd",
                metadata={"booking_id": booking_id},
            )
            intent_id = intent.id
            client_secret = intent.client_secret
        except Exception as e:
            return jsonify({"error": "Stripe error: {}".format(str(e))}), 502
    else:
        # Dev mode - return mock intent
        intent_id = "pi_dev_{}".format(generate_uuid()[:8])
        client_secret = "{}_secret_dev".format(intent_id)

    # Link intent to the job's payment record
    payment = Payment.query.filter_by(job_id=booking_id).first()
    if payment:
        payment.stripe_payment_intent_id = intent_id
        payment.amount = amount
        payment.payment_status = "pending"
        payment.updated_at = utcnow()
        db.session.commit()

    return jsonify({
        "success": True,
        "clientSecret": client_secret,
        "paymentIntentId": intent_id,
    }), 201


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
    else:
        # Dev mode — parse without verification
        import json
        try:
            event = json.loads(payload)
        except Exception:
            return jsonify({"error": "Invalid JSON"}), 400

    event_type = event.get("type") if isinstance(event, dict) else event["type"]
    data_object = event.get("data", {}).get("object", {}) if isinstance(event, dict) else event["data"]["object"]

    if event_type == "payment_intent.succeeded":
        _handle_payment_succeeded(data_object)

    elif event_type == "payment_intent.payment_failed":
        _handle_payment_failed(data_object)

    elif event_type == "charge.refunded":
        _handle_charge_refunded(data_object)

    elif event_type == "charge.dispute.created":
        _handle_dispute_created(data_object)

    return jsonify({"received": True}), 200


def _handle_payment_succeeded(intent):
    """Mark payment as succeeded and notify contractor."""
    intent_id = intent.get("id", "")
    payment = Payment.query.filter_by(stripe_payment_intent_id=intent_id).first()
    if not payment:
        return

    payment.payment_status = "succeeded"
    payment.updated_at = utcnow()

    job = db.session.get(Job, payment.job_id)
    if job:
        # Notify assigned contractor
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
                scheduled_date=str(job.scheduled_at.date()) if job.scheduled_at else "TBD",
                scheduled_time=str(job.scheduled_at.strftime("%H:%M")) if job.scheduled_at else "",
                total_amount=payment.amount,
            )

    db.session.commit()


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
