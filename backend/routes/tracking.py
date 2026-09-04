"""
Customer-facing tracking API routes for Umuve.
Public endpoints for real-time job status and driver location tracking.
"""

from flask import Blueprint, jsonify

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, Job, Contractor, User
from timeutils import iso_utc

tracking_bp = Blueprint("tracking", __name__, url_prefix="/api/tracking")


@tracking_bp.route("/<job_id>", methods=["GET"])
def get_tracking_info(job_id):
    """
    Public tracking endpoint for customers.
    Returns job status, driver info (if assigned), and driver location.
    """
    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Booking not found"}), 404

    # Pricing/financial details deliberately excluded: this endpoint is public
    # (the job UUID acts as the capability), so it returns only what the
    # tracking page needs.
    result = {
        "job_id": job.id,
        "status": job.status,
        "address": job.address,
        "scheduled_at": iso_utc(job.scheduled_at),
        "items": job.items or [],
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }

    # Include driver info if assigned
    if job.driver_id:
        contractor = db.session.get(Contractor, job.driver_id)
        if contractor:
            result["driver"] = {
                "id": contractor.id,
                "name": contractor.user.name if contractor.user else None,
                "truck_type": contractor.truck_type,
                "avg_rating": contractor.avg_rating,
                "total_jobs": contractor.total_jobs,
                "lat": contractor.current_lat,
                "lng": contractor.current_lng,
            }
        else:
            result["driver"] = None
    else:
        result["driver"] = None

    # Include payment status
    if job.payment:
        result["payment_status"] = job.payment.payment_status
    else:
        result["payment_status"] = None

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
    """Public tracking by confirmation code — no auth, customer-friendly fields only.

    Returns a minimal, safe shape suitable for a public /track/<code> page on
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

    stage, message = _STAGE_MAP.get(
        (job.status or "").lower(),
        ("unknown", "Booking status pending."),
    )

    hauler = None
    if job.driver_id or job.operator_id:
        contractor_id = job.driver_id or job.operator_id
        contractor = db.session.get(Contractor, contractor_id)
        if contractor:
            full_name = contractor.user.name if contractor.user else ""
            first_name = full_name.split()[0] if full_name else "your hauler"
            hauler = {
                "first_name": first_name,
                "truck_type": contractor.truck_type,
                "avg_rating": round(contractor.avg_rating, 1) if contractor.avg_rating else None,
                "total_jobs": contractor.total_jobs or 0,  # social proof
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
    Get the current driver location for a job.
    Returns lat/lng if a driver is assigned and has a known location.
    """
    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if not job.driver_id:
        return jsonify({"success": True, "location": None, "message": "No driver assigned yet"}), 200

    contractor = db.session.get(Contractor, job.driver_id)
    if not contractor or contractor.current_lat is None:
        return jsonify({"success": True, "location": None, "message": "Driver location unavailable"}), 200

    return jsonify({
        "success": True,
        "location": {
            "lat": contractor.current_lat,
            "lng": contractor.current_lng,
            "driver_name": contractor.user.name if contractor.user else None,
            "status": job.status,
        },
    }), 200
