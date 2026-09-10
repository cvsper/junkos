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
from geofencing import is_in_service_area, get_service_area_info, _point_in_polygon
from timeutils import parse_local, fmt_local, local_date_str, local_now, BUSINESS_TZ_NAME
from price_version import (
    ItemValidationError, validate_items, validate_coordinates, compute_price_version,
    quote_scope_hash, verify_quote_claim_token, zip_from_address, normalize_schedule,
    _coerce_quantity,
)

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
    # Hot tubs (2026-08-25 tiers): standard <=7 ft / 4-6 seats vs large 7-9 ft /
    # 6-8 seats or raised-deck carry. Competitor all-in $500-700 standard,
    # $700-1,200 large; crews decline sub-$400 payouts on this job.
    "hot_tub":              {"small": 549.00, "medium": 549.00, "large": 699.00, "default": 549.00},
    "pool_table":           {"default": 269.00},   # competitor: $328; slate weight
    "piano":                {"default": 399.00},   # competitor: $350-$550; two-man minimum, weight
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
# Bulk-debris guards (2026-07-17). The cheap catch-all categories priced
# per item collapse at demo scale: 20x construction @ $45 minus the 20%
# volume discount quoted $778 for a job the commercial market prices at
# $1,700+ — the hauler can net NEGATIVE after C&D dump fees (billed by the
# ton). Two rules:
#   1. Catch-alls never earn the volume discount (they're already floor-priced
#      and their disposal cost scales with quantity, unlike furniture).
#   2. `construction` beyond the base quantity bills at a marginal rate tied
#      to the commercial C&D full-load rate ($1,195 / ~20 item-equivalents ≈
#      $60) — smooth curve, no price cliff mid-funnel. Demo-scale jobs land
#      at market instead of at consumer item prices.
# Commercial per-load rate card (Jul 2026): 1/4 $445 · 1/2 $795 · full $1,195,
# disposal incl. to 2 tons/load — keep marginal rates consistent with it.
# ---------------------------------------------------------------------------
VOLUME_DISCOUNT_EXCLUDED = {"general", "other", "construction", "yard_waste"}
BULK_MARGINAL_RATES = {
    # category: (base_quantity_at_list_price, marginal_rate_beyond_base)
    "construction": (5, 60.00),
}

# Optional booking add-ons (industry-standard upsells; frontend may omit).
ADDON_FEES = {
    "disassembly_items": 25.00,   # per item we take apart (swing set, bed, desk)
    "stair_flights":     15.00,   # per flight of stairs beyond ground level
}
ADDON_LABELS = {
    "disassembly_items": "Disassembly",
    "stair_flights":     "Stairs (per flight)",
}

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
def _zone_contains(boundary, lat, lng):
    """True if the zone geometry contains (lat, lng).

    Accepted ``boundary`` shapes (admin-entered JSON):
      - polygon: ``[{"lat":..,"lng":..}, ...]`` or ``[[lat, lng], ...]`` (>= 3 pts)
      - circle:  ``{"lat":..,"lng":..,"radius_km":..}`` (or ``radius_miles``)
      - bbox:    ``{"north":..,"south":..,"east":..,"west":..}``
    A zone with no usable geometry applies nowhere (audit F10: a zone must
    never change the price of an address it doesn't cover).
    """
    if lat is None or lng is None or not boundary:
        return False
    try:
        if isinstance(boundary, list):
            pts = []
            for p in boundary:
                if isinstance(p, dict):
                    pts.append((float(p["lat"]), float(p["lng"])))
                elif isinstance(p, (list, tuple)) and len(p) >= 2:
                    pts.append((float(p[0]), float(p[1])))
            if len(pts) < 3:
                return False
            return _point_in_polygon(float(lat), float(lng), pts)
        if isinstance(boundary, dict):
            if "polygon" in boundary:
                return _zone_contains(boundary["polygon"], lat, lng)
            if all(k in boundary for k in ("north", "south", "east", "west")):
                return (float(boundary["south"]) <= float(lat) <= float(boundary["north"])
                        and float(boundary["west"]) <= float(lng) <= float(boundary["east"]))
            center = boundary.get("center") if isinstance(boundary.get("center"), dict) else boundary
            if "lat" in center and "lng" in center:
                radius_km = boundary.get("radius_km")
                if radius_km is None and boundary.get("radius_miles") is not None:
                    radius_km = float(boundary["radius_miles"]) * 1.609344
                if radius_km is None:
                    return False
                return _haversine(float(lat), float(lng), float(center["lat"]), float(center["lng"])) <= float(radius_km)
    except (TypeError, ValueError, KeyError):
        return False
    return False


def _active_surge(lat=None, lng=None, when=None):
    """Return ``(multiplier, zone_name)`` for the strongest active surge zone
    whose geometry contains the point. Day/time windows are evaluated in the
    market timezone (America/New_York), not UTC.
    """
    if lat is None or lng is None:
        return 1.0, None
    now = when or local_now()
    current_day = now.weekday()
    current_time = now.strftime("%H:%M")

    try:
        zones = SurgeZone.query.filter_by(is_active=True).all()
    except Exception:
        return 1.0, None
    max_surge = 1.0
    zone_name = None

    for zone in zones:
        if not _zone_contains(zone.boundary, lat, lng):
            continue
        if zone.days_of_week and current_day not in zone.days_of_week:
            continue
        if zone.start_time and current_time < zone.start_time:
            continue
        if zone.end_time and current_time > zone.end_time:
            continue
        if (zone.surge_multiplier or 1.0) > max_surge:
            max_surge = float(zone.surge_multiplier)
            zone_name = zone.name

    return max_surge, zone_name


def _active_surge_multiplier(lat=None, lng=None):
    """Back-compat wrapper: highest applicable zone multiplier for the point."""
    return _active_surge(lat, lng)[0]


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

    # Same-day / next-day are judged on the Florida calendar. Between 8 PM and
    # midnight local the UTC date is already tomorrow, which used to mislabel
    # a next-day booking as same-day surge.
    from timeutils import local_now
    today = local_now().date()
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
def calculate_estimate(items, scheduled_date=None, lat=None, lng=None, addons=None):
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

    # Audit F11: quantities are normalized ONCE, before any arithmetic, and
    # every loop below iterates the same normalized list. The bug was that the
    # item loop skipped a negative quantity while the recycling-fee loop
    # multiplied by it, so "-10 mattresses" subtracted $200 of disposal fees
    # from a valid cart. An unusable quantity now drops the line entirely, in
    # both loops, so a malformed cart can never come out cheaper than the
    # valid one it was built from.
    #
    # This is defence in depth, not the gate: every payable entry point
    # (POST /estimate, create_booking, the portal compatibility route) runs
    # price_version.validate_items first and rejects with 400. Internal
    # callers that price model-generated carts (Maya's phone tools, the SMS
    # photo quote, the call kit) reach this function directly, so it degrades
    # to a correct quote rather than raising into a live phone call.
    if not isinstance(items, (list, tuple)):
        raise ItemValidationError("items array is required")
    normalized = []
    for entry in items:
        if not isinstance(entry, dict):
            continue
        try:
            quantity = _coerce_quantity(entry.get("quantity", 1))
        except ItemValidationError:
            continue
        normalized.append({**entry, "quantity": quantity})
    items = normalized

    for entry in items:
        category = entry.get("category") or "other"
        quantity = entry["quantity"]
        size = entry.get("size")  # optional

        unit_price = _get_item_price(category, size)
        total_quantity += quantity

        bulk_cfg = BULK_MARGINAL_RATES.get(category.lower())
        if bulk_cfg and quantity > bulk_cfg[0]:
            base_qty, marginal_rate = bulk_cfg
            extra_qty = quantity - base_qty
            base_total = unit_price * base_qty
            extra_total = marginal_rate * extra_qty
            item_total += base_total + extra_total
            item_breakdown.append({
                "category": category,
                "quantity": base_qty,
                "unit_price": round(unit_price, 2),
                "line_total": round(base_total, 2),
            })
            item_breakdown.append({
                "category": category,
                "quantity": extra_qty,
                "unit_price": round(marginal_rate, 2),
                "line_total": round(extra_total, 2),
                "size": "bulk",
            })
            continue

        line_total = unit_price * quantity
        item_total += line_total

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
        quantity = entry["quantity"]
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

    # --- Volume discount (catch-all categories excluded — see guard above) ---
    eligible_quantity = 0
    eligible_total = 0.0
    for line in item_breakdown:
        if (line["category"] or "").lower() in VOLUME_DISCOUNT_EXCLUDED:
            continue
        eligible_quantity += line["quantity"]
        eligible_total += line["line_total"]
    discount_rate = _volume_discount_rate(eligible_quantity)
    volume_discount = round(eligible_total * discount_rate, 2)
    volume_discount_label = _volume_discount_label(eligible_quantity)

    items_subtotal = round(item_total - volume_discount, 2)

    # --- Zone-based surge multiplier (only zones covering the point) ---
    zone_surge, zone_name = _active_surge(lat, lng)

    # --- Time-based surge ---
    time_surge_pct, surge_reasons = _time_based_surge(scheduled_date)

    # Combined: zone multiplier is multiplicative, time surge is additive on top
    combined_multiplier = zone_surge * (1.0 + time_surge_pct)

    surged_subtotal = round(items_subtotal * combined_multiplier, 2)
    surge_amount = round(surged_subtotal - items_subtotal, 2)

    if zone_surge > 1.0:
        surge_reasons.insert(0, "High-demand zone{} (x{})".format(
            " — {}".format(zone_name) if zone_name else "", round(zone_surge, 2)))

    # --- Service fee (admin-overridable) ---
    fee_rate = _get_service_fee_rate()
    service_fee = round(surged_subtotal * fee_rate, 2)

    # --- Labor hours (optional, passed from frontend) ---
    labor_hours = 0
    labor_fee = 0.0

    # --- Optional add-ons (flat fees; not surged, not discounted) ---
    addons = addons or {}
    addons_total = 0.0
    addons_breakdown = []
    for addon_key, addon_fee in ADDON_FEES.items():
        try:
            addon_qty = int(addons.get(addon_key) or 0)
        except (TypeError, ValueError):
            addon_qty = 0
        if addon_qty > 0:
            addon_line = round(addon_fee * addon_qty, 2)
            addons_total += addon_line
            addons_breakdown.append({
                "addon": addon_key,
                "label": ADDON_LABELS[addon_key],
                "quantity": addon_qty,
                "unit_fee": addon_fee,
                "total": addon_line,
            })
    addons_total = round(addons_total, 2)

    # --- Total (with minimum floor, admin-overridable) ---
    min_price = _get_minimum_job_price()
    raw_total = round(surged_subtotal + service_fee + recycling_total + labor_fee + addons_total, 2)
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
        "surge_zone": zone_name,
        "zone_surge_multiplier": round(zone_surge, 4),
        "time_surge_pct": round(time_surge_pct, 4),
        "market_timezone": BUSINESS_TZ_NAME,
        "base_price": round(items_subtotal, 2),
        "service_fee": service_fee,
        "recycling_fees": round(recycling_total, 2),
        "recycling_breakdown": recycling_breakdown,
        "labor_fee": labor_fee,
        "labor_fee_rate": LABOR_FEE_PER_HOUR,
        "addons_total": addons_total,
        "addons": addons_breakdown,
        "total": total,
        "minimum_applied": minimum_applied,
        "minimum_job_price": min_price,
        "estimated_duration": estimated_duration,
        "truck_size": truck_size,
        "total_quantity": total_quantity,
    }


def _current_user_id():
    """Authenticated user id from the bearer token, or None (never from the body)."""
    try:
        from auth_routes import verify_token
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        uid = verify_token(token) if token else None
        if uid and not db.session.get(User, uid):
            return None
        return uid
    except Exception:
        return None


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
        address: { street?: str, lat: float, lng: float }
        scheduledDate / scheduled_date: str (ISO date for time-based surge)
        scheduledTimeSlot / scheduled_time: str (slot "8-10" or "HH:MM")
        promo_code / promoCode: str (optional — discount is priced server-side)
        addons: { disassembly_items?: int, stair_flights?: int }

    Returns the full breakdown plus ``price_version`` — the token POST
    /api/booking must echo back. Estimates without coordinates are returned
    for display but flagged ``bookable: false``.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    try:
        items = validate_items(data.get("items"))
    except ItemValidationError as exc:
        return jsonify({"error": str(exc), "code": "invalid_items"}), 400

    address = data.get("address") or {}
    if not isinstance(address, dict):
        address = {"street": str(address)}
    lat = address.get("lat", data.get("lat"))
    lng = address.get("lng", data.get("lng"))
    address_text = address.get("street") or address.get("formatted") or ""

    bookable = True
    if lat is None and lng is None:
        bookable = False
    else:
        try:
            lat, lng = validate_coordinates(lat, lng)
        except ValueError as exc:
            return jsonify({"error": str(exc), "code": "invalid_coordinates"}), 422
        if not is_in_service_area(lat, lng):
            return jsonify({
                "error": "Address is outside our service area. "
                         "We currently serve Miami-Dade, Broward, and Palm Beach counties.",
                "code": "outside_market",
            }), 422

    scheduled_date = data.get("scheduledDate") or data.get("scheduled_date")
    scheduled_time = data.get("scheduledTimeSlot") or data.get("scheduled_time") or data.get("scheduledTime")
    addons = data.get("addons") if isinstance(data.get("addons"), dict) else None

    try:
        result = calculate_estimate(items, scheduled_date=scheduled_date, lat=lat, lng=lng, addons=addons)
    except ItemValidationError as exc:
        return jsonify({"error": str(exc), "code": "invalid_items"}), 400

    # --- Binding photo quote: same scope/ownership rules as booking, not consumed ---
    honored_quote_id = None
    quote_id = (data.get("quote_id") or data.get("quoteId") or "").strip()
    if quote_id:
        try:
            q, honored = _resolve_quote(
                quote_id, items, lat, lng, scheduled_date, result, _current_user_id(),
                data.get("customerEmail") or data.get("customer_email"),
                data.get("quote_token") or data.get("quoteToken"),
            )
        except BookingError as exc:
            return jsonify(exc.to_dict()), exc.status
        if honored is not None:
            result["total"] = honored
            result["quote_locked"] = True
            honored_quote_id = q.id

    # --- Promo (priced here so the version covers the discounted total) ---
    promo_code = (data.get("promo_code") or data.get("promoCode") or "").strip()
    discount = 0.0
    promo_error = None
    if promo_code:
        from routes.promos import validate_promo_code
        promo, disc, promo_error = validate_promo_code(promo_code, result["total"])
        if promo_error:
            promo_code = ""
        else:
            discount = round(float(disc), 2)

    total_before_discount = result["total"]
    total = round(max(0.0, total_before_discount - discount), 2)
    date_part, slot = normalize_schedule(scheduled_date, scheduled_time)
    version = compute_price_version(
        items, lat, lng, address_text, date_part, slot, addons,
        promo_code, discount, result["service_fee"], total, quote_id=honored_quote_id,
    )

    result.update({
        "quote_id": honored_quote_id,
        "total_before_discount": total_before_discount,
        "discount_amount": discount,
        "promo_code": promo_code or None,
        "promo_error": promo_error,
        "total": total,
        "price_version": version,
        "bookable": bookable,
        "scheduled_date": date_part or None,
        "scheduled_time": slot or None,
    })

    return jsonify({
        "success": True,
        "estimate": result,
        "price_version": version,
    }), 200


# ---------------------------------------------------------------------------
# GET /api/booking/market-bounds  (public -- market geometry for the UI)
# ---------------------------------------------------------------------------
@booking_bp.route("/market-bounds", methods=["GET"])
def market_bounds():
    """Server-owned market bounds so expansion never needs a frontend change.

    ``mapbox_bbox`` is "west,south,east,north" for the geocoder; ``proximity``
    is "lng,lat".
    """
    info = get_service_area_info()
    b = info["bounds"]
    c = info["center"]
    return jsonify({
        "success": True,
        "market": {
            "bounds": b,
            "center": c,
            "counties": info["counties"],
            "polygon": info["polygon"],
            "timezone": BUSINESS_TZ_NAME,
            "mapbox_bbox": "{},{},{},{}".format(b["west"], b["south"], b["east"], b["north"]),
            "proximity": "{},{}".format(c["lng"], c["lat"]),
            "country": "us",
        },
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
# Booking service  (audit F09 / F10 / F11 / F30)
# ---------------------------------------------------------------------------
class BookingError(Exception):
    """A booking request that must not create a job. Carries the HTTP status
    and a machine-readable ``code`` so every entry point (canonical route,
    compatibility route, phone flows) answers identically."""

    def __init__(self, message, status=400, code=None, **extra):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.extra = extra

    def to_dict(self):
        body = {"error": self.message}
        if self.code:
            body["code"] = self.code
        body.update(self.extra)
        return body


QUOTE_OPEN_STATUSES = ("draft", "pending_review", "binding", "buffered", "accepted")


def _estimate_payload(est, discount, promo_code, total, version, date_part, slot):
    """Estimate dict as returned by POST /estimate — used in 409 bodies so the
    UI can re-confirm without a second round-trip."""
    payload = dict(est)
    payload.update({
        "total_before_discount": est["total"],
        "discount_amount": round(discount, 2),
        "promo_code": promo_code or None,
        "total": total,
        "price_version": version,
        "scheduled_date": date_part or None,
        "scheduled_time": slot or None,
    })
    return payload


def _resolve_quote(quote_id, items, lat, lng, scheduled_date, est, user_id,
                   customer_email, claim_token):
    """Load + authorize + scope-check a binding quote for conversion.

    Returns ``(quote, honored_total | None)``. Raises BookingError(409) when
    the quote is expired, already used, not owned by the caller, or its
    scope (items + ZIP + schedule surcharge) no longer matches — the caller
    must re-quote; there is no silent fallback to a recomputed price.
    """
    from models import Quote

    q = db.session.get(Quote, quote_id)
    if not q:
        raise BookingError("Quote not found — please get a new quote.", 409, "quote_not_found")

    # --- Ownership: authenticated user, the quote's email challenge, or the
    # claim token issued at creation. Never a body-supplied user_id.
    q_email = (q.guest_email or "").strip().lower()
    req_email = (customer_email or "").strip().lower()
    owns = False
    if q.user_id:
        owns = bool(user_id) and q.user_id == user_id
    elif q_email:
        owns = bool(req_email) and q_email == req_email
    else:
        owns = verify_quote_claim_token(q.id, claim_token)
    if not owns:
        raise BookingError("This quote belongs to a different customer.", 409, "quote_not_owned")

    if q.status not in QUOTE_OPEN_STATUSES or q.booking_id:
        raise BookingError("This quote has already been used — please get a new quote.",
                           409, "quote_already_used")

    exp = q.expires_at
    if exp is not None and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp is not None and exp <= datetime.now(timezone.utc):
        raise BookingError("This quote has expired — please get a new quote.", 409, "quote_expired")

    if not (q.binding and q.price_cents):
        return q, None  # non-binding: linked for attribution, price recomputed

    # --- Scope: items + ZIP must match exactly; a schedule/zone surcharge the
    # quote never priced means the scope changed.
    zip_code = q.zip_code if q.zip_code and q.zip_code != "00000" else ""
    candidates = {
        quote_scope_hash(items, zip_code, ""),
        quote_scope_hash(items, zip_code, scheduled_date),
    }
    if q.scope_hash and q.scope_hash not in candidates:
        raise BookingError(
            "The items or address changed since this quote was issued — please re-quote.",
            409, "quote_scope_mismatch",
        )
    if q.scope_hash != quote_scope_hash(items, zip_code, scheduled_date):
        # Quote was priced without this date; honor it only if the date adds nothing.
        if (est.get("time_surge_pct") or 0) > 0 or (est.get("zone_surge_multiplier") or 1.0) > 1.0:
            raise BookingError(
                "A scheduling surcharge applies to the date you picked that this quote "
                "didn't include — please confirm the updated price.",
                409, "quote_scope_mismatch",
            )
    return q, round(q.price_cents / 100.0, 2)


def _consume_quote(quote, job_id):
    """Single-use conversion: conditional UPDATE inside the booking transaction."""
    from models import Quote
    updated = (
        Quote.query
        .filter(Quote.id == quote.id, Quote.status.in_(QUOTE_OPEN_STATUSES), Quote.booking_id.is_(None))
        .update({"status": "booked", "booking_id": job_id, "booked_at": utcnow()},
                synchronize_session=False)
    )
    return updated == 1


def _parse_address(payload):
    address = payload.get("address")
    if isinstance(address, dict):
        lat = address.get("lat") if address.get("lat") is not None else payload.get("lat")
        lng = address.get("lng") if address.get("lng") is not None else payload.get("lng")
        text = address.get("street") or address.get("formatted") or ", ".join(
            v for v in [address.get("street"), address.get("city"),
                        address.get("state"), address.get("zip")] if v
        )
        zip_code = zip_from_address(address)
    else:
        lat = payload.get("lat")
        lng = payload.get("lng")
        text = address
        zip_code = zip_from_address(address)
    if isinstance(text, str):
        text = text.strip()
    return text, lat, lng, zip_code


def _capture_no_coverage_lead(payload, user_id, address, lat, lng):
    """Never charge for an address we can't fulfil: capture the lead, alert
    admin, and answer with the waitlist message (unchanged behaviour)."""
    from dispatcher import _notify_admin_no_coverage_lead

    customer_email = customer_phone = customer_name = ""
    try:
        if user_id:
            user_obj = db.session.get(User, user_id)
            if user_obj:
                customer_email = (user_obj.email or "").strip().lower()
                customer_phone = user_obj.phone or ""
                customer_name = user_obj.name or ""
        if not customer_email:
            customer_email = (
                payload.get("email") or payload.get("guest_email")
                or payload.get("customerEmail") or ""
            ).strip().lower()
        if not customer_phone:
            customer_phone = (payload.get("phone") or payload.get("customerPhone") or "").strip()
        if not customer_name:
            customer_name = (payload.get("name") or payload.get("customerName") or "").strip()
    except Exception:
        pass

    if customer_email:
        try:
            existing = AbandonedBooking.query.filter_by(email=customer_email, converted=False).first()
            if existing:
                existing.address = address or existing.address
                existing.phone = customer_phone or existing.phone
                existing.name = customer_name or existing.name
                existing.items = payload.get("items") or existing.items
                existing.estimated_price = payload.get("estimated_price") or existing.estimated_price
                existing.lead_source = "no_coverage_waitlist"
                existing.step = 99
                existing.waitlist_lat = lat
                existing.waitlist_lng = lng
            else:
                db.session.add(AbandonedBooking(
                    email=customer_email,
                    phone=customer_phone or None,
                    name=customer_name or None,
                    address=address,
                    items=payload.get("items"),
                    estimated_price=payload.get("estimated_price"),
                    lead_source="no_coverage_waitlist",
                    step=99,
                    waitlist_lat=lat,
                    waitlist_lng=lng,
                ))
            db.session.commit()
            try:
                from waitlist import send_holding_email
                send_holding_email(customer_email, customer_name, address)
            except Exception:
                pass
        except Exception:
            db.session.rollback()
            import logging
            logging.getLogger(__name__).exception(
                "Failed to capture no-coverage waitlist lead for %s", customer_email)

    try:
        _notify_admin_no_coverage_lead(
            address=address, lat=lat, lng=lng,
            customer_email=customer_email, customer_phone=customer_phone,
            customer_name=customer_name, items=payload.get("items"),
            estimated_price=payload.get("estimated_price"),
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Failed to alert admin about no-coverage lead at %s", address)

    raise BookingError(
        "We don't have a hauler available at this address yet, but your area is in "
        "our service zone. We've saved your request and our team will text you a "
        "confirmed time within 2 hours. No charge has been made.",
        400, "no_coverage", status="waitlist",
    )


def create_booking(payload, user, notify_operator=True):
    """Canonical booking service used by POST /api/booking and every
    compatibility adapter.

    ``payload`` is the request body (camelCase or snake_case accepted);
    ``user`` is the authenticated user id or ``None`` for a guest.

    Returns ``(body, 201)``. Raises :class:`BookingError` — including a 409
    ``price_changed`` (with the fresh estimate + ``price_version``) whenever
    the total the customer confirmed no longer matches the server's price.

    Contract changes (audit):
      * coordinates are REQUIRED and validated (422 ``invalid_coordinates`` /
        ``outside_market``) — no geofence bypass for missing/garbage coords;
      * items are strictly validated (400 ``invalid_items``);
      * ``price_version`` from /estimate is required. Clients that predate it
        may echo ``estimated_price`` instead; it must equal the server total;
      * binding quotes are scope-checked and consumed atomically (409
        ``quote_*``), never silently re-priced;
      * the job's ``total_price`` is the FINAL charge (promo already netted)
        — payments must not subtract ``discount_amount`` again;
      * nothing is sent to haulers and no "confirmed" message goes to the
        customer here — those fire on payment success.
    """
    user_id = user
    if not isinstance(payload, dict) or not payload:
        raise BookingError("Request body is required")

    # --- Address + coordinates (required, validated, inside the market) ---
    address, lat, lng, zip_code = _parse_address(payload)
    if not address:
        raise BookingError("address is required")
    try:
        lat, lng = validate_coordinates(lat, lng)
    except ValueError as exc:
        raise BookingError(str(exc), 422, "invalid_coordinates")
    if not is_in_service_area(lat, lng):
        raise BookingError(
            "Address is outside our service area. We currently serve Miami-Dade, "
            "Broward, and Palm Beach counties.",
            422, "outside_market",
        )

    # --- Coverage: is there actually a hauler in range? (never charge otherwise)
    try:
        from dispatcher import has_active_coverage
        covered = has_active_coverage(lat, lng)
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Coverage check failed unexpectedly — allowing booking to proceed")
        covered = True
    if not covered:
        _capture_no_coverage_lead(payload, user_id, address, lat, lng)

    # --- Items (strict) ---
    try:
        items = validate_items(payload.get("items"))
    except ItemValidationError as exc:
        raise BookingError(str(exc), 400, "invalid_items")

    # --- Price consent inputs ---
    client_version = (payload.get("price_version") or payload.get("priceVersion") or "").strip()
    estimated_price = payload.get("estimated_price", payload.get("estimatedPrice"))
    if estimated_price is not None:
        try:
            estimated_price = float(estimated_price)
        except (TypeError, ValueError):
            raise BookingError("estimated_price must be a number")
    if not client_version and estimated_price is None:
        raise BookingError("price_version is required (from POST /api/booking/estimate)",
                           400, "price_version_required")

    # --- Schedule (Florida wall-clock -> UTC) ---
    scheduled_at = None
    scheduled_date = payload.get("scheduled_date") or payload.get("scheduledDate")
    scheduled_time = (payload.get("scheduled_time") or payload.get("scheduledTimeSlot")
                      or payload.get("scheduledTime") or "09:00")
    if scheduled_date:
        try:
            scheduled_at = parse_local(scheduled_date, scheduled_time)
        except (ValueError, TypeError):
            raise BookingError("Invalid scheduled_date or scheduled_time format")
    date_part, slot = normalize_schedule(scheduled_date, scheduled_time if scheduled_date else None)

    photos = payload.get("photos") or payload.get("photoUrls") or payload.get("photo_urls") or []
    if not isinstance(photos, list):
        photos = []
    notes = payload.get("notes", "") or ""
    lead_source = payload.get("lead_source") or payload.get("leadSource") or None

    from impact import normalize_preference
    disposition_preference = normalize_preference(
        payload.get("disposition_preference") or payload.get("dispositionPreference")
    )

    addons = payload.get("addons") if isinstance(payload.get("addons"), dict) else None

    # --- Server price ---
    try:
        est = calculate_estimate(items, scheduled_date=scheduled_date, lat=lat, lng=lng, addons=addons)
    except ItemValidationError as exc:
        raise BookingError(str(exc), 400, "invalid_items")

    total = est["total"]
    service_fee = est["service_fee"]
    surge_multiplier = est["surge_multiplier"]
    item_total = est["items_subtotal"]

    guest_email = (payload.get("customerEmail") or payload.get("customer_email")
                   or payload.get("email") or "").strip().lower()

    # --- Binding quote (scope-checked; consumed atomically below) ---
    quote_to_convert = None
    honored_quote_id = None
    quote_id = (payload.get("quote_id") or payload.get("quoteId") or "").strip()
    if quote_id:
        quote_to_convert, honored = _resolve_quote(
            quote_id, items, lat, lng, scheduled_date, est, user_id, guest_email,
            payload.get("quote_token") or payload.get("quoteToken"),
        )
        if honored is not None:
            total = honored
            item_total = honored
            honored_quote_id = quote_to_convert.id

    # --- Promo (booking is the single owner of the discount) ---
    promo_code_str = (payload.get("promo_code") or payload.get("promoCode") or "").strip()
    promo_code_id = None
    discount_amount = 0.0
    if promo_code_str:
        from routes.promos import validate_promo_code
        promo, discount, promo_error = validate_promo_code(promo_code_str, total)
        if promo_error:
            raise BookingError(promo_error, 400, "invalid_promo")
        promo_code_id = promo.id
        discount_amount = round(float(discount), 2)
        total = round(max(0.0, total - discount_amount), 2)
        # use_count is incremented on PAYMENT SUCCESS, never here.

    # --- One server-issued price version; the client must have seen THIS price ---
    address_text = address if isinstance(address, str) else ""
    version = compute_price_version(
        items, lat, lng, address_text, date_part, slot, addons,
        promo_code_str, discount_amount, service_fee, total,
        quote_id=honored_quote_id,
    )
    if client_version:
        consented = client_version == version
    else:
        consented = abs(float(estimated_price) - total) <= 0.01
    if not consented:
        raise BookingError(
            "The price has changed since you last saw it — please review and confirm "
            "the updated total.",
            409, "price_changed",
            estimate=_estimate_payload(est, discount_amount, promo_code_str, total, version, date_part, slot),
            price_version=version,
            total=total,
        )

    # --- Resolve customer (auth user or guest) ---
    if not user_id:
        guest_name = (payload.get("customerName") or payload.get("name") or "").strip()
        guest_phone = (payload.get("customerPhone") or payload.get("phone") or "").strip()
        if not guest_email:
            raise BookingError("Email is required for guest checkout")
        existing = User.query.filter_by(email=guest_email).first()
        if existing:
            user_id = existing.id
            if guest_name and not existing.name:
                existing.name = guest_name
            if guest_phone and not existing.phone:
                existing.phone = guest_phone
        else:
            guest_user = User(
                id=generate_uuid(), email=guest_email, name=guest_name or None,
                phone=guest_phone or None, role="customer",
            )
            db.session.add(guest_user)
            db.session.flush()
            user_id = guest_user.id

    # --- Create Job + Payment ---
    job = Job(
        id=generate_uuid(),
        customer_id=user_id,
        status="pending",
        address=address,
        lat=lat,
        lng=lng,
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
        price_version=version,
        notes=notes,
        lead_source=lead_source,
        disposition_preference=disposition_preference,
        confirmation_code=generate_referral_code(),
    )
    db.session.add(job)
    db.session.flush()

    if quote_to_convert is not None and not _consume_quote(quote_to_convert, job.id):
        db.session.rollback()
        raise BookingError("This quote has already been used — please get a new quote.",
                           409, "quote_already_used")

    payment = Payment(
        id=generate_uuid(),
        job_id=job.id,
        amount=total,
        service_fee=service_fee,
        payment_status="pending",
    )
    db.session.add(payment)
    db.session.commit()

    # NOTE (audit F30): no hauler broadcast, no "Booking Confirmed" email/SMS
    # here — the job is unpaid. Payment success (routes/payments.py) sends the
    # confirmation and triggers dispatch.

    # --- Mark abandoned booking as converted ---
    try:
        customer = db.session.get(User, user_id)
        if customer and customer.email:
            abandoned = AbandonedBooking.query.filter_by(email=customer.email, converted=False).first()
            if abandoned:
                abandoned.converted = True
                db.session.commit()
    except Exception:
        pass

    # --- Schedule abandoned booking recovery SMS (30 min) — unpaid-job safety net ---
    try:
        customer = db.session.get(User, user_id)
        if customer and customer.phone:
            from flask import current_app
            from sms_service import schedule_abandoned_booking_sms
            schedule_abandoned_booking_sms(
                to_phone=customer.phone, customer_name=customer.name or "",
                job_id=job.id, app=current_app._get_current_object(), delay_seconds=1800,
            )
    except Exception:
        pass

    # --- Internal heads-up to the operator line (clearly labelled unpaid) ---
    if notify_operator:
        try:
            from sms_service import send_sms_async
            operator_phone = os.environ.get("OPERATOR_PHONE", "")
            if operator_phone:
                items_count = sum(i.get("quantity", 1) for i in items)
                send_sms_async(operator_phone, (
                    "NEW BOOKING (awaiting payment)\n{} - {} item{}\n${:.0f} | {}\nScheduled: {}"
                ).format(
                    address or "No address", items_count, "s" if items_count != 1 else "",
                    total, lead_source or "direct", local_date_str(scheduled_at, "ASAP"),
                ))
        except Exception:
            pass

    # --- n8n webhooks (existing automation; unchanged) ---
    try:
        import urllib.request
        import json as _json
        n8n_base = os.environ.get("N8N_WEBHOOK_URL", "")
        if n8n_base:
            customer = db.session.get(User, user_id)
            body = _json.dumps({
                "booking_id": job.confirmation_code or str(job.id)[:8],
                "customer_name": customer.name if customer else "Customer",
                "customer_email": customer.email if customer else "",
                "scheduled_date": fmt_local(scheduled_at, "%B %d, %Y", "ASAP"),
                "estimated_cost": "{:.2f}".format(total),
                "address": address or "",
            }).encode()
            headers = {"Content-Type": "application/json"}
            for path in ("/webhook/vnFFMeYDQOB8QIXa/webhook/booking-notification",
                         "/webhook/uaxzeHYyyF2twCvH/webhook/review-request"):
                req = urllib.request.Request(n8n_base + path, data=body, headers=headers, method="POST")
                urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass

    from cancellation import make_manage_token
    customer = db.session.get(User, user_id)
    manage_token = make_manage_token(job.id, customer.email if customer else "")

    # Scoped checkout capability for the (possibly guest) client: the public
    # create-intent route accepts it in place of the owner's JWT (audit F06).
    try:
        from routes.payments import checkout_token as _checkout_token
        _ck = _checkout_token(job.id)
    except Exception:
        _ck = None

    return {
        "success": True,
        "job": job.to_dict(),
        "payment": payment.to_dict(),
        "price_version": version,
        "manage_token": manage_token,
        "checkout_token": _ck,
    }, 201


# ---------------------------------------------------------------------------
# POST /api/booking  (guest or auth)
# ---------------------------------------------------------------------------
@booking_bp.route("", methods=["POST"])
@limiter.limit("10 per minute")
@optional_auth
def create_booking_endpoint(user_id):
    """Create a new job / booking. See :func:`create_booking` for the contract.

    Body JSON:
        address: { street, lat, lng, ... } | str (+ lat, lng)
        items: [{ category, quantity, size? }]
        scheduled_date / scheduledDate, scheduled_time / scheduledTimeSlot
        price_version: str (from /estimate)  -- required
        promo_code, quote_id, quote_token, photos, notes, lead_source,
        customerName / customerEmail / customerPhone (guest checkout)
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body is required"}), 400
    try:
        body, status = create_booking(data, user_id)
    except BookingError as exc:
        return jsonify(exc.to_dict()), exc.status
    return jsonify(body), status


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

    # Audit F21: customer serializer (no internal ops flags, hauler reduced to
    # the arrival profile) and a rating without the rater's contact details.
    from serializers import job_for_customer, rating_public
    result = job_for_customer(job)

    if job.payment:
        result["payment"] = {
            "payment_status": job.payment.payment_status,
            "amount": job.payment.amount,
            "tip_amount": job.payment.tip_amount,
        }
    else:
        result["payment"] = None

    result["rating"] = rating_public(job.rating) if job.rating else None

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
