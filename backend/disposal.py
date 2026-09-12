"""Dump fees in the customer's price.

Every load ends at a scale house, and the hauler pays by the ton at
whatever that county charges. Item prices were tuned assuming a light
household load; heavy or C&D carts made haulers eat the ticket. This
module turns a cart into an expected weigh-ticket for the job's address
— using the same facility data and ranking as the "Where to dump" card —
so the quote carries it as its own line and the payout passes it through
to the hauler untouched.

    disposal_estimate(items, lat, lng) -> {
        "disposal_fee": 25.20, "tons": 0.6, "category": "bulky",
        "rate_per_ton": 42.0, "facility": "SWA Central County ...",
        "rate_source": "facility" | "default", "lbs_by_category": {...}
    }
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Typical weight per item, lb. Conservative (rounded up) — a light estimate
# leaves the hauler short at the scale; a heavy one costs the customer a
# couple of dollars. Per-cubic-yard buckets (construction, yard_waste) use
# industry densities: mixed C&D ~500 lb/yd³, yard trash ~250, loose junk ~100.
ITEM_WEIGHT_LBS = {
    # furniture
    "sofa": 180, "sofa_sleeper": 260, "sofa_sectional": 320, "chair_recliner": 100, "chair_office": 40,
    "dresser": 150, "bookcase": 90, "cabinet": 120, "table_dining": 150, "table_dining_chairs": 80,
    "table_coffee": 60, "table_end": 30, "table_kitchen": 90, "table_conference": 250, "futon": 120,
    "filing_cabinet": 110, "desk_small": 90, "desk_large": 200, "mattress": 70, "box_spring": 60,
    "bed_frame": 80, "bed_set": 220,
    # appliances
    "refrigerator": 280, "refrigerator_bar": 70, "washer": 200, "dryer": 130, "washer_dryer_set": 330,
    "dishwasher": 110, "stove": 170, "microwave": 35, "freezer_chest": 180, "freezer_upright": 220,
    # electronics
    "tv_flatscreen": 45, "tv_console": 110, "tv_stand": 60, "entertainment_center": 180, "computer": 30,
    "copier_commercial": 300, "printer": 25,
    # specialty
    "treadmill": 220, "elliptical": 180, "bike_stationary": 90, "bbq_grill": 90, "basketball_hoop": 130,
    "basketball_hoop_stand": 200, "lawn_mower_push": 80, "lawn_mower_riding": 450, "hot_tub": 900,
    "pool_table": 700, "piano": 500, "bike": 30,
    # catch-alls (per item / per cubic yard)
    "general": 100, "other": 100, "furniture": 150, "appliances": 180, "electronics": 50,
    "construction": 500, "yard_waste": 250,
}
DEFAULT_WEIGHT_LBS = 100

# Which scale-house category each item is billed under.
SCALE_CATEGORY = {
    "construction": "c_and_d", "hot_tub": "c_and_d",
    "yard_waste": "yard",
    "mattress": "mattress", "box_spring": "mattress",
    "refrigerator": "appliance_w_freon", "refrigerator_bar": "appliance_w_freon", "washer": "appliance_w_freon",
    "dryer": "appliance_w_freon", "washer_dryer_set": "appliance_w_freon", "dishwasher": "appliance_w_freon",
    "stove": "appliance_w_freon", "freezer_chest": "appliance_w_freon", "freezer_upright": "appliance_w_freon",
    "appliances": "appliance_w_freon",
}
# Mixed loads are billed at the highest category on board, so this is the
# order we resolve a cart to one ticket category.
_PRECEDENCE = ("tires", "c_and_d", "concrete", "drywall", "mixed", "msw", "bulky", "mattress", "metal", "yard",
               "appliance_w_freon")

# Fallback when the job has no coordinates or the facility table is empty:
# SWA (Palm Beach) Rev 6, our home market.
DEFAULT_RATES = {"msw": 42.0, "bulky": 42.0, "mattress": 42.0, "metal": 42.0, "appliance_w_freon": 10.0,
                 "yard": 35.0, "c_and_d": 80.0, "drywall": 80.0, "concrete": 80.0, "mixed": 80.0, "tires": 125.0}
MIN_CHARGE = 10.0
LBS_PER_TON = 2000.0


def _quantity(entry):
    try:
        q = int(entry.get("quantity", 1))
    except (TypeError, ValueError):
        return 0
    return max(0, q)


def load_profile(items):
    """Pounds by scale category for a cart, plus the ticket category and tons."""
    from routes.booking import resolve_item_category
    lbs = {}
    for entry in items or []:
        if not isinstance(entry, dict):
            continue
        q = _quantity(entry)
        if q <= 0:
            continue
        item = resolve_item_category(entry)
        cat = SCALE_CATEGORY.get(item, "bulky")
        lbs[cat] = lbs.get(cat, 0) + ITEM_WEIGHT_LBS.get(item, DEFAULT_WEIGHT_LBS) * q
    total_lbs = sum(lbs.values())
    category = next((c for c in _PRECEDENCE if c in lbs), "bulky")
    return {"lbs_by_category": lbs, "total_lbs": total_lbs,
            "tons": round(total_lbs / LBS_PER_TON, 3), "category": category}


def _facility_rate(lat, lng, category, tons):
    """(rate_per_ton, facility_name, estimated?) from the ranked facilities, or None."""
    if lat is None or lng is None:
        return None
    try:
        import dump_suggest
        out = dump_suggest.suggest(float(lat), float(lng), category, max(tons, 0.1),
                                   dump_suggest.county_for(float(lat)))
    except Exception:
        logger.debug("disposal: facility lookup unavailable", exc_info=True)
        return None
    pick = out.get("suggested")
    if not pick or pick.get("rate_per_ton") is None:
        return None
    return float(pick["rate_per_ton"]), pick["facility"]["name"], bool(pick.get("rate_estimated"))


def disposal_estimate(items, lat=None, lng=None):
    """What the scale will charge for this cart at the job's address. Never raises."""
    try:
        profile = load_profile(items)
    except Exception:
        logger.exception("disposal: could not profile items")
        profile = {"lbs_by_category": {}, "total_lbs": 0, "tons": 0.0, "category": "bulky"}
    tons, category = profile["tons"], profile["category"]
    if tons <= 0:
        return {"disposal_fee": 0.0, "tons": 0.0, "category": category, "rate_per_ton": 0.0,
                "facility": None, "rate_source": "none", "lbs_by_category": {}}

    found = _facility_rate(lat, lng, category, tons)
    if found:
        rate, facility, estimated = found
        source = "facility_estimate" if estimated else "facility"
    else:
        rate, facility, source = DEFAULT_RATES.get(category, DEFAULT_RATES["bulky"]), None, "default"
    fee = round(max(rate * tons, MIN_CHARGE), 2)
    return {"disposal_fee": fee, "tons": tons, "category": category, "rate_per_ton": round(rate, 2),
            "facility": facility, "rate_source": source, "lbs_by_category": profile["lbs_by_category"]}
