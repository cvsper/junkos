"""Ops sentinel — watches the job/money states no other safety net covers.

Fills the gaps found in the 2026-07-03 lifecycle audit:
  A. assigned/accepted with no start-progress timeout
  B. en_route / arrived / started stalls (previously invisible — the no-show
     watchdog's "open" set never included the real in-progress statuses)
  C. ASAP jobs (scheduled_at NULL) invisible to the scheduled-time watchdog
  D. concierge payouts stuck pending_connect with money silently owed
  E. Stripe payouts stuck failed with no escalation
  H. assigned hauler offline mid-job

Runs every 10 minutes via APScheduler (see scheduler.py). Every alert is
exactly-once per (kind, job) via AutomationEvent. Alert-only by design: the
sentinel never mutates job state — it makes humans aware, fast.
"""
import logging
import os
from datetime import datetime, timedelta

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

# Stage stall thresholds (minutes since last state change / anchor)
ASAP_UNASSIGNED_MIN = 20      # confirmed (paid), never dispatched, no schedule
STALL_ACCEPT_ASAP_MIN = 45    # assigned/accepted, ASAP job, no movement
STALL_ACCEPT_SCHED_MIN = 30   # assigned/accepted, past scheduled time
STALL_EN_ROUTE_MIN = 120
STALL_ARRIVED_MIN = 60
STALL_STARTED_MIN = 360
PAYOUT_FAILED_HOURS = 18
PAYOUT_OWED_HOURS = 24
MAX_SMS_PER_RUN = 5


def _utcnow():
    from models import utcnow
    return utcnow()


def _once(kind, subject_id, detail=None, subject_type="job"):
    """True exactly once per (kind, subject). Safe under concurrent runs."""
    from models import db
    from models import AutomationEvent
    try:
        db.session.add(AutomationEvent(kind=kind, subject_type=subject_type,
                                       subject_id=str(subject_id), detail=detail))
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        return False


def _alert(subject, lines, sms_budget):
    """SMS (OPERATOR_PHONE -> ADMIN_PHONE fallback) + email ADMIN_EMAIL.
    Never raises. Returns remaining sms budget."""
    body = "\n".join(lines)
    phone = os.environ.get("OPERATOR_PHONE") or os.environ.get("ADMIN_PHONE", "")
    if phone and sms_budget > 0:
        try:
            from notifications import send_sms
            send_sms(phone, "🛰️ {}\n{}".format(subject, body[:280]))
            sms_budget -= 1
        except Exception:
            logger.exception("sentinel SMS failed")
    admin_email = os.environ.get("ADMIN_EMAIL", "")
    if admin_email:
        try:
            from email_service import send_email
            send_email(admin_email, "🛰️ Sentinel: {}".format(subject),
                       "<pre>{}</pre>".format(body))
        except Exception:
            logger.exception("sentinel email failed")
    logger.warning("SENTINEL %s | %s", subject, body.replace("\n", " | "))
    return sms_budget


def _job_label(job):
    code = getattr(job, "confirmation_code", None) or str(job.id)[:8]
    return "{} — {} (${:.0f})".format(code, (job.address or "?")[:60],
                                      float(job.total_price or 0))


def run_sentinel(app):
    with app.app_context():
        from models import db
        from models import Contractor, Job

        now = _utcnow()
        budget = MAX_SMS_PER_RUN

        # --- C: ASAP paid jobs that never got dispatched -------------------
        cutoff = now - timedelta(minutes=ASAP_UNASSIGNED_MIN)
        rows = (Job.query.filter(Job.status == "confirmed",
                                 Job.scheduled_at.is_(None),
                                 Job.created_at <= cutoff).all())
        for job in rows:
            if _once("asap_unassigned", job.id):
                budget = _alert("ASAP job undispatched {}min+".format(ASAP_UNASSIGNED_MIN),
                                [_job_label(job), "status=confirmed, no hauler assigned",
                                 "Booked {}Z".format(job.created_at)], budget)

        # --- A: assigned/accepted with no start progress -------------------
        rows = Job.query.filter(Job.status.in_(("assigned", "accepted"))).all()
        for job in rows:
            anchor = None
            if job.scheduled_at is not None:
                if now > _aware(job.scheduled_at) + timedelta(minutes=STALL_ACCEPT_SCHED_MIN):
                    anchor = "scheduled {}Z".format(job.scheduled_at)
            else:
                changed = _aware(job.updated_at) or _aware(job.created_at)
                if changed and now > changed + timedelta(minutes=STALL_ACCEPT_ASAP_MIN):
                    anchor = "last movement {}Z".format(changed)
            if anchor and _once("stall_" + job.status, job.id):
                budget = _alert("Job stuck in {}".format(job.status),
                                [_job_label(job), anchor,
                                 "Hauler has not started — chase or reassign"], budget)

        # --- B: mid-job stalls (en_route / arrived / started) ---------------
        stage_limits = {"en_route": STALL_EN_ROUTE_MIN, "arrived": STALL_ARRIVED_MIN,
                        "started": STALL_STARTED_MIN}
        rows = Job.query.filter(Job.status.in_(tuple(stage_limits))).all()
        for job in rows:
            changed = _aware(job.updated_at) or _aware(job.created_at)
            limit = stage_limits[job.status]
            if changed and now > changed + timedelta(minutes=limit):
                if _once("stall_" + job.status, job.id):
                    budget = _alert("Job stalled {}min+ in {}".format(limit, job.status),
                                    [_job_label(job), "since {}Z".format(changed),
                                     "Call the hauler — customer may be waiting"], budget)

        # --- H: hauler offline mid-job --------------------------------------
        rows = Job.query.filter(Job.status.in_(("assigned", "accepted", "en_route"))).all()
        for job in rows:
            cid = job.driver_id or job.operator_id
            if not cid:
                continue
            c = db.session.get(Contractor, cid)
            # concierge haulers work by SMS with no app presence — skip them
            if c is None or c.is_online or getattr(c, "is_concierge", False):
                continue
            if _once("offline_midjob", job.id):
                budget = _alert("Hauler OFFLINE mid-job",
                                [_job_label(job),
                                 "{} is offline while job is {}".format(
                                     getattr(c, "name", cid), job.status),
                                 "If unreachable, cancel+redispatch from admin"], budget)

        # --- E: payouts stuck failed (payout state lives on Payment) ---------
        from models import Payment
        cutoff = now - timedelta(hours=PAYOUT_FAILED_HOURS)
        rows = (db.session.query(Payment, Job)
                .join(Job, Payment.job_id == Job.id)
                .filter(Payment.payout_status == "failed",
                        Job.status == "completed",
                        Job.completed_at <= cutoff).all())
        for payment, job in rows:
            if _once("payout_failed", job.id):
                budget = _alert("Payout FAILING {}h+".format(PAYOUT_FAILED_HOURS),
                                [_job_label(job),
                                 "${:.2f} owed — Stripe transfer keeps failing; "
                                 "check hauler's Connect account".format(
                                     payment.driver_payout_amount or 0)],
                                budget)

        # --- D: concierge money owed (daily digest) --------------------------
        cutoff = now - timedelta(hours=PAYOUT_OWED_HOURS)
        rows = (db.session.query(Payment, Job)
                .join(Job, Payment.job_id == Job.id)
                .filter(Payment.payout_status == "pending_connect",
                        Job.status == "completed",
                        Job.completed_at <= cutoff).all())
        if rows:
            total = sum(float(p.driver_payout_amount or 0) for p, _j in rows)
            day_key = now.strftime("%Y-%m-%d")
            if _once("payout_owed", day_key, subject_type="digest"):
                budget = _alert("Concierge payouts owed",
                                ["{} completed job(s) with money owed ${:.2f}".format(
                                    len(rows), total),
                                 "Oldest: {}".format(_job_label(rows[0][1])),
                                 "Pay + mark in the concierge console"], budget)

        logger.info("sentinel sweep done (sms budget left %d)", budget)
