"""The evening-before text to the assigned hauler, on top of hauler_confirm.py.

hauler_confirm.py puts every job in the next ~36 hours on the desk until a
person has heard "yes, I'm coming", and releases an unconfirmed hauler thirty
minutes before the slot. This module gets that "yes" without a person having
to chase it: at 6pm Florida time the hauler is texted one question; YES marks
the job confirmed on the desk, NO releases them and re-dispatches on the spot,
and at 8:30pm silence pages a person so it's chased before bed, not at 7am.
The customer is never messaged from here.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from models import db, Job
from models_sameday import HaulerConfirmation
from hauler_confirm import upcoming, mark_confirmed, redispatch, _hauler, _page
from timeutils import fmt_local

logger = logging.getLogger(__name__)

YES_WORDS = ("yes", "y", "yeah", "yep", "yup", "confirm", "confirmed", "ok", "okay", "si", "sí")
NO_WORDS = ("no", "n", "nope", "cant", "can't", "cannot", "unable")
REPLY_WINDOW_HOURS = 30
ASK_WINDOW_HOURS = 36


def _now():
    return datetime.now(timezone.utc)


def _digits(v):
    return "".join(ch for ch in (v or "") if ch.isdigit())[-10:]


def _slot(job):
    t = fmt_local(job.scheduled_at, "%I:%M %p", default="")
    return t.lstrip("0") if t else "tomorrow"


def ask():
    """Text every hauler on an unconfirmed job in the next 36 hours. Returns the count."""
    from sms_service import send_sms_async
    asked = 0
    for row in upcoming(hours=ASK_WINDOW_HOURS):
        job = db.session.get(Job, row.get("job_id"))
        if job is None or job.hauler_confirmed_at or not job.driver_id:
            continue
        if HaulerConfirmation.query.filter_by(job_id=job.id, contractor_id=job.driver_id).first():
            continue
        c, name, phone = _hauler(job)
        digits = _digits(phone)
        if len(digits) != 10:
            _page("Tomorrow's hauler has no phone on file",
                  ["Job {} ({}) at {} is assigned to {} with no number to confirm on. Sort it in /va/dispatch."
                   .format(job.id[:8], row.get("when"), row.get("address"), name or "a hauler")])
            continue
        body = ("Umuve: you're on tomorrow at {} — {}. Reply YES to confirm, or NO if you can't make it."
                .format(_slot(job), (job.address or "address in the app")[:80]))
        try:
            send_sms_async("+1" + digits, body)
            db.session.add(HaulerConfirmation(job_id=job.id, contractor_id=job.driver_id, phone_digits=digits,
                                              status="asked", asked_at=_now()))
            db.session.commit()
            asked += 1
        except Exception:
            logger.exception("confirmation text failed for job %s", job.id)
            db.session.rollback()
    return asked


def handle_reply(from_phone, body):
    """YES / NO from a hauler with an open question. Returns the reply text, or None to fall through."""
    words = (body or "").strip().lower().split()
    if not words:
        return None
    w = words[0].strip(".!,")
    if w not in YES_WORDS and w not in NO_WORDS:
        return None
    digits = _digits(from_phone)
    row = (HaulerConfirmation.query
           .filter(HaulerConfirmation.phone_digits == digits, HaulerConfirmation.status == "asked",
                   HaulerConfirmation.asked_at >= _now() - timedelta(hours=REPLY_WINDOW_HOURS))
           .order_by(HaulerConfirmation.asked_at.desc()).first())
    if row is None:
        return None
    job = db.session.get(Job, row.job_id)
    yes = w in YES_WORDS
    row.status = "confirmed" if yes else "declined"
    row.replied_at = _now()
    row.reply = (body or "")[:160]
    if job is not None:
        _, name, _ = _hauler(job)
        if yes:
            mark_confirmed(job, "text from {}".format(name or "hauler"), note="Replied YES to the evening-before text")
        else:
            res = redispatch(job, "hauler-sms", "hauler texted NO the evening before",
                             va_name="dispatch", count_no_show=False)
            _page("Tomorrow's hauler can't make it: job {}".format(job.id[:8]),
                  ["{} replied NO for {} at {}.".format(name or "The hauler", fmt_local(job.scheduled_at, "%a %-I:%M %p"), job.address),
                   "Released and offered to {} nearby hauler(s).".format(res.get("waved", 0)),
                   "Confirm the replacement in /va/dispatch."])
    db.session.commit()
    if yes:
        return "Thanks, you're confirmed for tomorrow. Text this number if anything changes."
    return "Got it, we'll cover it. Thanks for letting us know."


def sweep_unanswered():
    """8:30pm: no answer yet. Page a person now; the desk queue and the
    30-minutes-out check in hauler_confirm.py do the rest."""
    cutoff = _now() - timedelta(hours=2)
    rows = HaulerConfirmation.query.filter(HaulerConfirmation.status == "asked",
                                           HaulerConfirmation.asked_at <= cutoff).all()
    lines, n = [], 0
    for row in rows:
        job = db.session.get(Job, row.job_id)
        if job is None or job.hauler_confirmed_at:
            row.status = "confirmed" if job is not None else "no_reply"
            continue
        row.status = "no_reply"
        _, name, phone = _hauler(job)
        lines.append("{} at {} — {} ({}) hasn't answered.".format(
            fmt_local(job.scheduled_at, "%a %-I:%M %p"), job.address, name or "hauler", phone or "no phone"))
        n += 1
    db.session.commit()
    if lines:
        _page("{} of tomorrow's jobs still unconfirmed".format(n),
              lines + ["", "Call them tonight, or line up cover in /va/dispatch."])
    return n


def run_ask(app):
    with app.app_context():
        try:
            logger.info("evening-before confirmations asked: %d", ask())
        except Exception:
            logger.exception("evening-before ask failed")


def run_sweep(app):
    with app.app_context():
        try:
            logger.info("evening-before unanswered: %d", sweep_unanswered())
        except Exception:
            logger.exception("evening-before sweep failed")
