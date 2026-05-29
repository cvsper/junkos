"""
Umuve AI Auto-Dispatch System

Uber-style dispatch: when a job is confirmed, automatically find and assign
the best available operator/driver based on proximity, truck capacity, rating,
and experience.  The operator gets notified (not asked) — they can decline
in the app later.

IMPORTANT: No function in this module should ever raise an exception.
All errors are caught and logged so that a dispatch failure never takes down
a booking or payment flow.
"""

import math
import logging
import threading
from datetime import timedelta

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------
WEIGHT_DISTANCE = 0.40
WEIGHT_RATING = 0.25
WEIGHT_CAPACITY = 0.20
WEIGHT_EXPERIENCE = 0.15

# Constraints
MAX_RADIUS_MILES = 30.0
SCHEDULE_CONFLICT_HOURS = 2  # hours around scheduled_at to check for conflicts
EXPERIENCE_CAP = 500  # total_jobs at which experience score = 1.0

# Admin notification contacts (set via env vars)
import os
ADMIN_PHONE = os.environ.get("ADMIN_PHONE", "")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")


# ---------------------------------------------------------------------------
# Haversine
# ---------------------------------------------------------------------------
def haversine(lat1, lng1, lat2, lng2):
    """Return the great-circle distance in miles between two GPS points.

    Never raises — returns float('inf') on bad input.
    """
    try:
        R_MILES = 3958.8  # Earth radius in miles
        lat1, lng1, lat2, lng2 = (
            math.radians(float(lat1)),
            math.radians(float(lng1)),
            math.radians(float(lat2)),
            math.radians(float(lng2)),
        )
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
        )
        return 2 * R_MILES * math.asin(math.sqrt(a))
    except Exception:
        logger.exception("haversine calculation failed")
        return float("inf")


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------
def _distance_score(distance_miles):
    """0.0 – 1.0.  Closer = higher.  Beyond MAX_RADIUS_MILES = 0."""
    if distance_miles > MAX_RADIUS_MILES:
        return 0.0
    return max(0.0, 1.0 - (distance_miles / MAX_RADIUS_MILES))


def _rating_score(avg_rating):
    """Normalise avg_rating (1-5) to 0-1.  None/0 → 0.5 (neutral)."""
    if not avg_rating or avg_rating <= 0:
        return 0.5
    return max(0.0, min(1.0, (float(avg_rating) - 1.0) / 4.0))


def _capacity_score(truck_capacity, volume_estimate):
    """Score how well the truck fits the job.

    - truck >= volume → 1.0 (exact or slight overshoot)
    - truck > volume * 1.5 → 0.8 (oversized)
    - truck < volume → 0.0 (undersized, disqualified)
    - No volume_estimate → 1.0 for everyone (skip this factor)
    """
    if not volume_estimate or volume_estimate <= 0:
        return 1.0  # no volume info — everyone qualifies
    if not truck_capacity or truck_capacity <= 0:
        return 0.5  # unknown truck capacity — neutral
    cap = float(truck_capacity)
    vol = float(volume_estimate)
    if cap < vol:
        return 0.0  # can't fit the load
    if cap <= vol * 1.5:
        return 1.0  # good match
    return 0.8  # oversized but acceptable


def _experience_score(total_jobs):
    """Log-scale score capped at EXPERIENCE_CAP jobs."""
    if not total_jobs or total_jobs <= 0:
        return 0.0
    jobs = min(float(total_jobs), EXPERIENCE_CAP)
    # log(1) = 0, log(501) ≈ 6.2 → normalise
    return math.log(jobs + 1) / math.log(EXPERIENCE_CAP + 1)


# ---------------------------------------------------------------------------
# Conflict check
# ---------------------------------------------------------------------------
def _has_schedule_conflict(contractor, scheduled_at, Job):
    """Return True if contractor has a job within SCHEDULE_CONFLICT_HOURS of scheduled_at.

    Never raises.
    """
    try:
        if not scheduled_at:
            # No schedule — only check for currently active jobs
            active = Job.query.filter(
                Job.driver_id == contractor.id,
                Job.status.in_(["accepted", "en_route", "arrived", "started"]),
            ).first()
            return active is not None

        window_start = scheduled_at - timedelta(hours=SCHEDULE_CONFLICT_HOURS)
        window_end = scheduled_at + timedelta(hours=SCHEDULE_CONFLICT_HOURS)

        conflicting = Job.query.filter(
            Job.driver_id == contractor.id,
            Job.status.in_(["assigned", "accepted", "en_route", "arrived", "started"]),
            Job.scheduled_at.isnot(None),
            Job.scheduled_at >= window_start,
            Job.scheduled_at <= window_end,
        ).first()

        if conflicting:
            return True

        # Also check for active jobs with no schedule (currently working)
        active = Job.query.filter(
            Job.driver_id == contractor.id,
            Job.status.in_(["en_route", "arrived", "started"]),
        ).first()
        return active is not None

    except Exception:
        logger.exception(
            "Schedule conflict check failed for contractor %s", contractor.id
        )
        return False  # fail open — don't disqualify on error


# ---------------------------------------------------------------------------
# Core: find_best_operator
# ---------------------------------------------------------------------------
def find_best_operator(job):
    """Score and rank available operators/drivers for the given job.

    Returns a list of up to 3 candidate dicts:
        [{"contractor": <Contractor>, "score": float, "breakdown": {...}}, ...]

    Returns an empty list if no candidates qualify.  Never raises.
    """
    try:
        from models import Contractor, Job as JobModel

        # Build base query: approved, online
        query = Contractor.query.filter_by(
            is_online=True,
            approval_status="approved",
        )

        # Scope to operator fleet if job belongs to an operator
        if job.operator_id:
            query = query.filter_by(operator_id=job.operator_id)
        else:
            # Independent contractors (not operators themselves, not in a fleet)
            query = query.filter(
                Contractor.is_operator.is_(False),
                Contractor.operator_id.is_(None),
            )

        contractors = query.all()

        if not contractors:
            logger.info(
                "No online approved contractors found for job %s",
                job.id,
            )
            return []

        candidates = []
        for c in contractors:
            # --- Disqualifiers ---

            # Schedule conflict
            if _has_schedule_conflict(c, job.scheduled_at, JobModel):
                logger.debug(
                    "Contractor %s disqualified: schedule conflict", c.id
                )
                continue

            # Distance check (requires both locations)
            dist = float("inf")
            if (
                job.lat is not None
                and job.lng is not None
                and c.current_lat is not None
                and c.current_lng is not None
            ):
                dist = haversine(c.current_lat, c.current_lng, job.lat, job.lng)
                if dist > MAX_RADIUS_MILES:
                    logger.debug(
                        "Contractor %s disqualified: %.1f mi > %d mi radius",
                        c.id, dist, MAX_RADIUS_MILES,
                    )
                    continue
            else:
                # No location data — use neutral distance score
                dist = MAX_RADIUS_MILES * 0.5  # middle-of-range default

            # Capacity hard-disqualify
            cap = _capacity_score(c.truck_capacity, job.volume_estimate)
            if cap == 0.0:
                logger.debug(
                    "Contractor %s disqualified: truck too small (%.1f < %.1f)",
                    c.id,
                    c.truck_capacity or 0,
                    job.volume_estimate or 0,
                )
                continue

            # --- Score ---
            d_score = _distance_score(dist)
            r_score = _rating_score(c.avg_rating)
            e_score = _experience_score(c.total_jobs)

            total = (
                d_score * WEIGHT_DISTANCE
                + r_score * WEIGHT_RATING
                + cap * WEIGHT_CAPACITY
                + e_score * WEIGHT_EXPERIENCE
            )

            candidates.append({
                "contractor": c,
                "score": round(total, 4),
                "breakdown": {
                    "distance_miles": round(dist, 1),
                    "distance_score": round(d_score, 3),
                    "rating_score": round(r_score, 3),
                    "capacity_score": round(cap, 3),
                    "experience_score": round(e_score, 3),
                },
            })

        # Sort descending by score
        candidates.sort(key=lambda c: c["score"], reverse=True)

        top = candidates[:3]
        if top:
            logger.info(
                "Dispatch candidates for job %s: %s",
                job.id,
                [
                    {"id": c["contractor"].id, "score": c["score"]}
                    for c in top
                ],
            )
        else:
            logger.info(
                "No qualifying contractors for job %s (checked %d)",
                job.id,
                len(contractors),
            )

        return top

    except Exception:
        logger.exception("find_best_operator failed for job %s", job.id)
        return []


# ---------------------------------------------------------------------------
# Core: auto_assign_job
# ---------------------------------------------------------------------------
def auto_assign_job(job_id, app=None):
    """Auto-assign the best operator to a confirmed job.

    This is designed to run in a background thread.  If ``app`` is provided
    it will push a Flask application context; otherwise it assumes a context
    is already active.

    Never raises.
    """
    try:
        from models import db, Job, Notification, generate_uuid, utcnow

        def _do_assign():
            job = db.session.get(Job, job_id)
            if not job:
                logger.warning("auto_assign_job: job %s not found", job_id)
                return
            if job.driver_id:
                logger.info(
                    "auto_assign_job: job %s already assigned to %s, skipping",
                    job_id, job.driver_id,
                )
                return
            if job.status not in ("confirmed", "pending"):
                logger.info(
                    "auto_assign_job: job %s status is '%s', skipping",
                    job_id, job.status,
                )
                return

            candidates = find_best_operator(job)

            if not candidates:
                logger.warning(
                    "auto_assign_job: no operators available for job %s at %s",
                    job_id, job.address,
                )
                # Notify admin
                _notify_admin_no_operators(job)
                return

            # Assign top candidate
            best = candidates[0]
            contractor = best["contractor"]

            job.driver_id = contractor.id
            job.status = "assigned"
            job.updated_at = utcnow()

            # Log the dispatch decision
            logger.info(
                "DISPATCH: job %s -> contractor %s (score=%.4f, "
                "dist=%.1f mi, rating=%.3f, capacity=%.3f, exp=%.3f)",
                job.id,
                contractor.id,
                best["score"],
                best["breakdown"]["distance_miles"],
                best["breakdown"]["rating_score"],
                best["breakdown"]["capacity_score"],
                best["breakdown"]["experience_score"],
            )

            # In-app notification to driver
            notification = Notification(
                id=generate_uuid(),
                user_id=contractor.user_id,
                type="job_assigned",
                title="New Job Assigned",
                body="You've been assigned a job at {}.".format(
                    job.address or "an address"
                ),
                data={
                    "job_id": job.id,
                    "address": job.address,
                    "total_price": job.total_price,
                    "dispatch_score": best["score"],
                },
            )
            db.session.add(notification)

            # In-app notification to customer
            notification_cust = Notification(
                id=generate_uuid(),
                user_id=job.customer_id,
                type="job_update",
                title="Driver Assigned",
                body="A driver has been assigned to your job.",
                data={"job_id": job.id, "status": "assigned"},
            )
            db.session.add(notification_cust)

            db.session.commit()

            # --- SMS to operator ---
            _sms_operator_assigned(contractor, job)

            # --- Push notification to driver ---
            try:
                from notifications import send_push_notification
                send_push_notification(
                    contractor.user_id,
                    "New Job Assigned",
                    "New job at {}. Open the app to view details.".format(
                        job.address or "a location"
                    ),
                    {"job_id": job.id, "type": "job_assigned"},
                )
            except Exception:
                logger.exception(
                    "Failed to send push to contractor %s for job %s",
                    contractor.id, job.id,
                )

            # --- Email to customer ---
            try:
                from models import User
                customer = db.session.get(User, job.customer_id)
                if customer and customer.email:
                    from notifications import send_driver_assigned_email
                    send_driver_assigned_email(
                        customer.email,
                        customer.name,
                        contractor.user.name if contractor.user else "Your driver",
                        job.address,
                        truck_type=contractor.truck_type,
                    )
            except Exception:
                logger.exception(
                    "Failed to send assignment email for job %s", job.id
                )

            # --- SocketIO events ---
            try:
                from socket_events import socketio
                socketio.emit(
                    "job:assigned",
                    {
                        "job_id": job.id,
                        "contractor_id": contractor.id,
                        "contractor_name": (
                            contractor.user.name if contractor.user else None
                        ),
                    },
                    room="driver:{}".format(contractor.id),
                )
                socketio.emit(
                    "job:status",
                    {
                        "job_id": job.id,
                        "status": "assigned",
                        "driver_id": contractor.id,
                    },
                    room=job.id,
                )
            except Exception:
                logger.exception(
                    "Failed to emit socket events for job %s", job.id
                )

        # Execute with or without app context
        if app:
            with app.app_context():
                _do_assign()
        else:
            _do_assign()

    except Exception:
        logger.exception("auto_assign_job failed for job %s", job_id)


def auto_assign_job_async(job_id, app):
    """Fire auto_assign_job in a background thread.

    Same pattern as sms_service.send_sms_async().  Never raises.
    """
    try:
        t = threading.Thread(
            target=auto_assign_job,
            args=(job_id, app),
            daemon=True,
        )
        t.start()
        logger.info("Dispatched background auto-assign thread for job %s", job_id)
        return t
    except Exception:
        logger.exception(
            "Failed to start auto-assign thread for job %s", job_id
        )
        return None


# ---------------------------------------------------------------------------
# SMS helpers
# ---------------------------------------------------------------------------
def _sms_operator_assigned(contractor, job):
    """SMS the operator that a new job has been assigned to them.

    Never raises.
    """
    try:
        from sms_service import send_sms_async

        phone = None
        if contractor.user:
            phone = contractor.user.phone
        if not phone:
            logger.info(
                "No phone for contractor %s, skipping assignment SMS",
                contractor.id,
            )
            return

        # Format the date nicely
        date_str = "TBD"
        if job.scheduled_at:
            date_str = job.scheduled_at.strftime("%b %d at %I:%M %p")

        body = (
            "New job assigned! {} on {}. "
            "Open the app to accept."
        ).format(job.address or "Address TBD", date_str)

        send_sms_async(phone, body)
    except Exception:
        logger.exception(
            "Failed to send assignment SMS to contractor %s for job %s",
            contractor.id, job.id,
        )


def _notify_admin_no_operators(job):
    """Alert admin (SMS + email) when no operators are available for a job.

    Fires on every configured channel (ADMIN_PHONE, ADMIN_EMAIL) so a single
    misconfiguration or provider hiccup can't swallow the alert silently. If
    NOTHING is configured, logs at error level so the gap is visible.

    Never raises.
    """
    short_id = str(job.id)[:8]

    # --- Gather actionable detail (all guarded; the alert must fire even if sparse) ---
    address = getattr(job, "address", None) or "unknown address"
    code = getattr(job, "confirmation_code", None) or short_id
    try:
        amount = "${:.2f}".format(float(job.total_price)) if getattr(job, "total_price", None) else "unknown"
    except (TypeError, ValueError):
        amount = "unknown"
    sched = (
        job.scheduled_at.strftime("%b %d at %I:%M %p")
        if getattr(job, "scheduled_at", None) else "ASAP/TBD"
    )

    customer_name = ""
    customer_phone = ""
    try:
        customer = getattr(job, "customer", None)
        if customer is not None:
            customer_name = getattr(customer, "name", "") or ""
            customer_phone = getattr(customer, "phone", "") or ""
    except Exception:
        pass

    if not ADMIN_PHONE and not ADMIN_EMAIL:
        logger.error(
            "UNASSIGNED PAID JOB #%s (%s, %s) but NO ADMIN_PHONE/ADMIN_EMAIL "
            "configured — alert cannot be delivered. Set one in the environment.",
            code, address, amount,
        )
        return

    # --- SMS channel ---
    if ADMIN_PHONE:
        try:
            from sms_service import send_sms_async
            sms_body = (
                "umuve ALERT: No operator for job #{} ({}). {} — {}. "
                "Scramble a hauler or refund."
            ).format(code, address, amount, sched)
            send_sms_async(ADMIN_PHONE, sms_body)
        except Exception:
            logger.exception("Failed to SMS admin about unassigned job %s", job.id)

    # --- Email channel ---
    if ADMIN_EMAIL:
        try:
            from email_service import send_email_async
            subject = "⚠️ Unassigned job #{} — no operator available".format(code)
            html = (
                "<h2>No operator available for a paid booking</h2>"
                "<p>A customer booked and paid, but no approved/online contractor "
                "could be assigned. Manual action needed — scramble a hauler or "
                "refund before they get frustrated.</p>"
                "<table cellpadding='6' style='font-family:sans-serif;font-size:14px'>"
                "<tr><td><b>Booking</b></td><td>#{code}</td></tr>"
                "<tr><td><b>Amount</b></td><td>{amount}</td></tr>"
                "<tr><td><b>Address</b></td><td>{address}</td></tr>"
                "<tr><td><b>Scheduled</b></td><td>{sched}</td></tr>"
                "<tr><td><b>Customer</b></td><td>{cname} {cphone}</td></tr>"
                "</table>"
            ).format(
                code=code, amount=amount, address=address, sched=sched,
                cname=customer_name, cphone=customer_phone,
            )
            send_email_async(ADMIN_EMAIL, subject, html)
        except Exception:
            logger.exception("Failed to email admin about unassigned job %s", job.id)


# ---------------------------------------------------------------------------
# Coverage-aware booking gate (used pre-payment by routes/booking.py)
# ---------------------------------------------------------------------------
def has_active_coverage(lat, lng, radius_miles=MAX_RADIUS_MILES):
    """Return True if any approved contractor's last-known location is within
    ``radius_miles`` of ``(lat, lng)``.

    Used pre-payment to decide whether a booking has any chance of being
    fulfilled. Independent of ``is_online`` — an offline-but-approved
    contractor who serves the area still counts as coverage (signals supply
    exists, even if not broadcasting right now). The runtime auto-assigner
    separately handles whether a contractor is reachable *at this moment*.

    Fails open (returns True) on any error — better to risk one missed-coverage
    edge case than to break the entire booking funnel.
    """
    try:
        if lat is None or lng is None:
            return True
        try:
            lat_f = float(lat)
            lng_f = float(lng)
        except (TypeError, ValueError):
            return True

        from models import Contractor
        contractors = Contractor.query.filter_by(approval_status="approved").all()
        for c in contractors:
            if c.current_lat is None or c.current_lng is None:
                continue
            if haversine(lat_f, lng_f, c.current_lat, c.current_lng) <= radius_miles:
                return True
        return False
    except Exception:
        logger.exception(
            "has_active_coverage check failed for (%s, %s) — failing open",
            lat, lng,
        )
        return True


def _notify_admin_no_coverage_lead(
    address, lat=None, lng=None,
    customer_email="", customer_phone="", customer_name="",
    items=None, estimated_price=None,
):
    """Alert admin (SMS + email) when a pre-payment lead lands in an uncovered area.

    Counterpart to ``_notify_admin_no_operators`` for the waitlist case: no Job
    record exists, no charge has happened, and the customer has been told
    we'll text them a confirmed time within 2 hours.

    Never raises.
    """
    if not ADMIN_PHONE and not ADMIN_EMAIL:
        logger.error(
            "NO-COVERAGE LEAD at %s (%s, %s) but NO ADMIN_PHONE/ADMIN_EMAIL "
            "configured — alert cannot be delivered. Set one in the environment.",
            address, lat, lng,
        )
        return

    try:
        amount_str = (
            "${:.2f}".format(float(estimated_price))
            if estimated_price else "estimate pending"
        )
    except (TypeError, ValueError):
        amount_str = "estimate pending"

    contact = " / ".join(
        c for c in [customer_name, customer_phone, customer_email] if c
    ) or "unknown"

    # --- SMS channel ---
    if ADMIN_PHONE:
        try:
            from sms_service import send_sms_async
            sms_body = (
                "umuve WAITLIST: lead in uncovered area. {} (no contractor in "
                "range). Est {}. Contact: {}. No charge — reach out within 2hrs "
                "or refer."
            ).format(address, amount_str, contact)
            send_sms_async(ADMIN_PHONE, sms_body)
        except Exception:
            logger.exception(
                "Failed to SMS admin about no-coverage lead at %s", address,
            )

    # --- Email channel ---
    if ADMIN_EMAIL:
        try:
            from email_service import send_email_async
            subject = "⚠️ No-coverage waitlist lead — {}".format(
                (address or "unknown")[:60]
            )
            html = (
                "<h2>Customer tried to book in an area we don't have a hauler for</h2>"
                "<p><b>No charge was made.</b> Customer has been told we'll text "
                "them a confirmed time within 2 hours. Action: reach out, refer "
                "to a partner, or scramble a contractor.</p>"
                "<table cellpadding='6' style='font-family:sans-serif;font-size:14px'>"
                "<tr><td><b>Address</b></td><td>{address}</td></tr>"
                "<tr><td><b>Estimate</b></td><td>{amount}</td></tr>"
                "<tr><td><b>Customer</b></td><td>{contact}</td></tr>"
                "<tr><td><b>Items</b></td><td>{items}</td></tr>"
                "</table>"
            ).format(
                address=address or "unknown",
                amount=amount_str,
                contact=contact,
                items=str(items or "—"),
            )
            send_email_async(ADMIN_EMAIL, subject, html)
        except Exception:
            logger.exception(
                "Failed to email admin about no-coverage lead at %s", address,
            )


def _notify_admin_late_job(job, minutes_late):
    """Alert admin when a scheduled job is past its start time with no progress.

    Counterpart to ``_notify_admin_no_operators`` for the post-scheduled-time
    case: the job had an assignment (or didn't, doesn't matter), but the
    real-world status hasn't moved to "started" / "completed". Almost always
    means the contractor is silently no-showing.

    Channels: SMS (OPERATOR_PHONE → ADMIN_PHONE fallback) + email (ADMIN_EMAIL).
    Never raises.
    """
    short_id = str(getattr(job, "id", ""))[:8]
    code = getattr(job, "confirmation_code", None) or short_id
    address = getattr(job, "address", None) or "unknown address"

    try:
        amount = (
            "${:.2f}".format(float(job.total_price))
            if getattr(job, "total_price", None) else "unknown"
        )
    except (TypeError, ValueError):
        amount = "unknown"

    sched = (
        job.scheduled_at.strftime("%b %d at %I:%M %p")
        if getattr(job, "scheduled_at", None) else "unknown time"
    )

    # Try to surface the assigned contractor (if any) so sevs knows who to chase.
    assigned_label = "unassigned"
    try:
        if getattr(job, "driver_id", None) or getattr(job, "operator_id", None):
            assigned_label = "assigned (driver={} / operator={})".format(
                getattr(job, "driver_id", None) or "—",
                getattr(job, "operator_id", None) or "—",
            )
    except Exception:
        pass

    customer_name = ""
    customer_phone = ""
    try:
        customer = getattr(job, "customer", None)
        if customer is not None:
            customer_name = getattr(customer, "name", "") or ""
            customer_phone = getattr(customer, "phone", "") or ""
    except Exception:
        pass

    if not ADMIN_PHONE and not ADMIN_EMAIL:
        logger.error(
            "LATE JOB #%s (%s, %d min late, %s) but NO ADMIN_PHONE/ADMIN_EMAIL "
            "configured — alert cannot be delivered.",
            code, address, minutes_late, assigned_label,
        )
        return

    if ADMIN_PHONE:
        try:
            from sms_service import send_sms_async
            sms_body = (
                "🚨 umuve LATE JOB #{} — {} min past scheduled "
                "({}). {} — {}. Status={}. Scramble or call the hauler now."
            ).format(
                code, minutes_late, sched, address, amount, assigned_label,
            )
            send_sms_async(ADMIN_PHONE, sms_body)
        except Exception:
            logger.exception("Failed to SMS admin about late job %s", job.id)

    if ADMIN_EMAIL:
        try:
            from email_service import send_email_async
            subject = "🚨 LATE JOB #{} — {} min past scheduled".format(
                code, minutes_late,
            )
            html = (
                "<h2>Job is past its scheduled start with no progress</h2>"
                "<p>Customer has been auto-texted a reassurance message, but the "
                "clock is on — call the assigned hauler or scramble a backup now.</p>"
                "<table cellpadding='6' style='font-family:sans-serif;font-size:14px'>"
                "<tr><td><b>Booking</b></td><td>#{code}</td></tr>"
                "<tr><td><b>Minutes late</b></td><td>{mins}</td></tr>"
                "<tr><td><b>Scheduled</b></td><td>{sched}</td></tr>"
                "<tr><td><b>Amount</b></td><td>{amount}</td></tr>"
                "<tr><td><b>Address</b></td><td>{address}</td></tr>"
                "<tr><td><b>Customer</b></td><td>{cname} {cphone}</td></tr>"
                "<tr><td><b>Assignment</b></td><td>{assigned}</td></tr>"
                "</table>"
            ).format(
                code=code, mins=minutes_late, sched=sched, amount=amount,
                address=address, cname=customer_name, cphone=customer_phone,
                assigned=assigned_label,
            )
            send_email_async(ADMIN_EMAIL, subject, html)
        except Exception:
            logger.exception("Failed to email admin about late job %s", job.id)
