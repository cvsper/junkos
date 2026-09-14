"""A hauler who already signed up must never be pitched again.

Tracy works the call queue from `call_prospects`. Signing up writes a
`contractors` row and nothing ever told the queue, so a hauler who joined —
through the JOBS keyword, the app, a Meta ad, or a referral — stayed in the
list and got recruited a second time. Embarrassing on the phone, and it
burns the queue on people who already said yes.

Three layers, because signups arrive by several paths and only one of them
carries a phone number at the moment the account is made:

  retire_for_phone(digits)  at signup — precise, immediate
  guard(prospect)           when the desk is about to hand out a card — the
                            failsafe; nothing reaches Tracy without this check
  sweep()                   nightly — catches accounts whose phone arrived
                            later (app signups start with e-mail only) and
                            cleans up the backlog so the queue count is honest

Retiring means `status="converted"`, no follow-up, and a logged outcome, so
the card reads as a win in the pipeline instead of vanishing.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from models import db, CallProspect, Contractor, User

logger = logging.getLogger(__name__)

WHY = "signed up as a hauler"
_CACHE = {"at": 0.0, "digits": {}}
_CACHE_SECONDS = 120


def _now_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def digits_of(v):
    d = "".join(ch for ch in str(v or "") if ch.isdigit())
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return d if len(d) == 10 else ""


def hauler_digits(fresh=False):
    """{phone digits: contractor id} for everyone who has a hauler account.

    Cached for a couple of minutes: the desk asks on every card, and the set
    changes a handful of times a day.
    """
    now = time.time()
    if not fresh and _CACHE["digits"] and now - _CACHE["at"] < _CACHE_SECONDS:
        return _CACHE["digits"]
    out = {}
    try:
        rows = (db.session.query(User.phone, Contractor.id)
                .join(Contractor, Contractor.user_id == User.id)
                .filter(User.phone.isnot(None)).all())
        for phone, cid in rows:
            d = digits_of(phone)
            if d:
                out.setdefault(d, cid)
    except Exception:
        logger.exception("hauler phone lookup failed")
        return _CACHE["digits"]          # stale beats wrong here
    _CACHE["digits"] = out
    _CACHE["at"] = now
    return out


def _invalidate():
    _CACHE["at"] = 0.0


def matches(prospect, table=None):
    """The contractor id this prospect already belongs to, or None.

    Checks the listed number and the decision maker's direct line, because a
    hauler often signs up from the cell Tracy captured, not the office line.
    """
    if prospect is None:
        return None
    table = hauler_digits() if table is None else table
    for value in (prospect.phone_digits, prospect.direct_phone, prospect.phone):
        d = digits_of(value)
        if d and d in table:
            return table[d]
    return None


def retire(prospect, contractor_id=None, why=WHY):
    """Take a prospect out of the queue as a win. Returns True if it changed."""
    if prospect is None or prospect.status == "converted":
        return False
    prospect.status = "converted"
    prospect.next_followup_at = None
    prospect.last_outcome = "converted"
    note = "Auto: {}{}.".format(why, " (contractor {})".format(contractor_id[:8]) if contractor_id else "")
    prospect.last_note = note if not prospect.last_note else (prospect.last_note + " · " + note)[:1000]
    prospect.updated_at = _now_naive()
    try:
        from models import CallAttempt
        db.session.add(CallAttempt(prospect_id=prospect.id, outcome="converted",
                                   note=note, va_name="system"))
    except Exception:
        logger.exception("could not log the auto-convert for prospect %s", prospect.id)
    try:
        from crm import set_stage
        set_stage(prospect, "won", by="system", force=True)
    except Exception:
        pass                              # the stage board is a nicety, the queue is the point
    logger.info("prospect %s (%s) retired: %s", prospect.id, prospect.company, why)
    return True


def retire_for_phone(phone, contractor_id=None, why=WHY, commit=True):
    """Called the moment a hauler account is created. Never raises."""
    try:
        d = digits_of(phone)
        if not d:
            return 0
        _invalidate()
        rows = (CallProspect.query
                .filter(CallProspect.status != "converted")
                .filter(db.or_(CallProspect.phone_digits == d, CallProspect.direct_phone.ilike("%" + d[-7:] + "%")))
                .all())
        hits = [p for p in rows if d in (digits_of(p.phone_digits), digits_of(p.direct_phone), digits_of(p.phone))]
        n = sum(1 for p in hits if retire(p, contractor_id, why))
        if n and commit:
            db.session.commit()
        return n
    except Exception:
        logger.exception("retire_for_phone failed for %s", str(phone)[-4:])
        try:
            db.session.rollback()
        except Exception:
            pass
        return 0


def guard(prospect):
    """True when this card must NOT be handed to a VA. Retires it on the spot."""
    cid = matches(prospect)
    if not cid:
        return False
    try:
        if retire(prospect, cid):
            db.session.commit()
    except Exception:
        logger.exception("guard could not retire prospect %s", getattr(prospect, "id", "?"))
        db.session.rollback()
    return True


def sweep(limit=5000):
    """Nightly + on demand: retire every workable prospect who is already a hauler."""
    table = hauler_digits(fresh=True)
    if not table:
        return {"checked": 0, "retired": 0}
    from va_calls import WORKABLE_STATUSES
    rows = (CallProspect.query
            .filter(CallProspect.status.in_(WORKABLE_STATUSES))
            .limit(limit).all())
    retired = []
    for p in rows:
        cid = matches(p, table)
        if cid and retire(p, cid):
            retired.append(p.company or p.id)
    if retired:
        try:
            db.session.commit()
        except Exception:
            logger.exception("signup sweep commit failed")
            db.session.rollback()
            return {"checked": len(rows), "retired": 0, "error": "commit failed"}
    logger.info("signup sweep: %d checked, %d retired", len(rows), len(retired))
    return {"checked": len(rows), "retired": len(retired), "companies": retired[:25]}
