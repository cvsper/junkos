"""
Pricing API routes for Umuve.
Exposes the v2 pricing engine, pricing rules, surge zones, and category
catalogue for admin and frontend consumption.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timezone

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extensions import limiter
from auth_routes import require_admin
from models import db, PricingRule, SurgeZone
from routes.booking import (
    calculate_estimate,
    CATEGORY_PRICES,
    VOLUME_DISCOUNT_TIERS,
    MINIMUM_JOB_PRICE,
    SAME_DAY_SURGE,
    NEXT_DAY_SURGE,
    WEEKEND_SURGE,
    _get_service_fee_rate,
    _get_demand_surge_config,
)

pricing_bp = Blueprint("pricing", __name__, url_prefix="/api/pricing")

COMMISSION_RATE = 0.20


@pricing_bp.route("/estimate", methods=["POST"])
@limiter.limit("20 per minute")
def get_estimate():
    """
    Calculate a price estimate using the v2 pricing engine.

    Body JSON (v2 format -- preferred):
        items: [ { category: str, quantity: int, size?: str }, ... ]
        scheduledDate: str (ISO date)
        address: { lat: float, lng: float }

    Body JSON (legacy format -- still supported):
        items: list of str (item-type names)
        volume: float (cubic yards)
        lat: float
        lng: float

    Returns the full v2 breakdown.
    """
    data = request.get_json() or {}

    # --- Detect format: v2 (list of dicts) vs legacy (list of strings) ---
    raw_items = data.get("items", [])

    if raw_items and isinstance(raw_items[0], dict):
        # v2 format
        items = raw_items
    else:
        # Legacy format: list of item-type strings -> convert to v2
        items = [{"category": name, "quantity": 1} for name in raw_items]

    # Support legacy volume field by adding a "yard_waste" line
    volume = data.get("volume")
    if volume and float(volume) > 0:
        items.append({"category": "yard_waste", "quantity": int(float(volume))})

    address = data.get("address") or {}
    lat = address.get("lat") or data.get("lat")
    lng = address.get("lng") or data.get("lng")
    scheduled_date = data.get("scheduledDate") or data.get("scheduled_date")

    result = calculate_estimate(items, scheduled_date=scheduled_date, lat=lat, lng=lng)

    return jsonify({
        "success": True,
        "estimate": result,
    }), 200


@pricing_bp.route("/rules", methods=["GET"])
@require_admin
def get_rules(user_id):
    """Return all active pricing rules (admin only — raw internal config)."""
    active_only = request.args.get("active", "true").lower() == "true"
    query = PricingRule.query
    if active_only:
        query = query.filter_by(is_active=True)
    rules = query.order_by(PricingRule.item_type).all()

    return jsonify({
        "success": True,
        "rules": [r.to_dict() for r in rules],
    }), 200


@pricing_bp.route("/surge", methods=["GET"])
@require_admin
def get_surge_zones(user_id):
    """Return all active surge zones (admin only — raw internal config)."""
    zones = SurgeZone.query.filter_by(is_active=True).all()
    return jsonify({
        "success": True,
        "surge_zones": [z.to_dict() for z in zones],
    }), 200


@pricing_bp.route("/categories", methods=["GET"])
def get_categories():
    """Return the full category catalogue with default prices.

    Merges hardcoded defaults with any active PricingRule overrides from the
    database so the frontend always has a complete list.
    """
    # Start with hardcoded defaults
    categories = {}
    for cat, sizes in CATEGORY_PRICES.items():
        categories[cat] = dict(sizes)

    # Layer on DB overrides
    rules = PricingRule.query.filter_by(is_active=True).all()
    for rule in rules:
        key = rule.item_type  # e.g. "furniture" or "furniture:large"
        if ":" in key:
            cat, size = key.split(":", 1)
            if cat not in categories:
                categories[cat] = {"default": rule.base_price}
            categories[cat][size] = rule.base_price
        else:
            if key not in categories:
                categories[key] = {}
            categories[key]["default"] = rule.base_price

    return jsonify({
        "success": True,
        "categories": categories,
    }), 200


@pricing_bp.route("/config", methods=["GET"])
def get_pricing_config():
    """Return the CUSTOMER-FACING pricing configuration (tiers, surge rates,
    minimum price). Internal economics (commission, fee rate) are excluded —
    see the admin-only ``/config/economics`` endpoint."""
    return jsonify({
        "success": True,
        "config": {
            "minimum_job_price": MINIMUM_JOB_PRICE,
            "volume_discount_tiers": [
                {"min_qty": lo, "max_qty": hi, "discount_rate": rate}
                for lo, hi, rate in VOLUME_DISCOUNT_TIERS
            ],
            "time_surge": {
                "same_day": SAME_DAY_SURGE,
                "next_day": NEXT_DAY_SURGE,
                "weekend": WEEKEND_SURGE,
            },
        },
    }), 200


@pricing_bp.route("/config/economics", methods=["GET"])
@require_admin
def get_pricing_economics(user_id):
    """Admin-only: internal pricing economics that must NOT be public —
    platform commission, service-fee rate, and demand-surge configuration."""
    enabled, radius, max_mult, tiers = _get_demand_surge_config()
    return jsonify({
        "success": True,
        "economics": {
            "commission_rate": COMMISSION_RATE,
            "service_fee_rate": _get_service_fee_rate(),
            "demand_surge": {
                "enabled": enabled,
                "radius_miles": radius,
                "max_multiplier": max_mult,
                "tiers": [{"ratio": r, "multiplier": m} for r, m in tiers],
            },
        },
    }), 200
