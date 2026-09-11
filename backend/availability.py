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
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)
availability_bp = Blueprint("availability", __name__, url_prefix="/api/booking")

SLOTS = ("8-10", "10-12", "12-14", "14-16", "16-18")
MIN_LEAD_MINUTES = 30
MAX_DAYS_AHEAD = 14


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
    """Every slot for the day with whether anyone can serve it."""
    from assignment import point_job, assignable_contractors
    try:
        from sameday import standby_ids
        standby = standby_ids(day_str)
    except Exception:
        standby = None
    now = _now().replace(tzinfo=None)
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
                pool = assignable_contractors(probe, start, mode="offer", on_standby=standby)
                pool = [e for e in pool if not (exclude_job_id and getattr(e.get("contractor"), "id", None) == exclude_job_id)]
                crews = len(pool)
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
    slots = slots_for(day, lat, lng, volume)
    return jsonify({"date": day, "slots": slots,
                    "any_available": any(s["available"] for s in slots)}), 200
