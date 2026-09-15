"""Thumbtack → the desk, in seconds.

Thumbtack lets a pro point lead / message / review webhooks at their own
tools (its "custom lead integration"), and its partner API posts the same
shapes. Replying *inside* Thumbtack needs their approval-gated partner
OAuth, but every lead carries the customer's phone — so the desk line texts
them at once, in the VA's name, and the lead lands in the desk's lead list
where the speed-to-lead and follow-up machinery already lives.

    POST /api/webhooks/thumbtack/lead          new lead (also accepts /  and infers)
    POST /api/webhooks/thumbtack/message       customer message on a lead
    PUT  /api/webhooks/thumbtack/lead/update   lead price / status change
    POST /api/webhooks/thumbtack/review        a review landed
    GET  /api/admin/thumbtack/events           last 50 raw payloads + recent leads (admin)

Auth: HTTP Basic with THUMBTACK_WEBHOOK_USER / THUMBTACK_WEBHOOK_PASSWORD —
the same pair typed into Thumbtack's webhook settings (or a Zapier step).
Unset → 503, never open. Payload parsing is deliberately tolerant: the field
names come from Thumbtack's reference and can drift, so every payload is
kept raw for an admin to read and the parser is adjusted from real data.
"""
from __future__ import annotations

import base64
import hmac
import logging
import os
import re
from collections import deque
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from models import db, generate_uuid
from models_thumbtack import ThumbtackLead

logger = logging.getLogger(__name__)
thumbtack_bp = Blueprint("thumbtack", __name__, url_prefix="/api/webhooks/thumbtack")

RECENT_EVENTS = deque(maxlen=50)
SOURCE = "thumbtack"


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _env(name):
    return (os.environ.get(name) or "").strip()


# ---------------------------------------------------------------------------
# auth
# ---------------------------------------------------------------------------
def _authorized():
    user, pw = _env("THUMBTACK_WEBHOOK_USER"), _env("THUMBTACK_WEBHOOK_PASSWORD")
    if not user or not pw:
        return None                                   # not configured → fail closed
    header = request.headers.get("Authorization", "")
    if header.startswith("Basic "):
        try:
            raw = base64.b64decode(header[6:].strip()).decode("utf-8", "replace")
        except Exception:
            raw = ""
        u, _, p = raw.partition(":")
        return hmac.compare_digest(u, user) and hmac.compare_digest(p, pw)
    secret = request.headers.get("X-Thumbtack-Secret", "") or request.args.get("key", "")
    return bool(secret) and hmac.compare_digest(secret, pw)


REJECTED = deque(maxlen=25)


def _note_rejected(why):
    """A refused call used to vanish, so "Thumbtack never called us" and "we
    turned Thumbtack away" looked identical while someone waited on a test."""
    try:
        REJECTED.appendleft({
            "at": _now().isoformat() + "Z", "why": why,
            "path": request.path, "method": request.method,
            "from": (request.headers.get("X-Forwarded-For") or request.remote_addr or "")[:60],
            "agent": (request.headers.get("User-Agent") or "")[:120],
            "had_auth": bool(request.headers.get("Authorization")
                             or request.headers.get("X-Thumbtack-Secret")
                             or request.args.get("key")),
            # header NAMES only — never the values, which may be secrets. Enough
            # to see whether they sign requests some other way.
            "headers": sorted(k for k in request.headers.keys()
                              if k.lower() not in ("cookie", "authorization")),
        })
    except Exception:
        pass


def _gate():
    ok = _authorized()
    if ok is None:
        _note_rejected("not configured — THUMBTACK_WEBHOOK_USER/PASSWORD unset on this service")
        return jsonify(error="Thumbtack webhook is not configured on this server."), 503
    if not ok:
        _note_rejected("bad or missing credentials")
        return jsonify(error="Unauthorized"), 401
    return None


# ---------------------------------------------------------------------------
# tolerant payload reading
# ---------------------------------------------------------------------------
def _dig(obj, *paths, default=None):
    """First non-empty value at any dotted path, e.g. 'customer.phone'."""
    for path in paths:
        cur = obj
        for key in path.split("."):
            if isinstance(cur, dict):
                cur = cur.get(key)
            else:
                cur = None
                break
        if cur not in (None, "", [], {}):
            return cur
    return default


def _digits(v):
    d = "".join(ch for ch in str(v or "") if ch.isdigit())
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return d if len(d) == 10 else ""


def _pretty(digits):
    return "({}) {}-{}".format(digits[:3], digits[3:6], digits[6:]) if len(digits) == 10 else ""


def _text(v, limit=2000):
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        import json
        v = json.dumps(v)
    return str(v).strip()[:limit] or None


def unwrap(p):
    """Thumbtack wraps everything: {"event": {...}, "data": {...}}.

    Returns (body, event_type). Falls back to the flat payload so a Zapier
    relay or a hand-made test still parses.
    """
    if not isinstance(p, dict):
        return {}, ""
    ev = p.get("event") if isinstance(p.get("event"), dict) else {}
    body = p.get("data") if isinstance(p.get("data"), dict) else p
    return body, str(ev.get("eventType") or p.get("eventType") or "")


def _money(v):
    """'$25.00' → 25.0. Their prices are display strings, not numbers."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    txt = re.sub(r"[^0-9.\-]", "", str(v))
    try:
        return float(txt) if txt not in ("", "-", ".") else None
    except Exception:
        return None


def is_test(p):
    """Thumbtack's own webhook test. Store it, alert on it, never text it."""
    body, ev = unwrap(p)
    name = str(_dig(body, "business.name") or "").lower()
    cust = "{} {}".format(_dig(body, "customer.firstName") or "",
                          _dig(body, "customer.lastName") or "").strip().lower()
    return name.startswith("test business") or cust == "test customer" or "test" in ev.lower()


def parse_lead(p):
    """Thumbtack's NegotiationCreated payload → our columns.

    Built from a real payload (15 Sep), not the published example: the body is
    under `data`, the lead id is `negotiationID`, the customer's name is split
    across firstName/lastName, category is an object, and prices are strings
    like "$25.00". Flat fallbacks are kept so an older shape still parses.
    """
    body, _ev = unwrap(p)
    req = body.get("request") if isinstance(body.get("request"), dict) else {}
    cust = body.get("customer") if isinstance(body.get("customer"), dict) else {}
    loc = _dig(req, "location", "address", default={}) or {}
    if not isinstance(loc, dict):
        loc = {}

    phone = _dig(cust, "phone", "phoneNumber") or _dig(body, "phone", "phoneNumber", "customerPhone")
    digits = _digits(phone)

    name = " ".join(x for x in [_dig(cust, "firstName"), _dig(cust, "lastName")] if x).strip()
    if not name:
        name = _dig(cust, "name", "displayName") or _dig(body, "customerName", "name")

    category = _dig(req, "category.name") or _dig(req, "category", "categoryName") \
        or _dig(body, "category.name", "category", "categoryName")
    if isinstance(category, dict):
        category = category.get("name")

    # proposedTimes is when they want it; fall back to a schedule string
    sched = None
    times = _dig(req, "proposedTimes", default=None)
    if isinstance(times, list) and times:
        first = times[0] if isinstance(times[0], dict) else {}
        start, end = first.get("start"), first.get("end")
        sched = " to ".join(x for x in [start, end] if x) or None
    if not sched:
        sched = _dig(req, "schedule") or _dig(body, "schedule")
        if isinstance(sched, dict):
            sched = " ".join(str(v) for v in sched.values() if v)

    details = _dig(req, "details", default=None) or _dig(body, "details")
    if isinstance(details, dict):
        details = [{"question": k, "answer": v} for k, v in details.items()]

    attachments = _dig(req, "attachments", default=None) or _dig(body, "attachments") or []
    if not isinstance(attachments, list):
        attachments = []

    address_bits = [_dig(loc, "address1", "line1", "street"), _dig(loc, "address2", "line2")]
    return {
        "lead_id": _text(_dig(body, "negotiationID", "negotiationId", "leadID", "leadId",
                              "lead_id", "id"), 80),
        "business_id": _text(_dig(body, "business.businessID", "business.id", "businessID",
                                  "businessId"), 80),
        "lead_type": _text(_dig(body, "status", "leadType", "lead_type", "type"), 40),
        "lead_price": _money(_dig(body, "leadPrice", "lead_price", "price")),
        "customer_id": _text(_dig(cust, "customerID", "customerId", "id")
                             or _dig(body, "customerID"), 80),
        "customer_name": _text(name, 160),
        "phone": _pretty(digits) or _text(phone, 40),
        "phone_digits": digits or None,
        "email": _text(_dig(cust, "email") or _dig(body, "email"), 254),
        "address": _text(", ".join(str(b) for b in address_bits if b), 500),
        "city": _text(_dig(loc, "city") or _dig(body, "city"), 80),
        "state": _text(_dig(loc, "state") or _dig(body, "state"), 8),
        "zip": _text(_dig(loc, "zipCode", "zip", "postalCode") or _dig(body, "zipCode", "zip"), 12),
        "category": _text(category, 120),
        "title": _text(_dig(req, "title") or category or _dig(body, "title"), 200),
        "description": _text(_dig(req, "description") or _dig(body, "description", "message")),
        "schedule": _text(sched, 300),
        "details": details if isinstance(details, list) else None,
        "attachments": [{"url": a.get("url"), "fileName": a.get("fileName") or a.get("name"),
                         "mimeType": a.get("mimeType")}
                        for a in attachments if isinstance(a, dict)] or None,
    }


def _num(v):
    try:
        return float(v) if v not in (None, "") else None
    except Exception:
        return None


def parse_message(p):
    """A MessageCreatedV4 body. Note what is NOT here: no phone, no address, no
    category. A message-only lead can be answered inside Thumbtack and nowhere
    else, which is why the lead webhook matters (15 Sep)."""
    body, _ev = unwrap(p)
    return {
        "customer_name": _text(_dig(body, "customer.displayName", "customer.firstName",
                                    "customer.name"), 160),
        "customer_id": _text(_dig(body, "customer.customerID", "customer.customerId"), 80),
        "lead_id": _text(_dig(body, "negotiationID", "negotiationId", "leadID", "leadId", "lead_id"), 80),
        "message_id": _text(_dig(body, "messageID", "messageId", "message.messageID", "id"), 80),
        "text": _text(_dig(body, "message.text", "text", "message", "body")),
        "from": _text(_dig(body, "message.sender", "sender", "from", "author"), 40) or "customer",
        "at": _text(_dig(body, "createdAt", "createTimestamp", "timestamp"), 40),
        "attachments": _dig(body, "message.attachments", "attachments", default=[]) or [],
    }


# ---------------------------------------------------------------------------
# is this a lead we can actually do?
# ---------------------------------------------------------------------------
# Thumbtack charges for a lead whether or not we can serve it. We cannot
# decline through their API (that needs the approval-gated partner platform),
# so the value here is: don't waste Tracy's time or text a stranger about work
# we can't do, and total up what the un-doable ones cost so their targeting
# settings can be fixed by hand.
DECLINE_WORDS = tuple(w.strip().lower() for w in (os.environ.get(
    "THUMBTACK_DECLINE_CATEGORIES",
    "lawn,landscap,mow,tree service,pest,clean,maid,handyman,plumb,electric,roof,paint,"
    "pressure wash,pool service,carpet,window,move out clean,hvac,air condition"
) or "").split(",") if w.strip())
ACCEPT_WORDS = tuple(w.strip().lower() for w in (os.environ.get(
    "THUMBTACK_ACCEPT_CATEGORIES",
    "junk,haul,debris,demo,dumpster,clean out,cleanout,removal,disposal,garbage,trash,"
    "furniture,appliance,mattress,estate,foreclosure,property clean"
) or "").split(",") if w.strip())


def classify(lead):
    """Sets serviceable / service_note / lat / lng / county. Never raises.

    Category first (a lawn-care lead is wrong however close it is), then the
    service area. Unknown location is treated as serviceable — better a wasted
    text than a dropped customer.
    """
    try:
        # The category Thumbtack assigns is authoritative: a lawn-care lead is
        # the wrong job even when the customer happens to mention a mattress.
        cat = " ".join(x for x in [lead.category, lead.title] if x).lower()
        blob = " ".join(x for x in [lead.category, lead.title, lead.description] if x).lower()
        if cat and any(w in cat for w in DECLINE_WORDS) and not any(w in cat for w in ACCEPT_WORDS):
            lead.serviceable = False
            lead.service_note = "not junk removal: {}".format((lead.category or "?")[:60])
            return lead.serviceable
        if cat and not any(w in blob for w in ACCEPT_WORDS) and any(w in blob for w in DECLINE_WORDS):
            lead.serviceable = False
            lead.service_note = "not junk removal: {}".format((lead.category or "?")[:60])
            return lead.serviceable
        where = ", ".join(x for x in [lead.address, lead.city, lead.state] if x) or lead.zip
        pt = None
        if where:
            try:
                from sameday import geocode
                pt = geocode(where)
            except Exception:
                logger.exception("thumbtack: geocode failed")
        if pt:
            lead.lat, lead.lng = float(pt[0]), float(pt[1])
            try:
                from dump_suggest import county_for, COUNTY_LABEL
                lead.county = COUNTY_LABEL.get(county_for(lead.lat), None)
            except Exception:
                pass
            try:
                from geofencing import is_in_service_area
                if not is_in_service_area(lead.lat, lead.lng):
                    lead.serviceable = False
                    lead.service_note = "outside the service area: {}".format(
                        ", ".join(x for x in [lead.city, lead.state, lead.zip] if x)[:80])
                    return lead.serviceable
            except Exception:
                logger.exception("thumbtack: service-area check failed")
        lead.serviceable = True
        lead.service_note = None
        return True
    except Exception:
        logger.exception("thumbtack: classify failed for %s", getattr(lead, "id", "?"))
        return None


# ---------------------------------------------------------------------------
# the desk side: text the customer, tell the team, join the lead list
# ---------------------------------------------------------------------------
def _va_name():
    return (_env("DESK_VA_NAME") or "Tracy").split()[0]


def first_text(lead):
    first = (lead.customer_name or "").split()[0] if lead.customer_name else "there"
    what = lead.category or lead.title or "junk removal"
    where = " in {}".format(lead.city) if lead.city else ""
    try:
        from inbound import humans_online
        live = bool(humans_online())
    except Exception:
        live = False
    line = ("Calling you in a few minutes — if now's bad, reply with a good time. " if live
            else "I'll call when we open, but I can price it now: ")
    return ("Hi {}, this is {} with Umuve — I saw your Thumbtack request for {}{}. {}"
            "Text a photo of the pile to this number and I'll send a firm price within minutes. "
            "Reply STOP to opt out.").format(first, _va_name(), what.lower(), where, line)


def _own_number(digits):
    try:
        from leads import own_numbers
        return digits in own_numbers()
    except Exception:
        return False


def text_customer(lead):
    """One text, now, in the VA's name — same kill switch as the speed-to-lead sweep."""
    try:
        from flags import flag
        if not flag("lead_auto_text"):
            return False
    except Exception:
        pass
    if not lead.phone_digits or _own_number(lead.phone_digits) or lead.text_sent_at:
        return False
    try:
        from desk_line import send_desk_text
        sid = send_desk_text("+1" + lead.phone_digits, first_text(lead), va_name=_va_name(), log=True)
    except Exception:
        logger.exception("thumbtack first text failed for lead %s", lead.id)
        return False
    if not sid:
        return False
    lead.text_sent_at = _now()
    lead.status = "replied"
    try:
        from leads import _touch_row
        row = _touch_row(SOURCE, lead.id, phone=lead.phone_digits, source=SOURCE)
        if row is not None:
            row.auto_text_at = _now()
    except Exception:
        logger.exception("thumbtack lead touch failed for %s", lead.id)
    db.session.commit()
    return True


def alert_team(lead, kind="lead", extra=None):
    """Email + Slack. Never a text — an inbound lead is not worth a per-message
    charge, and these arrive all day (sevs, 15 Sep)."""
    head = {"lead": "Thumbtack lead", "message": "Thumbtack message",
            "review": "Thumbtack review"}.get(kind, "Thumbtack")
    if lead is not None and lead.customer_name:
        head += " · " + lead.customer_name
    lines = []
    if lead is not None:
        lines.append(" · ".join(x for x in [lead.category or lead.title, lead.city] if x))
        if lead.phone:
            lines.append("Phone {}{}".format(lead.phone, " · texted" if lead.text_sent_at else " · NOT texted"))
        if lead.lead_price:
            lines.append("Thumbtack charged ${:.2f} for this lead".format(lead.lead_price))
        if lead.description:
            lines.append(lead.description[:300])
        if lead.schedule:
            lines.append("Wants: " + lead.schedule)
        if lead.attachments:
            lines.append("{} photo(s) attached".format(len(lead.attachments)))
    if extra:
        lines.append(str(extra)[:300])
    lines.append("Desk: {}/va/calls".format(_env("DESK_PUBLIC_URL") or "https://ops.goumuve.com"))
    try:
        from booking_alerts import ops_alert
        ops_alert(head, "\n".join(l for l in lines if l))
    except Exception:
        logger.exception("thumbtack alert failed")


def desk_leads(since):
    """Rows for leads.collect(): every Thumbtack lead in the window, one shape."""
    from leads import _lead
    out = []
    for r in (ThumbtackLead.query
              .filter(ThumbtackLead.created_at >= since,
                      ThumbtackLead.status.notin_(("test", "not_serviceable")))
              .order_by(ThumbtackLead.created_at.desc()).limit(200).all()):
        what = " · ".join(x for x in [r.category or r.title, r.description[:80] if r.description else None] if x)
        if r.status == "message_only":
            what = "REPLY IN THUMBTACK · " + (r.description or "")[:90]
        if r.messages:
            last = r.messages[-1].get("text") if isinstance(r.messages[-1], dict) else None
            if last:
                what = (what + " · " if what else "") + "they said: " + last[:80]
        out.append(_lead(SOURCE, r.id, phone=r.phone_digits or r.phone, name=r.customer_name,
                         what=what or "Thumbtack request", source=SOURCE, created_at=r.created_at,
                         extra={"email": r.email, "address": ", ".join(x for x in [r.address, r.city, r.zip] if x) or None,
                                "lead_id": r.lead_id, "photos": len(r.attachments or []),
                                "lead_price": r.lead_price, "thumbtack_status": r.status}))
    return out


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------
def _record(kind, payload):
    RECENT_EVENTS.appendleft({"at": _now().isoformat() + "Z", "kind": kind, "payload": payload})


def _payload():
    p = request.get_json(silent=True)
    if not isinstance(p, dict):
        form = request.form.to_dict() if request.form else {}
        p = form or {}
    return p


def _infer_kind(p):
    """Thumbtack declares it: event.eventType is "NegotiationCreatedV4" and so on."""
    _body, ev = unwrap(p)
    e = ev.lower()
    if "review" in e:
        return "review"
    if "message" in e:
        return "message"
    if "negotiation" in e or "lead" in e:
        return "lead"
    if "review" in p or "rating" in p:
        return "review"
    if "message" in p:
        return "message"
    return "lead"


def handle_lead(p):
    data = parse_lead(p)
    existing = ThumbtackLead.query.filter_by(lead_id=data["lead_id"]).first() if data["lead_id"] else None
    if existing:
        return existing, False
    lead = ThumbtackLead(id=generate_uuid(), raw=p, **data)
    db.session.add(lead)
    db.session.commit()
    classify(lead)
    db.session.commit()

    if is_test(p):
        lead.status = "test"
        db.session.commit()
        alert_team(lead, "lead")
        logger.info("thumbtack TEST payload stored (%s) — no text sent", lead.id)
        return lead, True
    if lead.serviceable is False:
        # we cannot do this job: no text to the customer, and it is logged as
        # money spent on a lead their targeting should never have sent us
        lead.status = "not_serviceable"
        db.session.commit()
        alert_team(lead, "lead", extra="NOT SERVICEABLE — {} (${:.2f} charged)".format(
            lead.service_note or "", lead.lead_price or 0))
        logger.info("thumbtack lead %s not serviceable: %s", lead.id, lead.service_note)
        return lead, True
    texted = text_customer(lead)
    alert_team(lead, "lead")
    logger.info("thumbtack lead %s (%s, %s) texted=%s", lead.id, lead.customer_name, lead.city, texted)
    return lead, True


def handle_message(p):
    m = parse_message(p)
    lead = ThumbtackLead.query.filter_by(lead_id=m["lead_id"]).first() if m["lead_id"] else None
    if lead is None:
        # A message for a negotiation we never got a lead webhook for. We have a
        # name and their words and NO phone number — the only way to answer is
        # inside Thumbtack, so say that loudly rather than filing a blank row.
        lead = ThumbtackLead(id=generate_uuid(), lead_id=m["lead_id"], raw=p,
                             description=m["text"],
                             customer_name=m.get("customer_name"),
                             customer_id=m.get("customer_id"),
                             category="Message on Thumbtack",
                             status="message_only", serviceable=True,
                             service_note="no phone on a message event — reply in the Thumbtack app")
        db.session.add(lead)
    msgs = list(lead.messages or [])
    if m["message_id"] and any(x.get("id") == m["message_id"] for x in msgs if isinstance(x, dict)):
        return lead, False
    msgs.append({"id": m["message_id"], "at": m["at"] or _now().isoformat() + "Z", "from": m["from"], "text": m["text"],
                 "attachments": [a.get("url") if isinstance(a, dict) else str(a) for a in (m["attachments"] or [])]})
    lead.messages = msgs
    lead.updated_at = _now()
    db.session.commit()
    if (m["from"] or "").lower() not in ("pro", "business", "umuve"):
        try:
            from leads import _touch_row
            row = _touch_row(SOURCE, lead.id, phone=lead.phone_digits, source=SOURCE)
            if row is not None and row.outcome not in ("booked", "spam", "not_a_fit"):
                row.touched_at = None          # a new customer message re-opens the clock
                db.session.commit()
        except Exception:
            logger.exception("thumbtack message touch failed")
        alert_team(lead, "message", extra=m["text"])
    return lead, True


@thumbtack_bp.route("", methods=["POST"])
@thumbtack_bp.route("/", methods=["POST"])
@thumbtack_bp.route("/lead", methods=["POST"])
def api_lead():
    err = _gate()
    if err:
        return err
    p = _payload()
    kind = "lead" if request.path.rstrip("/").endswith("/lead") else _infer_kind(p)
    _record(kind, p)
    try:
        if kind == "message":
            lead, created = handle_message(p)
        elif kind == "review":
            row, created = handle_review(p)
            if row is not None and created:
                stars = "{:.0f}★ ".format(row.rating) if row.rating else ""
                alert_team(None, "review", extra="{}{}{}".format(
                    stars, (row.reviewer + ": ") if row.reviewer else "", row.text or "no comment"))
            return jsonify(ok=True, kind="review", created=bool(created)), 200
        else:
            lead, created = handle_lead(p)
        return jsonify(ok=True, kind=kind, id=lead.id, created=created), 200
    except Exception:
        logger.exception("thumbtack %s webhook failed", kind)
        db.session.rollback()
        return jsonify(ok=False, kind=kind, error="stored raw; parsing failed"), 200   # keep Thumbtack from retrying forever


@thumbtack_bp.route("/message", methods=["POST"])
def api_message():
    err = _gate()
    if err:
        return err
    p = _payload()
    _record("message", p)
    try:
        lead, created = handle_message(p)
        return jsonify(ok=True, kind="message", id=lead.id, created=created), 200
    except Exception:
        logger.exception("thumbtack message webhook failed")
        db.session.rollback()
        return jsonify(ok=False, kind="message", error="stored raw; parsing failed"), 200


@thumbtack_bp.route("/lead/update", methods=["PUT", "POST"])
def api_lead_update():
    err = _gate()
    if err:
        return err
    p = _payload()
    _record("lead_update", p)
    lead_id = _text(_dig(p, "leadID", "leadId", "lead_id", "negotiationID"), 80)
    lead = ThumbtackLead.query.filter_by(lead_id=lead_id).first() if lead_id else None
    if lead:
        price = _num(_dig(p, "leadPrice", "price"))
        if price is not None:
            lead.lead_price = price
        st = _text(_dig(p, "status", "leadStatus"), 24)
        if st:
            lead.status = st.lower()[:24]
        db.session.commit()
    return jsonify(ok=True, kind="lead_update", found=bool(lead)), 200


def handle_review(p):
    """Store it. While the Google profile is unclaimed these are the only
    public proof we're accumulating, so they must not live in an alert only."""
    from models_thumbtack import ThumbtackReview
    body, _ev = unwrap(p)
    rid = _text(_dig(body, "review.reviewID", "review.id", "reviewID", "reviewId", "id"), 80)
    if rid and ThumbtackReview.query.filter_by(review_id=rid).first():
        return None, False
    rating = _dig(body, "review.rating", "rating", "starRating")
    try:
        rating = float(rating) if rating is not None else None
    except Exception:
        rating = None
    who = " ".join(x for x in [_dig(body, "customer.firstName", "reviewer.firstName"),
                               _dig(body, "customer.lastName", "reviewer.lastName")] if x).strip()
    row = ThumbtackReview(
        id=generate_uuid(), review_id=rid,
        lead_id=_text(_dig(body, "negotiationID", "leadID"), 80),
        rating=rating,
        text=_text(_dig(body, "review.text", "review.comment", "text", "comment"), 2000),
        reviewer=_text(who or _dig(body, "customer.name", "reviewer"), 120),
        raw=p)
    db.session.add(row)
    db.session.commit()
    return row, True


@thumbtack_bp.route("/review", methods=["POST"])
def api_review():
    err = _gate()
    if err:
        return err
    p = _payload()
    _record("review", p)
    try:
        row, created = handle_review(p)
    except Exception:
        logger.exception("thumbtack review webhook failed")
        db.session.rollback()
        return jsonify(ok=False, kind="review", error="stored raw; parsing failed"), 200
    if row is not None and created:
        stars = "{:.0f}★ ".format(row.rating) if row.rating else ""
        alert_team(None, "review", extra="{}{}{}".format(
            stars, (row.reviewer + ": ") if row.reviewer else "", row.text or "no comment"))
    return jsonify(ok=True, kind="review", created=bool(created)), 200


# ---------------------------------------------------------------------------
# what it costs, what it returns, where the demand is
# ---------------------------------------------------------------------------
def link_booking(job, digits=None):
    """A booking from a Thumbtack lead — the only way to know what a lead is
    really worth. Matches by phone within the window. Never raises."""
    try:
        d = _digits(digits or (job.customer.phone if getattr(job, "customer", None) else None))
        if not d:
            return None
        # never credit a lead we refused to work — the booking didn't come from it
        row = (ThumbtackLead.query
               .filter(ThumbtackLead.phone_digits == d, ThumbtackLead.job_id.is_(None),
                       ThumbtackLead.status.notin_(("test", "not_serviceable")),
                       ThumbtackLead.created_at >= _now() - timedelta(days=30))
               .order_by(ThumbtackLead.created_at.desc()).first())
        if row is None:
            return None
        row.job_id = job.id
        row.status = "booked"
        row.booked_value = float(getattr(job, "total_price", None) or 0)
        db.session.commit()
        logger.info("thumbtack lead %s became job %s (${:.0f})", row.id, job.id, row.booked_value or 0)
        return row
    except Exception:
        logger.exception("thumbtack: could not link a booking")
        db.session.rollback()
        return None


def report(days=30):
    """One screen: spend, what came back, what we wasted it on, and where the
    demand actually is — by category and by county."""
    since = _now() - timedelta(days=days)
    rows = ThumbtackLead.query.filter(ThumbtackLead.created_at >= since,
                                      ThumbtackLead.status != "test").all()
    spend = sum(r.lead_price or 0 for r in rows)
    booked = [r for r in rows if r.job_id]
    revenue = sum(r.booked_value or 0 for r in booked)
    wasted = [r for r in rows if r.serviceable is False]
    replied = [r for r in rows if r.text_sent_at]
    speeds = [int((r.text_sent_at - r.created_at).total_seconds()) for r in replied
              if r.text_sent_at and r.created_at]

    def group(key):
        out = {}
        for r in rows:
            k = (getattr(r, key, None) or "unknown")
            g = out.setdefault(k, {"leads": 0, "spend": 0.0, "booked": 0, "revenue": 0.0})
            g["leads"] += 1
            g["spend"] = round(g["spend"] + (r.lead_price or 0), 2)
            if r.job_id:
                g["booked"] += 1
                g["revenue"] = round(g["revenue"] + (r.booked_value or 0), 2)
        for k, g in out.items():
            g["cost_per_booking"] = round(g["spend"] / g["booked"], 2) if g["booked"] else None
        return dict(sorted(out.items(), key=lambda kv: -kv[1]["leads"])[:15])

    from models_thumbtack import ThumbtackReview
    reviews = ThumbtackReview.query.filter(ThumbtackReview.created_at >= since).all()
    rated = [r.rating for r in reviews if r.rating is not None]
    return {
        "days": days,
        "leads": len(rows),
        "spend": round(spend, 2),
        "booked": len(booked),
        "revenue": round(revenue, 2),
        "return_on_spend": round(revenue / spend, 2) if spend else None,
        "cost_per_booking": round(spend / len(booked), 2) if booked else None,
        "book_rate": round(len(booked) / len(rows), 3) if rows else None,
        "not_serviceable": len(wasted),
        "wasted_spend": round(sum(r.lead_price or 0 for r in wasted), 2),
        "wasted_reasons": _top([r.service_note for r in wasted]),
        "median_reply_seconds": sorted(speeds)[len(speeds) // 2] if speeds else None,
        "never_replied": len(rows) - len(replied),
        "by_category": group("category"),
        "by_county": group("county"),
        "reviews": {"count": len(reviews),
                    "average": round(sum(rated) / len(rated), 2) if rated else None},
    }


def _top(values, n=5):
    counts = {}
    for v in values:
        if v:
            counts[v[:80]] = counts.get(v[:80], 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1])[:n])


def register_admin_routes(app, require_admin):
    @app.route("/api/admin/thumbtack/report", methods=["GET"])
    @require_admin
    def thumbtack_report(user_id):
        """Is Thumbtack paying for itself, and where is the demand?"""
        days = max(1, min(request.args.get("days", 30, type=int), 365))
        return jsonify(report(days)), 200

    @app.route("/api/admin/thumbtack/events", methods=["GET"])
    @require_admin
    def thumbtack_events(user_id):
        rows = ThumbtackLead.query.order_by(ThumbtackLead.created_at.desc()).limit(20).all()
        return jsonify({"configured": bool(_env("THUMBTACK_WEBHOOK_USER") and _env("THUMBTACK_WEBHOOK_PASSWORD")),
                        "events": list(RECENT_EVENTS), "rejected": list(REJECTED),
                        # the raw body as Thumbtack sent it: the only way to fix
                        # the parser when their field names differ from the docs
                        "leads": [dict(r.to_dict(), raw=r.raw) for r in rows]}), 200
