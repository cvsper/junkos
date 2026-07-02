"""
No-show watchdog for Umuve jobs.

Runs as a cron job (recommended: every 5 minutes). Two checks per pass:

1. **T-30 unassigned** — Job scheduled 25-35 min from now, status still open
   (pending/confirmed/accepted/assigned), AND no driver_id AND no operator_id.
   Most likely: the post-payment auto-assign found nobody, sevs missed the
   alert, and the customer's pickup window is rushing up. Fire the existing
   _notify_admin_no_operators URGENT alert so sevs can scramble or refund
   before the customer realizes nobody is coming. (This is the Weston/Sy
   pattern caught 30 min earlier.)

2. **T+15 late-start** — Job scheduled 10-25 min ago, status is still
   pending/confirmed/accepted/assigned (i.e. nobody pressed "start" / no
   real-world progress). Either the contractor is silently no-showing OR
   the assignment never accepted. Fire the URGENT late-job alert AND text
   the customer a reassurance message so they don't sit there fuming.

Idempotency: each alert fires once per job via the noshow_t30_alerted /
noshow_late_alerted boolean flags on Job (added in migrate.py 2026-05-27).

Usage:
    python noshow_watchdog.py             # standalone, one pass
    # Render cron job (every 5 min):
    */5 * * * *  cd /app && python noshow_watchdog.py
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

# Windows are intentionally wider than the 5-min cron tick so a missed run
# doesn't drop a check entirely.
T30_WINDOW_MIN_MINUTES = 25
T30_WINDOW_MAX_MINUTES = 35

LATE_WINDOW_MIN_MINUTES = 10
LATE_WINDOW_MAX_MINUTES = 25


def _statuses_open():
    """Statuses that still represent an unfinished job (no real-world start).

    "broadcasting" matters: a paid job mid-offer-wave with no acceptor is
    exactly the case the watchdog exists for — omitting it made those jobs
    invisible to every safety net.
    """
    return ("pending", "confirmed", "broadcasting", "accepted", "assigned", "in_progress")


def run_t30_check():
    """Alert for jobs ~30 min from start that still have no contractor assigned."""
    from server import app
    with app.app_context():
        from models import db, Job
        from dispatcher import _notify_admin_no_operators

        now = datetime.now(timezone.utc)
        window_start = now + timedelta(minutes=T30_WINDOW_MIN_MINUTES)
        window_end = now + timedelta(minutes=T30_WINDOW_MAX_MINUTES)

        jobs = Job.query.filter(
            Job.scheduled_at >= window_start,
            Job.scheduled_at <= window_end,
            Job.noshow_t30_alerted == False,
            Job.driver_id.is_(None),
            Job.operator_id.is_(None),
            Job.status.in_(_statuses_open()),
        ).all()

        logger.info(
            "T-30 check: %d unassigned jobs in window %s..%s",
            len(jobs), window_start.isoformat(), window_end.isoformat(),
        )

        fired = 0
        for job in jobs:
            try:
                _notify_admin_no_operators(job)
                job.noshow_t30_alerted = True
                fired += 1
                logger.info(
                    "T-30 alert fired for job %s (scheduled %s)",
                    job.id, job.scheduled_at,
                )
            except Exception:
                logger.exception("T-30 alert failed for job %s", job.id)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception("Failed to commit T-30 flags")

        return fired


def run_late_check():
    """Alert for jobs past their scheduled start with no real-world progress."""
    from server import app
    with app.app_context():
        from models import db, Job, User
        from dispatcher import _notify_admin_late_job

        now = datetime.now(timezone.utc)
        # Window: jobs whose scheduled_at fell 10..25 min ago, still "open"
        window_start = now - timedelta(minutes=LATE_WINDOW_MAX_MINUTES)
        window_end = now - timedelta(minutes=LATE_WINDOW_MIN_MINUTES)

        jobs = Job.query.filter(
            Job.scheduled_at >= window_start,
            Job.scheduled_at <= window_end,
            Job.noshow_late_alerted == False,
            Job.status.in_(_statuses_open()),
        ).all()

        logger.info(
            "Late-start check: %d late jobs in window %s..%s",
            len(jobs), window_start.isoformat(), window_end.isoformat(),
        )

        fired = 0
        for job in jobs:
            try:
                mins_late = (
                    int((now - job.scheduled_at).total_seconds() // 60)
                    if job.scheduled_at else 0
                )
                _notify_admin_late_job(job, mins_late)

                # Customer reassurance text — heads off "where is my hauler" rage
                try:
                    customer = db.session.get(User, job.customer_id)
                    if customer and customer.phone:
                        from sms_service import send_sms_async
                        first_name = (customer.name or "there").split()[0]
                        addr_short = (job.address or "your pickup")[:60]
                        send_sms_async(customer.phone, (
                            "Hey {name} — this is umuve. We're confirming your "
                            "hauler for {addr} now. Sorry for the short delay; "
                            "we'll text you the moment they're en route. Reply "
                            "to this if you need anything in the meantime."
                        ).format(name=first_name, addr=addr_short))
                except Exception:
                    logger.exception(
                        "Failed to text customer for late job %s", job.id,
                    )

                job.noshow_late_alerted = True
                fired += 1
                logger.info(
                    "Late-start alert fired for job %s (%d min late)",
                    job.id, mins_late,
                )
            except Exception:
                logger.exception("Late-start alert failed for job %s", job.id)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception("Failed to commit late-start flags")

        return fired


def main():
    logger.info("=" * 60)
    logger.info("No-show watchdog starting")
    logger.info("=" * 60)

    t30 = run_t30_check()
    late = run_late_check()

    logger.info("Watchdog done: T-30 alerts=%d, late alerts=%d", t30, late)
    return t30 + late


if __name__ == "__main__":
    sys.exit(0 if main() is not None else 1)
