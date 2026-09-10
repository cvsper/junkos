"""
Recurring Booking API routes for Umuve.
Allows customers to set up recurring/scheduled junk removal pickups.
"""

import logging
from flask import Blueprint, request, jsonify
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta

import sys
import os

logger = logging.getLogger(__name__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Job, Payment, RecurringBooking, RecurringOccurrence,
    generate_uuid, utcnow,
)
from auth_routes import require_auth
from timeutils import to_local, to_utc, local_now

recurring_bp = Blueprint("recurring", __name__, url_prefix="/api/recurring")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
VALID_FREQUENCIES = {"weekly", "biweekly", "monthly"}


def _compute_next_scheduled(frequency, day_of_week, day_of_month, preferred_time, after=None):
    """Compute the next scheduled datetime based on frequency settings.

    ``after`` is the reference point (defaults to now).  The returned datetime
    is always in the future relative to ``after``.
    """
    # Customers pick "Mondays at 9" in Florida time, so do the calendar math
    # in the business timezone and hand back UTC for storage.
    after = to_local(after) if after is not None else local_now()

    hour, minute = 9, 0
    if preferred_time:
        parts = preferred_time.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0

    if frequency in ("weekly", "biweekly"):
        target_dow = day_of_week if day_of_week is not None else 0  # default Monday
        days_ahead = (target_dow - after.weekday()) % 7
        if days_ahead == 0:
            # Same weekday -- if time already passed, push to next occurrence
            candidate = after.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate <= after:
                days_ahead = 7
        next_date = after + timedelta(days=days_ahead)
        next_dt = next_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if frequency == "biweekly" and next_dt <= after + timedelta(days=7):
            next_dt += timedelta(weeks=1)
        return to_utc(next_dt)

    if frequency == "monthly":
        target_day = day_of_month if day_of_month is not None else 1
        # Try current month first
        try:
            candidate = after.replace(day=target_day, hour=hour, minute=minute, second=0, microsecond=0)
        except ValueError:
            # Day doesn't exist in current month (e.g. Feb 30) -- skip to next month
            candidate = (after + relativedelta(months=1)).replace(
                day=target_day, hour=hour, minute=minute, second=0, microsecond=0
            )
        if candidate <= after:
            candidate = (candidate + relativedelta(months=1)).replace(
                day=target_day, hour=hour, minute=minute, second=0, microsecond=0
            )
        return to_utc(candidate)

    # Fallback: 7 days from now
    return to_utc(after + timedelta(days=7))


def _advance_next_scheduled(recurring):
    """Advance ``next_scheduled_at`` to the next occurrence after the current one."""
    current = recurring.next_scheduled_at or datetime.now(timezone.utc)
    recurring.next_scheduled_at = _compute_next_scheduled(
        recurring.frequency,
        recurring.day_of_week,
        recurring.day_of_month,
        recurring.preferred_time,
        after=current,
    )


def _require_admin(f):
    """Inline admin check wrapping require_auth."""
    from functools import wraps

    @wraps(f)
    @require_auth
    def wrapper(user_id, *args, **kwargs):
        user = db.session.get(User, user_id)
        if not user or user.role != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(user_id=user_id, *args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# POST /api/recurring  -- Create a recurring booking
# ---------------------------------------------------------------------------
@recurring_bp.route("", methods=["POST"])
@require_auth
def create_recurring(user_id):
    """Create a new recurring booking for the authenticated customer.

    Body JSON:
        frequency: str ("weekly" | "biweekly" | "monthly")
        day_of_week: int (0-6, required for weekly/biweekly)
        day_of_month: int (1-28, required for monthly)
        preferred_time: str ("HH:MM", default "09:00")
        address: str (required)
        lat: float (optional)
        lng: float (optional)
        items: list (optional)
        notes: str (optional)
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    # --- Validate frequency ---
    frequency = data.get("frequency")
    if frequency not in VALID_FREQUENCIES:
        return jsonify({"error": "frequency must be one of: weekly, biweekly, monthly"}), 400

    # --- Validate day fields ---
    day_of_week = data.get("day_of_week")
    day_of_month = data.get("day_of_month")

    if frequency in ("weekly", "biweekly"):
        if day_of_week is None:
            return jsonify({"error": "day_of_week is required for weekly/biweekly frequency"}), 400
        try:
            day_of_week = int(day_of_week)
        except (TypeError, ValueError):
            return jsonify({"error": "day_of_week must be an integer 0-6"}), 400
        if not (0 <= day_of_week <= 6):
            return jsonify({"error": "day_of_week must be between 0 (Monday) and 6 (Sunday)"}), 400

    if frequency == "monthly":
        if day_of_month is None:
            return jsonify({"error": "day_of_month is required for monthly frequency"}), 400
        try:
            day_of_month = int(day_of_month)
        except (TypeError, ValueError):
            return jsonify({"error": "day_of_month must be an integer 1-28"}), 400
        if not (1 <= day_of_month <= 28):
            return jsonify({"error": "day_of_month must be between 1 and 28"}), 400

    # --- Validate address ---
    address = data.get("address")
    if not address:
        return jsonify({"error": "address is required"}), 400

    preferred_time = data.get("preferred_time", "09:00")
    lat = data.get("lat")
    lng = data.get("lng")
    items = data.get("items", [])
    notes = data.get("notes", "")

    # Compute first next_scheduled_at
    next_scheduled_at = _compute_next_scheduled(
        frequency, day_of_week, day_of_month, preferred_time
    )

    recurring = RecurringBooking(
        id=generate_uuid(),
        customer_id=user_id,
        frequency=frequency,
        day_of_week=day_of_week if frequency in ("weekly", "biweekly") else None,
        day_of_month=day_of_month if frequency == "monthly" else None,
        preferred_time=preferred_time,
        address=address,
        lat=float(lat) if lat is not None else None,
        lng=float(lng) if lng is not None else None,
        items=items,
        notes=notes,
        is_active=True,
        next_scheduled_at=next_scheduled_at,
        total_bookings_created=0,
    )
    db.session.add(recurring)
    db.session.commit()

    return jsonify({"success": True, "recurring_booking": recurring.to_dict()}), 201


# ---------------------------------------------------------------------------
# GET /api/recurring  -- List user's recurring bookings
# ---------------------------------------------------------------------------
@recurring_bp.route("", methods=["GET"])
@require_auth
def list_recurring(user_id):
    """Return all recurring bookings for the authenticated user."""
    include_inactive = request.args.get("include_inactive", "false").lower() == "true"

    query = RecurringBooking.query.filter_by(customer_id=user_id)
    if not include_inactive:
        query = query.filter_by(is_active=True)

    bookings = query.order_by(RecurringBooking.created_at.desc()).all()
    return jsonify({
        "success": True,
        "recurring_bookings": [b.to_dict() for b in bookings],
    }), 200


# ---------------------------------------------------------------------------
# GET /api/recurring/<id>  -- Get single recurring booking
# ---------------------------------------------------------------------------
@recurring_bp.route("/<recurring_id>", methods=["GET"])
@require_auth
def get_recurring(user_id, recurring_id):
    """Return a single recurring booking (must belong to user)."""
    recurring = db.session.get(RecurringBooking, recurring_id)
    if not recurring:
        return jsonify({"error": "Recurring booking not found"}), 404
    if recurring.customer_id != user_id:
        return jsonify({"error": "Not authorized"}), 403

    return jsonify({"success": True, "recurring_booking": recurring.to_dict()}), 200


# ---------------------------------------------------------------------------
# PUT /api/recurring/<id>  -- Update recurring booking
# ---------------------------------------------------------------------------
@recurring_bp.route("/<recurring_id>", methods=["PUT"])
@require_auth
def update_recurring(user_id, recurring_id):
    """Update a recurring booking's details.

    Updatable fields: frequency, day_of_week, day_of_month, preferred_time,
    address, lat, lng, items, notes, is_active.
    """
    recurring = db.session.get(RecurringBooking, recurring_id)
    if not recurring:
        return jsonify({"error": "Recurring booking not found"}), 404
    if recurring.customer_id != user_id:
        return jsonify({"error": "Not authorized"}), 403

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    recalc_schedule = False

    # --- Frequency ---
    if "frequency" in data:
        if data["frequency"] not in VALID_FREQUENCIES:
            return jsonify({"error": "frequency must be one of: weekly, biweekly, monthly"}), 400
        recurring.frequency = data["frequency"]
        recalc_schedule = True

    # --- Day of week ---
    if "day_of_week" in data:
        dow = data["day_of_week"]
        if dow is not None:
            try:
                dow = int(dow)
            except (TypeError, ValueError):
                return jsonify({"error": "day_of_week must be an integer 0-6"}), 400
            if not (0 <= dow <= 6):
                return jsonify({"error": "day_of_week must be between 0 and 6"}), 400
        recurring.day_of_week = dow
        recalc_schedule = True

    # --- Day of month ---
    if "day_of_month" in data:
        dom = data["day_of_month"]
        if dom is not None:
            try:
                dom = int(dom)
            except (TypeError, ValueError):
                return jsonify({"error": "day_of_month must be an integer 1-28"}), 400
            if not (1 <= dom <= 28):
                return jsonify({"error": "day_of_month must be between 1 and 28"}), 400
        recurring.day_of_month = dom
        recalc_schedule = True

    # --- Preferred time ---
    if "preferred_time" in data:
        recurring.preferred_time = data["preferred_time"]
        recalc_schedule = True

    # --- Address / location ---
    if "address" in data:
        if not data["address"]:
            return jsonify({"error": "address cannot be empty"}), 400
        recurring.address = data["address"]
    if "lat" in data:
        recurring.lat = float(data["lat"]) if data["lat"] is not None else None
    if "lng" in data:
        recurring.lng = float(data["lng"]) if data["lng"] is not None else None

    # --- Items / notes ---
    if "items" in data:
        recurring.items = data["items"]
    if "notes" in data:
        recurring.notes = data["notes"]

    # --- Active status ---
    if "is_active" in data:
        recurring.is_active = bool(data["is_active"])
        if recurring.is_active:
            recalc_schedule = True

    # Recompute next_scheduled_at if schedule parameters changed
    if recalc_schedule and recurring.is_active:
        recurring.next_scheduled_at = _compute_next_scheduled(
            recurring.frequency,
            recurring.day_of_week,
            recurring.day_of_month,
            recurring.preferred_time,
        )

    db.session.commit()
    return jsonify({"success": True, "recurring_booking": recurring.to_dict()}), 200


# ---------------------------------------------------------------------------
# DELETE /api/recurring/<id>  -- Cancel (soft delete)
# ---------------------------------------------------------------------------
@recurring_bp.route("/<recurring_id>", methods=["DELETE"])
@require_auth
def delete_recurring(user_id, recurring_id):
    """Soft-delete a recurring booking by setting is_active=False."""
    recurring = db.session.get(RecurringBooking, recurring_id)
    if not recurring:
        return jsonify({"error": "Recurring booking not found"}), 404
    if recurring.customer_id != user_id:
        return jsonify({"error": "Not authorized"}), 403

    recurring.is_active = False
    db.session.commit()

    return jsonify({"success": True, "message": "Recurring booking cancelled"}), 200


# ---------------------------------------------------------------------------
# Recurring job materialisation engine
# ---------------------------------------------------------------------------
# Shared by POST /api/recurring/generate-next and scheduler._generate_recurring_jobs
# so there is exactly ONE implementation of "turn a due recurring booking into
# a real, priced, payable, dispatched job" (audit F24).
#
# What a due occurrence produces:
#   1. A ``recurring_occurrences`` claim on (schedule_id, occurrence_at) — the
#      uniqueness key. Running the sweep twice creates one job, not two.
#   2. A real price from routes.booking.calculate_estimate — the same function
#      the live booking funnel uses. Never $0.
#   3. A Payment for that real amount. If the customer has a saved card we
#      charge it off-session and the job goes straight to ``confirmed`` +
#      dispatch. If they don't, the job is ``awaiting_payment`` and they get a
#      pay link — instead of a $0 "pending" Payment row that looks settled.
#   4. Dispatch (dispatcher.auto_assign_job_async) for jobs that are paid for.
# ---------------------------------------------------------------------------


def _claim_occurrence(recurring, occurrence_at):
    """Claim (booking id, occurrence_at). None when another run owns it."""
    from sqlalchemy.exc import IntegrityError

    occ = RecurringOccurrence(
        kind="residential", schedule_id=recurring.id,
        occurrence_at=occurrence_at, status="created",
    )
    try:
        with db.session.begin_nested():
            db.session.add(occ)
            db.session.flush()
        return occ
    except IntegrityError:
        logger.info(
            "recurring: occurrence already claimed booking=%s at=%s — skipping",
            recurring.id, occurrence_at,
        )
        return None


def _price_occurrence(recurring):
    """Price this pickup with the live estimator. Returns the estimate dict.

    Imports routes.booking lazily: booking.py owns the pricing rules and we
    must never fork them (a second copy is how recurring drifted to $0).
    """
    from routes.booking import calculate_estimate

    return calculate_estimate(
        recurring.items or [],
        scheduled_date=recurring.next_scheduled_at,
        lat=recurring.lat,
        lng=recurring.lng,
    )


def _saved_payment_method(customer):
    """Return (stripe_module, customer_id, payment_method_id) when the customer
    has a card we may charge off-session, else (None, None, None)."""
    if not customer or not getattr(customer, "stripe_customer_id", None):
        return None, None, None
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not key:
        return None, None, None
    try:
        import stripe
        stripe.api_key = key
        methods = stripe.PaymentMethod.list(
            customer=customer.stripe_customer_id, type="card", limit=1,
        )
        items = getattr(methods, "data", None) or []
        if not items:
            return None, None, None
        pm_id = items[0].id if hasattr(items[0], "id") else items[0].get("id")
        return stripe, customer.stripe_customer_id, pm_id
    except Exception:
        logger.exception("recurring: could not look up saved card for %s",
                         getattr(customer, "id", "?"))
        return None, None, None


def _charge_off_session(customer, job, amount):
    """Charge the customer's saved card for a recurring pickup.

    Returns the PaymentIntent id on success, None otherwise (no card, no
    Stripe key, declined, or authentication required). Never raises.
    """
    stripe, customer_id, pm_id = _saved_payment_method(customer)
    if not stripe:
        return None
    try:
        intent = stripe.PaymentIntent.create(
            amount=int(round(float(amount) * 100)),
            currency="usd",
            customer=customer_id,
            payment_method=pm_id,
            off_session=True,
            confirm=True,
            description="Umuve recurring pickup",
            metadata={"job_id": job.id, "booking_id": job.id, "source": "recurring"},
            idempotency_key="recurring-{}".format(job.id),
        )
        if getattr(intent, "status", None) == "succeeded":
            return intent.id
        logger.warning("recurring: off-session charge for job %s ended in status %s",
                       job.id, getattr(intent, "status", "?"))
        return None
    except Exception:
        # CardError / authentication_required / anything else: fall back to a
        # pay link rather than silently booking unpaid work.
        logger.exception("recurring: off-session charge failed for job %s", job.id)
        return None


def _send_pay_link(customer, job, amount):
    """Text/email the customer a Stripe Checkout link for this pickup.

    Reuses the same checkout-link builder Maya's phone bookings use, so the
    payment reconciles through the existing webhook path. Never raises.
    """
    if not customer:
        return False
    try:
        from routes.vapi import _build_checkout_url
        url = _build_checkout_url(job.id, amount)
    except Exception:
        logger.exception("recurring: could not build pay link for job %s", job.id)
        return False

    when = ""
    try:
        when = " on {}".format(to_local(job.scheduled_at).strftime("%a %b %-d"))
    except Exception:
        pass
    message = (
        "Umuve: your recurring pickup{} is scheduled. Total ${:.2f}. "
        "Pay here to lock it in: {}".format(when, float(amount), url)
    )
    sent = False
    if getattr(customer, "phone", None):
        try:
            from sms_service import send_sms_async
            send_sms_async(customer.phone, message)
            sent = True
        except Exception:
            logger.exception("recurring: pay-link SMS failed for job %s", job.id)
    if getattr(customer, "email", None):
        try:
            from notifications import send_email
            send_email(
                customer.email,
                "Your Umuve recurring pickup — payment needed",
                "<p>Your recurring pickup{} is scheduled at {}.</p>"
                "<p><strong>Total: ${:.2f}</strong></p>"
                '<p><a href="{}">Pay now to confirm</a></p>'.format(
                    when, job.address, float(amount), url),
            )
            sent = True
        except Exception:
            logger.exception("recurring: pay-link email failed for job %s", job.id)
    return sent


def sweep_paid_awaiting_payment_jobs():
    """Confirm + dispatch recurring jobs whose pay link has since been paid.

    ``_handle_payment_succeeded`` marks the Payment succeeded but only moves a
    job out of ``pending``, so an ``awaiting_payment`` recurring job would
    otherwise stay parked after the customer pays. Returns the job ids
    confirmed. Never raises.
    """
    confirmed = []
    try:
        rows = (
            db.session.query(Job)
            .join(Payment, Payment.job_id == Job.id)
            .filter(Job.status == "awaiting_payment",
                    Payment.payment_status == "succeeded")
            .limit(200)
            .all()
        )
        for job in rows:
            job.status = "confirmed"
            job.updated_at = utcnow()
            confirmed.append(job.id)
        if confirmed:
            db.session.commit()
            _dispatch_jobs(confirmed)
    except Exception:
        logger.exception("recurring: awaiting-payment sweep failed")
        db.session.rollback()
    return confirmed


def _dispatch_jobs(job_ids):
    """Hand paid jobs to the dispatcher (respects DISPATCH_MODE). Never raises."""
    if not job_ids:
        return
    try:
        from flask import current_app
        from dispatcher import auto_assign_job_async
        app_obj = current_app._get_current_object()
    except Exception:
        logger.exception("Could not import dispatcher for recurring jobs")
        return
    for job_id in job_ids:
        try:
            auto_assign_job_async(job_id, app_obj)
        except Exception:
            logger.exception("Recurring dispatch failed for job %s", job_id)


def generate_due_recurring_jobs(now=None):
    """Materialise every due residential recurring booking.

    Returns ``{"created": [job_id, ...], "dispatched": [job_id, ...],
    "awaiting_payment": [job_id, ...]}``.

    Each occurrence runs in its own savepoint, so one booking that blows up
    (bad address, pricing error) cannot discard the jobs already built in the
    same sweep.
    """
    now = now or datetime.now(timezone.utc)

    # Anything paid via a link since the last sweep gets confirmed + dispatched.
    sweep_paid_awaiting_payment_jobs()

    due_bookings = RecurringBooking.query.filter(
        RecurringBooking.is_active == True,  # noqa: E712
        RecurringBooking.next_scheduled_at <= now,
    ).all()

    created, to_dispatch, awaiting = [], [], []

    for recurring in due_bookings:
        occurrence_at = recurring.next_scheduled_at
        occ = _claim_occurrence(recurring, occurrence_at)
        if occ is None:
            continue

        job_id = None
        charged_intent = None
        amount = 0.0
        try:
            with db.session.begin_nested():
                estimate = _price_occurrence(recurring)
                amount = float(estimate.get("total") or 0.0)

                job = Job(
                    id=generate_uuid(),
                    customer_id=recurring.customer_id,
                    status="pending",
                    address=recurring.address,
                    lat=recurring.lat,
                    lng=recurring.lng,
                    items=recurring.items,
                    scheduled_at=occurrence_at,
                    notes="[Recurring] {}".format(recurring.notes or ""),
                    base_price=float(estimate.get("base_price") or 0.0),
                    item_total=float(estimate.get("items_subtotal") or 0.0),
                    service_fee=float(estimate.get("service_fee") or 0.0),
                    surge_multiplier=float(estimate.get("surge_multiplier") or 1.0),
                    total_price=amount,
                )
                db.session.add(job)
                db.session.flush()

                customer = db.session.get(User, recurring.customer_id)
                charged_intent = _charge_off_session(customer, job, amount)

                payment = Payment(
                    id=generate_uuid(),
                    job_id=job.id,
                    amount=amount,
                    service_fee=float(estimate.get("service_fee") or 0.0),
                    stripe_payment_intent_id=charged_intent,
                    payment_status="succeeded" if charged_intent else "pending",
                )
                db.session.add(payment)

                if charged_intent:
                    job.status = "confirmed"
                    occ.status = "created"
                else:
                    # Honest state: the work is scheduled but unpaid. Never a
                    # $0 "pending" payment masquerading as settled.
                    job.status = "awaiting_payment"
                    occ.status = "awaiting_payment"

                occ.job_id = job.id
                occ.detail = "total={:.2f}".format(amount)
                recurring.total_bookings_created = (recurring.total_bookings_created or 0) + 1
                _advance_next_scheduled(recurring)
                job_id = job.id
        except Exception as exc:
            logger.exception("recurring: failed booking=%s: %s", recurring.id, exc)
            try:
                occ.status = "failed"
                occ.detail = str(exc)[:500]
                _advance_next_scheduled(recurring)
            except Exception:  # pragma: no cover
                logger.exception("recurring: could not mark occurrence failed")
            continue

        created.append(job_id)
        if charged_intent:
            to_dispatch.append(job_id)
        else:
            awaiting.append((job_id, recurring.customer_id, amount))

    db.session.commit()

    # Post-commit side effects: pay links for unpaid jobs, dispatch for paid.
    awaiting_ids = []
    for job_id, customer_id, amount in awaiting:
        awaiting_ids.append(job_id)
        try:
            job = db.session.get(Job, job_id)
            customer = db.session.get(User, customer_id)
            _send_pay_link(customer, job, amount)
        except Exception:
            logger.exception("recurring: pay-link delivery failed for job %s", job_id)

    _dispatch_jobs(to_dispatch)

    return {"created": created, "dispatched": to_dispatch,
            "awaiting_payment": awaiting_ids}


# ---------------------------------------------------------------------------
# POST /api/recurring/generate-next  -- Admin/cron: generate jobs
# ---------------------------------------------------------------------------
@recurring_bp.route("/generate-next", methods=["POST"])
@_require_admin
def generate_next_jobs(user_id):
    """Generate Job records from all active recurring bookings that are due.

    Intended to be called by a cron job or scheduler.  Delegates to
    ``generate_due_recurring_jobs`` so this endpoint and the in-process
    scheduler share one implementation (pricing, payment, dispatch included).
    """
    result = generate_due_recurring_jobs()

    jobs = []
    for job_id in result["created"]:
        job = db.session.get(Job, job_id)
        if job is not None:
            jobs.append(job.to_dict())

    return jsonify({
        "success": True,
        "jobs_created": len(jobs),
        "jobs_dispatched": len(result["dispatched"]),
        "jobs_awaiting_payment": len(result["awaiting_payment"]),
        "jobs": jobs,
    }), 200
