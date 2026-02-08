"""
Booking API routes for JunkOS.
Customer booking flow: estimate, create job, and check status.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
from math import radians, cos, sin, asin, sqrt

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, Job, Payment, PricingRule, SurgeZone, Contractor, Notification,
    generate_uuid, utcnow,
)
from auth_routes import require_auth

booking_bp = Blueprint("booking", __name__, url_prefix="/api/booking")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_PRICE = 99.00
SERVICE_FEE_RATE = 0.08  # 8% of subtotal

FALLBACK_PRICES = {
    "furniture": 75.00,
    "appliances": 100.00,
    "electronics": 50.00,
    "construction": 85.00,
    "yard_waste": 60.00,
    "general": 45.00,
    "other": 55.00,
}

# Volume discount thresholds
VOLUME_DISCOUNT = {
    # (min_qty, max_qty): discount_rate
    (1, 3): 0.0,
    (4, 6): 0.10,
    (7, None): 0.15,
}

EARTH_RADIUS_KM = 6371.0
NEARBY_CONTRACTOR_RADIUS_KM = 50.0

# Average minutes per item for duration estimation
MINUTES_PER_ITEM = 8
BASE_DURATION_MINUTES = 30


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_item_price(category):
    """Look up the price for an item category from PricingRule, with fallback."""
    rule = PricingRule.query.filter(
        PricingRule.item_type == category,
        PricingRule.is_active == True,
    ).first()

    if rule:
        return rule.base_price

    return FALLBACK_PRICES.get(category.lower(), FALLBACK_PRICES["other"])


def _volume_discount_rate(total_quantity):
    """Return the discount rate based on total item quantity."""
    for (lo, hi), rate in VOLUME_DISCOUNT.items():
        if hi is None and total_quantity >= lo:
            return rate
        if hi is not None and lo <= total_quantity <= hi:
            return rate
    return 0.0


def _active_surge_multiplier(lat=None, lng=None):
    """Return the highest active surge multiplier that applies right now."""
    now = datetime.now(timezone.utc)
    current_day = now.weekday()
    current_time = now.strftime("%H:%M")

    zones = SurgeZone.query.filter_by(is_active=True).all()
    max_surge = 1.0

    for zone in zones:
        if zone.days_of_week and current_day not in zone.days_of_week:
            continue
        if zone.start_time and current_time < zone.start_time:
            continue
        if zone.end_time and current_time > zone.end_time:
            continue
        if zone.surge_multiplier > max_surge:
            max_surge = zone.surge_multiplier

    return max_surge


def _estimate_duration(total_quantity):
    """Estimate job duration in minutes."""
    return BASE_DURATION_MINUTES + (total_quantity * MINUTES_PER_ITEM)


def _haversine(lat1, lng1, lat2, lng2):
    """Return distance in kilometres between two GPS points."""
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


# ---------------------------------------------------------------------------
# POST /api/booking/estimate  (public -- no auth required)
# ---------------------------------------------------------------------------
@booking_bp.route("/estimate", methods=["POST"])
def estimate():
    """
    Calculate a price estimate for the customer booking flow.

    Body JSON:
        items: [ { category: str, quantity: int }, ... ]
        address: { lat: float, lng: float }
        scheduled_date: str (ISO date, optional -- used for context only)
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    items = data.get("items")
    if not items or not isinstance(items, list):
        return jsonify({"error": "items array is required"}), 400

    address = data.get("address") or {}
    lat = address.get("lat")
    lng = address.get("lng")

    # --- Item pricing ---
    item_total = 0.0
    total_quantity = 0
    item_breakdown = []

    for entry in items:
        category = entry.get("category")
        quantity = int(entry.get("quantity", 1))
        if not category:
            continue

        unit_price = _get_item_price(category)
        line_total = unit_price * quantity
        item_total += line_total
        total_quantity += quantity
        item_breakdown.append({
            "category": category,
            "quantity": quantity,
            "unit_price": round(unit_price, 2),
            "line_total": round(line_total, 2),
        })

    if total_quantity == 0:
        return jsonify({"error": "At least one item with a valid category is required"}), 400

    # --- Volume discount ---
    discount_rate = _volume_discount_rate(total_quantity)
    volume_adjustment = round(-(item_total * discount_rate), 2)

    # --- Surge multiplier ---
    surge_multiplier = _active_surge_multiplier(lat, lng)

    # --- Subtotal & service fee ---
    subtotal = BASE_PRICE + item_total + volume_adjustment
    surged_subtotal = subtotal * surge_multiplier
    service_fee = round(surged_subtotal * SERVICE_FEE_RATE, 2)
    total = round(surged_subtotal + service_fee, 2)

    # --- Duration estimate ---
    estimated_duration = _estimate_duration(total_quantity)

    return jsonify({
        "success": True,
        "estimate": {
            "base_price": BASE_PRICE,
            "item_total": round(item_total, 2),
            "items": item_breakdown,
            "volume_adjustment": volume_adjustment,
            "surge_multiplier": surge_multiplier,
            "service_fee": service_fee,
            "total": total,
            "estimated_duration": estimated_duration,
        },
    }), 200


# ---------------------------------------------------------------------------
# POST /api/booking  (auth required)
# ---------------------------------------------------------------------------
@booking_bp.route("", methods=["POST"])
@require_auth
def create_booking(user_id):
    """
    Create a new job / booking.

    Body JSON:
        address: str
        lat: float
        lng: float
        items: list
        photos: list (optional, URLs from upload endpoint)
        scheduled_date: str (ISO date)
        scheduled_time: str (HH:MM)
        notes: str (optional)
        estimated_price: float
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    # --- Validate required fields ---
    address = data.get("address")
    if not address:
        return jsonify({"error": "address is required"}), 400

    lat = data.get("lat")
    lng = data.get("lng")

    items = data.get("items")
    if not items or not isinstance(items, list):
        return jsonify({"error": "items array is required"}), 400

    estimated_price = data.get("estimated_price")
    if estimated_price is None:
        return jsonify({"error": "estimated_price is required"}), 400

    try:
        estimated_price = float(estimated_price)
    except (TypeError, ValueError):
        return jsonify({"error": "estimated_price must be a number"}), 400

    # Parse scheduled datetime
    scheduled_at = None
    scheduled_date = data.get("scheduled_date")
    scheduled_time = data.get("scheduled_time", "09:00")
    if scheduled_date:
        try:
            scheduled_at = datetime.strptime(
                "{} {}".format(scheduled_date, scheduled_time), "%Y-%m-%d %H:%M"
            ).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid scheduled_date or scheduled_time format"}), 400

    photos = data.get("photos", [])
    notes = data.get("notes", "")

    # --- Re-calculate pricing for record keeping ---
    item_total = 0.0
    total_quantity = 0
    for entry in items:
        category = entry.get("category", "other")
        quantity = int(entry.get("quantity", 1))
        unit_price = _get_item_price(category)
        item_total += unit_price * quantity
        total_quantity += quantity

    discount_rate = _volume_discount_rate(total_quantity)
    volume_adjustment = round(-(item_total * discount_rate), 2)
    surge_multiplier = _active_surge_multiplier(lat, lng)
    subtotal = BASE_PRICE + item_total + volume_adjustment
    surged_subtotal = subtotal * surge_multiplier
    service_fee = round(surged_subtotal * SERVICE_FEE_RATE, 2)
    total = round(surged_subtotal + service_fee, 2)

    # --- Create Job ---
    job = Job(
        id=generate_uuid(),
        customer_id=user_id,
        status="pending",
        address=address,
        lat=float(lat) if lat is not None else None,
        lng=float(lng) if lng is not None else None,
        items=items,
        photos=photos,
        scheduled_at=scheduled_at,
        base_price=BASE_PRICE,
        item_total=round(item_total, 2),
        service_fee=service_fee,
        surge_multiplier=surge_multiplier,
        total_price=total,
        notes=notes,
    )
    db.session.add(job)

    # --- Create Payment record ---
    payment = Payment(
        id=generate_uuid(),
        job_id=job.id,
        amount=total,
        service_fee=service_fee,
        payment_status="pending",
    )
    db.session.add(payment)

    # --- Notify nearby online contractors ---
    _notify_nearby_contractors(job)

    db.session.commit()

    return jsonify({
        "success": True,
        "job": job.to_dict(),
        "payment": payment.to_dict(),
    }), 201


# ---------------------------------------------------------------------------
# GET /api/booking/<job_id>  (public for now -- status check)
# ---------------------------------------------------------------------------
@booking_bp.route("/<job_id>", methods=["GET"])
def get_booking_status(job_id):
    """Return full booking status including payment and rating info."""
    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Booking not found"}), 404

    result = job.to_dict()

    if job.payment:
        result["payment"] = job.payment.to_dict()
    else:
        result["payment"] = None

    if job.rating:
        result["rating"] = job.rating.to_dict()
    else:
        result["rating"] = None

    return jsonify({"success": True, "booking": result}), 200


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _notify_nearby_contractors(job):
    """Create Notification records for nearby online contractors."""
    if job.lat is None or job.lng is None:
        # No location -- notify all online contractors
        contractors = Contractor.query.filter_by(
            is_online=True, approval_status="approved"
        ).all()
    else:
        contractors = Contractor.query.filter_by(
            is_online=True, approval_status="approved"
        ).all()
        contractors = [
            c for c in contractors
            if c.current_lat is not None
            and c.current_lng is not None
            and _haversine(job.lat, job.lng, c.current_lat, c.current_lng)
            <= NEARBY_CONTRACTOR_RADIUS_KM
        ]

    for contractor in contractors:
        notification = Notification(
            id=generate_uuid(),
            user_id=contractor.user_id,
            type="new_job",
            title="New Job Available",
            body="A new junk removal job is available near you.",
            data={"job_id": job.id, "address": job.address},
        )
        db.session.add(notification)
