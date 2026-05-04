"""
Celery Beat + worker for Portal v1 scheduled jobs (spec 04 §9).

Two tasks run on a schedule:

  * `portal.recurring_tick`   — every 5 minutes, generates Jobs for any
                                 recurring schedule whose next_run_at has
                                 passed (wraps `portal_recurring`).
  * `portal.invoice_monthly`  — 02:00 UTC on the 1st of every month,
                                 invoices the previous month's completed
                                 jobs (wraps `portal_invoicing`).

Broker + result backend: `REDIS_URL` (same Redis used by ops_event_bus).
If REDIS_URL is unset the module still imports cleanly so the web service
and unit tests keep working — only `celery worker` / `celery beat`
deployments actually need Redis.

Entry points for Render:
  * Worker + Beat (single process, fine at MVP volume):
      celery -A celery_app.celery worker -B --loglevel=info --concurrency=1
  * Worker only:   celery -A celery_app.celery worker   --loglevel=info
  * Beat only:     celery -A celery_app.celery beat     --loglevel=info

The Flask app is imported from `server` so the tasks run inside an
application context (db.session + config are available).
"""

import datetime as _dt
import logging
import os

from celery import Celery
from celery.schedules import crontab

logger = logging.getLogger(__name__)

_BROKER = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery = Celery("umuve_portal", broker=_BROKER, backend=_BROKER)
celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)


# ---------------------------------------------------------------------------
# Flask app context wrapper
# ---------------------------------------------------------------------------
def _flask_app():
    """Lazily import the Flask app so `import celery_app` stays cheap."""
    from server import app  # noqa: WPS433 — lazy import is intentional
    return app


class FlaskContextTask(celery.Task):
    """Every task runs inside `app.app_context()` so db.session works."""

    abstract = True

    def __call__(self, *args, **kwargs):
        with _flask_app().app_context():
            return super().__call__(*args, **kwargs)


celery.Task = FlaskContextTask


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------
@celery.task(name="portal.recurring_tick")
def recurring_tick():
    """Create Jobs for any recurring schedule whose next_run_at <= now.

    Thin wrapper around `portal_recurring.generate_jobs_for_due_schedules`.
    Returns the list of created Job ids (serialized to JSON by Celery).
    """
    from portal_recurring import generate_jobs_for_due_schedules

    created = generate_jobs_for_due_schedules(_dt.datetime.utcnow())
    if created:
        logger.info("portal.recurring_tick created %d jobs", len(created))
    return created


@celery.task(name="portal.invoice_monthly")
def invoice_monthly(month=None, year=None):
    """Generate monthly invoices.

    When called with no args (the Beat trigger), invoices the *previous*
    month — so a run at 02:00 UTC on 2026-05-01 invoices April 2026.

    Passing month/year explicitly supports manual backfills:
        celery -A celery_app.celery call portal.invoice_monthly \
            --args='[3, 2026]'
    """
    from portal_invoicing import generate_monthly_invoices

    if month is None or year is None:
        today = _dt.date.today()
        first_of_this_month = today.replace(day=1)
        last_of_prev = first_of_this_month - _dt.timedelta(days=1)
        month = last_of_prev.month
        year = last_of_prev.year

    created = generate_monthly_invoices(int(month), int(year))
    logger.info(
        "portal.invoice_monthly %02d/%d created %d invoices",
        month, year, len(created),
    )
    return created


# ---------------------------------------------------------------------------
# Customer-side scheduled tasks (migrated from Vivobook crontab 2026-05-04)
# ---------------------------------------------------------------------------

@celery.task(name="customer.drip_emails")
def drip_emails():
    """Process abandoned-booking drip emails (1h, 24h, 72h follow-ups)."""
    from drip_scheduler import run_drip
    return run_drip()


@celery.task(name="customer.review_calls")
def review_calls():
    """Place post-job review calls and win-back calls via Vapi."""
    from review_scheduler import run_review_calls, run_winback_calls
    review_count = run_review_calls()
    winback_count = run_winback_calls()
    logger.info("customer.review_calls reviews=%d winbacks=%d", review_count, winback_count)
    return {"review_calls": review_count, "winback_calls": winback_count}


@celery.task(name="customer.reminders")
def reminders():
    """Place 24h pre-pickup reminder calls."""
    from reminder_scheduler import run_reminders
    return run_reminders()


# ---------------------------------------------------------------------------
# Beat schedule
# ---------------------------------------------------------------------------
celery.conf.beat_schedule = {
    "portal-recurring-tick-every-5min": {
        "task": "portal.recurring_tick",
        "schedule": crontab(minute="*/5"),
    },
    "portal-invoice-monthly-at-02utc-day1": {
        "task": "portal.invoice_monthly",
        "schedule": crontab(minute=0, hour=2, day_of_month=1),
    },
    # Customer-side schedulers (migrated from Vivobook cron 2026-05-04).
    # Slight offsets so Celery doesn't fire all three at the same instant.
    "customer-drip-emails-every-30min": {
        "task": "customer.drip_emails",
        "schedule": crontab(minute="0,30"),
    },
    "customer-review-calls-every-30min": {
        "task": "customer.review_calls",
        "schedule": crontab(minute="5,35"),
    },
    "customer-reminders-every-30min": {
        "task": "customer.reminders",
        "schedule": crontab(minute="10,40"),
    },
}
