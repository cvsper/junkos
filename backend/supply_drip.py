"""Supply-activation drip — turns registered-but-idle haulers into online supply.

The recruiting funnels (JOBS keyword, /optext, Maya, referrals) create
Contractor rows; nothing followed up when a hauler registered and then never
went online. This sweep nudges exactly three times, then offers the concierge
path (run jobs by SMS, no app). Registered haulers have an existing business
relationship with us — these are transactional activation messages, not cold
outreach (cold email lives in operator_outreach.py).

Exactly-once per (kind, contractor) via AutomationEvent. Daily via APScheduler.
Gate: ACTIVATION_DRIP_ENABLED (default on; set "false" to silence).
"""
import logging
import os
from datetime import timedelta

logger = logging.getLogger(__name__)


def _aware(dt):
    """DB DateTime columns round-trip naive (SQLite + PG TIMESTAMP) — never
    compare them raw against aware utcnow(). Same lesson as dispatcher's
    _aware_utc (the bug that broke every broadcast accept link)."""
    import datetime as _dt
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=_dt.timezone.utc)
    return dt

NUDGE_1_DAYS = 1
NUDGE_2_DAYS = 3
NUDGE_3_DAYS = 7
DOC_NUDGE_DAYS = 2
MAX_SMS_PER_RUN = 15


def _once(kind, subject_id):
    from models import db
    from models import AutomationEvent
    try:
        db.session.add(AutomationEvent(kind=kind, subject_type="contractor",
                                       subject_id=str(subject_id)))
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        return False


def run_activation_drip(app):
    if os.environ.get("ACTIVATION_DRIP_ENABLED", "true").lower() != "true":
        return
    with app.app_context():
        from models import db
        from models import Contractor, Job, User, utcnow
        from sms_service import send_sms

        now = utcnow()
        sent = 0

        def _phone(c):
            u = db.session.get(User, c.user_id) if c.user_id else None
            return getattr(u, "phone", None) or getattr(c, "phone", None)

        # --- Approved app haulers who never went online ----------------------
        idle = Contractor.query.filter(
            Contractor.approval_status == "approved",
            Contractor.is_online == False,  # noqa: E712
            Contractor.is_concierge == False,  # noqa: E712
        ).all()
        for c in idle:
            if sent >= MAX_SMS_PER_RUN:
                break
            has_worked = Job.query.filter(
                (Job.driver_id == c.id) | (Job.operator_id == c.id),
                Job.status == "completed",
            ).first() is not None
            if has_worked:
                continue
            age = now - (_aware(c.created_at) or now)
            phone = _phone(c)
            if not phone:
                continue
            msg = None
            if age >= timedelta(days=NUDGE_3_DAYS) and _once("activation_nudge_3", c.id):
                msg = ("Umuve: don't want to run the app? No problem — we can "
                       "send you jobs by TEXT. You reply YES to a job, do the "
                       "pickup, get paid. Reply CONCIERGE to switch, or STOP to opt out.")
            elif age >= timedelta(days=NUDGE_2_DAYS) and _once("activation_nudge_2", c.id):
                msg = ("Umuve: jobs in your area pay $80-200+ and you keep the "
                       "tips. You're approved — tap Go Online in the Umuve Pro "
                       "app to start getting offers.")
            elif age >= timedelta(days=NUDGE_1_DAYS) and _once("activation_nudge_1", c.id):
                msg = ("Umuve: you're approved! 🎉 One step left — open Umuve "
                       "Pro and tap Go Online. First job usually comes fast.")
            if msg:
                try:
                    send_sms(phone, msg)
                    sent += 1
                except Exception:
                    logger.exception("activation nudge failed for %s", c.id)

        # --- Applicants stuck in pending (docs not finished) ------------------
        pending = Contractor.query.filter(
            Contractor.approval_status == "pending",
        ).all()
        for c in pending:
            if sent >= MAX_SMS_PER_RUN:
                break
            age = now - (_aware(c.created_at) or now)
            phone = _phone(c)
            if not phone or age < timedelta(days=DOC_NUDGE_DAYS):
                continue
            if _once("doc_nudge", c.id):
                try:
                    send_sms(phone,
                             "Umuve: your hauler application is almost done — "
                             "we just need your docs (insurance/license). Finish "
                             "in the Umuve Pro app and start earning this week.")
                    sent += 1
                except Exception:
                    logger.exception("doc nudge failed for %s", c.id)

        logger.info("activation drip done (%d SMS)", sent)
