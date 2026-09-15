"""A verbal yes that never became a job.

On 5 September a caller in Pembroke Pines asked about two projection TVs,
Maya quoted $119, he agreed to schedule the pickup, and the call ended. No
job was created. He got an automated "book online" text and was never called
back. In the 30 days to 15 September that was the closest Umuve came to
revenue.

Two things let that happen: `create_booking` demanded an email address the
caller never gave (fixed in routes/vapi.py), and nothing downstream noticed
that a priced, agreed call had produced nothing. This module is the second
half — it reads the end-of-call report and, when the transcript shows a price
and an agreement but no booking, puts the caller on the desk as a callback a
human has to work.

It never messages the customer. All it does is create the internal task and
alert the team, so it is safe to run on live calls from the first minute.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from models import db, DeskActivity
from models_inbound import CallbackRequest

logger = logging.getLogger(__name__)

# What the caller said, or what the call summary says they did. Kept broad on
# purpose: a false positive costs one phone call, a false negative costs a job.
_AGREE = (
    "agree to schedule", "agreed to schedule", "agrees to schedule",
    "agree to book", "agreed to book", "agreed to the price",
    "book it", "booked it", "let's do it", "lets do it", "let's book",
    "sign me up", "sounds good", "that works", "that'll work", "that will work",
    "go ahead and schedule", "go ahead and book", "yes let's", "yes lets",
    "i'll take it", "ill take it", "when can you come", "come get it",
    "put me down", "schedule the pickup", "schedule me",
)
# Never treat these as a yes even when an agreement phrase is nearby.
_REFUSE = (
    "too expensive", "too much", "i'll think about it", "ill think about it",
    "call me back later", "not interested", "shop around", "someone else",
    "no thanks", "no thank you", "changed my mind",
)

MARKER = "MISSED BOOKING"


def _flag(name, default=True):
    try:
        from flags import flag
        return flag(name)
    except Exception:
        return default


def enabled():
    return _flag("missed_booking_capture")


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def digits_of(phone):
    d = re.sub(r"\D", "", phone or "")
    return d[-10:] if len(d) >= 10 else d


def pretty(d):
    return "({}) {}-{}".format(d[:3], d[3:6], d[6:]) if len(d) == 10 else (d or "unknown")


def price_in(text):
    """The largest dollar figure the call mentioned, which is the quote."""
    found = []
    for raw in re.findall(r"\$\s?([0-9][0-9,]*(?:\.[0-9]{2})?)", text or ""):
        try:
            found.append(float(raw.replace(",", "")))
        except ValueError:
            continue
    return max(found) if found else None


def was_priced(transcript, summary=""):
    blob = "{}\n{}".format(transcript or "", summary or "")
    if "$" in blob:
        return True
    return bool(re.search(r"\b\d{2,4}\s?dollars\b", blob, re.I))


def looks_like_yes(transcript, summary=""):
    """Did this caller agree to have the work done?"""
    blob = " ".join("{}\n{}".format(transcript or "", summary or "").lower().split())
    if not blob:
        return False
    if any(r in blob for r in _REFUSE):
        return False
    return any(a in blob for a in _AGREE)


def should_capture(transcript, summary="", booking_created=False):
    if booking_created or not enabled():
        return False
    return was_priced(transcript, summary) and looks_like_yes(transcript, summary)


def already_captured(call_id, phone_digits):
    """One task per call, however many times Vapi re-posts the report."""
    q = DeskActivity.query.filter(DeskActivity.kind == "callback",
                                  DeskActivity.body.like("%" + MARKER + "%"))
    if call_id:
        return q.filter(DeskActivity.body.like("%" + str(call_id)[:40] + "%")).first() is not None
    if phone_digits:
        return q.filter(DeskActivity.phone_digits == phone_digits,
                        DeskActivity.status == "open").first() is not None
    return False


def capture(phone, call_id=None, summary="", transcript="", name=None):
    """Put the caller on the desk as a callback. Returns the row, or None."""
    d = digits_of(phone)
    if len(d) != 10:
        logger.info("missed booking with no usable number (call %s)", call_id)
        return None
    if already_captured(call_id, d):
        return None
    total = price_in("{}\n{}".format(transcript or "", summary or ""))
    quote = " — quoted ${:.0f}".format(total) if total else ""
    body = "{} — {} agreed on the call{} and no job exists. Call them back and book it. [{}]".format(
        MARKER, pretty(d), quote, (call_id or "no-call-id")[:40])
    try:
        cb = CallbackRequest(phone_digits=d, name=(name or None),
                             call_sid=str(call_id)[:64] if call_id else None,
                             requested_for=_now(), note=(summary or transcript or "")[:2000] or None)
        db.session.add(cb)
        db.session.add(DeskActivity(prospect_id=None, phone_digits=d, kind="callback", direction="in",
                                    body=body[:2000], status="open", va_name=None))
        db.session.commit()
    except Exception:
        logger.exception("could not record the missed booking for %s", d[-4:])
        db.session.rollback()
        return None
    logger.info("missed booking captured: %s%s (call %s)", pretty(d), quote, call_id)
    try:
        from booking_alerts import ops_alert
        ops_alert("Missed booking: {} said yes{}".format(pretty(d), quote),
                  "\n".join([body, "", (summary or "")[:600],
                             "", "This caller agreed and has no job. Call them."]),
                  kind="missed_booking")
    except Exception:
        logger.exception("missed-booking alert failed")
    return cb
