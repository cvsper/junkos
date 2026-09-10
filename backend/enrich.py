"""Card prep: a generated angle for every prospect, and a live Google listing
when the card is dealt.

Angle — the one line Tracy leads with for THIS company. Written by hand on the
older lists; blank on the faster ones. `generate_angle(p)` fills it from the
segment + the research line (`why`), with Claude Haiku when ANTHROPIC_API_KEY is
set and a template otherwise. Runs on import (merge_rows hook) and as a backfill
job for anything still blank.

Enrichment — Places Text Search (New) for "company, city": rating, review
count, open now, website, Maps link, business status. Cached 7 days per
prospect in desk_settings. Shown under the card's meta line.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from models import db, CallProspect, DeskSetting
from desk_auth import desk_identity, require_desk, audit, MANAGER_ROLES

try:
    from extensions import limiter
except Exception:  # pragma: no cover
    limiter = None

logger = logging.getLogger(__name__)
enrich_bp = Blueprint("enrich", __name__)
_ratelimit = (limiter.limit("240 per hour; 30 per minute") if limiter is not None else (lambda f: f))

ENRICH_TTL_DAYS = 7

# ---------------------------------------------------------------------------
# angles
# ---------------------------------------------------------------------------
_DEMAND_ANGLES = {
    "property": "Standing account with volume rates — one text and the unit is rentable in 24h.",
    "storage": "Abandoned unit back to rentable in a day, flat price, manager just texts the unit number.",
    "estate": "Be the full-service option: sale closes Saturday, house cleared Monday, family gets the keys back.",
    "realtor": "One number for sellers' cleanouts, upfront price, 10% referral credit on every job.",
    "flipper": "Photo quote, cleared same or next day so demo starts day one — no dumpster sitting.",
    "senior": "The respectful haul-away leg for downsizing families; you stay the trusted face.",
    "mover": "Hand off the 'don't move it' pile — we pick up the leftovers on your schedule.",
    "contractor": "Tear-out debris gone from a photo, same or next day, crew stays on the job.",
    "thrift": "Scheduled overflow pickups at a flat rate so donations never pile up out back.",
}
_SUPPLY_ANGLE = ("Booked, paid junk jobs to their phone; they keep the majority and cash out same day — "
                 "no fees, no app needed to start.")


def template_angle(p):
    from call_kit import detect_side, demand_segment
    if detect_side(p) == "supply":
        cat = (p.category or "").lower()
        if "appliance" in cat:
            return "They already run a truck for deliveries — fill the empty return leg with paid haul-away jobs."
        if "dumpster" in cat:
            return "Small-load jobs their roll-offs can't price — paid work between drop-offs, no fees."
        if "mov" in cat or "flete" in cat or "mudanza" in cat:
            return "Their crew and truck already roll daily — add paid junk jobs on the way, keep the majority."
        return _SUPPLY_ANGLE
    return _DEMAND_ANGLES.get(demand_segment(p.category), _DEMAND_ANGLES["property"])


def llm_angle(p, side):
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key or os.environ.get("ANGLE_LLM", "on").lower() == "off":
        return None
    goal = ("recruiting this hauling business to take booked, paid junk-removal jobs from Umuve "
            "(they keep the majority, same-day payout, no fees)"
            if side == "supply" else
            "selling Umuve's junk-removal/cleanout service to this business as a standing vendor")
    prompt = ("Write ONE sentence (max 140 characters) a caller should lead with for this company. "
              "Goal: {goal}.\nCompany: {co}\nType: {cat}\nCity: {city}\nResearch: {why}\n"
              "Be specific to what they do; no greeting, no fluff, no exclamation marks. Return only the sentence."
              ).format(goal=goal, co=p.company, cat=p.category or "", city=p.city or "", why=(p.why or "")[:400])
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(model=os.environ.get("COPILOT_MODEL", "claude-haiku-4-5-20251001"),
                                      max_tokens=80, messages=[{"role": "user", "content": prompt}])
        text = "".join(getattr(b, "text", "") for b in resp.content).strip().strip('"')
        text = re.sub(r"\s+", " ", text)
        return text[:200] if 20 <= len(text) <= 200 else None
    except Exception:
        logger.exception("llm angle failed for %s", p.id)
        return None


def generate_angle(p, use_llm=True):
    from call_kit import detect_side
    side = detect_side(p)
    return (llm_angle(p, side) if use_llm else None) or template_angle(p)


def angle_source(p):
    """'hand' (came with the list), 'supply'/'demand' (we generated it under that side), or None."""
    return DeskSetting.get("angle_src:" + p.id)


def mark_angle_source(p, source):
    DeskSetting.put("angle_src:" + p.id, source)


def reconcile_angles(limit=250, use_llm=True):
    """Prospects with an explicit side whose angle we generated under a different
    side (or before sides existed) get a fresh one. Hand-written angles are never touched."""
    from call_kit import detect_side
    rows = (CallProspect.query.filter(CallProspect.side.isnot(None), CallProspect.angle.isnot(None))
            .order_by(CallProspect.created_at.asc()).limit(2000).all())
    n = 0
    for p in rows:
        src = angle_source(p)
        if src == "hand":
            continue
        side = detect_side(p)
        if src == side:
            continue
        try:
            p.angle = generate_angle(p, use_llm=use_llm)
            mark_angle_source(p, side)
            n += 1
        except Exception:
            logger.exception("angle reconcile failed for %s", p.id)
        if n >= limit:
            break
    if n:
        db.session.commit()
    return n


def fill_missing_angles(limit=200, use_llm=True):
    """Fill blank angles, oldest first. Returns count filled."""
    rows = (CallProspect.query.filter((CallProspect.angle.is_(None)) | (CallProspect.angle == ""))
            .order_by(CallProspect.created_at.asc()).limit(limit).all())
    from call_kit import detect_side
    n = 0
    for p in rows:
        try:
            p.angle = generate_angle(p, use_llm=use_llm)
            mark_angle_source(p, detect_side(p))
            n += 1
        except Exception:
            logger.exception("angle generation failed for %s", p.id)
    if n:
        db.session.commit()
    fixed = reconcile_angles(use_llm=use_llm)
    DeskSetting.put("angles:last", json.dumps({"filled": n, "reconciled": fixed,
                                               "at": datetime.now(timezone.utc).isoformat()}))
    return n


def run_angle_backfill(app):
    with app.app_context():
        try:
            fill_missing_angles()
        except Exception:
            logger.exception("angle backfill failed")


@enrich_bp.route("/api/admin/angles/backfill", methods=["POST"])
@require_desk(MANAGER_ROLES)
def angles_backfill(ident):
    data = request.get_json(silent=True) or {}
    n = fill_missing_angles(limit=int(data.get("limit") or 500), use_llm=bool(data.get("llm", True)))
    audit("angles_backfill", "queue", None, {"filled": n})
    return jsonify({"filled": n, "remaining": CallProspect.query.filter(
        (CallProspect.angle.is_(None)) | (CallProspect.angle == "")).count()}), 200


# ---------------------------------------------------------------------------
# enrichment
# ---------------------------------------------------------------------------
def _places_lookup(api_key, query):
    import requests
    r = requests.post(
        "https://places.googleapis.com/v1/places:searchText",
        json={"textQuery": query, "maxResultCount": 1, "regionCode": "US",
              "locationBias": {"circle": {"center": {"latitude": 26.5, "longitude": -80.2}, "radius": 50000.0}}},
        headers={"X-Goog-Api-Key": api_key, "Content-Type": "application/json",
                 "X-Goog-FieldMask": ("places.displayName,places.rating,places.userRatingCount,places.websiteUri,"
                                      "places.currentOpeningHours.openNow,places.regularOpeningHours.weekdayDescriptions,"
                                      "places.formattedAddress,places.googleMapsUri,places.businessStatus,"
                                      "places.nationalPhoneNumber,places.primaryTypeDisplayName")},
        timeout=8,
    )
    r.raise_for_status()
    places = (r.json() or {}).get("places", [])
    return places[0] if places else None


_STOP = {"the", "and", "of", "llc", "inc", "co", "company", "corp", "services", "service", "group", "fl", "florida"}
_GENERIC = {"movers", "moving", "mover", "junk", "removal", "hauling", "haul", "dumpster", "dumpsters", "storage",
            "estate", "sales", "property", "properties", "management", "cleaning", "pressure", "appliance",
            "appliances", "recycling", "trash", "waste", "cleanouts", "cleanout", "demolition", "demo", "realty",
            "real", "solutions", "pros", "pro", "team", "boca", "raton", "palm", "beach", "west", "fort",
            "lauderdale", "miami", "delray", "lake", "worth", "county", "south"}


def _tokens(s):
    return {t for t in re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split() if t and t not in _STOP}


def name_matches(company, place_name, company_phone=None, place_phone=None):
    """True when the Google result is plausibly the same business: phone digits
    equal, or at least half of the company's meaningful words appear in the
    listing name (and vice-versa for one-word names)."""
    cp = re.sub(r"\D", "", company_phone or "")[-10:]
    pp = re.sub(r"\D", "", place_phone or "")[-10:]
    if cp and pp and cp == pp:
        return True
    a, b = _tokens(company), _tokens(place_name)
    if not a or not b:
        return False
    # industry words don't identify a business ("Luxury Movers" vs "City Movers")
    da, db_ = a - _GENERIC, b - _GENERIC
    if da:
        return bool(da & db_) and len(a & b) / len(a) >= 0.5
    return a <= b                      # all-generic names must match wholesale


def _shape(place):
    if not place:
        return {"found": False}
    hours = ((place.get("regularOpeningHours") or {}).get("weekdayDescriptions") or [])
    today_idx = (datetime.now(timezone.utc) - timedelta(hours=4)).weekday()
    return {
        "found": True,
        "name": (place.get("displayName") or {}).get("text"),
        "rating": place.get("rating"),
        "reviews": place.get("userRatingCount"),
        "open_now": (place.get("currentOpeningHours") or {}).get("openNow"),
        "hours_today": hours[today_idx] if len(hours) == 7 else None,
        "website": place.get("websiteUri"),
        "maps": place.get("googleMapsUri"),
        "address": place.get("formattedAddress"),
        "status": place.get("businessStatus"),
        "phone": place.get("nationalPhoneNumber"),
        "type": (place.get("primaryTypeDisplayName") or {}).get("text"),
    }


def enrich_prospect(p, force=False):
    key = "enrich:" + p.id
    if not force:
        cached = DeskSetting.get(key)
        if cached:
            try:
                d = json.loads(cached)
                at = datetime.fromisoformat(d.get("_at"))
                if datetime.now(timezone.utc) - at < timedelta(days=ENRICH_TTL_DAYS):
                    return d
            except Exception:
                pass
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
    if not api_key:
        return {"found": False, "reason": "no places key"}
    q = " ".join(x for x in [p.company, p.city, "FL"] if x)
    try:
        place = _places_lookup(api_key, q)
        d = _shape(place)
        if d.get("found") and not name_matches(p.company, d.get("name"), p.phone, d.get("phone")):
            logger.info("enrich: rejected '%s' for '%s'", d.get("name"), p.company)
            d = {"found": False, "reason": "no confident match", "rejected": d.get("name")}
    except Exception:
        logger.exception("enrich failed for %s", p.id)
        return {"found": False, "reason": "lookup failed"}
    d["_at"] = datetime.now(timezone.utc).isoformat()
    DeskSetting.put(key, json.dumps(d))
    return d


@enrich_bp.route("/api/va/calls/enrich", methods=["POST"])
@_ratelimit
def calls_enrich():
    data = request.get_json(silent=True) or {}
    if not desk_identity(data):
        return jsonify({"error": "Sign in to the desk first."}), 401
    p = db.session.get(CallProspect, data.get("prospect_id") or "") if data.get("prospect_id") else None
    if p is None:
        digits = re.sub(r"\D", "", str(data.get("phone") or ""))[-10:]
        if len(digits) == 10:
            p = CallProspect.query.filter_by(phone_digits=digits).first()
        if p is None and data.get("company"):
            p = CallProspect.query.filter(CallProspect.company == str(data["company"]).strip()).first()
    if not p:
        return jsonify({"error": "Prospect not found."}), 404
    d = enrich_prospect(p, force=bool(data.get("force")))
    d = {k: v for k, v in d.items() if not k.startswith("_")}
    return jsonify(dict(d, prospect_id=p.id)), 200
