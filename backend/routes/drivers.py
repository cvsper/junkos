"""
Driver / Contractor API routes for Umuve.
Handles contractor registration, availability, location, and job management.
"""

from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timezone
from math import radians, cos, sin, asin, sqrt
import logging

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, User, Contractor, Job, Notification, OperatorInvite, Referral, generate_uuid, utcnow
from auth_routes import require_auth
from timeutils import fmt_local

drivers_bp = Blueprint("drivers", __name__, url_prefix="/api/drivers")

logger = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371.0
DEFAULT_SEARCH_RADIUS_KM = 30.0


def _haversine(lat1, lng1, lat2, lng2):
    """Return distance in kilometres between two GPS points."""
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


@drivers_bp.route("/register", methods=["POST"])
@require_auth
def register_contractor(user_id):
    """Register the authenticated user as a contractor."""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.contractor_profile:
        return jsonify({"error": "User is already registered as a contractor"}), 409

    data = request.get_json() or {}

    is_operator = bool(data.get("is_operator", False))
    invite_code = data.get("invite_code")

    contractor = Contractor(
        id=generate_uuid(),
        user_id=user.id,
        license_url=data.get("license_url"),
        insurance_url=data.get("insurance_url"),
        truck_photos=data.get("truck_photos", []),
        truck_type=data.get("truck_type"),
        truck_capacity=data.get("truck_capacity"),
        approval_status="pending",
        is_operator=is_operator,
    )

    if is_operator:
        user.role = "operator"
    else:
        user.role = "driver"

    # Handle invite code — link contractor to an operator's fleet
    if invite_code and not is_operator:
        invite = OperatorInvite.query.filter_by(
            invite_code=invite_code, is_active=True
        ).first()
        if invite:
            now = utcnow()
            # Ensure both datetimes are tz-aware for comparison
            invite_exp = invite.expires_at
            if invite_exp and invite_exp.tzinfo is None:
                from datetime import timezone as _tz
                invite_exp = invite_exp.replace(tzinfo=_tz.utc)
            expired = invite_exp and invite_exp < now
            maxed = invite.use_count >= invite.max_uses
            if not expired and not maxed:
                contractor.operator_id = invite.operator_id
                invite.use_count += 1
                if invite.use_count >= invite.max_uses:
                    invite.is_active = False

    db.session.add(contractor)
    db.session.commit()

    return jsonify({"success": True, "contractor": contractor.to_dict()}), 201


@drivers_bp.route("/profile", methods=["GET"])
@require_auth
def get_profile(user_id):
    """Return the contractor profile for the authenticated user."""
    try:
        contractor = Contractor.query.filter_by(user_id=user_id).first()
        if not contractor:
            return jsonify({"error": "Contractor profile not found"}), 404

        return jsonify({"success": True, "contractor": contractor.to_dict()}), 200
    except Exception as e:
        current_app.logger.exception("Failed to load contractor profile for user %s: %s", user_id, e)
        db.session.rollback()
        return jsonify({"error": "Failed to load contractor profile"}), 500


@drivers_bp.route("/availability", methods=["PUT"])
@require_auth
def update_availability(user_id):
    """Toggle online status and update availability schedule."""
    contractor = Contractor.query.filter_by(user_id=user_id).first()
    if not contractor:
        return jsonify({"error": "Contractor profile not found"}), 404

    data = request.get_json() or {}

    was_online = bool(contractor.is_online)
    if "is_online" in data:
        contractor.is_online = bool(data["is_online"])
    if "availability_schedule" in data:
        contractor.availability_schedule = data["availability_schedule"]

    db.session.commit()

    # Just came online with a known location? Reactivate any no-coverage
    # waitlist customers near this hauler — turns dead demand into bookings.
    try:
        if (not was_online and contractor.is_online
                and contractor.approval_status == "approved"
                and contractor.current_lat is not None and contractor.current_lng is not None):
            import threading
            from flask import current_app
            app_obj = current_app._get_current_object()
            lat, lng = contractor.current_lat, contractor.current_lng

            def _reactivate():
                try:
                    from waitlist import notify_waitlist_for_coverage
                    notify_waitlist_for_coverage(app_obj, lat, lng)
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception("waitlist reactivation failed")

            threading.Thread(target=_reactivate, daemon=True).start()

            # LAUNCH MOMENT: the very first hauler going online is the last
            # gate before revenue. Fire the launch checklist at the admin,
            # exactly once ever.
            try:
                from ops_sentinel import _once as _sentinel_once
                if _sentinel_once("first_hauler_online", "global",
                                  subject_type="launch"):
                    admin_phone = (os.environ.get("OPERATOR_PHONE")
                                   or os.environ.get("ADMIN_PHONE", ""))
                    if admin_phone:
                        from notifications import send_sms as _launch_sms
                        _launch_sms(admin_phone,
                                    "🚀 FIRST HAULER ONLINE: {}. Launch checklist: "
                                    "1) GET /api/admin/launch-readiness "
                                    "2) PBC25 test booking end-to-end "
                                    "3) cancel test 4) flip ads ON. GO.".format(
                                        getattr(contractor, "name", contractor.id)))
            except Exception:
                pass
    except Exception:
        pass

    return jsonify({"success": True, "contractor": contractor.to_dict()}), 200


@drivers_bp.route("/location", methods=["PUT"])
@require_auth
def update_location(user_id):
    """Update the contractor current GPS coordinates."""
    contractor = Contractor.query.filter_by(user_id=user_id).first()
    if not contractor:
        return jsonify({"error": "Contractor profile not found"}), 404

    data = request.get_json() or {}
    lat = data.get("lat")
    lng = data.get("lng")

    if lat is None or lng is None:
        return jsonify({"error": "lat and lng are required"}), 400

    try:
        contractor.current_lat = float(lat)
        contractor.current_lng = float(lng)
    except (TypeError, ValueError):
        return jsonify({"error": "lat and lng must be numbers"}), 400

    db.session.commit()
    return jsonify({"success": True, "lat": contractor.current_lat, "lng": contractor.current_lng}), 200


@drivers_bp.route("/jobs/available", methods=["GET"])
@require_auth
def get_available_jobs(user_id):
    """Return pending jobs near the contractor current location with pagination."""
    contractor = Contractor.query.filter_by(user_id=user_id).first()
    if not contractor:
        return jsonify({"error": "Contractor profile not found"}), 404

    if contractor.approval_status != "approved":
        return jsonify({"error": "Contractor is not approved"}), 403

    radius_km = float(request.args.get("radius", DEFAULT_SEARCH_RADIUS_KM))
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    # Claimable = PAID and unassigned ("confirmed"/"broadcasting") — unpaid
    # "pending" jobs are no longer shown since accept rejects them anyway.
    # Plus jobs already assigned to this contractor.
    pending_jobs = Job.query.filter(
        db.or_(
            db.and_(
                Job.driver_id.is_(None),
                Job.status.in_(["confirmed", "broadcasting"]),
            ),
            db.and_(
                Job.driver_id == contractor.id,
                Job.status.in_(["assigned", "accepted", "en_route", "arrived", "started"]),
            ),
        )
    ).all()

    nearby = []
    for job in pending_jobs:
        if job.lat is not None and job.lng is not None and contractor.current_lat is not None and contractor.current_lng is not None:
            dist = _haversine(contractor.current_lat, contractor.current_lng, job.lat, job.lng)
            if dist <= radius_km:
                job_data = _with_driver_payout(job)
                job_data["distance_km"] = round(dist, 2)
                nearby.append(job_data)
        else:
            job_data = _with_driver_payout(job)
            job_data["distance_km"] = None
            nearby.append(job_data)

    nearby.sort(key=lambda j: j["distance_km"] if j["distance_km"] is not None else float("inf"))

    # Apply pagination to the distance-sorted results
    total = len(nearby)
    start = (page - 1) * per_page
    end = start + per_page
    paginated = nearby[start:end]
    pages = (total + per_page - 1) // per_page if total > 0 else 0

    return jsonify({
        "success": True,
        "jobs": paginated,
        "total": total,
        "page": page,
        "pages": pages,
    }), 200


@drivers_bp.route("/jobs/current", methods=["GET"])
@require_auth
def get_current_job(user_id):
    """Return the driver's current active job (accepted, en_route, arrived, or started)."""
    contractor = Contractor.query.filter_by(user_id=user_id).first()
    if not contractor:
        return jsonify({"error": "Contractor profile not found"}), 404

    # Find the driver's current active job
    active_job = Job.query.filter_by(driver_id=contractor.id).filter(
        Job.status.in_(["accepted", "en_route", "arrived", "started"])
    ).first()

    if not active_job:
        return jsonify({"success": True, "job": None}), 200

    return jsonify({"success": True, "job": _with_driver_payout(active_job)}), 200


def _with_driver_payout(job):
    """job.to_dict() + the driver's actual/estimated take for driver-facing
    endpoints — so the app can show 'Your pay' instead of the customer total."""
    d = job.to_dict()
    try:
        from routes.driver import _job_driver_payout
        d["driver_payout"] = _job_driver_payout(job)
    except Exception:
        pass
    return d


@drivers_bp.route("/jobs/<job_id>/accept", methods=["POST"])
@require_auth
def accept_job(user_id, job_id):
    """Accept a pending/confirmed/assigned job."""
    contractor = Contractor.query.filter_by(user_id=user_id).first()
    if not contractor:
        return jsonify({"error": "Contractor profile not found"}), 404

    if contractor.approval_status != "approved":
        return jsonify({"error": "Contractor is not approved"}), 403

    # Check if driver already has a job en route
    active_job = Job.query.filter_by(driver_id=contractor.id, status="en_route").first()
    if active_job:
        return jsonify({
            "error": "You already have a job en route. Complete your current job before accepting another.",
            "active_job_id": active_job.id
        }), 409

    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    # Atomic claim (same pattern as the broadcast accept path): a conditional
    # UPDATE so two concurrent accepts can't both win, a driver can't steal a
    # job already assigned to someone else, and unpaid ("pending") jobs can't
    # be accepted — payment confirmation is what makes a job claimable.
    now = utcnow()
    if job.driver_id == contractor.id and job.status == "assigned":
        # Dispatcher pre-assigned this driver; accepting flips assigned->accepted.
        claim = (
            Job.__table__.update()
            .where(Job.id == job_id)
            .where(Job.driver_id == contractor.id)
            .where(Job.status == "assigned")
            .values(status="accepted", updated_at=now)
        )
    else:
        _values = {"driver_id": contractor.id, "status": "accepted", "updated_at": now}
        if contractor.operator_id:
            _values["operator_id"] = contractor.operator_id
        claim = (
            Job.__table__.update()
            .where(Job.id == job_id)
            .where(Job.driver_id.is_(None))
            .where(Job.status.in_(("confirmed", "broadcasting")))
            .values(**_values)
        )

    result = db.session.execute(claim)
    if result.rowcount != 1:
        db.session.rollback()
        db.session.refresh(job)
        if job.driver_id and job.driver_id != contractor.id:
            return jsonify({"error": "That job was just taken by another hauler"}), 409
        if job.status == "pending":
            return jsonify({"error": "Job is awaiting payment and cannot be accepted yet"}), 409
        return jsonify({"error": "Job cannot be accepted (current status: {})".format(job.status)}), 409

    db.session.refresh(job)

    notification = Notification(
        id=generate_uuid(),
        user_id=job.customer_id,
        type="job_update",
        title="Driver Assigned",
        body="A driver has accepted your job.",
        data={"job_id": job.id, "status": "accepted"},
    )
    db.session.add(notification)
    db.session.commit()

    # Send APNs push + email to customer
    try:
        from notifications import send_push_notification, send_driver_assigned_email
        send_push_notification(
            job.customer_id,
            "Driver Assigned",
            "A driver has been assigned to your job!",
            {"job_id": job.id, "type": "job_update", "status": "accepted"}
        )
        customer = db.session.get(User, job.customer_id)
        if customer and customer.email:
            send_driver_assigned_email(
                customer.email, customer.name,
                contractor.user.name if contractor.user else "Your driver",
                job.address,
                truck_type=contractor.truck_type,
            )
    except Exception as e:
        logger.exception("Failed to send push/email to customer for job %s: %s", job.id, e)

    # Broadcast via SocketIO
    from socket_events import broadcast_job_accepted, socketio
    broadcast_job_accepted(job.id, contractor.id)

    # Also notify the customer's job room
    socketio.emit("job:driver-assigned", {
        "job_id": job.id,
        "driver": {
            "id": contractor.id,
            "name": contractor.user.name if contractor.user else None,
            "truck_type": contractor.truck_type,
            "avg_rating": contractor.avg_rating,
            "total_jobs": contractor.total_jobs,
        },
    }, room=job.id)

    return jsonify({"success": True, "job": _with_driver_payout(job)}), 200


@drivers_bp.route("/jobs/<job_id>/decline", methods=["POST"])
@require_auth
def decline_job(user_id, job_id):
    """Decline an assigned job (only if assigned to this driver)."""
    contractor = Contractor.query.filter_by(user_id=user_id).first()
    if not contractor:
        return jsonify({"error": "Contractor profile not found"}), 404

    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.driver_id != contractor.id:
        return jsonify({"error": "Job is not assigned to you"}), 403

    if job.status not in ("assigned", "accepted"):
        return jsonify({"error": "Cannot decline job in status: {}".format(job.status)}), 409

    # Unassign driver, revert to confirmed
    job.driver_id = None
    job.status = "confirmed"
    job.updated_at = utcnow()
    db.session.commit()

    # Re-run auto-dispatch to find another driver in background
    try:
        from dispatcher import auto_assign_job_async
        auto_assign_job_async(job.id, current_app._get_current_object())
    except Exception:
        logger.exception("Failed to trigger re-dispatch for declined job %s", job.id)

    from socket_events import broadcast_job_status
    broadcast_job_status(job.id, job.status)

    return jsonify({"success": True, "job": job.to_dict()}), 200


VALID_STATUS_TRANSITIONS = {
    "assigned": ["accepted", "cancelled"],
    "accepted": ["en_route", "cancelled"],
    "en_route": ["arrived", "cancelled"],
    "arrived": ["started", "cancelled"],
    "started": ["completed"],
}


@drivers_bp.route("/jobs/<job_id>/status", methods=["PUT"])
@require_auth
def update_job_status(user_id, job_id):
    """Advance the job through its lifecycle."""
    contractor = Contractor.query.filter_by(user_id=user_id).first()
    if not contractor:
        return jsonify({"error": "Contractor profile not found"}), 404

    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.driver_id != contractor.id:
        return jsonify({"error": "You are not assigned to this job"}), 403

    data = request.get_json() or {}
    new_status = data.get("status")

    if not new_status:
        return jsonify({"error": "status is required"}), 400

    ok, payload, code = apply_job_status_transition(job, contractor, new_status, data)
    return jsonify(payload), code


def apply_job_status_transition(job, contractor, new_status, data=None):
    """Advance a job through its lifecycle with every side effect the driver
    app relies on (timestamps, referrals, auto-payout, customer email/SMS/push).

    Shared by the authenticated driver route above and the concierge
    (phone-only hauler) console in routes/concierge.py so the two paths can
    never drift. Returns ``(ok, payload, http_code)``.
    """
    data = data or {}

    allowed = VALID_STATUS_TRANSITIONS.get(job.status, [])
    if new_status not in allowed:
        return False, {
            "error": "Cannot transition from {} to {}".format(job.status, new_status),
            "allowed": allowed,
        }, 409

    # Driver-initiated "cancelled" releases the job back to the pool instead of
    # killing the customer's paid booking: clear the driver, requeue, re-dispatch,
    # and tell the customer + admin. (Previously this flipped a paid job to
    # cancelled with no refund, no cleanup, and no word to guest customers.)
    if new_status == "cancelled":
        reason = (data.get("reason") or data.get("cancellation_reason") or "").strip()
        job.driver_id = None
        if job.operator_id and contractor.operator_id == job.operator_id:
            job.operator_id = None
        job.status = "confirmed"
        job.updated_at = utcnow()
        db.session.add(Notification(
            id=generate_uuid(),
            user_id=job.customer_id,
            type="job_update",
            title="Finding You a New Hauler",
            body="Your hauler had to cancel — we're lining up a replacement now. Your booking and payment are unaffected.",
            data={"job_id": job.id, "status": "reassigning"},
        ))
        db.session.commit()

        try:
            from notifications import send_push_notification as _push
            _push(job.customer_id, "Finding You a New Hauler",
                  "Your hauler had to cancel — we're lining up a replacement now.",
                  {"job_id": job.id, "status": "reassigning"})
            _customer = db.session.get(User, job.customer_id)
            if _customer and _customer.phone:
                from sms_service import send_sms_async
                send_sms_async(
                    _customer.phone,
                    "umuve update: your hauler had to cancel, and we're already lining up a replacement. "
                    "Your booking and payment are unaffected — we'll text you the moment a new hauler is confirmed.",
                )
            if _customer and _customer.email:
                from notifications import send_job_status_update_email
                send_job_status_update_email(_customer.email, _customer.name, job.id, "reassigning")
        except Exception:
            logger.exception("Driver-cancel customer notify failed for job %s", job.id)

        try:
            from sms_service import send_sms
            send_sms(
                os.environ.get("ADMIN_PHONE", ""),
                "UMUVE ALERT: hauler {} cancelled job {} ({}). Reason: {}. Auto re-dispatching.".format(
                    contractor.id[:8], str(job.id)[:8], job.address or "?", reason or "none given"),
            )
        except Exception:
            pass

        try:
            from dispatcher import auto_assign_job_async
            auto_assign_job_async(job.id, current_app._get_current_object())
        except Exception:
            logger.exception("Re-dispatch after driver cancel failed for job %s", job.id)

        return True, {"success": True, "job": job.to_dict(), "released": True}, 200

    job.status = new_status
    job.updated_at = utcnow()

    if new_status == "started":
        job.started_at = utcnow()
    elif new_status == "completed":
        job.completed_at = utcnow()
        contractor.total_jobs = (contractor.total_jobs or 0) + 1

        # Rescue Engine v1: capture the hauler's disposition outcome + reason,
        # then build the customer's impact-receipt copy (estimate-only, no
        # charity-name claims — all wording centralized in impact.py).
        try:
            from impact import normalize_outcome, build_impact_summary
            _outcome = normalize_outcome(data.get("disposition_outcome"))
            if _outcome:
                job.disposition_outcome = _outcome
            _dnotes = (data.get("disposition_notes") or "").strip()
            if _dnotes:
                job.disposition_notes = _dnotes[:1000]
            job.impact_summary = build_impact_summary(job)
        except Exception:
            logger.exception("Impact summary build failed for job %s", job.id)

        # Graduation ladder: once a concierge (no-app) hauler has proven out on
        # their 2nd completed job, invite them onto the full app + Stripe so
        # they get paid instantly instead of same-day by hand — the last human
        # step (the manual payout ledger) drains itself to zero. Fires exactly
        # once, at total_jobs == 2. Idempotent guard via a tag on the user.
        try:
            if (getattr(contractor, "is_concierge", False)
                    and contractor.total_jobs == 2
                    and contractor.user and contractor.user.phone):
                from recruiter import send_setup_link
                if send_setup_link(contractor.user.phone,
                                   name=contractor.user.name):
                    logger.info("GRADUATION: sent app+Stripe setup link to "
                                "concierge %s after 2nd job", contractor.id)
        except Exception:
            logger.exception("Graduation-ladder hook failed for contractor %s",
                             contractor.id)

        # Warn if proof photos have not been submitted
        has_before = bool(job.before_photos)
        has_after = bool(job.after_photos)
        if not has_before or not has_after:
            missing = []
            if not has_before:
                missing.append("before_photos")
            if not has_after:
                missing.append("after_photos")
            logger.warning(
                "Job %s completed without proof photos (missing: %s). "
                "Driver: %s",
                job.id, ", ".join(missing), contractor.id,
            )

        # --- Referral completion: check if this customer was referred ---
        try:
            referral = Referral.query.filter_by(
                referee_id=job.customer_id,
                status="signed_up",
            ).first()
            if referral:
                referral.status = "completed"
                referral.completed_at = utcnow()
                logger.info(
                    "Referral %s completed: referee %s first job %s done",
                    referral.id, job.customer_id, job.id,
                )
                # CUSTOMER referral reward — previously advertised ($10) but
                # never issued (pay_referral_bonus only handles contractors).
                # Issue the referrer a single-use $10 promo code + tell them.
                if getattr(referral, "referral_type", None) != "contractor":
                    try:
                        import secrets as _secrets
                        from models import PromoCode
                        bonus = float(referral.reward_amount or 10.0)
                        code = "THANKS-{}".format(_secrets.token_hex(3).upper())
                        db.session.add(PromoCode(
                            code=code, discount_type="fixed",
                            discount_value=bonus, max_uses=1,
                            created_by="referral:{}".format(referral.id),
                        ))
                        referral.status = "rewarded"
                        referrer = db.session.get(User, referral.referrer_id)
                        if referrer:
                            db.session.add(Notification(
                                id=generate_uuid(), user_id=referrer.id,
                                type="referral", title="You earned $10!",
                                body="Your friend completed their first pickup. "
                                     "Use code {} for ${:.0f} off your next one.".format(
                                         code, bonus),
                                data={"referral_id": referral.id, "promo_code": code},
                            ))
                            if referrer.phone:
                                from sms_service import send_sms as _ref_sms
                                _ref_sms(referrer.phone,
                                         "Umuve: your referral booked! Here's your "
                                         "$10 thank-you — code {} on your next "
                                         "pickup. goumuve.com".format(code))
                    except Exception:
                        logger.exception("customer referral reward failed for %s",
                                         referral.id)
        except Exception as e:
            logger.warning("Failed to update referral on job completion: %s", e)

        # --- Contractor referral: pay both haulers on the new hauler's first job ---
        try:
            c_referral = Referral.query.filter_by(
                referee_id=contractor.user_id,
                referral_type="contractor",
                status="signed_up",
            ).first()
            if c_referral:
                c_referral.status = "completed"
                c_referral.completed_at = utcnow()
                logger.info(
                    "Contractor referral %s completed: referrer %s + new hauler %s "
                    "(first job %s done) — paying bonus",
                    c_referral.id, c_referral.referrer_id, contractor.user_id, job.id,
                )
                # Auto-pay both haulers via Stripe Connect (idempotent; flips the
                # referral to 'rewarded' once both are paid, notifies each party,
                # falls back to an earned credit if a payout account isn't ready).
                from routes.payments import pay_referral_bonus
                pay_referral_bonus(c_referral)
        except Exception as e:
            logger.warning("Failed to update contractor referral on job completion: %s", e)

        # --- Reset win-back flag so customer can be called again next cycle ---
        try:
            customer_user = User.query.get(job.customer_id)
            if customer_user and customer_user.winback_called:
                customer_user.winback_called = False
                logger.info("Reset winback_called for customer %s after job %s completed",
                            job.customer_id, job.id)
        except Exception as e:
            logger.warning("Failed to reset winback flag on job completion: %s", e)


    if data.get("before_photos"):
        job.before_photos = data["before_photos"]
    if data.get("after_photos"):
        job.after_photos = data["after_photos"]

    notification = Notification(
        id=generate_uuid(),
        user_id=job.customer_id,
        type="job_update",
        title="Job {}".format(new_status.replace("_", " ").title()),
        body="Your job status has been updated to {}.".format(new_status),
        data={"job_id": job.id, "status": new_status},
    )
    db.session.add(notification)
    db.session.commit()

    # --- Auto-payout the hauler the moment the job is completed ---
    # Job completion is already committed above, so a payout hiccup can never
    # roll it back. attempt_payout is idempotent and never raises; if the
    # contractor hasn't connected Stripe yet it's marked pending_connect.
    if new_status == "completed":
        try:
            from routes.payments import attempt_payout
            payout_result = attempt_payout(job.id)
            logger.info("Auto-payout for job %s: %s", job.id, payout_result.get("status"))
        except Exception as e:
            logger.warning("Auto-payout hook failed for job %s: %s", job.id, e)

    # --- Email / SMS / Push notifications for key status changes ---
    driver_name = contractor.user.name if contractor.user else None
    try:
        from notifications import (
            send_driver_en_route_email, send_driver_en_route_sms,
            send_job_completed_email, send_job_status_update_email,
            send_push_notification,
        )
        customer = db.session.get(User, job.customer_id)

        if new_status == "accepted":
            # The customer's first human signal: someone real took the job.
            # Guests especially heard NOTHING between payment and en_route
            # before this — silence they read as "they forgot me."
            if customer:
                hauler_label = driver_name or "Your hauler"
                when = fmt_local(job.scheduled_at, "%a %b %d, %I:%M %p", "shortly")
                if customer.phone:
                    from sms_service import send_sms as _customer_sms
                    _customer_sms(
                        customer.phone,
                        "Umuve: {} confirmed your pickup — arriving {}. "
                        "Track: {}".format(hauler_label, when, job.tracking_url()),
                    )
                send_push_notification(
                    customer.id, "Hauler Confirmed",
                    "{} accepted your job and is scheduled for {}.".format(hauler_label, when),
                    {"job_id": job.id, "status": "accepted", "category": "job_update"},
                )

        elif new_status == "en_route":
            # Email + SMS customer, push to customer
            if customer:
                if customer.email:
                    send_driver_en_route_email(customer.email, customer.name, driver_name, job.address)
                if customer.phone:
                    send_driver_en_route_sms(customer.phone, driver_name, job.address)
                send_push_notification(
                    customer.id, "Your Driver Is On The Way!",
                    "Your driver is on the way!",
                    {"job_id": job.id, "status": "en_route", "category": "job_en_route"},
                )

        elif new_status == "arrived":
            if customer:
                if customer.email:
                    send_job_status_update_email(
                        customer.email, customer.name, job.id, "arrived",
                        driver_name=driver_name,
                    )
                send_push_notification(
                    customer.id, "Driver Has Arrived",
                    "Your driver has arrived at the location.",
                    {"job_id": job.id, "status": "arrived", "category": "job_arrived"},
                )

        elif new_status == "started":
            if customer:
                if customer.email:
                    send_job_status_update_email(
                        customer.email, customer.name, job.id, "started",
                        driver_name=driver_name,
                    )
                send_push_notification(
                    customer.id, "Job In Progress",
                    "Your driver has started the job.",
                    {"job_id": job.id, "status": "started", "category": "job_started"},
                )

        elif new_status == "completed":
            # Email + push to customer
            if customer:
                if customer.email:
                    from email_service import email_job_completed, schedule_email_follow_up
                    # Extract item names for the receipt
                    item_names = []
                    if job.items:
                        for item in job.items:
                            if isinstance(item, dict):
                                item_names.append(item.get("category", "Item").replace("_", " ").title())
                    
                    email_job_completed(
                        customer.email, customer.name, job.id,
                        job.total_price, item_names,
                        impact_summary=job.impact_summary,
                    )

                    # 24h review follow-up email now sent durably by the
                    # growth_loops sweep (Timer-based sends died on redeploy).

                _complete_body = (job.impact_summary
                                  or "Pickup complete! Rate your experience")
                send_push_notification(
                    customer.id, "Pickup Complete!",
                    _complete_body,
                    {"job_id": job.id, "status": "completed", "category": "job_completed",
                     "impact_summary": job.impact_summary},
                )
            # Push to operator if job was delegated
            if job.operator_id:
                from models import Contractor as _Contractor
                op = db.session.get(_Contractor, job.operator_id)
                if op:
                    send_push_notification(
                        op.user_id, "Job Completed",
                        "Job {} completed by {}".format(
                            str(job.id)[:8], driver_name or "driver"
                        ),
                        {"job_id": job.id, "driver_id": contractor.id},
                    )

            # Nudge the hauler for missing before/after photos — texted
            # photos auto-attach via the SMS webhook, so this works for
            # app operators and phone-only concierge haulers alike.
            if not job.before_photos or not job.after_photos:
                try:
                    _nudge = (
                        "Job done 💪 Before/after photos win you the next "
                        "one — text them to this number and they'll attach "
                        "to the job automatically. Start the text with "
                        "'before' or 'after' if sending separately."
                    )
                    if contractor.user and contractor.user.phone:
                        from sms_service import send_sms as _op_sms
                        _op_sms(contractor.user.phone, _nudge)
                    send_push_notification(
                        contractor.user_id, "Add your before/after photos",
                        _nudge, {"job_id": job.id, "category": "proof_nudge"},
                    )
                except Exception:
                    logger.exception(
                        "Proof-photo nudge failed for job %s", job.id)

            # Review-request SMS (2h later) now sent durably by the
            # growth_loops sweep — the threading.Timer version silently died
            # on every deploy/restart, losing a chunk of review asks.

    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).exception("Notification failed for job %s: %s", job.id, e)

    # Broadcast via SocketIO
    from socket_events import broadcast_job_status
    broadcast_job_status(job.id, new_status)

    return True, {"success": True, "job": job.to_dict()}, 200


@drivers_bp.route("/jobs/<job_id>/proof", methods=["POST"])
@require_auth
def submit_job_proof(user_id, job_id):
    """Submit before/after proof photos for a job.

    Accepts JSON body with:
        - before_photos: list of photo URLs
        - after_photos: list of photo URLs

    Only works on jobs with status 'started' or 'completed'.
    Sets proof_submitted_at to the current time.
    """
    import logging
    logger = logging.getLogger(__name__)

    contractor = Contractor.query.filter_by(user_id=user_id).first()
    if not contractor:
        return jsonify({"error": "Contractor profile not found"}), 404

    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.driver_id != contractor.id:
        return jsonify({"error": "You are not assigned to this job"}), 403

    if job.status not in ("started", "completed"):
        return jsonify({
            "error": "Proof can only be submitted for jobs with status 'started' or 'completed' (current: {})".format(job.status),
        }), 409

    data = request.get_json() or {}

    before_photos = data.get("before_photos")
    after_photos = data.get("after_photos")

    if not before_photos and not after_photos:
        return jsonify({"error": "At least one of before_photos or after_photos is required"}), 400

    if before_photos is not None:
        if not isinstance(before_photos, list):
            return jsonify({"error": "before_photos must be a list of URLs"}), 400
        job.before_photos = before_photos

    if after_photos is not None:
        if not isinstance(after_photos, list):
            return jsonify({"error": "after_photos must be a list of URLs"}), 400
        job.after_photos = after_photos

    job.proof_submitted_at = utcnow()
    job.updated_at = utcnow()

    db.session.commit()

    logger.info("Proof photos submitted for job %s by contractor %s", job.id, contractor.id)

    return jsonify({"success": True, "job": job.to_dict()}), 200


@drivers_bp.route("/jobs/<job_id>/volume", methods=["POST"])
@require_auth
def propose_volume_adjustment(user_id, job_id):
    """Driver proposes a volume adjustment after arriving on-site."""
    from routes.booking import calculate_estimate
    from notifications import send_push_notification
    from socket_events import socketio
    import stripe

    contractor = Contractor.query.filter_by(user_id=user_id).first()
    if not contractor:
        return jsonify({"error": "Contractor not found"}), 404

    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.status != "arrived":
        return jsonify({"error": "Job must be in 'arrived' status to propose volume adjustment"}), 400

    if job.driver_id != contractor.id:
        return jsonify({"error": "Only the assigned driver can propose volume adjustment"}), 403

    data = request.get_json() or {}
    actual_volume = data.get("actual_volume")

    if not actual_volume or not isinstance(actual_volume, (int, float)):
        return jsonify({"error": "actual_volume (number) is required"}), 400

    # Map volume to item quantity using Phase 2 tier mapping
    if actual_volume <= 4:
        quantity = 2  # quarter
    elif actual_volume <= 8:
        quantity = 5  # half
    elif actual_volume <= 12:
        quantity = 10  # threeQuarter
    else:
        quantity = 16  # full

    # Calculate new price
    try:
        items = [{"category": "general", "quantity": quantity}]
        result = calculate_estimate(items, scheduled_date=None, lat=None, lng=None)
        new_price = result["grand_total"]
    except Exception as e:
        logger.exception("Failed to calculate new price for volume adjustment")
        return jsonify({"error": "Failed to calculate new price"}), 500

    # Auto-approve if price decreased or stayed the same
    if new_price <= job.total_price:
        job.total_price = new_price
        job.volume_estimate = actual_volume
        job.updated_at = utcnow()

        # Update Stripe PaymentIntent if it exists
        try:
            if job.payment and job.payment.stripe_payment_intent_id:
                stripe.PaymentIntent.modify(
                    job.payment.stripe_payment_intent_id,
                    amount=int(new_price * 100)
                )
                job.payment.amount = new_price
                job.payment.commission = new_price * 0.20
                job.payment.driver_payout_amount = new_price * 0.80
        except Exception as e:
            logger.warning("Failed to update Stripe PaymentIntent for auto-approved volume adjustment: %s", e)

        db.session.commit()

        # Emit socket event
        try:
            socketio.emit("volume:approved", {"job_id": job_id}, room=f"driver:{contractor.id}")
        except Exception as e:
            logger.warning("Failed to emit volume:approved socket event: %s", e)

        logger.info("Volume adjustment auto-approved for job %s (price decreased: $%.2f -> $%.2f)",
                   job_id, job.total_price, new_price)

        return jsonify({
            "success": True,
            "auto_approved": True,
            "new_price": new_price
        }), 200

    # Price increased - require customer approval
    job.volume_adjustment_proposed = True
    job.adjusted_volume = actual_volume
    job.adjusted_price = new_price
    job.updated_at = utcnow()
    db.session.commit()

    # Send push notification with category for actionable notification
    try:
        send_push_notification(
            job.customer_id,
            "Price Adjustment Required",
            f"Volume increased. New price: ${new_price:.2f} (was ${job.total_price:.2f})",
            data={
                "job_id": job_id,
                "new_price": str(new_price),
                "original_price": str(job.total_price),
                "type": "volume_adjustment"
            },
            category="VOLUME_ADJUSTMENT"
        )
    except Exception as e:
        logger.warning("Failed to send volume adjustment push notification: %s", e)

    # Emit socket event
    try:
        socketio.emit("volume:proposed", {"job_id": job_id, "new_price": new_price}, room=f"driver:{contractor.id}")
    except Exception as e:
        logger.warning("Failed to emit volume:proposed socket event: %s", e)

    logger.info("Volume adjustment proposed for job %s: $%.2f -> $%.2f", job_id, job.total_price, new_price)

    return jsonify({
        "success": True,
        "new_price": new_price,
        "original_price": job.total_price
    }), 200
