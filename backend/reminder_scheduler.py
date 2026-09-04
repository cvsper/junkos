"""
Outbound reminder call scheduler with voicemail drop.

Uses Vapi to call customers ~24 hours before their scheduled job.
Maya confirms the date, time, address, and items — or leaves a voicemail.

Run as a cron job (recommended: every 30 min alongside drip_scheduler):
    python reminder_scheduler.py
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
VAPI_PHONE = "+15619441636"
VAPI_CALL_URL = "https://api.vapi.ai/call/phone"

BACKEND_URL = os.environ.get("BACKEND_URL", "https://junkos-backend.onrender.com")

# Reminder window: jobs scheduled 23-25 hours from now (±1h around 24h mark)
REMINDER_WINDOW_MIN_HOURS = 23
REMINDER_WINDOW_MAX_HOURS = 25


def format_items_list(items):
    """Format items JSON into a human-readable string for the call script."""
    if not items:
        return "your items"
    if isinstance(items, list):
        if len(items) == 1:
            return items[0] if isinstance(items[0], str) else items[0].get("name", "your item")
        names = []
        for item in items:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                names.append(item.get("name", item.get("type", "item")))
        if len(names) <= 2:
            return " and ".join(names)
        return ", ".join(names[:-1]) + ", and " + names[-1]
    return "your items"


def format_scheduled_time(dt):
    """Format a datetime into a friendly string like 'Tuesday, March 25th at 10 AM'."""
    if not dt:
        return "your scheduled time"

    if hasattr(dt, "astimezone"):
        from timeutils import to_local
        dt = to_local(dt)  # Maya reads this aloud in Florida time

    day_suffix = "th"
    day = dt.day
    if day in (1, 21, 31):
        day_suffix = "st"
    elif day in (2, 22):
        day_suffix = "nd"
    elif day in (3, 23):
        day_suffix = "rd"

    hour = dt.strftime("%-I %p") if hasattr(dt, "strftime") else str(dt)
    return dt.strftime(f"%A, %B {day}{day_suffix} at {hour}")


def build_first_message(name, scheduled_at, address, items):
    """Build the live call greeting message."""
    friendly_name = (name or "").split()[0] if name else "there"
    time_str = format_scheduled_time(scheduled_at)
    items_str = format_items_list(items)

    return (
        f"Hey {friendly_name}! This is Maya from You-Move. "
        f"I'm calling to confirm your junk removal appointment "
        f"scheduled for {time_str} at {address}. "
        f"We'll be picking up {items_str}. "
        f"Does that all still work for you?"
    )


def build_voicemail_message(name, scheduled_at, address):
    """Build the voicemail drop message."""
    friendly_name = (name or "").split()[0] if name else "there"
    time_str = format_scheduled_time(scheduled_at)

    return (
        f"Hey {friendly_name}, this is Maya from You-Move! "
        f"Just a friendly reminder that your junk removal is scheduled for "
        f"{time_str} at {address}. "
        f"If you need to make any changes, give us a call back at "
        f"{VAPI_PHONE.replace('+1', '').replace('+', '')}. "
        f"We look forward to helping you out. Have a great day!"
    )


def initiate_reminder_call(job, customer):
    """Place an outbound reminder call via Vapi."""
    customer_phone = customer.phone
    if not customer_phone:
        logger.warning("Job %s: customer %s has no phone number, skipping",
                       job.id, customer.id)
        return None

    # Normalize phone number — ensure it starts with +1
    phone = customer_phone.strip()
    if not phone.startswith("+"):
        if phone.startswith("1") and len(phone) == 11:
            phone = "+" + phone
        else:
            phone = "+1" + phone.lstrip("1")

    first_message = build_first_message(
        name=customer.name,
        scheduled_at=job.scheduled_at,
        address=job.address,
        items=job.items,
    )
    voicemail_message = build_voicemail_message(
        name=customer.name,
        scheduled_at=job.scheduled_at,
        address=job.address,
    )

    payload = {
        "assistantId": VAPI_ASSISTANT_ID,
        "phoneNumberId": VAPI_PHONE_NUMBER_ID,
        "customer": {
            "number": phone,
            "name": customer.name or "Customer",
        },
        "assistantOverrides": {
            "firstMessage": first_message,
            "voicemailDetectionEnabled": True,
            "voicemailMessage": voicemail_message,
        },
    }

    headers = {
        "Authorization": f"Bearer {VAPI_API_KEY}",
        "Content-Type": "application/json",
    }

    logger.info("Placing reminder call for job %s to %s", job.id, phone)

    try:
        resp = requests.post(VAPI_CALL_URL, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        call_id = data.get("id")
        logger.info("Call initiated successfully: call_id=%s, job=%s", call_id, job.id)
        return call_id
    except requests.exceptions.RequestException as e:
        logger.error("Failed to place call for job %s: %s", job.id, str(e))
        if hasattr(e, "response") and e.response is not None:
            logger.error("Response body: %s", e.response.text)
        return None


def run_reminders():
    """Query upcoming jobs and place reminder calls."""
    if not VAPI_API_KEY:
        logger.error("VAPI_API_KEY not set. Exiting.")
        return 0

    from server import app

    with app.app_context():
        from models import db, Job, User

        now = datetime.now(timezone.utc)
        window_start = now + timedelta(hours=REMINDER_WINDOW_MIN_HOURS)
        window_end = now + timedelta(hours=REMINDER_WINDOW_MAX_HOURS)

        # Find jobs scheduled tomorrow (24h ± 1h) that haven't been reminded
        jobs = Job.query.filter(
            Job.scheduled_at >= window_start,
            Job.scheduled_at <= window_end,
            Job.reminder_sent == False,
            Job.status.in_(["pending", "confirmed", "accepted", "assigned"]),
        ).all()

        logger.info("Found %d jobs needing reminder calls (window: %s to %s)",
                     len(jobs), window_start.isoformat(), window_end.isoformat())

        calls_made = 0
        calls_failed = 0

        for job in jobs:
            customer = User.query.get(job.customer_id)
            if not customer:
                logger.warning("Job %s: customer %s not found, skipping",
                               job.id, job.customer_id)
                continue

            call_id = initiate_reminder_call(job, customer)

            if call_id:
                job.reminder_sent = True
                job.reminder_call_id = call_id
                calls_made += 1
            else:
                calls_failed += 1

        db.session.commit()
        logger.info("Reminder run complete: %d calls placed, %d failed",
                     calls_made, calls_failed)
        return calls_made


def main():
    """Entry point for cron / CLI execution."""
    logger.info("=" * 60)
    logger.info("Reminder scheduler starting")
    logger.info("=" * 60)

    calls = run_reminders()

    logger.info("=" * 60)
    logger.info("Reminder scheduler finished: %d calls placed", calls)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
