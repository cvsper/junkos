"""Incoming leads, all channels, one list — and nothing waits.

Today a customer who *calls* the desk gets a good experience. Everyone else
leaks: web quotes and Meta forms never reach Tracy, a phone quote that didn't
book is never followed up, a booking made on the phone doesn't record where
the lead came from, and when Maya transfers a call her summary goes out as an
SMS instead of onto the screen.

This module is the seam that closes those gaps:

  source_for_number     the number they dialled → channel (desk / google / meta)
  collect / untouched   every open lead from every source, one shape
  speed_to_lead_sweep   untouched for 2 minutes → text in the VA's name,
                        escalate in the work queue
  schedule_followup     quoted, didn't book → +2h and +24h texts, day-3 item
  remember_maya_handoff Maya's transfer summary, on screen for 30 minutes
  dispute_list          Google leads marked spam / not a fit, inside the
                        dispute window — money back
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from models import db, DeskSetting, DeskActivity, AbandonedBooking, User, Job
from models_leads import LeadTouch, QuoteFollowup
from desk_auth import desk_identity, desk_va_name, audit, require_desk, MANAGER_ROLES

try:
    from extensions import limiter
except Exception:  # pragma: no cover
    limiter = None

logger = logging.getLogger(__name__)
leads_bp = Blueprint("leads", __name__)
_ratelimit = (limiter.limit("300 per hour; 60 per minute") if limiter is not None else (lambda f: f))

SPEED_TO_LEAD_SECONDS = int(os.environ.get("SPEED_TO_LEAD_SECONDS", "120") or 120)
LEAD_WINDOW_DAYS = 7
MAYA_CONTEXT_TTL_MIN = 30
FOLLOWUP_STEPS_HOURS = (2, 24)          # texts; then a queue item on day 3
FOLLOWUP_QUEUE_DAY = 3
GOOGLE_DISPUTE_DAYS = 30

# Texts that are not a customer reaching out: our own lines talking to
# themselves, and a business autoresponder answering Tracy's outreach. Both
# showed up as "leads" on the first live run — and the speed-to-lead sweep
# would have texted them back.
AUTOREPLY_HINTS = ("thanks for contacting", "thank you for contacting", "auto-reply", "auto reply",
                   "automatic reply", "out of office", "we have received your", "we've received your",
                   "we'll get back to you", "will get back to you", "this is an automated")
SPEED_TO_LEAD_MAX_SECONDS = int(os.environ.get("SPEED_TO_LEAD_MAX_SECONDS", str(6 * 3600)) or 6 * 3600)


def own_numbers():
    """Digits of every number Umuve itself sends from. A text FROM one of these
    is a test or an echo, never a lead."""
    out = set()
    for var in ("DESK_TWILIO_NUMBER", "TWILIO_FROM_NUMBER", "PUBLIC_PHONE_NUMBER", "VAPI_PHONE_NUMBER",
                "GOOGLE_LSA_NUMBER", "META_ADS_NUMBER"):
        d = _digits(os.environ.get(var, ""))
        if d:
            out.add(d)
    out.update(source_numbers().keys())
    out.update({"5619441636", "8444356005"})       # Maya's line and the toll-free, known
    return out


def looks_like_autoreply(body):
    b = (body or "").strip().lower()
    return any(h in b for h in AUTOREPLY_HINTS)


SOURCE_LABELS = {"google": "Google", "meta": "Meta", "desk": "Desk", "web": "Web",
                 "maya": "Maya", "text": "Text", "unknown": "New"}


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _digits(v):
    d = re.sub(r"\D", "", v or "")
    return d[-10:] if len(d) >= 10 else d


def _pretty(d):
    d = _digits(d)
    return "({}) {}-{}".format(d[:3], d[3:6], d[6:]) if len(d) == 10 else (d or None)


def _age_label(seconds):
    if seconds < 60:
        return "{}s".format(int(seconds))
    if seconds < 3600:
        return "{} min".format(int(seconds // 60))
    if seconds < 86400:
        return "{}h".format(int(seconds // 3600))
    return "{}d".format(int(seconds // 86400))


# ---------------------------------------------------------------------------
# Source from the dialled number
# ---------------------------------------------------------------------------
def source_numbers():
    """{E.164 or digits: source}. INBOUND_SOURCE_NUMBERS is a JSON map; the
    single-purpose vars are the simple form."""
    out = {}
    raw = os.environ.get("INBOUND_SOURCE_NUMBERS", "")
    if raw:
        try:
            for k, v in json.loads(raw).items():
                out[_digits(k)] = (v or "").strip().lower()
        except Exception:
            logger.warning("INBOUND_SOURCE_NUMBERS is not valid JSON")
    for var, src in (("GOOGLE_LSA_NUMBER", "google"), ("META_ADS_NUMBER", "meta")):
        val = _digits(os.environ.get(var, ""))
        if val:
            out[val] = src
    return out


def source_for_number(to_number):
    return source_numbers().get(_digits(to_number), "desk")


# ---------------------------------------------------------------------------
# Touch state
# ---------------------------------------------------------------------------
def _touch_row(kind, ref_id, create=True, phone=None, source=None):
    row = LeadTouch.query.filter_by(kind=kind, ref_id=ref_id).first()
    if row is None and create:
        row = LeadTouch(kind=kind, ref_id=ref_id, phone_digits=_digits(phone) or None, source=source)
        db.session.add(row)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            row = LeadTouch.query.filter_by(kind=kind, ref_id=ref_id).first()
    return row


def touch(kind, ref_id, va_name, outcome=None, note=None, phone=None, source=None):
    row = _touch_row(kind, ref_id, phone=phone, source=source)
    if row is None:
        return None
    row.touched_at = row.touched_at or _now()
    row.touched_by = va_name or row.touched_by
    if outcome:
        row.outcome = outcome[:20]
    if note:
        row.note = note[:300]
    db.session.commit()
    return row


def touch_phone(digits, va_name, outcome=None, note=None):
    """Any action on a number touches every open lead for it."""
    digits = _digits(digits)
    if not digits:
        return 0
    n = 0
    for l in collect():
        if l["phone_digits"] == digits:
            touch(l["kind"], l["ref_id"], va_name, outcome=outcome, note=note,
                  phone=digits, source=l["source"])
            n += 1
    return n


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------
def _lead(kind, ref_id, *, phone, name, what, source, created_at, extra=None):
    d = {
        "kind": kind, "ref_id": ref_id,
        "phone_digits": _digits(phone) or None, "phone": _pretty(phone),
        "name": (name or "").strip() or None,
        "what": what, "source": source or "unknown",
        "source_label": SOURCE_LABELS.get(source or "unknown", (source or "New").title()),
        "created_at": created_at.isoformat() + "Z" if created_at else None,
        "age_seconds": (_now() - created_at).total_seconds() if created_at else 0,
    }
    d["age_label"] = _age_label(d["age_seconds"])
    if extra:
        d.update(extra)
    return d


def _calls(since):
    try:
        from models_inbound import InboundCall
    except Exception:
        return []
    rows = (InboundCall.query.filter(InboundCall.created_at >= since,
                                     InboundCall.kind.in_(("customer", "unknown")))
            .order_by(InboundCall.created_at.desc()).limit(200).all())
    out = []
    for r in rows:
        if (r.lead_outcome or "") in ("booked", "spam", "not_a_fit"):
            continue
        what = {"ringing": "call, nobody answered", "voicemail": "left a voicemail",
                "to_maya": "spoke to Maya", "answered_by_human": "spoke to the desk",
                "missed": "missed call", "no_answer": "missed call"}.get(r.disposition or "", r.disposition or "call")
        name = None
        try:
            from inbound import find_customer
            u = find_customer(r.phone_digits)
            name = u.name if u else None
        except Exception:
            pass
        if r.phone_digits in own_numbers():
            continue
        answered = bool(r.answered_by) or (r.disposition or "") == "answered_by_human"
        out.append(_lead("call", r.call_sid or r.id, phone=r.phone_digits, name=name, what=what,
                         source=r.source or ("maya" if r.disposition == "to_maya" else "desk"),
                         created_at=r.created_at,
                         extra={"disposition": r.disposition, "answered": answered}))
    return out


def _callbacks(since):
    try:
        from models_inbound import CallbackRequest
    except Exception:
        return []
    out = []
    for r in CallbackRequest.query.filter(CallbackRequest.status == "open",
                                          CallbackRequest.created_at >= since).all():
        out.append(_lead("callback", r.id, phone=r.phone_digits, name=r.name,
                         what="asked for a callback" + ((": " + r.note[:60]) if r.note else ""),
                         source="desk", created_at=r.created_at))
    return out


def _web(since):
    out = []
    rows = (AbandonedBooking.query.filter(AbandonedBooking.created_at >= since,
                                          AbandonedBooking.converted == False)  # noqa: E712
            .order_by(AbandonedBooking.created_at.desc()).limit(200).all())
    for r in rows:
        items = r.items if isinstance(r.items, list) else []
        what = ", ".join(str(i.get("name") or i.get("category") or "") for i in items[:3] if isinstance(i, dict))
        if r.estimated_price:
            what = (what + " · " if what else "") + "${:.0f} quote".format(r.estimated_price)
        src = (r.lead_source or "web").lower()
        src = "meta" if "meta" in src or "facebook" in src else ("google" if "google" in src or "lsa" in src else "web")
        out.append(_lead("web", r.id, phone=r.phone, name=r.name, what=what or "started a booking online",
                         source=src, created_at=r.created_at, extra={"email": r.email, "address": r.address}))
    return out


def _texts(since):
    """Customer texts to the desk line — inbound, from a number that is not a prospect."""
    rows = (DeskActivity.query.filter(DeskActivity.kind == "sms", DeskActivity.direction == "in",
                                      DeskActivity.prospect_id.is_(None),
                                      DeskActivity.created_at >= since)
            .order_by(DeskActivity.created_at.desc()).limit(200).all())
    seen, out = set(), []
    for r in rows:
        if r.phone_digits in seen:
            continue
        seen.add(r.phone_digits)
        body = (r.body or "").strip()
        if body.split(" ")[0].strip(".!,").lower() in ("stop", "unsubscribe", "jobs", "y", "n", "yes", "no"):
            continue
        if r.phone_digits in own_numbers() or looks_like_autoreply(body):
            continue
        out.append(_lead("text", r.id, phone=r.phone_digits, name=None,
                         what=("texted: " + body[:70]) if body else "sent a photo",
                         source="text", created_at=r.created_at))
    return out


_SOURCES = ("_calls", "_callbacks", "_web", "_texts")


def collect(days=LEAD_WINDOW_DAYS):
    since = _now() - timedelta(days=days)
    items, broken = [], []
    for name in _SOURCES:
        fn = globals().get(name)
        try:
            items.extend(fn(since))
        except Exception:
            logger.exception("lead source %s failed", name)
            broken.append(name.lstrip("_"))
    # one row per phone number: keep the newest, remember how many touches
    by_phone = {}
    for l in sorted(items, key=lambda x: x["created_at"] or "", reverse=True):
        key = l["phone_digits"] or (l["kind"] + ":" + l["ref_id"])
        if key in by_phone:
            by_phone[key]["contacts"] = by_phone[key].get("contacts", 1) + 1
            continue
        l["contacts"] = 1
        by_phone[key] = l
    leads = list(by_phone.values())
    # attach touch state
    if leads:
        rows = LeadTouch.query.filter(LeadTouch.kind.in_({l["kind"] for l in leads}),
                                      LeadTouch.ref_id.in_({l["ref_id"] for l in leads})).all()
        state = {(r.kind, r.ref_id): r for r in rows}
        for l in leads:
            r = state.get((l["kind"], l["ref_id"]))
            l["touched_at"] = r.touched_at.isoformat() + "Z" if r and r.touched_at else None
            l["touched_by"] = r.touched_by if r else None
            l["auto_text_at"] = r.auto_text_at.isoformat() + "Z" if r and r.auto_text_at else None
            l["outcome"] = r.outcome if r else None
            # a call a person picked up is touched by definition — the outcome
            # flow decides what happens next, the speed-to-lead clock does not
            if not l.get("touched_at") and l.get("answered"):
                l["touched_at"] = l["created_at"]
                l["touched_by"] = l.get("touched_by") or "desk"
    leads = [l for l in leads if (l.get("outcome") or "") not in ("booked", "spam", "not_a_fit")]
    order = {"google": 0, "meta": 1, "web": 2, "text": 3, "desk": 4, "maya": 5, "unknown": 6}
    leads.sort(key=lambda l: (bool(l.get("touched_at")), order.get(l["source"], 9), -l["age_seconds"]))
    return leads, broken


def untouched(min_age_seconds=0):
    leads, _ = collect()
    return [l for l in leads if not l.get("touched_at") and l["age_seconds"] >= min_age_seconds]


# ---------------------------------------------------------------------------
# Speed to lead
# ---------------------------------------------------------------------------
def _va_display_name():
    return (os.environ.get("DESK_VA_NAME") or "Tracy").strip()


def speed_to_lead_sweep():
    """Untouched for the window and never auto-texted → one text in the VA's
    name. Not a second one; the follow-up is a person calling."""
    sent = []
    try:
        from flags import flag
        if not flag("lead_auto_text"):
            return sent                              # kill switch
    except Exception:
        pass
    # "Calling you in a minute" is only true if someone is clocked in. The
    # posted hours are unset in production and read as always-open, which is
    # how four people got that promise at 6pm with nobody on shift.
    try:
        from inbound import humans_online
        in_hours = bool(humans_online())
    except Exception:
        in_hours = False
    for l in untouched(min_age_seconds=SPEED_TO_LEAD_SECONDS):
        if not l["phone_digits"] or l.get("auto_text_at"):
            continue
        if l["kind"] == "call" and l.get("answered"):
            continue                                  # they already spoke to a person
        if l["age_seconds"] > SPEED_TO_LEAD_MAX_SECONDS:
            continue                                  # stale — a person decides, not a bot
        if l["phone_digits"] in own_numbers():
            continue
        row = _touch_row(l["kind"], l["ref_id"], phone=l["phone_digits"], source=l["source"])
        if row is None or row.auto_text_at:
            continue
        first = (l["name"] or "").split()[0] if l["name"] else "there"
        va = _va_display_name()
        if in_hours:
            body = ("Hi {}, this is {} at Umuve — I saw you reached out about a pickup. "
                    "Calling you in a minute; if now's bad, reply with a good time.").format(first, va)
        else:
            body = ("Hi {}, this is {} at Umuve — got your request. I'll call you first thing "
                    "when we open. Reply with any details and I'll have a price ready.").format(first, va)
        try:
            from desk_line import send_desk_text
            send_desk_text("+1" + l["phone_digits"], body, va_name=va, log=True)
            row.auto_text_at = _now()
            db.session.commit()
            sent.append(l["phone_digits"])
        except Exception:
            logger.exception("speed-to-lead text failed for %s", l["phone_digits"][-4:])
            db.session.rollback()
    return sent


# ---------------------------------------------------------------------------
# Quote follow-ups
# ---------------------------------------------------------------------------
def schedule_followup(digits, name, quote_total, items=None, va_name=None):
    digits = _digits(digits)
    if not digits:
        return None
    # one open sequence per number
    open_row = QuoteFollowup.query.filter(QuoteFollowup.phone_digits == digits,
                                          QuoteFollowup.stopped_at.is_(None),
                                          QuoteFollowup.step < 3).first()
    if open_row:
        open_row.quote_total = quote_total or open_row.quote_total
        open_row.name = name or open_row.name
        db.session.commit()
        return open_row
    row = QuoteFollowup(phone_digits=digits, name=(name or "")[:120] or None, quote_total=quote_total,
                        items=json.dumps(items)[:2000] if items else None, va_name=va_name,
                        step=0, next_at=_now() + timedelta(hours=FOLLOWUP_STEPS_HOURS[0]))
    db.session.add(row)
    db.session.commit()
    return row


def stop_followups(phone, reason="manual"):
    digits = _digits(phone)
    if not digits:
        return 0
    n = 0
    for r in QuoteFollowup.query.filter(QuoteFollowup.phone_digits == digits,
                                        QuoteFollowup.stopped_at.is_(None)).all():
        r.stopped_at = _now()
        r.stop_reason = reason[:40]
        n += 1
    if n:
        db.session.commit()
    return n


def _booked_since(digits, since):
    try:
        from inbound import find_customer
        u = find_customer(digits)
        if not u:
            return False
        return Job.query.filter(Job.customer_id == u.id, Job.created_at >= since,
                                Job.status.notin_(("cancelled", "canceled"))).first() is not None
    except Exception:
        return False


def followup_sweep():
    """Send whichever step is due. Stops on its own when they book."""
    acted = []
    due = QuoteFollowup.query.filter(QuoteFollowup.stopped_at.is_(None),
                                     QuoteFollowup.next_at.isnot(None),
                                     QuoteFollowup.next_at <= _now()).limit(100).all()
    for r in due:
        if _booked_since(r.phone_digits, r.created_at):
            r.stopped_at = _now(); r.stop_reason = "booked"
            db.session.commit()
            acted.append((r.phone_digits[-4:], "booked"))
            continue
        first = (r.name or "").split()[0] if r.name else "there"
        va = r.va_name or _va_display_name()
        price = " (${:.0f})".format(r.quote_total) if r.quote_total else ""
        if r.step == 0:
            body = ("Hi {}, {} from Umuve — just checking you got the price{}. Want me to hold a "
                    "slot? Reply with a day and I'll lock it in.").format(first, va, price)
            r.next_at = _now() + timedelta(hours=FOLLOWUP_STEPS_HOURS[1] - FOLLOWUP_STEPS_HOURS[0])
        elif r.step == 1:
            body = ("Hi {}, {} again — still happy to help with that pickup{}. No pressure; if "
                    "you went another way just let me know and I'll stop bugging you.").format(first, va, price)
            r.next_at = _now() + timedelta(days=FOLLOWUP_QUEUE_DAY - 1)
        else:
            # day 3: no more texts — a person decides (surfaces via the work queue)
            r.step = 3; r.next_at = None
            db.session.commit()
            acted.append((r.phone_digits[-4:], "queued"))
            continue
        try:
            from desk_line import send_desk_text
            send_desk_text("+1" + r.phone_digits, body, va_name=va, log=True)
            r.step += 1
            r.last_sent_at = _now()
            db.session.commit()
            acted.append((r.phone_digits[-4:], "step{}".format(r.step)))
        except Exception:
            logger.exception("quote follow-up text failed for %s", r.phone_digits[-4:])
            db.session.rollback()
    return acted


def day3_followups():
    """Sequence exhausted, still not booked — a person decides. For the work queue."""
    out = []
    for r in QuoteFollowup.query.filter(QuoteFollowup.step == 3, QuoteFollowup.stopped_at.is_(None)).all():
        out.append({"id": r.id, "phone": _pretty(r.phone_digits), "phone_digits": r.phone_digits,
                    "name": r.name, "quote_total": r.quote_total,
                    "age_hours": round((_now() - r.created_at).total_seconds() / 3600.0, 1)})
    return out


# ---------------------------------------------------------------------------
# Maya handoff context
# ---------------------------------------------------------------------------
def remember_maya_handoff(phone, summary):
    digits = _digits(phone)
    if not digits or not summary:
        return False
    DeskSetting.put("maya_ctx:" + digits, json.dumps({"at": _now().isoformat(), "summary": summary[:1200]}))
    return True


def maya_context(digits):
    raw = DeskSetting.get("maya_ctx:" + _digits(digits))
    if not raw:
        return None
    try:
        d = json.loads(raw)
        at = datetime.fromisoformat(d["at"])
        if _now() - at > timedelta(minutes=MAYA_CONTEXT_TTL_MIN):
            return None
        return {"summary": d["summary"], "minutes_ago": int((_now() - at).total_seconds() // 60)}
    except Exception:
        return None


def whois_extras(digits):
    """What the inbound panel adds to the caller card."""
    digits = _digits(digits)
    source = None
    try:
        from models_inbound import InboundCall
        last = (InboundCall.query.filter(InboundCall.phone_digits == digits)
                .order_by(InboundCall.created_at.desc()).first())
        source = last.source if last else None
    except Exception:
        pass
    ctx = maya_context(digits)
    banner = None
    if source in ("google", "meta"):
        banner = "{} lead — paid".format(SOURCE_LABELS[source])
    elif ctx:
        banner = "Transferred from Maya"
    return {"source": source, "banner": banner, "maya_context": ctx}


def record_form_lead(phone, name, source="meta", items=None, email=None):
    """A form submission (Meta) becomes a row the desk can see. Never raises."""
    try:
        digits = _digits(phone)
        row = AbandonedBooking(email=(email or (digits + "@lead.local")), phone=("+1" + digits) if digits else None,
                               name=(name or "")[:255] or None, items=items if isinstance(items, list) else None,
                               step=0, lead_source=source, converted=False)
        db.session.add(row)
        db.session.commit()
        return row
    except Exception:
        logger.exception("record_form_lead failed")
        db.session.rollback()
        return None


# ---------------------------------------------------------------------------
# Google dispute list
# ---------------------------------------------------------------------------
def dispute_list(days=GOOGLE_DISPUTE_DAYS):
    try:
        from models_inbound import InboundCall
    except Exception:
        return []
    since = _now() - timedelta(days=days)
    rows = (InboundCall.query.filter(InboundCall.source == "google", InboundCall.created_at >= since,
                                     InboundCall.lead_outcome.in_(("spam", "not_a_fit")))
            .order_by(InboundCall.created_at.desc()).all())
    return [{"when": r.created_at.isoformat() + "Z", "phone": _pretty(r.phone_digits),
             "outcome": r.lead_outcome, "note": r.outcome_note,
             "days_left": max(0, days - int((_now() - r.created_at).days))} for r in rows]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
def _ident(data):
    ident = desk_identity(data)
    return ident, (desk_va_name(data) or (ident.get("name") if ident else None) or "someone")


@leads_bp.route("/api/va/leads/list", methods=["POST"])
@_ratelimit
def leads_list():
    data = request.get_json(silent=True) or {}
    ident, _ = _ident(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    leads, broken = collect()
    return jsonify({"leads": leads, "total": len(leads),
                    "untouched": sum(1 for l in leads if not l.get("touched_at")),
                    "paid": sum(1 for l in leads if l["source"] in ("google", "meta")),
                    "speed_to_lead_seconds": SPEED_TO_LEAD_SECONDS,
                    "day3": day3_followups(), "sources_failed": broken}), 200


@leads_bp.route("/api/va/leads/touch", methods=["POST"])
@_ratelimit
def leads_touch():
    data = request.get_json(silent=True) or {}
    ident, va = _ident(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    kind, ref = (data.get("kind") or "").strip(), (data.get("ref_id") or "").strip()
    outcome = (data.get("outcome") or "").strip().lower() or None
    if outcome and outcome not in ("booked", "not_a_fit", "spam", "no_answer", "quoted", "callback"):
        return jsonify({"error": "Outcome must be booked, not_a_fit, spam, no_answer, quoted or callback."}), 400
    note = (data.get("note") or "").strip()
    if data.get("phone") and not kind:
        n = touch_phone(data.get("phone"), va, outcome=outcome, note=note)
        return jsonify({"ok": True, "touched": n}), 200
    if not kind or not ref:
        return jsonify({"error": "Which lead?"}), 400
    row = touch(kind, ref, va, outcome=outcome, note=note, phone=data.get("phone"))
    # a call lead's outcome is what Google disputes are built from
    if kind == "call" and outcome:
        try:
            from models_inbound import InboundCall
            c = InboundCall.query.filter((InboundCall.call_sid == ref) | (InboundCall.id == ref)).first()
            if c:
                c.lead_outcome = outcome
                c.outcome_note = note[:300] or c.outcome_note
                db.session.commit()
        except Exception:
            logger.exception("lead outcome stamp failed")
    if outcome in ("booked", "not_a_fit", "spam") and data.get("phone"):
        stop_followups(data.get("phone"), outcome)
    audit("lead_touch", kind, ref, {"by": va, "outcome": outcome, "note": note[:80]})
    return jsonify({"ok": True, "touched": bool(row)}), 200


@leads_bp.route("/api/va/leads/disputes", methods=["POST"])
@require_desk(MANAGER_ROLES)
def leads_disputes(ident):
    rows = dispute_list()
    return jsonify({"leads": rows, "total": len(rows), "window_days": GOOGLE_DISPUTE_DAYS,
                    "how": "Google Ads → Local Services → Leads → mark 'Dispute' on each; "
                           "credits post on the next invoice."}), 200
