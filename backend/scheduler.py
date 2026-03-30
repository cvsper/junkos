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

logger = logging.getLogger(__name__)


def _generate_recurring_jobs(app):
    """Create Job records from active recurring bookings that are due."""
    with app.app_context():
        from models import db, Job, Payment, RecurringBooking, generate_uuid
        from routes.recurring import _advance_next_scheduled

        now = datetime.now(timezone.utc)
        due = RecurringBooking.query.filter(
            RecurringBooking.is_active == True,
            RecurringBooking.next_scheduled_at <= now,
        ).all()

        count = 0
        for recurring in due:
            try:
                job = Job(
                    id=generate_uuid(),
                    customer_id=recurring.customer_id,
                    status="pending",
                    address=recurring.address,
                    lat=recurring.lat,
                    lng=recurring.lng,
                    items=recurring.items,
                    scheduled_at=recurring.next_scheduled_at,
                    notes="[Recurring] {}".format(recurring.notes or ""),
                )
                db.session.add(job)

                payment = Payment(
                    id=generate_uuid(),
                    job_id=job.id,
                    amount=0.0,
                    payment_status="pending",
                )
                db.session.add(payment)

                recurring.total_bookings_created += 1
                _advance_next_scheduled(recurring)
                count += 1
            except Exception:
                logger.exception(
                    "Failed to generate job for recurring booking %s", recurring.id
                )

        if count > 0:
            db.session.commit()
            logger.info("Scheduler: created %d jobs from recurring bookings", count)


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

                date_str = job.scheduled_at.strftime("%B %d, %Y") if job.scheduled_at else "TBD"
                time_str = job.scheduled_at.strftime("%I:%M %p") if job.scheduled_at else "TBD"

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

        # Stage 1: 2+ hours old, drip_stage=0 → send reminder
        stage1_cutoff = now - timedelta(hours=2)
        stage1_jobs = Job.query.filter(
            Job.status == "pending",
            Job.drip_stage == 0,
            Job.created_at <= stage1_cutoff,
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


def init_scheduler(app):
    """Initialize and start the background scheduler.

    Only runs if ENABLE_SCHEDULER=true env var is set.
    """
    if os.environ.get("ENABLE_SCHEDULER", "").lower() != "true":
        logger.info("Scheduler disabled (set ENABLE_SCHEDULER=true to enable)")
        return None

    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler(daemon=True)

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

        scheduler.start()
        logger.info("Background scheduler started with 3 jobs")
        return scheduler
    except ImportError:
        logger.warning("APScheduler not installed — scheduler disabled")
        return None
    except Exception:
        logger.exception("Failed to start scheduler")
        return None
