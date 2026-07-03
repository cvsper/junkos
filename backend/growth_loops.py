"""Growth loops sweep — durable, exactly-once post-job and retention sends.

Replaces the threading.Timer review sends (lost on every deploy/restart) with
a DB-polled sweep, and adds the loops the 2026-07-03 growth audit found
missing: post-job referral nudge, 6-month re-engagement, B2B trial nudges.

Every send is exactly-once via AutomationEvent (kind, subject) — a redeploy
mid-window costs nothing and double-sends nothing. Runs every 30 minutes via
APScheduler (see scheduler.py).
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

REVIEW_SMS_MIN_H, REVIEW_SMS_MAX_H = 2, 12
REVIEW_EMAIL_MIN_H, REVIEW_EMAIL_MAX_H = 24, 48
REFERRAL_NUDGE_MIN_H, REFERRAL_NUDGE_MAX_H = 48, 96
REENGAGE_MIN_D, REENGAGE_MAX_D = 150, 210
TRIAL_NUDGE_EARLY_D = 3
TRIAL_NUDGE_LATE_D = 10


def _once(kind, subject_id, subject_type="job"):
    from models import db
    from models import AutomationEvent
    try:
        db.session.add(AutomationEvent(kind=kind, subject_type=subject_type,
                                       subject_id=str(subject_id)))
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        return False


def _city_from(address):
    if not address:
        return None
    parts = [p.strip() for p in address.split(",")]
    return parts[-2] if len(parts) >= 2 else parts[0]


def run_growth_sweep(app):
    with app.app_context():
        from models import db
        from models import Job, Org, User, utcnow

        now = utcnow()

        # --- Durable review SMS (2-12h after completion) --------------------
        rows = Job.query.filter(
            Job.status == "completed",
            Job.completed_at <= now - timedelta(hours=REVIEW_SMS_MIN_H),
            Job.completed_at >= now - timedelta(hours=REVIEW_SMS_MAX_H),
        ).all()
        for job in rows:
            customer = db.session.get(User, job.customer_id)
            if not customer or not customer.phone:
                continue
            if _once("review_sms", job.id):
                try:
                    from sms_service import send_review_request_sms
                    send_review_request_sms(customer.phone, customer.name,
                                            _city_from(job.address))
                except Exception:
                    logger.exception("review SMS failed for job %s", job.id)

        # --- Durable review follow-up email (24-48h) -------------------------
        rows = Job.query.filter(
            Job.status == "completed",
            Job.completed_at <= now - timedelta(hours=REVIEW_EMAIL_MIN_H),
            Job.completed_at >= now - timedelta(hours=REVIEW_EMAIL_MAX_H),
        ).all()
        for job in rows:
            customer = db.session.get(User, job.customer_id)
            if not customer or not customer.email:
                continue
            if _once("review_email", job.id):
                try:
                    from email_service import email_follow_up
                    email_follow_up(customer.email, customer.name)
                except Exception:
                    logger.exception("review email failed for job %s", job.id)

        # --- Post-job referral nudge (48-96h): share & earn $10 ---------------
        rows = Job.query.filter(
            Job.status == "completed",
            Job.completed_at <= now - timedelta(hours=REFERRAL_NUDGE_MIN_H),
            Job.completed_at >= now - timedelta(hours=REFERRAL_NUDGE_MAX_H),
        ).all()
        for job in rows:
            customer = db.session.get(User, job.customer_id)
            code = getattr(customer, "referral_code", None) if customer else None
            if not customer or not customer.phone or not code:
                continue
            if _once("referral_nudge", job.id):
                try:
                    from sms_service import send_sms
                    send_sms(customer.phone,
                             "Enjoying the space? Give a friend $10 off their "
                             "Umuve pickup with your code {} — you earn $10 "
                             "credit when they book. goumuve.com".format(code))
                    from notifications import send_push_notification
                    send_push_notification(
                        customer.id, "Give $10, Get $10",
                        "Share code {} — friends save $10, you earn $10.".format(code),
                        {"category": "referral"})
                except Exception:
                    logger.exception("referral nudge failed for job %s", job.id)

        # --- 6-month re-engagement (junk accumulates) -------------------------
        # Customers whose LAST completed job fell 150-210 days ago.
        window_lo = now - timedelta(days=REENGAGE_MAX_D)
        window_hi = now - timedelta(days=REENGAGE_MIN_D)
        from sqlalchemy import func
        last_jobs = (db.session.query(Job.customer_id,
                                      func.max(Job.completed_at).label("last"))
                     .filter(Job.status == "completed")
                     .group_by(Job.customer_id)
                     .having(func.max(Job.completed_at) >= window_lo)
                     .having(func.max(Job.completed_at) <= window_hi)
                     .all())
        for customer_id, _last in last_jobs:
            if not _once("reengage_6mo", customer_id, subject_type="user"):
                continue
            customer = db.session.get(User, customer_id)
            if not customer:
                continue
            try:
                if customer.email:
                    from email_service import _wrap_template, send_email_async
                    first = (customer.name or "there").split()[0]
                    content = (
                        "<h2>Six months of stuff piles up fast</h2>"
                        "<p>Hi {},</p>"
                        "<p>It's been a while since your last Umuve pickup — and "
                        "garages have a way of refilling themselves. Book in two "
                        "minutes and we'll haul it away again.</p>"
                        "<p style='margin-top:30px'><a href='https://goumuve.com/book' "
                        "class='button'>Book a Pickup</a></p>"
                        "<p>Use code <b>COMEBACK10</b> for 10% off.</p>"
                    ).format(first)
                    send_email_async(customer.email, "Time for another clear-out?",
                                     _wrap_template(content))
                from notifications import send_push_notification
                send_push_notification(
                    customer.id, "Garage filling up again?",
                    "It's been ~6 months — book a pickup, 10% off with COMEBACK10.",
                    {"category": "winback"})
            except Exception:
                logger.exception("6mo re-engagement failed for user %s", customer_id)

        # --- B2B trial nudges --------------------------------------------------
        try:
            trials = Org.query.filter(Org.status == "trial").all()
        except Exception:
            trials = []
        for org in trials:
            created = _aware(getattr(org, "created_at", None))
            if not created:
                continue
            age_d = (now - created).days
            has_usage = Job.query.filter(Job.org_id == org.id).first() is not None
            portal = "https://portal.goumuve.com"
            try:
                if age_d >= TRIAL_NUDGE_LATE_D and _once("trial_nudge_10d", org.id, "org"):
                    from email_service import _wrap_template, send_email_async
                    send_email_async(
                        org.billing_email, "Your Umuve trial — pick a plan",
                        _wrap_template(
                            "<h2>Keep your pickups running</h2>"
                            "<p>Your {} trial is {} days in. Choose a plan to keep "
                            "scheduled pickups and reporting active.</p>"
                            "<p style='margin-top:30px'><a href='{}' class='button'>"
                            "Choose a plan</a></p>".format(org.name, age_d, portal)))
                elif (age_d >= TRIAL_NUDGE_EARLY_D and not has_usage
                        and _once("trial_nudge_3d", org.id, "org")):
                    from email_service import _wrap_template, send_email_async
                    send_email_async(
                        org.billing_email, "Get your first Umuve pickup scheduled",
                        _wrap_template(
                            "<h2>Your account is ready — nothing scheduled yet</h2>"
                            "<p>Book your first commercial pickup in under two "
                            "minutes, or set a recurring schedule and forget it.</p>"
                            "<p style='margin-top:30px'><a href='{}' class='button'>"
                            "Schedule a pickup</a></p>".format(portal)))
            except Exception:
                logger.exception("trial nudge failed for org %s", org.id)

        logger.info("growth sweep done")
