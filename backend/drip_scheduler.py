"""
Abandoned booking email drip scheduler.

Run as a cron job or scheduled task:
    python drip_scheduler.py

Drip stages:
    0 -> 1: Send 1-hour follow-up (after 1 hour)
    1 -> 2: Send 24-hour follow-up (after 24 hours from creation)
    2 -> 3: Send 72-hour follow-up (after 72 hours from creation)
"""

import os
import sys
import logging
from datetime import datetime, timezone, timedelta

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Drip timing: (min_age_hours, max_age_hours, stage_from, stage_to, template)
DRIP_STAGES = [
    (1, 23, 0, 1, "1h"),
    (24, 71, 1, 2, "24h"),
    (72, 168, 2, 3, "72h"),  # Stop after 7 days
]

FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://app.goumuve.com")


def run_drip():
    """Process all pending drip emails."""
    from server import app

    with app.app_context():
        from models import db, AbandonedBooking
        from notifications import send_email
        from email_templates import (
            abandoned_drip_1h_html,
            abandoned_drip_24h_html,
            abandoned_drip_72h_html,
        )

        now = datetime.now(timezone.utc)
        sent_count = 0

        for min_hours, max_hours, stage_from, stage_to, template_name in DRIP_STAGES:
            cutoff_min = now - timedelta(hours=max_hours)
            cutoff_max = now - timedelta(hours=min_hours)

            candidates = AbandonedBooking.query.filter(
                AbandonedBooking.converted == False,
                AbandonedBooking.drip_stage == stage_from,
                AbandonedBooking.created_at >= cutoff_min,
                AbandonedBooking.created_at <= cutoff_max,
            ).all()

            for ab in candidates:
                resume_url = "{}/book".format(FRONTEND_URL)

                if template_name == "1h":
                    subject = "Still thinking about junk removal?"
                    html = abandoned_drip_1h_html(
                        name=ab.name, items=ab.items, resume_url=resume_url
                    )
                elif template_name == "24h":
                    subject = "Your junk removal quote is waiting"
                    html = abandoned_drip_24h_html(
                        name=ab.name, estimated_price=ab.estimated_price,
                        resume_url=resume_url,
                    )
                else:
                    subject = "Last chance — 10% off your first pickup"
                    html = abandoned_drip_72h_html(
                        name=ab.name, resume_url=resume_url
                    )

                send_email(ab.email, subject, html)
                ab.drip_stage = stage_to
                ab.last_drip_at = now
                sent_count += 1
                logger.info("Drip %s sent to %s (stage %d->%d)",
                            template_name, ab.email, stage_from, stage_to)

        db.session.commit()
        logger.info("Drip run complete: %d emails sent", sent_count)
        return sent_count


if __name__ == "__main__":
    run_drip()
