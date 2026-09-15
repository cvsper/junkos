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
    """A booking link that knows who it came from."""
    base = (_env("FRONTEND_URL") or "https://app.goumuve.com").rstrip("/")
    return "{}/book?p={}&s={}".format(base, prospect.id, sign(prospect.id))


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


def due_for_nudge(limit=200):
    """Said yes, never booked, and it has been long enough to ask once."""
    cutoff = _now() - timedelta(days=NUDGE_AFTER_DAYS)
    floor = _now() - timedelta(days=NUDGE_WINDOW_DAYS)
    return (CallProspect.query
            .filter(CallProspect.status.in_(INTERESTED),
                    CallProspect.job_id.is_(None),
                    CallProspect.offer_sent_at.is_(None),
                    CallProspect.updated_at <= cutoff,
                    CallProspect.updated_at >= floor)
            .order_by(CallProspect.updated_at.asc()).limit(limit).all())


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
    out = {"due": len(rows), "sent": 0, "dry_run": bool(dry_run),
           "companies": [p.company for p in rows[:25]]}
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
