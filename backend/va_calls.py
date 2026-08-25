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
    (("property", "hoa", "apartment", "commercial", "office", "institution",
      "hotel"), "property"),
    (("storage",), "storage"),
    (("estate", "auction", "antiques", "thrift"), "estate"),
    (("real estate", "staging", "probate"), "realtor"),
    (("investor", "flipper"), "flipper"),
    (("senior",), "senior"),
    (("moving",), "mover"),
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


def _card_payload(p, va_name):
    d = p.to_dict()
    d["opener"] = opener_for(p.category).format(va=(va_name or "Tracy").split()[0])
    d["tel"] = "tel:+1" + p.phone_digits if len(p.phone_digits) == 10 else "tel:" + p.phone
    direct = _digits(p.direct_phone) if p.direct_phone else ""
    d["direct_tel"] = "tel:+1" + direct if len(direct) == 10 else None
    d["is_followup"] = bool(p.next_followup_at)
    return d


# ---------------------------------------------------------------------------
# VA-facing API (passcode-gated, same code as /va)
# ---------------------------------------------------------------------------

@vacalls_bp.route("/api/va/calls/next", methods=["POST"])
@_ratelimit
def calls_next():
    data = request.get_json(silent=True) or {}
    if not _passcode_ok(data.get("code")):
        return jsonify({"error": "That code didn't work."}), 401
    p = next_card()
    stats = day_stats()
    if not p:
        nxt = (CallProspect.query
               .filter(CallProspect.status.in_(WORKABLE_STATUSES),
                       CallProspect.next_followup_at.isnot(None))
               .order_by(CallProspect.next_followup_at.asc()).first())
        return jsonify({"empty": True, "stats": stats,
                        "next_due": nxt.next_followup_at.isoformat() if nxt else None}), 200
    return jsonify({"card": _card_payload(p, data.get("va_name")), "stats": stats}), 200


@vacalls_bp.route("/api/va/calls/log", methods=["POST"])
@_ratelimit
def calls_log():
    data = request.get_json(silent=True) or {}
    if not _passcode_ok(data.get("code")):
        return jsonify({"error": "That code didn't work."}), 401
    outcome = (data.get("outcome") or "").strip()
    if outcome not in OUTCOMES:
        return jsonify({"error": "Unknown outcome."}), 400
    p = db.session.get(CallProspect, data.get("prospect_id") or "")
    if not p:
        return jsonify({"error": "Prospect not found — reload the page."}), 404
    note = (data.get("note") or "").strip()[:1000]
    va_name = (data.get("va_name") or "").strip()[:80]
    apply_outcome(p, outcome, note, va_name)
    db.session.commit()

    texted, text_reason = False, None
    if data.get("send_text"):
        texted, text_reason = maybe_send_followup_text(p, outcome, va_name)
        db.session.commit()

    nxt = next_card()
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
    if not _passcode_ok(data.get("code")):
        return jsonify({"error": "That code didn't work."}), 401
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
    if not _passcode_ok(data.get("code")):
        return jsonify({"error": "That code didn't work."}), 401
    p = db.session.get(CallProspect, data.get("prospect_id") or "")
    if not p:
        return jsonify({"error": "Prospect not found."}), 404
    return jsonify({"card": _card_payload(p, data.get("va_name")),
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
    if not _passcode_ok(data.get("code")):
        return jsonify({"error": "That code didn't work."}), 401
    p = db.session.get(CallProspect, data.get("prospect_id") or "")
    if not p:
        return jsonify({"error": "Prospect not found — reload the page."}), 404
    va_name = (data.get("va_name") or "").strip()[:80]
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
    if not _passcode_ok(data.get("code")):
        return jsonify({"error": "That code didn't work."}), 401
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
    return jsonify({"ok": True,
                    "card": _card_payload(p, data.get("va_name"))}), 200


# ---------------------------------------------------------------------------
# Admin: seed/merge + stats
# ---------------------------------------------------------------------------

@vacalls_bp.route("/api/admin/call-prospects/import", methods=["POST"])
@require_admin
def import_prospects(user_id):
    """Body: {"rows": [{tier, category, company, phone, city, contact_name,
    why, angle}]}. Merges on phone digits — existing rows keep their status."""
    data = request.get_json(silent=True) or {}
    rows = data.get("rows") or []
    added, skipped, invalid = 0, 0, 0
    for r in rows:
        digits = _digits(r.get("phone"))
        if len(digits) != 10 or not (r.get("company") or "").strip():
            invalid += 1
            continue
        if CallProspect.query.filter_by(phone_digits=digits).first():
            skipped += 1
            continue
        try:
            tier = int(str(r.get("tier") or "2").strip()[0])
        except (ValueError, IndexError):
            tier = 2
        db.session.add(CallProspect(
            tier=tier if tier in (1, 2, 3) else 2,
            category=(r.get("category") or "").strip()[:60],
            company=r["company"].strip()[:200],
            phone=(r.get("phone") or "").strip()[:40],
            phone_digits=digits,
            city=(r.get("city") or "").strip()[:80] or None,
            contact_name=(r.get("contact_name") or "").strip()[:120] or None,
            why=(r.get("why") or "").strip() or None,
            angle=(r.get("angle") or "").strip() or None,
        ))
        added += 1
    db.session.commit()
    total = CallProspect.query.count()
    return jsonify({"success": True, "added": added, "skipped_dupes": skipped,
                    "invalid": invalid, "total": total}), 200


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
    return Response(CALLS_HTML, mimetype="text/html")


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
<link rel="stylesheet" href="/va/app.css?v=3" />
<link rel="stylesheet" href="/va/calls.css?v=6" />
</head>
<body>
<div id="app">
  <section id="gate" class="gate">
    <div class="gatewrap">
      <img class="brand-lg rv" src="/va/logo.png" alt="Umuve" /><div class="eyebrow rv">Internal · VA suite</div>
      <h1 class="display" id="display-gate" aria-label="Call Desk">CALL&nbsp;DESK</h1>
      <p class="sub rv">One card at a time. Tap the number, make the call, tap what happened.</p>
      <form id="gate-form" autocomplete="off" class="rv">
        <label class="lbl" for="code">Access code</label>
        <input id="code" type="password" autocomplete="off" placeholder="Enter your code" />
        <button class="btn" type="submit">Open the desk</button>
        <p id="gate-err" class="err" hidden></p>
      </form>
      <p class="hint rv">Same code as your other VA tools.</p>
    </div>
  </section>

  <section id="tool" class="tool" hidden>
    <header class="bar">
      <a class="back" href="/va" aria-label="Back to VA tools">←</a>
      <div class="wordmark">CALL&nbsp;DESK</div>
      <div class="bar-sub" id="daybar">—</div>
      <button class="back" id="search-toggle" type="button" aria-label="Find a business">⌕</button>
    </header>

    <div class="body" id="deck">
      <div id="searchbox" hidden>
        <input id="search-q" type="search" autocomplete="off"
               placeholder="Someone calling back? Type their name, city, or number" />
        <div id="search-results"></div>
      </div>
      <div id="empty" class="deskcard" hidden>
        <div class="q-chip done">QUEUE CLEAR</div>
        <h2 class="co">Nothing due right now</h2>
        <p class="whytext" id="empty-sub">Every prospect is either scheduled for a future touch or finished. Nice work.</p>
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
        <details class="openerbox"><summary>Your opener</summary><p id="c-opener"></p></details>
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
  </section>
</div>
<script src="/va/calls.js?v=6"></script>
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
"""


CALLS_JS = r"""(function(){
  var KEY = "umuve_coach_code";      // shared login across the VA suite
  var VA_KEY = "umuve_va_name";
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
  function vaName(){ return localStorage.getItem(VA_KEY) || ""; }
  function showTool(){ gate.hidden = true; tool.hidden = false; }
  function showGate(msg){
    tool.hidden = true; gate.hidden = false; reveal(gate);
    if(msg && gateErr){ gateErr.textContent = msg; gateErr.hidden = false; }
    var c = document.getElementById("code"); if(c) c.focus();
  }

  var gateForm = document.getElementById("gate-form");
  if(gateForm){
    gateForm.addEventListener("submit", function(e){
      e.preventDefault();
      var v = document.getElementById("code").value.trim();
      if(!v){ gateErr.textContent = "Enter your access code."; gateErr.hidden = false; return; }
      localStorage.setItem(KEY, v);
      showTool(); fetchNext();
    });
  }

  function post(path, body){
    body.code = code();
    body.va_name = vaName();
    return fetch(path, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body)
    }).then(function(r){
      return r.json().then(function(j){ return {status: r.status, body: j}; });
    });
  }

  function fmtPhone(p){ return p; }

  function setDaybar(stats){
    if(!stats) return;
    var el = document.getElementById("daybar");
    el.textContent = stats.calls_today + " calls today · " +
      stats.interested_today + " interested · " +
      (stats.due_now + stats.fresh) + " in queue";
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
      if(resp.next_due){
        var d = new Date(resp.next_due + "Z");
        document.getElementById("empty-sub").textContent =
          "Next follow-up comes due " + d.toLocaleString([], {weekday:"long", hour:"numeric", minute:"2-digit"}) + ". Check back then.";
      }
      current = null;
      return;
    }
    var c = resp.card;
    current = c;
    empty.hidden = true;
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
    if(status === 401){ localStorage.removeItem(KEY); showGate(body.error || "That code didn't work."); return; }
    deskErr.textContent = (body && body.error) || "Something went wrong — try again.";
    deskErr.hidden = false;
  }

  function fetchNext(){
    post("/api/va/calls/next", {}).then(function(r){
      if(r.status !== 200){ fail(r.status, r.body); return; }
      render(r.body);
    }).catch(function(){ fail(0, {error: "No connection — check your internet and try again."}); });
  }

  function setBusy(b){
    busy = b;
    document.querySelectorAll("#outcomes button").forEach(function(btn){ btn.disabled = b; });
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
      document.getElementById("c-direct-num").textContent =
        (c.contact_name ? c.contact_name + " — " : "") + c.direct_phone;
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

  // boot: saved code -> straight to the desk; the first API call re-verifies it
  if(code()){ showTool(); fetchNext(); } else { showGate(); }
  reveal(document);
})();
"""
