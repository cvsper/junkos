"""Turning "interested" into work.

In the 30 days to 15 Sep the desk made 736 dials, got 226 connects, 70
interested and 31 wins — and booked $0. Nothing asked an interested property
manager to actually put a pickup on the books; a win set a follow-up date and
went back in the queue.

This closes that. Three parts:

  offer_url(prospect)     a signed link that books a first pickup and comes
                          back attributed to that prospect
  send_offer(prospect)    one text, in the VA's name, with that link
  nurture_sweep()         the ones who said yes and still have no job get one
                          nudge, then are left alone

and `link_booking(job, digits)` so a booking from any of it marks the prospect
as real revenue instead of a remembered phone call.

The nurture text ships behind a flag that is OFF, per the rule learned when a
sweep texted four real people before anyone looked at it.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from datetime import datetime, timedelta, timezone

from models import db, CallProspect

logger = logging.getLogger(__name__)

# How long after "interested" we nudge, and how many times. Once. A second
# unprompted text to a business that already said yes is how you become spam.
NUDGE_AFTER_DAYS = int(os.environ.get("FIRST_JOB_NUDGE_DAYS", "3") or 3)
NUDGE_WINDOW_DAYS = int(os.environ.get("FIRST_JOB_NUDGE_WINDOW_DAYS", "21") or 21)
INTERESTED = ("interested", "vendor_listed")


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _env(k):
    return (os.environ.get(k) or "").strip()


def _secret():
    return (_env("RATE_CARD_SECRET") or _env("SECRET_KEY")
            or _env("TRIXIE_ASSISTANT_PASSCODE") or "umuve-first-job")


def sign(prospect_id):
    return hmac.new(_secret().encode(), ("first-job:" + str(prospect_id)).encode(),
                    hashlib.sha256).hexdigest()[:20]


def check_sig(prospect_id, sig):
    return hmac.compare_digest(sign(prospect_id), str(sig or ""))


def offer_url(prospect):
    """A booking link that knows who it came from.

    It lands on the partner request page, not the consumer checkout: 29 links
    to office lines produced zero bookings, because a property manager does
    not put a card into a six-step form. They tell us what, where and when,
    and a person confirms."""
    base = (_env("FRONTEND_URL") or "https://app.goumuve.com").rstrip("/")
    if "app." not in base:
        base = "https://app.goumuve.com"
    return "{}/partners/start?p={}&s={}".format(base, prospect.id, sign(prospect.id))


def offer_info(prospect, va_name=None):
    """What the request page needs to greet them by name and know who it is."""
    from rate_card import public_url
    from desk_line import desk_number
    first = (prospect.contact_name or "").split()[0] if prospect.contact_name else ""
    d = _digits(desk_number())
    return {
        "prospect_id": prospect.id,
        "company": prospect.company,
        "first_name": first,
        "city": prospect.city,
        "va_name": _va_name(va_name),
        "desk_number": "({}) {}-{}".format(d[:3], d[3:6], d[6:]) if len(d) == 10 else None,
        "desk_tel": "+1" + d if len(d) == 10 else None,
        "rate_card_url": public_url(prospect.id),
        "already_booked": bool(prospect.job_id),
    }


def record_open(prospect):
    """The first time they open the link is the signal; keep it."""
    if prospect.offer_opened_at is None:
        prospect.offer_opened_at = _now()
        db.session.commit()
        return True
    return False


def pickup_request(prospect, data):
    """A business told us what, where and when. That is the desk's job now:
    an open callback with everything on it, the prospect bumped to the top
    of the queue, and a text to the VA's cell so it isn't missed."""
    from models_inbound import CallbackRequest
    what = _text(data.get("what"), 300)
    address = _text(data.get("address"), 300)
    when = _text(data.get("when"), 80)
    name = _text(data.get("name"), 120)
    phone = _digits(data.get("phone"))
    email = _text(data.get("email"), 254)
    notes = _text(data.get("notes"), 500)
    if not what:
        return None, "Tell us what needs to go."
    if not phone and not _digits(prospect.direct_phone) and not _digits(prospect.phone):
        return None, "Add a number we can confirm on."
    parts = ["Pickup request from {}".format(prospect.company), "what: " + what]
    if address:
        parts.append("where: " + address)
    if when:
        parts.append("when: " + when)
    if name or phone or email:
        parts.append("contact: " + " ".join(x for x in (name, ("(" + phone[:3] + ") " + phone[3:6] + "-" + phone[6:]) if len(phone) == 10 else "", email) if x))
    if notes:
        parts.append("notes: " + notes)
    note = " | ".join(parts)
    cb = CallbackRequest(phone_digits=(phone if len(phone) == 10 else (_digits(prospect.direct_phone) or _digits(prospect.phone))),
                         name=name or prospect.contact_name, note=note[:2000], requested_for=_now(), status="open")
    db.session.add(cb)
    if name and not prospect.contact_name:
        prospect.contact_name = name
    if len(phone) == 10 and not prospect.direct_phone:
        prospect.direct_phone = phone
    if email and not prospect.email:
        prospect.email = email
    if prospect.status in ("queued", "dead"):
        prospect.status = "interested"
    prospect.next_followup_at = _now()
    prospect.last_note = note[:2000]
    db.session.commit()
    try:
        from growth import notify_reply
        notify_reply(prospect, "Pickup request: " + what[:80])
    except Exception:
        logger.exception("notify_reply failed")
    try:
        from desk_line import _ping_forward
        _ping_forward(prospect, cb.phone_digits, "PICKUP REQUEST — " + what[:60] + (" · " + when if when else ""))
    except Exception:
        logger.exception("forward ping failed")
    return cb, None


def _text(v, limit):
    v = " ".join(str(v or "").split())
    return v[:limit]


# --------------------------------------------------------------------------
# Month-end: the businesses that have us on file get one useful text
# --------------------------------------------------------------------------
VENDOR_TOUCH_DAYS = (25, 26, 27, 28)          # move-outs cluster at month end
VENDOR_TOUCH_GAP_DAYS = 20                    # never twice in a month


def vendor_month_end_text(prospect, va_name=None):
    from rate_card import public_url
    from desk_line import desk_number
    first = (prospect.contact_name or "").split()[0] if prospect.contact_name else ""
    greet = "Hi {},".format(first) if first else "Hi there,"
    d = _digits(desk_number())
    desk = "({}) {}-{}".format(d[:3], d[3:6], d[6:]) if len(d) == 10 else "this number"
    return ("{greet} it's {va} with Umuve. Move-outs this week? Text {desk} the unit "
            "count and what's left behind and you'll have a price back in minutes and a "
            "same-day slot held. Rate card: {rc}. Reply STOP to opt out."
            ).format(greet=greet, va=_va_name(va_name), desk=desk, rc=public_url(prospect.id))


def due_for_vendor_touch(limit=100, include_skipped=False):
    gap = _now() - timedelta(days=VENDOR_TOUCH_GAP_DAYS)
    rows = (CallProspect.query
            .filter(CallProspect.status == "vendor_listed", CallProspect.job_id.is_(None))
            .filter((CallProspect.last_texted_at.is_(None)) | (CallProspect.last_texted_at <= gap))
            .order_by(CallProspect.updated_at.asc()).limit(limit).all())
    if include_skipped:
        return rows
    return [p for p in rows if skip_reason(p) is None]


def vendor_month_end_sweep(dry_run=None, force_day=False):
    """Once a month, around the 25th, one text to every business with us on
    their vendor list. Off unless `vendor_month_end` is on."""
    today = _now().day
    if not force_day and today not in VENDOR_TOUCH_DAYS:
        return {"due": 0, "sent": 0, "dry_run": True, "companies": [], "skipped": [],
                "note": "runs on the {}th-{}th".format(VENDOR_TOUCH_DAYS[0], VENDOR_TOUCH_DAYS[-1])}
    rows = due_for_vendor_touch()
    if dry_run is None:
        try:
            from flags import flag
            dry_run = not flag("vendor_month_end")
        except Exception:
            dry_run = True
    skipped = [{"company": p.company, "why": skip_reason(p)}
               for p in due_for_vendor_touch(include_skipped=True) if skip_reason(p)]
    out = {"due": len(rows), "sent": 0, "dry_run": bool(dry_run),
           "companies": [p.company for p in rows[:50]], "skipped": skipped}
    if dry_run:
        return out
    from desk_line import send_desk_text
    for p in rows:
        digits = _digits(p.direct_phone) or _digits(p.phone)
        if not digits:
            continue
        sid = send_desk_text("+1" + digits, vendor_month_end_text(p), prospect=p)
        if sid:
            p.last_texted_at = _now()
            out["sent"] += 1
    db.session.commit()
    logger.info("vendor month-end: %d due, %d sent", out["due"], out["sent"])
    return out


def _digits(v):
    d = "".join(ch for ch in str(v or "") if ch.isdigit())
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return d if len(d) == 10 else ""


def _va_name(va_name=None):
    return (va_name or _env("DESK_VA_NAME") or "Tracy").split()[0]


def offer_text(prospect, va_name=None):
    first = (prospect.contact_name or "").split()[0] if prospect.contact_name else ""
    hi = "Hi {}, ".format(first) if first else ""
    return ("{}it's {} with Umuve. Here's the link to put your first pickup on the books — "
            "pick a time, we quote it up front, and you only pay when it's done: {}\n"
            "Text a photo of anything you want priced first. Reply STOP to opt out."
            ).format(hi, _va_name(va_name), offer_url(prospect))


def send_offer(prospect, va_name=None, force=False):
    """One text with the booking link. Returns (sent, reason)."""
    if prospect is None:
        return False, "no prospect"
    if prospect.job_id:
        return False, "they already have a job"
    why = skip_reason(prospect)
    if why and not force:
        return False, why
    if prospect.offer_sent_at and not force:
        return False, "already sent"
    digits = _digits(prospect.direct_phone) or _digits(prospect.phone) or prospect.phone_digits
    if not _digits(digits):
        return False, "no textable number"
    try:
        from desk_line import send_desk_text
        sid = send_desk_text("+1" + _digits(digits), offer_text(prospect, va_name),
                             prospect=prospect, va_name=va_name)
    except Exception:
        logger.exception("first-job offer text failed for %s", prospect.id)
        return False, "the text didn't go through"
    if not sid:
        return False, "the text didn't go through"
    prospect.offer_sent_at = _now()
    db.session.commit()
    return True, None


def link_booking(job, digits=None, prospect_id=None):
    """A booking that came from the desk's work — attribute it. Never raises."""
    try:
        p = None
        if prospect_id:
            p = db.session.get(CallProspect, str(prospect_id))
        if p is None:
            d = _digits(digits or (job.customer.phone if getattr(job, "customer", None) else None))
            if d:
                p = (CallProspect.query
                     .filter(db.or_(CallProspect.phone_digits == d,
                                    CallProspect.direct_phone.ilike("%" + d[-7:] + "%")))
                     .order_by(CallProspect.updated_at.desc()).first())
        if p is None or p.job_id:
            return None
        p.job_id = job.id
        p.job_value = float(getattr(job, "total_price", None) or 0)
        p.status = "converted"
        p.last_outcome = "converted"
        p.next_followup_at = None
        try:
            from crm import set_stage
            set_stage(p, "won", by="system", force=True)
        except Exception:
            pass
        db.session.commit()
        logger.info("prospect %s (%s) booked job %s — $%.0f", p.id, p.company, job.id, p.job_value or 0)
        try:
            from booking_alerts import ops_alert
            ops_alert("Desk win booked work: {}".format(p.company),
                      "\n".join(["{} · {}".format(p.company, p.city or ""),
                                 "${:.0f} · job {}".format(p.job_value or 0,
                                                           job.confirmation_code or job.id[:8]),
                                 "This is the one that counts."]))
        except Exception:
            pass
        return p
    except Exception:
        logger.exception("first-job attribution failed")
        db.session.rollback()
        return None


# Numbers that already told us texting them is pointless or dangerous. The
# apartment-office auto-responders are the ones that traded ~1,100 messages
# with Maya on 11 Sep and burned $20 of Twilio credit in a night.
_DEAD_NUMBER = ("can't be received", "cannot be received", "unable to receive",
                "not a valid phone", "landline", "undeliverable", "message blocked")


def skip_reason(prospect):
    """Why this prospect must not be texted, or None."""
    note = (prospect.last_note or "")
    low = " ".join(note.split()).lower()
    if any(m in low for m in _DEAD_NUMBER):
        return "that number can't receive texts"
    said = note.split("THEY TEXTED:", 1)[1] if "THEY TEXTED:" in note else ""
    if said:
        try:
            from sms_guard import looks_automated
            if looks_automated(said):
                return "their line is an auto-responder"
        except Exception:
            pass
        try:
            from leads import looks_like_autoreply
            if looks_like_autoreply(said):
                return "their line is an auto-responder"
        except Exception:
            pass
    return None


def due_for_nudge(limit=200, include_skipped=False):
    """Said yes, never booked, long enough to ask once — and textable.

    A business that already answered with a consent bot or a "this number
    can't receive texts" is excluded: texting it again costs money and, in the
    auto-responder case, risks the loop that burned a night of credit.
    """
    cutoff = _now() - timedelta(days=NUDGE_AFTER_DAYS)
    floor = _now() - timedelta(days=NUDGE_WINDOW_DAYS)
    rows = (CallProspect.query
            .filter(CallProspect.status.in_(INTERESTED),
                    CallProspect.job_id.is_(None),
                    CallProspect.offer_sent_at.is_(None),
                    CallProspect.updated_at <= cutoff,
                    CallProspect.updated_at >= floor)
            .order_by(CallProspect.updated_at.asc()).limit(limit).all())
    if include_skipped:
        return rows
    return [p for p in rows if skip_reason(p) is None]


def nurture_sweep(dry_run=None):
    """One booking link to everyone who said yes and never booked.

    Off unless `first_job_nudge` is on. `dry_run` lists who would get it
    without sending, which is how this gets turned on safely.
    """
    rows = due_for_nudge()
    if dry_run is None:
        try:
            from flags import flag
            dry_run = not flag("first_job_nudge")
        except Exception:
            dry_run = True
    skipped = [{"company": p.company, "why": skip_reason(p)}
               for p in due_for_nudge(include_skipped=True) if skip_reason(p)]
    out = {"due": len(rows), "sent": 0, "dry_run": bool(dry_run),
           "companies": [p.company for p in rows[:25]],
           "skipped": skipped}
    if dry_run:
        return out
    for p in rows:
        ok, _why = send_offer(p)
        if ok:
            out["sent"] += 1
    logger.info("first-job nudge: %d due, %d sent", out["due"], out["sent"])
    return out


def scoreboard(days=30):
    """What the desk's work actually produced. A win is a job, not an outcome."""
    since = _now() - timedelta(days=days)
    # "interested" means said yes and STILL owes us a first job — someone who
    # booked has stopped being a prospect and started being a customer.
    interested = CallProspect.query.filter(CallProspect.status.in_(INTERESTED),
                                           CallProspect.job_id.is_(None)).count()
    offered = CallProspect.query.filter(CallProspect.offer_sent_at.isnot(None)).count()
    booked = CallProspect.query.filter(CallProspect.job_id.isnot(None)).all()
    recent = [p for p in booked if p.updated_at and p.updated_at >= since]
    revenue = sum(p.job_value or 0 for p in recent)
    return {
        "days": days,
        "interested_now": interested,
        "offers_sent": offered,
        "booked_ever": len(booked),
        "booked_in_window": len(recent),
        "revenue_in_window": round(revenue, 2),
        "conversion": (round(len(booked) / (interested + len(booked)), 3)
                       if (interested + len(booked)) else None),
        "waiting_on_an_offer": len(due_for_nudge(limit=1000)),
    }
