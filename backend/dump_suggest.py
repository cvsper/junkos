"""Where should this hauler dump the load?

Ranks every facility in seed_landfills for a hauler's position, load type and
tonnage on *what the trip actually costs* — tip fee plus the drive — and
explains the pick in plain words the app can show. Conservative on purpose:
a site that can't legally take the load (wrong category, account-only,
out-of-county rule) is never suggested, just listed with the reason.

    GET /api/driver/dump/suggest?lat&lng[&category=bulky][&tons=0.6][&job_id=]
    GET /api/driver/dump/facilities

Cost model (all tunable via env):
    tip   = max(rate * tons, MIN_CHARGE)          -- per_ton rows; None if quote-at-gate
    drive = miles * COST_PER_MILE + minutes/60 * HOURLY
    miles = haversine * ROAD_FACTOR ; minutes = miles / AVG_MPH * 60 + turnaround
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from models import db, Job, LandfillFacility, TipFee
from geofencing import _haversine
from timeutils import BUSINESS_TZ
from seed_landfills import SWA_OUT_OF_COUNTY_RATE, MIN_CHARGE, WALK_IN, ACCOUNT, PERMIT

logger = logging.getLogger(__name__)
dump_bp = Blueprint("dump", __name__, url_prefix="/api/driver/dump")

ROAD_FACTOR = float(os.environ.get("DUMP_ROAD_FACTOR", "1.3"))
AVG_MPH = float(os.environ.get("DUMP_AVG_MPH", "28"))
COST_PER_MILE = float(os.environ.get("DUMP_COST_PER_MILE", "0.65"))
HOURLY = float(os.environ.get("DUMP_HOURLY_VALUE", "30"))
DEFAULT_TONS = float(os.environ.get("DUMP_DEFAULT_TONS", "0.6"))
MAX_MILES = float(os.environ.get("DUMP_MAX_MILES", "45"))
KM_PER_MILE = 1.609344

CATEGORIES = ("msw", "c_and_d", "yard", "bulky", "metal", "appliance_w_freon", "mattress", "tires", "concrete", "drywall", "mixed")
CATEGORY_LABEL = {
    "msw": "garbage", "c_and_d": "construction debris", "yard": "yard waste", "bulky": "bulk junk",
    "metal": "scrap metal", "appliance_w_freon": "appliances", "mattress": "mattresses", "tires": "tires",
    "concrete": "concrete", "drywall": "drywall", "mixed": "a mixed load",
}
# Item-category words that turn a junk load into C&D at the scale.
_CD_WORDS = ("concrete", "drywall", "lumber", "roofing", "shingle", "tile", "brick", "block", "cabinet", "construction",
             "demolition", "renovation", "debris", "fence", "deck", "pallet", "stump", "asphalt", "c_and_d")
_APPLIANCE_WORDS = ("refrigerator", "freezer", "washer", "dryer", "dishwasher", "stove", "microwave", "appliance")
_YARD_WORDS = ("yard", "branch", "palm", "brush", "vegetation", "landscap", "grass", "tree")

# Coastal counties stack north-to-south, so latitude is a good-enough county
# line for "did this load originate in county X".
_COUNTY_BANDS = (("miami-dade", 25.957), ("broward", 26.32), ("palm-beach", 26.97), ("martin", 27.21),
                 ("st-lucie", 27.56), ("indian-river", 27.86), ("brevard", 28.79))
COUNTY_LABEL = {"miami-dade": "Miami-Dade", "broward": "Broward", "palm-beach": "Palm Beach", "martin": "Martin",
                "st-lucie": "St. Lucie", "indian-river": "Indian River", "brevard": "Brevard"}


def county_for(lat):
    if lat is None:
        return None
    for name, north in _COUNTY_BANDS:
        if lat < north:
            return name
    return None


def infer_category(items):
    """Pick the scale-house category a job's item list will be billed at."""
    words = " ".join(
        str(i.get("category") or "") + " " + str(i.get("name") or i.get("label") or "") if isinstance(i, dict) else str(i)
        for i in (items or [])
    ).lower()
    if not words.strip():
        return "bulky"
    if any(w in words for w in _CD_WORDS):
        return "c_and_d"
    if any(w in words for w in _YARD_WORDS) and not any(w in words for w in ("sofa", "mattress", "table", "chair", "desk")):
        return "yard"
    if all(any(w in str(i).lower() for w in _APPLIANCE_WORDS) for i in items):
        return "appliance_w_freon"
    return "bulky"


def _current_fees(facility_ids):
    rows = (TipFee.query.filter(TipFee.facility_id.in_(facility_ids), TipFee.effective_to.is_(None))
            .order_by(TipFee.captured_at.asc()).all())
    out = {}
    for r in rows:
        out.setdefault(r.facility_id, {})[r.category] = r
    return out


def _local_now():
    return datetime.now(timezone.utc).astimezone(BUSINESS_TZ)


def open_state(hours_json, now=None):
    """(open_now, closes_at_str, next_open_str) in business-local time."""
    now = now or _local_now()
    hours = hours_json or {}
    today = hours.get(str(now.weekday()))
    fmt = lambda s: datetime.strptime(s, "%H:%M").strftime("%-I:%M %p").replace(":00", "")  # noqa: E731
    if today:
        o = now.replace(hour=int(today["open"][:2]), minute=int(today["open"][3:]), second=0, microsecond=0)
        c = now.replace(hour=int(today["close"][:2]), minute=int(today["close"][3:]), second=0, microsecond=0)
        if o <= now < c:
            return True, fmt(today["close"]), None
        if now < o:
            return False, None, "today " + fmt(today["open"])
    for d in range(1, 8):
        day = (now.weekday() + d) % 7
        h = hours.get(str(day))
        if h:
            label = "tomorrow" if d == 1 else (now + timedelta(days=d)).strftime("%A")
            return False, None, "{} {}".format(label, fmt(h["open"]))
    return False, None, None


def _drive(from_lat, from_lng, f):
    miles = _haversine(from_lat, from_lng, f.lat, f.lon) / KM_PER_MILE * ROAD_FACTOR
    minutes = miles / AVG_MPH * 60.0
    cost = miles * COST_PER_MILE + (minutes + (f.avg_turnaround_min or 25)) / 60.0 * HOURLY
    return round(miles, 1), int(round(minutes)), round(cost, 2)


def _estimate_rate(category, county, all_fees, facilities):
    """Median published rate for this category, same county first, else region."""
    def median(vals):
        vals = sorted(v for v in vals if v is not None and v > 0)
        return vals[len(vals) // 2] if vals else None
    same = [all_fees.get(f.id, {}).get(category) for f in facilities if f.county == county]
    est = median(r.fee_amount for r in same if r)
    if est is None:
        est = median(r.fee_amount for r in (all_fees.get(f.id, {}).get(category) for f in facilities) if r)
    return est


def evaluate(f, fees, lat, lng, category, tons, origin_county, now=None, est_rate=None):
    """One facility scored for one load. Never raises."""
    miles, minutes, drive_cost = _drive(lat, lng, f)
    is_open, closes_at, next_open = open_state(f.hours_json, now)
    accepts = category in (f.accepts_categories or [])
    blockers, caveats, reasons = [], [], []

    if not accepts:
        blockers.append("Doesn't take {}".format(CATEGORY_LABEL.get(category, category)))
    access = getattr(f, "access", WALK_IN) or WALK_IN
    if access == ACCOUNT:
        blockers.append("Account customers only")
    elif access == PERMIT:
        blockers.append("County hauler permit required, no cash")
    elif access not in (WALK_IN,):
        blockers.append("Residents only")
    if f.origin_county and origin_county and f.origin_county != origin_county:
        blockers.append("Only takes loads from {} County".format(COUNTY_LABEL.get(f.origin_county, f.origin_county)))
    if miles > MAX_MILES:
        blockers.append("{:.0f} mi away".format(miles))

    fee_row = fees.get(category)
    rate = fee_row.fee_amount if fee_row else None
    rate_note = None
    if rate is not None and f.county == "palm-beach" and origin_county and origin_county != "palm-beach" \
            and category in ("msw", "bulky", "mattress", "metal", "c_and_d", "drywall", "mixed"):
        rate, rate_note = SWA_OUT_OF_COUNTY_RATE, "out-of-county rate"
    estimated = False
    if rate is None and est_rate is not None:
        rate, estimated = est_rate, True
    tip = round(max(rate * tons, MIN_CHARGE), 2) if rate is not None else None
    total = round(tip + drive_cost, 2) if tip is not None else None

    if rate is not None and not estimated:
        reasons.append("${:.2f}/ton for {}{} — about ${:.0f} for this load".format(
            rate, CATEGORY_LABEL.get(category, category), " ({})".format(rate_note) if rate_note else "", tip))
    elif estimated:
        caveats.append("No published rate — they quote at the scale; ~${:.0f}/ton is the going rate nearby".format(rate))
    else:
        caveats.append("No published rate — they quote at the scale")
    reasons.append("{:.1f} mi, about {} min from you".format(miles, minutes))
    if is_open:
        reasons.append("Open now, closes {}".format(closes_at))
    elif next_open:
        caveats.append("Closed right now — opens {}".format(next_open))
    else:
        caveats.append("Hours unknown — call first")
    if f.notes:
        caveats.append(f.notes)

    return {
        "facility": f.to_dict(),
        "miles": miles, "minutes": minutes,
        "open_now": is_open, "closes_at": closes_at, "next_open": next_open,
        "rate_per_ton": rate, "rate_note": rate_note, "rate_estimated": estimated,
        "est_tip": tip, "est_drive": drive_cost, "est_total": total,
        "eligible": not blockers, "blockers": blockers, "reasons": reasons, "caveats": caveats,
        "accepts": accepts,
    }


def rank(lat, lng, category="bulky", tons=DEFAULT_TONS, origin_county=None, now=None):
    facilities = LandfillFacility.query.all()
    fees = _current_fees([f.id for f in facilities])
    est_by_county = {c: _estimate_rate(category, c, fees, facilities) for c in {f.county for f in facilities}}
    rows = [evaluate(f, fees.get(f.id, {}), lat, lng, category, tons, origin_county, now, est_by_county.get(f.county))
            for f in facilities]

    def key(r):
        # eligible → open now → known price → cheapest → closest
        return (not r["eligible"], not r["open_now"], r["est_total"] is None, r["est_total"] or 0, r["miles"])
    rows.sort(key=key)
    return rows


def suggest(lat, lng, category="bulky", tons=DEFAULT_TONS, origin_county=None, now=None):
    rows = rank(lat, lng, category, tons, origin_county, now)
    eligible = [r for r in rows if r["eligible"]]
    pick = eligible[0] if eligible else None
    if pick:
        priced = [r for r in eligible if r["est_total"] is not None and r is not pick]
        if pick["est_total"] is not None and priced:
            runner = priced[0]
            saving = runner["est_total"] - pick["est_total"]
            if saving >= 5:
                pick["reasons"].insert(0, "Cheapest trip: saves about ${:.0f} over {}".format(saving, runner["facility"]["name"]))
            else:
                pick["reasons"].insert(0, "Best trip for this load: lowest tip fee plus drive")
        elif pick["est_total"] is None:
            pick["reasons"].insert(0, "Closest place that takes {} — no rate published, ask at the gate".format(
                CATEGORY_LABEL.get(category, category)))
        if pick.get("rate_estimated"):
            pick["reasons"].insert(1, "Closest yard for {}; expect about ${:.0f} at the gate".format(
                CATEGORY_LABEL.get(category, category), pick["est_tip"]))
        else:
            pick["reasons"].insert(0, "Only priced site that can take this load")
    return {
        "suggested": pick,
        "alternatives": [r for r in eligible[1:6]],
        "not_eligible": sorted(({"name": r["facility"]["name"], "miles": r["miles"], "blockers": r["blockers"]}
                                for r in rows if not r["eligible"]), key=lambda r: r["miles"]),
        "assumptions": {"category": category, "category_label": CATEGORY_LABEL.get(category, category), "tons": tons,
                        "origin_county": origin_county, "cost_per_mile": COST_PER_MILE, "hourly_value": HOURLY,
                        "avg_mph": AVG_MPH, "road_factor": ROAD_FACTOR, "min_charge": MIN_CHARGE},
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def _job_point(job):
    for a, b in (("lat", "lng"), ("latitude", "longitude"), ("pickup_lat", "pickup_lng")):
        la, ln = getattr(job, a, None), getattr(job, b, None)
        if la is not None and ln is not None:
            return float(la), float(ln)
    return None, None


@dump_bp.route("/suggest", methods=["GET"])
def dump_suggest_route():
    from auth_routes import authenticate_access_token
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    user, reason = authenticate_access_token(token)
    if not user:
        return jsonify({"error": reason or "Unauthorized"}), 401

    lat = request.args.get("lat", type=float)
    lng = request.args.get("lng", type=float)
    category = (request.args.get("category") or "").strip() or None
    tons = request.args.get("tons", type=float)
    origin_county = (request.args.get("origin_county") or "").strip() or None
    job_id = (request.args.get("job_id") or "").strip()

    job = db.session.get(Job, job_id) if job_id else None
    if job is not None:
        jlat, jlng = _job_point(job)
        if lat is None and jlat is not None:
            lat, lng = jlat, jlng
        if category is None:
            category = infer_category(job.items or [])
        if origin_county is None and jlat is not None:
            origin_county = county_for(jlat)
        if tons is None and getattr(job, "volume_estimate", None):
            # ~15 cu yd of household junk ≈ 1 ton; keep it conservative.
            tons = round(max(0.25, float(job.volume_estimate) / 15.0), 2)
    if lat is None or lng is None:
        return jsonify({"error": "lat and lng are required (or a job_id with a geocoded address)"}), 400
    category = category or "bulky"
    if category not in CATEGORIES:
        return jsonify({"error": "category must be one of " + ", ".join(CATEGORIES)}), 400
    tons = tons or DEFAULT_TONS
    origin_county = origin_county or county_for(lat)
    try:
        return jsonify(suggest(lat, lng, category, tons, origin_county)), 200
    except Exception:
        logger.exception("dump suggest failed")
        return jsonify({"error": "could not rank facilities right now"}), 500


@dump_bp.route("/facilities", methods=["GET"])
def dump_facilities_route():
    facilities = LandfillFacility.query.order_by(LandfillFacility.county, LandfillFacility.name).all()
    fees = _current_fees([f.id for f in facilities])
    out = []
    for f in facilities:
        d = f.to_dict()
        d["fees"] = {cat: r.fee_amount for cat, r in fees.get(f.id, {}).items()}
        d["open_now"], d["closes_at"], d["next_open"] = open_state(f.hours_json)
        out.append(d)
    return jsonify({"facilities": out, "count": len(out)}), 200
