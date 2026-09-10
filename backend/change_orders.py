"""Versioned change orders (audit F12).

A change order captures a proposed change to a job's scope and price after
booking — the on-site "there's more here than the photos showed" moment —
with an explicit customer decision and a SEPARATE financial operation:

  * increase  -> a new PaymentIntent for the delta (explicitly authorised by
                 the customer's accept); the captured booking intent is never
                 modified (Stripe refuses that anyway once captured)
  * decrease  -> a partial refund on the booking intent
  * unpaid job -> only the job/payment amounts move

Proposals expire after 24h. Declining keeps the original scope and price —
there is no cancellation-fee framing here; if the hauler cannot do the
original scope, that is a separate (operator) cancellation with no customer
fee (see cancellation.py).

The driver-facing API shape (POST /api/drivers/jobs/<id>/volume) is preserved
by :func:`propose_volume_adjustment`; new fields are additive.
"""

import logging
import os
from datetime import datetime, timedelta, timezone

from models import db, ChangeOrder, Refund, generate_uuid, utcnow
from timeutils import to_utc

logger = logging.getLogger(__name__)

CHANGE_ORDER_TTL_HOURS = 24


def _stripe():
    from routes import payments as _payments
    return _payments._get_stripe()


def _recompute_split(payment, job):
    from routes.payments import recompute_payment_split
    recompute_payment_split(payment, job)


def _open_order(job):
    return (ChangeOrder.query.filter_by(job_id=job.id, status="proposed")
            .order_by(ChangeOrder.version.desc()).first())


def _expired(order, now):
    return order.expires_at is not None and to_utc(order.expires_at) <= to_utc(now)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
def propose_change_order(job, actor_type, actor_id, new_price, scope=None,
                         evidence_photos=None, reason="volume_adjustment", now=None):
    """Create the next version for ``job`` (superseding any open proposal).
    Mirrors the proposal onto the legacy job fields the Umuve Pro app reads."""
    now = now or datetime.now(timezone.utc)
    new_price = round(float(new_price), 2)
    old_price = round(float(job.total_price or 0.0), 2)

    open_order = _open_order(job)
    if open_order is not None:
        open_order.status = "expired"
        open_order.decided_at = utcnow()

    last = (ChangeOrder.query.filter_by(job_id=job.id)
            .order_by(ChangeOrder.version.desc()).first())
    order = ChangeOrder(
        id=generate_uuid(),
        job_id=job.id,
        version=(last.version + 1) if last else 1,
        status="proposed",
        reason=reason,
        proposed_by_type=actor_type,
        proposed_by_id=actor_id,
        scope=scope or {},
        evidence_photos=list(evidence_photos or []),
        old_price=old_price,
        new_price=new_price,
        delta=round(new_price - old_price, 2),
        expires_at=now + timedelta(hours=CHANGE_ORDER_TTL_HOURS),
    )
    db.session.add(order)

    job.volume_adjustment_proposed = True
    job.adjusted_price = new_price
    if scope and scope.get("actual_volume") is not None:
        job.adjusted_volume = scope.get("actual_volume")
    job.updated_at = utcnow()
    return order


def accept_change_order(job, order, now=None):
    """Customer (or auto for a decrease) accepts: apply scope/price and settle."""
    now = now or datetime.now(timezone.utc)
    if order.status != "proposed":
        raise ValueError("Change order is not open (status={})".format(order.status))
    if _expired(order, now):
        order.status = "expired"
        order.decided_at = utcnow()
        job.volume_adjustment_proposed = False
        raise ValueError("Change order has expired — the hauler must re-propose")

    order.status = "accepted"
    order.decided_at = utcnow()
    settle_change_order(job, order)

    job.total_price = order.new_price
    if (order.scope or {}).get("actual_volume") is not None:
        job.volume_estimate = order.scope["actual_volume"]
    if (order.scope or {}).get("items"):
        job.items = order.scope["items"]
    job.volume_adjustment_proposed = False
    job.adjusted_price = None
    job.adjusted_volume = None
    job.updated_at = utcnow()
    return order


def decline_change_order(job, order, now=None):
    """Customer declines: original scope and price stand. No fee, no cancel."""
    if order.status != "proposed":
        raise ValueError("Change order is not open (status={})".format(order.status))
    order.status = "declined"
    order.decided_at = utcnow()
    job.volume_adjustment_proposed = False
    job.adjusted_price = None
    job.adjusted_volume = None
    job.updated_at = utcnow()
    return order


def settle_change_order(job, order):
    """Move money for an accepted order. Never touches the captured intent."""
    payment = getattr(job, "payment", None)
    delta = round(float(order.delta), 2)

    if payment is None:
        order.settlement_status = "none"
        return order

    paid = payment.payment_status in ("succeeded", "partially_refunded")
    intent_id = payment.stripe_payment_intent_id or ""
    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")
    live = paid and stripe_key and intent_id and not intent_id.startswith("pi_dev_")

    if not paid or abs(delta) < 0.01:
        # Unpaid booking: the (single, future) charge simply becomes the new total.
        payment.amount = order.new_price
        _recompute_split(payment, job)
        order.settlement_status = "none"
        payment.updated_at = utcnow()
        return order

    if delta > 0:
        return _charge_increase(job, order, payment, delta, live, intent_id)
    return _refund_decrease(job, order, payment, -delta, live, intent_id)


def _charge_increase(job, order, payment, delta, live, intent_id):
    cents = int(round(delta * 100))
    if not live:
        order.settlement_status = "charged"
        order.settlement_intent_id = "pi_dev_co_{}".format(order.id[:8])
        payment.amount = order.new_price
        _recompute_split(payment, job)
        payment.updated_at = utcnow()
        return order
    try:
        stripe = _stripe()
        original = stripe.PaymentIntent.retrieve(intent_id)
        kwargs = {
            "amount": cents,
            "currency": "usd",
            "description": "Umuve on-site scope change — job {} v{}".format(
                str(job.id)[:8], order.version),
            "metadata": {
                "job_id": job.id, "change_order_id": order.id, "kind": "change_order",
                "version": str(order.version),
            },
        }
        customer = getattr(original, "customer", None)
        method = getattr(original, "payment_method", None)
        if customer and method:
            kwargs.update({"customer": customer, "payment_method": method,
                           "off_session": True, "confirm": True})
        intent = stripe.PaymentIntent.create(
            idempotency_key="co_{}_charge".format(order.id), **kwargs)
        order.settlement_intent_id = intent.id
        if getattr(intent, "status", "") == "succeeded":
            order.settlement_status = "charged"
            order.status = "settled"
            payment.amount = order.new_price
            _recompute_split(payment, job)
            payment.updated_at = utcnow()
        else:
            # Needs the customer to confirm in-app (no reusable saved method).
            order.settlement_status = "requires_action"
            order.client_secret = getattr(intent, "client_secret", None)  # transient, returned once
    except Exception as exc:  # noqa: BLE001
        logger.exception("change order %s charge failed", order.id)
        order.settlement_status = "failed"
        order.settlement_error = str(exc)[:500]
    return order


def _refund_decrease(job, order, payment, amount, live, intent_id):
    amount = round(min(amount, float(payment.amount or 0.0)), 2)
    row = Refund(
        id=generate_uuid(), payment_id=payment.id, amount=amount,
        reason="change_order v{} price decrease".format(order.version), status="pending",
    )
    db.session.add(row)
    if not live:
        row.status = "succeeded"
        order.settlement_status = "refunded"
        order.status = "settled"
    else:
        try:
            stripe = _stripe()
            sr = stripe.Refund.create(
                payment_intent=intent_id,
                amount=int(round(amount * 100)),
                reason="requested_by_customer",
                idempotency_key="co_{}_refund".format(order.id),
            )
            row.stripe_refund_id = sr.id
            row.status = "succeeded"
            order.settlement_refund_id = sr.id
            order.settlement_status = "refunded"
            order.status = "settled"
        except Exception as exc:  # noqa: BLE001
            logger.exception("change order %s refund failed", order.id)
            row.status = "failed"
            order.settlement_status = "failed"
            order.settlement_error = str(exc)[:500]
            return order
    payment.amount = order.new_price
    payment.payment_status = "partially_refunded"
    _recompute_split(payment, job)
    payment.updated_at = utcnow()
    return order


def confirm_settlement(job, order):
    """After the customer confirmed a ``requires_action`` intent client-side,
    verify with Stripe and finalise the amounts."""
    if order.settlement_status != "requires_action" or not order.settlement_intent_id:
        return order
    payment = job.payment
    try:
        intent = _stripe().PaymentIntent.retrieve(order.settlement_intent_id)
    except Exception as exc:  # noqa: BLE001
        order.settlement_error = str(exc)[:500]
        return order
    if getattr(intent, "status", "") == "succeeded":
        order.settlement_status = "charged"
        order.settlement_error = None
        order.status = "settled"
        if payment is not None:
            payment.amount = order.new_price
            _recompute_split(payment, job)
            payment.updated_at = utcnow()
    return order


def expire_stale_change_orders(now=None):
    """Flip proposals past their TTL to ``expired`` and clear the job flag."""
    now = now or datetime.now(timezone.utc)
    stale = ChangeOrder.query.filter(ChangeOrder.status == "proposed",
                                     ChangeOrder.expires_at.isnot(None),
                                     ChangeOrder.expires_at <= now.replace(tzinfo=None)).all()
    for order in stale:
        order.status = "expired"
        order.decided_at = utcnow()
        if order.job is not None:
            order.job.volume_adjustment_proposed = False
    return len(stale)


# ---------------------------------------------------------------------------
# Driver/operator entry point — preserves the existing /volume API shape
# ---------------------------------------------------------------------------
def volume_to_quantity(actual_volume):
    """Phase-2 tier mapping (unchanged)."""
    if actual_volume <= 4:
        return 2
    if actual_volume <= 8:
        return 5
    if actual_volume <= 12:
        return 10
    return 16


def propose_volume_adjustment(job, actor_type, actor_id, actual_volume,
                              evidence_photos=None, driver_room_id=None):
    """Shared implementation for the driver + operator volume routes.

    Returns ``(body, status)``. Decreases are customer-favourable and settle
    immediately (partial refund); increases wait for the customer's decision.
    """
    from routes.booking import calculate_estimate

    quantity = volume_to_quantity(actual_volume)
    try:
        result = calculate_estimate([{"category": "general", "quantity": quantity}],
                                    scheduled_date=None, lat=None, lng=None)
        new_price = round(float(result["total"]), 2)  # was result["grand_total"] -> KeyError
    except Exception:
        logger.exception("Failed to calculate new price for volume adjustment")
        return {"error": "Failed to calculate new price"}, 500

    original_price = round(float(job.total_price or 0.0), 2)
    scope = {"actual_volume": actual_volume, "quantity_tier": quantity,
             "items": [{"category": "general", "quantity": quantity}]}
    order = propose_change_order(job, actor_type, actor_id, new_price, scope=scope,
                                 evidence_photos=evidence_photos)

    if new_price <= original_price:
        accept_change_order(job, order)
        db.session.commit()
        _emit(driver_room_id or job.driver_id, "volume:approved",
              {"job_id": job.id, "change_order_id": order.id})
        logger.info("Volume adjustment auto-approved for job %s ($%.2f -> $%.2f)",
                    job.id, original_price, new_price)
        return {
            "success": True,
            "auto_approved": True,
            "new_price": new_price,
            "original_price": original_price,
            "change_order_id": order.id,
            "settlement_status": order.settlement_status,
        }, 200

    db.session.commit()
    try:
        from notifications import send_push_notification
        send_push_notification(
            job.customer_id,
            "Price Adjustment Required",
            "Volume increased. New price: ${:.2f} (was ${:.2f})".format(new_price, original_price),
            data={"job_id": job.id, "new_price": str(new_price),
                  "original_price": str(original_price), "type": "volume_adjustment",
                  "change_order_id": order.id},
            category="VOLUME_ADJUSTMENT",
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to send volume adjustment push notification: %s", e)
    _emit(driver_room_id or job.driver_id, "volume:proposed",
          {"job_id": job.id, "new_price": new_price, "change_order_id": order.id})
    logger.info("Volume adjustment proposed for job %s: $%.2f -> $%.2f", job.id, original_price, new_price)
    return {
        "success": True,
        "auto_approved": False,
        "new_price": new_price,
        "original_price": original_price,
        "change_order_id": order.id,
        "expires_at": order.expires_at.isoformat() if order.expires_at else None,
    }, 200


def _emit(driver_id, event, payload):
    if not driver_id:
        return
    try:
        from socket_events import socketio
        socketio.emit(event, payload, room="driver:{}".format(driver_id))
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to emit %s socket event: %s", event, e)
