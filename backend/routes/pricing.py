"""
Pricing API routes for JunkOS.
Hybrid pricing: item-based + volume-based + surge multiplier.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timezone

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, PricingRule, SurgeZone

pricing_bp = Blueprint("pricing", __name__, url_prefix="/api/pricing")

BASE_SERVICE_FEE = 15.00
VOLUME_RATE_PER_YARD = 35.00
COMMISSION_RATE = 0.20


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


@pricing_bp.route("/estimate", methods=["POST"])
def get_estimate():
    """
    Calculate a hybrid price estimate.
    Body JSON: items (list of str), volume (float), lat (float), lng (float)
    """
    data = request.get_json() or {}
    item_names = data.get("items", [])
    volume = data.get("volume")
    lat = data.get("lat")
    lng = data.get("lng")

    # Item-based pricing
    item_total = 0.0
    matched_items = []
    if item_names:
        rules = PricingRule.query.filter(
            PricingRule.item_type.in_(item_names),
            PricingRule.is_active == True,
        ).all()
        rule_map = {r.item_type: r for r in rules}

        for name in item_names:
            rule = rule_map.get(name)
            if rule:
                item_total += rule.base_price
                matched_items.append({"item_type": name, "price": rule.base_price})
            else:
                matched_items.append({"item_type": name, "price": 0.0, "note": "no pricing rule found"})

    # Volume-based pricing
    volume_price = 0.0
    if volume and float(volume) > 0:
        volume_price = float(volume) * VOLUME_RATE_PER_YARD

    # Surge
    surge = _active_surge_multiplier(lat, lng)

    subtotal = item_total + volume_price
    surged_subtotal = subtotal * surge
    service_fee = BASE_SERVICE_FEE
    total = round(surged_subtotal + service_fee, 2)

    return jsonify({
        "success": True,
        "estimate": {
            "item_total": round(item_total, 2),
            "volume_price": round(volume_price, 2),
            "subtotal": round(subtotal, 2),
            "surge_multiplier": surge,
            "surged_subtotal": round(surged_subtotal, 2),
            "service_fee": service_fee,
            "total": total,
            "items": matched_items,
        },
    }), 200


@pricing_bp.route("/rules", methods=["GET"])
def get_rules():
    """Return all active pricing rules."""
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
def get_surge_zones():
    """Return all active surge zones."""
    zones = SurgeZone.query.filter_by(is_active=True).all()
    return jsonify({
        "success": True,
        "surge_zones": [z.to_dict() for z in zones],
    }), 200
