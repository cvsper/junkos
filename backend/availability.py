"""Server-side availability: which slots can actually be served.

The booking wizard offers static two-hour slots from tomorrow through ninety
days out, and nothing checks whether anyone can come. A slot is only real if
a hauler who passes the same eligibility gate dispatch uses could take it.

Ported from Codex's mobile_availability idea, but built on the one gate the
platform already has (assignment.eligibility via point_job) rather than a
second copy of the radius / capacity / heartbeat rules. Conservative on
purpose: a slot with nobody assignable is "unavailable", not "probably fine".
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)
availability_bp = Blueprint("availability", __name__, url_prefix="/api/booking")

SLOTS = ("8-10", "10-12", "12-14", "14-16", "16-18")
MIN_LEAD_MINUTES = 30
MAX_DAYS_AHEAD = 14

# The booking wizard blocks on this call, so a repeat ask should be free. Two
# people in the same ZIP asking about Thursday are the same question; so is one
# person stepping back and forth through the wizard. Keyed on the day, the
# pickup rounded to ~110m (far finer than the radius rule it feeds), and a
# fingerprint of the hauler pool — so approving a hauler, or one coming online,
# invalidates immediately instead of waiting out the clock. The TTL covers what
# the fingerprint cannot see: a slot filling up. The cache sits on the HTTP
# route only — dispatch_desk calls slots_for directly and always runs fresh.
CACHE_SECONDS = int(os.environ.get("AVAILABILITY_CACHE_SECONDS", "60") or 60)
CACHE_MAX_KEYS = 512
_cache = {}


def _now():
    return datetime.now(timezone.utc)


def slot_bounds(day_str, slot):
    """(start_utc_naive, end_utc_naive) for a slot on a local date."""
    from timeutils import local_naive_to_utc
    day = datetime.strptime(day_str, "%Y-%m-%d").date()
    h0, h1 = (int(x) for x in slot.split("-"))
    start = local_naive_to_utc(datetime.combine(day, datetime.min.time()).replace(hour=h0))
    end = local_naive_to_utc(datetime.combine(day, datetime.min.time()).replace(hour=h1))
    return start.replace(tzinfo=None), end.replace(tzinfo=None)


def slots_for(day_str, lat=None, lng=None, volume=None, exclude_job_id=None):
    """Every slot for the day with whether anyone can serve it.

    The pool and the per-hauler lookups are fetched once for the whole sweep,
    not once per slot: which haulers exist, what their documents say and how
    reliable they are do not change between 8am and 4pm on the same day. Only
    radius, capacity, schedule and conflicts are re-evaluated per slot, which
    is where the real answer lives.
    """
    from assignment import point_job, assignable_contractors, contractor_pool, ProbeCache
    try:
        from sameday import standby_ids
        standby = standby_ids(day_str)
    except Exception:
        standby = None
    now = _now().replace(tzinfo=None)
    # Pool membership is scoped by operator, which no slot changes — one read.
    pool = contractor_pool(point_job(lat=lat, lng=lng, volume_estimate=volume))
    cache = ProbeCache()
    out = []
    for slot in SLOTS:
        try:
            start, end = slot_bounds(day_str, slot)
        except ValueError:
            continue
        too_soon = start < now + timedelta(minutes=MIN_LEAD_MINUTES)
        too_far = start > now + timedelta(days=MAX_DAYS_AHEAD)
        crews = 0
        reason = None
        if too_soon:
            reason = "past"
        elif too_far:
            reason = "too_far"
        else:
            try:
                probe = point_job(lat=lat, lng=lng, scheduled_at=start, volume_estimate=volume)
                eligible = assignable_contractors(probe, start, mode="offer", on_standby=standby,
                                                  pool=pool, cache=cache)
                eligible = [e for e in eligible if not (exclude_job_id and getattr(e.get("contractor"), "id", None) == exclude_job_id)]
                crews = len(eligible)
            except Exception:
                logger.exception("availability probe failed for %s %s", day_str, slot)
                reason = "unknown"
        available = crews > 0 and reason is None
        out.append({
            "slot": slot,
            "label": "{}–{}".format(_fmt_hour(int(slot.split("-")[0])), _fmt_hour(int(slot.split("-")[1]))),
            "start_at": start.isoformat() + "Z",
            "available": available,
            "crews": crews,
            "reason": reason if not available else None,
        })
    return out


def _fmt_hour(h):
    if h == 12:
        return "12pm"
    return "{}am".format(h) if h < 12 else "{}pm".format(h - 12)


def _pool_fingerprint():
    """One aggregate that changes whenever a hauler does: who is approved, who
    is online, who moved. Cheap enough to pay on every request (1 query, versus
    the ~290 a full sweep costs) and it makes the cache correct for the change
    people actually notice — a hauler coming online."""
    try:
        from sqlalchemy import func
        from models import db, Contractor
        row = db.session.query(
            func.count(Contractor.id),
            func.max(Contractor.updated_at),
            func.max(Contractor.last_heartbeat_at),
        ).filter(Contractor.approval_status == "approved").one()
        return (row[0], str(row[1]), str(row[2]))
    except Exception:
        # No fingerprint means no caching rather than a wrong answer.
        logger.debug("pool fingerprint failed", exc_info=True)
        return None


def _cache_key(day, lat, lng, volume, fingerprint):
    def r(v):
        return None if v is None else round(float(v), 3)
    return (day, r(lat), r(lng), r(volume), fingerprint)


def cached_slots(day, lat, lng, volume):
    """slots_for() with a short shared TTL. Returns (slots, from_cache)."""
    if CACHE_SECONDS <= 0:
        return slots_for(day, lat, lng, volume), False
    fingerprint = _pool_fingerprint()
    if fingerprint is None:
        return slots_for(day, lat, lng, volume), False
    key = _cache_key(day, lat, lng, volume, fingerprint)
    now = _now()
    hit = _cache.get(key)
    if hit and (now - hit[0]).total_seconds() < CACHE_SECONDS:
        return hit[1], True
    slots = slots_for(day, lat, lng, volume)
    if len(_cache) >= CACHE_MAX_KEYS:
        # Cheapest sane eviction for a dict this small: drop the oldest half.
        for k in sorted(_cache, key=lambda k: _cache[k][0])[: CACHE_MAX_KEYS // 2]:
            _cache.pop(k, None)
    _cache[key] = (now, slots)
    return slots, False


def reset_cache():
    """Drop every cached sweep. For tests and for anything that changes the
    world in a way the fingerprint cannot see."""
    _cache.clear()


@availability_bp.route("/availability", methods=["GET"])
def availability():
    day = (request.args.get("date") or "").strip()
    try:
        datetime.strptime(day, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "date must be YYYY-MM-DD"}), 400
    lat = request.args.get("lat", type=float)
    lng = request.args.get("lng", type=float)
    volume = request.args.get("volume", type=float)
    slots, cached = cached_slots(day, lat, lng, volume)
    resp = jsonify({"date": day, "slots": slots,
                    "any_available": any(s["available"] for s in slots)})
    resp.headers["X-Availability-Cache"] = "hit" if cached else "miss"
    return resp, 200
