"""Dispatcher desk — the VA's full dispatch console.

    GET  /va/dispatch                         the page (static/dispatch-page.html, desk shell)
    POST /api/va/dispatch/overview            board + roster + capacity + activity in one call
    POST /api/va/dispatch/job                 one job with its timeline, dump suggestion, customer history
    POST /api/va/dispatch/candidates          every approved hauler ranked for a job, with eligibility
    POST /api/va/dispatch/assign-hauler       assign (or force-assign) a hauler
    POST /api/va/dispatch/hauler              hauler profile, docs, reliability, recent jobs
    POST /api/va/dispatch/hauler/text         text a hauler from the desk line
    POST /api/va/dispatch/geocode             address → lat/lng, county, in-area
    POST /api/va/dispatch/catalog             bookable items, add-ons, truck loads, prices
    POST /api/va/dispatch/estimate            live price breakdown from the booking engine
    POST /api/va/dispatch/slots               time windows with capacity for a date/point
    POST /api/va/dispatch/customer            find a customer by phone or name
    POST /api/va/dispatch/book                create a full booking (priced, geocoded, texted, assigned)
    POST /api/va/dispatch/job/transition      en_route / arrived / started / completed
    POST /api/va/dispatch/job/reschedule      move it, tell the customer
    POST /api/va/dispatch/job/cancel          cancel with the real cancellation policy
    POST /api/va/dispatch/job/text            text the customer or the hauler about this job
    POST /api/va/dispatch/job/paylink         make (and text) the Stripe pay link
    POST /api/va/dispatch/job/confirm         hauler confirmed / can't make it (re-dispatch)
    POST /api/va/dispatch/job/broadcast       offer the job to every eligible hauler nearby

Everything prices through routes.booking.calculate_estimate, assigns through
dispatch_service (row-locked), cancels through cancellation, and texts from
the desk line, so the desk never diverges from the app. Auth is the desk
convention (Bearer desk JWT or {code, va_name}); every mutation is audited.
The contract the page codes against is scratchpad/DISPATCH_CONTRACT.md.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone

from flask import Blueprint, Response, jsonify, request

from desk_auth import desk_identity, is_manager, audit
from models import db, Job, User, Contractor, Payment, VaDispatchAction, generate_uuid, generate_referral_code
from timeutils import to_local, fmt_local, iso_utc, parse_local

dispatchdesk_bp = Blueprint("dispatchdesk", __name__)
logger = logging.getLogger(__name__)

STATUS_LABEL = {"pending": "Needs a hauler", "confirmed": "Needs a hauler", "broadcasting": "Offered to haulers",
                "delegating": "With an operator", "assigned": "Assigned", "accepted": "Accepted", "en_route": "On the way",
                "arrived": "Arrived", "started": "Working", "completed": "Done", "cancelled": "Cancelled",
                "paid": "Paid", "refunded": "Refunded"}
NEXT_STATUS = {"assigned": "accepted", "accepted": "en_route", "en_route": "arrived", "arrived": "started", "started": "completed"}
SLOT_LABELS = {"8-10": "8–10 AM", "10-12": "10 AM–12 PM", "12-14": "12–2 PM", "14-16": "2–4 PM", "16-18": "4–6 PM"}
ITEM_GROUPS = [
    ("Furniture", ("sofa", "chair", "dresser", "bookcase", "cabinet", "table", "futon", "filing", "desk", "entertainment", "tv_stand")),
    ("Bedroom", ("mattress", "box_spring", "bed")),
    ("Appliances", ("refrigerator", "washer", "dryer", "dishwasher", "stove", "microwave", "freezer")),
    ("Electronics & office", ("tv", "computer", "copier", "printer")),
    ("Fitness & outdoor", ("treadmill", "elliptical", "bike", "bbq", "basketball", "lawn", "hot_tub", "pool_table", "piano")),
    ("Cleanouts & debris", ("general", "yard_waste", "construction", "other")),
]
GENERIC_BUCKETS = ("furniture", "appliances", "electronics")
REASON_LABEL = {"offline": "Offline right now", "stale_heartbeat": "Hasn't checked in for a while", "outside_schedule": "Outside their working hours",
                "out_of_radius": "Too far from the job", "declined_recently": "Declined a job recently", "schedule_conflict": "Has another job at that time",
                "concierge_needs_offer": "Text-only hauler — send an offer", "documents_unverified": "Documents not verified yet",
                "volume_unknown": "Job size not set", "first_job_needs_call": "First job — call them first", "not_approved": "Not approved yet",
                "suspended": "Suspended", "no_location": "No location yet", "capacity": "Truck too small for this job"}


def _reason_text(code):
    return REASON_LABEL.get(code, _pretty(str(code)))
REAL_JOBS_SINCE = datetime(2026, 6, 1)
# server.py stamps this West Palm Beach point on haulers who never sent a real
# location (approval + the no-coords branch of the location update). It is a
# placeholder, not a position — the desk must not draw 40 trucks on one corner.
PLACEHOLDER_POS = (26.7153, -80.0534)


def _real_position(lat, lng):
    if lat is None or lng is None:
        return None, None
    if abs(float(lat) - PLACEHOLDER_POS[0]) < 0.0005 and abs(float(lng) - PLACEHOLDER_POS[1]) < 0.0005:
        return None, None
    return lat, lng


# ---------------------------------------------------------------------------
# auth + small helpers
# ---------------------------------------------------------------------------
def _sees_everyone(ident):
    return is_manager(ident) or ident.get("via") == "passcode"


def _ident_or_401():
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return None, data, (jsonify({"error": "Sign in to the desk first."}), 401)
    return ident, data, None


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _naive(dt):
    """Naive UTC, whatever timeutils hands back."""
    if dt is not None and getattr(dt, "tzinfo", None) is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _digits(s):
    return re.sub(r"\D", "", s or "")


def _e164(d):
    d = _digits(d)
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return "+1" + d if len(d) == 10 else None


def _pretty(key):
    return (key or "").replace("_", " ").strip().capitalize()


def _county(lat):
    if lat is None:
        return None
    try:
        from dump_suggest import county_for, COUNTY_LABEL
        c = county_for(float(lat))
        return COUNTY_LABEL.get(c, _pretty(c)) if c else None
    except Exception:
        return None


def _window_for(dt):
    if not dt:
        return None
    try:
        h = to_local(dt).hour
    except Exception:
        return None
    for slot, label in SLOT_LABELS.items():
        a, b = (int(x) for x in slot.split("-"))
        if a <= h < b:
            return label
    return None


def _action(job_id, action, va, contractor_id=None):
    try:
        db.session.add(VaDispatchAction(job_id=job_id, contractor_id=contractor_id, action=action[:20], va_name=(va or "")[:80]))
        db.session.commit()
    except Exception:
        logger.exception("dispatch action log failed")
        db.session.rollback()


# ---------------------------------------------------------------------------
# hauler + job shapes
# ---------------------------------------------------------------------------
def _kind(c):
    if getattr(c, "is_operator", False):
        return "operator"
    if getattr(c, "is_concierge", False):
        return "text"
    return "app"


def _hauler_row(c, now=None, on_standby=None, jobs_today=None):
    from sameday import is_live
    from hauler_reliability import profile
    now = now or _now()
    u = c.user
    seen = None
    if c.last_heartbeat_at:
        seen = max(0, int((now - c.last_heartbeat_at).total_seconds() // 60))
    prof = {}
    try:
        prof = profile(c) or {}
    except Exception:
        logger.exception("reliability profile failed")
    live = False
    try:
        live = bool(is_live(c, now, on_standby))
    except Exception:
        pass
    rlat, rlng = _real_position(c.current_lat, c.current_lng)
    return {
        "id": c.id, "name": (u.name if u else None) or "Hauler", "phone": u.phone if u else None,
        "kind": _kind(c), "approved": c.approval_status == "approved",
        "live": live, "online": bool(c.is_online), "standby": c.id in (on_standby or set()), "seen_minutes": seen,
        "lat": rlat, "lng": rlng, "county": _county(rlat), "location": "known" if rlat is not None else "unknown",
        "truck_type": c.truck_type, "rating": c.avg_rating, "total_jobs": c.total_jobs or 0,
        "tier": prof.get("tier"), "tier_label": prof.get("label"), "completed": prof.get("completed", 0),
        "no_shows": prof.get("no_shows", 0), "jobs_today": (jobs_today or {}).get(c.id, 0),
        "stripe": bool(c.stripe_connect_id), "concierge": bool(c.is_concierge),
    }


def _items_of(job):
    out = []
    for e in (job.items or []) if isinstance(job.items, list) else []:
        if not isinstance(e, dict):
            continue
        name = e.get("name") or _pretty(e.get("category"))
        if e.get("size"):
            name += " ({})".format(e["size"])
        try:
            qty = int(e.get("quantity") or 1)
        except (TypeError, ValueError):
            qty = 1
        out.append({"name": name, "qty": qty})
    return out


def _payment_of(job):
    p = job.payment
    if not p:
        return {"status": "none", "amount": None, "link_sent": False}
    link_sent = bool(p.stripe_payment_intent_id) or VaDispatchAction.query.filter_by(job_id=job.id, action="paylink").count() > 0
    return {"status": p.payment_status or "pending", "amount": p.amount, "link_sent": link_sent}


def _hauler_of(job):
    c = job.driver
    if not c:
        return None
    from hauler_reliability import profile
    try:
        prof = profile(c) or {}
    except Exception:
        prof = {}
    u = c.user
    return {"id": c.id, "name": (u.name if u else None) or "Hauler", "phone": u.phone if u else None,
            "kind": _kind(c), "tier": prof.get("tier"), "tier_label": prof.get("label")}


def _card(job):
    cust = job.customer
    now = _now()
    items = _items_of(job)
    prior = 0
    if cust:
        try:
            prior = Job.query.filter(Job.customer_id == cust.id, Job.status != "cancelled", Job.id != job.id).count()
        except Exception:
            prior = 0
    tracking = None
    try:
        tracking = job.tracking_url()
    except Exception:
        pass
    return {
        "id": job.id, "code": job.confirmation_code, "status": job.status,
        "status_label": STATUS_LABEL.get(job.status, _pretty(job.status)),
        "address": job.address, "lat": job.lat, "lng": job.lng, "county": _county(job.lat),
        "scheduled_at": iso_utc(job.scheduled_at),
        "scheduled_human": fmt_local(job.scheduled_at, "%a %b %-d, %-I:%M %p", "Not scheduled"),
        "window": _window_for(job.scheduled_at),
        "hours_out": round((job.scheduled_at - now).total_seconds() / 3600.0, 1) if job.scheduled_at else None,
        "items": items, "items_text": ", ".join("{}× {}".format(i["qty"], i["name"]) for i in items) or (job.notes or "")[:120],
        "item_count": sum(i["qty"] for i in items),
        "total": job.total_price, "disposal_fee": job.disposal_fee, "service_fee": job.service_fee,
        "payment": _payment_of(job),
        "customer": {"id": cust.id if cust else None, "name": (cust.name if cust else None) or "Customer",
                     "phone": cust.phone if cust else None, "email": cust.email if cust else None, "prior_jobs": prior},
        "hauler": _hauler_of(job),
        "confirmed": bool(job.hauler_confirmed_at), "confirmed_by": job.hauler_confirmed_by, "confirmed_at": iso_utc(job.hauler_confirmed_at),
        "notes": (job.notes or "")[:600], "lead_source": job.lead_source or "", "tracking_url": tracking,
        "created_at": iso_utc(job.created_at), "version": job.version,
    }


def _real_jobs():
    from sqlalchemy import or_
    return Job.query.filter(Job.created_at >= REAL_JOBS_SINCE,
                            or_(Job.notes.is_(None), ~Job.notes.ilike("%SYNTHETIC%")))


def _local_day_bounds(now=None):
    from timeutils import local_naive_to_utc
    loc = to_local(now or _now())
    start = loc.replace(hour=0, minute=0, second=0, microsecond=0)
    s = local_naive_to_utc(start.replace(tzinfo=None))
    return s, s + timedelta(days=1)


# ---------------------------------------------------------------------------
# blocks
# ---------------------------------------------------------------------------
def board():
    from assignment import ASSIGNABLE_STATUSES, IN_PROGRESS_STATUSES as IN_PROGRESS
    now = _now()
    day_s, day_e = _local_day_bounds(now)
    q = _real_jobs()
    open_ = (q.filter(Job.status.in_(ASSIGNABLE_STATUSES), Job.driver_id.is_(None), Job.operator_id.is_(None))
             .order_by(Job.scheduled_at.asc().nullslast(), Job.created_at.asc()).limit(60).all())
    scheduled = (q.filter(Job.status.in_(("pending", "confirmed", "assigned", "accepted", "delegating")),
                          Job.driver_id.isnot(None))
                 .order_by(Job.scheduled_at.asc().nullslast()).limit(60).all())
    active = q.filter(Job.status.in_(IN_PROGRESS)).order_by(Job.scheduled_at.asc().nullslast()).limit(40).all()
    done = (q.filter(Job.status.in_(("completed", "paid")), Job.completed_at >= day_s).order_by(Job.completed_at.desc()).limit(40).all())
    cancelled = (q.filter(Job.status == "cancelled", Job.cancelled_at >= day_s).order_by(Job.cancelled_at.desc()).limit(40).all())
    return {"open": [_card(j) for j in open_], "scheduled": [_card(j) for j in scheduled],
            "active": [_card(j) for j in active], "done": [_card(j) for j in done], "cancelled": [_card(j) for j in cancelled]}


def roster():
    from sameday import standby_ids
    now = _now()
    try:
        on_standby = set(standby_ids())
    except Exception:
        on_standby = set()
    day_s, day_e = _local_day_bounds(now)
    jobs_today = {}
    for j in Job.query.filter(Job.driver_id.isnot(None), Job.scheduled_at >= day_s, Job.scheduled_at < day_e,
                              Job.status.notin_(("cancelled",))).all():
        jobs_today[j.driver_id] = jobs_today.get(j.driver_id, 0) + 1
    rows = [_hauler_row(c, now, on_standby, jobs_today)
            for c in Contractor.query.filter_by(approval_status="approved").all()]
    rows.sort(key=lambda h: (not h["live"], not h["online"], not h["standby"], h["seen_minutes"] if h["seen_minutes"] is not None else 10 ** 6, -(h["completed"] or 0)))
    return rows


def recent(limit=20):
    rows = VaDispatchAction.query.order_by(VaDispatchAction.created_at.desc()).limit(limit).all()
    out = []
    for r in rows:
        job = db.session.get(Job, r.job_id) if r.job_id else None
        c = db.session.get(Contractor, r.contractor_id) if r.contractor_id else None
        out.append({"at": iso_utc(r.created_at), "action": r.action, "who": r.va_name,
                    "job_code": job.confirmation_code if job else None,
                    "detail": ((c.user.name if c and c.user else None) or (job.address if job else "")) or ""})
    return out


def area():
    from geofencing import SERVICE_AREA_POLYGON, SERVICE_AREA_BOUNDS, SERVICE_COUNTIES
    return {"polygon": [[float(a), float(b)] for a, b in SERVICE_AREA_POLYGON], "bounds": dict(SERVICE_AREA_BOUNDS),
            "counties": list(SERVICE_COUNTIES)}


def capacity_block():
    try:
        from sameday import capacity
        from geofencing import SERVICE_AREA_CENTER
        c = capacity(SERVICE_AREA_CENTER["lat"], SERVICE_AREA_CENTER["lng"]) or {}
        return {"level": c.get("level"), "count": c.get("count"), "unconfirmed": c.get("unconfirmed"), "note": c.get("note")}
    except Exception:
        logger.exception("capacity failed")
        return None


# ---------------------------------------------------------------------------
# routes: read
# ---------------------------------------------------------------------------
@dispatchdesk_bp.route("/api/va/dispatch/overview", methods=["POST"])
def api_overview():
    ident, data, err = _ident_or_401()
    if err:
        return err
    haulers = roster()
    jobs = board()
    counts = {"open": len(jobs["open"]), "scheduled": len(jobs["scheduled"]), "active": len(jobs["active"]),
              "done_today": len(jobs["done"]), "cancelled_today": len(jobs["cancelled"]),
              "live": sum(1 for h in haulers if h["live"]), "online": sum(1 for h in haulers if h["online"]),
              "standby": sum(1 for h in haulers if h["standby"])}
    return jsonify({"va": ident.get("name"), "manager": _sees_everyone(ident), "now": iso_utc(_now()),
                    "counts": counts, "capacity": capacity_block(), "haulers": haulers, "jobs": jobs,
                    "recent": recent(), "area": area()}), 200


def _job_or_404(data):
    job = db.session.get(Job, (data.get("job_id") or "").strip()) if data.get("job_id") else None
    if not job:
        return None, (jsonify({"error": "Job not found — refresh the board."}), 404)
    return job, None


@dispatchdesk_bp.route("/api/va/dispatch/job", methods=["POST"])
def api_job():
    ident, data, err = _ident_or_401()
    if err:
        return err
    job, err = _job_or_404(data)
    if err:
        return err
    from assignment import job_events
    events = []
    for e in job_events(job.id):
        events.append({"at": iso_utc(e.created_at), "type": (e.to_status or "") if e.to_status else (e.meta or {}).get("event", "note"),
                       "actor": e.actor_role or "system", "detail": e.reason or ((e.meta or {}).get("detail") if isinstance(e.meta, dict) else None) or ""})
    dump = None
    if job.lat is not None and job.lng is not None:
        try:
            from dump_suggest import suggest, infer_category, county_for
            s = suggest(float(job.lat), float(job.lng), category=infer_category(job.items),
                        origin_county=county_for(float(job.lat)))
            best = (s or {}).get("suggested") or {}
            if best:
                dump = {"facility": (best.get("facility") or {}).get("name"), "miles": best.get("miles"), "minutes": best.get("minutes"),
                        "rate_per_ton": best.get("rate_per_ton"), "est_tip": best.get("est_tip"), "reasons": best.get("reasons") or []}
        except Exception:
            logger.exception("dump suggestion failed")
    history = []
    if job.customer_id:
        for j in (Job.query.filter(Job.customer_id == job.customer_id, Job.id != job.id)
                  .order_by(Job.created_at.desc()).limit(8).all()):
            history.append({"code": j.confirmation_code, "status": j.status, "when": fmt_local(j.scheduled_at, "%b %-d", "—"),
                            "total": j.total_price, "address": j.address})
    return jsonify({"job": _card(job), "events": events, "dump": dump, "customer_jobs": history}), 200


@dispatchdesk_bp.route("/api/va/dispatch/candidates", methods=["POST"])
def api_candidates():
    ident, data, err = _ident_or_401()
    if err:
        return err
    job, err = _job_or_404(data)
    if err:
        return err
    from assignment import eligibility
    from sameday import standby_ids
    now = _now()
    try:
        on_standby = set(standby_ids())
    except Exception:
        on_standby = set()
    rows = []
    for c in Contractor.query.filter_by(approval_status="approved").all():
        row = _hauler_row(c, now, on_standby)
        try:
            v = eligibility(job, c, at=job.scheduled_at, mode="manual", on_standby=on_standby)
            dist = getattr(v, "distance", None)
            if dist is None:
                dist = getattr(v, "distance_miles", None)
            if dist is None and None not in (job.lat, job.lng, c.current_lat, c.current_lng):
                from dispatcher import haversine
                dist = haversine(float(job.lat), float(job.lng), float(c.current_lat), float(c.current_lng))
            row.update({"distance_miles": round(float(dist), 1) if dist is not None else None,
                        "ok": bool(v.ok), "reasons": [_reason_text(r) for r in (v.reasons or [])],
                        "warnings": [_reason_text(w) for w in (getattr(v, "warnings", []) or [])],
                        "reason_codes": list(v.reasons or [])})
        except Exception:
            logger.exception("eligibility failed")
            row.update({"distance_miles": None, "ok": False, "reasons": ["could not evaluate"], "warnings": []})
        rows.append(row)
    rows.sort(key=lambda h: (not h["ok"], not h["live"], h["distance_miles"] if h["distance_miles"] is not None else 10 ** 4, -(h["completed"] or 0)))
    return jsonify({"job": _card(job), "haulers": rows}), 200


@dispatchdesk_bp.route("/api/va/dispatch/hauler", methods=["POST"])
def api_hauler():
    ident, data, err = _ident_or_401()
    if err:
        return err
    c = db.session.get(Contractor, (data.get("contractor_id") or "").strip()) if data.get("contractor_id") else None
    if not c:
        return jsonify({"error": "Hauler not found."}), 404
    from hauler_reliability import stats
    row = _hauler_row(c)
    u = c.user
    row["email"] = u.email if u else None
    row["docs"] = {"insurance_expiry": iso_utc(c.insurance_expiry) if c.insurance_expiry else None,
                   "license_expiry": iso_utc(c.license_expiry) if c.license_expiry else None,
                   "verification": c.documents_verification_status}
    try:
        st = stats(c.id)
        row["stats"] = {k: st.get(k) for k in ("offered", "accepted", "completed", "no_shows")}
        row["stats"]["last_completed_at"] = iso_utc(st.get("last_completed_at")) if st.get("last_completed_at") else None
    except Exception:
        row["stats"] = None
    row["recent_jobs"] = [{"code": j.confirmation_code, "status": j.status, "when": fmt_local(j.scheduled_at, "%b %-d, %-I %p", "—"),
                           "total": j.total_price, "address": j.address}
                          for j in Job.query.filter_by(driver_id=c.id).order_by(Job.scheduled_at.desc().nullslast()).limit(8).all()]
    return jsonify({"hauler": row}), 200


@dispatchdesk_bp.route("/api/va/dispatch/hauler/text", methods=["POST"])
def api_hauler_text():
    ident, data, err = _ident_or_401()
    if err:
        return err
    c = db.session.get(Contractor, (data.get("contractor_id") or "").strip()) if data.get("contractor_id") else None
    if not c or not c.user or not c.user.phone:
        return jsonify({"error": "That hauler has no phone on file."}), 404
    body = (data.get("body") or "").strip()[:900]
    if len(body) < 2:
        return jsonify({"error": "Type the message first."}), 400
    from desk_line import send_desk_text
    sid = send_desk_text(c.user.phone, body, va_name=ident.get("name"))
    if not sid:
        return jsonify({"error": "The text didn't go through."}), 502
    audit("dispatch_text_hauler", "contractor", c.id, {"by": ident.get("name"), "len": len(body)})
    return jsonify({"ok": True}), 200


@dispatchdesk_bp.route("/api/va/dispatch/geocode", methods=["POST"])
def api_geocode():
    ident, data, err = _ident_or_401()
    if err:
        return err
    address = " ".join((data.get("address") or "").split())[:200]
    if len(address) < 4:
        return jsonify({"ok": False, "message": "Type the address first."}), 200
    from sameday import geocode
    from geofencing import is_in_service_area
    try:
        pt = geocode(address)
    except Exception:
        logger.exception("geocode failed")
        pt = None
    if not pt:
        return jsonify({"ok": False, "message": "Couldn't find that address. Add the city or ZIP."}), 200
    lat, lng = pt
    inside = bool(is_in_service_area(lat, lng))
    return jsonify({"ok": True, "lat": lat, "lng": lng, "in_area": inside, "county": _county(lat),
                    "message": None if inside else "That address is outside the seven counties we serve."}), 200


@dispatchdesk_bp.route("/api/va/dispatch/catalog", methods=["POST"])
def api_catalog():
    ident, data, err = _ident_or_401()
    if err:
        return err
    from routes.booking import CATEGORY_PRICES, ADDON_FEES, TRUCK_LOAD_PRICES, MINIMUM_JOB_PRICE, SERVICE_FEE_RATE
    items = []
    for key, prices in CATEGORY_PRICES.items():
        if key in GENERIC_BUCKETS:
            continue
        sizes = {k: v for k, v in prices.items() if k != "default"}
        price = prices.get("default") or prices.get("medium") or (min(sizes.values()) if sizes else None)
        group = next((g for g, prefixes in ITEM_GROUPS if any(key.startswith(p) or p in key for p in prefixes)), "Other")
        items.append({"key": key, "name": _pretty(key), "price": price, "sizes": sizes or None, "group": group})
    addons = [{"key": k, "label": {"disassembly_items": "Disassembly (per item)", "stair_flights": "Stairs (per flight)"}.get(k, _pretty(k)), "price": v}
              for k, v in ADDON_FEES.items()]
    loads = [{"key": k, "label": {"min": "Minimum load", "full": "Full truck"}.get(k, k + " truck"), "price": v[1]} for k, v in TRUCK_LOAD_PRICES.items()]
    return jsonify({"items": items, "addons": addons, "loads": loads, "minimum": MINIMUM_JOB_PRICE, "service_fee_rate": SERVICE_FEE_RATE}), 200


def _clean_items(raw):
    out = []
    for e in raw or []:
        if not isinstance(e, dict) or not e.get("category"):
            continue
        try:
            q = int(e.get("quantity") or 1)
        except (TypeError, ValueError):
            q = 1
        if q <= 0:
            continue
        item = {"category": str(e["category"])[:60], "quantity": min(q, 50)}
        if e.get("size"):
            item["size"] = str(e["size"])[:20]
        if e.get("name"):
            item["name"] = str(e["name"])[:80]
        out.append(item)
    return out


def _estimate(items, scheduled_date, lat, lng, addons):
    from routes.booking import calculate_estimate
    est = calculate_estimate(items, scheduled_date=scheduled_date or None, lat=lat, lng=lng, addons=addons or None)
    lines = []
    for l in est.get("items") or []:
        lines.append({"category": l.get("category"), "name": l.get("name") or _pretty(l.get("category")),
                      "quantity": l.get("quantity"), "unit_price": l.get("unit_price"), "line_total": l.get("line_total")})
    keys = ("items_subtotal", "volume_discount", "volume_discount_label", "surge_amount", "surge_reasons", "service_fee",
            "recycling_fees", "addons_total", "disposal_fee", "total", "minimum_applied", "estimated_duration", "truck_size")
    out = {k: est.get(k) for k in keys}
    out["items"] = lines
    out["base_price"] = est.get("base_price")
    out["surge_multiplier"] = est.get("surge_multiplier")
    return out, est


@dispatchdesk_bp.route("/api/va/dispatch/estimate", methods=["POST"])
def api_estimate():
    ident, data, err = _ident_or_401()
    if err:
        return err
    items = _clean_items(data.get("items"))
    if not items:
        return jsonify({"error": "Add at least one item.", "code": "invalid_items"}), 400
    try:
        out, _ = _estimate(items, data.get("scheduled_date"), data.get("lat"), data.get("lng"), data.get("addons"))
    except Exception:
        logger.exception("estimate failed")
        return jsonify({"error": "Couldn't price that — check the items.", "code": "estimate_failed"}), 422
    return jsonify({"estimate": out}), 200


@dispatchdesk_bp.route("/api/va/dispatch/slots", methods=["POST"])
def api_slots():
    ident, data, err = _ident_or_401()
    if err:
        return err
    day = (data.get("date") or "").strip()[:10]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        return jsonify({"error": "date must be YYYY-MM-DD"}), 400
    from availability import slots_for
    try:
        slots = slots_for(day, data.get("lat"), data.get("lng"))
    except Exception:
        logger.exception("slots failed")
        slots = []
    return jsonify({"date": day, "slots": [{"slot": s.get("slot"), "label": SLOT_LABELS.get(s.get("slot"), s.get("label")),
                                            "start_at": s.get("start_at"), "available": bool(s.get("available")), "reason": s.get("reason")}
                                           for s in slots]}), 200


def _customer_row(u):
    from inbound import customer_summary
    try:
        s = customer_summary(u) or {}
    except Exception:
        s = {}
    last = s.get("last_job") or None
    return {"id": u.id, "name": u.name, "phone": u.phone, "email": u.email, "prior_jobs": s.get("prior_jobs", 0),
            "last_job": {"code": last.get("code"), "status": last.get("status"), "when": last.get("scheduled_human"), "total": last.get("total_price")} if last else None}


@dispatchdesk_bp.route("/api/va/dispatch/customer", methods=["POST"])
def api_customer():
    ident, data, err = _ident_or_401()
    if err:
        return err
    q = (data.get("q") or "").strip()[:80]
    if len(q) < 3:
        return jsonify({"customers": []}), 200
    found = []
    d = _digits(q)
    if len(d) >= 7:
        from inbound import find_customer
        u = find_customer(d[-10:]) if len(d) >= 10 else None
        if u:
            found.append(u)
        if len(d) < 10 or not u:
            for u2 in User.query.filter(User.role == "customer", User.phone.ilike("%" + d[-7:] + "%")).limit(8).all():
                if u2 not in found:
                    found.append(u2)
    else:
        for u2 in User.query.filter(User.role == "customer", User.name.ilike("%" + q + "%")).limit(8).all():
            found.append(u2)
    return jsonify({"customers": [_customer_row(u) for u in found]}), 200


# ---------------------------------------------------------------------------
# routes: book
# ---------------------------------------------------------------------------
def _find_or_create_customer(name, phone_e164, email):
    from inbound import find_customer
    u = find_customer(_digits(phone_e164)[-10:])
    if not u and email:
        u = User.query.filter(User.email.ilike(email)).first()
    if u:
        if name and not u.name:
            u.name = name
        return u, False
    u = User(id=generate_uuid(), email=email or "{}@phone.goumuve.com".format(_digits(phone_e164)), phone=phone_e164,
             name=name or "Customer", role="customer")
    db.session.add(u)
    db.session.flush()
    return u, True


@dispatchdesk_bp.route("/api/va/dispatch/book", methods=["POST"])
def api_book():
    ident, data, err = _ident_or_401()
    if err:
        return err
    va = ident.get("name") or ""
    name = (data.get("name") or "").strip()[:120]
    phone = _e164(data.get("phone"))
    email = (data.get("email") or "").strip()[:254] or None
    address = " ".join((data.get("address") or "").split())[:300]
    if not phone:
        return jsonify({"error": "A 10-digit phone number is required.", "code": "invalid_phone"}), 400
    if len(address) < 4:
        return jsonify({"error": "The pickup address is required.", "code": "invalid_address"}), 400
    lat, lng = data.get("lat"), data.get("lng")
    if lat is None or lng is None:
        try:
            from sameday import geocode
            pt = geocode(address)
            if pt:
                lat, lng = pt
        except Exception:
            logger.exception("book geocode failed")
    if lat is None or lng is None:
        return jsonify({"error": "Couldn't place that address on the map — use Find first.", "code": "invalid_coordinates"}), 422
    from geofencing import is_in_service_area
    if not is_in_service_area(float(lat), float(lng)):
        return jsonify({"error": "That address is outside the seven counties we serve.", "code": "outside_market"}), 422
    items = _clean_items(data.get("items"))
    load = (data.get("load") or "").strip()
    if not items and not load:
        return jsonify({"error": "Add at least one item.", "code": "invalid_items"}), 400
    day = (data.get("scheduled_date") or "").strip()[:10]
    slot = (data.get("scheduled_time") or "").strip()[:5]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        return jsonify({"error": "Pick a date.", "code": "invalid_date"}), 400
    if re.fullmatch(r"\d{1,2}-\d{1,2}", slot):
        slot = "{:02d}:00".format(int(slot.split("-")[0]))
    try:
        scheduled_at = _naive(parse_local(day, slot or "09:00"))
    except Exception:
        return jsonify({"error": "That date or time didn't parse.", "code": "invalid_date"}), 400
    if scheduled_at < _now() - timedelta(minutes=30):
        return jsonify({"error": "That time is already in the past.", "code": "in_the_past"}), 400

    if load:
        from routes.booking import TRUCK_LOAD_PRICES, SERVICE_FEE_RATE
        if load not in TRUCK_LOAD_PRICES:
            return jsonify({"error": "Unknown truck load.", "code": "invalid_items"}), 400
        base = float(TRUCK_LOAD_PRICES[load][1])
        items = [{"category": "general", "quantity": 1, "name": "Truck load ({})".format(load)}]
        from disposal import disposal_estimate
        try:
            disp = disposal_estimate([{"category": "general", "quantity": max(1, int(TRUCK_LOAD_PRICES[load][0] * 8))}], lat, lng) or {}
        except Exception:
            disp = {}
        service_fee = round(base * SERVICE_FEE_RATE, 2)
        disposal_fee = float(disp.get("disposal_fee") or 0.0)
        pricing = {"items_subtotal": base, "base_price": base, "service_fee": service_fee, "disposal_fee": disposal_fee,
                   "total": round(base + service_fee + disposal_fee, 2), "volume_discount": 0.0, "surge_multiplier": 1.0,
                   "truck_size": load, "estimated_duration": None}
    else:
        try:
            pricing, _raw = _estimate(items, day, lat, lng, data.get("addons"))
        except Exception:
            logger.exception("book estimate failed")
            return jsonify({"error": "Couldn't price those items.", "code": "estimate_failed"}), 422

    notes = (data.get("notes") or "").strip()[:600]
    payment_mode = "settled" if data.get("payment") == "settled" else "link"
    note_lines = [notes] if notes else []
    note_lines.append("Booked on the dispatch desk by {}.".format(va or "the desk"))
    if payment_mode == "settled":
        note_lines.append("Payment settled outside Stripe (cash/invoice) — desk.")
    try:
        cust, created = _find_or_create_customer(name, phone, email)
        job = Job(id=generate_uuid(), customer_id=cust.id, status="pending", address=address, lat=float(lat), lng=float(lng),
                  items=items, scheduled_at=scheduled_at, base_price=pricing.get("base_price") or pricing.get("items_subtotal"),
                  item_total=pricing.get("items_subtotal"), service_fee=pricing.get("service_fee"), disposal_fee=pricing.get("disposal_fee"),
                  surge_multiplier=pricing.get("surge_multiplier") or 1.0, discount_amount=pricing.get("volume_discount") or 0.0,
                  total_price=pricing["total"], notes="\n".join(note_lines), lead_source="phone_desk",
                  confirmation_code=generate_referral_code(), volume_estimate=None)
        db.session.add(job)
        db.session.flush()
        pay = Payment(id=generate_uuid(), job_id=job.id, amount=pricing["total"], service_fee=pricing.get("service_fee") or 0.0,
                      disposal_fee=pricing.get("disposal_fee") or 0.0, payment_status="pending",
                      payout_method="manual" if payment_mode == "settled" else None)
        db.session.add(pay)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.exception("book failed")
        if "UNIQUE" in str(exc).upper() or "unique" in str(exc):
            return jsonify({"error": "That phone or email already belongs to another customer.", "code": "duplicate_customer"}), 409
        return jsonify({"error": "Couldn't save the booking.", "code": "save_failed"}), 500
    audit("dispatch_book", "job", job.id, {"by": va, "total": pricing["total"], "payment": payment_mode, "items": len(items)})
    _action(job.id, "book", va)

    texted, pay_url = False, None
    if payment_mode == "link":
        try:
            from routes.vapi import _build_checkout_url
            pay_url = _build_checkout_url(job.id, pricing["total"])
        except Exception:
            logger.exception("pay link failed")
    if data.get("send_text", True):
        try:
            from notifications import send_booking_sms
            send_booking_sms(phone, job.id, fmt_local(scheduled_at, "%a %b %-d, %-I:%M %p", day), address,
                             pay_url=pay_url, confirmation_code=job.confirmation_code)
            texted = True
            if pay_url:
                _action(job.id, "paylink", va)
        except Exception:
            logger.exception("booking text failed")
    try:
        from booking_alerts import notify_booking
        notify_booking(job, "booked", pay)
    except Exception:
        logger.exception("booking alert failed")

    assigned, message = False, "Booked #{} for {}.".format(job.confirmation_code, cust.name or "the customer")
    cid = (data.get("contractor_id") or "").strip()
    if cid:
        c = db.session.get(Contractor, cid)
        if c:
            ok, payload, http = _assign(job, c, ident, bool(data.get("force")))
            assigned = ok
            message += " " + (payload.get("message") or payload.get("error") or "")
    offers = 0
    if not assigned and data.get("broadcast"):
        offers = _broadcast(job, va)
        if offers:
            message += " Offered to {} nearby hauler{}.".format(offers, "" if offers == 1 else "s")
    db.session.refresh(job)
    return jsonify({"ok": True, "job": _card(job), "texted": texted, "pay_url": pay_url, "assigned": assigned,
                    "broadcast": offers, "message": message.strip()}), 201


# ---------------------------------------------------------------------------
# routes: act on a job
# ---------------------------------------------------------------------------
def _assign(job, contractor, ident, force=False):
    from dispatch_service import assign_contractor_to_job
    va = ident.get("name") or "desk"
    try:
        assign_contractor_to_job(job, contractor, assigned_by="{} (dispatch desk)".format(va),
                                 actor={"role": "va", "name": va}, source="va_desk", force=force)
    except Exception as exc:
        code = getattr(exc, "code", None) or "assign_failed"
        reasons = list(getattr(exc, "reasons", None) or [])
        status = getattr(exc, "status_code", None) or 409
        logger.warning("assign failed: %s %s", code, reasons)
        return False, {"error": str(getattr(exc, "message", None) or exc) or "Couldn't assign that hauler.", "code": code, "reasons": reasons}, status
    audit("dispatch_assign", "job", job.id, {"by": va, "contractor": contractor.id, "force": force})
    _action(job.id, "assign", va, contractor.id)
    name = (contractor.user.name if contractor.user else None) or "the hauler"
    return True, {"ok": True, "message": "Assigned to {}. {}".format(name, "They'll get the job console by text." if contractor.is_concierge else "They've been notified in the app.")}, 200


@dispatchdesk_bp.route("/api/va/dispatch/assign-hauler", methods=["POST"])
def api_assign():
    ident, data, err = _ident_or_401()
    if err:
        return err
    job, err = _job_or_404(data)
    if err:
        return err
    c = db.session.get(Contractor, (data.get("contractor_id") or "").strip()) if data.get("contractor_id") else None
    if not c or c.approval_status != "approved":
        return jsonify({"error": "Pick an approved hauler."}), 404
    ok, payload, http = _assign(job, c, ident, bool(data.get("force")))
    if not ok:
        return jsonify(payload), http
    db.session.refresh(job)
    payload["job"] = _card(job)
    return jsonify(payload), 200


def _broadcast(job, va):
    from dispatcher import broadcast_job
    from models import JobOffer
    try:
        broadcast_job(job.id)
    except Exception:
        logger.exception("broadcast failed")
        return 0
    n = JobOffer.query.filter_by(job_id=job.id).count()
    audit("dispatch_broadcast", "job", job.id, {"by": va, "offers": n})
    _action(job.id, "broadcast", va)
    return n


@dispatchdesk_bp.route("/api/va/dispatch/job/broadcast", methods=["POST"])
def api_broadcast():
    ident, data, err = _ident_or_401()
    if err:
        return err
    job, err = _job_or_404(data)
    if err:
        return err
    if job.driver_id:
        return jsonify({"error": "This job already has a hauler.", "code": "already_assigned"}), 409
    n = _broadcast(job, ident.get("name"))
    db.session.refresh(job)
    return jsonify({"ok": True, "offers": n, "job": _card(job),
                    "message": "Offered to {} hauler{}.".format(n, "" if n == 1 else "s") if n else "No eligible hauler is in range right now."}), 200


@dispatchdesk_bp.route("/api/va/dispatch/job/transition", methods=["POST"])
def api_transition():
    ident, data, err = _ident_or_401()
    if err:
        return err
    job, err = _job_or_404(data)
    if err:
        return err
    status = (data.get("status") or "").strip()
    if status not in ("accepted", "en_route", "arrived", "started", "completed"):
        return jsonify({"error": "Unknown status.", "code": "bad_status"}), 400
    from assignment import transition_job
    va = ident.get("name") or "desk"
    reason = (data.get("reason") or "").strip()[:200] or "dispatch desk"
    ok, payload, http = transition_job(job, status, {"role": "admin", "name": "{} (dispatch desk)".format(va)},
                                       data={"override_reason": reason, "exception_reason": reason if status in ("started", "completed") else None},
                                       contractor=job.driver)
    if not ok:
        return jsonify(payload), http
    audit("dispatch_transition", "job", job.id, {"by": va, "to": status, "reason": reason})
    _action(job.id, "transition", va)
    db.session.refresh(job)
    cust = job.customer
    try:
        if status == "en_route" and cust and cust.phone:
            from sms_service import sms_driver_en_route
            sms_driver_en_route(cust.phone, (job.driver.user.name if job.driver and job.driver.user else "Your hauler"), job.tracking_url())
        elif status == "completed" and cust and cust.phone:
            from sms_service import sms_job_completed
            sms_job_completed(cust.phone, job.total_price)
    except Exception:
        logger.exception("transition customer text failed")
    return jsonify({"ok": True, "job": _card(job)}), 200


@dispatchdesk_bp.route("/api/va/dispatch/job/reschedule", methods=["POST"])
def api_reschedule():
    ident, data, err = _ident_or_401()
    if err:
        return err
    job, err = _job_or_404(data)
    if err:
        return err
    if job.status not in ("pending", "confirmed", "assigned", "accepted", "broadcasting", "delegating"):
        return jsonify({"error": "This job can't be moved once the hauler is on the way.", "code": "not_reschedulable"}), 409
    day = (data.get("scheduled_date") or "").strip()[:10]
    slot = (data.get("scheduled_time") or "").strip()[:5]
    if re.fullmatch(r"\d{1,2}-\d{1,2}", slot):
        slot = "{:02d}:00".format(int(slot.split("-")[0]))
    try:
        new_at = _naive(parse_local(day, slot or "09:00"))
    except Exception:
        return jsonify({"error": "That date or time didn't parse.", "code": "invalid_date"}), 400
    if new_at < _now():
        return jsonify({"error": "That time is already in the past.", "code": "in_the_past"}), 400
    old = job.scheduled_at
    job.scheduled_at = new_at
    job.rescheduled_count = (job.rescheduled_count or 0) + 1
    job.hauler_confirmed_at = None
    job.hauler_confirmed_by = None
    db.session.commit()
    va = ident.get("name") or "desk"
    audit("dispatch_reschedule", "job", job.id, {"by": va, "from": iso_utc(old), "to": iso_utc(new_at)})
    _action(job.id, "resched", va)
    if data.get("notify", True) and job.customer and job.customer.phone:
        try:
            from desk_line import send_desk_text
            send_desk_text(job.customer.phone, "Umuve: your pickup #{} is now {}. Reply here with any questions.".format(
                job.confirmation_code, fmt_local(new_at, "%a %b %-d, %-I:%M %p")), va_name=va)
        except Exception:
            logger.exception("reschedule text failed")
    if job.driver and job.driver.user and job.driver.user.phone:
        try:
            from desk_line import send_desk_text
            send_desk_text(job.driver.user.phone, "Umuve dispatch: job #{} at {} moved to {}. Reply Y to confirm you can still make it.".format(
                job.confirmation_code, job.address, fmt_local(new_at, "%a %b %-d, %-I:%M %p")), va_name=va)
        except Exception:
            logger.exception("reschedule hauler text failed")
    return jsonify({"ok": True, "job": _card(job)}), 200


@dispatchdesk_bp.route("/api/va/dispatch/job/cancel", methods=["POST"])
def api_cancel():
    ident, data, err = _ident_or_401()
    if err:
        return err
    job, err = _job_or_404(data)
    if err:
        return err
    if job.status in ("completed", "cancelled", "paid", "refunded"):
        return jsonify({"error": "This job is already {}.".format(job.status), "code": "terminal"}), 409
    reason = (data.get("reason") or "").strip()[:120] or "cancelled by the dispatch desk"
    from cancellation import execute_cancellation, notify_customer_cancelled
    va = ident.get("name") or "desk"
    try:
        outcome, result = execute_cancellation(job, actor="va", reason=reason, confirmed=True)
    except Exception:
        logger.exception("cancel failed")
        db.session.rollback()
        return jsonify({"error": "Couldn't cancel that job.", "code": "cancel_failed"}), 500
    if not (result or {}).get("applied", True):
        return jsonify({"error": getattr(outcome, "message", None) or "Cancellation was not applied.",
                        "code": getattr(outcome, "reason_code", None) or "not_applied"}), 409
    try:
        notify_customer_cancelled(job)
    except Exception:
        logger.exception("cancel notify failed")
    audit("dispatch_cancel", "job", job.id, {"by": va, "reason": reason})
    _action(job.id, "cancel", va)
    db.session.refresh(job)
    return jsonify({"ok": True, "job": _card(job), "cancellation": result}), 200


@dispatchdesk_bp.route("/api/va/dispatch/job/text", methods=["POST"])
def api_job_text():
    ident, data, err = _ident_or_401()
    if err:
        return err
    job, err = _job_or_404(data)
    if err:
        return err
    to = data.get("to")
    body = (data.get("body") or "").strip()[:900]
    if len(body) < 2:
        return jsonify({"error": "Type the message first."}), 400
    if to == "hauler":
        phone = job.driver.user.phone if job.driver and job.driver.user else None
    else:
        to = "customer"
        phone = job.customer.phone if job.customer else None
    if not phone:
        return jsonify({"error": "No phone on file for the {}.".format(to)}), 404
    from desk_line import send_desk_text
    va = ident.get("name")
    sid = send_desk_text(phone, body, va_name=va)
    if not sid:
        return jsonify({"error": "The text didn't go through."}), 502
    audit("dispatch_text", "job", job.id, {"by": va, "to": to, "len": len(body)})
    _action(job.id, "text", va, job.driver_id if to == "hauler" else None)
    return jsonify({"ok": True}), 200


@dispatchdesk_bp.route("/api/va/dispatch/job/paylink", methods=["POST"])
def api_paylink():
    ident, data, err = _ident_or_401()
    if err:
        return err
    job, err = _job_or_404(data)
    if err:
        return err
    if not job.total_price:
        return jsonify({"error": "This job has no price yet."}), 409
    try:
        from routes.vapi import _build_checkout_url
        url = _build_checkout_url(job.id, job.total_price)
    except Exception:
        logger.exception("paylink failed")
        return jsonify({"error": "Couldn't create the pay link."}), 502
    texted = False
    va = ident.get("name")
    if data.get("send", True) and job.customer and job.customer.phone:
        from desk_line import send_desk_text
        texted = bool(send_desk_text(job.customer.phone, "Umuve booking #{}: ${:.2f}. Pay here to lock in your pickup: {}".format(
            job.confirmation_code, float(job.total_price), url), va_name=va))
    audit("dispatch_paylink", "job", job.id, {"by": va, "texted": texted})
    _action(job.id, "paylink", va)
    return jsonify({"ok": True, "url": url, "texted": texted}), 200


@dispatchdesk_bp.route("/api/va/dispatch/job/confirm", methods=["POST"])
def api_confirm():
    ident, data, err = _ident_or_401()
    if err:
        return err
    job, err = _job_or_404(data)
    if err:
        return err
    if not job.driver_id:
        return jsonify({"error": "This job has no hauler to confirm.", "code": "no_hauler"}), 409
    from hauler_confirm import mark_confirmed, redispatch
    va = ident.get("name") or "desk"
    note = (data.get("note") or "").strip()[:300] or None
    if data.get("confirmed", True):
        mark_confirmed(job, va, note)
        db.session.commit()
        audit("hauler_confirmed", "job", job.id, {"by": va, "hauler": job.driver_id, "note": note})
        _action(job.id, "confirm", va, job.driver_id)
        db.session.refresh(job)
        return jsonify({"ok": True, "job": _card(job)}), 200
    res = redispatch(job, "va", "hauler_declined_on_confirm", va_name=va, count_no_show=False)
    audit("hauler_cant_make_it", "job", job.id, {"by": va, "released": res.get("released"), "waved": res.get("waved")})
    _action(job.id, "redispatch", va)
    db.session.refresh(job)
    return jsonify({"ok": True, "job": _card(job), "released": res.get("released"), "waved": res.get("waved")}), 200


# ---------------------------------------------------------------------------
# map tiles — proxied so the desk CSP (img-src 'self') can show a real map
# ---------------------------------------------------------------------------
import threading as _threading
from collections import OrderedDict as _OrderedDict

_TILE_UA = os.environ.get("TILE_USER_AGENT", "UmuveDesk/1.0 (contact@goumuve.com)")
_TILE_SRC = os.environ.get("TILE_URL_TEMPLATE", "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
_TILE_MIN_Z, _TILE_MAX_Z = 7, 17
_TILE_CACHE, _TILE_LOCK, _TILE_CACHE_MAX = _OrderedDict(), _threading.Lock(), 1500


def _fetch_tile(z, x, y):
    key = (z, x, y)
    with _TILE_LOCK:
        hit = _TILE_CACHE.get(key)
        if hit is not None:
            _TILE_CACHE.move_to_end(key)
            return hit
    import requests as _rq
    r = _rq.get(_TILE_SRC.format(z=z, x=x, y=y), headers={"User-Agent": _TILE_UA, "Accept": "image/png"}, timeout=8)
    if r.status_code != 200 or not r.content:
        return None
    with _TILE_LOCK:
        _TILE_CACHE[key] = r.content
        while len(_TILE_CACHE) > _TILE_CACHE_MAX:
            _TILE_CACHE.popitem(last=False)
    return r.content


@dispatchdesk_bp.route("/api/va/dispatch/tile/<int:z>/<int:x>/<int:y>.png", methods=["GET"])
def api_tile(z, x, y):
    """Same-origin OpenStreetMap tiles for the dispatch map. Zoom is clamped to
    the service area's useful range and tiles are cached in memory, so the
    upstream sees one small desk, not a crawler. Attribution is drawn on the map."""
    if z < _TILE_MIN_Z or z > _TILE_MAX_Z or x < 0 or y < 0 or x >= 2 ** z or y >= 2 ** z:
        return Response(status=404)
    try:
        data = _fetch_tile(z, x, y)
    except Exception:
        logger.exception("tile fetch failed")
        data = None
    if not data:
        return Response(status=502)
    resp = Response(data, mimetype="image/png")
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


# ---------------------------------------------------------------------------
# page
# ---------------------------------------------------------------------------
_PAGE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "dispatch-page.html")


def dispatch_page():
    try:
        with open(_PAGE_PATH, "r", encoding="utf-8") as fh:
            html = fh.read()
    except OSError:
        return Response("Dispatch page is not built yet.", status=503, mimetype="text/plain")
    resp = Response(html, mimetype="text/html")
    resp.headers["Cache-Control"] = "no-cache, must-revalidate"
    return resp
