"""Inbound customer calls on the Call Desk (Phase 6).

Google Local Services Ads send customers to the desk line. A human closes
better than Maya, so every inbound call rings the humans first — one
<Client> per VA on the clock (identity ``desk-<slug>``), the legacy shared
``desk`` identity, and the forward cell — and only falls back to Maya (the
Vapi receptionist) when nobody picks up, or outside human hours.

The TwiML itself is built in desk_line.py (twilio_voice_inbound /
twilio_voice_after_in / twilio_voice_after_maya); this module owns the
decisions and the data:

  humans_online()          who is clocked in (VaShift open)
  ring_identities()        Twilio <Client> identities to ring right now
  in_human_hours()         INBOUND_HUMAN_HOURS window, America/New_York
  maya_number()            where the fallback <Dial> goes
  record_call()/touch_call InboundCall rows keyed by CallSid

VA-facing (desk identity: JWT or passcode):
  POST /api/va/inbound/whois        {phone} → customer | prospect | unknown
  POST /api/va/inbound/quote        {items, zip, date?} → engine quote
  POST /api/va/inbound/quote-text   text the quote to the caller
  POST /api/va/inbound/book         create the job + text confirmation & pay link
  POST /api/va/inbound/callback     they asked for a call back
  POST /api/va/inbound/outcome      not_fit | spam
  POST /api/va/inbound/recent       recent customer calls (for the inbox)
  POST /api/va/inbound/stats        manager: last N days, by hour
Public:
  GET  /api/inbound/humans-online   {online, count} — Maya's transfer check

Env:
  INBOUND_HUMAN_HOURS  "08:00-20:00" (local, 7 days). "00:00-24:00" = always.
  MAYA_NUMBER          E.164 Maya line (falls back to VAPI_PHONE, then the
                       public +15619441636).
  FEATURE_INBOUND_CUSTOMERS / FEATURE_MAYA_FALLBACK  flag env overrides.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from desk_auth import desk_identity, desk_va_name, audit, require_desk, MANAGER_ROLES
from models import db, User, Job, DeskActivity, VaShift, CallProspect
from models_inbound import InboundCall, CallbackRequest
from timeutils import local_now, parse_local, fmt_local, to_local, local_naive_to_utc

try:
    from extensions import limiter
except Exception:  # pragma: no cover
    limiter = None

logger = logging.getLogger(__name__)

inbound_bp = Blueprint("inbound", __name__)

_ratelimit = (
    limiter.limit("240 per hour; 30 per minute")
    if limiter is not None
    else (lambda f: f)
)

DEFAULT_MAYA = "+15619441636"
DEFAULT_HOURS = "08:00-20:00"
RING_SECONDS = 20
MAYA_RING_SECONDS = 30
LEGACY_IDENTITY = "desk"
RECENT_DAYS = 7
MAX_ITEMS = 40
MAX_QTY = 50

# Schedule windows the intake card offers → the slot start the engine stores.
WINDOWS = {
    "8-10": "08:00", "10-12": "10:00", "12-2": "12:00", "2-4": "14:00", "4-6": "16:00",
}
WINDOW_LABELS = {
    "8-10": "8–10 AM", "10-12": "10 AM–12 PM", "12-2": "12–2 PM", "2-4": "2–4 PM", "4-6": "4–6 PM",
}

OUTCOMES = ("booked", "quoted", "callback", "not_fit", "spam")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _env(name, default=""):
    return (os.environ.get(name) or default).strip()


def _digits(phone):
    d = re.sub(r"\D", "", phone or "")
    return d[-10:] if len(d) >= 10 else d


def _e164(digits):
    return "+1" + digits if len(digits) == 10 else ""


def _pretty(digits):
    return "({}) {}-{}".format(digits[:3], digits[3:6], digits[6:]) if len(digits) == 10 else digits


def _now_utc_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _now_local():
    """Business-local clock. Tests patch this."""
    return local_now()


def _flag(name, default=True):
    try:
        from flags import flag
        return flag(name)
    except Exception:
        return default


def inbound_enabled():
    return _flag("inbound_customers")


def maya_fallback_enabled():
    return _flag("maya_fallback")


def maya_number():
    raw = _env("MAYA_NUMBER") or _env("VAPI_PHONE") or DEFAULT_MAYA
    d = re.sub(r"\D", "", raw)
    if len(d) == 10:
        return "+1" + d
    if len(d) == 11 and d.startswith("1"):
        return "+" + d
    return raw if raw.startswith("+") else DEFAULT_MAYA


def human_hours():
    """(start_minute, end_minute) of the human window, local time.
    end == 24*60 or start == end means always."""
    raw = _env("INBOUND_HUMAN_HOURS", DEFAULT_HOURS)
    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*$", raw)
    if not m:
        raw = DEFAULT_HOURS
        m = re.match(r"^(\d{2}):(\d{2})-(\d{2}):(\d{2})$", raw)
    start = int(m.group(1)) * 60 + int(m.group(2))
    end = int(m.group(3)) * 60 + int(m.group(4))
    start = max(0, min(start, 24 * 60))
    end = max(0, min(end, 24 * 60))
    return start, end


def in_human_hours(now_local=None):
    start, end = human_hours()
    if start == end:
        return True
    now_local = now_local or _now_local()
    minute = now_local.hour * 60 + now_local.minute
    if start < end:
        return start <= minute < end
    return minute >= start or minute < end          # overnight window


def slug(v):
    return re.sub(r"[^a-z0-9]+", "-", (v or "").lower()).strip("-")[:40]


def client_identity(va_name):
    """Twilio Client identity for a VA's browser. Falls back to the shared
    legacy identity when the feature is off or the name is blank."""
    s = slug(va_name)
    if not s or not inbound_enabled():
        return LEGACY_IDENTITY
    return LEGACY_IDENTITY + "-" + s


def humans_online():
    """Names of VAs with an open shift (ignores shifts stale past the
    auto-close limit so a forgotten clock-out doesn't ring a ghost)."""
    try:
        from va_time import MAX_SHIFT_HOURS
    except Exception:  # pragma: no cover
        MAX_SHIFT_HOURS = 12
    cutoff = _now_utc_naive() - timedelta(hours=MAX_SHIFT_HOURS)
    names, seen = [], set()
    for sh in (VaShift.query.filter(VaShift.ended_at.is_(None), VaShift.started_at >= cutoff)
               .order_by(VaShift.started_at.asc()).all()):
        key = (sh.va_name or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            names.append(sh.va_name.strip())
    return names


def ring_identities():
    """Every browser identity to ring: one per clocked-in VA plus the legacy
    shared 'desk' so an un-clocked desk still rings."""
    out = []
    for name in humans_online():
        ident = client_identity(name)
        if ident not in out:
            out.append(ident)
    if LEGACY_IDENTITY not in out:
        out.append(LEGACY_IDENTITY)
    return out


# ---------------------------------------------------------------------------
# Caller identification
# ---------------------------------------------------------------------------
def find_customer(digits):
    """User row whose phone matches these 10 digits in any formatting."""
    if len(digits) != 10:
        return None
    exact = User.query.filter(User.phone.in_([digits, "+1" + digits, "1" + digits])).first()
    if exact:
        return exact
    best = None
    for u in (User.query.filter(User.phone.isnot(None))
              .filter(User.phone.like("%{}%".format(digits[-4:]))).limit(300)):
        if _digits(u.phone) == digits:
            if u.role == "customer":
                return u
            best = best or u
    return best


def customer_summary(user):
    jobs = (Job.query.filter_by(customer_id=user.id)
            .order_by(Job.created_at.desc()).limit(50).all())
    real = [j for j in jobs if not (j.notes or "").upper().startswith("SYNTHETIC")]
    last = real[0] if real else None
    return {
        "id": user.id,
        "name": user.name or "",
        "phone": user.phone,
        "email": user.email,
        "role": user.role,
        "prior_jobs": len([j for j in real if j.status != "cancelled"]),
        "last_job": ({
            "id": last.id, "code": last.confirmation_code, "status": last.status,
            "address": last.address, "total_price": last.total_price,
            "scheduled_human": fmt_local(last.scheduled_at, "%a %b %-d, %-I:%M %p", "TBD"),
            "created_at": last.created_at.isoformat() if last.created_at else None,
        } if last else None),
    }


def prospect_summary(p):
    return {"id": p.id, "company": p.company, "city": p.city, "contact_name": p.contact_name,
            "status": p.status, "tier": p.tier, "category": p.category}


def classify_caller(digits):
    """→ (kind, customer_user_or_None, prospect_or_None)."""
    prospect = None
    try:
        from desk_line import match_prospect
        prospect = match_prospect(digits)
    except Exception:
        logger.exception("prospect match failed")
    customer = find_customer(digits)
    if customer:
        return "customer", customer, prospect
    if prospect:
        return "prospect", None, prospect
    return "unknown", None, None


# ---------------------------------------------------------------------------
# InboundCall bookkeeping
# ---------------------------------------------------------------------------
def record_call(call_sid, digits, kind, **fields):
    """Create (or refresh) the InboundCall for this CallSid. Commits."""
    row = InboundCall.query.filter_by(call_sid=call_sid).first() if call_sid else None
    if row is None:
        row = InboundCall(call_sid=call_sid or None, phone_digits=digits or "0000000000", kind=kind)
        db.session.add(row)
    for k, v in fields.items():
        setattr(row, k, v)
    db.session.commit()
    return row


def touch_call(call_sid, **fields):
    if not call_sid:
        return None
    row = InboundCall.query.filter_by(call_sid=call_sid).first()
    if row is None:
        return None
    for k, v in fields.items():
        setattr(row, k, v)
    db.session.commit()
    return row


def latest_call_for(digits, within_hours=2):
    since = _now_utc_naive() - timedelta(hours=within_hours)
    return (InboundCall.query.filter(InboundCall.phone_digits == digits,
                                     InboundCall.created_at >= since)
            .order_by(InboundCall.created_at.desc()).first())


def _resolve_call(data, digits):
    """The InboundCall an intake action belongs to: by CallSid when the
    desk knows it, else the latest recent call from this number."""
    sid = (data.get("call_sid") or "").strip()[:64]
    row = InboundCall.query.filter_by(call_sid=sid).first() if sid else None
    return row or latest_call_for(digits)


def _mark_activity(digits, call_sid, note):
    """Annotate the desk-line activity for this call so the thread shows
    what happened, and clear its unread state."""
    act = None
    if call_sid:
        act = DeskActivity.query.filter_by(twilio_sid=call_sid, kind="call").first()
    if act is None:
        since = _now_utc_naive() - timedelta(hours=2)
        act = (DeskActivity.query.filter(DeskActivity.phone_digits == digits,
                                         DeskActivity.kind == "call",
                                         DeskActivity.direction == "in",
                                         DeskActivity.created_at >= since)
               .order_by(DeskActivity.created_at.desc()).first())
    if act is not None:
        act.body = (act.body + " · " if act.body else "") + note[:400]
        act.read_at = act.read_at or _now_utc_naive()
        db.session.commit()
    return act


# ---------------------------------------------------------------------------
# TwiML pieces used by desk_line (kept here so the line file stays thin)
# ---------------------------------------------------------------------------
def voicemail_twiml(resp, base_url):
    resp.say("You've reached Umuve. Leave your name, number, and what you need, "
             "and we'll call you right back.", voice="Polly.Joanna")
    resp.record(max_length=120, play_beep=True, transcribe=True,
                transcribe_callback=base_url + "/api/desk/twilio/voice/transcript",
                action=base_url + "/api/desk/twilio/voice/vm-done")
    resp.hangup()
    return resp


def maya_twiml(resp, base_url):
    resp.say("Connecting you to our booking line.", voice="Polly.Joanna")
    dial = resp.dial(timeout=MAYA_RING_SECONDS, action=base_url + "/api/desk/twilio/voice/after-maya")
    dial.number(maya_number())
    return resp


# ---------------------------------------------------------------------------
# Quotes + items
# ---------------------------------------------------------------------------
def clean_items(raw):
    """[{category, quantity, size?}] with the junk stripped. Raises ValueError."""
    if not isinstance(raw, list) or not raw:
        raise ValueError("Add at least one item.")
    if len(raw) > MAX_ITEMS:
        raise ValueError("That's more line items than one job can hold.")
    items = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        cat = re.sub(r"[^a-z0-9_]", "", str(entry.get("category") or "").lower().replace(" ", "_"))[:40]
        if not cat:
            continue
        try:
            qty = int(entry.get("quantity") or 1)
        except (TypeError, ValueError):
            raise ValueError("Quantities must be whole numbers.")
        if qty <= 0:
            continue
        if qty > MAX_QTY:
            raise ValueError("Quantity over {} — double-check it.".format(MAX_QTY))
        item = {"category": cat, "quantity": qty}
        size = re.sub(r"[^a-z0-9_]", "", str(entry.get("size") or "").lower())[:20]
        if size and size != "default":
            item["size"] = size
        items.append(item)
    if not items:
        raise ValueError("Add at least one item.")
    return items


def items_text(items):
    parts = []
    for it in items:
        label = it["category"].replace("_", " ")
        if it.get("size"):
            label += " ({})".format(it["size"])
        parts.append("{}x {}".format(it["quantity"], label))
    return ", ".join(parts)


def quote_for(items, date_str=None):
    from routes.booking import calculate_estimate
    est = calculate_estimate(items, scheduled_date=date_str or None)
    return {
        "total": round(float(est["total"]), 2),
        "items_subtotal": est["items_subtotal"],
        "items": est["items"],
        "volume_discount": est["volume_discount"],
        "volume_discount_label": est.get("volume_discount_label"),
        "surge_amount": est["surge_amount"],
        "surge_reasons": est.get("surge_reasons") or [],
        "service_fee": est["service_fee"],
        "recycling_fees": est.get("recycling_fees", 0.0),
        "base_price": est["base_price"],
        "minimum_applied": est["minimum_applied"],
        "minimum_job_price": est["minimum_job_price"],
        "estimated_duration": est.get("estimated_duration"),
        "truck_size": est.get("truck_size"),
        "total_quantity": est.get("total_quantity"),
        "items_text": items_text(items),
    }


def _frontend():
    return (_env("FRONTEND_URL") or "https://app.goumuve.com").rstrip("/")


def quote_text_body(items, total, va_name=None, name=None):
    hi = "Hi {}! ".format(name.split(" ")[0]) if name else ""
    who = " — {}, Umuve".format(va_name.split(" ")[0]) if va_name else " — Umuve"
    return ("{}Your Umuve quote: {} — ${:,.0f} all-in (pickup, labor, and disposal included). "
            "Reply to this text to lock in a time, or book online: {}/book?ref=desk{}"
            ).format(hi, items_text(items), total, _frontend(), who)


def _send_text(digits, body, va_name=None):
    """Desk-line text (falls back to the Umuve number). Returns sid or None."""
    from desk_line import send_desk_text
    return send_desk_text(digits, body, va_name=va_name)


# ---------------------------------------------------------------------------
# Booking — delegates to the dispatch desk's log-job so an inbound booking is
# the same job a hand-logged phone close is (customer match, pending job,
# Payment row, board visibility, confirmation text with the Stripe pay link).
# ---------------------------------------------------------------------------
def create_phone_job(payload):
    """→ (status_code, json_body) from /api/va/dispatch/log-job's view."""
    from flask import current_app
    from va_dispatch import dispatch_log_job
    body = dict(payload)
    body["code"] = os.environ.get("TRIXIE_ASSISTANT_PASSCODE", "")
    with current_app.test_request_context("/api/va/dispatch/log-job", method="POST", json=body):
        result = dispatch_log_job()
    if isinstance(result, tuple):
        resp, status = result[0], result[1]
    else:
        resp, status = result, getattr(result, "status_code", 200)
    return status, (resp.get_json(silent=True) or {})


def _schedule_from(data):
    """(scheduled_local_iso, date_str, window_key, human) from the intake."""
    date_str = (data.get("date") or "").strip()[:10]
    window = (data.get("window") or "").strip()
    if not date_str:
        return None, None, None, "TBD — we'll confirm the time"
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Couldn't read the date — use the picker.")
    slot = WINDOWS.get(window, "09:00")
    human = "{} {}".format(datetime.strptime(date_str, "%Y-%m-%d").strftime("%a %b %-d"),
                           WINDOW_LABELS.get(window, "morning"))
    return "{}T{}".format(date_str, slot), date_str, (window if window in WINDOWS else None), human


# ---------------------------------------------------------------------------
# VA-facing endpoints
# ---------------------------------------------------------------------------
def _ident_or_401(data):
    ident = desk_identity(data)
    if not ident:
        return None, (jsonify({"error": "Sign in to the desk first."}), 401)
    return ident, None


@inbound_bp.route("/api/va/inbound/whois", methods=["POST"])
@_ratelimit
def inbound_whois():
    data = request.get_json(silent=True) or {}
    ident, err = _ident_or_401(data)
    if err:
        return err
    digits = _digits(data.get("phone"))
    if len(digits) != 10:
        return jsonify({"kind": "unknown", "phone": None, "customer": None, "prospect": None,
                        "call": None, "callback": None}), 200
    kind, customer, prospect = classify_caller(digits)
    call = latest_call_for(digits)
    cb = (CallbackRequest.query.filter_by(phone_digits=digits, status="open")
          .order_by(CallbackRequest.created_at.desc()).first())
    prior = (InboundCall.query.filter(InboundCall.phone_digits == digits)
             .order_by(InboundCall.created_at.desc()).limit(5).all())
    return jsonify({
        "kind": kind,
        "phone": _pretty(digits),
        "phone_digits": digits,
        "customer": customer_summary(customer) if customer else None,
        "prospect": prospect_summary(prospect) if prospect else None,
        "call": call.to_dict() if call else None,
        "callback": cb.to_dict() if cb else None,
        "recent_calls": [c.to_dict() for c in prior],
    }), 200


@inbound_bp.route("/api/va/inbound/quote", methods=["POST"])
@_ratelimit
def inbound_quote():
    data = request.get_json(silent=True) or {}
    ident, err = _ident_or_401(data)
    if err:
        return err
    try:
        items = clean_items(data.get("items"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    date_str = (data.get("date") or "").strip()[:10] or None
    q = quote_for(items, date_str)
    q["zip"] = re.sub(r"\D", "", str(data.get("zip") or ""))[:5] or None
    q["items_in"] = items
    return jsonify(q), 200


@inbound_bp.route("/api/va/inbound/quote-text", methods=["POST"])
@_ratelimit
def inbound_quote_text():
    data = request.get_json(silent=True) or {}
    ident, err = _ident_or_401(data)
    if err:
        return err
    digits = _digits(data.get("phone"))
    if len(digits) != 10:
        return jsonify({"error": "That doesn't look like a valid US number."}), 400
    try:
        items = clean_items(data.get("items"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    date_str = (data.get("date") or "").strip()[:10] or None
    q = quote_for(items, date_str)
    va_name = desk_va_name(data)
    name = (data.get("name") or "").strip()[:120]
    body = quote_text_body(items, q["total"], va_name, name)
    sid = _send_text(digits, body, va_name=va_name)

    call = _resolve_call(data, digits)
    kind = call.kind if call else classify_caller(digits)[0]
    note = "Quoted ${:,.2f}: {}".format(q["total"], q["items_text"])
    if call:
        touch_call(call.call_sid, outcome="quoted", quote_total=q["total"], va_name=va_name,
                   notes=((call.notes + "\n") if call.notes else "") + note)
    else:
        record_call(None, digits, kind, disposition="answered_by_human", outcome="quoted",
                    quote_total=q["total"], va_name=va_name, answered_by=va_name, notes=note)
    _mark_activity(digits, call.call_sid if call else None, note)
    audit("inbound_quote_text", "phone", digits[-4:],
          {"total": q["total"], "items": q["items_text"], "texted": bool(sid)})
    return jsonify({"ok": True, "texted": bool(sid), "sid": sid, "total": q["total"],
                    "body": body,
                    "message": ("Quote texted to {}.".format(_pretty(digits)) if sid else
                                "Quote saved, but the text didn't go through — read it to them.")}), 200


@inbound_bp.route("/api/va/inbound/book", methods=["POST"])
@_ratelimit
def inbound_book():
    data = request.get_json(silent=True) or {}
    ident, err = _ident_or_401(data)
    if err:
        return err
    va_name = desk_va_name(data)
    digits = _digits(data.get("phone"))
    if len(digits) != 10:
        return jsonify({"error": "Customer phone needs 10 digits."}), 400
    name = (data.get("name") or "").strip()[:120]
    address = (data.get("address") or "").strip()[:400]
    zip_code = re.sub(r"\D", "", str(data.get("zip") or ""))[:5]
    if not address:
        return jsonify({"error": "The job address is required."}), 400
    if zip_code and zip_code not in address:
        address = "{}, {}".format(address, zip_code)
    try:
        items = clean_items(data.get("items"))
        sched_iso, date_str, window, when_human = _schedule_from(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    q = quote_for(items, date_str)
    price = q["total"]
    override = None
    if data.get("price") not in (None, ""):
        try:
            override = round(float(data.get("price")), 2)
        except (TypeError, ValueError):
            return jsonify({"error": "Price must be a number."}), 400
        if not (0 < override < 20000):
            return jsonify({"error": "That price looks off — double-check it."}), 400
        price = override

    notes = (data.get("notes") or "").strip()[:500]
    note_lines = ["Booked on an inbound call to the desk line."]
    if window:
        note_lines.append("Arrival window: {}".format(WINDOW_LABELS[window]))
    if data.get("photo_quote"):
        note_lines.append("Customer will text photos for a firm quote.")
    if override is not None and abs(override - q["total"]) >= 0.01:
        note_lines.append("Price set by {} (engine quoted ${:,.2f}).".format(va_name or "the desk", q["total"]))
    if notes:
        note_lines.append(notes)

    status, body = create_phone_job({
        "va_name": va_name,
        "customer_name": name,
        "customer_phone": digits,          # log-job wants exactly 10 digits
        "customer_email": (data.get("email") or "").strip()[:254],
        "address": address,
        "items_text": q["items_text"],
        "notes": "\n".join(note_lines),
        "price": price,
        "scheduled_at": sched_iso or "",
        "send_confirmation": data.get("send_text", True),
    })
    if status != 200:
        return jsonify({"error": body.get("error") or "Couldn't create the job."}), status

    job = db.session.get(Job, (body.get("job") or {}).get("id") or "")
    if job is not None:
        # Structured pricing on the job: the engine breakdown, not just a
        # hand-typed total, so dispatch and payouts see the real shape.
        job.items = items
        job.item_total = q["items_subtotal"]
        job.base_price = q["base_price"] if override is None else price
        job.service_fee = q["service_fee"] if override is None else 0.0
        job.discount_amount = q["volume_discount"]
        job.surge_multiplier = 1.0
        db.session.commit()

    call = _resolve_call(data, digits)
    kind = call.kind if call else "customer"
    note = "Booked {} — ${:,.2f} {}".format(job.confirmation_code if job else "job", price, when_human)
    if call:
        touch_call(call.call_sid, outcome="booked", job_id=job.id if job else None, quote_total=price,
                   va_name=va_name, notes=((call.notes + "\n") if call.notes else "") + note)
    else:
        record_call(None, digits, kind, disposition="answered_by_human", outcome="booked",
                    job_id=job.id if job else None, quote_total=price, va_name=va_name,
                    answered_by=va_name, notes=note)
    _mark_activity(digits, call.call_sid if call else None, note)
    for cb in CallbackRequest.query.filter_by(phone_digits=digits, status="open").all():
        cb.status = "done"
        cb.closed_at = _now_utc_naive()
    db.session.commit()

    audit("inbound_book", "job", job.id if job else None,
          {"total": price, "engine_total": q["total"], "items": q["items_text"],
           "texted": bool(body.get("texted")), "window": window, "date": date_str,
           "phone_last4": digits[-4:]})
    return jsonify({"ok": True, "job": body.get("job"), "texted": bool(body.get("texted")),
                    "total": price, "message": body.get("message") or "Job created."}), 200


def _callback_when(raw):
    """Preset key or a 'YYYY-MM-DDTHH:MM' typed in Florida time → naive UTC."""
    raw = (raw or "").strip()
    now_local = _now_local()
    presets = {
        "tomorrow_am": (now_local + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0),
        "tomorrow_pm": (now_local + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0),
        "two_days": (now_local + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0),
        "next_week": (now_local + timedelta(days=7)).replace(hour=10, minute=0, second=0, microsecond=0),
        "hour": now_local + timedelta(hours=1),
    }
    if raw in presets:
        return presets[raw].astimezone(timezone.utc).replace(tzinfo=None)
    if not raw:
        return None
    try:
        naive = datetime.strptime(raw[:16], "%Y-%m-%dT%H:%M")
    except ValueError:
        raise ValueError("Couldn't read that time — use the picker.")
    return local_naive_to_utc(naive).replace(tzinfo=None)


@inbound_bp.route("/api/va/inbound/callback", methods=["POST"])
@_ratelimit
def inbound_callback():
    data = request.get_json(silent=True) or {}
    ident, err = _ident_or_401(data)
    if err:
        return err
    digits = _digits(data.get("phone"))
    if len(digits) != 10:
        return jsonify({"error": "That doesn't look like a valid US number."}), 400
    try:
        when = _callback_when(data.get("when"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    va_name = desk_va_name(data)
    name = (data.get("name") or "").strip()[:120]
    note = (data.get("note") or "").strip()[:500]
    call = _resolve_call(data, digits)
    cb = CallbackRequest(phone_digits=digits, name=name or None, call_sid=call.call_sid if call else None,
                         requested_for=when, note=note or None, va_name=va_name or None)
    db.session.add(cb)
    when_h = fmt_local(when, "%a %b %-d, %-I:%M %p", "when they're free") if when else "when they're free"
    preview = "CALLBACK {} — {}{}".format(when_h, name or _pretty(digits), (": " + note) if note else "")
    # The inbox entry: an unread inbound activity on the desk line so the
    # badge bumps and the thread shows the ask. kind='callback' keeps it out
    # of the call-status machinery (_finish_call filters kind='call').
    db.session.add(DeskActivity(prospect_id=None, phone_digits=digits, kind="callback", direction="in",
                                body=preview[:2000], status="open", va_name=va_name or None))
    db.session.commit()
    if call:
        touch_call(call.call_sid, outcome="callback", va_name=va_name,
                   notes=((call.notes + "\n") if call.notes else "") + preview)
    else:
        record_call(None, digits, classify_caller(digits)[0], disposition="answered_by_human",
                    outcome="callback", va_name=va_name, answered_by=va_name, notes=preview)
    _mark_activity(digits, call.call_sid if call else None, preview)
    audit("inbound_callback", "callback", cb.id, {"phone_last4": digits[-4:], "for": when_h})
    return jsonify({"ok": True, "callback": cb.to_dict(), "message": "Callback set for {}.".format(when_h)}), 200


@inbound_bp.route("/api/va/inbound/outcome", methods=["POST"])
@_ratelimit
def inbound_outcome():
    """Close an intake without a booking: not_fit | spam (also 'done' to
    close an open callback)."""
    data = request.get_json(silent=True) or {}
    ident, err = _ident_or_401(data)
    if err:
        return err
    digits = _digits(data.get("phone"))
    outcome = (data.get("outcome") or "").strip()
    if len(digits) != 10:
        return jsonify({"error": "That doesn't look like a valid US number."}), 400
    if outcome not in ("not_fit", "spam", "done"):
        return jsonify({"error": "Unknown outcome."}), 400
    va_name = desk_va_name(data)
    note = (data.get("note") or "").strip()[:500]
    label = {"not_fit": "Not a fit", "spam": "Spam", "done": "Handled"}[outcome]
    line = label + ((": " + note) if note else "")
    if outcome == "done":
        n = 0
        for cb in CallbackRequest.query.filter_by(phone_digits=digits, status="open").all():
            cb.status = "done"
            cb.closed_at = _now_utc_naive()
            n += 1
        for act in DeskActivity.query.filter_by(phone_digits=digits, read_at=None).all():
            act.read_at = _now_utc_naive()
        db.session.commit()
        audit("inbound_callback_done", "phone", digits[-4:], {"closed": n})
        return jsonify({"ok": True, "closed": n}), 200
    call = _resolve_call(data, digits)
    if call:
        touch_call(call.call_sid, outcome=outcome, va_name=va_name,
                   notes=((call.notes + "\n") if call.notes else "") + line)
    else:
        record_call(None, digits, classify_caller(digits)[0], disposition="answered_by_human",
                    outcome=outcome, va_name=va_name, answered_by=va_name, notes=line)
    _mark_activity(digits, call.call_sid if call else None, line)
    audit("inbound_" + outcome, "phone", digits[-4:], {"note": note} if note else None)
    return jsonify({"ok": True, "outcome": outcome}), 200


@inbound_bp.route("/api/va/inbound/recent", methods=["POST"])
@_ratelimit
def inbound_recent():
    """Recent customer/unknown calls + open callbacks — the desk decorates
    the inbox with these ("CUSTOMER · missed", "Call back now")."""
    data = request.get_json(silent=True) or {}
    ident, err = _ident_or_401(data)
    if err:
        return err
    try:
        days = max(1, min(int(data.get("days") or RECENT_DAYS), 30))
    except (TypeError, ValueError):
        days = RECENT_DAYS
    since = _now_utc_naive() - timedelta(days=days)
    rows = (InboundCall.query.filter(InboundCall.created_at >= since)
            .order_by(InboundCall.created_at.desc()).limit(200).all())
    open_cbs = (CallbackRequest.query.filter(CallbackRequest.status == "open")
                .order_by(CallbackRequest.created_at.desc()).limit(100).all())
    names = {}
    items = []
    for r in rows:
        if r.phone_digits not in names:
            u = find_customer(r.phone_digits)
            names[r.phone_digits] = (u.name or "") if u else ""
        d = r.to_dict()
        d["phone"] = _pretty(r.phone_digits)
        d["name"] = names[r.phone_digits]
        d["missed"] = r.disposition in ("to_maya", "voicemail", "missed") and r.outcome == "none"
        items.append(d)
    return jsonify({
        "calls": items,
        "callbacks": [dict(cb.to_dict(), phone=_pretty(cb.phone_digits),
                           requested_human=fmt_local(cb.requested_for, "%a %b %-d, %-I:%M %p", "any time"))
                      for cb in open_cbs],
        "humans_online": humans_online() if ident.get("role") in MANAGER_ROLES else len(humans_online()),
    }), 200


@inbound_bp.route("/api/va/inbound/stats", methods=["POST"])
@_ratelimit
@require_desk(MANAGER_ROLES)
def inbound_stats(ident=None):
    data = request.get_json(silent=True) or {}
    try:
        days = max(1, min(int(data.get("days") or 7), 90))
    except (TypeError, ValueError):
        days = 7
    since = _now_utc_naive() - timedelta(days=days)
    rows = InboundCall.query.filter(InboundCall.created_at >= since).all()
    counts = {"calls": 0, "answered_by_human": 0, "to_maya": 0, "voicemail": 0, "missed": 0,
              "booked": 0, "quoted": 0, "callback": 0, "not_fit": 0, "spam": 0}
    by_hour = {h: {"calls": 0, "answered": 0, "booked": 0} for h in range(24)}
    booked_ids = []
    for r in rows:
        counts["calls"] += 1
        if r.disposition in counts:
            counts[r.disposition] += 1
        if r.outcome in counts:
            counts[r.outcome] += 1
        if r.outcome == "booked" and r.job_id:
            booked_ids.append(r.job_id)
        hour = to_local(r.created_at).hour if r.created_at else 0
        by_hour[hour]["calls"] += 1
        if r.disposition == "answered_by_human":
            by_hour[hour]["answered"] += 1
        if r.outcome == "booked":
            by_hour[hour]["booked"] += 1
    revenue = 0.0
    if booked_ids:
        for j in Job.query.filter(Job.id.in_(booked_ids)).all():
            if j.status != "cancelled":
                revenue += float(j.total_price or 0)
    answered = counts["answered_by_human"]
    return jsonify({
        "days": days,
        "since": since.isoformat(),
        "counts": counts,
        "revenue_booked": round(revenue, 2),
        "answer_rate": round(answered / counts["calls"], 3) if counts["calls"] else None,
        "close_rate": round(counts["booked"] / answered, 3) if answered else None,
        "by_hour": [dict(hour=h, **by_hour[h]) for h in range(24)],
        "humans_online": humans_online(),
        "human_hours": _env("INBOUND_HUMAN_HOURS", DEFAULT_HOURS),
        "maya_number": maya_number(),
        "flags": {"inbound_customers": inbound_enabled(), "maya_fallback": maya_fallback_enabled()},
    }), 200


# ---------------------------------------------------------------------------
# Public: Maya's transfer check
# ---------------------------------------------------------------------------
@inbound_bp.route("/api/inbound/humans-online", methods=["GET"])
@_ratelimit
def inbound_humans_online():
    """No auth, no secrets: is a human on the desk right now? Vapi gives
    Maya a tool that reads this before offering to transfer a caller."""
    try:
        online = inbound_enabled() and in_human_hours()
        names = humans_online() if online else []
    except Exception:
        logger.exception("humans-online check failed")
        names, online = [], False
    return jsonify({"online": bool(online and names), "count": len(names) if online else 0,
                    "in_hours": in_human_hours()}), 200
