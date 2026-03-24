"""
Outbound call schedulers: post-job review requests and win-back calls.

Uses Vapi to have Maya call customers for Google reviews (1-3h after job
completion) and to re-engage dormant customers (30+ days since last job).

Run as a cron job (recommended: every 30 min):
    python review_scheduler.py
"""

import os
import sys
import logging
import requests
from datetime import datetime, timezone, timedelta

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
VAPI_API_KEY = os.environ.get("VAPI_API_KEY")
VAPI_ASSISTANT_ID = "91198234-25c8-450a-9075-854509e9e59d"
VAPI_PHONE_NUMBER_ID = "8efe5578-e752-4154-98d0-b1dc3eba3938"
VAPI_CALL_URL = "https://api.vapi.ai/call/phone"

BACKEND_URL = os.environ.get("BACKEND_URL", "https://junkos-backend.onrender.com")

# Review call window: 1-3 hours after job completion
REVIEW_WINDOW_MIN_HOURS = 1
REVIEW_WINDOW_MAX_HOURS = 3

# Win-back: days since last completed job before calling
WINBACK_DAYS_THRESHOLD = 30


def normalize_phone(phone_str):
    """Ensure phone number starts with +1."""
    phone = (phone_str or "").strip()
    if not phone:
        return None
    if not phone.startswith("+"):
        if phone.startswith("1") and len(phone) == 11:
            phone = "+" + phone
        else:
            phone = "+1" + phone.lstrip("1")
    return phone


def place_vapi_call(phone, customer_name, first_message, voicemail_message=None):
    """Place an outbound call via Vapi. Returns call_id or None."""
    payload = {
        "assistantId": VAPI_ASSISTANT_ID,
        "phoneNumberId": VAPI_PHONE_NUMBER_ID,
        "customer": {
            "number": phone,
            "name": customer_name or "Customer",
        },
        "assistantOverrides": {
            "firstMessage": first_message,
            "voicemailDetectionEnabled": True,
            "serverUrl": BACKEND_URL + "/api/vapi/tool",
        },
    }

    if voicemail_message:
        payload["assistantOverrides"]["voicemailMessage"] = voicemail_message

    headers = {
        "Authorization": f"Bearer {VAPI_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(VAPI_CALL_URL, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        call_id = data.get("id")
        logger.info("Call initiated: call_id=%s, phone=%s", call_id, phone)
        return call_id
    except requests.exceptions.RequestException as e:
        logger.error("Failed to place call to %s: %s", phone, str(e))
        if hasattr(e, "response") and e.response is not None:
            logger.error("Response body: %s", e.response.text)
        return None


# ---------------------------------------------------------------------------
# Feature 1: Post-Job Review Calls
# ---------------------------------------------------------------------------

def run_review_calls():
    """Query recently completed jobs and call customers for Google reviews."""
    if not VAPI_API_KEY:
        logger.error("VAPI_API_KEY not set. Skipping review calls.")
        return 0

    from server import app

    with app.app_context():
        from models import db, Job, User

        now = datetime.now(timezone.utc)
        window_start = now - timedelta(hours=REVIEW_WINDOW_MAX_HOURS)
        window_end = now - timedelta(hours=REVIEW_WINDOW_MIN_HOURS)

        # Jobs completed 1-3 hours ago that haven't been review-called
        jobs = Job.query.filter(
            Job.status == "completed",
            Job.completed_at >= window_start,
            Job.completed_at <= window_end,
            Job.review_requested == False,
        ).all()

        logger.info(
            "Found %d completed jobs needing review calls (completed between %s and %s)",
            len(jobs), window_start.isoformat(), window_end.isoformat(),
        )

        calls_made = 0
        calls_failed = 0

        for job in jobs:
            customer = User.query.get(job.customer_id)
            if not customer:
                logger.warning("Job %s: customer %s not found, skipping", job.id, job.customer_id)
                continue

            phone = normalize_phone(customer.phone)
            if not phone:
                logger.warning("Job %s: customer %s has no phone, skipping", job.id, customer.id)
                continue

            friendly_name = (customer.name or "").split()[0] if customer.name else "there"

            first_message = (
                f"Hey {friendly_name}! This is Maya from You-Move. "
                f"I just wanted to check in — how did everything go with "
                f"your pickup today?"
            )

            voicemail_message = (
                f"Hey {friendly_name}, this is Maya from You-Move! "
                f"Just wanted to check in and make sure everything went "
                f"great with your pickup today. If you have a moment, "
                f"we'd really appreciate a quick Google review — it helps "
                f"us a ton! We'll text you the link. Thanks so much, "
                f"and have a wonderful day!"
            )

            call_id = place_vapi_call(phone, customer.name, first_message, voicemail_message)

            if call_id:
                job.review_requested = True
                job.review_call_id = call_id
                calls_made += 1
            else:
                calls_failed += 1

        db.session.commit()
        logger.info("Review calls complete: %d placed, %d failed", calls_made, calls_failed)
        return calls_made


# ---------------------------------------------------------------------------
# Feature 2: Win-Back Calls
# ---------------------------------------------------------------------------

def run_winback_calls():
    """Query dormant customers (30+ days since last job) and call to re-engage."""
    if not VAPI_API_KEY:
        logger.error("VAPI_API_KEY not set. Skipping win-back calls.")
        return 0

    from server import app

    with app.app_context():
        from models import db, Job, User
        from sqlalchemy import func

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=WINBACK_DAYS_THRESHOLD)

        # Find users whose most recent completed job was before the cutoff
        # and who haven't been win-back called yet
        subq = (
            db.session.query(
                Job.customer_id,
                func.max(Job.completed_at).label("last_completed"),
            )
            .filter(Job.status == "completed")
            .group_by(Job.customer_id)
            .subquery()
        )

        results = (
            db.session.query(User, subq.c.last_completed)
            .join(subq, User.id == subq.c.customer_id)
            .filter(
                subq.c.last_completed <= cutoff,
                User.winback_called == False,
                User.phone.isnot(None),
                User.status == "active",
            )
            .all()
        )

        logger.info(
            "Found %d dormant customers eligible for win-back calls (last job before %s)",
            len(results), cutoff.isoformat(),
        )

        calls_made = 0
        calls_failed = 0

        for user, last_completed in results:
            phone = normalize_phone(user.phone)
            if not phone:
                continue

            friendly_name = (user.name or "").split()[0] if user.name else "there"

            first_message = (
                f"Hey {friendly_name}! This is Maya from You-Move. "
                f"It's been a little while since we helped you out — "
                f"got anything else piling up we can take care of?"
            )

            voicemail_message = (
                f"Hey {friendly_name}, this is Maya from You-Move! "
                f"It's been a bit since your last pickup and we wanted "
                f"to check in. If you've got anything piling up — "
                f"furniture, appliances, yard waste, whatever — just "
                f"give us a call back at 561-944-1636 and we'll get "
                f"you scheduled. Have a great day!"
            )

            call_id = place_vapi_call(phone, user.name, first_message, voicemail_message)

            if call_id:
                user.winback_called = True
                user.last_winback_at = now
                calls_made += 1
            else:
                calls_failed += 1

        db.session.commit()
        logger.info("Win-back calls complete: %d placed, %d failed", calls_made, calls_failed)
        return calls_made


def reset_winback_after_completion(job):
    """Reset winback_called=False after a job completes so the customer
    can be called again in the next cycle. Call this when marking a job
    as 'completed'."""
    from models import db, User
    customer = User.query.get(job.customer_id)
    if customer:
        customer.winback_called = False
        db.session.commit()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    """Run both review calls and win-back calls."""
    logger.info("=" * 60)
    logger.info("Review & win-back scheduler starting")
    logger.info("=" * 60)

    review_count = run_review_calls()
    winback_count = run_winback_calls()

    logger.info("=" * 60)
    logger.info(
        "Scheduler finished: %d review calls, %d win-back calls",
        review_count, winback_count,
    )
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
