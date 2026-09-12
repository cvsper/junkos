"""
Umuve Background Scheduler

Runs periodic tasks:
- Generate jobs from due recurring bookings (hourly)
- Send 24-hour pickup reminders (hourly)

Only starts when ENABLE_SCHEDULER=true to prevent running on multiple instances.
"""

import os
import logging
from datetime import datetime, timezone, timedelta

from timeutils import fmt_local

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Liveness state (read by GET /api/ready -- see server.py)
# ---------------------------------------------------------------------------
# The scheduler shares a process with the web worker, so "the deploy is up"
# says nothing about whether background work is still firing. These stamps are
# what readiness actually inspects: a heartbeat job proves the scheduler thread
# is alive even during quiet hours, and the event listener records the last
# time each real job ran so a wedged job is visible (audit finding F26).
_SCHEDULER = None
_SCHEDULER_STARTED_AT = None
_LAST_JOB_RUN = {}          # job_id -> {"at": datetime, "ok": bool, "error": str|None}
_IN_FLIGHT = {}             # job_id -> datetime submitted; cleared when it finishes (hung jobs show here)
_EVENTS = []                # last scheduler events (submitted / missed / max-instances), newest last
_LOG_RING = []              # last apscheduler + scheduler log lines, newest last


class _RingHandler(logging.Handler):
    """Keeps the last N log records in memory so /api/ready can show what the
    scheduler said on a host where nobody can read the process log."""
    def __init__(self, ring, n=40):
        super().__init__(level=logging.INFO)
        self.ring, self.n = ring, n

    def emit(self, record):
        try:
            self.ring.append("{} {} {}".format(
                datetime.now(timezone.utc).strftime("%H:%M:%S"), record.levelname[:1], self.format(record)[:220]))
            del self.ring[:-self.n]
        except Exception:
            pass
_HEARTBEAT_JOB_ID = "readiness_heartbeat"
# Heartbeat runs every 5 minutes; readiness allows 3 missed beats before it
# calls the scheduler dead, so a single slow pass is not an outage.
_HEARTBEAT_MINUTES = 5
_HEARTBEAT_STALE_AFTER = timedelta(minutes=_HEARTBEAT_MINUTES * 3)


def _readiness_heartbeat():
    """Cheap no-op job whose only product is a fresh timestamp."""
    logger.debug("scheduler heartbeat")


def _note_event(event):
    """APScheduler listener for the non-completion events: submitted, missed,
    max-instances. A job that is submitted and never completes is a hung job."""
    try:
        code = getattr(event, "code", None)
        now = datetime.now(timezone.utc)
        from apscheduler.events import EVENT_JOB_SUBMITTED, EVENT_JOB_MISSED, EVENT_JOB_MAX_INSTANCES
        kind = {EVENT_JOB_SUBMITTED: "submitted", EVENT_JOB_MISSED: "missed",
                EVENT_JOB_MAX_INSTANCES: "max_instances"}.get(code, str(code))
        if kind == "submitted":
            _IN_FLIGHT[event.job_id] = now
        _EVENTS.append({"at": now.strftime("%H:%M:%S"), "job": event.job_id, "event": kind})
        del _EVENTS[:-30]
    except Exception:
        pass


def _stamp_job_event(event):
    """APScheduler listener: record the outcome of every job execution."""
    try:
        _IN_FLIGHT.pop(event.job_id, None)
        _LAST_JOB_RUN[event.job_id] = {
            "at": datetime.now(timezone.utc),
            "ok": getattr(event, "exception", None) is None,
            "error": (
                str(event.exception)[:200]
                if getattr(event, "exception", None) is not None
                else None
            ),
        }
    except Exception:  # pragma: no cover - a listener must never raise
        logger.exception("scheduler event listener failed")


def scheduler_status():
    """Readiness snapshot of the background scheduler.

    Returns a dict with ``enabled`` (was it asked to run), ``running`` (is the
    thread alive), ``healthy`` (enabled ⇒ running with a fresh heartbeat) and
    per-job last-run stamps. Never raises.
    """
    enabled = (os.environ.get("ENABLE_SCHEDULER", "").lower() == "true")
    status = {
        "enabled": enabled,
        "running": False,
        "healthy": (not enabled),      # not asked to run ⇒ nothing to be unhealthy about
        "jobs": 0,
        "started_at": None,
        "last_heartbeat_at": None,
        "heartbeat_age_seconds": None,
        "last_job_runs": {},
        "failing_jobs": [],
    }
    try:
        if _SCHEDULER_STARTED_AT is not None:
            status["started_at"] = _SCHEDULER_STARTED_AT.isoformat()
        status["running"] = bool(_SCHEDULER is not None and _SCHEDULER.running)
        if _SCHEDULER is not None:
            try:
                status["jobs"] = len(_SCHEDULER.get_jobs())
            except Exception:
                pass

        now = datetime.now(timezone.utc)
        beat = _LAST_JOB_RUN.get(_HEARTBEAT_JOB_ID, {}).get("at")
        # Before the first beat fires, boot time is the reference point --
        # otherwise every fresh deploy would report the scheduler as dead.
        reference = beat or _SCHEDULER_STARTED_AT
        if beat is not None:
            status["last_heartbeat_at"] = beat.isoformat()
        if reference is not None:
            age = (now - reference).total_seconds()
            status["heartbeat_age_seconds"] = round(age, 1)

        status["last_job_runs"] = {
            job_id: {
                "at": info["at"].isoformat(),
                "ok": info["ok"],
                "error": info["error"],
            }
            for job_id, info in _LAST_JOB_RUN.items()
        }
        status["failing_jobs"] = sorted(
            job_id for job_id, info in _LAST_JOB_RUN.items() if not info["ok"]
        )
        # Diagnostics: what is the scheduler actually doing right now.
        try:
            diag = {"thread_alive": bool(_SCHEDULER is not None and getattr(_SCHEDULER, "_thread", None) is not None
                                         and _SCHEDULER._thread.is_alive())}
            diag["in_flight"] = {j: round((now - t).total_seconds()) for j, t in _IN_FLIGHT.items()}
            diag["events"] = list(_EVENTS[-20:])
            diag["log"] = list(_LOG_RING[-30:])
            if _SCHEDULER is not None:
                jobs = sorted(_SCHEDULER.get_jobs(), key=lambda j: (j.next_run_time is None, j.next_run_time))
                diag["next_runs"] = [{"job": j.id, "at": j.next_run_time.isoformat() if j.next_run_time else None}
                                     for j in jobs[:8]]
                try:
                    ex = _SCHEDULER._lookup_executor("default")
                    pool = getattr(ex, "_pool", None)
                    diag["pool"] = {"threads": len(getattr(pool, "_threads", []) or []),
                                    "queued": pool._work_queue.qsize() if pool is not None else None,
                                    "instances": {k: v for k, v in getattr(ex, "_instances", {}).items() if v}}
                except Exception as exc:
                    diag["pool"] = {"error": str(exc)[:120]}
            status["diag"] = diag
        except Exception as exc:
            status["diag"] = {"error": str(exc)[:200]}

        if enabled:
            fresh = (
                reference is not None
                and (now - reference) < _HEARTBEAT_STALE_AFTER
            )
            status["healthy"] = bool(status["running"] and fresh)
    except Exception:  # pragma: no cover
        logger.exception("scheduler_status failed")
    return status


def _retry_failed_pushes(app):
    """Re-send push notifications that failed transiently (F27).

    A 5xx from APNs or a dropped connection used to mean the notification was
    simply gone. Deliveries are now recorded, and this sweep retries the
    retryable ones with exponential backoff up to 3 attempts.
    """
    try:
        from push_notifications import retry_pending_pushes
        with app.app_context():
            retry_pending_pushes()
    except Exception:
        logger.exception("push retry sweep failed")


def _run_noshow_watchdog():
    """No-show watchdog pass: T-30 unassigned + T+15 late-start alerts.

    run_t30_check/run_late_check push their own app context, so no app arg.
    Idempotent per job via noshow_t30_alerted / noshow_late_alerted flags.
    """
    try:
        from noshow_watchdog import run_t30_check, run_late_check

        t30 = run_t30_check()
        late = run_late_check()
        if t30 or late:
            logger.info("No-show watchdog fired: t30=%d late=%d", t30, late)
    except Exception:
        logger.exception("No-show watchdog pass failed")


def _sweep_expired_broadcasts(app):
    """Second-wave: re-broadcast broadcast offers that all expired unclaimed."""
    try:
        from dispatcher import sweep_expired_broadcasts
        sweep_expired_broadcasts(app)
    except Exception:
        logger.exception("Broadcast re-offer sweep failed")


def _angle_backfill(app):
    """Fill blank prospect angles (Claude when keyed, template otherwise). See enrich.py."""
    try:
        from enrich import run_angle_backfill
        run_angle_backfill(app)
    except Exception:
        logger.exception("angle backfill job failed")


def _sameday_online_sweep(app):
    """Hourly: app haulers with a stale heartbeat go offline (sameday.sweep_stale_online)."""
    try:
        from sameday import run_online_sweep
        run_online_sweep(app)
    except Exception:
        logger.exception("online sweep job failed")


def _sameday_standby_ask(app):
    """Morning 'available for same-day jobs today?' text to approved haulers. See sameday.py."""
    try:
        from sameday import run_standby_ask
        run_standby_ask(app)
    except Exception:
        logger.exception("standby ask job failed")


def _leads_sweep(app):
    """Speed-to-lead auto-text + quote follow-ups (leads.py)."""
    with app.app_context():
        try:
            from leads import speed_to_lead_sweep, followup_sweep
            speed_to_lead_sweep()
            followup_sweep()
        except Exception:
            logger.exception("leads sweep failed")


def _preslot_check(app):
    """T-30: an assigned hauler with no movement is re-dispatched (unconfirmed)
    or a person is paged (confirmed). hauler_confirm.py."""
    with app.app_context():
        try:
            from hauler_confirm import preslot_check
            preslot_check()
        except Exception:
            logger.exception("preslot check failed")


def _assign_weekly_classes(app):
    """Friday 5pm: build each VA's weekly improvement class (coaching_class.py)."""
    with app.app_context():
        try:
            from coaching_class import assign_week
            built = assign_week()
            if built:
                logger.info("weekly classes assigned: %s", ", ".join(r.va_name for r in built))
        except Exception:
            logger.exception("weekly class assignment failed")


def _reconcile_refunded_jobs(app):
    """Open jobs whose payment was refunded in full get cancelled (cancellation.py)."""
    with app.app_context():
        try:
            from cancellation import reconcile_refunded_jobs
            closed = reconcile_refunded_jobs()
            if closed:
                logger.warning("refund reconcile cancelled %d open job(s): %s", len(closed), ", ".join(closed))
        except Exception:
            logger.exception("refund reconcile failed")


def _owed_alert(app):
    """5pm Florida: haulers still unpaid for jobs completed today (sameday_pay.py)."""
    try:
        from sameday_pay import owed_alert
        owed_alert(app)
    except Exception:
        logger.exception("owed alert failed")


def _check_desk_health(app):
    """Desk line dependencies (Twilio balance/webhooks/browser-calling env). See desk_health.py."""
    try:
        from desk_health import run_desk_health
        run_desk_health(app)
    except Exception:
        logger.exception("desk health job failed")


def _run_retention(app):
    """Nightly Call Desk compliance retention (transcripts, call bodies, audit). See compliance.py."""
    try:
        from compliance import run_retention
        with app.app_context():
            run_retention()
    except Exception:
        logger.exception("compliance retention job failed")


def _check_twilio_health(app):
    """Probe Twilio; email-alert if the account is down (e.g. billing suspension
    → all SMS silently failing). Email-only alert, so it survives a Twilio
    outage. See twilio_health.py.
    """
    with app.app_context():
        try:
            from twilio_health import run_twilio_health_check
            run_twilio_health_check(alert=True)
        except Exception:
            logger.exception("Twilio health check job failed")


def _sweep_pending_payouts(app):
    """Retry payouts that were deferred because the contractor hadn't connected
    a Stripe account yet (payout_status='pending_connect'). Idempotent.

    Lets a hauler who completes a job *then* finishes Stripe onboarding still
    get paid automatically, instead of the payout being lost.
    """
    with app.app_context():
        # Tip legs retry on their own: a failed tip transfer must not wait on,
        # or be hidden by, the base payout's status.
        try:
            from models import db as _db, Contractor as _C
            from models_payments import Payout as _P
            from routes.payments import _transfer_leg as _leg
            for tip in _P.query.filter(_P.recipient_type == "tip", _P.status == "failed").limit(50).all():
                c = _db.session.get(_C, tip.contractor_id) if tip.contractor_id else None
                if c and c.stripe_connect_id:
                    st, _ = _leg(tip, c.stripe_connect_id, tip.job_id)
                    _db.session.commit()
                    logger.info("tip retry job %s -> %s", tip.job_id, st)
        except Exception:
            logger.exception("tip payout retry failed")
        from models import db, Payment
        from routes.payments import attempt_payout

        # Include "failed" too: one transient Stripe error at completion time
        # previously meant the hauler was silently never paid. attempt_payout
        # is idempotent (Stripe idempotency key per job), so retrying is safe.
        pending = Payment.query.filter(
            Payment.payout_status.in_(("pending_connect", "failed"))
        ).all()
        retried = paid = 0
        for p in pending:
            retried += 1
            try:
                result = attempt_payout(p.job_id)
                if result.get("status") == "paid":
                    paid += 1
            except Exception:
                logger.exception("Pending payout retry failed for job %s", p.job_id)
        if retried:
            logger.info("Pending-payout sweep: %d retried, %d now paid", retried, paid)


def _generate_recurring_jobs(app):
    """Create + dispatch Jobs from active recurring bookings that are due.

    Delegates to ``routes.recurring.generate_due_recurring_jobs`` — the single
    implementation shared with POST /api/recurring/generate-next. It prices
    each occurrence with the live estimator, charges a saved card off-session
    (or sends a pay link and parks the job in ``awaiting_payment``), claims a
    ``recurring_occurrences`` uniqueness key so a double tick can't double-book,
    and dispatches whatever is paid for. This used to be a second copy of the
    logic here that created $0 "pending" payments (audit F24).
    """
    with app.app_context():
        try:
            from routes.recurring import generate_due_recurring_jobs
            result = generate_due_recurring_jobs()
        except Exception:
            logger.exception("Scheduler: recurring job generation failed")
            return
        if result["created"]:
            logger.info(
                "Scheduler: created %d jobs from recurring bookings "
                "(%d dispatched, %d awaiting payment)",
                len(result["created"]), len(result["dispatched"]),
                len(result["awaiting_payment"]),
            )


def _send_pickup_reminders(app):
    """Send 24-hour pickup reminder emails and SMS."""
    with app.app_context():
        from models import db, Job, User

        now = datetime.now(timezone.utc)
        window_start = now + timedelta(hours=23)
        window_end = now + timedelta(hours=25)

        jobs = Job.query.filter(
            Job.status.in_(["pending", "confirmed", "assigned", "accepted"]),
            Job.scheduled_at >= window_start,
            Job.scheduled_at <= window_end,
        ).all()

        for job in jobs:
            try:
                user = db.session.get(User, job.customer_id)
                if not user:
                    continue

                date_str = fmt_local(job.scheduled_at, "%B %d, %Y")
                time_str = fmt_local(job.scheduled_at, "%I:%M %p")

                # Email reminder
                if user.email:
                    from notifications import send_email
                    from email_templates import pickup_reminder_html
                    html = pickup_reminder_html(user.name, job.id, job.address, date_str, time_str)
                    send_email(user.email, "Reminder: Your Umuve Pickup is Tomorrow!", html)

                # SMS reminder
                if user.phone:
                    from sms_service import sms_pickup_reminder
                    sms_pickup_reminder(user.phone, job.id, date_str, time_str, job.address)

            except Exception:
                logger.exception("Failed to send reminder for job %s", job.id)

        if jobs:
            logger.info("Scheduler: sent reminders for %d upcoming jobs", len(jobs))


def _send_abandoned_booking_drip(app):
    """Send abandoned booking drip emails based on pending job age."""
    with app.app_context():
        from models import db, Job, User
        from notifications import (
            send_abandoned_booking_reminder,
            send_abandoned_booking_incentive,
            send_abandoned_booking_final,
        )

        now = datetime.now(timezone.utc)
        base_url = os.environ.get("FRONTEND_URL", "https://goumuve.com")

        # Phone bookings are confirmed orders awaiting fulfillment, not
        # abandoned checkouts — "You left something behind" reads as a
        # cancellation to a customer who already got a confirmation email.
        from sqlalchemy import or_
        not_phone_booking = or_(
            Job.notes.is_(None), ~Job.notes.ilike("%AI receptionist%")
        )

        # Stage 1: 2+ hours old, drip_stage=0 → send reminder
        stage1_cutoff = now - timedelta(hours=2)
        stage1_jobs = Job.query.filter(
            Job.status == "pending",
            Job.drip_stage == 0,
            Job.created_at <= stage1_cutoff,
            not_phone_booking,
        ).all()

        for job in stage1_jobs:
            try:
                user = db.session.get(User, job.customer_id)
                if not user or not user.email:
                    continue
                booking_url = "{}/book?resume={}".format(base_url.rstrip("/"), job.id)
                send_abandoned_booking_reminder(user.email, user.name, booking_url)
                job.drip_stage = 1
            except Exception:
                logger.exception("Failed to send drip stage 1 for job %s", job.id)

        # Stage 2: 24+ hours old, drip_stage=1 → send incentive
        stage2_cutoff = now - timedelta(hours=24)
        stage2_jobs = Job.query.filter(
            Job.status == "pending",
            Job.drip_stage == 1,
            Job.created_at <= stage2_cutoff,
            not_phone_booking,
        ).all()

        for job in stage2_jobs:
            try:
                user = db.session.get(User, job.customer_id)
                if not user or not user.email:
                    continue
                booking_url = "{}/book?resume={}".format(base_url.rstrip("/"), job.id)
                send_abandoned_booking_incentive(
                    user.email, user.name, booking_url, "COMEBACK10"
                )
                job.drip_stage = 2
            except Exception:
                logger.exception("Failed to send drip stage 2 for job %s", job.id)

        # Stage 3: 72+ hours old, drip_stage=2 → send final
        stage3_cutoff = now - timedelta(hours=72)
        stage3_jobs = Job.query.filter(
            Job.status == "pending",
            Job.drip_stage == 2,
            Job.created_at <= stage3_cutoff,
            not_phone_booking,
        ).all()

        for job in stage3_jobs:
            try:
                user = db.session.get(User, job.customer_id)
                if not user or not user.email:
                    continue
                booking_url = "{}/book?resume={}".format(base_url.rstrip("/"), job.id)
                send_abandoned_booking_final(user.email, user.name, booking_url)
                job.drip_stage = 3
            except Exception:
                logger.exception("Failed to send drip stage 3 for job %s", job.id)

        total = len(stage1_jobs) + len(stage2_jobs) + len(stage3_jobs)
        if total > 0:
            db.session.commit()
            logger.info(
                "Scheduler: sent abandoned booking drip emails — "
                "stage1=%d, stage2=%d, stage3=%d",
                len(stage1_jobs), len(stage2_jobs), len(stage3_jobs),
            )


def _send_winback_emails(app):
    """Send winback emails to customers whose last completed job was 7+ days ago."""
    with app.app_context():
        from models import db, User, Job
        from notifications import send_email
        from email_templates import winback_html

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=7)
        max_age = now - timedelta(days=90)  # Don't winback customers older than 90 days

        # Find customers with completed jobs 7-90 days ago who haven't been winbacked
        from sqlalchemy import func
        customers_with_completed = (
            db.session.query(
                User.id, User.email, User.name,
                func.max(Job.updated_at).label("last_job")
            )
            .join(Job, Job.customer_id == User.id)
            .filter(
                Job.status == "completed",
                User.winback_called == False,
                User.email.isnot(None),
            )
            .group_by(User.id)
            .having(func.max(Job.updated_at) <= cutoff)
            .having(func.max(Job.updated_at) >= max_age)
            .limit(20)  # Batch size per run
            .all()
        )

        count = 0
        for uid, email, name, last_job in customers_with_completed:
            try:
                html = winback_html(customer_name=name, promo_code="COMEBACK10")
                send_email(email, "Still have stuff to get rid of?", html)

                user = db.session.get(User, uid)
                if user:
                    user.winback_called = True
                    user.last_winback_at = now
                count += 1
            except Exception:
                logger.exception("Failed to send winback to %s", email)

        if count > 0:
            db.session.commit()
            logger.info("Scheduler: sent %d winback emails", count)


# ---------------------------------------------------------------------------
# Tasks migrated off the Celery worker (umuve-portal-beat) 2026-06-19.
# These previously ran under `celery -A celery_app.celery worker -B`, which
# required a dedicated Render worker dyno + Redis broker. They run different
# data/channels than the jobs above (Portal-v1 B2B recurring + invoicing, and
# Vapi voice calls vs. the email/SMS reminders), so this is functional parity,
# not duplication. Folding them into APScheduler lets us delete the worker and
# Redis. celery_app.py is kept for manual CLI backfills, just not deployed.
# ---------------------------------------------------------------------------
def _portal_recurring_tick(app):
    """Portal-v1: generate Jobs for due recurring schedules (was
    celery portal.recurring_tick, every 5 min)."""
    with app.app_context():
        try:
            from portal_recurring import generate_jobs_for_due_schedules
            created = generate_jobs_for_due_schedules(datetime.utcnow())
            if created:
                logger.info("portal.recurring_tick created %d jobs", len(created))
        except Exception:
            logger.exception("portal.recurring_tick failed")


def _portal_invoice_monthly(app):
    """Portal-v1: invoice the previous month (was celery
    portal.invoice_monthly, 02:00 UTC on the 1st)."""
    with app.app_context():
        try:
            from portal_invoicing import generate_monthly_invoices
            today = datetime.utcnow().date()
            last_of_prev = today.replace(day=1) - timedelta(days=1)
            created = generate_monthly_invoices(last_of_prev.month, last_of_prev.year)
            logger.info(
                "portal.invoice_monthly %02d/%d created %d invoices",
                last_of_prev.month, last_of_prev.year, len(created),
            )
        except Exception:
            logger.exception("portal.invoice_monthly failed")


def _customer_drip_emails(app):
    """AbandonedBooking email drip (was celery customer.drip_emails). Hits the
    AbandonedBooking table — distinct from _send_abandoned_booking_drip (Job)."""
    try:
        from drip_scheduler import run_drip  # pushes its own app context
        run_drip()
    except Exception:
        logger.exception("customer.drip_emails failed")


def _customer_review_calls(app):
    """Vapi post-job review + win-back calls (was celery customer.review_calls).
    Voice channel — distinct from _send_winback_emails (email)."""
    try:
        from review_scheduler import run_review_calls, run_winback_calls  # own context
        reviews = run_review_calls()
        winbacks = run_winback_calls()
        if reviews or winbacks:
            logger.info("customer.review_calls reviews=%s winbacks=%s", reviews, winbacks)
    except Exception:
        logger.exception("customer.review_calls failed")


def _customer_reminders(app):
    """Vapi 24h pre-pickup reminder calls (was celery customer.reminders).
    Voice channel — distinct from _send_pickup_reminders (email + SMS)."""
    try:
        from reminder_scheduler import run_reminders  # pushes its own app context
        run_reminders()
    except Exception:
        logger.exception("customer.reminders failed")


def _run_operator_outreach(app):
    """Daily operator/hauler recruiting outreach: source -> qualify -> email
    drip. No-ops to a safe dry run until the compliance env is set."""
    try:
        from operator_outreach import run_outreach_cycle  # opens its own app ctx
        run_outreach_cycle(app)
    except Exception:
        logger.exception("operator outreach job crashed")


def _run_demand_records(app):
    """Daily public-records demand sweep: code-enforcement citations, probate
    and eviction filings -> DemandRecord rows + digest. Observe-only."""
    try:
        from demand_records import run_demand_records_cycle  # opens its own app ctx
        run_demand_records_cycle(app)
    except Exception:
        logger.exception("demand records sweep crashed")


def _run_b2b_outreach(app):
    """Daily B2B customer-acquisition outreach: source businesses -> qualify ->
    email drip to portal signup. Safe dry run until the B2B env is set."""
    try:
        from b2b_outreach import run_b2b_outreach_cycle  # opens its own app ctx
        run_b2b_outreach_cycle(app)
    except Exception:
        logger.exception("b2b outreach job crashed")


def _run_doc_expiry_sweep(app):
    """Daily: suspend any approved hauler whose insurance/license/registration
    has lapsed, and remind those expiring soon. Keeps an uninsured truck from
    ever being dispatched."""
    try:
        from operator_doc_verifier import run_expiry_sweep  # opens its own app ctx
        run_expiry_sweep(app)
    except Exception:
        logger.exception("doc expiry sweep job crashed")


def _run_recruiter_calls(app):
    """Maya Recruiter: place a capped batch of outbound recruiting calls to
    NEW driver leads. Fully kill-switched — no-ops unless RECRUITER_CALLS_ENABLED
    (+ Vapi env) is set. Runs a few times a day inside the calling window."""
    try:
        from recruiter_calls import run_recruiter_calls
        run_recruiter_calls(app)
    except Exception:
        logger.exception("recruiter calls job crashed")


def _run_ops_sentinel(app):
    """Every 10 min: catch jobs/money stalling in states nothing else watches
    (mid-job stalls, ASAP jobs with no dispatch, offline hauler mid-job,
    stuck/owed payouts). Alert-only; exactly-once per (kind, job)."""
    try:
        from ops_sentinel import run_sentinel
        run_sentinel(app)
    except Exception:
        logger.exception("ops sentinel job crashed")


def _run_morning_brief(app):
    """Daily ops digest email to ADMIN_EMAIL — the backstop that catches
    whatever every other alert missed."""
    try:
        with app.app_context():
            from morning_brief import send_brief
            send_brief()
    except Exception:
        logger.exception("morning brief job crashed")


def _run_mystery_shop(app):
    """Daily synthetic shopper: walks the public booking funnel (no payment,
    no Stripe) and URGENT-alerts if it's broken. Gate: MYSTERY_SHOP_ENABLED
    (default on — it is read-only against prod)."""
    if os.environ.get("MYSTERY_SHOP_ENABLED", "true").lower() != "true":
        return
    try:
        with app.app_context():
            from mystery_shop import main as mystery_main
            mystery_main()
    except Exception:
        logger.exception("mystery shop job crashed")


def _run_vapi_health(app):
    """Hourly: scan recent Vapi calls for hang-up/failure patterns."""
    try:
        with app.app_context():
            from vapi_health_monitor import check_call_health
            check_call_health()
    except Exception:
        logger.exception("vapi health monitor job crashed")


def _run_growth_sweep(app):
    """Every 30 min: durable post-job review SMS/email (replaces the
    threading.Timer sends that died on redeploy), referral share nudge,
    6-month re-engagement, B2B trial nudges. Exactly-once per send."""
    try:
        from growth_loops import run_growth_sweep
        run_growth_sweep(app)
    except Exception:
        logger.exception("growth sweep job crashed")


def _run_activation_drip(app):
    """Daily: nudge registered haulers who never went online (T+1/3/7 SMS,
    concierge fallback offer) + doc-completion nudges. Gate:
    ACTIVATION_DRIP_ENABLED (default on)."""
    try:
        from supply_drip import run_activation_drip
        run_activation_drip(app)
    except Exception:
        logger.exception("activation drip job crashed")


def init_scheduler(app):
    """Initialize and start the background scheduler.

    Only runs if ENABLE_SCHEDULER=true env var is set.
    """
    global _SCHEDULER, _SCHEDULER_STARTED_AT

    if os.environ.get("ENABLE_SCHEDULER", "").lower() != "true":
        logger.info("Scheduler disabled (set ENABLE_SCHEDULER=true to enable)")
        return None

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

        scheduler = BackgroundScheduler(daemon=True)

        # Liveness plumbing for GET /api/ready (F26). Additive: it records what
        # the existing jobs do, and adds one no-op heartbeat.
        scheduler.add_listener(_stamp_job_event, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        try:
            from apscheduler.events import EVENT_JOB_SUBMITTED, EVENT_JOB_MISSED, EVENT_JOB_MAX_INSTANCES
            scheduler.add_listener(_note_event, EVENT_JOB_SUBMITTED | EVENT_JOB_MISSED | EVENT_JOB_MAX_INSTANCES)
            ring = _RingHandler(_LOG_RING)
            ring.setFormatter(logging.Formatter("%(name)s: %(message)s"))
            for name in ("apscheduler", "apscheduler.executors.default", "apscheduler.scheduler", __name__):
                lg = logging.getLogger(name)
                lg.addHandler(ring)
                if lg.level == logging.NOTSET or lg.level > logging.INFO:
                    lg.setLevel(logging.INFO)
        except Exception:
            logger.debug("scheduler diagnostics not attached", exc_info=True)
        scheduler.add_job(
            _readiness_heartbeat,
            "interval",
            minutes=_HEARTBEAT_MINUTES,
            id=_HEARTBEAT_JOB_ID,
            name="Readiness heartbeat",
        )

        # Prospect angles — 60s after boot, then every 30 min (only blanks)
        from datetime import datetime as _dt, timedelta as _td
        scheduler.add_job(
            _angle_backfill,
            "interval",
            minutes=30,
            next_run_time=_dt.now() + _td(seconds=60),
            args=[app],
            id="angle_backfill",
            name="Fill blank prospect angles",
        )

        # Push delivery retries — every 2 min (backoff lives in the rows)
        scheduler.add_job(
            _retry_failed_pushes,
            "interval",
            minutes=2,
            args=[app],
            id="push_retry_sweep",
            name="Retry transiently failed push notifications",
        )

        # Online-flag aging — hourly
        scheduler.add_job(
            _sameday_online_sweep,
            "interval",
            hours=1,
            args=[app],
            id="sameday_online_sweep",
            name="Age out stale hauler online flags",
        )

        # Same-day standby roster — 08:45 Florida time (Sundays skipped inside)
        scheduler.add_job(
            _sameday_standby_ask,
            "cron",
            hour=8, minute=45, timezone="America/New_York",
            args=[app],
            id="sameday_standby_ask",
            name="Same-day standby roster text",
        )

        # Speed-to-lead auto-text + quote follow-ups — every minute
        scheduler.add_job(
            _leads_sweep,
            "interval",
            minutes=1,
            args=[app],
            id="leads_sweep",
            name="Speed-to-lead + quote follow-ups",
        )

        # Weekly improvement class — Friday 5pm ET (idempotent; Sunday 6pm retry)
        scheduler.add_job(
            _assign_weekly_classes,
            "cron",
            day_of_week="fri,sun", hour=17, minute=0, timezone="America/New_York",
            args=[app],
            id="weekly_classes",
            name="Assign weekly coaching classes",
        )

        # Assigned hauler, 30 min out, no movement — every 5 min
        scheduler.add_job(
            _preslot_check,
            "interval",
            minutes=5,
            args=[app],
            id="preslot_check",
            name="Pre-slot hauler movement check",
        )

        # Refunded-but-open jobs — 90s after boot, then hourly
        scheduler.add_job(
            _reconcile_refunded_jobs,
            "interval",
            hours=1,
            next_run_time=_dt.now() + _td(seconds=90),
            args=[app],
            id="reconcile_refunded_jobs",
            name="Cancel jobs refunded in full",
        )

        # Haulers owed for today — 17:00 Florida time
        scheduler.add_job(
            _owed_alert,
            "cron",
            hour=17, minute=0, timezone="America/New_York",
            args=[app],
            id="owed_alert",
            name="Haulers owed today alert",
        )

        # Call Desk line health — every 30 min, alerts on state change
        scheduler.add_job(
            _check_desk_health,
            "interval",
            minutes=30,
            args=[app],
            id="desk_health",
            name="Call Desk line health",
        )

        # Call Desk compliance retention — nightly 03:30 UTC (compliance.py)
        scheduler.add_job(
            _run_retention,
            "cron",
            hour=3,
            minute=30,
            args=[app],
            id="compliance_retention",
            name="Call Desk compliance retention sweep",
        )

        # Generate recurring jobs every hour
        scheduler.add_job(
            _generate_recurring_jobs,
            "interval",
            hours=1,
            args=[app],
            id="generate_recurring_jobs",
            name="Generate recurring booking jobs",
        )

        # Send pickup reminders every hour
        scheduler.add_job(
            _send_pickup_reminders,
            "interval",
            hours=1,
            args=[app],
            id="send_pickup_reminders",
            name="Send 24h pickup reminders",
        )

        # Send abandoned booking drip emails every 30 minutes
        scheduler.add_job(
            _send_abandoned_booking_drip,
            "interval",
            minutes=30,
            args=[app],
            id="send_abandoned_booking_drip",
            name="Send abandoned booking drip emails",
        )

        # Send winback emails every 6 hours
        scheduler.add_job(
            _send_winback_emails,
            "interval",
            hours=6,
            args=[app],
            id="send_winback_emails",
            name="Send customer winback emails",
        )

        # Retry deferred (pending_connect) hauler payouts every 6 hours
        scheduler.add_job(
            _sweep_pending_payouts,
            "interval",
            hours=6,
            args=[app],
            id="sweep_pending_payouts",
            name="Retry deferred contractor payouts",
        )

        # Twilio account health — catch billing suspensions before they
        # silently kill all SMS for days (every 6 hours).
        scheduler.add_job(
            _check_twilio_health,
            "interval",
            hours=6,
            args=[app],
            id="check_twilio_health",
            name="Twilio account health probe",
        )

        # No-show watchdog: T-30 unassigned + T+15 late-start alerts.
        # Checks push their own app context (also runnable standalone).
        scheduler.add_job(
            _run_noshow_watchdog,
            "interval",
            minutes=5,
            id="noshow_watchdog",
            name="No-show watchdog (T-30 unassigned, T+15 late-start)",
        )

        # Broadcast second-wave: re-offer jobs whose offers all expired unclaimed.
        scheduler.add_job(
            _sweep_expired_broadcasts,
            "interval",
            minutes=5,
            args=[app],
            id="sweep_expired_broadcasts",
            name="Re-broadcast expired job offers",
        )

        # --- Migrated from the Celery worker (umuve-portal-beat) 2026-06-19 ---

        # Portal-v1: generate jobs for due recurring schedules (every 5 min).
        scheduler.add_job(
            _portal_recurring_tick,
            "interval",
            minutes=5,
            args=[app],
            id="portal_recurring_tick",
            name="Portal recurring schedule -> jobs",
        )

        # Portal-v1: monthly invoicing — 02:00 UTC on the 1st.
        scheduler.add_job(
            _portal_invoice_monthly,
            "cron",
            day=1,
            hour=2,
            minute=0,
            args=[app],
            id="portal_invoice_monthly",
            name="Portal monthly invoicing",
        )

        # AbandonedBooking email drip (every 30 min).
        scheduler.add_job(
            _customer_drip_emails,
            "interval",
            minutes=30,
            args=[app],
            id="customer_drip_emails",
            name="AbandonedBooking email drip",
        )

        # Vapi review + win-back calls (every 30 min).
        scheduler.add_job(
            _customer_review_calls,
            "interval",
            minutes=30,
            args=[app],
            id="customer_review_calls",
            name="Vapi review + win-back calls",
        )

        # Vapi 24h pre-pickup reminder calls (every 30 min).
        scheduler.add_job(
            _customer_reminders,
            "interval",
            minutes=30,
            args=[app],
            id="customer_reminders",
            name="Vapi pre-pickup reminder calls",
        )

        # Daily operator/hauler recruiting outreach — 14:00 UTC (~9-10am ET).
        scheduler.add_job(
            _run_operator_outreach,
            "cron",
            hour=14,
            minute=0,
            args=[app],
            id="operator_outreach",
            name="Daily operator recruiting outreach",
        )

        # Daily operator document expiry sweep — 13:00 UTC (~8-9am ET), before
        # the recruiting outreach. Suspends lapsed-coverage haulers.
        scheduler.add_job(
            _run_doc_expiry_sweep,
            "cron",
            hour=13,
            minute=0,
            args=[app],
            id="doc_expiry_sweep",
            name="Daily operator document expiry sweep",
        )

        # Daily public-records demand sweep — 12:30 UTC (~7-8am ET), before the
        # outreach engines so fresh signals are in the morning digest. Sources
        # code-violation / probate / eviction records; contacts no one.
        scheduler.add_job(
            _run_demand_records,
            "cron",
            hour=12,
            minute=30,
            args=[app],
            id="demand_records",
            name="Daily public-records demand sweep",
        )

        # Daily B2B customer-acquisition outreach — 15:00 UTC (~11am ET), after
        # the hauler outreach so the two sends don't collide.
        scheduler.add_job(
            _run_b2b_outreach,
            "cron",
            hour=15,
            minute=0,
            args=[app],
            id="b2b_outreach",
            name="Daily B2B customer outreach",
        )

        # Maya Recruiter outbound calls — three passes inside the ET calling
        # window (15:00 / 18:00 / 21:00 UTC ~= 10am / 1pm / 4pm ET). Each pass
        # is capped and the whole job is dark unless RECRUITER_CALLS_ENABLED.
        scheduler.add_job(
            _run_recruiter_calls,
            "cron",
            hour="15,18,21",
            minute=30,
            args=[app],
            id="recruiter_calls",
            name="Maya recruiter outbound calls (kill-switched)",
        )

        # Ops sentinel — the net under every other net. Every 10 min.
        scheduler.add_job(
            _run_ops_sentinel,
            "interval",
            minutes=10,
            args=[app],
            id="ops_sentinel",
            name="Ops sentinel (stall/payout/offline watchdog)",
        )

        # Daily morning brief — 11:00 UTC (~7am ET), lands before the workday.
        scheduler.add_job(
            _run_morning_brief,
            "cron",
            hour=11,
            minute=0,
            args=[app],
            id="morning_brief",
            name="Daily admin morning brief",
        )

        # Daily synthetic mystery shop — 12:10 UTC, after the brief.
        scheduler.add_job(
            _run_mystery_shop,
            "cron",
            hour=12,
            minute=10,
            args=[app],
            id="mystery_shop",
            name="Synthetic booking-funnel shopper",
        )

        # Vapi call-health scan — hourly at :20.
        scheduler.add_job(
            _run_vapi_health,
            "cron",
            minute=20,
            args=[app],
            id="vapi_health",
            name="Vapi call-health monitor",
        )

        # Growth loops — every 30 min (durable review sends, referral nudge,
        # 6-month re-engagement, B2B trial nudges).
        scheduler.add_job(
            _run_growth_sweep,
            "interval",
            minutes=30,
            args=[app],
            id="growth_sweep",
            name="Growth loops sweep",
        )

        # Supply-activation drip — daily 16:00 UTC (~noon ET, good SMS hour).
        scheduler.add_job(
            _run_activation_drip,
            "cron",
            hour=16,
            minute=0,
            args=[app],
            id="activation_drip",
            name="Hauler activation drip",
        )

        # VA Call Desk digest to admin — daily 11:00 UTC (7am ET).
        try:
            from va_calls import send_caller_digest
            scheduler.add_job(
                send_caller_digest,
                "cron",
                hour=11,
                minute=0,
                args=[app],
                id="caller_digest",
                name="Call Desk morning digest",
            )
        except Exception:
            logger.exception("caller digest job not registered")

        # Call Desk growth: sourced leads → queue daily 15:30 UTC; Maya pre-qual
        # hourly (acts only 10:00-16:00 ET Mon-Sat, flag + env kill-switched).
        try:
            from growth import run_auto_ingest
            from prequal import run_prequal_job
            scheduler.add_job(
                run_auto_ingest,
                "cron",
                hour=15,
                minute=30,
                args=[app],
                id="growth_auto_ingest",
                name="Call Desk auto-ingest (sourced leads → queue)",
            )
            scheduler.add_job(
                run_prequal_job,
                "cron",
                minute=5,
                args=[app],
                id="growth_maya_prequal",
                name="Call Desk Maya pre-qualification",
            )
        except Exception:
            logger.exception("growth jobs not registered")

        scheduler.start()
        _SCHEDULER = scheduler
        _SCHEDULER_STARTED_AT = datetime.now(timezone.utc)
        logger.info("Background scheduler started with %d jobs", len(scheduler.get_jobs()))
        return scheduler
    except ImportError:
        logger.warning("APScheduler not installed — scheduler disabled")
        return None
    except Exception:
        logger.exception("Failed to start scheduler")
        return None
