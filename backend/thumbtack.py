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
from collections import deque
from datetime import datetime, timezone

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


def _gate():
    ok = _authorized()
    if ok is None:
        return jsonify(error="Thumbtack webhook is not configured on this server."), 503
    if not ok:
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


def parse_lead(p):
    """Thumbtack's lead shape (customer, request, business, leadID…) → our columns.
    Every read is a list of candidate paths so a renamed field degrades to
    'missing', never to a crash."""
    req = p.get("request") if isinstance(p.get("request"), dict) else {}
    cust = p.get("customer") if isinstance(p.get("customer"), dict) else {}
    loc = _dig(req, "location", "address", default={}) or {}
    if not isinstance(loc, dict):
        loc = {}
    phone = _dig(p, "customer.phone", "customer.phoneNumber", "phone", "phoneNumber", "customerPhone")
    digits = _digits(phone)
    sched = _dig(req, "schedule", default=None) or _dig(p, "schedule")
    if isinstance(sched, dict):
        sched = " ".join(str(v) for v in sched.values() if v)
    details = _dig(req, "details", default=None) or _dig(p, "details")
    if isinstance(details, dict):
        details = [{"question": k, "answer": v} for k, v in details.items()]
    attachments = _dig(req, "attachments", default=None) or _dig(p, "attachments") or []
    if not isinstance(attachments, list):
        attachments = []
    address_bits = [_dig(loc, "address1", "line1", "street"), _dig(loc, "address2", "line2")]
    return {
        "lead_id": _text(_dig(p, "leadID", "leadId", "lead_id", "negotiationID", "negotiationId", "id"), 80),
        "business_id": _text(_dig(p, "business.businessID", "business.id", "businessID", "businessId"), 80),
        "lead_type": _text(_dig(p, "leadType", "lead_type", "type"), 40),
        "lead_price": _num(_dig(p, "leadPrice", "lead_price", "price")),
        "customer_id": _text(_dig(cust, "customerID", "customerId", "id") or _dig(p, "customerID"), 80),
        "customer_name": _text(_dig(cust, "name", "firstName", "displayName") or _dig(p, "customerName", "name"), 160),
        "phone": _pretty(digits) or _text(phone, 40),
        "phone_digits": digits or None,
        "email": _text(_dig(cust, "email") or _dig(p, "email"), 254),
        "address": _text(", ".join(str(b) for b in address_bits if b), 500),
        "city": _text(_dig(loc, "city") or _dig(p, "city"), 80),
        "state": _text(_dig(loc, "state") or _dig(p, "state"), 8),
        "zip": _text(_dig(loc, "zipCode", "zip", "postalCode") or _dig(p, "zipCode", "zip"), 12),
        "category": _text(_dig(req, "category", "categoryName") or _dig(p, "category", "categoryName"), 120),
        "title": _text(_dig(req, "title") or _dig(p, "title"), 200),
        "description": _text(_dig(req, "description") or _dig(p, "description", "message")),
        "schedule": _text(sched, 300),
        "details": details if isinstance(details, list) else None,
        "attachments": [{"url": a.get("url"), "fileName": a.get("fileName") or a.get("name"),
                         "mimeType": a.get("mimeType")} for a in attachments if isinstance(a, dict)] or None,
    }


def _num(v):
    try:
        return float(v) if v not in (None, "") else None
    except Exception:
        return None


def parse_message(p):
    return {
        "lead_id": _text(_dig(p, "leadID", "leadId", "lead_id", "negotiationID", "negotiationId"), 80),
        "message_id": _text(_dig(p, "messageID", "messageId", "id"), 80),
        "text": _text(_dig(p, "message.text", "text", "message", "body")),
        "from": _text(_dig(p, "message.sender", "sender", "from", "author"), 40) or "customer",
        "at": _text(_dig(p, "createTimestamp", "timestamp", "createdAt"), 40),
        "attachments": _dig(p, "message.attachments", "attachments", default=[]) or [],
    }


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
    """Same fan-out as booking alerts: SMS to the alert phones, email, Slack. Never raises."""
    try:
        from booking_alerts import _phones
    except Exception:
        _phones = lambda: []  # noqa: E731
    headline = {"lead": "Thumbtack lead", "message": "Thumbtack message", "review": "Thumbtack review"}.get(kind, "Thumbtack")
    lines = [headline + (" · " + lead.customer_name if lead and lead.customer_name else ""),
             "{}{}".format(lead.category or lead.title or "", " · " + lead.city if lead and lead.city else "") if lead else ""]
    if lead and lead.phone:
        lines.append("Phone " + lead.phone + (" · texted" if lead.text_sent_at else " · NOT texted"))
    if lead and lead.description:
        lines.append(lead.description[:240])
    if extra:
        lines.append(extra[:300])
    lines.append("Desk: {}/va/calls".format(_env("DESK_PUBLIC_URL") or "https://ops.goumuve.com"))
    body = "\n".join(l for l in lines if l)
    try:
        for phone in _phones():
            try:
                from sms_service import send_sms_async
                send_sms_async(phone, body)
            except Exception:
                logger.exception("thumbtack alert sms failed")
        if _env("ADMIN_EMAIL"):
            try:
                from notifications import _send_email_sync
                _send_email_sync(_env("ADMIN_EMAIL"), lines[0], "<pre style='font:13px/1.5 monospace'>{}</pre>".format(body))
            except Exception:
                logger.exception("thumbtack alert email failed")
        hook = _env("SLACK_ALERT_WEBHOOK")
        if hook:
            try:
                import requests
                requests.post(hook, json={"text": "*{}*\n```{}```".format(lines[0], body)}, timeout=10)
            except Exception:
                logger.exception("thumbtack alert slack failed")
    except Exception:
        logger.exception("thumbtack alert failed")


def desk_leads(since):
    """Rows for leads.collect(): every Thumbtack lead in the window, one shape."""
    from leads import _lead
    out = []
    for r in (ThumbtackLead.query.filter(ThumbtackLead.created_at >= since)
              .order_by(ThumbtackLead.created_at.desc()).limit(200).all()):
        what = " · ".join(x for x in [r.category or r.title, r.description[:80] if r.description else None] if x)
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
    if "review" in p or "rating" in p:
        return "review"
    if "message" in p or "text" in p and "leadID" in p:
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
    texted = text_customer(lead)
    alert_team(lead, "lead")
    logger.info("thumbtack lead %s (%s, %s) texted=%s", lead.id, lead.customer_name, lead.city, texted)
    return lead, True


def handle_message(p):
    m = parse_message(p)
    lead = ThumbtackLead.query.filter_by(lead_id=m["lead_id"]).first() if m["lead_id"] else None
    if lead is None:
        # a message for a lead we never saw: make a stub so nothing is lost
        lead = ThumbtackLead(id=generate_uuid(), lead_id=m["lead_id"], raw=p, description=m["text"])
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
            return api_review()
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


@thumbtack_bp.route("/review", methods=["POST"])
def api_review():
    err = _gate()
    if err:
        return err
    p = _payload()
    _record("review", p)
    rating = _dig(p, "review.rating", "rating")
    text = _text(_dig(p, "review.text", "text", "review"), 400)
    alert_team(None, "review", extra="{}★ {}".format(rating, text or "") if rating else (text or "new review"))
    return jsonify(ok=True, kind="review"), 200


def register_admin_routes(app, require_admin):
    @app.route("/api/admin/thumbtack/events", methods=["GET"])
    @require_admin
    def thumbtack_events(user_id):
        rows = ThumbtackLead.query.order_by(ThumbtackLead.created_at.desc()).limit(20).all()
        return jsonify({"configured": bool(_env("THUMBTACK_WEBHOOK_USER") and _env("THUMBTACK_WEBHOOK_PASSWORD")),
                        "events": list(RECENT_EVENTS), "leads": [r.to_dict() for r in rows]}), 200
