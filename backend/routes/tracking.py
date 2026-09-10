"""
Customer-facing tracking API routes for Umuve.

Audit F21: these endpoints used to be reachable with just a job UUID or
confirmation code and kept returning the hauler's live position forever.
Now every request needs either

  * ``?t=<token>`` — the purpose-scoped, expiring HMAC token that
    ``Job.tracking_url()`` embeds in every texted/emailed link, or
  * a JWT for a participant (the job's customer, the assigned hauler, or an
    admin) in the ``Authorization`` header,

and the driver's location is only returned while the job is in an active
travel/work stage and within the scheduled window + 6h
(``tracking_token.location_window_open``). Contractor details come from the
public arrival serializer — never ``Contractor.to_dict``.
"""

from flask import Blueprint, jsonify, request

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, Job, Contractor, User
from timeutils import iso_utc
from auth_routes import verify_token
from serializers import contractor_public_arrival
from tracking_token import verify_tracking_token, location_window_open

tracking_bp = Blueprint("tracking", __name__, url_prefix="/api/tracking")


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------
def _bearer_user():
    token = request.headers.get("Authorization", "")
    if not token.startswith("Bearer "):
        return None
    user_id = verify_token(token[len("Bearer "):].strip())
    if not user_id:
        return None
    user = db.session.get(User, user_id)
    if not user or user.status not in (None, "active"):
        return None
    return user


def _is_participant(user, job):
    if user is None:
        return False
    if user.role == "admin" or job.customer_id == user.id:
        return True
    profile = user.contractor_profile
    return bool(profile and profile.id in (job.driver_id, job.operator_id))


def _authorize(job):
    """Return None when the caller may view ``job``'s tracking, else a response."""
    token = request.args.get("t") or request.args.get("token")
    if token and verify_tracking_token(job.id, token):
        return None
    if _is_participant(_bearer_user(), job):
        return None
    if token:
        return jsonify({"error": "This tracking link has expired. Check your latest text for a fresh one."}), 401
    return jsonify({"error": "A tracking token is required"}), 401


def _driver_location(job, contractor):
    """lat/lng only during the active window; otherwise None."""
    if contractor is None or not location_window_open(job):
        return None, None
    return contractor.current_lat, contractor.current_lng


@tracking_bp.route("/<job_id>", methods=["GET"])
def get_tracking_info(job_id):
    """
    Tracking endpoint for the customer's page.
    Returns job status, the hauler's arrival profile (if assigned), and the
    hauler's location while the job is active.
    """
    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Booking not found"}), 404
    denied = _authorize(job)
    if denied:
        return denied

    # Pricing/financial details deliberately excluded — this is the shared
    # tracking view, not the receipt.
    result = {
        "job_id": job.id,
        "status": job.status,
        "address": job.address,
        "scheduled_at": iso_utc(job.scheduled_at),
        "items": job.items or [],
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "location_live": location_window_open(job),
    }

    contractor = db.session.get(Contractor, job.driver_id) if job.driver_id else None
    if contractor:
        driver = contractor_public_arrival(contractor)
        # Backwards-compatible keys the web tracking page reads.
        driver["name"] = driver["first_name"]
        driver["truck_type"] = driver["vehicle"]
        driver["lat"], driver["lng"] = _driver_location(job, contractor)
        result["driver"] = driver
    else:
        result["driver"] = None

    result["payment_status"] = job.payment.payment_status if job.payment else None

    return jsonify({"success": True, "tracking": result}), 200


# ---------------------------------------------------------------------------
# Public customer tracking by confirmation code  (Tier 3-H)
# ---------------------------------------------------------------------------
# Customers should never see internal UUIDs. The booking confirmation email
# includes the 8-char ``confirmation_code`` (e.g. #1F96FC1A). The /code/<code>
# endpoint maps that to a customer-friendly status snapshot — stage names
# they understand, hauler first-name only, no internal IDs leaked.

# Internal status → customer-facing stage label + short copy
_STAGE_MAP = {
    "pending":      ("waiting",   "We're confirming a hauler for your pickup."),
    "confirmed":    ("waiting",   "We're confirming a hauler for your pickup."),
    "broadcasting": ("waiting",   "We're confirming a hauler for your pickup."),
    "accepted":     ("assigned",  "A hauler has been assigned and will arrive at your scheduled time."),
    "assigned":     ("assigned",  "A hauler has been assigned and will arrive at your scheduled time."),
    # The real driver-app statuses — previously missing, so the public page
    # showed "Booking status pending." while the hauler was literally driving.
    "en_route":     ("en_route",  "Your hauler is on the way."),
    "arrived":      ("on_site",   "Your hauler has arrived and is loading up."),
    "in_progress":  ("en_route",  "Your hauler is on the way."),
    "started":      ("on_site",   "Your hauler has arrived and is loading up."),
    "completed":    ("complete",  "Pickup complete. Thanks for choosing umuve!"),
    "cancelled":    ("cancelled", "This booking was cancelled."),
    "no_show":      ("issue",     "We're sorting out a hauler — please check your texts."),
}


@tracking_bp.route("/code/<code>", methods=["GET"])
def get_tracking_by_code(code):
    """Tracking by confirmation code — token-gated, customer-friendly fields only.

    Returns a minimal, safe shape suitable for the /track/code/<code> page on
    the frontend. Never leaks contractor phone, internal IDs, or pricing
    breakdowns; just the stage, scheduled time, address (short), and
    hauler's first name + truck info.
    """
    if not code:
        return jsonify({"error": "tracking code required"}), 400

    # Normalize — codes are stored uppercase
    code_norm = code.strip().upper()
    job = Job.query.filter_by(confirmation_code=code_norm).first()
    if not job:
        return jsonify({"error": "No booking found for that code"}), 404
    denied = _authorize(job)
    if denied:
        return denied

    stage, message = _STAGE_MAP.get(
        (job.status or "").lower(),
        ("unknown", "Booking status pending."),
    )

    hauler = None
    if job.driver_id or job.operator_id:
        contractor_id = job.driver_id or job.operator_id
        contractor = db.session.get(Contractor, contractor_id)
        if contractor:
            arrival = contractor_public_arrival(contractor)
            hauler = {
                "first_name": arrival["first_name"],
                "truck_type": arrival["vehicle"],
                "photo_url": arrival["photo_url"],
                "vehicle_photo_url": arrival["vehicle_photo_url"],
                "plate_last3": arrival["plate_last3"],
                "avg_rating": arrival["avg_rating"],
                "total_jobs": arrival["total_jobs"],  # social proof
            }

    # Before/after photos = the customer's own job proof. Surface them once the
    # work is underway/done so the customer sees the cleanout was completed.
    before_photos = (job.before_photos or []) if stage in ("on_site", "complete") else []
    after_photos = (job.after_photos or []) if stage == "complete" else []

    return jsonify({
        "success": True,
        "tracking": {
            "code": code_norm,
            "stage": stage,                 # waiting | assigned | en_route | on_site | complete | cancelled | issue
            "message": message,
            "scheduled_at": iso_utc(job.scheduled_at),
            "address_short": (job.address or "").split(",")[0] if job.address else None,
            "hauler": hauler,
            "before_photos": before_photos,
            "after_photos": after_photos,
            # Items as count + first 3 categories — enough for "yes this is my booking"
            "items_summary": _summarize_items(job.items),
            # Rescue Engine impact receipt — shows once complete, estimate-only.
            "impact_summary": job.impact_summary if stage == "complete" else None,
        },
    }), 200


def _summarize_items(items):
    """Compact human label for items: '3 items: sofa, mattress, +1 more'."""
    if not items or not isinstance(items, list):
        return ""
    cats = []
    total_qty = 0
    for it in items:
        cat = (it or {}).get("category") if isinstance(it, dict) else None
        qty = (it or {}).get("quantity", 1) if isinstance(it, dict) else 1
        try:
            total_qty += int(qty)
        except (TypeError, ValueError):
            total_qty += 1
        if cat and cat not in cats:
            cats.append(cat)
    head = ", ".join(cats[:3])
    rest = " +{} more".format(len(cats) - 3) if len(cats) > 3 else ""
    return "{} item{}: {}{}".format(
        total_qty, "" if total_qty == 1 else "s", head, rest,
    )


@tracking_bp.route("/<job_id>/driver-location", methods=["GET"])
def get_driver_location(job_id):
    """
    Current driver location for a job — token/participant gated and only
    while the job is active (see location_window_open).
    """
    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    denied = _authorize(job)
    if denied:
        return denied

    if not job.driver_id:
        return jsonify({"success": True, "location": None, "message": "No driver assigned yet"}), 200

    contractor = db.session.get(Contractor, job.driver_id)
    if not location_window_open(job):
        return jsonify({"success": True, "location": None,
                        "message": "Live location is only shared while your pickup is underway"}), 200
    if not contractor or contractor.current_lat is None:
        return jsonify({"success": True, "location": None, "message": "Driver location unavailable"}), 200

    arrival = contractor_public_arrival(contractor)
    return jsonify({
        "success": True,
        "location": {
            "lat": contractor.current_lat,
            "lng": contractor.current_lng,
            "driver_name": arrival["first_name"],
            "status": job.status,
        },
    }), 200
