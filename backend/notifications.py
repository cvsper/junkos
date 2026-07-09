"""
Notification services for Umuve.

Email: Resend (preferred) or SendGrid (legacy fallback).
SMS: Twilio.

IMPORTANT: No function in this module should ever raise an exception.
All errors are caught and logged so that a notification failure never
takes down a booking or payment flow.

Email sending is performed asynchronously via a background thread so that
HTTP request handlers are never blocked by network I/O to the email provider.
"""

import os
import logging
import threading

from email_templates import (
    booking_confirmation_html,
    booking_assigned_html,
    driver_en_route_html,
    job_completed_html,
    payment_receipt_html,
    welcome_html,
    password_reset_html,
    job_status_update_html,
    pickup_reminder_html,
    abandoned_booking_reminder_html,
    abandoned_booking_incentive_html,
    abandoned_booking_final_html,
    winback_html,
    operator_recruitment_1_html,
    operator_recruitment_2_html,
    operator_recruitment_3_html,
    operator_recruitment_4_html,
    operator_recruitment_5_html,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Twilio SMS
# ---------------------------------------------------------------------------
_twilio_client = None

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER", "")


def _get_twilio():
    """Lazily initialise the Twilio client."""
    global _twilio_client
    if _twilio_client is None and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        try:
            from twilio.rest import Client
            _twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        except Exception:
            logger.exception("Failed to initialise Twilio client")
    return _twilio_client


def send_sms(to_number, body):
    """Send an SMS via Twilio. Returns message SID or None.

    Never raises. Logs errors and returns None on failure.
    """
    try:
        client = _get_twilio()
        if not client or not TWILIO_FROM_NUMBER:
            logger.warning("[DEV] No Twilio credentials — SMS NOT sent. To %s: %s", to_number, body[:50])
            return None

        message = client.messages.create(
            body=body,
            from_=TWILIO_FROM_NUMBER,
            to=to_number,
        )
        logger.info("SMS sent to %s (SID: %s)", to_number, message.sid)
        return message.sid
    except Exception:
        logger.exception("Failed to send SMS to %s", to_number)
        return None


def send_verification_sms(phone_number, code):
    """Send a verification code via SMS. Never raises."""
    try:
        body = "Your Umuve verification code is: {}. It expires in 10 minutes.".format(code)
        return send_sms(phone_number, body)
    except Exception:
        logger.exception("Failed in send_verification_sms for %s", phone_number)
        return None


def send_booking_sms(phone_number, booking_id, scheduled_date, address):
    """Send booking confirmation via SMS. Never raises."""
    try:
        short_id = str(booking_id)[:8] if booking_id else "N/A"
        body = (
            "Umuve Booking Confirmed!\n"
            "Booking: #{}\n"
            "Date: {}\n"
            "Address: {}\n\n"
            "We'll send a reminder 24h before your pickup."
        ).format(short_id, scheduled_date, address)
        return send_sms(phone_number, body)
    except Exception:
        logger.exception("Failed in send_booking_sms for %s", phone_number)
        return None


# ---------------------------------------------------------------------------
# Email — Resend (preferred) or SendGrid (legacy fallback)
# ---------------------------------------------------------------------------
# Prefer RESEND_API_KEY_2 (fresh key, verified working 2026-07-09) over the
# original RESEND_API_KEY, which is suspected stale but deliberately left in
# place because other services may still reference it.
RESEND_API_KEY = (os.environ.get("RESEND_API_KEY_2", "")
                  or os.environ.get("RESEND_API_KEY", ""))
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM",
                            os.environ.get("SENDGRID_FROM_EMAIL", "bookings@goumuve.com"))
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME",
                                 os.environ.get("SENDGRID_FROM_NAME", "Umuve"))


def _send_email_sync(to_email, subject, html_content, from_override=None):
    """Send an email synchronously via Resend (preferred) or SendGrid (fallback).

    Returns a status indicator or None in dev mode. Never raises.
    """
    try:
        # --- Resend (preferred) ---
        if RESEND_API_KEY:
            return _send_email_resend(to_email, subject, html_content, from_override)

        # --- SendGrid (legacy fallback) ---
        if SENDGRID_API_KEY:
            return _send_email_sendgrid(to_email, subject, html_content, from_override)

        # --- Dev mode: no email provider configured ---
        logger.warning(
            "[DEV] No email provider configured — email NOT sent. To %s: %s",
            to_email, subject,
        )
        return None
    except Exception:
        logger.exception("Failed to send email to %s", to_email)
        return None


def send_email(to_email, subject, html_content, from_override=None):
    """Send an email asynchronously in a background thread.

    This ensures the HTTP request handler is never blocked by email I/O.
    Returns immediately. Never raises. ``from_override`` (a full "Name <email>"
    string) lets a caller send from a different identity — e.g. the operator
    outreach engine sends from a recruiting address, NOT the customer
    transactional sender, to keep their deliverability separate.
    """
    try:
        thread = threading.Thread(
            target=_send_email_sync,
            args=(to_email, subject, html_content, from_override),
            daemon=True,
        )
        thread.start()
        logger.debug("Email queued (async) to %s: %s", to_email, subject)
    except Exception:
        logger.exception("Failed to queue async email to %s", to_email)


def send_email_sync(to_email, subject, html_content):
    """Public synchronous email sender (for cases where you need to wait).

    Prefer ``send_email`` (async) for request handlers.
    """
    return _send_email_sync(to_email, subject, html_content)


# ---------------------------------------------------------------------------
# Branded approval emails (driver + operator onboarding)
# ---------------------------------------------------------------------------
# Email-client-safe: table layout, inline styles, web-font with fallbacks.
# Built with plain string .replace() (no f-string/.format) so the HTML can
# contain braces/percent/quotes freely. Brand: red #DC2626, Outfit + DM Sans.
import html as _html

_APPROVAL_LOGO = "https://goumuve.com/logo-full.png"

_APPROVAL_STEP = """<tr>
<td width="44" valign="top" style="padding-bottom:__PB__;">
<div style="width:34px;height:34px;background:#DC2626;border-radius:50%;color:#ffffff;font-family:'Outfit',Arial,sans-serif;font-size:16px;font-weight:700;text-align:center;line-height:34px;">__N__</div>
</td>
<td valign="top" style="padding-bottom:__PB__;font-family:'DM Sans',-apple-system,'Segoe UI',Arial,sans-serif;">
<div style="font-size:16px;font-weight:600;color:#141414;">__TITLE__</div>
<div style="font-size:14px;color:#777;line-height:1.55;margin-top:3px;">__DESC__</div>
</td></tr>"""

_APPROVAL_SHELL = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="light">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@600;700;800&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
</head><body style="margin:0;padding:0;background:#f1f1f4;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f1f1f4;"><tr><td align="center" style="padding:36px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:600px;max-width:600px;background:#ffffff;border-radius:18px;overflow:hidden;border:1px solid #e8e8ec;">
<tr><td style="height:6px;background:#DC2626;font-size:0;line-height:0;">&nbsp;</td></tr>
<tr><td style="padding:28px 44px 0 44px;"><img src="__LOGO__" alt="Umuve" height="30" style="height:30px;display:block;border:0;"></td></tr>
<tr><td style="padding:26px 44px 0 44px;">
<div style="font-family:'Outfit','Segoe UI',Arial,sans-serif;font-size:12px;font-weight:700;letter-spacing:2px;color:#DC2626;text-transform:uppercase;">__EYEBROW__</div>
<div style="font-family:'Outfit','Segoe UI',Arial,sans-serif;font-size:32px;line-height:1.12;font-weight:800;color:#141414;margin-top:10px;letter-spacing:-0.5px;">__HEADING__</div>
<div style="font-family:'DM Sans',-apple-system,'Segoe UI',Arial,sans-serif;font-size:16px;line-height:1.6;color:#555;margin-top:14px;">__INTRO__</div>
</td></tr>
<tr><td style="padding:28px 44px 8px 44px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">__STEPS__</table></td></tr>
<tr><td style="padding:18px 44px 4px 44px;"><table role="presentation" cellpadding="0" cellspacing="0"><tr><td bgcolor="#DC2626" style="border-radius:12px;"><a href="__CTA_URL__" style="display:inline-block;padding:15px 34px;font-family:'Outfit','Segoe UI',Arial,sans-serif;font-size:16px;font-weight:700;color:#ffffff;border-radius:12px;">__CTA_LABEL__ &nbsp;&rarr;</a></td></tr></table></td></tr>
<tr><td style="padding:22px 44px 0 44px;"><div style="font-family:'DM Sans',-apple-system,'Segoe UI',Arial,sans-serif;font-size:14px;color:#777;line-height:1.6;">Questions? Just reply to this email &mdash; a real person reads these.</div></td></tr>
<tr><td style="padding:26px 44px 0 44px;"><div style="border-top:1px solid #eeeef1;font-size:0;line-height:0;">&nbsp;</div></td></tr>
<tr><td style="padding:18px 44px 34px 44px;"><div style="font-family:'Outfit','Segoe UI',Arial,sans-serif;font-size:13px;font-weight:700;color:#141414;letter-spacing:0.5px;">UMUVE</div><div style="font-family:'DM Sans',-apple-system,'Segoe UI',Arial,sans-serif;font-size:12px;color:#9a9aa2;line-height:1.6;margin-top:4px;">Premium junk removal &middot; South Florida<br>__FOOTER__</div></td></tr>
</table></td></tr></table></body></html>"""


def _render_steps(steps):
    rows = []
    total = len(steps)
    for idx, (title, desc) in enumerate(steps, 1):
        pb = "0" if idx == total else "22px"
        rows.append(
            _APPROVAL_STEP
            .replace("__PB__", pb)
            .replace("__N__", str(idx))
            .replace("__TITLE__", title)
            .replace("__DESC__", desc)
        )
    return "".join(rows)


def _build_approval_email(eyebrow, heading, intro, steps, cta_label, cta_url, footer):
    return (
        _APPROVAL_SHELL
        .replace("__LOGO__", _APPROVAL_LOGO)
        .replace("__STEPS__", _render_steps(steps))
        .replace("__EYEBROW__", eyebrow)
        .replace("__HEADING__", heading)
        .replace("__INTRO__", intro)
        .replace("__CTA_LABEL__", cta_label)
        .replace("__CTA_URL__", cta_url)
        .replace("__FOOTER__", footer)
    )


def render_driver_approval_email(name):
    """Return (subject, html_content) for an approved driver."""
    first = _html.escape((name or "there").split()[0] or "there")
    html = _build_approval_email(
        eyebrow="Driver Approved &nbsp;&#10003;",
        heading="You're in, " + first + ".",
        intro="Welcome to Umuve &mdash; South Florida's premium junk-removal network. Three quick steps and jobs start coming straight to you.",
        steps=[
            ("Log in to Umuve Pro", "Sign in at app.goumuve.com/driver/login (or the Umuve Pro app) with this email."),
            ("Finish your payment setup", "Connect your bank so you get paid the moment a job is done. <strong style=\"color:#DC2626;\">Don't skip this</strong> &mdash; no payouts without it."),
            ("Go Online", "Flip yourself live and nearby jobs start coming to you."),
        ],
        cta_label="Log in to Umuve Pro",
        cta_url="https://app.goumuve.com/driver/login",
        footer="You're receiving this because your hauler application was approved.",
    )
    return ("You're approved to drive with Umuve!", html)


def render_operator_approval_email(name):
    """Return (subject, html_content) for an approved operator."""
    first = _html.escape((name or "there").split()[0] or "there")
    html = _build_approval_email(
        eyebrow="Operator Approved &nbsp;&#10003;",
        heading="Welcome aboard, " + first + ".",
        intro="Your operator account is live on Umuve &mdash; South Florida's premium junk-removal network. Here's how to get your fleet earning.",
        steps=[
            ("Log in to your operator dashboard", "Sign in at app.goumuve.com/operator with this email to manage your fleet and jobs."),
            ("Finish your payment setup", "Connect your bank so your fleet earnings &amp; commission pay out. <strong style=\"color:#DC2626;\">Required before any payouts.</strong>"),
            ("Invite your drivers", "Send your haulers an invite code from the dashboard &mdash; once they're approved, jobs flow to them and you earn your cut."),
        ],
        cta_label="Open your dashboard",
        cta_url="https://app.goumuve.com/operator",
        footer="You're receiving this because your operator application was approved.",
    )
    return ("Welcome to Umuve — Operator Approved!", html)


def _send_email_resend(to_email, subject, html_content, from_override=None):
    """Send via the Resend API. Returns the response id or None."""
    try:
        import resend
        resend.api_key = RESEND_API_KEY

        params = {
            "from": from_override or "{} <{}>".format(EMAIL_FROM_NAME, EMAIL_FROM),
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        }
        response = resend.Emails.send(params)
        logger.info("Email sent via Resend to %s (id: %s)", to_email, response.get("id"))
        return response.get("id")
    except Exception:
        logger.exception("Resend email failed for %s", to_email)
        return None


def _send_email_sendgrid(to_email, subject, html_content, from_override=None):
    """Send via SendGrid. Returns status code or None."""
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        if from_override and "<" in from_override:
            _from = (from_override.split("<")[1].rstrip(">").strip(),
                     from_override.split("<")[0].strip() or EMAIL_FROM_NAME)
        else:
            _from = (EMAIL_FROM, EMAIL_FROM_NAME)
        message = Mail(
            from_email=_from,
            to_emails=to_email,
            subject=subject,
            html_content=html_content,
        )
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        logger.info("Email sent via SendGrid to %s (status: %s)", to_email, response.status_code)
        return response.status_code
    except Exception:
        logger.exception("SendGrid email failed for %s", to_email)
        return None


# ---------------------------------------------------------------------------
# Booking confirmation email
# ---------------------------------------------------------------------------
def send_booking_confirmation_email(to_email, customer_name, booking_id, address,
                                     scheduled_date, scheduled_time, total_amount):
    """Send a booking confirmation email. Never raises."""
    try:
        short_id = str(booking_id)[:8] if booking_id else "N/A"
        subject = "Your Umuve Booking is Confirmed! #{}".format(short_id)

        html = booking_confirmation_html(
            customer_name=customer_name,
            booking_id=booking_id,
            address=address,
            date=scheduled_date,
            time=scheduled_time,
            total=total_amount,
        )

        return send_email(to_email, subject, html)
    except Exception:
        logger.exception("Failed in send_booking_confirmation_email for %s", to_email)
        return None


# ---------------------------------------------------------------------------
# Job lifecycle: Driver Assigned
# ---------------------------------------------------------------------------
def send_driver_assigned_email(to_email, customer_name, driver_name, address,
                                truck_type=None, eta=None):
    """Email customer that a driver has been assigned. Never raises.

    Backward compatible: ``address`` is kept as positional for existing
    callers; ``truck_type`` and ``eta`` are optional enhancements.
    """
    try:
        subject = "Your Umuve Driver Has Been Assigned"

        html = booking_assigned_html(
            customer_name=customer_name,
            driver_name=driver_name,
            truck_type=truck_type,
            eta=eta or address,
        )

        return send_email(to_email, subject, html)
    except Exception:
        logger.exception("Failed in send_driver_assigned_email for %s", to_email)
        return None


def send_driver_assigned_sms(to_number, driver_name, address):
    """SMS customer that a driver has been assigned. Never raises."""
    try:
        body = "Umuve: Driver {} assigned to your pickup at {}".format(
            driver_name or "your driver", address or "your location"
        )
        return send_sms(to_number, body)
    except Exception:
        logger.exception("Failed in send_driver_assigned_sms for %s", to_number)
        return None


# ---------------------------------------------------------------------------
# Job lifecycle: Driver En Route
# ---------------------------------------------------------------------------
def send_driver_en_route_email(to_email, customer_name, driver_name, address,
                                eta_minutes=None):
    """Email customer that driver is on the way. Never raises.

    Backward compatible: ``address`` is kept as positional for existing
    callers; ``eta_minutes`` is an optional enhancement.
    """
    try:
        subject = "Your Umuve Driver Is On The Way!"

        html = driver_en_route_html(
            customer_name=customer_name,
            driver_name=driver_name,
            eta_minutes=eta_minutes,
        )

        return send_email(to_email, subject, html)
    except Exception:
        logger.exception("Failed in send_driver_en_route_email for %s", to_email)
        return None


# Convenience alias matching the task specification
send_en_route_email = send_driver_en_route_email


def send_driver_en_route_sms(to_number, driver_name, address):
    """SMS customer that driver is en route. Never raises."""
    try:
        body = "Umuve: Driver {} is en route to {}".format(
            driver_name or "your driver", address or "your location"
        )
        return send_sms(to_number, body)
    except Exception:
        logger.exception("Failed in send_driver_en_route_sms for %s", to_number)
        return None


# ---------------------------------------------------------------------------
# Job lifecycle: Job Completed
# ---------------------------------------------------------------------------
def send_job_completed_email(to_email, customer_name, job_id, address,
                              total=None, rating_url=None):
    """Email customer that pickup is complete, asking for a rating. Never raises.

    Backward compatible: ``job_id`` and ``address`` are positional for
    existing callers; ``total`` and ``rating_url`` are optional enhancements.
    """
    try:
        short_id = str(job_id)[:8] if job_id else "N/A"
        subject = "Your Umuve Pickup Is Complete! #{}".format(short_id)

        html = job_completed_html(
            customer_name=customer_name,
            booking_id=job_id,
            total=total,
            rating_url=rating_url,
        )

        return send_email(to_email, subject, html)
    except Exception:
        logger.exception("Failed in send_job_completed_email for %s", to_email)
        return None


# ---------------------------------------------------------------------------
# Payment receipt email
# ---------------------------------------------------------------------------
def send_payment_receipt_email(to_email, customer_name, job_id, address, amount,
                                payment_method_last4=None, date=None):
    """Email customer a payment receipt. Never raises.

    Backward compatible: ``job_id``, ``address``, and ``amount`` are
    positional for existing callers; ``payment_method_last4`` and ``date``
    are optional enhancements.
    """
    try:
        short_id = str(job_id)[:8] if job_id else "N/A"
        subject = "Umuve Payment Receipt #{}".format(short_id)

        html = payment_receipt_html(
            customer_name=customer_name,
            booking_id=job_id,
            amount=amount,
            payment_method_last4=payment_method_last4,
            date=date,
        )

        return send_email(to_email, subject, html)
    except Exception:
        logger.exception("Failed in send_payment_receipt_email for %s", to_email)
        return None


# ---------------------------------------------------------------------------
# Welcome email (new user registration)
# ---------------------------------------------------------------------------
def send_welcome_email(to_email, user_name):
    """Send a welcome email to a newly registered user. Never raises."""
    try:
        subject = "Welcome to Umuve!"

        html = welcome_html(name=user_name)

        return send_email(to_email, subject, html)
    except Exception:
        logger.exception("Failed in send_welcome_email for %s", to_email)
        return None


# ---------------------------------------------------------------------------
# Password reset email
# ---------------------------------------------------------------------------
def send_password_reset_email(to_email, reset_token, customer_name=None):
    """Send a password reset email. Never raises.

    Backward compatible: ``reset_token`` can be a raw token string (legacy
    callers pass just a token) or a full URL.  If it does not look like a
    URL the template builds one automatically.  ``customer_name`` is optional.
    """
    try:
        subject = "Reset Your Umuve Password"

        # Build a reset URL if the caller passed a bare token
        if reset_token and not str(reset_token).startswith("http"):
            base = os.environ.get("FRONTEND_URL", "https://goumuve.com")
            reset_url = "{}/reset-password?token={}".format(base.rstrip("/"), reset_token)
        else:
            reset_url = str(reset_token) if reset_token else ""

        html = password_reset_html(
            name=customer_name,
            reset_url=reset_url,
        )

        return send_email(to_email, subject, html)
    except Exception:
        logger.exception("Failed in send_password_reset_email for %s", to_email)
        return None


# ---------------------------------------------------------------------------
# Push notification (delegates to push_notifications.py APNs sender)
# ---------------------------------------------------------------------------
def send_push_notification(user_id, title, body, data=None, category=None):
    """Send a push notification to a user's device(s) via APNs.

    Delegates to push_notifications.send_push_notification which queries
    DeviceToken and sends real APNs pushes via HTTP/2.
    Never raises.
    """
    try:
        from push_notifications import send_push_notification as _send_apns
        return _send_apns(user_id, title, body, data=data, category=category)
    except Exception:
        logger.exception("Failed in send_push_notification for user %s", user_id)
        return None


# ---------------------------------------------------------------------------
# Job status update email (generic — covers assigned, en_route, arrived, etc.)
# ---------------------------------------------------------------------------
def send_job_status_update_email(to_email, customer_name, job_id, status, driver_name=None):
    """Email customer a generic job status update. Never raises."""
    try:
        status_lower = (status or "").lower()
        subject = "Umuve Job Update — {}".format(status_lower.replace("_", " ").title())

        html = job_status_update_html(
            customer_name=customer_name,
            job_id=job_id,
            status=status,
            driver_name=driver_name,
        )

        return send_email(to_email, subject, html)
    except Exception:
        logger.exception("Failed in send_job_status_update_email for %s", to_email)
        return None


# ---------------------------------------------------------------------------
# Pickup reminder email (24h before scheduled pickup)
# ---------------------------------------------------------------------------
def send_pickup_reminder_email(to_email, customer_name, job_id, address,
                                scheduled_date, scheduled_time):
    """Email customer a 24-hour pickup reminder. Never raises."""
    try:
        subject = "Umuve Pickup Reminder — Tomorrow!"

        html = pickup_reminder_html(
            customer_name=customer_name,
            job_id=job_id,
            address=address,
            date=scheduled_date,
            time=scheduled_time,
        )

        return send_email(to_email, subject, html)
    except Exception:
        logger.exception("Failed in send_pickup_reminder_email for %s", to_email)
        return None


# ---------------------------------------------------------------------------
# Abandoned booking drip emails
# ---------------------------------------------------------------------------
def send_abandoned_booking_reminder(to_email, customer_name, booking_url):
    """Send a 2-hour abandoned booking reminder email. Never raises."""
    try:
        subject = "You left something behind!"
        html = abandoned_booking_reminder_html(
            customer_name=customer_name,
            booking_url=booking_url,
        )
        return send_email(to_email, subject, html)
    except Exception:
        logger.exception("Failed in send_abandoned_booking_reminder for %s", to_email)
        return None


def send_abandoned_booking_incentive(to_email, customer_name, booking_url, promo_code):
    """Send a 24-hour abandoned booking incentive email with promo code. Never raises."""
    try:
        subject = "Here's 10% off to finish your booking"
        html = abandoned_booking_incentive_html(
            customer_name=customer_name,
            booking_url=booking_url,
            promo_code=promo_code,
        )
        return send_email(to_email, subject, html)
    except Exception:
        logger.exception("Failed in send_abandoned_booking_incentive for %s", to_email)
        return None


def send_abandoned_booking_final(to_email, customer_name, booking_url):
    """Send a 72-hour final abandoned booking email. Never raises."""
    try:
        subject = "We saved your spot"
        html = abandoned_booking_final_html(
            customer_name=customer_name,
            booking_url=booking_url,
        )
        return send_email(to_email, subject, html)
    except Exception:
        logger.exception("Failed in send_abandoned_booking_final for %s", to_email)
        return None
