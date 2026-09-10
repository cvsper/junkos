"""Same-day dispatch from the desk — close the job while the customer is on the line.

  1. Capacity before promising:  POST /api/va/sameday/capacity {zip|address}
     → haulers who could take a job today near there (online now, or on today's
       standby roster), nearest first, with a green/amber/red level.
  2. Find a hauler now:           POST /api/va/sameday/find {job_id, limit=3}
     → offers the booked job to the top N eligible haulers (nearest first) by
       SMS with the existing one-tap accept link; POST /api/va/sameday/status
       {job_id} shows replies live; `widen` sends the next N.
  3. Standby roster:              08:45 ET Mon–Sat text to approved haulers,
     "Y" replies build today's roster (POST /api/va/sameday/standby).
  4. Pricing: the intake quote already passes the date → same-day surge.
  5. Maya bookings for today run the same offer wave (hook in routes/vapi.py).

Geocoding uses Google Places Text Search (New) — the key and API are already
enabled for the outreach engines — cached per query in desk_settings.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from models import db, Contractor, Job, JobOffer, User, DeskSetting, generate_uuid
from models_sameday import HaulerStandby
from desk_auth import desk_identity, desk_va_name, audit, require_desk, MANAGER_ROLES

try:
    from extensions import limiter
except Exception:  # pragma: no cover
    limiter = None

logger = logging.getLogger(__name__)
sameday_bp = Blueprint("sameday", __name__)
_ratelimit = (limiter.limit("240 per hour; 30 per minute") if limiter is not None else (lambda f: f))

RADIUS_MILES = float(os.environ.get("SAMEDAY_RADIUS_MILES", "15") or 15)
WAVE_SIZE = int(os.environ.get("SAMEDAY_WAVE_SIZE", "3") or 3)
STANDBY_HOUR = os.environ.get("SAMEDAY_STANDBY_TIME", "08:45")
_YES = ("y", "yes", "yeah", "yep", "available", "in", "im in", "i'm in", "ready")
_NO = ("n", "no", "nope", "not today", "off", "unavailable")


# ---------------------------------------------------------------------------
# time + geo helpers
# ---------------------------------------------------------------------------
def _now_utc():
    return datetime.now(timezone.utc)


def _local_today():
    from timeutils import to_local
    return to_local(_now_utc()).date()


def _local_date_of(dt_naive_utc):
    if dt_naive_utc is None:
        return None
    from timeutils import to_local
    return to_local(dt_naive_utc.replace(tzinfo=timezone.utc)).date()


def _places_search_text(api_key, query):
    """Google Places Text Search (New) with a location field mask — the outreach
    helper in places_search.py asks for name/phone only, so this is separate."""
    import requests
    r = requests.post(
        "https://places.googleapis.com/v1/places:searchText",
        json={"textQuery": query, "maxResultCount": 1, "regionCode": "US",
              "locationBias": {"circle": {"center": {"latitude": 26.45, "longitude": -80.15}, "radius": 50000.0}}},
        headers={"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": "places.location,places.formattedAddress",
                 "Content-Type": "application/json"},
        timeout=8,
    )
    r.raise_for_status()
    return (r.json() or {}).get("places", [])


def geocode(text):
    """(lat, lng) for a zip/address in South Florida, or None. Cached."""
    q = " ".join(str(text or "").split())[:160]
    if not q:
        return None
    if re.fullmatch(r"\d{5}", q):
        q = q + ", FL"
    key = "geo:" + q.lower()
    cached = DeskSetting.get(key)
    if cached:
        try:
            d = json.loads(cached)
            if d.get("lat") is not None:
                return (d["lat"], d["lng"])
            # a failed lookup is remembered for an hour only (transient API errors must not stick)
            at = d.get("at")
            if at and (_now_utc() - datetime.fromisoformat(at)).total_seconds() < 3600:
                return None
        except Exception:
            pass
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        for r in _places_search_text(api_key, q) or []:
            loc = r.get("location") or {}
            lat, lng = loc.get("latitude"), loc.get("longitude")
            if lat is not None and lng is not None:
                DeskSetting.put(key, json.dumps({"lat": float(lat), "lng": float(lng)}))
                return float(lat), float(lng)
    except Exception:
        logger.exception("geocode failed for %r", q)
    DeskSetting.put(key, json.dumps({"lat": None, "at": _now_utc().isoformat()}))
    return None


def _haversine(a, b, c, d):
    from dispatcher import haversine
    return haversine(a, b, c, d)


def _hauler_name(c):
    for attr in ("business_name", "company_name", "display_name"):
        v = getattr(c, attr, None)
        if v:
            return v
    return (c.user.name if getattr(c, "user", None) and c.user.name else "Hauler")[:60]


def _hauler_phone(c):
    return c.user.phone if getattr(c, "user", None) and c.user.phone else None


# ---------------------------------------------------------------------------
# 1. capacity
# ---------------------------------------------------------------------------
def standby_ids(day=None):
    day = day or _local_today()
    return {s.contractor_id for s in HaulerStandby.query.filter_by(day=day, available=True).all()}


def capacity(lat=None, lng=None):
    today = _local_today()
    on_standby = standby_ids(today)
    rows = []
    for c in Contractor.query.filter_by(approval_status="approved").all():
        available = bool(c.is_online) or c.id in on_standby
        if not available:
            continue
        dist = None
        if lat is not None and lng is not None and c.current_lat is not None and c.current_lng is not None:
            dist = round(_haversine(lat, lng, c.current_lat, c.current_lng), 1)
            if dist > RADIUS_MILES:
                continue
        rows.append({"id": c.id, "name": _hauler_name(c), "miles": dist,
                     "online": bool(c.is_online), "standby": c.id in on_standby,
                     "rating": round(float(c.avg_rating or 0), 1)})
    rows.sort(key=lambda r: (r["miles"] if r["miles"] is not None else 9999, -r["rating"]))
    n = len(rows)
    level = "green" if n >= 3 else ("amber" if n >= 1 else "red")
    nearest = rows[0] if rows else None
    if lat is None:
        note = "{} hauler{} available today (no location for this zip yet)".format(n, "" if n == 1 else "s")
    elif n == 0:
        note = "No haulers within {:.0f} miles right now — book tomorrow's first window".format(RADIUS_MILES)
    else:
        note = "Same day: {} hauler{} within {:.0f} mi".format(n, "" if n == 1 else "s", RADIUS_MILES)
        if nearest and nearest["miles"] is not None:
            note += ", nearest {} mi ({})".format(nearest["miles"], nearest["name"])
    return {"level": level, "count": n, "nearest": nearest, "haulers": rows[:8], "note": note,
            "online_total": Contractor.query.filter_by(approval_status="approved", is_online=True).count(),
            "standby_total": len(on_standby), "geocoded": lat is not None}


@sameday_bp.route("/api/va/sameday/capacity", methods=["POST"])
@_ratelimit
def sameday_capacity():
    data = request.get_json(silent=True) or {}
    if not desk_identity(data):
        return jsonify({"error": "Sign in to the desk first."}), 401
    where = (data.get("address") or data.get("zip") or "").strip()
    loc = geocode(where) if where else None
    lat, lng = loc if loc else (None, None)
    return jsonify(dict(capacity(lat, lng), where=where)), 200


# ---------------------------------------------------------------------------
# 2. find a hauler now (offer wave on a booked job)
# ---------------------------------------------------------------------------
def _ensure_job_geo(job):
    if job.lat is None or job.lng is None:
        loc = geocode(job.address or "")
        if loc:
            job.lat, job.lng = loc
            db.session.commit()


def _offered_ids(job):
    return {o.contractor_id for o in JobOffer.query.filter_by(job_id=job.id).all()}


def wave(job, limit=WAVE_SIZE, va_name=None):
    """Offer the job to the next `limit` nearest eligible haulers. Returns the new offers' summary."""
    from dispatcher import find_eligible_operators, _contractor_payout, _sms_broadcast_offer, OFFER_EXPIRY_MINUTES
    from models import utcnow
    if job.driver_id:
        return {"sent": [], "reason": "already assigned"}
    _ensure_job_geo(job)
    already = _offered_ids(job)
    eligible = [e for e in find_eligible_operators(job) if e["contractor"].id not in already]
    # standby haulers count even when the app says offline
    on_standby = standby_ids(_local_date_of(job.scheduled_at) or _local_today())
    if on_standby:
        seen = {e["contractor"].id for e in eligible}
        for c in Contractor.query.filter(Contractor.id.in_(list(on_standby)), Contractor.approval_status == "approved").all():
            if c.id in seen or c.id in already:
                continue
            dist = None
            if job.lat is not None and c.current_lat is not None:
                dist = round(_haversine(job.lat, job.lng, c.current_lat, c.current_lng), 1)
                if dist > RADIUS_MILES * 2:
                    continue
            eligible.append({"contractor": c, "distance_miles": dist})
        eligible.sort(key=lambda e: e["distance_miles"] if e["distance_miles"] is not None else 9999)
    batch = eligible[:max(1, int(limit or WAVE_SIZE))]
    if not batch:
        return {"sent": [], "reason": "nobody eligible right now"}
    payout = _contractor_payout(job)
    expires = utcnow() + timedelta(minutes=OFFER_EXPIRY_MINUTES)
    sent = []
    for e in batch:
        offer = JobOffer(id=generate_uuid(), job_id=job.id, contractor_id=e["contractor"].id, status="sent",
                         accept_token=generate_uuid(), distance_miles=e["distance_miles"],
                         payout_amount=payout, expires_at=expires)
        db.session.add(offer)
        sent.append((offer, e["contractor"]))
    if job.status in ("pending", "confirmed"):
        job.status = "broadcasting"
    db.session.commit()
    for offer, c in sent:
        try:
            _sms_broadcast_offer(offer, c, job)
        except Exception:
            logger.exception("offer sms failed for %s", c.id)
    audit("sameday_wave", "job", job.id, {"count": len(sent), "va": va_name})
    return {"sent": [{"name": _hauler_name(c), "miles": o.distance_miles} for o, c in sent],
            "payout": payout, "expires_minutes": OFFER_EXPIRY_MINUTES}


def wave_async(job_id, app):
    def _run():
        with app.app_context():
            job = db.session.get(Job, job_id)
            if job and _local_date_of(job.scheduled_at) == _local_today():
                try:
                    wave(job, va_name="Maya")
                except Exception:
                    logger.exception("maya same-day wave failed for %s", job_id)
    threading.Thread(target=_run, daemon=True).start()


def wave_status(job):
    offers = (JobOffer.query.filter_by(job_id=job.id).order_by(JobOffer.created_at.asc()).all()
              if hasattr(JobOffer, "created_at") else JobOffer.query.filter_by(job_id=job.id).all())
    rows = []
    accepted = None
    for o in offers:
        c = db.session.get(Contractor, o.contractor_id)
        row = {"name": _hauler_name(c) if c else "Hauler", "miles": o.distance_miles, "status": o.status}
        if o.distance_miles is not None:
            row["eta_minutes"] = int(10 + o.distance_miles / 25.0 * 60)
        rows.append(row)
        if o.status == "accepted" or (job.driver_id and c and c.id == job.driver_id):
            accepted = row
    return {"job_id": job.id, "job_status": job.status, "assigned": bool(job.driver_id),
            "accepted": accepted, "offers": rows}


@sameday_bp.route("/api/va/sameday/find", methods=["POST"])
@_ratelimit
def sameday_find():
    data = request.get_json(silent=True) or {}
    if not desk_identity(data):
        return jsonify({"error": "Sign in to the desk first."}), 401
    job = db.session.get(Job, data.get("job_id") or "")
    if not job:
        return jsonify({"error": "Job not found."}), 404
    from flags import flag
    if not flag("sameday_wave"):
        return jsonify({"error": "Same-day offers are switched off."}), 403
    res = wave(job, limit=data.get("limit") or WAVE_SIZE, va_name=desk_va_name(data))
    return jsonify(dict(res, status=wave_status(job))), 200


@sameday_bp.route("/api/va/sameday/status", methods=["POST"])
@_ratelimit
def sameday_status():
    data = request.get_json(silent=True) or {}
    if not desk_identity(data):
        return jsonify({"error": "Sign in to the desk first."}), 401
    job = db.session.get(Job, data.get("job_id") or "")
    if not job:
        return jsonify({"error": "Job not found."}), 404
    return jsonify(wave_status(job)), 200


# ---------------------------------------------------------------------------
# 3. standby roster
# ---------------------------------------------------------------------------
def _contractor_for_phone(digits):
    if len(digits or "") != 10:
        return None
    for u in User.query.filter(User.phone.isnot(None)).filter(User.phone.like("%" + digits)).all():
        c = Contractor.query.filter_by(user_id=u.id).first()
        if c:
            return c
    return None


def parse_standby_reply(body):
    t = re.sub(r"[^a-z' ]", "", (body or "").strip().lower())
    if t in _YES or t.startswith("yes") or t == "y":
        return True
    if t in _NO or t.startswith("no") or t == "n":
        return False
    return None


def record_standby_reply(from_phone, body, via="sms"):
    """Called from the SMS webhooks. Returns a reply text if this was a standby answer, else None."""
    digits = re.sub(r"\D", "", from_phone or "")[-10:]
    answer = parse_standby_reply(body)
    if answer is None:
        return None
    c = _contractor_for_phone(digits)
    if not c:
        return None
    today = _local_today()
    row = HaulerStandby.query.filter_by(day=today, contractor_id=c.id).first()
    if row is None:
        # only treat a bare Y/N as a standby answer if we asked today (or they're volunteering)
        row = HaulerStandby(day=today, contractor_id=c.id)
        db.session.add(row)
    row.available = answer
    row.replied_at = _now_utc().replace(tzinfo=None)
    row.via = via
    db.session.commit()
    audit("standby_reply", "contractor", c.id, {"available": answer}, via="twilio")
    if answer:
        return "You're on Umuve's same-day list for today. Job offers come by text — first to accept gets it."
    return "Got it — no same-day jobs for you today. Text Y anytime to opt back in."


def ask_standby(app=None):
    """Morning text to every approved hauler with a phone. Never raises."""
    def _do():
        from sms_service import send_sms
        today = _local_today()
        asked = 0
        for c in Contractor.query.filter_by(approval_status="approved").all():
            phone = _hauler_phone(c)
            if not phone:
                continue
            try:
                from compliance import text_allowed
                ok, _ = text_allowed(re.sub(r"\D", "", phone)[-10:])
                if not ok:
                    continue
            except Exception:
                pass
            row = HaulerStandby.query.filter_by(day=today, contractor_id=c.id).first()
            if row and row.asked_at:
                continue
            if row is None:
                row = HaulerStandby(day=today, contractor_id=c.id)
                db.session.add(row)
            row.asked_at = _now_utc().replace(tzinfo=None)
            db.session.commit()
            send_sms(phone, "Umuve: available for same-day jobs today? Reply Y or N. "
                            "Booked, paid jobs near you come by text — first to accept gets it.")
            asked += 1
        total_asked = HaulerStandby.query.filter(HaulerStandby.day == today,
                                                 HaulerStandby.asked_at.isnot(None)).count()
        DeskSetting.put("standby:last", json.dumps({"day": today.isoformat(), "asked": total_asked,
                                                    "new": asked, "at": _now_utc().isoformat()}))
        logger.info("standby ask: %d haulers texted for %s", asked, today)
        return asked
    if app is not None:
        with app.app_context():
            try:
                return _do()
            except Exception:
                logger.exception("standby ask failed")
    else:
        return _do()


def run_standby_ask(app):
    from timeutils import to_local
    local = to_local(_now_utc())
    if local.weekday() == 6:          # Sunday off
        return
    ask_standby(app)


@sameday_bp.route("/api/va/sameday/standby", methods=["POST"])
@_ratelimit
def sameday_standby():
    data = request.get_json(silent=True) or {}
    if not desk_identity(data):
        return jsonify({"error": "Sign in to the desk first."}), 401
    today = _local_today()
    rows = HaulerStandby.query.filter_by(day=today).all()
    out = []
    for r in rows:
        c = db.session.get(Contractor, r.contractor_id)
        out.append({"name": _hauler_name(c) if c else "Hauler", "available": r.available,
                    "replied": r.replied_at is not None, "online": bool(c.is_online) if c else False})
    out.sort(key=lambda x: (not x["available"], x["name"]))
    last = DeskSetting.get("standby:last")
    return jsonify({"day": today.isoformat(), "available": sum(1 for x in out if x["available"]),
                    "asked": sum(1 for r in rows if r.asked_at), "haulers": out,
                    "online_now": Contractor.query.filter_by(approval_status="approved", is_online=True).count(),
                    "last_ask": json.loads(last) if last else None}), 200


@sameday_bp.route("/api/admin/sameday/standby-ask", methods=["POST"])
@require_desk(MANAGER_ROLES)
def sameday_standby_ask_now(ident):
    n = ask_standby()
    audit("standby_ask", "roster", _local_today().isoformat(), {"asked": n})
    return jsonify({"asked": n}), 200
