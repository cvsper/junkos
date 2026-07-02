"""
Booking API routes for Umuve.
Customer booking flow: estimate, create job, and check status.

Pricing engine v2 -- tiered item categories with size variants, volume
discounts (4 tiers), time-based surge, zone-based surge, and a minimum
job price of $89.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timezone, date as date_type, timedelta
from math import radians, cos, sin, asin, sqrt

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Job, Payment, PricingRule, PricingConfig, SurgeZone, Contractor,
    Notification, PromoCode, AbandonedBooking, generate_uuid, utcnow, generate_referral_code,
)
from auth_routes import require_auth, optional_auth
from extensions import limiter
from geofencing import is_in_service_area

booking_bp = Blueprint("booking", __name__, url_prefix="/api/booking")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_PRICE = 0.0            # Removed flat base -- pricing is fully item-driven
SERVICE_FEE_RATE = 0.08     # 8 % of subtotal
MINIMUM_JOB_PRICE = 119.00  # Floor price for any job (2026-07-02 re-tier)

# ---------------------------------------------------------------------------
# Specific item prices. Re-tiered 2026-07-02: singles must clear the driver
# floor — payout is ~77.8% of list (x1.08 service fee, x0.72 after take), and
# a single-item run costs a hauler 60-90 min + fuel + dump fees, so list
# prices below ~$99 pay under $77 and starve supply. Market anchors: LoadUp
# effective $129-159 single item (after their service-area fee), GOT-JUNK
# $130-250. We stay the cheapest *transparent* binding quote, not the
# cheapest price. Keyed by item_type -> size -> price; flat-rate items use
# "default". Admin PricingRules in the DB override these when present.
# Frontend duplicate: customer-portal-react .../Step3Items.jsx — keep in sync.
# ---------------------------------------------------------------------------
CATEGORY_PRICES = {
    # ── Furniture ─────────────────────────────────────────────────────────
    "sofa":                 {"default": 119.00},   # competitor: $170-$200
    "sofa_sleeper":         {"default": 139.00},   # heavier than sofa — keep above it
    "sofa_sectional":       {"default": 169.00},   # competitor: $175–$225
    "chair_recliner":       {"default":  99.00},   # competitor: $120
    "chair_office":         {"default":  69.00},   # competitor: $120
    "dresser":              {"default":  99.00},   # competitor: $120
    "bookcase":             {"default":  69.00},   # competitor: $120
    "cabinet":              {"default": 149.00},   # competitor: $225
    "table_dining":         {"default":  99.00},   # competitor: $140
    "table_dining_chairs":  {"default": 129.00},   # competitor: $175
    "table_coffee":         {"default":  59.00},   # competitor: $120
    "table_end":            {"default":  49.00},   # competitor: $120
    "table_kitchen":        {"default":  69.00},   # competitor: $120
    "table_conference":     {"default":  89.00},   # competitor: $125
    "futon":                {"default":  79.00},   # competitor: $120
    "filing_cabinet":       {"default":  69.00},   # competitor: $120
    "desk_small":           {"default":  69.00},   # competitor: $120
    "desk_large":           {"default":  99.00},   # competitor: $159
    # ── Beds & Mattresses ─────────────────────────────────────────────────
    "mattress":             {"default":  99.00},   # competitor: $130-$250; +$20 recycling fee
    "box_spring":           {"default":  89.00},   # competitor: $120; +$20 recycling fee
    "bed_frame":            {"default":  75.00},   # competitor: $120
    "bed_set":              {"default": 149.00},   # competitor: $120 (but set = 3 items)
    # ── Appliances ────────────────────────────────────────────────────────
    "refrigerator":         {"default": 129.00},   # competitor: $145
    "refrigerator_bar":     {"default":  69.00},   # competitor: $120
    "washer":               {"default":  99.00},   # competitor: $120
    "dryer":                {"default":  99.00},   # competitor: $120
    "washer_dryer_set":     {"default": 119.00},   # competitor: $160
    "dishwasher":           {"default":  69.00},   # competitor: $120
    "stove":                {"default":  79.00},   # competitor: $120
    "microwave":            {"default":  35.00},   # competitor: $59
    "freezer_chest":        {"default":  79.00},   # competitor: $120
    "freezer_upright":      {"default":  89.00},   # competitor: $125
    # ── Electronics & Entertainment ───────────────────────────────────────
    "tv_flatscreen":        {"default":  89.00},   # competitor: $140
    "tv_console":           {"default":  79.00},   # competitor: $120
    "tv_stand":             {"default":  59.00},   # competitor: $120
    "entertainment_center": {"default":  89.00},   # competitor: $145
    "computer":             {"default":  59.00},   # competitor: $125
    "copier_commercial":    {"default": 109.00},   # competitor: $175
    "printer":              {"default":  35.00},   # competitor: $120
    # ── Exercise Equipment ────────────────────────────────────────────────
    "treadmill":            {"default":  89.00},   # competitor: $120
    "elliptical":           {"default":  99.00},   # competitor: $140
    "bike_stationary":      {"default":  69.00},   # competitor: $120
    # ── Outdoor & Specialty ───────────────────────────────────────────────
    "bbq_grill":            {"default":  69.00},   # competitor: $120
    "basketball_hoop":      {"default":  79.00},   # competitor: $120
    "basketball_hoop_stand":{"default":  99.00},   # competitor: $145
    "lawn_mower_push":      {"default":  69.00},   # competitor: $120
    "lawn_mower_riding":    {"default": 149.00},   # competitor: $200
    "hot_tub":              {"default": 349.00},   # competitor: $400+; two-man + disposal
    "pool_table":           {"default": 269.00},   # competitor: $328; slate weight
    "piano":                {"default": 299.00},   # competitor: $300-$500; two-man minimum
    # ── General / Bulk ────────────────────────────────────────────────────
    "bike":                 {"default":  49.00},   # competitor: $120
    "general":              {"default":  25.00},
    "yard_waste":           {"default":  30.00},   # per cubic yard
    "construction":         {"default":  45.00},   # per cubic yard
    "other":                {"default":  25.00},
    # ── Legacy category fallbacks (for old bookings / AI analysis) ────────
    "furniture":  {"small": 59.00, "medium": 79.00, "large": 99.00, "default": 79.00},
    "appliances": {"small": 49.00, "medium": 79.00, "large": 99.00, "default": 79.00},
    "electronics":{"small": 25.00, "medium": 45.00, "large": 69.00, "default": 45.00},
}

# Legacy flat-price mapping (used as ultimate fallback)
FALLBACK_PRICES = {cat: sizes["default"] for cat, sizes in CATEGORY_PRICES.items()}

# ---------------------------------------------------------------------------
# Truck load volume pricing (alternative to per-item).
# Competitor charges $148 min up to $798 full load.
# We undercut by ~25%.
# ---------------------------------------------------------------------------
TRUCK_LOAD_PRICES = {
    # fraction_label: (fraction_value, price)
    "min":   (0.0,   119.00),    # competitor: $148; aligned to MINIMUM_JOB_PRICE
    "1/8":   (0.125, 179.00),    # competitor: $258
    "1/6":   (0.167, 229.00),    # competitor: $328
    "1/4":   (0.25,  279.00),    # competitor: $388
    "1/3":   (0.333, 329.00),    # competitor: $448
    "3/8":   (0.375, 359.00),    # competitor: $498
    "1/2":   (0.5,   389.00),    # competitor: $538
    "5/8":   (0.625, 419.00),    # competitor: $578
    "2/3":   (0.667, 449.00),    # competitor: $628
    "3/4":   (0.75,  489.00),    # competitor: $678
    "5/6":   (0.833, 529.00),    # competitor: $728
    "7/8":   (0.875, 549.00),    # competitor: $758
    "full":  (1.0,   579.00),    # competitor: $798
}

# ---------------------------------------------------------------------------
# Recycling / disposal surcharges (added on top of item price).
# Competitor charges these as separate fees; we include most but charge
# for genuinely expensive disposal items at lower rates.
# ---------------------------------------------------------------------------
RECYCLING_FEES = {
    "tire_small":        5.00,     # competitor: $10
    "tire_large":       15.00,     # competitor: $25
    "tire_tractor":     20.00,     # competitor: $30
    "mattress":         20.00,     # competitor: $30 (recycling surcharge)
    "box_spring":       20.00,     # competitor: $30
    "propane_tank":      5.00,     # competitor: $10
    "e_waste":           0.00,     # competitor: $5 -- we absorb this
    "appliance_freon":  10.00,     # competitor: $20 (freon recovery)
    "batteries":         5.00,     # competitor: $10
    "tube_tv":          10.00,     # competitor: $15
    "paint":            10.00,     # competitor: $20 per gallon
    "hazardous":       100.00,     # competitor: $150
}

# Items that automatically trigger recycling fees
RECYCLING_FEE_TRIGGERS = {
    "mattress":          "mattress",
    "box_spring":        "box_spring",
    "refrigerator":      "appliance_freon",
    "freezer_chest":     "appliance_freon",
    "freezer_upright":   "appliance_freon",
    "tv_console":        "tube_tv",
    "washer":            "appliance_freon",
    "dryer":             "appliance_freon",
    "washer_dryer_set":  "appliance_freon",
    "dishwasher":        "appliance_freon",
}

# ---------------------------------------------------------------------------
# Labor fee -- competitor charges $75/hr/person, we charge $55
# Applied only for jobs requiring extra labor (stairs, long carry, etc.)
# ---------------------------------------------------------------------------
LABOR_FEE_PER_HOUR = 55.00   # competitor: $75

# ---------------------------------------------------------------------------
# Volume discount tiers
# ---------------------------------------------------------------------------
VOLUME_DISCOUNT_TIERS = [
    # (min_qty, max_qty, discount_rate)
    (1,  3,  0.00),
    (4,  7,  0.10),
    (8,  15, 0.15),
    (16, None, 0.20),
]

# ---------------------------------------------------------------------------
# Time-based surge configuration (additive percentages)
# ---------------------------------------------------------------------------
SAME_DAY_SURGE  = 0.25   # +25 %
NEXT_DAY_SURGE  = 0.10   # +10 %
WEEKEND_SURGE   = 0.15   # +15 %

EARTH_RADIUS_KM = 6371.0
NEARBY_CONTRACTOR_RADIUS_KM = 50.0

# Duration estimation constants
MINUTES_PER_ITEM = 8
BASE_DURATION_MINUTES = 30

# Truck size thresholds
TRUCK_SIZE_THRESHOLDS = [
    (1,  5,  "Standard Pickup"),
    (6,  12, "Large Truck"),
    (13, None, "Extra-Large Truck / Multiple Loads"),
]


# ============================================================================
# Admin-overridable config loader
# ============================================================================
def _load_config(key, default):
    """Load a pricing config value from the DB, falling back to *default*."""
    try:
        row = db.session.get(PricingConfig, key)
        if row is not None and row.value is not None:
            return row.value
    except Exception:
        pass  # DB not ready or table missing -- use default
    return default


def _get_minimum_job_price():
    return float(_load_config("minimum_job_price", MINIMUM_JOB_PRICE))


def _get_volume_discount_tiers():
    """Return volume discount tiers, preferring DB override."""
    raw = _load_config("volume_discount_tiers", None)
    if raw and isinstance(raw, list):
        return [(t["min_qty"], t.get("max_qty"), t["discount_rate"]) for t in raw]
    return VOLUME_DISCOUNT_TIERS


def _get_time_surge_rates():
    """Return (same_day, next_day, weekend) surge rates."""
    same_day = float(_load_config("same_day_surge", SAME_DAY_SURGE))
    next_day = float(_load_config("next_day_surge", NEXT_DAY_SURGE))
    weekend = float(_load_config("weekend_surge", WEEKEND_SURGE))
    return same_day, next_day, weekend


def _get_service_fee_rate():
    return float(_load_config("service_fee_rate", SERVICE_FEE_RATE))


# ============================================================================
# Helpers -- item pricing
# ============================================================================
def _get_item_price(category, size=None):
    """Return the unit price for a (category, size) pair.

    Resolution order:
      1. Active PricingRule in the database whose ``item_type`` matches
         ``<category>:<size>`` (size-specific) or ``<category>`` (flat).
      2. Hardcoded CATEGORY_PRICES dict (size-aware).
      3. FALLBACK_PRICES flat default.
    """
    cat_lower = (category or "other").lower()
    size_lower = (size or "").lower().strip()

    # --- Try DB rule (size-specific first, then flat category) ---
    if size_lower:
        sized_key = "{}:{}".format(cat_lower, size_lower)
        rule = PricingRule.query.filter(
            PricingRule.item_type == sized_key,
            PricingRule.is_active == True,
        ).first()
        if rule:
            return rule.base_price

    rule = PricingRule.query.filter(
        PricingRule.item_type == cat_lower,
        PricingRule.is_active == True,
    ).first()
    if rule:
        return rule.base_price

    # --- Hardcoded tier ---
    cat_prices = CATEGORY_PRICES.get(cat_lower)
    if cat_prices:
        if size_lower and size_lower in cat_prices:
            return cat_prices[size_lower]
        return cat_prices.get("default", 30.00)

    return FALLBACK_PRICES.get(cat_lower, FALLBACK_PRICES["other"])


# ============================================================================
# Helpers -- volume discount
# ============================================================================
def _volume_discount_rate(total_quantity):
    """Return the discount rate based on total item quantity.

    Reads from admin-overridable config first, then falls back to defaults.
    """
    tiers = _get_volume_discount_tiers()
    for lo, hi, rate in tiers:
        if hi is None and total_quantity >= lo:
            return rate
        if hi is not None and lo <= total_quantity <= hi:
            return rate
    return 0.0


def _volume_discount_label(total_quantity):
    """Human-readable label for the discount tier that applies."""
    rate = _volume_discount_rate(total_quantity)
    if rate <= 0:
        return None
    pct = int(rate * 100)
    return "{}% volume discount ({} items)".format(pct, total_quantity)


# ============================================================================
# Helpers -- zone-based surge (existing behaviour)
# ============================================================================
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


# ============================================================================
# Helpers -- time-based surge (new)
# ============================================================================
def _time_based_surge(scheduled_date_str):
    """Compute additive surge percentage and a human-readable reason list
    based on the *scheduled pickup date* relative to today (UTC).

    Returns ``(surge_pct, [reason_strings])``.
    """
    if not scheduled_date_str:
        return 0.0, []

    try:
        if isinstance(scheduled_date_str, str):
            sched = datetime.strptime(scheduled_date_str[:10], "%Y-%m-%d").date()
        elif isinstance(scheduled_date_str, datetime):
            sched = scheduled_date_str.date()
        elif isinstance(scheduled_date_str, date_type):
            sched = scheduled_date_str
        else:
            return 0.0, []
    except (ValueError, TypeError):
        return 0.0, []

    today = datetime.now(timezone.utc).date()
    delta_days = (sched - today).days

    same_day_rate, next_day_rate, weekend_rate = _get_time_surge_rates()

    surge = 0.0
    reasons = []

    # Same-day
    if delta_days <= 0:
        surge += same_day_rate
        reasons.append("Same-day pickup (+{}%)".format(int(same_day_rate * 100)))
    # Next-day
    elif delta_days == 1:
        surge += next_day_rate
        reasons.append("Next-day pickup (+{}%)".format(int(next_day_rate * 100)))

    # Weekend (Saturday=5, Sunday=6)
    if sched.weekday() in (5, 6):
        surge += weekend_rate
        reasons.append("Weekend pickup (+{}%)".format(int(weekend_rate * 100)))

    return surge, reasons


# ============================================================================
# Helpers -- duration & truck size
# ============================================================================
def _estimate_duration(total_quantity):
    """Estimate job duration in minutes."""
    return BASE_DURATION_MINUTES + (total_quantity * MINUTES_PER_ITEM)


def _estimate_truck_size(total_quantity):
    """Return a truck-size label based on item count."""
    for lo, hi, label in TRUCK_SIZE_THRESHOLDS:
        if hi is None and total_quantity >= lo:
            return label
        if hi is not None and lo <= total_quantity <= hi:
            return label
    return "Standard Pickup"


# ============================================================================
# Core pricing function  (shared by estimate + booking endpoints)
# ============================================================================
def calculate_estimate(items, scheduled_date=None, lat=None, lng=None):
    """Compute the full pricing breakdown.

    Parameters
    ----------
    items : list[dict]
        Each dict: ``{ category, quantity, size? }``
    scheduled_date : str | datetime | None
        ISO date string or datetime for time-based surge.
    lat, lng : float | None
        Customer location for zone-based surge.

    Returns
    -------
    dict with detailed pricing breakdown.
    """
    item_total = 0.0
    total_quantity = 0
    item_breakdown = []

    for entry in items:
        category = entry.get("category") or "other"
        quantity = int(entry.get("quantity", 1))
        size = entry.get("size")  # optional
        if quantity <= 0:
            continue

        unit_price = _get_item_price(category, size)
        line_total = unit_price * quantity
        item_total += line_total
        total_quantity += quantity

        line = {
            "category": category,
            "quantity": quantity,
            "unit_price": round(unit_price, 2),
            "line_total": round(line_total, 2),
        }
        if size:
            line["size"] = size
        item_breakdown.append(line)

    # --- Recycling / disposal fees ---
    recycling_total = 0.0
    recycling_breakdown = []
    for entry in items:
        category = (entry.get("category") or "other").lower()
        quantity = int(entry.get("quantity", 1))
        fee_key = RECYCLING_FEE_TRIGGERS.get(category)
        if fee_key and fee_key in RECYCLING_FEES:
            fee = RECYCLING_FEES[fee_key]
            if fee > 0:
                line_fee = fee * quantity
                recycling_total += line_fee
                recycling_breakdown.append({
                    "item": category,
                    "fee_type": fee_key,
                    "unit_fee": fee,
                    "quantity": quantity,
                    "total": round(line_fee, 2),
                })

    # --- Volume discount ---
    discount_rate = _volume_discount_rate(total_quantity)
    volume_discount = round(item_total * discount_rate, 2)
    volume_discount_label = _volume_discount_label(total_quantity)

    items_subtotal = round(item_total - volume_discount, 2)

    # --- Zone-based surge multiplier ---
    zone_surge = _active_surge_multiplier(lat, lng)

    # --- Time-based surge ---
    time_surge_pct, surge_reasons = _time_based_surge(scheduled_date)

    # Combined: zone multiplier is multiplicative, time surge is additive on top
    combined_multiplier = zone_surge * (1.0 + time_surge_pct)

    surged_subtotal = round(items_subtotal * combined_multiplier, 2)
    surge_amount = round(surged_subtotal - items_subtotal, 2)

    if zone_surge > 1.0:
        surge_reasons.insert(0, "High-demand zone (x{})".format(round(zone_surge, 2)))

    # --- Service fee (admin-overridable) ---
    fee_rate = _get_service_fee_rate()
    service_fee = round(surged_subtotal * fee_rate, 2)

    # --- Labor hours (optional, passed from frontend) ---
    labor_hours = 0
    labor_fee = 0.0

    # --- Total (with minimum floor, admin-overridable) ---
    min_price = _get_minimum_job_price()
    raw_total = round(surged_subtotal + service_fee + recycling_total + labor_fee, 2)
    total = max(raw_total, min_price)
    minimum_applied = total > raw_total

    # --- Duration & truck size ---
    estimated_duration = _estimate_duration(total_quantity)
    truck_size = _estimate_truck_size(total_quantity)

    return {
        "items_subtotal": round(item_total, 2),
        "items": item_breakdown,
        "volume_discount": volume_discount,
        "volume_discount_rate": discount_rate,
        "volume_discount_label": volume_discount_label,
        "surge_multiplier": round(combined_multiplier, 4),
        "surge_amount": surge_amount,
        "surge_reasons": surge_reasons,
        "base_price": round(items_subtotal, 2),
        "service_fee": service_fee,
        "recycling_fees": round(recycling_total, 2),
        "recycling_breakdown": recycling_breakdown,
        "labor_fee": labor_fee,
        "labor_fee_rate": LABOR_FEE_PER_HOUR,
        "total": total,
        "minimum_applied": minimum_applied,
        "minimum_job_price": min_price,
        "estimated_duration": estimated_duration,
        "truck_size": truck_size,
        "total_quantity": total_quantity,
    }


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
@limiter.limit("20 per minute")
def estimate():
    """
    Calculate a price estimate for the customer booking flow.

    Body JSON:
        items: [ { category: str, quantity: int, size?: str }, ... ]
        address: { lat: float, lng: float }
        scheduledDate: str (ISO date for time-based surge)
        scheduled_date: str (alias)
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

    scheduled_date = data.get("scheduledDate") or data.get("scheduled_date")

    result = calculate_estimate(items, scheduled_date=scheduled_date, lat=lat, lng=lng)

    if result["total_quantity"] == 0:
        return jsonify({"error": "At least one item with a valid category is required"}), 400

    return jsonify({
        "success": True,
        "estimate": result,
    }), 200


# ---------------------------------------------------------------------------
# POST /api/booking/estimate-load  (public -- truck load pricing)
# ---------------------------------------------------------------------------
@booking_bp.route("/estimate-load", methods=["POST"])
def estimate_load():
    """
    Calculate a price estimate based on truck load volume.

    Body JSON:
        load_size: str  (e.g. "1/4", "1/2", "full")
        scheduledDate: str (ISO date for time-based surge)
        labor_hours: float (optional, extra labor hours needed)
        recycling_items: [ { type: str, quantity: int }, ... ]  (optional)
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    load_size = (data.get("load_size") or "").strip().lower()
    if load_size not in TRUCK_LOAD_PRICES:
        return jsonify({
            "error": "Invalid load_size. Options: {}".format(
                ", ".join(sorted(TRUCK_LOAD_PRICES.keys()))
            )
        }), 400

    fraction, base_price = TRUCK_LOAD_PRICES[load_size]

    # --- Time-based surge ---
    scheduled_date = data.get("scheduledDate") or data.get("scheduled_date")
    time_surge_pct, surge_reasons = _time_based_surge(scheduled_date)
    surged_price = round(base_price * (1.0 + time_surge_pct), 2)
    surge_amount = round(surged_price - base_price, 2)

    # --- Service fee ---
    fee_rate = _get_service_fee_rate()
    service_fee = round(surged_price * fee_rate, 2)

    # --- Labor hours ---
    labor_hours = float(data.get("labor_hours", 0))
    labor_fee = round(labor_hours * LABOR_FEE_PER_HOUR, 2)

    # --- Recycling fees ---
    recycling_total = 0.0
    recycling_breakdown = []
    for entry in (data.get("recycling_items") or []):
        fee_type = (entry.get("type") or "").lower()
        qty = int(entry.get("quantity", 1))
        fee = RECYCLING_FEES.get(fee_type, 0)
        if fee > 0:
            line = fee * qty
            recycling_total += line
            recycling_breakdown.append({
                "fee_type": fee_type,
                "unit_fee": fee,
                "quantity": qty,
                "total": round(line, 2),
            })

    # --- Total ---
    min_price = _get_minimum_job_price()
    raw_total = round(surged_price + service_fee + labor_fee + recycling_total, 2)
    total = max(raw_total, min_price)

    return jsonify({
        "success": True,
        "estimate": {
            "load_size": load_size,
            "load_fraction": fraction,
            "base_price": base_price,
            "surge_amount": surge_amount,
            "surge_reasons": surge_reasons,
            "service_fee": service_fee,
            "labor_hours": labor_hours,
            "labor_fee": labor_fee,
            "labor_fee_rate": LABOR_FEE_PER_HOUR,
            "recycling_fees": round(recycling_total, 2),
            "recycling_breakdown": recycling_breakdown,
            "total": total,
            "minimum_applied": total > raw_total,
        },
    }), 200


# ---------------------------------------------------------------------------
# GET /api/booking/pricing  (public -- pricing info for frontend)
# ---------------------------------------------------------------------------
@booking_bp.route("/pricing", methods=["GET"])
def get_pricing_info():
    """Return current pricing data for the frontend to display."""
    return jsonify({
        "success": True,
        "truck_load_prices": {
            k: {"fraction": v[0], "price": v[1]}
            for k, v in TRUCK_LOAD_PRICES.items()
        },
        "recycling_fees": RECYCLING_FEES,
        "labor_fee_per_hour": LABOR_FEE_PER_HOUR,
        "minimum_job_price": _get_minimum_job_price(),
        "service_fee_rate": _get_service_fee_rate(),
    }), 200


# ---------------------------------------------------------------------------
# POST /api/booking  (auth required)
# ---------------------------------------------------------------------------
@booking_bp.route("", methods=["POST"])
@limiter.limit("10 per minute")
@optional_auth
def create_booking(user_id):
    """
    Create a new job / booking.

    Body JSON:
        address: str
        lat: float
        lng: float
        items: list  [{ category, quantity, size? }]
        photos: list (optional, URLs from upload endpoint)
        scheduled_date: str (ISO date)
        scheduled_time: str (HH:MM)
        notes: str (optional)
        estimated_price: float
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    # --- Validate required fields (accept both camelCase and snake_case) ---
    address = data.get("address")
    if isinstance(address, dict):
        # Frontend sends address as object — flatten to string
        lat = address.get("lat") or data.get("lat")
        lng = address.get("lng") or data.get("lng")
        address = address.get("street") or address.get("formatted") or ", ".join(
            v for v in [address.get("street"), address.get("city"),
                        address.get("state"), address.get("zip")] if v
        )
    else:
        lat = data.get("lat")
        lng = data.get("lng")

    if not address:
        return jsonify({"error": "address is required"}), 400

    # --- Service area geofence check ---
    if lat is not None and lng is not None:
        try:
            if not is_in_service_area(float(lat), float(lng)):
                return jsonify({
                    "error": "Address is outside our service area. "
                             "We currently serve Miami-Dade, Broward, and Palm Beach counties."
                }), 400
        except (TypeError, ValueError):
            pass  # Invalid coords -- skip check, let downstream handle it

    # --- Coverage check: do we actually have a hauler near this address? ---
    # The geofence above only confirms the county is in scope. This second gate
    # confirms an approved contractor's last-known location is within range. If
    # not, NEVER charge — capture the lead, alert admin, and tell the customer
    # we'll text a confirmed time. This is what kept us from missing booking
    # #1f96fc1a in Weston and refunding $116.64.
    if lat is not None and lng is not None:
        try:
            from dispatcher import has_active_coverage, _notify_admin_no_coverage_lead

            if not has_active_coverage(float(lat), float(lng)):
                # Resolve customer contact (authed user or guest fields in body)
                customer_email = ""
                customer_phone = ""
                customer_name = ""
                try:
                    if user_id:
                        user_obj = db.session.get(User, user_id)
                        if user_obj:
                            customer_email = (user_obj.email or "").strip().lower()
                            customer_phone = user_obj.phone or ""
                            customer_name = user_obj.name or ""
                    if not customer_email:
                        customer_email = (
                            data.get("email") or data.get("guest_email") or ""
                        ).strip().lower()
                    if not customer_phone:
                        customer_phone = (data.get("phone") or "").strip()
                    if not customer_name:
                        customer_name = (data.get("name") or "").strip()
                except Exception:
                    pass

                # Capture as a waitlist lead if we have an email (for drip / follow-up)
                if customer_email:
                    try:
                        existing = AbandonedBooking.query.filter_by(
                            email=customer_email, converted=False
                        ).first()
                        if existing:
                            existing.address = address or existing.address
                            existing.phone = customer_phone or existing.phone
                            existing.name = customer_name or existing.name
                            existing.items = data.get("items") or existing.items
                            existing.estimated_price = (
                                data.get("estimated_price") or existing.estimated_price
                            )
                            existing.lead_source = "no_coverage_waitlist"
                            existing.step = 99
                            try:
                                existing.waitlist_lat = float(lat)
                                existing.waitlist_lng = float(lng)
                            except (TypeError, ValueError):
                                pass
                        else:
                            wl_lat = wl_lng = None
                            try:
                                wl_lat, wl_lng = float(lat), float(lng)
                            except (TypeError, ValueError):
                                pass
                            db.session.add(AbandonedBooking(
                                email=customer_email,
                                phone=customer_phone or None,
                                name=customer_name or None,
                                address=address,
                                items=data.get("items"),
                                estimated_price=data.get("estimated_price"),
                                lead_source="no_coverage_waitlist",
                                step=99,
                                waitlist_lat=wl_lat,
                                waitlist_lng=wl_lng,
                            ))
                        db.session.commit()

                        # Immediate branded "you're on the list" email so a guest
                        # who closes the tab is still captured.
                        try:
                            from waitlist import send_holding_email
                            send_holding_email(customer_email, customer_name, address)
                        except Exception:
                            pass
                    except Exception:
                        db.session.rollback()
                        import logging
                        logging.getLogger(__name__).exception(
                            "Failed to capture no-coverage waitlist lead for %s",
                            customer_email,
                        )

                # Fire the admin alert immediately (never blocks the response)
                try:
                    _notify_admin_no_coverage_lead(
                        address=address, lat=lat, lng=lng,
                        customer_email=customer_email,
                        customer_phone=customer_phone,
                        customer_name=customer_name,
                        items=data.get("items"),
                        estimated_price=data.get("estimated_price"),
                    )
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception(
                        "Failed to alert admin about no-coverage lead at %s",
                        address,
                    )

                return jsonify({
                    "error": (
                        "We don't have a hauler available at this address yet, "
                        "but your area is in our service zone. We've saved your "
                        "request and our team will text you a confirmed time "
                        "within 2 hours. No charge has been made."
                    ),
                    "status": "waitlist",
                }), 400
        except Exception:
            # Coverage check itself failed — fail open, let booking proceed
            import logging
            logging.getLogger(__name__).exception(
                "Coverage check failed unexpectedly — allowing booking to proceed",
            )

    items = data.get("items")
    if not items or not isinstance(items, list):
        return jsonify({"error": "items array is required"}), 400

    estimated_price = data.get("estimated_price") or data.get("estimatedPrice")
    if estimated_price is None:
        return jsonify({"error": "estimated_price is required"}), 400

    try:
        estimated_price = float(estimated_price)
    except (TypeError, ValueError):
        return jsonify({"error": "estimated_price must be a number"}), 400

    # Parse scheduled datetime (accept camelCase from web frontend)
    scheduled_at = None
    scheduled_date = data.get("scheduled_date") or data.get("scheduledDate")
    scheduled_time = data.get("scheduled_time") or data.get("scheduledTimeSlot") or "09:00"
    # Convert time slot ranges (e.g. "8-10") to HH:MM start time
    if scheduled_time and "-" in scheduled_time and ":" not in scheduled_time:
        try:
            start_hour = int(scheduled_time.split("-")[0])
            scheduled_time = "{:02d}:00".format(start_hour)
        except (ValueError, IndexError):
            scheduled_time = "09:00"
    if scheduled_date:
        try:
            scheduled_at = datetime.strptime(
                "{} {}".format(scheduled_date, scheduled_time), "%Y-%m-%d %H:%M"
            ).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid scheduled_date or scheduled_time format"}), 400

    photos = data.get("photos", [])
    notes = data.get("notes", "")
    lead_source = data.get("lead_source") or data.get("leadSource") or None

    # --- Re-calculate pricing with the v2 engine ---
    est = calculate_estimate(items, scheduled_date=scheduled_date, lat=lat, lng=lng)

    total = est["total"]
    service_fee = est["service_fee"]
    surge_multiplier = est["surge_multiplier"]
    item_total = est["items_subtotal"]

    # --- Honor a binding vision quote if this booking came from one ---
    # Additive + defensive: a customer who got an instant photo quote should
    # pay the LOCKED price they were shown, not a recomputed one. Any problem
    # here falls back to the recomputed price and never blocks the booking.
    quote_to_convert = None
    quote_id = (data.get("quote_id") or data.get("quoteId") or "").strip()
    if quote_id:
        try:
            from models import Quote
            q = db.session.get(Quote, quote_id)
            if q and q.status not in ("booked", "voided"):
                q_email = (q.guest_email or "").strip().lower()
                req_email = (data.get("customerEmail") or "").strip().lower()
                owns = (
                    (user_id and q.user_id == user_id)
                    or (q.user_id is None and (not q_email or q_email == req_email))
                )
                exp = q.expires_at
                if exp is not None and exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                not_expired = exp is None or exp > datetime.now(timezone.utc)
                if owns:
                    quote_to_convert = q
                    if q.binding and not_expired and q.price_cents:
                        total = round(q.price_cents / 100.0, 2)
                        item_total = total
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "quote->booking: failed to apply quote %s", quote_id
            )
            quote_to_convert = None

    # --- Apply promo code if provided ---
    promo_code_str = data.get("promo_code", "").strip()
    promo_code_id = None
    discount_amount = 0.0

    if promo_code_str:
        from routes.promos import validate_promo_code
        promo, discount, promo_error = validate_promo_code(promo_code_str, total)
        if promo_error:
            return jsonify({"error": promo_error}), 400
        promo_code_id = promo.id
        discount_amount = discount
        total = round(total - discount, 2)
        # NOTE: use_count is incremented on PAYMENT SUCCESS (webhook/confirm),
        # not here — counting at booking creation double-counted every paid
        # booking and exhausted max-use codes at half their budget.

    # --- Resolve customer (auth user or guest) ---
    if not user_id:
        guest_email = (data.get("customerEmail") or "").strip().lower()
        guest_name = (data.get("customerName") or "").strip()
        guest_phone = (data.get("customerPhone") or "").strip()

        if not guest_email:
            return jsonify({"error": "Email is required for guest checkout"}), 400

        # Find existing user by email, or create a guest record
        existing = User.query.filter_by(email=guest_email).first()
        if existing:
            user_id = existing.id
            # Update name/phone if not already set
            if guest_name and not existing.name:
                existing.name = guest_name
            if guest_phone and not existing.phone:
                existing.phone = guest_phone
        else:
            guest_user = User(
                id=generate_uuid(),
                email=guest_email,
                name=guest_name or None,
                phone=guest_phone or None,
                role="customer",
            )
            db.session.add(guest_user)
            db.session.flush()
            user_id = guest_user.id

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
        base_price=est["base_price"],
        item_total=round(item_total, 2),
        service_fee=service_fee,
        surge_multiplier=surge_multiplier,
        total_price=total,
        promo_code_id=promo_code_id,
        discount_amount=discount_amount,
        notes=notes,
        lead_source=lead_source,
        confirmation_code=generate_referral_code(),
    )
    db.session.add(job)

    # Link the converted quote to this booking (binding price already honored).
    if quote_to_convert is not None:
        quote_to_convert.booking_id = job.id
        quote_to_convert.status = "booked"

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

    # --- Send booking confirmation email ---
    try:
        customer = db.session.get(User, user_id)
        if customer and customer.email:
            from email_service import email_booking_confirmed
            email_booking_confirmed(
                to_email=customer.email,
                name=customer.name or "",
                job_id=job.id,
                date=str(job.scheduled_at.date()) if job.scheduled_at else "TBD",
                time=job.scheduled_at.strftime("%I:%M %p") if job.scheduled_at else "TBD",
                address=job.address or "",
            )
    except Exception:
        pass  # Notifications must never block the main flow

    # --- Mark abandoned booking as converted ---
    try:
        customer = db.session.get(User, user_id)
        if customer and customer.email:
            abandoned = AbandonedBooking.query.filter_by(
                email=customer.email, converted=False
            ).first()
            if abandoned:
                abandoned.converted = True
                db.session.commit()
    except Exception:
        pass

    # --- SMS confirmation to customer ---
    try:
        customer = db.session.get(User, user_id)
        if customer and customer.phone:
            from sms_service import send_sms_async
            sched_str = scheduled_at.strftime("%b %d at %I:%M %p") if scheduled_at else "ASAP"
            sms_body = (
                "Umuve Booking Confirmed!\n"
                "#{} — ${:.0f}\n"
                "{}\n"
                "Scheduled: {}\n\n"
                "We'll text you when your hauler is on the way. "
                "Reply to this text with any questions!"
            ).format(
                job.confirmation_code or str(job.id)[:8],
                total,
                address or "",
                sched_str,
            )
            send_sms_async(customer.phone, sms_body)
    except Exception:
        pass

    # --- Schedule abandoned booking recovery SMS (30 min) ---
    try:
        customer = db.session.get(User, user_id)
        if customer and customer.phone:
            from flask import current_app
            from sms_service import schedule_abandoned_booking_sms
            schedule_abandoned_booking_sms(
                to_phone=customer.phone,
                customer_name=customer.name or "",
                job_id=job.id,
                app=current_app._get_current_object(),
                delay_seconds=1800,
            )
    except Exception:
        pass  # Recovery SMS must never block the main flow

    # --- SMS operator about new booking ---
    try:
        from sms_service import send_sms_async
        operator_phone = os.environ.get("OPERATOR_PHONE", "")
        if operator_phone:
            items_count = sum(i.get("quantity", 1) for i in items if isinstance(i, dict))
            msg = (
                "NEW BOOKING!\n"
                "{} - {} item{}\n"
                "${:.0f} | {}\n"
                "Scheduled: {}"
            ).format(
                address or "No address",
                items_count, "s" if items_count != 1 else "",
                total,
                lead_source or "direct",
                str(scheduled_at.date()) if scheduled_at else "ASAP",
            )
            send_sms_async(operator_phone, msg)
    except Exception:
        pass

    # --- Trigger n8n booking confirmation + review request webhooks ---
    try:
        import urllib.request
        import json as _json
        n8n_base = os.environ.get("N8N_WEBHOOK_URL", "")
        if n8n_base:
            customer = db.session.get(User, user_id)
            sched_str = scheduled_at.strftime("%B %d, %Y") if scheduled_at else "ASAP"
            payload = _json.dumps({
                "booking_id": job.confirmation_code or str(job.id)[:8],
                "customer_name": customer.name if customer else "Customer",
                "customer_email": customer.email if customer else "",
                "scheduled_date": sched_str,
                "estimated_cost": "{:.2f}".format(total),
                "address": address or "",
            }).encode()
            headers = {"Content-Type": "application/json"}
            # Booking confirmation
            req = urllib.request.Request(
                n8n_base + "/webhook/vnFFMeYDQOB8QIXa/webhook/booking-notification",
                data=payload, headers=headers, method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
            # Review request (n8n waits 24h before sending)
            req2 = urllib.request.Request(
                n8n_base + "/webhook/uaxzeHYyyF2twCvH/webhook/review-request",
                data=payload, headers=headers, method="POST",
            )
            urllib.request.urlopen(req2, timeout=5)
    except Exception:
        pass  # n8n webhooks must never block the booking flow

    return jsonify({
        "success": True,
        "job": job.to_dict(),
        "payment": payment.to_dict(),
    }), 201


# ---------------------------------------------------------------------------
# GET /api/booking/lead-stats  (admin -- lead source analytics)
# ---------------------------------------------------------------------------
@booking_bp.route("/lead-stats", methods=["GET"])
@require_auth
def lead_stats(user_id):
    """Return lead source analytics: booking count and revenue per source."""
    from sqlalchemy import func

    # Verify admin role
    user = db.session.get(User, user_id)
    if not user or user.role != "admin":
        return jsonify({"error": "Admin access required"}), 403

    rows = (
        db.session.query(
            Job.lead_source,
            func.count(Job.id).label("count"),
            func.coalesce(func.sum(Job.total_price), 0.0).label("revenue"),
        )
        .group_by(Job.lead_source)
        .all()
    )

    stats = []
    for source, count, revenue in rows:
        stats.append({
            "source": source or "unknown",
            "count": count,
            "revenue": round(float(revenue), 2),
        })

    # Sort by count descending
    stats.sort(key=lambda x: x["count"], reverse=True)

    total_bookings = sum(s["count"] for s in stats)
    total_revenue = round(sum(s["revenue"] for s in stats), 2)

    return jsonify({
        "success": True,
        "total_bookings": total_bookings,
        "total_revenue": total_revenue,
        "by_source": stats,
    }), 200


# ---------------------------------------------------------------------------
# GET /api/booking/<job_id>  (public for now -- status check)
# ---------------------------------------------------------------------------
@booking_bp.route("/<job_id>", methods=["GET"])
def get_booking_status(job_id):
    """Return booking status for the confirmation/status page.

    Public (the UUID is the capability), so the payment sub-object is reduced
    to what the page needs — never the Stripe intent id, commission, or
    driver/operator payout splits, which previously leaked here.
    """
    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Booking not found"}), 404

    result = job.to_dict()

    if job.payment:
        result["payment"] = {
            "payment_status": job.payment.payment_status,
            "amount": job.payment.amount,
            "tip_amount": job.payment.tip_amount,
        }
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
    """Create Notification records for nearby online contractors.

    Also sends APNs push notifications and Socket.IO events to nearby drivers.
    """
    # Lazy imports to avoid circular dependencies
    from socket_events import notify_nearby_drivers
    from notifications import send_push_notification

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

    # Broadcast Socket.IO event to all nearby drivers (once)
    notify_nearby_drivers(job)

    for contractor in contractors:
        # Create Notification DB record (in-app notification history)
        notification = Notification(
            id=generate_uuid(),
            user_id=contractor.user_id,
            type="new_job",
            title="New Job Available",
            body="A new junk removal job is available near you.",
            data={"job_id": job.id, "address": job.address},
        )
        db.session.add(notification)

        # Send APNs push notification
        try:
            send_push_notification(
                contractor.user_id,
                "New Job Nearby",
                "{} - ${}".format(job.address, int(job.total_price) if job.total_price else 0),
                {"job_id": job.id, "type": "new_job", "address": job.address}
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception(
                "Failed to send push notification for job %s to contractor %s: %s",
                job.id, contractor.id, e
            )


# ---------------------------------------------------------------------------
# POST /api/booking/abandoned  (capture partial booking for drip recovery)
# ---------------------------------------------------------------------------
@booking_bp.route("/abandoned", methods=["POST"])
def capture_abandoned():
    """Capture a partial booking for email drip recovery.

    Called by the frontend when a user reaches step 6 of booking
    and provides their email. No auth required.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    email = (data.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"error": "Valid email required"}), 400

    # Upsert -- update if same email exists and hasn't converted
    existing = AbandonedBooking.query.filter_by(
        email=email, converted=False
    ).first()

    if existing:
        existing.phone = data.get("phone") or existing.phone
        existing.name = data.get("name") or existing.name
        existing.address = data.get("address") or existing.address
        existing.items = data.get("items") or existing.items
        existing.step = data.get("step") or existing.step
        existing.estimated_price = data.get("estimatedPrice") or existing.estimated_price
        existing.lead_source = data.get("leadSource") or existing.lead_source
        existing.updated_at = utcnow()
    else:
        abandoned = AbandonedBooking(
            id=generate_uuid(),
            email=email,
            phone=data.get("phone"),
            name=data.get("name"),
            address=data.get("address"),
            items=data.get("items"),
            step=data.get("step"),
            estimated_price=data.get("estimatedPrice"),
            lead_source=data.get("leadSource"),
        )
        db.session.add(abandoned)

    db.session.commit()
    return jsonify({"success": True}), 200
