"""
Umuve SMS Service

Centralised SMS sending via Twilio with:
- Phone number formatting (ensures +1 prefix for US numbers)
- Graceful fallback when credentials are not configured
- Background-thread sending so SMS never blocks a request
- Pre-built message helpers for every job lifecycle event

IMPORTANT: No function in this module should ever raise an exception.
All errors are caught and logged so that an SMS failure never takes down
a booking or payment flow.
"""

import os
import re
import logging
import threading

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Twilio configuration (lazy-initialised)
# ---------------------------------------------------------------------------
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER",
                                     os.environ.get("TWILIO_FROM_NUMBER", ""))

_twilio_client = None


def _get_twilio():
    """Lazily initialise the Twilio REST client."""
    global _twilio_client
    if _twilio_client is None and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        try:
            from twilio.rest import Client
            _twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        except Exception:
            logger.exception("Failed to initialise Twilio client")
    return _twilio_client


# ---------------------------------------------------------------------------
# Phone number formatting
# ---------------------------------------------------------------------------
def format_phone(phone):
    """Ensure a US phone number has the +1 international prefix.

    Handles common input formats:
        "3055551234"       -> "+13055551234"
        "13055551234"      -> "+13055551234"
        "+13055551234"     -> "+13055551234"
        "(305) 555-1234"   -> "+13055551234"
        ""                 -> ""
        None               -> ""

    Non-US numbers that already start with '+' are returned as-is.
    """
    if not phone:
        return ""

    # Strip everything except digits and leading '+'
    stripped = re.sub(r"[^\d+]", "", phone.strip())

    if not stripped:
        return ""

    # Already has international prefix
    if stripped.startswith("+"):
        return stripped

    # Digits only from here
    digits = re.sub(r"\D", "", stripped)

    if len(digits) == 10:
        # US 10-digit number -> prepend +1
        return "+1{}".format(digits)
    elif len(digits) == 11 and digits.startswith("1"):
        # US 11-digit with leading 1 -> prepend +
        return "+{}".format(digits)
    else:
        # Best effort: prepend + and hope for the best
        return "+{}".format(digits)


# ---------------------------------------------------------------------------
# Core send function
# ---------------------------------------------------------------------------
def send_sms(to_phone, message):
    """Send an SMS via Twilio. Returns the message SID or None.

    If Twilio credentials are not configured, logs the message content at
    INFO level (dev/test fallback) and returns None.

    Never raises.
    """
    try:
        formatted = format_phone(to_phone)
        if not formatted:
            logger.warning("send_sms called with empty/invalid phone: %r", to_phone)
            return None

        client = _get_twilio()
        if not client or not TWILIO_PHONE_NUMBER:
            logger.warning("[SMS-DEV] No Twilio credentials — SMS NOT sent. To %s: %s", formatted, message[:50])
            return None

        msg = client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=formatted,
        )
        logger.info("SMS sent to %s (SID: %s)", formatted, msg.sid)
        return msg.sid
    except Exception:
        logger.exception("Failed to send SMS to %s", to_phone)
        return None


def send_sms_async(to_phone, message):
    """Send an SMS in a background thread so the calling request is not blocked.

    Returns the Thread object (useful for testing), or None if the phone is
    empty.  Never raises.
    """
    try:
        if not to_phone:
            return None
        t = threading.Thread(
            target=send_sms,
            args=(to_phone, message),
            daemon=True,
        )
        t.start()
        return t
    except Exception:
        logger.exception("Failed to start background SMS thread for %s", to_phone)
        return None


# ---------------------------------------------------------------------------
# Job lifecycle SMS helpers
# ---------------------------------------------------------------------------

def sms_booking_confirmed(to_phone, job_id, date, time):
    """Booking confirmed -> SMS to customer.

    Message: "Your Umuve pickup is confirmed for {date} at {time}. Job #{job_id}"
    """
    try:
        short_id = str(job_id)[:8] if job_id else "N/A"
        body = (
            "Your Umuve pickup is confirmed for {} at {}. "
            "Job #{}"
        ).format(date or "TBD", time or "TBD", short_id)
        return send_sms_async(to_phone, body)
    except Exception:
        logger.exception("sms_booking_confirmed failed for %s", to_phone)
        return None


def sms_driver_en_route(to_phone, driver_name, tracking_url=None):
    """Driver en_route -> SMS to customer.

    Message: "Your driver {name} is on the way! Track live: {tracking_url}"
    """
    try:
        name = driver_name or "your driver"
        if tracking_url:
            body = (
                "Your driver {} is on the way! "
                "Track live: {}"
            ).format(name, tracking_url)
        else:
            body = "Your driver {} is on the way!".format(name)
        return send_sms_async(to_phone, body)
    except Exception:
        logger.exception("sms_driver_en_route failed for %s", to_phone)
        return None


def sms_driver_arrived(to_phone, address):
    """Driver arrived -> SMS to customer.

    Message: "Your driver has arrived at {address}!"
    """
    try:
        body = "Your driver has arrived at {}!".format(address or "your location")
        return send_sms_async(to_phone, body)
    except Exception:
        logger.exception("sms_driver_arrived failed for %s", to_phone)
        return None


def sms_job_completed(to_phone, amount):
    """Job completed -> SMS to customer.

    Message: "Pickup complete! Total: ${amount}. Thank you!"
    """
    try:
        if amount is not None:
            body = "Pickup complete! Total: ${:.2f}. Thank you for using Umuve!".format(
                float(amount)
            )
        else:
            body = "Pickup complete! Thank you for using Umuve!"
        return send_sms_async(to_phone, body)
    except Exception:
        logger.exception("sms_job_completed failed for %s", to_phone)
        return None


def sms_pickup_reminder(to_phone, job_id, date, time, address):
    """24-hour pickup reminder -> SMS to customer.

    Intended to be called by a scheduler (not wired up here).
    Message: "Reminder: Your Umuve pickup is tomorrow at {time}. Job #{job_id}"
    """
    try:
        short_id = str(job_id)[:8] if job_id else "N/A"
        body = (
            "Reminder: Your Umuve pickup is tomorrow at {} at {}. "
            "Job #{}\n"
            "Address: {}"
        ).format(date or "your scheduled date", time or "the scheduled time",
                 short_id, address or "your location")
        return send_sms_async(to_phone, body)
    except Exception:
        logger.exception("sms_pickup_reminder failed for %s", to_phone)
        return None


def sms_custom(to_phone, message):
    """Send a custom / freeform SMS (used by the admin endpoint).

    Sends in a background thread. Never raises.
    """
    try:
        return send_sms_async(to_phone, message)
    except Exception:
        logger.exception("sms_custom failed for %s", to_phone)
        return None


# ---------------------------------------------------------------------------
# Review request SMS (delayed after job completion)
# ---------------------------------------------------------------------------

# Set GOOGLE_REVIEW_URL on Render once the Umuve Google Business Profile is
# claimed (the old hardcoded g.page/r/umuve/review placeholder 302'd to the
# Google homepage — worse than no link). Unset → ask for feedback by reply.


def send_review_request_sms(phone, customer_name, city_name):
    """Send a Google review request SMS to the customer.

    Intended to be called after a delay (see ``schedule_review_request``).
    Never raises.
    """
    try:
        import os as _os
        review_url = _os.environ.get("GOOGLE_REVIEW_URL", "").strip()
        first_name = customer_name.split()[0] if customer_name else "there"
        city = city_name or "your area"
        if review_url:
            body = (
                "Hi {}! Thanks for choosing Umuve for your "
                "junk removal in {}. We'd love your feedback — "
                "it takes 30 seconds and helps us serve {} better.\n\n"
                "Leave a review: {}\n\n"
                "Thanks! — The Umuve Team"
            ).format(first_name, city, city, review_url)
        else:
            body = (
                "Hi {}! Thanks for choosing Umuve for your "
                "junk removal in {}. How did we do? Reply to this "
                "text with a quick note or a 1-5 — it goes straight "
                "to the team.\n\n— The Umuve Team"
            ).format(first_name, city)
        send_sms_async(phone, body)
    except Exception:
        logger.exception("send_review_request_sms failed for %s", phone)


# ---------------------------------------------------------------------------
# Abandoned booking recovery SMS (delayed after pending job creation)
# ---------------------------------------------------------------------------

# Active timers keyed by job_id — allows cancellation when job is confirmed/paid.
_abandoned_timers = {}


def _generate_comeback_promo(job_id):
    """Create a single-use 10% promo code for an abandoned booking.

    Returns the code string, or None on failure.  Requires Flask app context.
    Never raises.
    """
    try:
        import random
        import string
        from datetime import datetime, timezone, timedelta
        from models import db, PromoCode, generate_uuid

        code = "COMEBACK" + "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        promo = PromoCode(
            id=generate_uuid(),
            code=code,
            discount_type="percentage",
            discount_value=10.0,
            max_uses=1,
            use_count=0,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            is_active=True,
        )
        db.session.add(promo)
        db.session.commit()
        return code
    except Exception:
        logger.exception("_generate_comeback_promo failed for job %s", job_id)
        return None


def _send_abandoned_booking_sms(to_phone, customer_name, job_id, app):
    """Send the abandoned booking recovery SMS (runs inside timer callback).

    Needs the Flask ``app`` reference so we can push an application context
    for the database access required to create the promo code.
    Never raises.
    """
    try:
        # Clean up the timer reference
        _abandoned_timers.pop(job_id, None)

        with app.app_context():
            # Check if job is still pending — skip if already confirmed/paid
            from models import Job
            job = Job.query.get(job_id)
            if not job or job.status != "pending":
                logger.info(
                    "Abandoned booking SMS skipped for job %s (status: %s)",
                    job_id, job.status if job else "not found",
                )
                return

            code = _generate_comeback_promo(job_id)
            if not code:
                return

            first_name = customer_name.split()[0] if customer_name else "there"
            body = (
                "Hey {}! You left a pickup in your cart. "
                "Book now and get 10% off with code {}. "
                "Reply STOP to opt out."
            ).format(first_name, code)
            send_sms(to_phone, body)
    except Exception:
        logger.exception("_send_abandoned_booking_sms failed for job %s", job_id)


def schedule_abandoned_booking_sms(to_phone, customer_name, job_id, app, delay_seconds=1800):
    """Schedule an abandoned booking recovery SMS after *delay_seconds* (default 30 min).

    Uses ``threading.Timer`` (same pattern as ``schedule_review_request``).
    The timer is daemonic — it will not prevent process shutdown.

    Pass the Flask ``app`` object so the callback can create an app context for
    database access (promo code creation + job status check).

    Never raises.
    """
    try:
        if not to_phone:
            return
        timer = threading.Timer(
            delay_seconds,
            _send_abandoned_booking_sms,
            args=[to_phone, customer_name, job_id, app],
        )
        timer.daemon = True
        _abandoned_timers[job_id] = timer
        timer.start()
        logger.info(
            "Scheduled abandoned booking SMS to %s for job %s in %d seconds",
            format_phone(to_phone), job_id, delay_seconds,
        )
    except Exception:
        logger.exception("schedule_abandoned_booking_sms failed for job %s", job_id)


def cancel_abandoned_booking_sms(job_id):
    """Cancel a pending abandoned booking SMS timer for the given job.

    Safe to call even if no timer exists for the job.  Never raises.
    """
    try:
        timer = _abandoned_timers.pop(job_id, None)
        if timer is not None:
            timer.cancel()
            logger.info("Cancelled abandoned booking SMS timer for job %s", job_id)
    except Exception:
        logger.exception("cancel_abandoned_booking_sms failed for job %s", job_id)


def schedule_review_request(phone, customer_name, city_name, delay_seconds=7200):
    """Schedule a review request SMS after a delay (default 2 hours).

    Uses ``threading.Timer`` so no extra dependencies are needed.
    The timer is daemonic — it will not prevent process shutdown, which
    means some review requests may be lost on deploy/restart.  That is
    acceptable for v1.

    Never raises.
    """
    try:
        timer = threading.Timer(
            delay_seconds,
            send_review_request_sms,
            args=[phone, customer_name, city_name],
        )
        timer.daemon = True
        timer.start()
        logger.info(
            "Scheduled review request SMS to %s in %d seconds",
            format_phone(phone), delay_seconds,
        )
    except Exception:
        logger.exception("schedule_review_request failed for %s", phone)
