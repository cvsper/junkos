"""VA Call Desk — one-prospect-at-a-time calling console for the VA suite.

Grew out of the demand-side call list (Aug 2026): 300+ business prospects on
a 3-touch cadence outgrew the spreadsheet. The desk deals one card at a time
(due follow-ups first, then fresh rows by tier), the number is tap-to-call,
and one tap logs the outcome + schedules the next touch server-side.

Routes:
  GET  /va/calls            -> console page (same gate/passcode as /va)
  GET  /va/calls.css        -> console-only styles (layered over /va/app.css)
  GET  /va/calls.js         -> client script
  POST /api/va/calls/next   -> passcode-gated; next card + day stats
  POST /api/va/calls/log    -> passcode-gated; log outcome, return next card
  POST /api/va/calls/send-info -> passcode-gated; info pack by text or email,
                                  independent of outcome logging (gatekeeper
                                  flow: "send something for the manager")
  POST /api/va/calls/contact   -> passcode-gated; save the decision-maker a
                                  gatekeeper hands over (name / direct cell /
                                  email) onto the prospect card
  POST /api/admin/call-prospects/import -> admin; seed/merge prospect rows
  GET  /api/admin/caller-stats          -> admin; outcomes by day + segment

Cadence rules (server-side, mirrors the playbook):
  voicemail / no_answer  -> retry in 3 days, then 4 days; 3 strikes -> dead
  interested / sent_link -> status interested, follow up in 2 days
  not_interested / bad_number -> dead
  vendor_listed -> on their vendor list / rate card on file (a soft win);
                   light check-in every 3 weeks so we stay top of mind
  converted -> won (they booked / signed up)
  skip -> back of today's queue (4 hours)
"""
from __future__ import annotations

import hmac
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Blueprint, Response, jsonify, request

from desk_auth import desk_identity, desk_va_name, audit, is_manager
from models import db, CallAttempt, CallProspect, User
from auth_routes import require_auth

try:
    from extensions import limiter
except Exception:  # pragma: no cover
    limiter = None

logger = logging.getLogger(__name__)

vacalls_bp = Blueprint("vacalls", __name__)

_ratelimit = (
    limiter.limit("240 per hour; 30 per minute")
    if limiter is not None
    else (lambda f: f)
)


def _passcode_ok(supplied):
    expected = os.environ.get("TRIXIE_ASSISTANT_PASSCODE", "")
    if not expected:
        return False  # fail closed
    return hmac.compare_digest(str(supplied or ""), str(expected))


def require_admin(f):
    @wraps(f)
    @require_auth
    def wrapper(user_id, *args, **kwargs):
        user = db.session.get(User, user_id)
        if not user or user.role != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(user_id=user_id, *args, **kwargs)
    return wrapper


def _digits(phone):
    d = re.sub(r"\D", "", phone or "")
    return d[-10:] if len(d) >= 10 else d


# The VA reads this out loud — one opener per segment, from the playbook.
OPENERS = {
    "property": (
        "Hi, this is {va} with Umuve, a Palm Beach County junk-removal service. "
        "Quick question — when a tenant leaves furniture behind or someone dumps "
        "a couch by the compactor, who handles that for you today? ... That's "
        "what we do: one call or text, upfront price, usually gone same day. We "
        "set up standing accounts with volume rates for management companies."),
    "storage": (
        "Hi, this is {va} with Umuve. When a unit gets abandoned or goes to "
        "auction and there's leftovers, what do you do with it now? We turn an "
        "abandoned unit back into a rentable unit in about 24 hours — flat "
        "upfront price, your manager texts us, it's handled."),
    "estate": (
        "Hi, this is {va} with Umuve. Every sale ends with stuff that didn't "
        "sell — what happens to it now? We're the cleanout partner: you close "
        "the sale Saturday, we clear the house Monday, the family gets the keys "
        "back. Upfront pricing, and you look full-service without owning a truck."),
    "realtor": (
        "Hi, this is {va} with Umuve. When a listing or an estate needs a "
        "cleanout before it can move, who do you send them to? Give your "
        "sellers one number — upfront price, insured local pros, and there's a "
        "10% referral credit for realtors on every job."),
    "flipper": (
        "Hi, this is {va} with Umuve. Every property you close on comes with a "
        "dumpster's worth of stuff. We quote upfront from photos and clear it "
        "same-day or next-day, so your crew starts demo on day one instead of "
        "hauling."),
    "senior": (
        "Hi, this is {va} with Umuve. Your clients downsize — most of what's "
        "left needs to go somewhere. We handle the haul-away leg: respectful "
        "crews, upfront pricing, donation drop-offs where items qualify. You "
        "stay the trusted face; we do the lifting."),
    "mover": (
        "Hi, this is {va} with Umuve. How often do customers ask you to take "
        "stuff they DON'T want moved? You say no to that every week. Hand them "
        "our number instead — your customer gets solved, you look good, costs "
        "you nothing."),
    "contractor": (
        "Hi, this is {va} with Umuve. When a remodel produces a pile of old "
        "cabinets or torn-out flooring, your options are your crew's truck or a "
        "dumpster in the driveway. We do same-day debris pickup at an upfront "
        "price — your guys stay on the tools."),
    "thrift": (
        "Hi, this is {va} with Umuve. What do you do with donations you can't "
        "sell? Most stores pay to dispose of overflow. We do scheduled overflow "
        "pickups at a flat rate — compare it to what you're paying now."),
}

_CATEGORY_OPENER = [
    (("moving", "mover", "fletes", "mudanza"), "mover"),
    (("property", "hoa", "apartment", "commercial", "office", "institution",
      "hotel"), "property"),
    (("storage",), "storage"),
    (("real estate", "staging", "probate"), "realtor"),
    (("estate", "auction", "antiques", "thrift"), "estate"),
    (("investor", "flipper"), "flipper"),
    (("senior",), "senior"),
    (("contractor", "flooring", "restoration", "handyman", "painting"),
     "contractor"),
]


def opener_for(category):
    c = (category or "").lower()
    if "thrift" in c or "donation" in c:
        return OPENERS["thrift"]
    for keys, name in _CATEGORY_OPENER:
        if any(k in c for k in keys):
            return OPENERS[name]
    return OPENERS["property"]


# Follow-up texts the desk can send from the Umuve number — server-side
# whitelist keyed by the outcome that was just logged (same rule as /va:
# the client never supplies free text).
def _first_name(contact):
    parts = (contact or "").strip().split()
    return parts[0] if parts else ""


def followup_text_for(outcome, prospect, va_name):
    name = _first_name(prospect.contact_name)
    greet = "Hi {},".format(name) if name else "Hi there,"
    va = (va_name or "Tracy").split()[0]
    if outcome in ("interested", "sent_link"):
        return (
            "{greet} it's {va} with Umuve — great talking with you. Partner "
            "info: goumuve.com/partners — volume rates, priority scheduling, "
            "one number for every cleanout. Save this number: text a photo of "
            "any pile and you'll have an upfront price in minutes. Reply STOP "
            "to opt out."
        ).format(greet=greet, va=va)
    if outcome == "vendor_listed":
        return (
            "{greet} it's {va} with Umuve — thanks for adding us to your "
            "vendor list. Rates + volume plans: goumuve.com/partners. When a "
            "cleanout comes up, call or text (561) 944-1636 any time, day or "
            "night — upfront price, same-day available. Reply STOP to opt out."
        ).format(greet=greet, va=va)
    if outcome in ("voicemail", "no_answer"):
        return (
            "{greet} it's {va} with Umuve (just tried you). We do same-day "
            "junk & cleanout pickups for Palm Beach County businesses at "
            "upfront prices — goumuve.com/partners. This number takes texts "
            "if that's easier. Reply STOP to opt out."
        ).format(greet=greet, va=va)
    return None


def info_text_for(prospect, va_name):
    """The standalone info-pack text — self-contained so it still makes sense
    forwarded to a decision-maker who never heard the call."""
    va = (va_name or "Tracy").split()[0]
    return (
        "Hi, it's {va} with Umuve — the info I promised, feel free to pass it "
        "along: we do junk removal & cleanouts for South Florida businesses. "
        "Upfront price before we come out, pickup same or next day. Details: "
        "goumuve.com/partners. This number takes calls, texts & photos — text "
        "a photo of any pile for a quick price. Reply STOP to opt out."
    ).format(va=va)


TEXT_DEDUPE_HOURS = 24


def _run(fn):
    try:
        from eventlet import tpool  # type: ignore
    except Exception:
        tpool = None
    if tpool is not None:
        return tpool.execute(fn)
    return fn()


def maybe_send_followup_text(prospect, outcome, va_name):
    """Send the whitelisted follow-up text for this outcome, if allowed.

    Returns (sent: bool, reason: str)."""
    body = followup_text_for(outcome, prospect, va_name)
    if body is None:
        return False, "no text for this outcome"
    if len(prospect.phone_digits or "") != 10:
        return False, "no valid mobile number"
    now_naive = _now().replace(tzinfo=None)
    if prospect.last_texted_at and \
            now_naive - prospect.last_texted_at < timedelta(hours=TEXT_DEDUPE_HOURS):
        return False, "already texted in the last day"
    import sms_service
    sid = _run(lambda: sms_service.send_sms(prospect.phone, body))
    if not sid:
        return False, "text didn't go through"
    prospect.last_texted_at = now_naive
    return True, "sent"


# ---------------------------------------------------------------------------
# Queue + cadence
# ---------------------------------------------------------------------------

RETRY_DAYS = [3, 4]          # voicemail/no-answer touches after the first call
MAX_SOFT_ATTEMPTS = 3        # then dead
INTERESTED_FOLLOWUP_DAYS = 2
VENDOR_LISTED_CHECKIN_DAYS = 21   # "still on file? anything coming up?"

# Outcomes that count as a conversation that went our way.
WIN_OUTCOMES = ("interested", "sent_link", "vendor_listed", "converted")
# Prospect statuses the desk keeps serving (everything else is done).
WORKABLE_STATUSES = ("queued", "interested", "vendor_listed")

OUTCOMES = {"interested", "sent_link", "vendor_listed", "voicemail", "no_answer",
            "not_interested", "bad_number", "converted", "skip"}


def _now():
    return datetime.now(timezone.utc)


def _eastern_day_start(now=None):
    """Start of 'today' in US Eastern expressed as naive UTC (matches column)."""
    now = now or _now()
    local = now - timedelta(hours=4)
    day_start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return (day_start_local + timedelta(hours=4)).replace(tzinfo=None)


# Recurring-demand accounts outrank one-off jobs inside a tier: one property
# manager with 30 doors produces move-out cleanouts every month forever, while
# an estate sale is a single job. Rank 0 = standing institutional demand,
# rank 1 = repeat referrers (their clients churn junk constantly), rank 2 =
# episodic. Note "estate sales" lands in rank 2 — only "real estate" is a
# referrer — because the recurring/referrer keyword lists are checked first.
_RECURRING_CATS = ("property", "hoa", "apartment", "hotel", "institution",
                   "commercial", "office", "storage")
_REFERRER_CATS = ("real estate", "staging", "probate", "senior", "moving",
                  "investor", "flipper")


def _category_rank_sql():
    from sqlalchemy import case, func
    cat = func.lower(func.coalesce(CallProspect.category, ""))
    return case(
        *[(cat.contains(k), 0) for k in _RECURRING_CATS],
        *[(cat.contains(k), 1) for k in _REFERRER_CATS],
        else_=2,
    )


def next_card():
    """Due follow-ups first (oldest due), then fresh rows by tier with
    recurring-demand categories served before one-off categories."""
    now_naive = _now().replace(tzinfo=None)
    workable = CallProspect.status.in_(WORKABLE_STATUSES)
    due = (CallProspect.query
           .filter(workable,
                   CallProspect.next_followup_at.isnot(None),
                   CallProspect.next_followup_at <= now_naive)
           .order_by(CallProspect.next_followup_at.asc())
           .first())
    if due:
        return due
    return (CallProspect.query
            .filter(workable, CallProspect.next_followup_at.is_(None))
            .order_by(CallProspect.tier.asc(), _category_rank_sql().asc(),
                      CallProspect.category.asc(), CallProspect.created_at.asc())
            .first())


def day_stats():
    start = _eastern_day_start()
    calls_today = CallAttempt.query.filter(
        CallAttempt.created_at >= start,
        CallAttempt.outcome != "skip").count()
    interested_today = CallAttempt.query.filter(
        CallAttempt.created_at >= start,
        CallAttempt.outcome.in_(WIN_OUTCOMES)).count()
    now_naive = _now().replace(tzinfo=None)
    workable = CallProspect.status.in_(WORKABLE_STATUSES)
    due_now = CallProspect.query.filter(
        workable, CallProspect.next_followup_at.isnot(None),
        CallProspect.next_followup_at <= now_naive).count()
    fresh = CallProspect.query.filter(
        CallProspect.status == "queued",
        CallProspect.next_followup_at.is_(None)).count()
    return {"calls_today": calls_today, "interested_today": interested_today,
            "due_now": due_now, "fresh": fresh}


def apply_outcome(prospect, outcome, note, va_name):
    now = _now()
    now_naive = now.replace(tzinfo=None)
    if outcome != "skip":
        prospect.attempts = (prospect.attempts or 0) + 1
        prospect.last_called_at = now_naive
        prospect.last_outcome = outcome
    if note:
        prospect.last_note = note

    if outcome in ("interested", "sent_link"):
        prospect.status = "interested"
        prospect.next_followup_at = now_naive + timedelta(days=INTERESTED_FOLLOWUP_DAYS)
    elif outcome in ("voicemail", "no_answer"):
        if prospect.attempts >= MAX_SOFT_ATTEMPTS:
            prospect.status = "dead"
            prospect.next_followup_at = None
        else:
            days = RETRY_DAYS[min(prospect.attempts - 1, len(RETRY_DAYS) - 1)]
            prospect.next_followup_at = now_naive + timedelta(days=days)
    elif outcome in ("not_interested", "bad_number"):
        prospect.status = "dead"
        prospect.next_followup_at = None
    elif outcome == "vendor_listed":
        prospect.status = "vendor_listed"
        prospect.next_followup_at = now_naive + timedelta(days=VENDOR_LISTED_CHECKIN_DAYS)
    elif outcome == "converted":
        prospect.status = "converted"
        prospect.next_followup_at = None
    elif outcome == "skip":
        prospect.next_followup_at = now_naive + timedelta(hours=4)

    db.session.add(CallAttempt(prospect_id=prospect.id, outcome=outcome,
                               note=note or None, va_name=va_name or None))
    from crm import on_outcome; on_outcome(prospect, outcome, note, va_name)  # CRM (Phase 3)


def _card_payload(p, va_name):
    d = p.to_dict()
    d["opener"] = opener_for(p.category).format(va=(va_name or "Tracy").split()[0])
    d["tel"] = "tel:+1" + p.phone_digits if len(p.phone_digits) == 10 else "tel:" + p.phone
    direct = _digits(p.direct_phone) if p.direct_phone else ""
    d["direct_tel"] = "tel:+1" + direct if len(direct) == 10 else None
    d["is_followup"] = bool(p.next_followup_at)
    from crm import crm_card_fields; d.update(crm_card_fields(p))  # CRM (Phase 3)
    from compliance import compliance_for_card; d["compliance"] = compliance_for_card(p)  # Phase 2 (compliance.py)
    if not (d.get("angle") or "").strip():
        try:
            from enrich import template_angle       # instant stand-in until the backfill writes a real one
            d["angle"] = template_angle(p)
            d["angle_generated"] = True
        except Exception:
            pass
    return d


# ---------------------------------------------------------------------------
# VA-facing API (passcode-gated, same code as /va)
# ---------------------------------------------------------------------------

@vacalls_bp.route("/api/va/calls/next", methods=["POST"])
@_ratelimit
def calls_next():
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    from crm import next_unclaimed
    p = next_unclaimed(desk_va_name(data))
    stats = day_stats()
    if not p:
        nxt = (CallProspect.query
               .filter(CallProspect.status.in_(WORKABLE_STATUSES),
                       CallProspect.next_followup_at.isnot(None))
               .order_by(CallProspect.next_followup_at.asc()).first())
        total = CallProspect.query.count()
        scheduled = CallProspect.query.filter(
            CallProspect.status.in_(WORKABLE_STATUSES),
            CallProspect.next_followup_at.isnot(None)).count()
        return jsonify({"empty": True, "stats": stats, "total": total, "scheduled": scheduled,
                        "next_due": nxt.next_followup_at.isoformat() if nxt else None}), 200
    return jsonify({"card": _card_payload(p, desk_va_name(data)), "stats": stats}), 200


@vacalls_bp.route("/api/va/calls/log", methods=["POST"])
@_ratelimit
def calls_log():
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    outcome = (data.get("outcome") or "").strip()
    if outcome not in OUTCOMES:
        return jsonify({"error": "Unknown outcome."}), 400
    p = db.session.get(CallProspect, data.get("prospect_id") or "")
    if not p:
        return jsonify({"error": "Prospect not found — reload the page."}), 404
    note = (data.get("note") or "").strip()[:1000]
    va_name = desk_va_name(data)
    apply_outcome(p, outcome, note, va_name)
    db.session.commit()
    audit("outcome", "prospect", p.id, {"outcome": outcome, "company": p.company})

    texted, text_reason = False, None
    if data.get("send_text"):
        texted, text_reason = maybe_send_followup_text(p, outcome, va_name)
        db.session.commit()

    from crm import next_unclaimed
    nxt = next_unclaimed(va_name)
    stats = day_stats()
    resp = {"logged": True, "stats": stats,
            "texted": texted, "text_reason": text_reason}
    if nxt:
        resp["card"] = _card_payload(nxt, va_name)
    else:
        resp["empty"] = True
    return jsonify(resp), 200


@vacalls_bp.route("/api/va/calls/search", methods=["POST"])
@_ratelimit
def calls_search():
    """Find a prospect who called back — by name, city, or number."""
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    q = (data.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"results": []}), 200
    digits = re.sub(r"\D", "", q)
    like = "%{}%".format(q)
    filters = [CallProspect.company.ilike(like), CallProspect.city.ilike(like),
               CallProspect.contact_name.ilike(like)]
    if len(digits) >= 4:
        filters.append(CallProspect.phone_digits.like("%{}%".format(digits)))
    from sqlalchemy import or_
    rows = (CallProspect.query.filter(or_(*filters))
            .order_by(CallProspect.tier.asc(), CallProspect.company.asc())
            .limit(8).all())
    return jsonify({"results": [
        {"id": r.id, "company": r.company, "city": r.city, "phone": r.phone,
         "category": r.category, "tier": r.tier, "status": r.status}
        for r in rows]}), 200


@vacalls_bp.route("/api/va/calls/get", methods=["POST"])
@_ratelimit
def calls_get():
    """Load one specific prospect as the active card (callback flow)."""
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    p = db.session.get(CallProspect, data.get("prospect_id") or "")
    if not p:
        return jsonify({"error": "Prospect not found."}), 404
    return jsonify({"card": _card_payload(p, desk_va_name(data)),
                    "stats": day_stats()}), 200


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _va_email_from():
    return (os.environ.get("VA_EMAIL_FROM")
            or os.environ.get("OUTREACH_FROM") or "").strip() or None


@vacalls_bp.route("/api/va/calls/send-info", methods=["POST"])
@_ratelimit
def calls_send_info():
    """Send the partner info pack by text or email, no outcome required.

    Born from the gatekeeper problem (Tracy, Aug 2026): most B2B dials reach a
    receptionist who says "send us something for the manager" — often with a
    different cell number or an email address. Bodies are server-side
    templates; the client only supplies the destination.
    """
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    p = db.session.get(CallProspect, data.get("prospect_id") or "")
    if not p:
        return jsonify({"error": "Prospect not found — reload the page."}), 404
    va_name = desk_va_name(data)
    channel = (data.get("channel") or "").strip()
    to = (data.get("to") or "").strip()

    if channel == "text":
        digits = _digits(to) if to else p.phone_digits
        if len(digits or "") != 10:
            return jsonify({"error": "That doesn't look like a valid US number."}), 400
        import sms_service
        sid = _run(lambda: sms_service.send_sms("+1" + digits, info_text_for(p, va_name)))
        if not sid:
            return jsonify({"error": "The text didn't go through — texting may be "
                                     "down, or that's not a textable number."}), 502
        p.last_texted_at = _now().replace(tzinfo=None)
        db.session.commit()
        audit("info_text", "prospect", p.id, {"to_last4": digits[-4:]})
        logger.info("call desk info text sent to %s (company=%s)", digits, p.company)
        return jsonify({"ok": True, "channel": "text",
                        "to": "(...) " + digits[-4:], "sid": sid}), 200

    if channel == "email":
        to_email = to.lower()
        if not _EMAIL_RE.match(to_email):
            return jsonify({"error": "Enter a valid email address."}), 400
        from email_templates import va_partner_info_html
        html = va_partner_info_html(company=p.company,
                                    to_name=_first_name(p.contact_name),
                                    va_name=va_name)
        subject = "Junk removal & cleanouts for {} — Umuve".format(
            (p.company or "your business")[:80])
        from notifications import _send_email_sync
        from_addr = _va_email_from()
        result = _run(lambda: _send_email_sync(to_email, subject, html,
                                               from_override=from_addr))
        if result is None and from_addr:
            logger.warning("call desk email from %s failed; retrying from default sender",
                           from_addr)
            result = _run(lambda: _send_email_sync(to_email, subject, html))
        if result is None:
            return jsonify({"error": "Email isn't configured yet — ask Shamar."}), 503
        p.email = to_email[:254]
        p.last_emailed_at = _now().replace(tzinfo=None)
        db.session.commit()
        audit("info_email", "prospect", p.id, {"to": to_email})
        logger.info("call desk info email sent to %s (company=%s)", to_email, p.company)
        return jsonify({"ok": True, "channel": "email", "to": to_email}), 200

    return jsonify({"error": "Unknown channel."}), 400


@vacalls_bp.route("/api/va/calls/contact", methods=["POST"])
@_ratelimit
def calls_contact():
    """Save the decision-maker a gatekeeper hands over.

    Any of contact_name / direct_phone / email may be supplied; a present-but-
    empty value clears the field. The name feeds "ask for X" on the card and
    the greeting on every outgoing text/email; the direct cell becomes a
    second tap-to-call and the default target for the info text.
    """
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    p = db.session.get(CallProspect, data.get("prospect_id") or "")
    if not p:
        return jsonify({"error": "Prospect not found — reload the page."}), 404

    if "contact_name" in data:
        p.contact_name = (data.get("contact_name") or "").strip()[:120] or None
    if "direct_phone" in data:
        raw = (data.get("direct_phone") or "").strip()
        if raw:
            digits = _digits(raw)
            if len(digits) != 10:
                return jsonify({"error": "That direct number doesn't look like "
                                         "a valid US cell."}), 400
            p.direct_phone = raw[:40]
        else:
            p.direct_phone = None
    if "email" in data:
        raw = (data.get("email") or "").strip().lower()
        if raw and not _EMAIL_RE.match(raw):
            return jsonify({"error": "Enter a valid email address."}), 400
        p.email = raw[:254] or None

    db.session.commit()
    audit("contact_saved", "prospect", p.id)
    return jsonify({"ok": True,
                    "card": _card_payload(p, desk_va_name(data))}), 200


@vacalls_bp.route("/rate-card/<prospect_id>.pdf", methods=["GET"])
def rate_card_pdf(prospect_id):
    """Public, signed: the personalized rate card. Linked from texts, attached to emails."""
    from rate_card import check_sig, build_rate_card_pdf
    if not check_sig(prospect_id, request.args.get("s")):
        return Response("Not found", status=404)
    p = db.session.get(CallProspect, prospect_id)
    if not p:
        return Response("Not found", status=404)
    from desk_line import desk_number
    pdf = build_rate_card_pdf(p, va_name=request.args.get("va"), desk_number=desk_number())
    resp = Response(pdf, mimetype="application/pdf")
    resp.headers["Content-Disposition"] = 'inline; filename="Umuve-rate-card-{}.pdf"'.format(
        re.sub(r"[^A-Za-z0-9]+", "-", p.company or "prospect").strip("-")[:40])
    resp.headers["Cache-Control"] = "private, max-age=600"
    return resp


@vacalls_bp.route("/api/va/calls/rate-card", methods=["POST"])
@_ratelimit
def calls_rate_card():
    """Text a link to, or email, the personalized PDF rate card."""
    from rate_card import public_url, build_rate_card_pdf
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    p = db.session.get(CallProspect, data.get("prospect_id") or "")
    if not p:
        return jsonify({"error": "Prospect not found — reload the page."}), 404
    va_name = desk_va_name(data)
    va = (va_name or "Tracy").split()[0]
    channel = (data.get("channel") or "").strip()
    to = (data.get("to") or "").strip()
    url = public_url(p.id) + "&va=" + va
    if channel == "preview":
        return jsonify({"ok": True, "url": url}), 200
    if channel == "text":
        digits = _digits(to) if to else (_digits(p.direct_phone) if p.direct_phone else p.phone_digits)
        if len(digits or "") != 10:
            return jsonify({"error": "That doesn't look like a valid US number."}), 400
        body = ("Hi{}, it's {} with Umuve - here's the rate card for {}: {} "
                "Text a photo of any pile to this number for an exact price. Reply STOP to opt out."
                ).format(" " + _first_name(p.contact_name) if p.contact_name else "", va,
                         (p.company or "your business")[:60], url)
        from desk_line import send_desk_text
        sid = _run(lambda: send_desk_text(digits, body, prospect=p, va_name=va_name))
        if not sid:
            return jsonify({"error": "The text didn't go through — texting may be down, "
                                     "or that's not a textable number."}), 502
        audit("rate_card_text", "prospect", p.id, {"to_last4": digits[-4:]})
        return jsonify({"ok": True, "channel": "text", "to": "(...) " + digits[-4:], "url": url}), 200
    if channel == "email":
        to_email = to.lower()
        if not _EMAIL_RE.match(to_email):
            return jsonify({"error": "Enter a valid email address."}), 400
        from desk_line import desk_number
        pdf = build_rate_card_pdf(p, va_name=va_name, desk_number=desk_number())
        from email_templates import va_partner_info_html
        html = va_partner_info_html(company=p.company, to_name=_first_name(p.contact_name), va_name=va_name)
        html = html.replace("</body>", '<p style="font:14px/1.5 -apple-system,Helvetica,Arial;color:#333">'
                            'Your rate card is attached as a PDF, or open it here: '
                            '<a href="{}">rate card for {}</a>.</p></body>'.format(url, (p.company or "")[:60]))
        subject = "Rate card for {} - Umuve".format((p.company or "your business")[:70])
        from notifications import _send_email_resend
        fname = "Umuve-rate-card-{}.pdf".format(re.sub(r"[^A-Za-z0-9]+", "-", p.company or "prospect").strip("-")[:40])
        result = _run(lambda: _send_email_resend(to_email, subject, html, from_override=_va_email_from(),
                                                 attachments=[{"filename": fname, "content": pdf}]))
        if result is None and _va_email_from():
            result = _run(lambda: _send_email_resend(to_email, subject, html,
                                                     attachments=[{"filename": fname, "content": pdf}]))
        if result is None:
            return jsonify({"error": "Email isn't configured yet — ask Shamar."}), 503
        p.email = to_email[:254]
        p.last_emailed_at = _now().replace(tzinfo=None)
        db.session.commit()
        audit("rate_card_email", "prospect", p.id, {"to": to_email})
        return jsonify({"ok": True, "channel": "email", "to": to_email, "url": url}), 200
    return jsonify({"error": "Unknown channel."}), 400


@vacalls_bp.route("/api/va/calls/kit", methods=["POST"])
@_ratelimit
def calls_kit():
    """Mid-call kit: talk track, objection replies, fact sheet, live prices,
    lookups — keyed to whether we're selling them (demand) or recruiting
    them (supply). `side` lets the VA override the guess."""
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    p = db.session.get(CallProspect, data.get("prospect_id") or "")
    if not p:
        return jsonify({"error": "Prospect not found — reload the page."}), 404
    from call_kit import build_kit
    return jsonify(build_kit(p, va_name=desk_va_name(data), side=data.get("side"))), 200


CALLBACK_PRESETS = {
    "tomorrow_am": (1, 9), "tomorrow_pm": (1, 14),
    "two_days": (2, 9), "next_week": (7, 9),
}


def schedule_callback(prospect, when_utc, note, va_name):
    """They asked for a specific time: pin the follow-up, log the touch."""
    now_naive = _now().replace(tzinfo=None)
    prospect.attempts = (prospect.attempts or 0) + 1
    prospect.last_called_at = now_naive
    prospect.last_outcome = "callback"
    if prospect.status not in WORKABLE_STATUSES:
        prospect.status = "interested"
    prospect.next_followup_at = when_utc.replace(tzinfo=None)
    if note:
        prospect.last_note = note
    db.session.add(CallAttempt(prospect_id=prospect.id, outcome="callback",
                               note=note or None, va_name=va_name or None))
    try:
        from crm import on_outcome
        on_outcome(prospect, "callback", note, va_name)
    except Exception:
        logger.exception("crm on_outcome(callback) failed")


@vacalls_bp.route("/api/va/calls/callback", methods=["POST"])
@_ratelimit
def calls_callback():
    """Body: {prospect_id, preset | at, note}. `preset` is one of
    CALLBACK_PRESETS; `at` is 'YYYY-MM-DDTHH:MM' in Florida time. Logs a
    'callback' attempt, pins next_followup_at, deals the next card."""
    from timeutils import local_now, local_naive_to_utc, parse_local_iso, to_local
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    p = db.session.get(CallProspect, data.get("prospect_id") or "")
    if not p:
        return jsonify({"error": "Prospect not found — reload the page."}), 404
    preset = (data.get("preset") or "").strip()
    at = (data.get("at") or "").strip()
    try:
        if preset in CALLBACK_PRESETS:
            days, hour = CALLBACK_PRESETS[preset]
            local = local_now().replace(tzinfo=None) + timedelta(days=days)
            when = local_naive_to_utc(local.replace(hour=hour, minute=0, second=0, microsecond=0))
        elif at:
            when = parse_local_iso(at)
        else:
            return jsonify({"error": "Pick a time for the callback."}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "That date/time didn't make sense."}), 400
    if when <= _now():
        return jsonify({"error": "That time already passed — pick a later one."}), 400
    note = (data.get("note") or "").strip()[:1000]
    va_name = desk_va_name(data)
    schedule_callback(p, when, note, va_name)
    db.session.commit()
    audit("callback", "prospect", p.id, {"at": when.isoformat(), "company": p.company})
    from crm import next_unclaimed
    nxt = next_unclaimed(va_name)
    resp = {"logged": True, "callback_at": when.isoformat(),
            "callback_local": to_local(when).strftime("%a %b %-d, %-I:%M %p"),
            "stats": day_stats()}
    if nxt:
        resp["card"] = _card_payload(nxt, va_name)
    else:
        resp["empty"] = True
    return jsonify(resp), 200


# ---------------------------------------------------------------------------
# Admin: seed/merge + stats
# ---------------------------------------------------------------------------

_TIER_RE = re.compile(r"(\d)")
_CSV_ALIASES = {
    "tier": "tier", "company": "company", "business": "company", "name": "company",
    "phone": "phone", "number": "phone", "city": "city", "area": "city",
    "what they do": "category", "category": "category", "type": "category",
    "contact": "contact_name", "contact_name": "contact_name", "contact name": "contact_name",
    "notes": "why", "why": "why", "angle": "angle", "email": "email", "side": "side",
}


def parse_tier(raw):
    """'Tier 1 — Palm Beach County (LAUNCH…)' / 'Tier 2 — 2' / '3' → 1..3 (default 2)."""
    m = _TIER_RE.search(str(raw or ""))
    t = int(m.group(1)) if m else 2
    return t if t in (1, 2, 3) else (3 if t > 3 else 2)


def rows_from_csv(text):
    """Turn a call-list CSV (the Desktop weekly/re-touch shape, or plain
    tier/company/phone/... headers) into import rows. Unknown columns are
    ignored; 'Call status' / 'Outcome' / '#' never come along."""
    import csv
    import io
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for raw in reader:
        row = {}
        for k, v in raw.items():
            key = _CSV_ALIASES.get((k or "").strip().lower())
            if key and v is not None:
                row[key] = str(v).strip()
        if row.get("company") or row.get("phone"):
            rows.append(row)
    return rows


def merge_rows(rows):
    """Insert prospects, merging on phone digits. Existing rows keep their
    status and history — re-running a list is safe. Returns (added, skipped, invalid)."""
    added, skipped, invalid = 0, 0, 0
    seen = set()
    _hand_angles = []
    try:
        from compliance import filter_rows      # drop do-not-call numbers before they enter the queue
        before = len(rows)
        rows = filter_rows(rows)
        skipped += before - len(rows)           # blocked numbers count as skipped, never as invalid
    except Exception:
        logger.exception("compliance.filter_rows failed; importing unfiltered")
    for r in rows:
        digits = _digits(r.get("phone"))
        company = (r.get("company") or "").strip()
        if len(digits) != 10 or not company:
            invalid += 1
            continue
        side = (r.get("side") or "").strip().lower()
        side = side if side in ("supply", "demand") else None
        existing = None if digits in seen else CallProspect.query.filter_by(phone_digits=digits).first()
        if digits in seen or existing:
            if existing is not None and side and existing.side != side:
                existing.side = side          # a list may tell us which side an old row is on
                try:
                    from enrich import angle_source
                    if angle_source(existing) != "hand":
                        existing.angle = None     # generated under the other side → regenerate
                except Exception:
                    pass
            skipped += 1
            continue
        seen.add(digits)
        email = (r.get("email") or "").strip().lower()
        db.session.add(CallProspect(
            tier=parse_tier(r.get("tier")),
            category=(r.get("category") or "").strip()[:60],
            company=company[:200],
            phone=(r.get("phone") or "").strip()[:40],
            phone_digits=digits,
            city=(r.get("city") or "").strip()[:80] or None,
            contact_name=(r.get("contact_name") or "").strip()[:120] or None,
            why=(r.get("why") or "").strip() or None,
            angle=(r.get("angle") or "").strip() or None,
            email=email[:254] if email and _EMAIL_RE.match(email) else None,
            side=side,
        ))
        if (r.get("angle") or "").strip():
            _hand_angles.append(digits)
        added += 1
    db.session.commit()
    if _hand_angles:
        try:
            from enrich import mark_angle_source
            for d in _hand_angles:
                p = CallProspect.query.filter_by(phone_digits=d).first()
                if p:
                    mark_angle_source(p, "hand")
        except Exception:
            logger.exception("angle source marking failed")
    return added, skipped, invalid


def _import_response(added, skipped, invalid):
    return {"success": True, "added": added, "skipped_dupes": skipped, "invalid": invalid,
            "total": CallProspect.query.count(), "stats": day_stats()}


@vacalls_bp.route("/api/admin/call-prospects/import", methods=["POST"])
@require_admin
def import_prospects(user_id):
    """Body: {"rows": [{tier, category, company, phone, city, contact_name,
    why, angle}]} or {"csv": "..."}. Merges on phone digits."""
    data = request.get_json(silent=True) or {}
    rows = data.get("rows") or (rows_from_csv(data["csv"]) if data.get("csv") else [])
    return jsonify(_import_response(*merge_rows(rows))), 200


_import_ratelimit = limiter.limit("20 per hour") if limiter is not None else (lambda f: f)


@vacalls_bp.route("/api/va/calls/import", methods=["POST"])
@_import_ratelimit
def va_import_prospects():
    """Same merge, gated by the desk passcode so a list can be loaded from
    the desk itself (drag a CSV in) or by the ops CLI without an admin login."""
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    rows = data.get("rows") or (rows_from_csv(data["csv"]) if data.get("csv") else [])
    if not rows:
        return jsonify({"error": "No rows found — check the file has a header row with "
                                 "Company and Phone."}), 400
    if len(rows) > 2000:
        return jsonify({"error": "That's more than 2,000 rows — split the file."}), 400
    added, skipped, invalid = merge_rows(rows)
    audit("import", "queue", None, {"added": added, "skipped": skipped, "invalid": invalid})
    return jsonify(_import_response(added, skipped, invalid)), 200


@vacalls_bp.route("/api/va/calls/add", methods=["POST"])
@_ratelimit
def va_add_prospect():
    """One business, typed in on the desk (a callback from an unknown number,
    a referral, a walk-in). Returns the card so it can be worked right now."""
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    digits = _digits(data.get("phone"))
    if len(digits) != 10:
        return jsonify({"error": "That doesn't look like a valid US number."}), 400
    if not (data.get("company") or "").strip():
        return jsonify({"error": "Give the business a name."}), 400
    existing = CallProspect.query.filter_by(phone_digits=digits).first()
    if existing:
        return jsonify({"exists": True, "card": _card_payload(existing, desk_va_name(data)),
                        "stats": day_stats()}), 200
    merge_rows([{"tier": data.get("tier") or "1", "company": data.get("company"),
                 "phone": data.get("phone"), "city": data.get("city"),
                 "category": data.get("category"), "contact_name": data.get("contact_name"),
                 "why": data.get("why"), "email": data.get("email")}])
    p = CallProspect.query.filter_by(phone_digits=digits).first()
    audit("add_business", "prospect", p.id, {"company": p.company})
    return jsonify({"exists": False, "card": _card_payload(p, desk_va_name(data)),
                    "stats": day_stats()}), 200


def _queue_row(p):
    return {"id": p.id, "company": p.company, "city": p.city, "category": p.category,
            "tier": p.tier, "status": p.status, "attempts": p.attempts or 0,
            "contact_name": p.contact_name, "last_outcome": p.last_outcome,
            "due_at": p.next_followup_at.isoformat() if p.next_followup_at else None}


@vacalls_bp.route("/api/va/calls/queue", methods=["POST"])
@_ratelimit
def va_queue():
    """The whole list, in the order the desk will deal it: due follow-ups
    first, then fresh cards by tier and category rank."""
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    now_naive = _now().replace(tzinfo=None)
    workable = CallProspect.status.in_(WORKABLE_STATUSES)
    due = (CallProspect.query.filter(workable, CallProspect.next_followup_at.isnot(None),
                                     CallProspect.next_followup_at <= now_naive)
           .order_by(CallProspect.next_followup_at.asc()).limit(60).all())
    later = (CallProspect.query.filter(workable, CallProspect.next_followup_at.isnot(None),
                                       CallProspect.next_followup_at > now_naive)
             .order_by(CallProspect.next_followup_at.asc()).limit(40).all())
    fresh = (CallProspect.query.filter(workable, CallProspect.next_followup_at.is_(None))
             .order_by(CallProspect.tier.asc(), _category_rank_sql().asc(),
                       CallProspect.category.asc(), CallProspect.created_at.asc())
             .limit(80).all())
    from sqlalchemy import func
    by_status = dict(db.session.query(CallProspect.status, func.count(CallProspect.id))
                     .group_by(CallProspect.status).all())
    fresh_total = CallProspect.query.filter(workable, CallProspect.next_followup_at.is_(None)).count()
    by_tier = dict(db.session.query(CallProspect.tier, func.count(CallProspect.id))
                   .filter(workable, CallProspect.next_followup_at.is_(None))
                   .group_by(CallProspect.tier).all())
    return jsonify({
        "due": [_queue_row(p) for p in due],
        "later": [_queue_row(p) for p in later],
        "fresh": [_queue_row(p) for p in fresh],
        "counts": {"due": len(due), "fresh": fresh_total,
                   "by_tier": {str(k): v for k, v in by_tier.items()},
                   "by_status": by_status, "total": CallProspect.query.count()},
        "stats": day_stats(),
    }), 200


@vacalls_bp.route("/api/admin/caller-stats", methods=["GET"])
@require_admin
def caller_stats(user_id):
    days = min(int(request.args.get("days", 7)), 60)
    since = (_now() - timedelta(days=days)).replace(tzinfo=None)
    attempts = CallAttempt.query.filter(CallAttempt.created_at >= since).all()
    by_outcome = {}
    for a in attempts:
        by_outcome[a.outcome] = by_outcome.get(a.outcome, 0) + 1
    seg = {}
    for a in attempts:
        p = db.session.get(CallProspect, a.prospect_id)
        key = (p.category if p else "?") or "?"
        s = seg.setdefault(key, {"calls": 0, "interested": 0})
        s["calls"] += 1
        if a.outcome in WIN_OUTCOMES:
            s["interested"] += 1
    statuses = {}
    for st, in db.session.query(CallProspect.status).all():
        statuses[st] = statuses.get(st, 0) + 1
    return jsonify({"days": days, "attempts": len(attempts),
                    "by_outcome": by_outcome, "by_segment": seg,
                    "pipeline": statuses}), 200


# ---------------------------------------------------------------------------
# Morning digest — yesterday's desk activity to the admin (SMS + email)
# ---------------------------------------------------------------------------

def send_caller_digest(app):
    """Daily summary of Call Desk activity to ADMIN_PHONE / ADMIN_EMAIL.

    The load-bearing part is the INTERESTED list: every interested Tier 1
    deserves a personal follow-up call the same day. Silent when the desk
    saw no activity and nothing is awaiting follow-up.
    """
    with app.app_context():
        day_start = _eastern_day_start()
        prev_start = day_start - timedelta(days=1)
        attempts = CallAttempt.query.filter(
            CallAttempt.created_at >= prev_start,
            CallAttempt.created_at < day_start,
            CallAttempt.outcome != "skip").all()
        interested = (CallProspect.query
                      .filter(CallProspect.status.in_(("interested", "vendor_listed")))
                      .order_by(CallProspect.tier.asc(),
                                CallProspect.last_called_at.desc())
                      .limit(15).all())
        if not attempts and not interested:
            logger.info("caller digest: no activity, skipping send")
            return

        by = {}
        for a in attempts:
            by[a.outcome] = by.get(a.outcome, 0) + 1
        talked = by.get("interested", 0) + by.get("sent_link", 0) + \
            by.get("vendor_listed", 0) + by.get("not_interested", 0) + \
            by.get("converted", 0)
        hot = sum(by.get(o, 0) for o in WIN_OUTCOMES)

        sms_lines = ["Umuve Call Desk yesterday: {} calls, {} conversations, "
                     "{} interested.".format(len(attempts), talked, hot)]
        if interested:
            sms_lines.append("Awaiting YOUR follow-up:")
            for p in interested[:5]:
                sms_lines.append("T{} {} {}".format(p.tier, p.company, p.phone))
            if len(interested) > 5:
                sms_lines.append("+{} more in the email.".format(len(interested) - 5))
        admin_phone = os.environ.get("ADMIN_PHONE", "").strip()
        if admin_phone:
            import sms_service
            sms_service.send_sms(admin_phone, "\n".join(sms_lines))

        admin_email = os.environ.get("ADMIN_EMAIL", "").strip()
        if admin_email:
            rows = "".join(
                "<tr><td style='padding:6px 10px'>T{}</td>"
                "<td style='padding:6px 10px'><b>{}</b></td>"
                "<td style='padding:6px 10px'>{}</td>"
                "<td style='padding:6px 10px'>{}</td>"
                "<td style='padding:6px 10px'>{}</td></tr>".format(
                    p.tier, p.company, p.phone, p.category or "",
                    (p.last_note or "").replace("<", "&lt;")[:120])
                for p in interested) or "<tr><td>none yet</td></tr>"
            outcome_bits = ", ".join("{}: {}".format(k, v)
                                     for k, v in sorted(by.items())) or "no calls"
            html = (
                "<h2>Call Desk — yesterday</h2>"
                "<p>{} calls logged ({}).</p>"
                "<h3>Interested — call them back today</h3>"
                "<table border='0' cellspacing='0' "
                "style='border-collapse:collapse;font-size:14px'>{}</table>"
            ).format(len(attempts), outcome_bits, rows)
            try:
                from email_service import send_email
                send_email(admin_email, "Call Desk digest — {} calls, {} interested".format(
                    len(attempts), hot), html)
            except Exception:
                logger.exception("caller digest email failed")


# ---------------------------------------------------------------------------
# Pages + assets
# ---------------------------------------------------------------------------

def _no_cache(resp):
    resp.headers["Cache-Control"] = "no-cache, must-revalidate"
    return resp


@vacalls_bp.route("/va/calls", methods=["GET"])
def calls_page():
    return _no_cache(Response(CALLS_HTML, mimetype="text/html"))


@vacalls_bp.route("/va/calls.css", methods=["GET"])
def calls_css():
    return _no_cache(Response(CALLS_CSS, mimetype="text/css"))


@vacalls_bp.route("/va/calls.js", methods=["GET"])
def calls_js():
    return _no_cache(Response(CALLS_JS, mimetype="application/javascript"))


CALLS_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<meta name="robots" content="noindex, nofollow" />
<meta name="theme-color" content="#0B0E12" />
<title>Umuve — Call Desk</title>
<link rel="stylesheet" href="/va/app.css?v=4" />
<link rel="stylesheet" href="/va/calls.css?v=27" />
<link rel="manifest" href="/static/desk-manifest.json" />
</head>
<body>
<div id="app">
  <section id="gate" class="gate">
    <div class="gatewrap">
      <img class="brand-hero rv" src="/static/brand-logo.png" alt="Umuve" /><div class="eyebrow rv">Internal · VA suite</div>
      <h1 class="display" id="display-gate" aria-label="Call Desk">CALL&nbsp;DESK</h1>
      <p class="sub rv">One card at a time. Tap the number, make the call, tap what happened.</p>
      <form id="gate-form" autocomplete="on" class="rv">
        <label class="lbl" for="g-email">Email</label>
        <input id="g-email" type="email" autocomplete="username" placeholder="you@goumuve.com" />
        <label class="lbl" for="g-pass">Password</label>
        <input id="g-pass" type="password" autocomplete="current-password" placeholder="Your password" />
        <button class="btn" type="submit">Sign in</button>
        <p id="gate-err" class="err" hidden></p>
      </form>
      <details class="gate-alt rv" id="gate-alt">
        <summary>Have an access code instead?</summary>
        <form id="gate-code-form" autocomplete="off">
          <input id="code" type="password" autocomplete="off" placeholder="Access code" />
          <input id="code-name" type="text" autocomplete="off" placeholder="Your first name" />
          <button class="btn btn-alt" type="submit">Open with the code</button>
        </form>
      </details>
      <p class="hint rv">No account yet? Ask Shamar to add you.</p>
    </div>
  </section>

  <section id="tool" class="tool" hidden>
    <header class="bar">
      <a class="back" href="/va" aria-label="Back to VA tools">←</a>
      <div class="brand"><img class="brand-mark" src="/static/brand-logo.png" alt="" /><div class="wordmark">CALL&nbsp;DESK</div></div>
      <div class="bar-sub" id="daybar">—</div>
      <button class="who who-btn" id="who" type="button" hidden title="Account"></button>
      <button class="clock" id="clock-chip" type="button" aria-label="Time clock"><span class="ck-dot"></span><span id="clock-label">Clock in</span></button>
      <button class="back" id="queue-toggle" type="button" aria-label="Your queue">☰</button>
      <button class="back" id="search-toggle" type="button" aria-label="Find a business">⌕</button>
    </header>
    <div class="statsbar" id="daybar2">—</div>
    <div id="callstrip" class="callstrip" hidden>
      <div class="cs-dot"></div>
      <div class="cs-txt"><div class="cs-who" id="cs-who">—</div><div class="cs-state" id="cs-state">Calling…</div></div>
      <div class="cs-time" id="cs-time"></div>
      <button class="cs-btn" id="cs-keypad" type="button" title="Press 2 for sales, dial an extension">Keypad</button>
      <button class="cs-btn" id="cs-mute" type="button">Mute</button>
      <button class="cs-btn cs-hang" id="cs-hang" type="button">Hang up</button>
    </div>

    <div class="body desk" id="deck">
      <div class="col-main">
        <div id="searchbox" hidden>
          <input id="search-q" type="search" autocomplete="off"
                 placeholder="Someone calling back? Type their name, city, or number" />
          <div id="search-results"></div>
        </div>
        <div id="acctbox" class="deskcard" hidden>
          <div class="qb-head">
            <div><div class="qb-t">Your account</div><div class="qb-sub" id="ac-sub">—</div></div>
            <button type="button" class="si-btn" id="acct-close">Back to the card</button>
          </div>
          <form id="pw-form" class="qb-addform" autocomplete="on">
            <input id="pw-cur" type="password" autocomplete="current-password" placeholder="Current password" required />
            <input id="pw-new" type="password" autocomplete="new-password" placeholder="New password (8+ characters)" required minlength="8" />
            <button class="si-btn" type="submit">Change password</button>
          </form>
          <p class="qb-sub" id="ac-note" hidden></p>
          <p class="qb-status" id="ac-status" hidden></p>
          <button type="button" class="tb-btn out" id="sign-out">Sign out</button>
        </div>
        <div id="timebox" class="deskcard" hidden>
          <div class="qb-head">
            <div><div class="qb-t">Your hours</div><div class="qb-sub" id="tb-sub">—</div></div>
            <button type="button" class="si-btn" id="time-close">Back to the card</button>
          </div>
          <div class="tb-name" id="tb-name" hidden>
            <input id="tb-name-input" type="text" autocomplete="off" placeholder="Your first name (once)" />
            <button type="button" class="si-btn" id="tb-name-save">Save</button>
          </div>
          <div class="tb-tiles">
            <div class="tb-tile"><div class="tb-k">Today</div><div class="tb-v" id="tb-today">0:00</div></div>
            <div class="tb-tile"><div class="tb-k">This week</div><div class="tb-v" id="tb-week">0:00</div></div>
            <div class="tb-tile"><div class="tb-k" id="tb-period-k">Pay period</div><div class="tb-v" id="tb-period">0:00</div></div>
          </div>
          <button type="button" class="tb-btn" id="tb-toggle">Clock in</button>
          <p class="qb-status" id="tb-status" hidden></p>
          <div class="tb-views"><button type="button" class="kit-tab is-on" id="tb-mine">My shifts</button><button type="button" class="kit-tab" id="tb-team">Everyone</button></div>
          <div id="tb-team-totals" hidden></div>
          <div id="tb-list"></div>
        </div>
        <div id="queuebox" class="deskcard" hidden>
          <div class="qb-head">
            <div><div class="qb-t">Your queue</div><div class="qb-sub" id="qb-sub">—</div></div>
            <button type="button" class="si-btn" id="queue-close">Back to the card</button>
          </div>
          <div class="qb-tools">
            <label class="qb-load"><input type="file" id="qb-file" accept=".csv,text/csv" hidden /><span>Load a list (CSV)</span></label>
            <button type="button" class="qb-load" id="qb-add-toggle">Add a business</button>
          </div>
          <form id="qb-add" class="qb-addform" autocomplete="off" hidden>
            <input id="qa-company" type="text" placeholder="Business name" required />
            <input id="qa-phone" type="tel" inputmode="tel" placeholder="Phone" required />
            <input id="qa-city" type="text" placeholder="City" />
            <input id="qa-category" type="text" placeholder="What they do (e.g. property management, junk removal)" />
            <input id="qa-contact" type="text" placeholder="Contact name (optional)" />
            <input id="qa-why" type="text" placeholder="Why them / how they reached us (optional)" />
            <button class="si-btn" type="submit">Add and open the card</button>
          </form>
          <p class="qb-status" id="qb-status" hidden></p>
          <div id="qb-list"></div>
        </div>
        <div id="empty" class="deskcard" hidden>
          <div class="q-chip done" id="empty-chip">QUEUE CLEAR</div>
          <h2 class="co" id="empty-t">Nothing due right now</h2>
          <p class="whytext" id="empty-sub">Every prospect is either scheduled for a future touch or finished. Replies and callbacks are in the line panel.</p>
          <button type="button" class="si-btn" id="empty-load" hidden>Load a list or add a business</button>
        </div>

        <div id="card" class="deskcard" hidden>
          <div class="chiprow">
            <span class="chip tierchip" id="c-tier">T1</span>
            <span class="chip" id="c-cat">Category</span>
            <span class="chip followchip" id="c-follow" hidden>FOLLOW-UP</span>
          </div>
          <h2 class="co" id="c-company">Company</h2>
          <div class="meta" id="c-meta">City</div>
          <a class="dial" id="c-tel" href="#"><span class="dial-num" id="c-phone">(561) 000-0000</span><span class="dial-hint">tap to call</span></a>
          <a class="dial dial-direct" id="c-direct" href="#" hidden><span class="dial-num-sm" id="c-direct-num"></span><span class="dial-hint">direct line — skips the front desk</span></a>
          <div class="factrow"><div class="fact-k">Why them</div><div class="fact-v" id="c-why"></div></div>
          <div class="factrow"><div class="fact-k">Your angle</div><div class="fact-v" id="c-angle"></div></div>
          <p id="c-opener" hidden></p>
          <div class="kit" id="kit">
            <div class="kit-bar">
              <div class="kit-tabs" role="tablist">
                <button type="button" class="kit-tab is-on" data-k="track">Script</button>
                <button type="button" class="kit-tab" data-k="objections">Objections</button>
                <button type="button" class="kit-tab" data-k="answers">Answers</button>
                <button type="button" class="kit-tab" data-k="prices">Prices</button>
                <button type="button" class="kit-tab" data-k="lookup">Look up</button>
              </div>
              <button type="button" class="kit-side" id="kit-side" title="Switch between selling them and recruiting them">—</button>
            </div>
            <div class="kit-body" id="kit-body"><p class="kit-loading">Loading the kit…</p></div>
          </div>
          <div class="sendinfo">
            <div class="si-head">WHO DECIDES?</div>
            <p class="si-sub">Receptionist gave you a name or the boss's cell? Save it — it sticks to this card and their name goes on everything we send.</p>
            <div class="si-row">
              <input id="dm-name" type="text" autocomplete="off" placeholder="decision-maker's name" />
              <input id="dm-phone" type="tel" autocomplete="off" inputmode="tel" placeholder="their cell" />
              <button class="si-btn" id="dm-save-btn" type="button">Save</button>
            </div>
          </div>
          <div class="sendinfo">
            <div class="si-head">THEY SAID “SEND US SOMETHING”?</div>
            <p class="si-sub">The info pack goes out from the Umuve number/email — written so a receptionist can pass it straight to the boss.</p>
            <div class="si-row">
              <input id="si-phone" type="tel" autocomplete="off" inputmode="tel" placeholder="their cell (prefilled)" />
              <button class="si-btn" id="si-text-btn" type="button">Text it</button>
            </div>
            <div class="si-row">
              <input id="si-email" type="email" autocomplete="off" inputmode="email" placeholder="email address they gave you" />
              <button class="si-btn" id="si-email-btn" type="button">Email it</button>
            </div>
            <div class="rc-row">
              <div class="rc-l"><b>Rate card</b> - a one-page PDF with their name on it and today's prices</div>
              <div class="rc-btns">
                <button class="si-btn" id="rc-text-btn" type="button">Text the link</button>
                <button class="si-btn" id="rc-email-btn" type="button">Email the PDF</button>
                <button class="si-btn rc-prev" id="rc-prev-btn" type="button">Preview</button>
              </div>
            </div>
            <p class="si-status" id="si-status" hidden></p>
          </div>
          <div class="notewrap" id="c-lastnote" hidden></div>
          <label class="lbl" for="note">Note <span class="opt">(optional — sticks to this business)</span></label>
          <input id="note" type="text" autocomplete="off" placeholder="e.g. asked to call back Thursday" />
        </div>

        <label class="textopt" id="textopt" hidden>
          <input type="checkbox" id="send-text" />
          <span><b>Text them after I tap</b> — the right follow-up goes out from the Umuve number (interested → partner info · on their vendor list → thanks + rates + booking number · no answer → who-we-are text)</span>
        </label>

        <div id="callback" class="callback" hidden>
          <div class="cb-l">They asked you to call back</div>
          <div class="cb-row">
            <button type="button" class="cb" data-p="tomorrow_am">Tomorrow 9am</button>
            <button type="button" class="cb" data-p="tomorrow_pm">Tomorrow 2pm</button>
            <button type="button" class="cb" data-p="two_days">In 2 days</button>
            <button type="button" class="cb" data-p="next_week">Next week</button>
            <label class="cb cb-pick"><span>Pick a time</span><input type="datetime-local" id="cb-at" /></label>
          </div>
        </div>
        <div id="outcomes" class="outcomes" hidden>
          <button class="oc oc-good" data-o="interested">Interested</button>
          <button class="oc oc-good" data-o="sent_link">Sent the link</button>
          <button class="oc oc-good" data-o="vendor_listed">On their vendor list</button>
          <button class="oc" data-o="voicemail">Voicemail</button>
          <button class="oc" data-o="no_answer">No answer</button>
          <button class="oc oc-bad" data-o="not_interested">Not interested</button>
          <button class="oc oc-bad" data-o="bad_number">Bad number</button>
          <button class="oc-skip" data-o="skip">Skip for now — deal me another</button>
        </div>

        <p id="desk-toast" class="toast" hidden></p>
        <p id="desk-err" class="err" hidden></p>
      </div>

      <aside class="line" id="line" aria-label="Desk line">
        <div class="ln-head">
          <div class="ln-title">
            <div class="ln-who" id="ln-who">Desk line</div>
          </div>
          <button class="ln-btn" id="inbox-toggle" type="button" aria-label="Replies and callbacks">Replies<span class="badge" id="inbox-badge" hidden>0</span></button>
          <div class="ln-status"><span class="ln-num" id="th-num"></span></div>
          <div class="ln-tools" id="ln-tools">
            <button class="ln-btn ln-call" id="desk-call-btn" type="button" hidden>Call</button>
            <button class="ln-btn" id="pd-toggle" type="button" hidden title="Power dial: the next card dials itself after you log an outcome; answering machines get your recorded voicemail">Power</button>
            <button class="ln-btn" id="cp-toggle" type="button" hidden title="Copilot: live transcript, objection cues while they talk, and a written-up note after the call. The other side hears a recording notice.">Copilot</button>
          </div>
        </div>
        <div class="pdbar" id="pdbar" hidden>
          <div class="pd-txt" id="pd-txt">Power dial is on</div>
          <div class="pd-btns">
            <button type="button" class="pd-btn" id="pd-record">Record voicemail</button>
            <button type="button" class="pd-btn" id="pd-play" hidden>Play</button>
            <button type="button" class="pd-btn pd-stop" id="pd-skip" hidden>Stop countdown</button>
          </div>
        </div>
        <div class="cp" id="cp" hidden>
          <div class="cp-cue" id="cp-cue" hidden>
            <div class="cp-cue-k">They just said</div>
            <div class="cp-cue-q" id="cp-cue-q"></div>
            <div class="cp-cue-k cp-cue-k2">Say this</div>
            <div class="cp-cue-r" id="cp-cue-r"></div>
          </div>
          <div class="cp-sum" id="cp-sum" hidden>
            <div class="cp-cue-k">Call summary</div>
            <div class="cp-sum-t" id="cp-sum-t"></div>
            <div class="cp-sum-btns">
              <button type="button" class="pd-btn" id="cp-use-note">Use as note</button>
              <button type="button" class="pd-btn cp-log" id="cp-log" hidden></button>
            </div>
          </div>
          <div class="cp-lines" id="cp-lines"></div>
        </div>
        <div class="ln-body" id="ln-thread">
          <div class="th-list" id="th-list"></div>
          <div class="th-empty" id="th-empty" hidden>
            <div class="th-empty-t">No texts or calls yet</div>
            <p>Send the first one below. Anything they text or call back lands here, on this card.</p>
          </div>
        </div>
        <div class="ln-body" id="inboxbox" hidden>
          <div class="ib-head"><span>Replies and callbacks</span><button class="ib-back" id="inbox-close" type="button" hidden>Back to this business</button></div>
          <div id="inbox-list"></div>
        </div>
        <div class="ln-foot" id="ln-foot">
          <div class="th-quick" id="th-quick">
            <button type="button" data-t="intro">Who we are</button>
            <button type="button" data-t="info">Info pack</button>
            <button type="button" data-t="followup">Follow-up</button>
          </div>
          <form id="th-form" class="th-form" autocomplete="off">
            <textarea id="th-input" rows="1" maxlength="640" placeholder="Text them — replies come back here"></textarea>
            <button class="th-send" type="submit">Send</button>
          </form>
        </div>
      </aside>
    </div>
  </section>
</div>
<div id="incoming" class="incoming" hidden>
  <div class="inc-card">
    <div class="inc-l">Incoming call on the desk line</div>
    <div class="inc-who" id="inc-who">—</div>
    <div class="inc-row">
      <button class="inc-btn inc-decline" id="inc-decline" type="button">Decline</button>
      <button class="inc-btn inc-answer" id="inc-answer" type="button">Answer</button>
    </div>
  </div>
</div>
<script src="/static/desk-crm.js?v=1"></script>
<script src="/static/desk-compliance.js?v=1"></script>
<script src="/static/desk-analytics.js?v=1"></script>
<script src="/static/desk-growth.js?v=1"></script>
<script src="/static/desk-inbound.js?v=1"></script>
<script src="/static/desk-sameday.js?v=1"></script>
<script src="/static/desk-enrich.js?v=1"></script>
<script src="/static/desk-dialpad.js?v=2"></script>
<script src="/static/desk-work.js?v=1"></script>
<script src="/va/calls.js?v=31"></script>
</body>
</html>
"""


CALLS_CSS = r"""/* Call Desk — layers over /va/app.css tokens */
[hidden]{display:none!important}
.deskcard{background:var(--surface);border:1px solid var(--line);border-radius:18px;
  padding:18px 18px 16px}
.chiprow{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}
.chip{font-family:var(--display);font-weight:700;font-size:11px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--muted);background:var(--raise);
  border:1px solid var(--line);border-radius:8px;padding:5px 9px}
.tierchip{color:var(--accent);border-color:rgba(255,106,44,.4)}
.followchip{color:#7FB8FF;border-color:rgba(127,184,255,.4)}
.q-chip{display:inline-block;font-family:var(--display);font-weight:700;font-size:11px;
  letter-spacing:.14em;color:var(--ok);border:1px solid rgba(61,214,140,.35);
  border-radius:8px;padding:5px 9px;margin-bottom:10px}
.co{font-family:var(--display);font-weight:800;font-size:clamp(22px,6vw,30px);
  letter-spacing:-.02em;line-height:1.05;margin:0 0 4px}
.meta{color:var(--faint);font-size:13px;margin-bottom:14px}
.dial{display:flex;flex-direction:column;align-items:center;gap:2px;text-decoration:none;
  background:var(--raise);border:1.5px solid rgba(255,106,44,.45);border-radius:16px;
  padding:16px 12px;margin:0 0 14px;transition:transform .06s,border-color .15s}
.dial:active{transform:scale(.985)}
.dial-num{font-family:var(--display);font-weight:900;color:var(--ink);
  font-size:clamp(28px,8.5vw,40px);letter-spacing:-.01em;font-variant-numeric:tabular-nums}
.dial-hint{font-family:var(--display);font-weight:600;font-size:10.5px;letter-spacing:.28em;
  text-transform:uppercase;color:var(--accent)}
.factrow{display:flex;gap:12px;padding:10px 0;border-top:1px solid var(--line)}
.fact-k{flex:none;width:72px;font-family:var(--display);font-weight:600;font-size:10px;
  letter-spacing:.16em;text-transform:uppercase;color:var(--faint);padding-top:2px}
.fact-v{color:var(--muted);font-size:13.5px;line-height:1.5}
.openerbox{border-top:1px solid var(--line);padding:10px 0 2px}
.openerbox summary{font-family:var(--display);font-weight:600;font-size:10px;
  letter-spacing:.16em;text-transform:uppercase;color:var(--accent);cursor:pointer;
  list-style:none}
.openerbox summary::before{content:"▸ "}
.openerbox[open] summary::before{content:"▾ "}
.openerbox p{color:var(--muted);font-size:14px;line-height:1.6;margin:10px 0 4px;
  border-left:2px solid rgba(255,106,44,.5);padding-left:12px}
.sendinfo{border-top:1px solid var(--line);padding:12px 0 4px;margin-top:2px}
.dial-direct{border-style:dashed;border-color:rgba(127,184,255,.5);padding:10px 12px;margin-top:-6px}
.dial-direct .dial-hint{color:#7FB8FF}
.dial-num-sm{font-family:var(--display);font-weight:800;color:var(--ink);
  font-size:clamp(19px,5.5vw,24px);letter-spacing:-.01em;font-variant-numeric:tabular-nums}
.si-status{color:var(--ok);font-size:12px;line-height:1.5;margin:2px 0 4px}
.si-head{font-family:var(--display);font-weight:600;font-size:10px;letter-spacing:.16em;
  text-transform:uppercase;color:var(--faint)}
.si-sub{color:var(--faint);font-size:12px;line-height:1.5;margin:5px 0 10px}
.si-row{display:flex;gap:8px;margin-bottom:8px}
.si-row input{flex:1;min-width:0;margin:0}
.si-btn{flex:none;padding:0 16px;font-family:var(--display);font-weight:700;font-size:13px;
  color:var(--accent);background:var(--raise);border:1px solid rgba(255,106,44,.45);
  border-radius:12px;cursor:pointer;transition:border-color .15s,transform .05s}
.si-btn:hover{border-color:var(--accent)}
.si-btn:active{transform:translateY(1px)}
.si-btn:disabled{opacity:.45;cursor:default}
.notewrap{margin-top:10px;padding:10px 12px;border-radius:10px;background:var(--raise);
  border:1px solid var(--line);color:var(--muted);font-size:13px;line-height:1.5}
.notewrap b{color:var(--faint);font-family:var(--display);font-weight:600;font-size:10px;
  letter-spacing:.14em;text-transform:uppercase;display:block;margin-bottom:3px}
.outcomes{display:grid;grid-template-columns:1fr 1fr;gap:9px}
.oc{padding:15px 8px;font-family:var(--display);font-weight:700;font-size:14.5px;
  letter-spacing:.01em;color:var(--ink);background:var(--surface);
  border:1px solid var(--line);border-radius:14px;cursor:pointer;
  transition:border-color .15s,transform .05s}
.oc:active{transform:translateY(1px)}
.oc-good{color:var(--ok);border-color:rgba(61,214,140,.35)}
.oc-good:hover{border-color:var(--ok)}
.oc-bad{color:#FF7A5C;border-color:rgba(255,122,92,.3)}
.oc-bad:hover{border-color:#FF7A5C}
.oc:hover{border-color:rgba(255,106,44,.45)}
.oc:disabled,.oc-skip:disabled{opacity:.45;cursor:default}
.oc-skip{grid-column:1 / -1;padding:12px;font-family:var(--display);font-weight:600;
  font-size:12.5px;letter-spacing:.06em;color:var(--faint);background:transparent;
  border:1px dashed var(--line);border-radius:12px;cursor:pointer}
.oc-skip:hover{color:var(--muted)}
.textopt{display:flex;gap:10px;align-items:flex-start;background:var(--surface);
  border:1px solid var(--line);border-radius:14px;padding:12px 14px;cursor:pointer}
.textopt input{width:18px;height:18px;margin:2px 0 0;accent-color:var(--accent);flex:none}
.textopt span{color:var(--muted);font-size:12.5px;line-height:1.5}
.textopt b{color:var(--ink);font-family:var(--display);font-weight:700;font-size:12.5px}
#searchbox input{margin-bottom:8px}
.sr{display:flex;align-items:center;gap:10px;width:100%;text-align:left;
  background:var(--surface);border:1px solid var(--line);border-radius:12px;
  padding:12px 14px;margin-bottom:7px;cursor:pointer;color:var(--ink)}
.sr:hover{border-color:rgba(255,106,44,.45)}
.sr-t{font-family:var(--display);font-weight:700;font-size:14.5px}
.sr-d{color:var(--faint);font-size:12px;margin-top:2px}
.sr-status{margin-left:auto;flex:none;font-family:var(--display);font-weight:600;
  font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--faint)}
.sr-none{color:var(--faint);font-size:13px;padding:6px 2px}
.toast{margin:0;padding:11px 14px;border-radius:12px;font-size:13.5px;
  background:rgba(61,214,140,.12);color:var(--ok);border:1px solid rgba(61,214,140,.35)}
@media (min-width:700px){
  .outcomes{grid-template-columns:1fr 1fr 1fr}
  .oc-skip{grid-column:1 / -1}
}

/* sign-in headline: fit the column at every width (app.css lets it bleed) */
.gate .gatewrap{max-width:520px}
.gate .display{font-size:clamp(40px,11vw,84px);margin-left:0;letter-spacing:-.03em;line-height:.95;
  overflow-wrap:anywhere;max-width:100%}
/* header + brand */
.brand{display:flex;align-items:center;gap:9px;min-width:0}
.brand-mark{width:30px;height:30px;object-fit:contain;flex:none}
.brand-hero{height:72px;width:auto;display:block;margin-bottom:18px}
.bar{gap:8px}
.bar .back{flex:none}
.bar-sub{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}
.statsbar{display:none;padding:6px 14px 7px;color:var(--faint);font-size:12px;border-bottom:1px solid var(--line);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dial-num-sm{display:flex;flex-direction:column;align-items:center;line-height:1.15}
.dn-name{font-size:.72em;color:var(--muted);font-weight:700;letter-spacing:0}
@media (max-width:640px){
  .bar{padding-left:10px;padding-right:10px;gap:6px}
  .bar .wordmark{font-size:12px;letter-spacing:.18em}
  .brand-mark{width:26px;height:26px}
  .bar-sub{display:none}
  .statsbar{display:block}
  /* was display:none — which made the account panel (change password, sign
     out) completely unreachable on a phone. Keep the button, drop the name. */
  /* .who's base rule is declared AFTER this block, so it wins at equal
     specificity — qualify with .bar or the name renders next to the initial */
  .bar .who{display:inline-flex;align-items:center;justify-content:center;
    width:34px;height:34px;padding:0;margin-right:0;font-size:0;
    border-color:var(--line);border-radius:999px}
  .bar .who::before{content:attr(data-initial);font-size:13px;font-weight:800;color:var(--muted)}
  .clock{padding:0 9px;margin-right:0}
  .bar .back{width:34px;height:34px;font-size:15px}
  .dial-num{font-size:clamp(26px,8.2vw,36px)}
  .dial-num-sm{font-size:clamp(17px,5.2vw,22px)}
  .dial-hint{letter-spacing:.18em;font-size:10px;text-align:center}
  .kit-bar{flex-wrap:wrap}
  .kit-side{width:100%;text-align:center}
  .ln-head{padding:10px 12px}
  .si-row{flex-wrap:wrap}
  .si-row input{flex:1 1 100%}
  .si-row .si-btn{flex:1 1 auto}
  .rc-btns .si-btn{flex:1 1 auto}
}
/* sign-in */
.gate-alt{margin-top:14px}
.gate-alt summary{cursor:pointer;color:var(--faint);font-size:12.5px;list-style:none}
.gate-alt summary::before{content:"▸ "}
.gate-alt[open] summary::before{content:"▾ "}
.gate-alt form{display:flex;flex-direction:column;gap:8px;margin-top:10px}
.btn-alt{background:var(--raise);color:var(--ink);border:1px solid var(--line)}
.who{font-family:var(--display);font-weight:700;font-size:11.5px;color:var(--faint);margin-right:8px;white-space:nowrap}
.who-btn{background:transparent;border:1px solid transparent;border-radius:8px;padding:6px 8px;cursor:pointer}
.who-btn:hover{border-color:var(--line);color:var(--muted)}
.qb-addform #pw-cur,.qb-addform #pw-new{grid-column:1 / -1}
/* desk line: two-pane desk, thread, inbox, dialer */
.col-main{display:contents}
.col-main>*{order:5}
#acctbox{order:0}#timebox{order:0}#queuebox{order:0}#searchbox{order:1}#empty{order:2}#card{order:3}
.desk.acct-open #card,.desk.acct-open #empty,.desk.acct-open #textopt,.desk.acct-open #callback,
.desk.acct-open #outcomes,.desk.acct-open #queuebox,.desk.acct-open #timebox{display:none}
.desk.time-open #card,.desk.time-open #empty,.desk.time-open #textopt,.desk.time-open #callback,
.desk.time-open #outcomes,.desk.time-open #queuebox{display:none}
.desk.queue-open #card,.desk.queue-open #empty,.desk.queue-open #textopt,.desk.queue-open #callback,
.desk.queue-open #outcomes{display:none}
.line{order:4;display:flex;flex-direction:column;background:var(--surface);
  border:1px solid var(--line);border-radius:18px;overflow:hidden;min-height:0}
.ln-head{display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:10px 14px;border-bottom:1px solid var(--line)}
.ln-status{flex:1 1 100%;display:flex;flex-wrap:wrap;gap:4px 14px;align-items:center;min-height:14px;
  font-size:11px;color:var(--faint);font-variant-numeric:tabular-nums}
.ln-status:empty{display:none}
.ln-tools{flex:1 1 100%;display:flex;gap:6px;flex-wrap:wrap;margin-top:2px}
.ln-tools:not(:has(button:not([hidden]))){display:none}
.ln-tools .ln-btn{flex:1 1 auto;text-align:center}
.ln-tools .ln-call{flex:2 1 auto}
.ln-title{min-width:0;flex:1}
.ln-who{font-family:var(--display);font-weight:800;font-size:15px;letter-spacing:-.01em;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ln-num{color:var(--faint);font-size:11px;white-space:nowrap}
.ln-btn{position:relative;flex:none;padding:8px 12px;font-family:var(--display);font-weight:700;
  font-size:12.5px;color:var(--ink);background:var(--raise);border:1px solid var(--line);
  border-radius:10px;cursor:pointer;transition:border-color .15s}
.ln-btn:hover{border-color:rgba(255,106,44,.45)}
.ln-call{color:var(--ok);border-color:rgba(61,214,140,.45);padding-left:26px}
.ln-call::before{content:"";position:absolute;left:11px;top:50%;width:8px;height:8px;margin-top:-4px;
  border-radius:50%;background:var(--ok)}
.badge{position:absolute;top:-7px;right:-7px;min-width:18px;height:18px;padding:0 5px;border-radius:9px;
  background:#7FB8FF;color:#0B0E12;font-family:var(--display);font-weight:800;font-size:10.5px;
  line-height:18px;text-align:center}
.ln-body{flex:1;min-height:0;overflow-y:auto;padding:12px 14px;scroll-behavior:smooth}
#ln-thread{max-height:360px}
.th-list{display:flex;flex-direction:column;gap:6px}
.msg{max-width:86%;display:flex;flex-direction:column;gap:2px}
.msg-in{align-self:flex-start}
.msg-out{align-self:flex-end;align-items:flex-end}
.msg-b{padding:9px 12px;border-radius:14px;font-size:13.5px;line-height:1.45;color:var(--ink);
  white-space:pre-wrap;word-break:break-word;background:var(--raise);border:1px solid var(--line)}
.msg-in .msg-b{background:rgba(127,184,255,.12);border-color:rgba(127,184,255,.35);border-bottom-left-radius:5px}
.msg-out .msg-b{border-bottom-right-radius:5px}
.msg-call .msg-b{background:transparent;border-style:dashed}
.msg-call-l{font-family:var(--display);font-weight:700;font-size:11.5px;letter-spacing:.06em;
  color:var(--muted);margin-bottom:2px}
.msg-m{font-size:10.5px;color:var(--faint);padding:0 4px}
.msg-rec{display:inline-block;margin-top:4px;color:#7FB8FF;font-size:12.5px}
.th-empty{padding:18px 6px;text-align:center}
.th-empty-t{font-family:var(--display);font-weight:800;font-size:15px;margin-bottom:4px}
.th-empty p{color:var(--faint);font-size:12.5px;line-height:1.5;margin:0}
.ib-head{display:flex;align-items:center;justify-content:space-between;gap:8px;
  font-family:var(--display);font-weight:600;font-size:10px;letter-spacing:.16em;
  text-transform:uppercase;color:var(--faint);margin:2px 0 10px}
.ib-back{font-family:var(--display);font-weight:600;font-size:11px;letter-spacing:.02em;text-transform:none;
  color:var(--accent);background:transparent;border:0;cursor:pointer;padding:0}
.sr-w{min-width:0;flex:1}
.sr-d{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sr-unread{border-color:rgba(127,184,255,.55)}
.sr-unread .sr-t::before{content:"";display:inline-block;width:7px;height:7px;border-radius:50%;
  background:#7FB8FF;margin-right:7px;vertical-align:2px}
.ln-foot{border-top:1px solid var(--line);padding:10px 14px 12px;background:var(--surface)}
.th-quick{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}
.th-quick button{font-family:var(--display);font-weight:600;font-size:11.5px;color:var(--muted);
  background:transparent;border:1px solid var(--line);border-radius:999px;padding:5px 11px;cursor:pointer;
  transition:border-color .15s,color .15s}
.th-quick button:hover{color:var(--ink);border-color:rgba(255,106,44,.45)}
.th-quick button:disabled{opacity:.4;cursor:default}
.th-form{display:flex;gap:8px;align-items:flex-end}
.th-form textarea{flex:1;min-width:0;margin:0;resize:none;min-height:44px;max-height:140px;
  font:inherit;font-size:14px;line-height:1.4;color:var(--ink);background:var(--raise);
  border:1px solid var(--line);border-radius:12px;padding:11px 12px}
.th-form textarea:focus{outline:none;border-color:rgba(255,106,44,.6)}
.th-send{flex:none;height:44px;padding:0 16px;font-family:var(--display);font-weight:800;font-size:13.5px;
  color:#0B0E12;background:var(--accent);border:0;border-radius:12px;cursor:pointer}
.th-send:disabled{opacity:.45;cursor:default}
.callstrip{display:flex;align-items:center;gap:10px;padding:10px 14px;background:var(--surface);
  border-bottom:1px solid var(--line)}
.cs-dot{width:10px;height:10px;border-radius:50%;background:var(--accent);flex:none}
.callstrip.live .cs-dot{background:var(--ok);animation:cs-pulse 1.6s ease-in-out infinite}
@keyframes cs-pulse{0%,100%{box-shadow:0 0 0 0 rgba(61,214,140,.55)}50%{box-shadow:0 0 0 7px rgba(61,214,140,0)}}
.cs-txt{min-width:0;flex:1}
.cs-who{font-family:var(--display);font-weight:800;font-size:14.5px;white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis}
.cs-state{font-size:11.5px;color:var(--faint)}
.cs-time{font-family:var(--display);font-weight:700;font-size:13px;color:var(--muted);
  font-variant-numeric:tabular-nums;min-width:38px;text-align:right}
.cs-btn{padding:8px 12px;font-family:var(--display);font-weight:700;font-size:12.5px;color:var(--ink);
  background:var(--raise);border:1px solid var(--line);border-radius:10px;cursor:pointer}
.cs-hang{color:#FF7A5C;border-color:rgba(255,122,92,.45)}
/* three buttons on a phone squeezed the company name down to "Palm ..." —
   tighten the buttons rather than lose who you are talking to */
@media(max-width:430px){
  .cs-btn{padding:8px 9px;font-size:12px}
  #cs-keypad{padding:8px 8px}
}
.callstrip.failed .cs-dot{background:#FF7A5C}
.callstrip.failed .cs-state{color:#FF7A5C;font-weight:600}
.incoming{position:fixed;inset:0;display:flex;align-items:flex-end;justify-content:center;
  background:rgba(11,14,18,.72);z-index:50;padding:16px}
.inc-card{width:100%;max-width:440px;background:var(--surface);border:1px solid rgba(127,184,255,.45);
  border-radius:20px;padding:18px 18px 16px}
.inc-l{font-family:var(--display);font-weight:600;font-size:10.5px;letter-spacing:.2em;
  text-transform:uppercase;color:#7FB8FF}
.inc-who{font-family:var(--display);font-weight:900;font-size:clamp(26px,8vw,36px);letter-spacing:-.01em;
  margin:6px 0 14px;font-variant-numeric:tabular-nums}
.inc-row{display:flex;gap:10px}
.inc-btn{flex:1;padding:15px;font-family:var(--display);font-weight:800;font-size:15px;border-radius:14px;
  cursor:pointer;border:1px solid var(--line);background:var(--raise);color:var(--ink)}
.inc-answer{background:var(--ok);border-color:var(--ok);color:#0B0E12}
.inc-decline{color:#FF7A5C;border-color:rgba(255,122,92,.45)}
@media (prefers-reduced-motion: reduce){.callstrip.live .cs-dot{animation:none}}
/* power dial */
#pd-toggle.on{color:var(--ok);border-color:rgba(61,214,140,.45)}
.pdbar{display:flex;align-items:center;gap:10px;padding:8px 14px;border-bottom:1px solid var(--line);
  background:rgba(61,214,140,.06)}
.pd-txt{flex:1;min-width:0;font-size:12px;color:var(--muted);line-height:1.4}
.pd-txt b{color:var(--ok);font-family:var(--display);font-weight:700}
.pd-txt.count b{color:var(--accent)}
.pd-btns{display:flex;gap:6px;flex:none}
.pd-btn{font-family:var(--display);font-weight:700;font-size:11.5px;color:var(--ink);background:var(--raise);
  border:1px solid var(--line);border-radius:9px;padding:6px 10px;cursor:pointer}
.pd-stop{color:#FF7A5C;border-color:rgba(255,122,92,.45)}
/* copilot */
#cp-toggle.on{color:#7FB8FF;border-color:rgba(127,184,255,.5)}
.cp{border-bottom:1px solid var(--line);padding:10px 14px;max-height:46%;overflow-y:auto;background:rgba(127,184,255,.04)}
.cp-cue{background:rgba(61,214,140,.1);border:1px solid rgba(61,214,140,.4);border-radius:12px;padding:10px 12px;margin-bottom:10px}
.cp-cue-k{font-family:var(--display);font-weight:700;font-size:10px;letter-spacing:.16em;text-transform:uppercase;color:var(--faint)}
.cp-cue-k2{margin-top:8px;color:var(--ok)}
.cp-cue-q{font-size:12.5px;color:var(--muted);font-style:italic;margin-top:2px}
.cp-cue-r{font-size:14px;line-height:1.5;color:var(--ink);margin-top:3px}
.cp-sum{background:var(--raise);border:1px solid rgba(127,184,255,.4);border-radius:12px;padding:10px 12px;margin-bottom:10px}
.cp-sum-t{font-size:13.5px;line-height:1.5;color:var(--ink);margin:4px 0 8px}
.cp-sum-btns{display:flex;gap:6px;flex-wrap:wrap}
.cp-log{color:var(--ok);border-color:rgba(61,214,140,.45)}
.cp-lines{display:flex;flex-direction:column;gap:4px}
.cp-ln{font-size:13px;line-height:1.45;color:var(--muted)}
.cp-ln b{font-family:var(--display);font-weight:700;font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;margin-right:6px;color:var(--faint)}
.cp-ln.them{color:var(--ink)}
.cp-ln.them b{color:#7FB8FF}
.cp-empty{font-size:12px;color:var(--faint)}
/* rate card */
.rc-row{display:flex;flex-direction:column;gap:8px;padding:10px 12px;margin:2px 0 8px;background:var(--raise);
  border:1px dashed rgba(255,106,44,.4);border-radius:12px}
.rc-l{color:var(--muted);font-size:12.5px;line-height:1.5}
.rc-l b{color:var(--ink);font-family:var(--display);font-weight:700}
.rc-btns{display:flex;gap:8px;flex-wrap:wrap}
.rc-btns .si-btn{padding:9px 12px;font-size:12.5px}
.rc-prev{color:var(--muted);border-color:var(--line)}
/* call kit */
.kit{border-top:1px solid var(--line);padding:10px 0 4px}
.kit-bar{display:flex;align-items:center;gap:8px;margin-bottom:10px}
.kit-tabs{display:flex;gap:4px;flex:1;min-width:0;overflow-x:auto;scrollbar-width:none}
.kit-tabs::-webkit-scrollbar{display:none}
.kit-tab{flex:none;font-family:var(--display);font-weight:700;font-size:12px;letter-spacing:.02em;
  color:var(--faint);background:transparent;border:1px solid transparent;border-radius:999px;
  padding:6px 11px;cursor:pointer;transition:color .15s,border-color .15s,background .15s}
.kit-tab:hover{color:var(--muted)}
.kit-tab.is-on{color:var(--ink);background:var(--raise);border-color:var(--line)}
.kit-side{flex:none;font-family:var(--display);font-weight:700;font-size:10.5px;letter-spacing:.12em;
  text-transform:uppercase;padding:6px 10px;border-radius:8px;cursor:pointer;background:transparent;
  border:1px dashed var(--line);color:var(--faint)}
.kit-side.supply{color:var(--ok);border-color:rgba(61,214,140,.4)}
.kit-side.demand{color:var(--accent);border-color:rgba(255,106,44,.4)}
.kit-body{min-height:60px}
.kit-loading,.kit-note{color:var(--faint);font-size:12px;line-height:1.5;margin:0 0 8px}
.kt-step{display:grid;grid-template-columns:78px 1fr;gap:10px;padding:8px 0;border-top:1px solid var(--line)}
.kt-step:first-child{border-top:0;padding-top:0}
.kt-k{font-family:var(--display);font-weight:700;font-size:10px;letter-spacing:.16em;text-transform:uppercase;
  color:var(--accent);padding-top:3px}
.kt-v{color:var(--ink);font-size:13.5px;line-height:1.55}
.kt-v ol{margin:0;padding-left:18px}
.kt-v li{margin:0 0 4px}
.kt-v li:last-child{margin:0}
.kt-obj{border-top:1px solid var(--line)}
.kt-obj summary{list-style:none;cursor:pointer;padding:9px 0;font-family:var(--display);font-weight:700;
  font-size:13.5px;color:var(--ink);display:flex;gap:8px;align-items:baseline}
.kt-obj summary::-webkit-details-marker{display:none}
.kt-obj summary::before{content:"“";color:var(--faint);font-family:Georgia,serif;font-size:18px;line-height:0}
.kt-obj p{margin:0 0 10px;padding-left:12px;border-left:2px solid rgba(61,214,140,.5);
  color:var(--muted);font-size:13.5px;line-height:1.55}
.kt-ans{display:grid;grid-template-columns:110px 1fr;gap:8px 12px;font-size:13px;line-height:1.5}
.kt-ans dt{font-family:var(--display);font-weight:700;color:var(--ink);font-size:12.5px;padding-top:1px}
.kt-ans dd{margin:0;color:var(--muted)}
.kt-price{display:grid;grid-template-columns:1fr 1fr;gap:4px 16px}
.kt-price div{display:flex;justify-content:space-between;gap:8px;padding:6px 0;border-bottom:1px dashed var(--line);
  font-size:13px;color:var(--muted)}
.kt-price b{font-family:var(--display);font-weight:800;color:var(--ink);font-variant-numeric:tabular-nums}
.kt-links{display:flex;flex-wrap:wrap;gap:8px}
.kt-links a{font-family:var(--display);font-weight:700;font-size:12.5px;color:var(--ink);text-decoration:none;
  background:var(--raise);border:1px solid var(--line);border-radius:10px;padding:9px 12px}
.kt-links a:hover{border-color:rgba(255,106,44,.45)}
/* time clock */
.clock{display:inline-flex;align-items:center;gap:7px;height:38px;padding:0 12px;margin-right:6px;
  font-family:var(--display);font-weight:700;font-size:12px;color:var(--muted);background:var(--surface);
  border:1px solid var(--line);border-radius:12px;cursor:pointer;white-space:nowrap;font-variant-numeric:tabular-nums}
.clock.on{color:var(--ok);border-color:rgba(61,214,140,.45)}
.ck-dot{width:8px;height:8px;border-radius:50%;background:var(--faint)}
.clock.on .ck-dot{background:var(--ok);box-shadow:0 0 0 3px rgba(61,214,140,.18)}
.tb-name{display:flex;gap:8px;margin-bottom:12px}
.tb-name input{flex:1;margin:0}
.tb-tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:12px}
.tb-tile{background:var(--raise);border:1px solid var(--line);border-radius:12px;padding:10px 12px}
.tb-k{font-family:var(--display);font-weight:600;font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--faint)}
.tb-v{font-family:var(--display);font-weight:900;font-size:clamp(20px,5vw,26px);letter-spacing:-.01em;
  font-variant-numeric:tabular-nums;margin-top:2px}
.tb-btn{width:100%;padding:14px;font-family:var(--display);font-weight:800;font-size:15px;border-radius:14px;
  cursor:pointer;border:1px solid rgba(61,214,140,.45);background:transparent;color:var(--ok);margin-bottom:10px}
.tb-btn.out{color:#FF7A5C;border-color:rgba(255,122,92,.45)}
.tb-btn:disabled{opacity:.45;cursor:default}
.tb-row{display:flex;align-items:center;gap:10px;padding:9px 2px;border-bottom:1px solid var(--line);font-size:13px}
.tb-row .d{font-family:var(--display);font-weight:700;min-width:84px}
.tb-row .t{color:var(--muted);flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tb-row .h{font-family:var(--display);font-weight:800;font-variant-numeric:tabular-nums}
.tb-row .c{color:var(--faint);font-size:11.5px;min-width:56px;text-align:right}
.tb-row.open .h{color:var(--ok)}
.tb-views{display:flex;gap:4px;margin:2px 0 8px}
.tb-who{font-family:var(--display);font-weight:600;font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--faint);min-width:56px}
.tb-tot{display:flex;gap:14px;align-items:baseline;padding:8px 2px;border-bottom:1px solid var(--line);font-size:13px}
.tb-tot b{font-family:var(--display);font-weight:800;font-size:15px}
.tb-tot span{color:var(--muted)}
@media (max-width:480px){.clock #clock-label{display:none}.clock{padding:0 10px}}
/* queue panel */
.qb-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin-bottom:12px}
.qb-t{font-family:var(--display);font-weight:800;font-size:20px;letter-spacing:-.02em}
.qb-sub{color:var(--faint);font-size:12.5px;margin-top:2px}
.qb-tools{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}
.qb-load{display:inline-flex;align-items:center;font-family:var(--display);font-weight:700;font-size:12.5px;
  color:var(--ink);background:var(--raise);border:1px dashed var(--line);border-radius:10px;padding:9px 12px;
  cursor:pointer;transition:border-color .15s}
.qb-load:hover{border-color:rgba(255,106,44,.45)}
.qb-addform{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px}
.qb-addform input{margin:0;min-width:0}
.qb-addform #qa-category,.qb-addform #qa-why,.qb-addform button{grid-column:1 / -1}
.qb-status{color:var(--ok);font-size:12.5px;line-height:1.5;margin:0 0 10px}
.qb-status.err{color:#FF7A5C}
.qb-sec{font-family:var(--display);font-weight:600;font-size:10px;letter-spacing:.16em;text-transform:uppercase;
  color:var(--faint);margin:12px 0 6px;display:flex;justify-content:space-between}
.qb-sec:first-child{margin-top:0}
.qr{display:flex;align-items:center;gap:10px;width:100%;text-align:left;background:transparent;
  border:0;border-bottom:1px solid var(--line);padding:9px 2px;cursor:pointer;color:var(--ink)}
.qr:hover .qr-t{color:var(--accent)}
.qr-tier{flex:none;font-family:var(--display);font-weight:700;font-size:10.5px;color:var(--accent);
  border:1px solid rgba(255,106,44,.4);border-radius:6px;padding:2px 5px;min-width:24px;text-align:center}
.qr-w{min-width:0;flex:1}
.qr-t{font-family:var(--display);font-weight:700;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.qr-d{color:var(--faint);font-size:11.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.qr-s{flex:none;font-family:var(--display);font-weight:600;font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--faint)}
.qr-s.due{color:#7FB8FF}
/* callback scheduler */
.callback{background:var(--surface);border:1px dashed rgba(127,184,255,.45);border-radius:14px;padding:11px 12px}
.cb-l{font-family:var(--display);font-weight:600;font-size:10px;letter-spacing:.16em;text-transform:uppercase;
  color:#7FB8FF;margin-bottom:8px}
.cb-row{display:flex;flex-wrap:wrap;gap:6px}
.cb{font-family:var(--display);font-weight:700;font-size:12.5px;color:var(--ink);background:var(--raise);
  border:1px solid var(--line);border-radius:10px;padding:8px 11px;cursor:pointer;transition:border-color .15s}
.cb:hover{border-color:#7FB8FF}
.cb:disabled{opacity:.45;cursor:default}
.cb-pick{position:relative;overflow:hidden;color:var(--muted)}
.cb-pick input{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%}
/* phones: the line is a bottom sheet — header always visible, tap to open */
@media (max-width:959px){
  .body.desk{padding-bottom:96px}
  .line{position:fixed;left:0;right:0;bottom:0;z-index:40;border-radius:18px 18px 0 0;
    border-bottom:0;max-height:78vh;box-shadow:0 -12px 40px rgba(0,0,0,.55)}
  .line .ln-head{cursor:pointer;padding-right:44px}
  .line .ln-head::after{content:"";position:absolute;right:18px;top:50%;width:9px;height:9px;
    margin-top:-7px;border-right:2px solid var(--faint);border-bottom:2px solid var(--faint);
    transform:rotate(-135deg);transition:transform .18s}
  .line.open .ln-head::after{transform:rotate(45deg);margin-top:-3px}
  .line:not(.open) .ln-body,.line:not(.open) .ln-foot{display:none}
  .ln-head{position:relative}
  #ln-thread{max-height:none}
}
/* wide screens: card on the left, the line pinned on the right */
@media (min-width:960px){
  #app{max-width:1240px;overflow:visible}
  .bar{max-width:1240px;width:100%;margin:0 auto}
  .body.desk{display:grid;grid-template-columns:minmax(0,720px) minmax(380px,460px);gap:20px;
    justify-content:center;align-items:start;width:100%}
  .col-main{display:flex;flex-direction:column;gap:14px;min-width:0}
  #acctbox{order:0}#timebox{order:0}#queuebox{order:0}#searchbox{order:1}#empty{order:2}#card{order:3}
  .line{position:sticky;top:16px;height:calc(100vh - 32px);max-height:900px}
  #ln-thread{max-height:none}
  .outcomes{grid-template-columns:1fr 1fr 1fr}
  .oc-skip{grid-column:1 / -1}
}
"""


CALLS_JS = r"""(function(){
  var KEY = "umuve_coach_code";      // legacy shared code across the VA suite
  var VA_KEY = "umuve_va_name";
  var JWT_KEY = "umuve_desk_jwt";
  var ME_KEY = "umuve_desk_me";
  var flags = {};
  function jwt(){ return localStorage.getItem(JWT_KEY) || ""; }
  function me(){ try { return JSON.parse(localStorage.getItem(ME_KEY) || "null"); } catch(e){ return null; } }
  function isManager(){ var m = me(); return !!(m && m.is_manager); }
  var gate = document.getElementById("gate");
  var tool = document.getElementById("tool");
  var gateErr = document.getElementById("gate-err");
  var deskErr = document.getElementById("desk-err");
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var current = null;
  var busy = false;

  function splitChars(el){
    if(!el || el.dataset.split) return;
    el.dataset.split = "1";
    var text = el.textContent;
    el.textContent = "";
    for(var i = 0; i < text.length; i++){
      var s = document.createElement("span");
      s.className = "ch";
      s.textContent = text[i] === " " ? " " : text[i];
      el.appendChild(s);
    }
  }
  function reveal(scope){
    if(reduced){
      scope.querySelectorAll(".rv,.display .ch").forEach(function(el){ el.classList.add("in"); });
      return;
    }
    scope.querySelectorAll(".display").forEach(splitChars);
    scope.querySelectorAll(".display .ch").forEach(function(c, i){
      setTimeout(function(){ c.classList.add("in"); }, 40 + i * 26);
    });
    scope.querySelectorAll(".rv").forEach(function(b, i){
      setTimeout(function(){ b.classList.add("in"); }, 140 + i * 65);
    });
  }

  function code(){ return localStorage.getItem(KEY) || ""; }
  function vaName(){ var m = me(); return (m && m.name) || localStorage.getItem(VA_KEY) || ""; }
  function signedIn(){ return !!jwt() || !!code(); }
  function showTool(){
    gate.hidden = true; tool.hidden = false;
    var who = document.getElementById("who"); var m = me();
    var whoName = (m && m.name) ? m.name : vaName();
    if(whoName){
      who.textContent = whoName + (m && m.is_manager ? " · manager" : "");
      // Phones hide the name for space; the button survives as an initial so
      // "Your account" (change password, sign out) stays reachable there.
      who.setAttribute("data-initial", whoName.trim().charAt(0).toUpperCase());
      who.hidden = false;
    } else { who.hidden = true; }
    syncRoleUI();
    deskBoot();
  }
  function signOut(msg){
    localStorage.removeItem(JWT_KEY); localStorage.removeItem(ME_KEY); localStorage.removeItem(KEY);
    showGate(msg);
  }
  function showGate(msg){
    tool.hidden = true; gate.hidden = false; reveal(gate);
    if(msg && gateErr){ gateErr.textContent = msg; gateErr.hidden = false; }
    var c = document.getElementById("g-email"); if(c) c.focus();
  }

  var gateForm = document.getElementById("gate-form");
  if(gateForm){
    gateForm.addEventListener("submit", function(e){
      e.preventDefault();
      var email = document.getElementById("g-email").value.trim();
      var pass = document.getElementById("g-pass").value;
      if(!email || !pass){ gateErr.textContent = "Enter your email and password."; gateErr.hidden = false; return; }
      var btn = gateForm.querySelector("button"); btn.disabled = true;
      fetch("/api/desk/login", {method: "POST", headers: {"Content-Type": "application/json"},
                                 body: JSON.stringify({email: email, password: pass})})
        .then(function(r){ return r.json().then(function(j){ return {status: r.status, body: j}; }); })
        .then(function(r){
          btn.disabled = false;
          if(r.status !== 200){ gateErr.textContent = (r.body && r.body.error) || "Sign-in failed."; gateErr.hidden = false; return; }
          localStorage.setItem(JWT_KEY, r.body.token);
          localStorage.setItem(ME_KEY, JSON.stringify({name: r.body.name, full_name: r.body.full_name, email: r.body.email, role: r.body.role, is_manager: r.body.is_manager}));
          localStorage.setItem(VA_KEY, r.body.name || "");
          localStorage.removeItem(KEY);
          gateErr.hidden = true;
          showTool(); fetchNext();
        }).catch(function(){ btn.disabled = false; gateErr.textContent = "No connection — try again."; gateErr.hidden = false; });
    });
  }
  var gateCodeForm = document.getElementById("gate-code-form");
  if(gateCodeForm){
    gateCodeForm.addEventListener("submit", function(e){
      e.preventDefault();
      var v = document.getElementById("code").value.trim();
      var n = document.getElementById("code-name").value.trim();
      if(!v){ gateErr.textContent = "Enter the access code."; gateErr.hidden = false; return; }
      if(!n){ gateErr.textContent = "Enter your first name so your work is yours."; gateErr.hidden = false; return; }
      localStorage.setItem(KEY, v); localStorage.setItem(VA_KEY, n); localStorage.removeItem(JWT_KEY); localStorage.removeItem(ME_KEY);
      gateErr.hidden = true;
      showTool(); fetchNext();
    });
  }

  function post(path, body){
    var headers = {"Content-Type": "application/json"};
    if(jwt()) headers["Authorization"] = "Bearer " + jwt();
    else { body.code = code(); body.va_name = vaName(); }
    return fetch(path, {
      method: "POST",
      headers: headers,
      body: JSON.stringify(body)
    }).then(function(r){
      return r.json().then(function(j){ return {status: r.status, body: j}; });
    });
  }
  function applyFlags(){
    var off = function(id, on){ var el = document.getElementById(id); if(el && !on) el.hidden = true; };
    if(flags.power_dial === false){ off("pd-toggle", false); off("pdbar", false); }
    if(flags.copilot === false){ off("cp-toggle", false); }
    if(flags.rate_card === false){ var rc = document.querySelector(".rc-row"); if(rc) rc.hidden = true; }
    if(flags.queue_import === false){ var l = document.querySelector(".qb-tools"); if(l) l.hidden = true; }
    if(flags.passcode_login === false){ var alt = document.getElementById("gate-alt"); if(alt) alt.hidden = true; }
  }

  function fmtPhone(p){ return p; }

  function setDaybar(stats){
    if(!stats) return;
    var txt = stats.calls_today + " calls today · " +
      stats.interested_today + " interested · " +
      (stats.due_now + stats.fresh) + " in queue";
    document.getElementById("daybar").textContent = txt;
    var d2 = document.getElementById("daybar2"); if(d2) d2.textContent = txt;
  }

  function render(resp){
    var card = document.getElementById("card");
    var empty = document.getElementById("empty");
    var outcomes = document.getElementById("outcomes");
    var textopt = document.getElementById("textopt");
    deskErr.hidden = true;
    setDaybar(resp.stats);
    if(resp.empty || !resp.card){
      card.hidden = true; outcomes.hidden = true; textopt.hidden = true; empty.hidden = false;
      var emptyLoad = document.getElementById("empty-load");
      if(!resp.total){
        document.getElementById("empty-chip").textContent = "QUEUE EMPTY";
        document.getElementById("empty-t").textContent = "No businesses loaded yet";
        document.getElementById("empty-sub").textContent =
          "Nothing is in the queue. Load a call list (CSV) or add a business, and the first card deals itself.";
        emptyLoad.hidden = false;
      } else {
        document.getElementById("empty-chip").textContent = "QUEUE CLEAR";
        document.getElementById("empty-t").textContent = "Nothing due right now";
        var sub = (resp.scheduled || 0) + " scheduled for later, " + resp.total + " in the list.";
        if(resp.next_due){
          var d = new Date(resp.next_due + "Z");
          sub += " Next one comes due " + d.toLocaleString([], {weekday:"long", hour:"numeric", minute:"2-digit"}) + ".";
        }
        document.getElementById("empty-sub").textContent = sub;
        emptyLoad.hidden = true;
      }
      current = null;
      window.__deskProspectId = null;
      loadThread(null);
      document.getElementById("callback").hidden = true;
      deskCallBtn.hidden = true;
      setLineWho(null);
      showInboxPane(true);
      return;
    }
    var c = resp.card;
    current = c;
    window.__deskProspectId = c.id;   // desk-dialpad.js saves contacts to this card
    empty.hidden = true;
    setLineWho(c.company);
    showThreadPane();
    document.getElementById("c-tier").textContent = "T" + c.tier;
    document.getElementById("c-cat").textContent = c.category || "Prospect";
    document.getElementById("c-follow").hidden = !c.is_followup;
    document.getElementById("c-company").textContent = c.company;
    var meta = [c.city, c.contact_name ? ("ask for " + c.contact_name) : null,
                c.attempts ? ("attempt " + (c.attempts + 1)) : null];
    document.getElementById("c-meta").textContent = meta.filter(Boolean).join(" · ");
    document.getElementById("c-phone").textContent = fmtPhone(c.phone);
    document.getElementById("c-tel").href = c.tel;
    document.getElementById("c-why").textContent = c.why || "—";
    document.getElementById("c-angle").textContent = c.angle || "—";
    document.getElementById("c-opener").textContent = c.opener || "";
    var noteEl = document.getElementById("c-lastnote");
    if(c.last_note){
      noteEl.innerHTML = "<b>Last note</b>";
      noteEl.appendChild(document.createTextNode(c.last_note));
      noteEl.hidden = false;
    } else { noteEl.hidden = true; }
    document.getElementById("note").value = "";
    syncContactUI();
    loadThread(c);
    loadKit(c);
    document.getElementById("callback").hidden = false;
    syncDialUI();
    if(pdArmed){ pdArmed = false; setTimeout(pdStartCountdown, 400); }
    if(!activeCall){ cpBox.hidden = true; }
    card.hidden = false; outcomes.hidden = false; textopt.hidden = false;
    if(!reduced){
      card.style.opacity = "0"; card.style.transform = "translateY(6px)";
      requestAnimationFrame(function(){
        card.style.transition = "opacity .18s ease, transform .18s ease";
        card.style.opacity = "1"; card.style.transform = "none";
        setTimeout(function(){ card.style.transition = ""; }, 220);
      });
    }
  }

  function fail(status, body){
    if(status === 401){ signOut((body && body.error) || "Please sign in again."); return; }
    deskErr.textContent = (body && body.error) || "Something went wrong — try again.";
    deskErr.hidden = false;
  }

  window.addEventListener("desk:refresh", function(){ fetchNext(); });
  function fetchNext(){
    post("/api/va/calls/next", {}).then(function(r){
      if(r.status !== 200){ fail(r.status, r.body); return; }
      render(r.body);
    }).catch(function(){ fail(0, {error: "No connection — check your internet and try again."}); });
  }

  function setBusy(b){
    busy = b;
    document.querySelectorAll("#outcomes button, #callback button").forEach(function(btn){ btn.disabled = b; });
  }

  var toast = document.getElementById("desk-toast");
  var toastTimer = null;
  function showToast(msg){
    toast.textContent = msg; toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function(){ toast.hidden = true; }, 4000);
  }

  var TEXT_KEY = "umuve_desk_send_text";
  var sendText = document.getElementById("send-text");
  sendText.checked = localStorage.getItem(TEXT_KEY) === "1";
  sendText.addEventListener("change", function(){
    localStorage.setItem(TEXT_KEY, sendText.checked ? "1" : "0");
  });

  document.getElementById("outcomes").addEventListener("click", function(e){
    var btn = e.target.closest("button");
    if(!btn || busy || !current) return;
    setBusy(true);
    post("/api/va/calls/log", {
      prospect_id: current.id,
      outcome: btn.dataset.o,
      note: document.getElementById("note").value.trim(),
      send_text: sendText.checked && btn.dataset.o !== "skip"
    }).then(function(r){
      setBusy(false);
      if(r.status !== 200){ fail(r.status, r.body); return; }
      pdArmed = true;
      if(r.body.texted){ showToast("Logged — and the follow-up text is on its way."); }
      else if(sendText.checked && r.body.text_reason && btn.dataset.o !== "skip" &&
              r.body.text_reason !== "no text for this outcome"){
        showToast("Logged. No text went out: " + r.body.text_reason + ".");
      }
      render(r.body);
    }).catch(function(){ setBusy(false); fail(0, {error: "No connection — that call wasn't logged. Try again."}); });
  });

  // ---- decision-maker capture + info-sent status ----
  function fmtDay(iso){
    if(!iso) return null;
    var d = new Date(iso + (iso.slice(-1) === "Z" ? "" : "Z"));
    return d.toLocaleDateString([], {weekday:"short", month:"short", day:"numeric"});
  }

  function syncContactUI(){
    var c = current;
    if(!c) return;
    var meta = [c.city, c.contact_name ? ("ask for " + c.contact_name) : null,
                c.attempts ? ("attempt " + (c.attempts + 1)) : null];
    document.getElementById("c-meta").textContent = meta.filter(Boolean).join(" · ");
    var direct = document.getElementById("c-direct");
    if(c.direct_tel){
      var dn = document.getElementById("c-direct-num"); dn.textContent = "";
      if(c.contact_name){ var nm = document.createElement("span"); nm.className = "dn-name"; nm.textContent = c.contact_name; dn.appendChild(nm); }
      var nb = document.createElement("span"); nb.className = "dn-num"; nb.textContent = c.direct_phone; dn.appendChild(nb);
      direct.href = c.direct_tel;
      direct.hidden = false;
    } else { direct.hidden = true; }
    document.getElementById("dm-name").value = c.contact_name || "";
    document.getElementById("dm-phone").value = c.direct_phone || "";
    // the info text goes to the boss's cell when we have one
    document.getElementById("si-phone").value = c.direct_phone || c.phone || "";
    document.getElementById("si-email").value = c.email || "";
    var bits = [];
    if(c.last_texted_at) bits.push("texted " + fmtDay(c.last_texted_at));
    if(c.last_emailed_at) bits.push("emailed " + fmtDay(c.last_emailed_at));
    var status = document.getElementById("si-status");
    if(bits.length){
      status.textContent = "✓ Info pack already " + bits.join(" · ") +
        " — reference it on this call.";
      status.hidden = false;
    } else { status.hidden = true; }
  }

  document.getElementById("dm-save-btn").addEventListener("click", function(){
    if(!current || this.disabled) return;
    var btn = this;
    btn.disabled = true;
    post("/api/va/calls/contact", {
      prospect_id: current.id,
      contact_name: document.getElementById("dm-name").value.trim(),
      direct_phone: document.getElementById("dm-phone").value.trim(),
      email: document.getElementById("si-email").value.trim()
    }).then(function(r){
      btn.disabled = false;
      if(r.status !== 200){ fail(r.status, r.body); return; }
      current = r.body.card;
      syncContactUI();
      showToast("Saved — it'll be on this card every time they come back.");
    }).catch(function(){
      btn.disabled = false;
      fail(0, {error: "No connection — nothing was saved. Try again."});
    });
  });

  // ---- send the info pack (text or email), no outcome needed ----
  // After a text "sends", poll the real carrier status so a landline can't
  // swallow it silently (the DR BILLIARDS lesson).
  function checkDelivery(sid, attempt){
    fetch("/api/va/status", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({passcode: code(), sid: sid})
    }).then(function(r){ return r.json(); }).then(function(j){
      if(!j || !j.ok) return;
      if(j.status === "delivered"){ showToast("Text delivered ✓"); return; }
      if(j.status === "failed" || j.status === "undelivered"){
        showToast("Text did NOT arrive: " + (j.reason || "delivery failed") +
                  " Try email instead.");
        return;
      }
      if(attempt < 2){ setTimeout(function(){ checkDelivery(sid, attempt + 1); }, 15000); }
    }).catch(function(){});
  }

  function sendInfo(channel, to, btn){
    if(!current || btn.disabled) return;
    if(channel === "email" && !to){
      showToast("Type the email address they gave you first."); return;
    }
    btn.disabled = true;
    post("/api/va/calls/send-info", {
      prospect_id: current.id, channel: channel, to: to
    }).then(function(r){
      btn.disabled = false;
      if(r.status !== 200){ fail(r.status, r.body); return; }
      if(channel === "text"){
        showToast("Info text sent to " + r.body.to + " — checking it lands…");
        if(r.body.sid){ setTimeout(function(){ checkDelivery(r.body.sid, 0); }, 8000); }
        current.last_texted_at = new Date().toISOString();
      } else {
        showToast("Info pack emailed to " + r.body.to + " ✓");
        current.email = r.body.to;
        current.last_emailed_at = new Date().toISOString();
      }
      syncContactUI();
    }).catch(function(){
      btn.disabled = false;
      fail(0, {error: "No connection — nothing was sent. Try again."});
    });
  }

  function sendRateCard(channel, btn){
    if(!current || btn.disabled) return;
    var to = channel === "email" ? document.getElementById("si-email").value.trim()
           : channel === "text" ? document.getElementById("si-phone").value.trim() : "";
    if(channel === "email" && !to){ showToast("Type the email address they gave you first."); return; }
    btn.disabled = true;
    post("/api/va/calls/rate-card", {prospect_id: current.id, channel: channel, to: to}).then(function(r){
      btn.disabled = false;
      if(r.status !== 200){ fail(r.status, r.body); return; }
      if(channel === "preview"){ window.open(r.body.url, "_blank", "noopener"); return; }
      if(channel === "text"){ showToast("Rate card link texted to " + r.body.to + "."); current.last_texted_at = new Date().toISOString(); if(current) loadThread(current); }
      else { showToast("Rate card PDF emailed to " + r.body.to + "."); current.email = r.body.to; current.last_emailed_at = new Date().toISOString(); }
      syncContactUI();
    }).catch(function(){ btn.disabled = false; fail(0, {error: "No connection — nothing was sent. Try again."}); });
  }
  document.getElementById("rc-text-btn").addEventListener("click", function(){ sendRateCard("text", this); });
  document.getElementById("rc-email-btn").addEventListener("click", function(){ sendRateCard("email", this); });
  document.getElementById("rc-prev-btn").addEventListener("click", function(){ sendRateCard("preview", this); });

  document.getElementById("si-text-btn").addEventListener("click", function(){
    sendInfo("text", document.getElementById("si-phone").value.trim(), this);
  });
  document.getElementById("si-email-btn").addEventListener("click", function(){
    sendInfo("email", document.getElementById("si-email").value.trim(), this);
  });

  // ---- callback search ----
  var searchbox = document.getElementById("searchbox");
  var searchQ = document.getElementById("search-q");
  var searchResults = document.getElementById("search-results");
  var searchTimer = null;
  document.getElementById("search-toggle").addEventListener("click", function(){
    searchbox.hidden = !searchbox.hidden;
    if(!searchbox.hidden){ searchQ.focus(); }
    else { searchResults.textContent = ""; searchQ.value = ""; }
  });
  searchQ.addEventListener("input", function(){
    clearTimeout(searchTimer);
    var q = searchQ.value.trim();
    if(q.length < 2){ searchResults.textContent = ""; return; }
    searchTimer = setTimeout(function(){
      post("/api/va/calls/search", {q: q}).then(function(r){
        if(r.status !== 200){ fail(r.status, r.body); return; }
        searchResults.textContent = "";
        var rows = r.body.results || [];
        if(!rows.length){
          var none = document.createElement("p");
          none.className = "sr-none";
          none.textContent = "No business matches that — check the spelling or try the phone number.";
          searchResults.appendChild(none);
          return;
        }
        rows.forEach(function(row){
          var b = document.createElement("button");
          b.className = "sr"; b.type = "button";
          var wrap = document.createElement("div");
          var t = document.createElement("div"); t.className = "sr-t"; t.textContent = row.company;
          var d = document.createElement("div"); d.className = "sr-d";
          d.textContent = [row.phone, row.city].filter(Boolean).join(" · ");
          wrap.appendChild(t); wrap.appendChild(d);
          var s = document.createElement("div"); s.className = "sr-status"; s.textContent = row.status;
          b.appendChild(wrap); b.appendChild(s);
          b.addEventListener("click", function(){
            post("/api/va/calls/get", {prospect_id: row.id}).then(function(rr){
              if(rr.status !== 200){ fail(rr.status, rr.body); return; }
              searchbox.hidden = true; searchResults.textContent = ""; searchQ.value = "";
              render(rr.body);
              showToast("Loaded " + row.company + " — log this call, then the queue continues.");
            });
          });
          searchResults.appendChild(b);
        });
      });
    }, 250);
  });

  // ---- call kit ----
  var kitBody = document.getElementById("kit-body");
  var kitSideBtn = document.getElementById("kit-side");
  var kitTab = "track", kitData = null, kitFor = null, kitSideOverride = {};
  function el(tag, cls, text){ var e = document.createElement(tag); if(cls) e.className = cls; if(text != null) e.textContent = text; return e; }
  function renderKit(){
    kitBody.textContent = "";
    if(!kitData){ kitBody.appendChild(el("p", "kit-loading", "Loading the kit…")); return; }
    var d = kitData;
    kitSideBtn.textContent = d.side === "supply" ? "Recruiting a hauler" : "Selling a customer";
    kitSideBtn.className = "kit-side " + d.side;
    if(kitTab === "track"){
      var steps = [["Open", d.track.opener], ["Ask", d.track.discover], ["Pitch", d.track.pitch], ["Close", d.track.close]];
      steps.forEach(function(st){
        var row = el("div", "kt-step"); row.appendChild(el("div", "kt-k", st[0]));
        var v = el("div", "kt-v");
        if(Array.isArray(st[1])){ var ol = el("ol"); st[1].forEach(function(q){ ol.appendChild(el("li", null, q)); }); v.appendChild(ol); }
        else v.textContent = st[1];
        row.appendChild(v); kitBody.appendChild(row);
      });
    } else if(kitTab === "objections"){
      d.objections.forEach(function(o){
        var det = el("details", "kt-obj"); det.appendChild(el("summary", null, o.say));
        det.appendChild(el("p", null, o.reply)); kitBody.appendChild(det);
      });
    } else if(kitTab === "answers"){
      var dl = el("dl", "kt-ans");
      d.answers.forEach(function(a){ dl.appendChild(el("dt", null, a.q)); dl.appendChild(el("dd", null, a.a)); });
      kitBody.appendChild(dl);
    } else if(kitTab === "prices"){
      kitBody.appendChild(el("p", "kit-note", d.price_note));
      var grid = el("div", "kt-price");
      d.prices.forEach(function(p){ var row = el("div"); row.appendChild(el("span", null, p.label)); row.appendChild(el("b", null, "$" + p.from)); grid.appendChild(row); });
      kitBody.appendChild(grid);
    } else if(kitTab === "lookup"){
      var wrap = el("div", "kt-links");
      d.lookup.forEach(function(l){ var a = el("a", null, l.label); a.href = l.url; a.target = "_blank"; a.rel = "noopener"; wrap.appendChild(a); });
      kitBody.appendChild(wrap);
    }
  }
  function loadKit(c){
    kitFor = c.id; kitData = null; renderKit();
    post("/api/va/calls/kit", {prospect_id: c.id, side: kitSideOverride[c.id] || null}).then(function(r){
      if(r.status !== 200 || kitFor !== c.id) return;
      kitData = r.body; renderKit();
    }).catch(function(){ kitBody.textContent = ""; kitBody.appendChild(el("p", "kit-loading", "Couldn't load the kit — check your connection.")); });
  }
  document.querySelector(".kit-tabs").addEventListener("click", function(e){
    var b = e.target.closest(".kit-tab"); if(!b) return;
    document.querySelectorAll(".kit-tab").forEach(function(t){ t.classList.toggle("is-on", t === b); });
    kitTab = b.dataset.k; renderKit();
  });
  kitSideBtn.addEventListener("click", function(){
    if(!current || !kitData) return;
    kitSideOverride[current.id] = kitData.side === "supply" ? "demand" : "supply";
    loadKit(current);
  });

  // ---- account: change password, sign out ----
  var acctbox = document.getElementById("acctbox");
  function showAcct(){
    hideQueue(); hideTime(); searchbox.hidden = true;
    var m = me();
    document.getElementById("ac-sub").textContent = m ? (m.full_name || m.name) + " · " + (m.email || "") + (m.is_manager ? " · manager" : "") : (vaName() || "") + " · signed in with the access code";
    // A shared access code has no password to change, so the form is hidden.
    // Say why, instead of showing a panel whose only button is Sign out.
    var hasAccount = !!jwt();
    document.getElementById("pw-form").hidden = !hasAccount;
    var pwNote = document.getElementById("ac-note");
    if(pwNote){
      pwNote.hidden = hasAccount;
      pwNote.textContent = "The access code is shared, so there's no password here to change. " +
        "Ask Shamar for your own sign-in (your email and a password) and this is where you'd change it.";
    }
    document.getElementById("ac-status").hidden = true;
    acctbox.hidden = false; deck.classList.add("acct-open"); window.scrollTo(0, 0);
  }
  function hideAcct(){ acctbox.hidden = true; deck.classList.remove("acct-open"); }
  document.getElementById("who").addEventListener("click", function(){ if(acctbox.hidden) showAcct(); else hideAcct(); });
  document.getElementById("acct-close").addEventListener("click", hideAcct);
  document.getElementById("sign-out").addEventListener("click", function(){ hideAcct(); signOut("Signed out."); });
  document.getElementById("pw-form").addEventListener("submit", function(e){
    e.preventDefault();
    var st = document.getElementById("ac-status"); var btn = this.querySelector("button"); btn.disabled = true;
    post("/api/desk/change-password", {current: document.getElementById("pw-cur").value, new: document.getElementById("pw-new").value}).then(function(r){
      btn.disabled = false; st.hidden = false;
      if(r.status !== 200){ st.className = "qb-status err"; st.textContent = (r.body && r.body.error) || "That didn't work."; return; }
      st.className = "qb-status"; st.textContent = "Password changed. Use the new one next time you sign in.";
      document.getElementById("pw-form").reset();
    }).catch(function(){ btn.disabled = false; st.hidden = false; st.className = "qb-status err"; st.textContent = "No connection — nothing changed."; });
  });

  // ---- time clock ----
  var timebox = document.getElementById("timebox");
  var clockChip = document.getElementById("clock-chip");
  var clockLabel = document.getElementById("clock-label");
  var tbToggle = document.getElementById("tb-toggle");
  var tbStatus = document.getElementById("tb-status");
  var tbList = document.getElementById("tb-list");
  var clockState = null, clockTimer = null;
  function hm(sec){ sec = sec | 0; var h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60); return h + ":" + ("0" + m).slice(-2); }
  function hms(sec){ sec = sec | 0; return hm(sec) + ":" + ("0" + (sec % 60)).slice(-2); }
  function liveShiftSeconds(){
    if(!clockState || !clockState.shift) return 0;
    var start = new Date(clockState.shift.started_at + (clockState.shift.started_at.slice(-1) === "Z" ? "" : "Z"));
    return Math.max(0, (Date.now() - start.getTime()) / 1000);
  }
  function money(v){ return (v == null) ? "" : "$" + Number(v).toFixed(2); }
  function renderClock(){
    var on = !!(clockState && clockState.on_clock);
    clockChip.classList.toggle("on", on);
    clockLabel.textContent = on ? "On the clock · " + hm(liveShiftSeconds()) : "Clock in";
    tbToggle.textContent = on ? "Clock out" : "Clock in";
    tbToggle.classList.toggle("out", on);
    if(clockState){
      var extra = on ? (Date.now() / 1000 - (clockState._at || Date.now() / 1000)) : 0;
      document.getElementById("tb-today").textContent = hm((clockState.today_seconds || 0) + extra);
      document.getElementById("tb-week").textContent = hm((clockState.week_seconds || 0) + extra);
      var pSecs = (clockState.period_seconds || 0) + extra;
      var pPay = clockState.hourly_rate ? (pSecs / 3600) * clockState.hourly_rate : null;
      document.getElementById("tb-period").textContent = hm(pSecs) + (pPay != null ? " · " + money(pPay) : "");
      document.getElementById("tb-period-k").textContent = "Pay period · " + (clockState.period_label || "") +
        (clockState.hourly_rate ? " · " + money(clockState.hourly_rate) + "/hr" : "");
      document.getElementById("tb-sub").textContent = (vaName() ? vaName() + " · " : "") +
        (on ? "on the clock since " + new Date(clockState.shift.started_at + "Z").toLocaleTimeString([], {hour:"numeric", minute:"2-digit"}) : "off the clock");
    }
  }
  function setClockState(st){ clockState = st; clockState._at = Date.now() / 1000; renderClock(); }
  function pollClock(){
    clearInterval(clockTimer);
    clockTimer = setInterval(function(){ if(clockState && clockState.on_clock) renderClock(); }, 30000);
  }
  function loadClock(){
    post("/api/va/time/status", {}).then(function(r){ if(r.status === 200) setClockState(r.body); }).catch(function(){});
  }
  function tbSay(msg, isErr){ tbStatus.textContent = msg; tbStatus.hidden = false; tbStatus.className = "qb-status" + (isErr ? " err" : ""); }
  var tbView = "mine";
  function renderShifts(rows, showWho){
    tbList.textContent = "";
    if(!rows || !rows.length){ tbList.appendChild(el("p", "sr-none", showWho ? "Nobody has clocked in yet." : "No shifts yet. Clock in when you start calling.")); return; }
    rows.forEach(function(s){
      var row = el("div", "tb-row" + (s.open ? " open" : ""));
      if(showWho) row.appendChild(el("span", "tb-who", s.va_name));
      row.appendChild(el("span", "d", s.day));
      row.appendChild(el("span", "t", s.start_local + " – " + (s.end_local || "now") + (s.auto_closed ? " · auto-closed at 12h" : "") + (s.note ? " · " + s.note : "")));
      row.appendChild(el("span", "c", s.calls + (s.calls === 1 ? " call" : " calls")));
      row.appendChild(el("span", "h", hm(s.seconds) + (s.pay != null ? " · " + money(s.pay) : "")));
      tbList.appendChild(row);
    });
  }
  var tbTeamTotals = document.getElementById("tb-team-totals");
  function loadHours(){
    document.getElementById("tb-mine").classList.toggle("is-on", tbView === "mine");
    document.getElementById("tb-team").classList.toggle("is-on", tbView === "team");
    if(tbView === "team"){
      document.getElementById("tb-name").hidden = true;
      post("/api/va/time/team", {days: 45}).then(function(r){
        if(r.status !== 200){ tbSay((r.body && r.body.error) || "Couldn't load hours.", true); return; }
        tbTeamTotals.textContent = ""; tbTeamTotals.hidden = false;
        var names = r.body.vas || [];
        if(!names.length){ tbTeamTotals.hidden = true; }
        names.forEach(function(n){
          var t = r.body.totals[n] || {};
          var row = el("div", "tb-tot");
          row.appendChild(el("b", null, n));
          row.appendChild(el("span", null, "today " + hm(t.today_seconds)));
          row.appendChild(el("span", null, "week " + hm(t.week_seconds)));
          row.appendChild(el("span", null, (t.period_label || "pay period") + " " + hm(t.period_seconds) +
            (t.period_pay != null ? " · " + money(t.period_pay) : "")));
          tbTeamTotals.appendChild(row);
        });
        renderShifts(r.body.shifts, true);
      }).catch(function(){ tbSay("No connection — couldn't load hours.", true); });
      return;
    }
    tbTeamTotals.hidden = true;
    if(!vaName()){ document.getElementById("tb-name").hidden = false; tbList.textContent = ""; return; }
    document.getElementById("tb-name").hidden = true;
    post("/api/va/time/hours", {days: 45}).then(function(r){
      if(r.status !== 200){ tbSay((r.body && r.body.error) || "Couldn't load hours.", true); return; }
      setClockState(r.body); renderShifts(r.body.shifts, false);
    }).catch(function(){ tbSay("No connection — couldn't load hours.", true); });
  }
  document.getElementById("tb-mine").addEventListener("click", function(){ tbView = "mine"; loadHours(); });
  document.getElementById("tb-team").addEventListener("click", function(){ tbView = "team"; loadHours(); });
  function syncRoleUI(){
    var vaOnly = !!jwt() && !isManager();
    document.getElementById("tb-team").hidden = vaOnly;
    if(vaOnly && tbView === "team"){ tbView = "mine"; }
  }
  function showTime(){ hideQueue(); hideAcct(); searchbox.hidden = true; tbStatus.hidden = true; timebox.hidden = false; deck.classList.add("time-open"); loadHours(); window.scrollTo(0, 0); }
  function hideTime(){ timebox.hidden = true; deck.classList.remove("time-open"); }
  clockChip.addEventListener("click", function(){ if(timebox.hidden) showTime(); else hideTime(); });
  document.getElementById("time-close").addEventListener("click", hideTime);
  document.getElementById("tb-name-save").addEventListener("click", function(){
    var v = document.getElementById("tb-name-input").value.trim();
    if(!v){ return; }
    localStorage.setItem(VA_KEY, v); loadHours();
  });
  tbToggle.addEventListener("click", function(){
    if(!vaName()){ document.getElementById("tb-name").hidden = false; document.getElementById("tb-name-input").focus(); return; }
    var on = !!(clockState && clockState.on_clock);
    tbToggle.disabled = true;
    post("/api/va/time/clock", {action: on ? "out" : "in"}).then(function(r){
      tbToggle.disabled = false;
      if(r.status !== 200){ tbSay((r.body && r.body.error) || "That didn't work.", true); return; }
      setClockState(r.body);
      if(on && r.body.closed){ tbSay("Clocked out — that shift was " + hm(r.body.closed.seconds) + "."); showToast("Clocked out. " + hm(r.body.closed.seconds) + " on that shift."); }
      else if(!on){ tbSay("Clocked in at " + new Date().toLocaleTimeString([], {hour:"numeric", minute:"2-digit"}) + "."); showToast("On the clock."); }
      loadHours();
    }).catch(function(){ tbToggle.disabled = false; tbSay("No connection — nothing changed.", true); });
  });

  // ---- queue panel: the whole list, load a CSV, add one business ----
  var queuebox = document.getElementById("queuebox");
  var qbList = document.getElementById("qb-list");
  var qbStatus = document.getElementById("qb-status");
  var qbAdd = document.getElementById("qb-add");
  function qbSay(msg, isErr){ qbStatus.textContent = msg; qbStatus.hidden = false; qbStatus.className = "qb-status" + (isErr ? " err" : ""); }
  function fmtDue(iso){
    if(!iso) return "";
    var d = new Date(iso + (iso.slice(-1) === "Z" ? "" : "Z"));
    return d.toLocaleString([], {weekday:"short", hour:"numeric", minute:"2-digit"});
  }
  function queueRow(r, kind){
    var b = el("button", "qr"); b.type = "button";
    b.appendChild(el("span", "qr-tier", "T" + r.tier));
    var w = el("div", "qr-w");
    w.appendChild(el("div", "qr-t", r.company));
    w.appendChild(el("div", "qr-d", [r.city, r.category, r.contact_name ? "ask for " + r.contact_name : null].filter(Boolean).join(" · ")));
    b.appendChild(w);
    var s = el("span", "qr-s" + (kind === "due" ? " due" : ""),
      kind === "due" ? (r.last_outcome === "callback" ? "callback" : "due") :
      kind === "later" ? fmtDue(r.due_at) : (r.attempts ? "try " + (r.attempts + 1) : "new"));
    b.appendChild(s);
    b.addEventListener("click", function(){
      post("/api/va/calls/get", {prospect_id: r.id}).then(function(rr){
        if(rr.status !== 200){ fail(rr.status, rr.body); return; }
        hideQueue(); render(rr.body);
      });
    });
    return b;
  }
  function loadQueue(){
    qbList.textContent = "";
    post("/api/va/calls/queue", {}).then(function(r){
      if(r.status !== 200){ fail(r.status, r.body); return; }
      var q = r.body, c = q.counts;
      setDaybar(q.stats);
      var tiers = Object.keys(c.by_tier || {}).sort().map(function(t){ return "T" + t + " " + c.by_tier[t]; }).join(" · ");
      document.getElementById("qb-sub").textContent =
        c.due + " due now · " + c.fresh + " fresh" + (tiers ? " (" + tiers + ")" : "") +
        " · " + ((c.by_status || {}).interested || 0) + " interested · " + c.total + " total";
      function section(title, rows, kind, note){
        if(!rows.length) return;
        var h = el("div", "qb-sec"); h.appendChild(el("span", null, title)); h.appendChild(el("span", null, note || rows.length));
        qbList.appendChild(h);
        rows.forEach(function(row){ qbList.appendChild(queueRow(row, kind)); });
      }
      section("Due now", q.due, "due");
      section("Fresh — dealt in this order", q.fresh, "fresh", c.fresh > q.fresh.length ? q.fresh.length + " of " + c.fresh : null);
      section("Coming up", q.later, "later");
      if(!q.due.length && !q.fresh.length && !q.later.length){
        qbList.appendChild(el("p", "sr-none", "The queue is empty. Load a list or add a business above."));
      }
    }).catch(function(){ fail(0, {error: "No connection — couldn't load the queue."}); });
  }
  var deck = document.getElementById("deck");
  function showQueue(){ hideTime(); hideAcct(); searchbox.hidden = true; qbStatus.hidden = true; queuebox.hidden = false; deck.classList.add("queue-open"); loadQueue(); window.scrollTo(0, 0); }
  function hideQueue(){ queuebox.hidden = true; deck.classList.remove("queue-open"); }
  document.getElementById("queue-toggle").addEventListener("click", function(){
    if(queuebox.hidden) showQueue(); else hideQueue();
  });
  document.getElementById("queue-close").addEventListener("click", hideQueue);
  document.getElementById("empty-load").addEventListener("click", showQueue);
  document.getElementById("qb-file").addEventListener("change", function(){
    var f = this.files && this.files[0]; this.value = "";
    if(!f) return;
    qbSay("Reading " + f.name + "…");
    var reader = new FileReader();
    reader.onload = function(){
      post("/api/va/calls/import", {csv: String(reader.result || "")}).then(function(r){
        if(r.status !== 200){ qbSay((r.body && r.body.error) || "That file didn't load.", true); if(r.status === 401) fail(401, r.body); return; }
        var b = r.body;
        qbSay("Loaded " + f.name + ": " + b.added + " added, " + b.skipped_dupes + " already in the queue, " +
              b.invalid + " skipped (no usable phone or name). " + b.total + " businesses total.");
        loadQueue();
      }).catch(function(){ qbSay("No connection — the list wasn't loaded.", true); });
    };
    reader.readAsText(f);
  });
  document.getElementById("qb-add-toggle").addEventListener("click", function(){
    qbAdd.hidden = !qbAdd.hidden; if(!qbAdd.hidden) document.getElementById("qa-company").focus();
  });
  qbAdd.addEventListener("submit", function(e){
    e.preventDefault();
    var btn = qbAdd.querySelector("button"); btn.disabled = true;
    post("/api/va/calls/add", {
      company: document.getElementById("qa-company").value.trim(),
      phone: document.getElementById("qa-phone").value.trim(),
      city: document.getElementById("qa-city").value.trim(),
      category: document.getElementById("qa-category").value.trim(),
      contact_name: document.getElementById("qa-contact").value.trim(),
      why: document.getElementById("qa-why").value.trim()
    }).then(function(r){
      btn.disabled = false;
      if(r.status !== 200){ qbSay((r.body && r.body.error) || "Couldn't add them.", true); return; }
      qbAdd.reset(); qbAdd.hidden = true; hideQueue();
      render(r.body);
      showToast(r.body.exists ? "They were already in the queue — here's their card." : "Added — here's their card.");
    }).catch(function(){ btn.disabled = false; qbSay("No connection — nothing was added.", true); });
  });

  // ---- callback scheduler ----
  var cbBox = document.getElementById("callback");
  function scheduleCallback(payload){
    if(!current || busy) return;
    setBusy(true);
    payload.prospect_id = current.id;
    payload.note = document.getElementById("note").value.trim();
    post("/api/va/calls/callback", payload).then(function(r){
      setBusy(false);
      if(r.status !== 200){ fail(r.status, r.body); return; }
      showToast("Callback set for " + r.body.callback_local + " — it'll be dealt back to you then.");
      pdArmed = true; render(r.body);
    }).catch(function(){ setBusy(false); fail(0, {error: "No connection — the callback wasn't saved. Try again."}); });
  }
  cbBox.addEventListener("click", function(e){
    var b = e.target.closest("button.cb"); if(!b) return;
    scheduleCallback({preset: b.dataset.p});
  });
  document.getElementById("cb-at").addEventListener("change", function(){
    if(this.value) scheduleCallback({at: this.value});
    this.value = "";
  });

  // ---- desk line: conversation thread ----
  var thList = document.getElementById("th-list");
  var thEmpty = document.getElementById("th-empty");
  var thForm = document.getElementById("th-form");
  var thInput = document.getElementById("th-input");
  var thNum = document.getElementById("th-num");
  var threadFor = null;

  function prettyNum(e){
    var d = (e || "").replace(/\D/g, "").slice(-10);
    return d.length === 10 ? "(" + d.slice(0,3) + ") " + d.slice(3,6) + "-" + d.slice(6) : (e || "");
  }
  function fmtWhen(iso){
    if(!iso) return "";
    var d = new Date(iso + (iso.slice(-1) === "Z" ? "" : "Z"));
    var t = d.toLocaleTimeString([], {hour:"numeric", minute:"2-digit"});
    if(d.toDateString() === new Date().toDateString()) return t;
    return d.toLocaleDateString([], {month:"short", day:"numeric"}) + " " + t;
  }
  function fmtDur(s){ s = s | 0; return Math.floor(s / 60) + ":" + ("0" + (s % 60)).slice(-2); }

  var lnThread = document.getElementById("ln-thread");
  var lnFoot = document.getElementById("ln-foot");
  var inboxClose = document.getElementById("inbox-close");
  function setLineWho(name){
    document.getElementById("ln-who").textContent = name || "No business on the card";
    thQuick.querySelectorAll("button").forEach(function(b){ b.disabled = !name; });
    thInput.disabled = !name;
    thForm.querySelector("button").disabled = !name;
  }
  var line = document.getElementById("line");
  var lnHead = line.querySelector(".ln-head");
  function isSheet(){ return window.matchMedia("(max-width:959px)").matches; }
  lnHead.addEventListener("click", function(e){
    if(e.target.closest("button") || !isSheet()) return;
    line.classList.toggle("open");
    if(line.classList.contains("open")) lnThread.scrollTop = lnThread.scrollHeight;
  });
  function showThreadPane(){
    inboxbox.hidden = true; lnThread.hidden = false; lnFoot.hidden = false;
  }
  function showInboxPane(noCard){
    if(isSheet()) line.classList.add("open");
    lnThread.hidden = true; lnFoot.hidden = true; inboxbox.hidden = false;
    inboxClose.hidden = !!noCard || !current;
    loadInbox();
  }
  function renderThread(msgs){
    thList.textContent = "";
    if(!msgs || !msgs.length){ thEmpty.hidden = false; return; }
    thEmpty.hidden = true;
    msgs.forEach(function(m){
      var row = document.createElement("div");
      row.className = "msg " + (m.direction === "in" ? "msg-in" : "msg-out") + (m.kind === "call" ? " msg-call" : "");
      var b = document.createElement("div"); b.className = "msg-b";
      if(m.kind === "call"){
        var label = m.direction === "in" ? "They called" : "You called";
        if(m.status === "completed") label += " · " + fmtDur(m.duration || 0);
        else if(m.status === "voicemail") label = "Voicemail";
        else if(m.status === "no-answer") label = "Missed call";
        else if(m.status && m.status !== "ringing") label += " · " + m.status.replace("-", " ");
        var l = document.createElement("div"); l.className = "msg-call-l"; l.textContent = label; b.appendChild(l);
        if(m.body) b.appendChild(document.createTextNode(m.body));
        if(m.recording_url){
          var a = document.createElement("a"); a.href = m.recording_url + ".mp3"; a.target = "_blank";
          a.rel = "noopener"; a.className = "msg-rec"; a.textContent = "Play recording"; b.appendChild(a);
        }
      } else {
        if(m.body) b.appendChild(document.createTextNode(m.body));
        (m.media || []).forEach(function(u){
          var a2 = document.createElement("a"); a2.href = u; a2.target = "_blank"; a2.rel = "noopener";
          a2.className = "msg-rec"; a2.textContent = "Photo"; b.appendChild(a2);
        });
      }
      var meta = document.createElement("div"); meta.className = "msg-m";
      var st = "";
      if(m.direction === "out" && m.kind === "sms" && m.status){
        if(m.status === "delivered") st = " · delivered";
        else if(m.status.indexOf("failed") === 0 || m.status.indexOf("undelivered") === 0) st = " · not delivered";
      }
      meta.textContent = fmtWhen(m.created_at) + st;
      row.appendChild(b); row.appendChild(meta);
      thList.appendChild(row);
    });
    lnThread.scrollTop = lnThread.scrollHeight;
  }

  function loadThread(c){
    threadFor = c ? c.id : null;
    thList.textContent = ""; thEmpty.hidden = true;
    if(!c) return;
    post("/api/va/desk/thread", {prospect_id: c.id}).then(function(r){
      if(r.status !== 200 || threadFor !== c.id) return;
      renderThread(r.body.messages);
      setUnread(r.body.unread);
      if(!deskReady) thNum.textContent = r.body.desk_number ? "on " + prettyNum(r.body.desk_number) : "on the Umuve number";
    }).catch(function(){});
  }

  function autosize(){ thInput.style.height = "auto"; thInput.style.height = Math.min(140, thInput.scrollHeight) + "px"; }
  thInput.addEventListener("input", autosize);
  thInput.addEventListener("keydown", function(e){
    if(e.key === "Enter" && !e.shiftKey){ e.preventDefault(); thForm.requestSubmit(); }
  });
  var thQuick = document.getElementById("th-quick");
  thQuick.addEventListener("click", function(e){
    var b = e.target.closest("button"); if(!b || !current || b.disabled) return;
    post("/api/va/desk/templates", {prospect_id: current.id}).then(function(r){
      if(r.status !== 200){ fail(r.status, r.body); return; }
      var t = r.body[b.dataset.t]; if(!t) return;
      thInput.value = t; autosize(); thInput.focus();
      thInput.setSelectionRange(thInput.value.length, thInput.value.length);
    }).catch(function(){});
  });
  thForm.addEventListener("submit", function(e){
    e.preventDefault();
    if(!current) return;
    var body = thInput.value.trim();
    if(!body){ thInput.focus(); return; }
    var btn = thForm.querySelector("button"); btn.disabled = true;
    post("/api/va/desk/text", {prospect_id: current.id, body: body}).then(function(r){
      btn.disabled = false;
      if(r.status !== 200){ fail(r.status, r.body); return; }
      thInput.value = ""; autosize();
      renderThread(r.body.messages);
      current.last_texted_at = new Date().toISOString();
      syncContactUI();
      showToast("Sent to " + r.body.to);
    }).catch(function(){ btn.disabled = false; fail(0, {error: "No connection — nothing was sent. Try again."}); });
  });

  // ---- inbox: replies + callbacks across every prospect ----
  var inboxbox = document.getElementById("inboxbox");
  var inboxList = document.getElementById("inbox-list");
  var badge = document.getElementById("inbox-badge");
  function setUnread(n){ n = n | 0; badge.textContent = n > 99 ? "99+" : String(n); badge.hidden = n === 0; }
  function unreadNow(){ return badge.hidden ? 0 : (parseInt(badge.textContent, 10) || 0); }

  function loadInbox(){
    post("/api/va/desk/inbox", {}).then(function(r){
      if(r.status !== 200){ fail(r.status, r.body); return; }
      setUnread(r.body.unread);
      inboxList.textContent = "";
      var items = r.body.items || [];
      if(!items.length){
        var none = document.createElement("p"); none.className = "sr-none";
        none.textContent = "No replies or callbacks yet. They show up here the moment someone texts or calls the desk line.";
        inboxList.appendChild(none); return;
      }
      items.forEach(function(it){
        var b = document.createElement("button"); b.className = "sr" + (it.unread ? " sr-unread" : ""); b.type = "button";
        var wrap = document.createElement("div"); wrap.className = "sr-w";
        var t = document.createElement("div"); t.className = "sr-t"; t.textContent = it.company || it.phone;
        var d = document.createElement("div"); d.className = "sr-d";
        d.textContent = (it.kind === "call" ? "☎ " : "") + (it.preview || "");
        wrap.appendChild(t); wrap.appendChild(d);
        var s = document.createElement("div"); s.className = "sr-status"; s.textContent = fmtWhen(it.at);
        b.appendChild(wrap); b.appendChild(s);
        b.addEventListener("click", function(){
          if(!it.prospect_id){ showToast("Unknown number " + it.phone + " — not on any list. Call them back from your phone."); return; }
          post("/api/va/calls/get", {prospect_id: it.prospect_id}).then(function(rr){
            if(rr.status !== 200){ fail(rr.status, rr.body); return; }
            render(rr.body);
          });
        });
        inboxList.appendChild(b);
      });
    }).catch(function(){});
  }
  document.getElementById("inbox-toggle").addEventListener("click", function(){
    if(inboxbox.hidden) showInboxPane(false); else if(current) showThreadPane();
  });
  inboxClose.addEventListener("click", function(){ showThreadPane(); });
  var unreadTimer = null;
  function pollUnread(){
    clearInterval(unreadTimer);
    unreadTimer = setInterval(function(){
      if(document.hidden) return;
      post("/api/va/desk/unread", {}).then(function(r){
        if(r.status !== 200) return;
        var before = unreadNow();
        setUnread(r.body.unread);
        if(r.body.unread > before){
          if(current) loadThread(current);
          if(!inboxbox.hidden) loadInbox();
        }
      }).catch(function(){});
    }, 45000);
  }

  // ---- browser dialer (Twilio Voice) — only when the desk line is provisioned ----
  var device = null, activeCall = null, callTimer = null, callStart = 0, deskReady = false, deskBooted = false, deskNumber = "";
  var strip = document.getElementById("callstrip");
  var stripWho = document.getElementById("cs-who");
  var stripState = document.getElementById("cs-state");
  var stripTime = document.getElementById("cs-time");
  var muteBtn = document.getElementById("cs-mute");
  var hangBtn = document.getElementById("cs-hang");
  var deskCallBtn = document.getElementById("desk-call-btn");
  var incoming = document.getElementById("incoming");
  var incWho = document.getElementById("inc-who");
  var pendingIncoming = null;

  function loadSdk(){
    return new Promise(function(res, rej){
      if(window.Twilio && window.Twilio.Device){ res(); return; }
      var s = document.createElement("script");
      s.src = "/static/twilio-voice-2.18.4.min.js";
      s.onload = res; s.onerror = rej;
      document.head.appendChild(s);
    });
  }
  function deskBoot(){
    if(deskBooted) return; deskBooted = true;
    post("/api/va/flags", {}).then(function(r){ if(r.status === 200){ flags = r.body.flags || {}; applyFlags(); } }).catch(function(){});
    pollUnread(); loadClock(); pollClock();
    post("/api/va/desk/unread", {}).then(function(r){ if(r.status === 200) setUnread(r.body.unread); }).catch(function(){});
    post("/api/va/desk/token", {}).then(function(r){
      if(r.status !== 200) return;
      if(!r.body.enabled){ setDialerStatus(r.body.reason || "browser calling isn't set up"); return; }
      deskNumber = r.body.desk_number || "";
      setDialerStatus("connecting the desk line…");
      return loadSdk().then(function(){ initDevice(r.body.token); })
        .catch(function(){ setDialerStatus("dialer script blocked — check the network or ad blocker"); });
    }).catch(function(){ deskReady = false; });
  }
  function refreshToken(){
    post("/api/va/desk/token", {}).then(function(r){
      if(r.status === 200 && r.body.enabled && device) device.updateToken(r.body.token);
    }).catch(function(){});
  }
  deskCallBtn.textContent = "Call";
  function initDevice(token){
    try {
      device = new Twilio.Device(token, {codecPreferences: ["opus", "pcmu"], closeProtection: true});
      window.__deskDevice = device;   // inbound customer desk (desk-inbound.js) dials through it
    } catch(e){ return; }
    device.on("registered", function(){ deskReady = true; syncDialUI(); setDialerStatus("desk line ready · " + prettyNum(deskNumber)); pdToggle.hidden = flags.power_dial === false; loadVm(); pdRender(); cpToggle.hidden = flags.copilot === false; cpRender(); applyFlags(); });
    device.on("unregistered", function(){ deskReady = false; syncDialUI(); setDialerStatus("desk line offline — reload"); });
    device.on("tokenWillExpire", refreshToken);
    device.on("error", function(e){
      var msg = e && e.message ? e.message : "error";
      showToast("Dialer: " + msg); setDialerStatus("dialer error: " + msg.slice(0, 60));
    });
    device.on("incoming", function(call){
      pendingIncoming = call;
      incWho.textContent = call.parameters && call.parameters.From ? prettyNum(call.parameters.From) : "Unknown number";
      incoming.hidden = false;
      call.on("cancel", function(){ pendingIncoming = null; incoming.hidden = true; });
      call.on("disconnect", function(){ pendingIncoming = null; incoming.hidden = true; });
    });
    device.register();
  }
  function setDialerStatus(msg){
    var n = document.getElementById("th-num");
    if(msg){ n.textContent = msg; }
  }
  function syncDialUI(){
    var tel = document.getElementById("c-tel");
    var direct = document.getElementById("c-direct");
    var hint = tel.querySelector(".dial-hint");
    var dhint = direct.querySelector(".dial-hint");
    if(deskReady && current){
      tel.href = "#"; hint.textContent = "call from the desk";
      direct.href = "#"; dhint.textContent = "direct line — call from the desk";
      deskCallBtn.hidden = false;
    } else if(current){
      tel.href = current.tel; hint.textContent = "tap to call";
      if(current.direct_tel) direct.href = current.direct_tel;
      dhint.textContent = "direct line — skips the front desk";
      deskCallBtn.hidden = true;
    }
  }
  function callErrorText(e){
    var code = e && e.code ? e.code : 0;
    var msg = e && e.message ? e.message : "unknown error";
    if(code === 31401 || code === 31402 || /permission|NotAllowed|getUserMedia/i.test(msg))
      return "microphone blocked — click the lock icon in the address bar, allow Microphone, then reload (" + code + ")";
    if(code === 31208) return "no microphone found — plug in a headset and reload (31208)";
    if(code === 31005 || code === 31009) return "lost the connection to Twilio — check the internet (" + code + ")";
    if(code === 20101 || code === 20104) return "desk line token expired — reload the page (" + code + ")";
    if(code === 31002 || code === 31003) return "the other side didn't pick up or rejected (" + code + ")";
    return msg + (code ? " (" + code + ")" : "");
  }
  function startDeskCall(to){
    if(window.__deskCallsBlocked){ showToast("Calling window is closed right now."); return; }
    if(!device || !deskReady || !current || activeCall) return;
    stripWho.textContent = current.company; stripState.textContent = "Starting…"; stripTime.textContent = "";
    strip.hidden = false; strip.classList.remove("live", "failed");
    device.connect({params: {To: to, prospect_id: current.id, va_name: vaName(), amd: powerOn ? "1" : "0", copilot: copilotOn ? "1" : "0"}}).then(function(call){
      bindCall(call, current.company);
      cpStart();
    }).catch(function(e){
      strip.classList.add("failed"); stripState.textContent = "Call failed: " + callErrorText(e);
      showToast("Couldn't start the call: " + callErrorText(e));
      setTimeout(function(){ strip.hidden = true; strip.classList.remove("failed"); }, 9000);
    });
  }
  // surface a blocked microphone before the first call
  try {
    if(navigator.permissions && navigator.permissions.query){
      navigator.permissions.query({name: "microphone"}).then(function(p){
        function show(){ if(p.state === "denied") setDialerStatus("microphone BLOCKED — click the lock icon in the address bar, allow Microphone, reload"); }
        show(); p.onchange = show;
      }).catch(function(){});
    }
  } catch(e){}
  document.getElementById("c-tel").addEventListener("click", function(e){
    if(deskReady && current){ e.preventDefault(); startDeskCall((current.tel || "").replace("tel:", "")); }
  });
  document.getElementById("c-direct").addEventListener("click", function(e){
    if(deskReady && current && current.direct_tel){ e.preventDefault(); startDeskCall(current.direct_tel.replace("tel:", "")); }
  });
  // ---- copilot: live transcript, cues, post-call summary ----
  var CP_KEY = "umuve_desk_copilot";
  var cpToggle = document.getElementById("cp-toggle");
  var cpBox = document.getElementById("cp");
  var cpLines = document.getElementById("cp-lines");
  var cpCue = document.getElementById("cp-cue");
  var cpSum = document.getElementById("cp-sum");
  var copilotOn = localStorage.getItem(CP_KEY) === "1";
  var cpTimer = null, cpSeq = -1, cpFor = null, cpLastCue = "", cpSuggested = null;
  function cpRender(){ cpToggle.classList.toggle("on", copilotOn); if(!copilotOn){ cpBox.hidden = true; } }
  cpToggle.addEventListener("click", function(){
    copilotOn = !copilotOn; localStorage.setItem(CP_KEY, copilotOn ? "1" : "0"); cpRender();
    showToast(copilotOn ? "Copilot on — the other side will hear a recording notice." : "Copilot off.");
  });
  function cpReset(){
    cpLines.textContent = ""; cpCue.hidden = true; cpSum.hidden = true; cpSeq = -1; cpLastCue = ""; cpSuggested = null;
    cpLines.appendChild(el("p", "cp-empty", "Listening… the transcript shows up here a sentence at a time."));
  }
  function cpAppend(lines){
    if(!lines.length) return;
    var empty = cpLines.querySelector(".cp-empty"); if(empty) empty.remove();
    lines.forEach(function(l){
      var row = el("div", "cp-ln " + (l.track === "them" ? "them" : "you"));
      row.appendChild(el("b", null, l.track === "them" ? "Them" : "You"));
      row.appendChild(document.createTextNode(l.text));
      cpLines.appendChild(row);
      if(l.seq > cpSeq) cpSeq = l.seq;
    });
    cpBox.scrollTop = cpBox.scrollHeight;
  }
  function cpPoll(){
    if(!current || !copilotOn) return;
    var pid = current.id;
    post("/api/va/desk/transcript", {prospect_id: pid, after_seq: cpSeq, side: kitData ? kitData.side : null}).then(function(r){
      if(r.status !== 200 || !current || current.id !== pid) return;
      cpAppend(r.body.lines || []);
      var cue = r.body.cue;
      if(cue && cue.say !== cpLastCue){
        cpLastCue = cue.say;
        document.getElementById("cp-cue-q").textContent = "“" + cue.quote + "”";
        document.getElementById("cp-cue-r").textContent = cue.reply;
        cpCue.hidden = false;
      }
    }).catch(function(){});
  }
  function cpStart(){
    if(!copilotOn) return;
    cpFor = current ? current.id : null; cpReset(); cpBox.hidden = false;
    clearInterval(cpTimer); cpTimer = setInterval(cpPoll, 2500); setTimeout(cpPoll, 1200);
  }
  function cpStop(){ clearInterval(cpTimer); cpTimer = null; }
  function cpSummarize(){
    if(!copilotOn || !current) return;
    var pid = current.id;
    setTimeout(function(){ cpPoll(); }, 800);
    setTimeout(function(){
      post("/api/va/desk/summarize", {prospect_id: pid, side: kitData ? kitData.side : null}).then(function(r){
        if(r.status !== 200 || !current || current.id !== pid) return;
        var b = r.body;
        if(!b.lines){ return; }
        cpSuggested = b;
        var t = (b.note || "No clear takeaway from the transcript.");
        if(b.callback) t += " Callback: " + b.callback + ".";
        document.getElementById("cp-sum-t").textContent = t;
        var logBtn = document.getElementById("cp-log");
        var labels = {interested: "Interested", sent_link: "Sent the link", vendor_listed: "On their vendor list",
                      voicemail: "Voicemail", no_answer: "No answer", not_interested: "Not interested", bad_number: "Bad number"};
        if(b.outcome && labels[b.outcome]){ logBtn.textContent = "Log as " + labels[b.outcome]; logBtn.dataset.o = b.outcome; logBtn.hidden = false; }
        else if(b.outcome === "callback"){ logBtn.textContent = "Schedule the callback below"; logBtn.dataset.o = ""; logBtn.hidden = false; }
        else { logBtn.hidden = true; }
        cpSum.hidden = false; cpBox.hidden = false; cpBox.scrollTop = 0;
      }).catch(function(){});
    }, 3500);
  }
  document.getElementById("cp-use-note").addEventListener("click", function(){
    if(!cpSuggested) return;
    document.getElementById("note").value = (cpSuggested.note || "").slice(0, 1000);
    showToast("Note filled in — edit it if you like, then tap the outcome.");
  });
  document.getElementById("cp-log").addEventListener("click", function(){
    var o = this.dataset.o;
    if(!o){ document.getElementById("callback").scrollIntoView({behavior: "smooth", block: "center"}); return; }
    if(!document.getElementById("note").value.trim() && cpSuggested) document.getElementById("note").value = (cpSuggested.note || "").slice(0, 1000);
    var btn = document.querySelector('#outcomes button[data-o="' + o + '"]');
    if(btn) btn.click();
  });

  // ---- power dial: auto-advance + voicemail drop ----
  var PD_KEY = "umuve_desk_power_dial";
  var pdToggle = document.getElementById("pd-toggle");
  var pdBar = document.getElementById("pdbar");
  var pdTxt = document.getElementById("pd-txt");
  var pdSkip = document.getElementById("pd-skip");
  var pdPlay = document.getElementById("pd-play");
  var powerOn = localStorage.getItem(PD_KEY) === "1";
  var pdArmed = false, pdCountdown = null, pdVm = {has_voicemail: false}, recordingVm = false;
  var PD_DELAY = 4;
  function pdRender(){
    pdToggle.classList.toggle("on", powerOn);
    pdBar.hidden = !(powerOn && deskReady);
    pdPlay.hidden = !pdVm.has_voicemail;
    if(pdCountdown) return;
    pdTxt.className = "pd-txt";
    if(!pdVm.has_voicemail){
      pdTxt.innerHTML = "<b>Power dial on.</b> No voicemail recorded yet — machines will ring through to you. Record one to drop it automatically.";
    } else {
      pdTxt.innerHTML = "<b>Power dial on.</b> Log an outcome and the next card dials itself. Machines get your " + (pdVm.seconds ? pdVm.seconds + "s " : "") + "voicemail and move on.";
    }
    pdSkip.hidden = true;
  }
  function loadVm(){
    post("/api/va/desk/voicemail", {action: "status"}).then(function(r){ if(r.status === 200){ pdVm = r.body; pdRender(); } }).catch(function(){});
  }
  function pdCancel(){ if(pdCountdown){ clearInterval(pdCountdown); pdCountdown = null; } pdRender(); }
  function pdStartCountdown(){
    if(window.__deskCallsBlocked){ showToast("Calling window is closed — power dial paused."); return; }
    if(!powerOn || !deskReady || !current || activeCall || recordingVm) return;
    var left = PD_DELAY;
    var who = current.company;
    pdCancel();
    function paint(){ pdTxt.className = "pd-txt count"; pdTxt.innerHTML = "Dialing <b>" + who + "</b> in " + left + "…"; pdSkip.hidden = false; }
    paint();
    pdCountdown = setInterval(function(){
      left -= 1;
      if(left <= 0){ clearInterval(pdCountdown); pdCountdown = null; pdRender();
        if(current && current.company === who) startDeskCall((current.direct_tel || current.tel || "").replace("tel:", ""));
        return; }
      paint();
    }, 1000);
  }
  pdSkip.addEventListener("click", pdCancel);
  pdToggle.addEventListener("click", function(){
    powerOn = !powerOn; localStorage.setItem(PD_KEY, powerOn ? "1" : "0");
    if(!powerOn) pdCancel(); else loadVm();
    pdRender();
    showToast(powerOn ? "Power dial on — the next card dials after you log an outcome." : "Power dial off.");
  });
  document.getElementById("pd-record").addEventListener("click", function(){
    if(!device || !deskReady || activeCall) return;
    recordingVm = true;
    device.connect({params: {mode: "record_vm", va_name: vaName()}}).then(function(call){
      bindCall(call, "Recording your voicemail — press # when done");
      call.on("disconnect", function(){ recordingVm = false; setTimeout(loadVm, 1500); });
    }).catch(function(e){ recordingVm = false; showToast("Couldn't start recording: " + callErrorText(e)); });
  });
  pdPlay.addEventListener("click", function(){ if(pdVm.play_url) window.open(pdVm.play_url, "_blank", "noopener"); });
  function pdAfterCall(){
    // Decide what to do once a power-dialed call ends: machine → log voicemail and advance.
    if(!powerOn || !current) return;
    var pid = current.id;
    post("/api/va/desk/last-call", {prospect_id: pid}).then(function(r){
      if(r.status !== 200 || !r.body.call || !current || current.id !== pid) return;
      var st = r.body.call.status || "";
      if(st === "vm_dropped" || st === "machine"){
        setBusy(true);
        post("/api/va/calls/log", {prospect_id: pid, outcome: "voicemail", note: document.getElementById("note").value.trim(),
                                   send_text: sendText.checked}).then(function(rr){
          setBusy(false);
          if(rr.status !== 200){ fail(rr.status, rr.body); return; }
          showToast(st === "vm_dropped" ? "Machine — your voicemail was dropped. Next card." : "Machine — logged as voicemail. Next card.");
          pdArmed = true; render(rr.body);
        }).catch(function(){ setBusy(false); });
      } else {
        pdTxt.className = "pd-txt"; pdTxt.innerHTML = "<b>Call ended.</b> Tap what happened and the next card dials itself.";
      }
    }).catch(function(){});
  }
  function tick(){ stripTime.textContent = fmtDur((Date.now() - callStart) / 1000); }
  function bindCall(call, who){
    activeCall = call;
    // desk-dialpad.js needs the live call to send extension digits (DTMF)
    window.__deskActiveCall = call;
    try { window.dispatchEvent(new CustomEvent("desk:call", {detail: {live: true}})); } catch(e){}
    stripWho.textContent = who;
    stripState.textContent = "Calling…"; stripTime.textContent = "";
    strip.hidden = false; strip.classList.remove("live");
    muteBtn.textContent = "Mute";
    call.on("accept", function(){
      stripState.textContent = "Connected"; strip.classList.add("live");
      callStart = Date.now(); clearInterval(callTimer); callTimer = setInterval(tick, 1000); tick();
    });
    function done(){
      clearInterval(callTimer); strip.hidden = true; strip.classList.remove("live", "failed");
      activeCall = null;
      window.__deskActiveCall = null;
      try { window.dispatchEvent(new CustomEvent("desk:call", {detail: {live: false}})); } catch(e){}
      cpStop();
      if(current && !recordingVm) cpSummarize();
      if(current) setTimeout(function(){ loadThread(current); if(!recordingVm) pdAfterCall(); }, 1800);
    }
    function failed(msg){
      clearInterval(callTimer); activeCall = null;
      strip.classList.remove("live"); strip.classList.add("failed");
      stripState.textContent = "Call failed: " + msg; stripTime.textContent = "";
      showToast("Call failed: " + msg);
      setTimeout(function(){ strip.hidden = true; strip.classList.remove("failed"); }, 9000);
    }
    call.on("disconnect", done); call.on("cancel", done); call.on("reject", done);
    call.on("error", function(e){ failed(callErrorText(e)); });
  }
  deskCallBtn.addEventListener("click", function(){
    if(!current) return;
    startDeskCall((current.direct_tel || current.tel || "").replace("tel:", ""));
  });
  hangBtn.addEventListener("click", function(){ if(activeCall) activeCall.disconnect(); });
  muteBtn.addEventListener("click", function(){
    if(!activeCall) return;
    var m = !activeCall.isMuted(); activeCall.mute(m); muteBtn.textContent = m ? "Unmute" : "Mute";
  });
  document.getElementById("inc-answer").addEventListener("click", function(){
    var call = pendingIncoming; if(!call) return;
    pendingIncoming = null; incoming.hidden = true;
    bindCall(call, incWho.textContent); call.accept();
    var digits = incWho.textContent.replace(/\D/g, "");
    if(digits.length === 10){
      post("/api/va/calls/search", {q: digits}).then(function(r){
        if(r.status === 200 && r.body.results && r.body.results.length === 1){
          post("/api/va/calls/get", {prospect_id: r.body.results[0].id}).then(function(rr){ if(rr.status === 200) render(rr.body); });
        }
      }).catch(function(){});
    }
  });
  document.getElementById("inc-decline").addEventListener("click", function(){
    var call = pendingIncoming; if(!call) return;
    pendingIncoming = null; incoming.hidden = true; call.reject();
  });

  // boot: a saved login goes straight to the desk; the first API call re-verifies it
  if(signedIn()){ showTool(); fetchNext(); } else { showGate(); }
  reveal(document);
})();
"""
