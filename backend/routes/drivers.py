"""
Driver / Contractor API routes for JunkOS.
Handles contractor registration, availability, location, and job management.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
from math import radians, cos, sin, asin, sqrt

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, User, Contractor, Job, Notification, generate_uuid, utcnow
from auth_routes import require_auth

drivers_bp = Blueprint("drivers", __name__, url_prefix="/api/drivers")

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

    contractor = Contractor(
        id=generate_uuid(),
        user_id=user.id,
        license_url=data.get("license_url"),
        insurance_url=data.get("insurance_url"),
        truck_photos=data.get("truck_photos", []),
        truck_type=data.get("truck_type"),
        truck_capacity=data.get("truck_capacity"),
        approval_status="pending",
    )
    user.role = "driver"

    db.session.add(contractor)
    db.session.commit()

    return jsonify({"success": True, "contractor": contractor.to_dict()}), 201


@drivers_bp.route("/profile", methods=["GET"])
@require_auth
def get_profile(user_id):
    """Return the contractor profile for the authenticated user."""
    contractor = Contractor.query.filter_by(user_id=user_id).first()
    if not contractor:
        return jsonify({"error": "Contractor profile not found"}), 404

    return jsonify({"success": True, "contractor": contractor.to_dict()}), 200


@drivers_bp.route("/availability", methods=["PUT"])
@require_auth
def update_availability(user_id):
    """Toggle online status and update availability schedule."""
    contractor = Contractor.query.filter_by(user_id=user_id).first()
    if not contractor:
        return jsonify({"error": "Contractor profile not found"}), 404

    if contractor.approval_status != "approved":
        return jsonify({"error": "Contractor is not approved"}), 403

    data = request.get_json() or {}

    if "is_online" in data:
        contractor.is_online = bool(data["is_online"])
    if "availability_schedule" in data:
        contractor.availability_schedule = data["availability_schedule"]

    db.session.commit()
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
    """Return pending jobs near the contractor current location."""
    contractor = Contractor.query.filter_by(user_id=user_id).first()
    if not contractor:
        return jsonify({"error": "Contractor profile not found"}), 404

    if contractor.approval_status != "approved":
        return jsonify({"error": "Contractor is not approved"}), 403

    radius_km = float(request.args.get("radius", DEFAULT_SEARCH_RADIUS_KM))

    pending_jobs = Job.query.filter_by(status="pending").all()

    nearby = []
    for job in pending_jobs:
        if job.lat is not None and job.lng is not None and contractor.current_lat is not None and contractor.current_lng is not None:
            dist = _haversine(contractor.current_lat, contractor.current_lng, job.lat, job.lng)
            if dist <= radius_km:
                job_data = job.to_dict()
                job_data["distance_km"] = round(dist, 2)
                nearby.append(job_data)
        else:
            job_data = job.to_dict()
            job_data["distance_km"] = None
            nearby.append(job_data)

    nearby.sort(key=lambda j: j["distance_km"] if j["distance_km"] is not None else float("inf"))

    return jsonify({"success": True, "jobs": nearby}), 200


@drivers_bp.route("/jobs/<job_id>/accept", methods=["POST"])
@require_auth
def accept_job(user_id, job_id):
    """Accept a pending job."""
    contractor = Contractor.query.filter_by(user_id=user_id).first()
    if not contractor:
        return jsonify({"error": "Contractor profile not found"}), 404

    if contractor.approval_status != "approved":
        return jsonify({"error": "Contractor is not approved"}), 403

    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.status != "pending":
        return jsonify({"error": "Job cannot be accepted (current status: {})".format(job.status)}), 409

    job.driver_id = contractor.id
    job.status = "accepted"
    job.updated_at = utcnow()

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

    return jsonify({"success": True, "job": job.to_dict()}), 200


VALID_STATUS_TRANSITIONS = {
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

    allowed = VALID_STATUS_TRANSITIONS.get(job.status, [])
    if new_status not in allowed:
        return jsonify({
            "error": "Cannot transition from {} to {}".format(job.status, new_status),
            "allowed": allowed,
        }), 409

    job.status = new_status
    job.updated_at = utcnow()

    if new_status == "started":
        job.started_at = utcnow()
    elif new_status == "completed":
        job.completed_at = utcnow()
        contractor.total_jobs = (contractor.total_jobs or 0) + 1

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

    return jsonify({"success": True, "job": job.to_dict()}), 200
