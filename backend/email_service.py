"""
Umuve Email Service

Centralised email sending via SendGrid with:
- Asynchronous sending (background threads)
- HTML templates with Umuve branding (#DC2626)
- Never-raise patterns for stability

IMPORTANT: No function in this module should ever raise an exception.
All errors are caught and logged to ensure email failures never block 
the core booking or payment flow.
"""

import os
import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SendGrid configuration (lazy-initialised)
# ---------------------------------------------------------------------------
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
DEFAULT_FROM_EMAIL = "bookings@goumuve.com"
UMUVE_LOGO_URL = "https://goumuve.com/logo-full.png"
UMUVE_RED = "#DC2626"

_sg_client = None

def _get_sg():
    """Lazily initialise the SendGrid client."""
    global _sg_client
    if _sg_client is None and SENDGRID_API_KEY:
        try:
            from sendgrid import SendGridAPIClient
            _sg_client = SendGridAPIClient(SENDGRID_API_KEY)
        except Exception:
            logger.exception("Failed to initialise SendGrid client")
    return _sg_client

# ---------------------------------------------------------------------------
# Core send function
# ---------------------------------------------------------------------------
def send_email(to_email, subject, html_content):
    """Send an email via SendGrid.

    If credentials are missing, logs the attempt at INFO level.
    Never raises.
    """
    try:
        if not to_email:
            logger.warning("send_email called with empty recipient")
            return False

        client = _get_sg()
        if not client:
            logger.info("[EMAIL-DEV] To: %s, Subject: %s", to_email, subject)
            return True

        from sendgrid.helpers.mail import Mail
        message = Mail(
            from_email=DEFAULT_FROM_EMAIL,
            to_emails=to_email,
            subject=subject,
            html_content=html_content
        )
        
        response = client.send(message)
        if response.status_code >= 200 and response.status_code < 300:
            logger.info("Email sent to %s (Status: %s)", to_email, response.status_code)
            return True
        else:
            logger.error("SendGrid failed to send email to %s: %s", to_email, response.body)
            return False

    except Exception:
        logger.exception("Failed to send email to %s", to_email)
        return False

def send_email_async(to_email, subject, html_content):
    """Send an email in a background thread."""
    try:
        if not to_email:
            return None
        t = threading.Thread(
            target=send_email,
            args=(to_email, subject, html_content),
            daemon=True,
        )
        t.start()
        return t
    except Exception:
        logger.exception("Failed to start background email thread for %s", to_email)
        return None

# ---------------------------------------------------------------------------
# HTML Template Wrapper
# ---------------------------------------------------------------------------
def _wrap_template(content):
    """Wrap content in Umuve's standard HTML template."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'DM Sans', sans-serif; color: #1f2937; line-height: 1.6; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ text-align: center; padding: 20px 0; border-bottom: 2px solid {UMUVE_RED}; }}
            .logo {{ width: 150px; }}
            .content {{ padding: 30px 0; }}
            .footer {{ text-align: center; font-size: 12px; color: #6b7280; padding: 20px 0; border-top: 1px solid #e5e7eb; }}
            .button {{ background-color: {UMUVE_RED}; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <img src="{UMUVE_LOGO_URL}" alt="Umuve" class="logo">
            </div>
            <div class="content">
                {content}
            </div>
            <div class="footer">
                &copy; {datetime.now().year} Umuve - Hauling made simple.<br>
                South Florida's fastest junk removal platform.
            </div>
        </div>
    </body>
    </html>
    """

# ---------------------------------------------------------------------------
# Lifecycle Email Helpers
# ---------------------------------------------------------------------------

def email_booking_confirmed(to_email, name, job_id, date, time, address):
    """Send booking confirmation email."""
    try:
        first_name = name.split()[0] if name else "there"
        short_id = str(job_id)[:8] if job_id else "N/A"
        
        content = f"""
        <h2>Booking Confirmed!</h2>
        <p>Hi {first_name},</p>
        <p>Your junk removal is confirmed. Our team will arrive at the scheduled time below.</p>
        <div style="background: #f9fafb; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <strong>Job ID:</strong> #{short_id}<br>
            <strong>Date:</strong> {date}<br>
            <strong>Time Window:</strong> {time}<br>
            <strong>Address:</strong> {address}
        </div>
        <p>Need to make changes? You can view your booking status anytime on your dashboard.</p>
        <p style="margin-top: 30px;">
            <a href="https://app.goumuve.com/dashboard" class="button">View Dashboard</a>
        </p>
        <p>Thanks for choosing Umuve!</p>
        """
        
        subject = f"Your Umuve pickup is confirmed - #{short_id}"
        return send_email_async(to_email, subject, _wrap_template(content))
    except Exception:
        logger.exception("email_booking_confirmed failed for %s", to_email)
        return None

def email_job_completed(to_email, name, job_id, amount, items):
    """Send job completion receipt."""
    try:
        first_name = name.split()[0] if name else "there"
        short_id = str(job_id)[:8] if job_id else "N/A"
        
        items_list = ""
        if items:
            items_list = "<p><strong>Items removed:</strong> " + ", ".join(items) + "</p>"

        content = f"""
        <h2>Job Completed Successfully!</h2>
        <p>Hi {first_name},</p>
        <p>Your pickup has been completed. Thank you for using Umuve for your junk removal needs.</p>
        <div style="background: #f9fafb; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <strong>Total Paid:</strong> ${float(amount):.2f}<br>
            <strong>Job ID:</strong> #{short_id}
            {items_list}
        </div>
        <p>We hope you're happy with the service! A review request will follow shortly.</p>
        <p>Have more junk? We're always here to help.</p>
        <p style="margin-top: 30px;">
            <a href="https://app.goumuve.com/book" class="button">Book Another Pickup</a>
        </p>
        """
        
        subject = f"Receipt for Umuve Job #{short_id}"
        return send_email_async(to_email, subject, _wrap_template(content))
    except Exception:
        logger.exception("email_job_completed failed for %s", to_email)
        return None

def email_follow_up(to_email, name):
    """Send 24-hour follow-up email."""
    try:
        first_name = name.split()[0] if name else "there"
        
        content = f"""
        <h2>How did we do?</h2>
        <p>Hi {first_name},</p>
        <p>It's been 24 hours since your Umuve pickup. We'd love to hear about your experience.</p>
        <p>Feedback helps us improve and ensures we're sending the best operators to our customers.</p>
        <p style="margin-top: 30px;">
            <a href="https://g.page/r/umuve/review" class="button">Leave a Review</a>
        </p>
        <p>If you had any issues, please reply to this email and our support team will get back to you immediately.</p>
        """
        
        subject = "How was your Umuve experience?"
        return send_email_async(to_email, subject, _wrap_template(content))
    except Exception:
        logger.exception("email_follow_up failed for %s", to_email)
        return None

def schedule_email_follow_up(to_email, name, delay_seconds=86400):
    """Schedule a follow-up email after a delay (default 24 hours)."""
    try:
        if not to_email:
            return
        timer = threading.Timer(
            delay_seconds,
            email_follow_up,
            args=[to_email, name],
        )
        timer.daemon = True
        timer.start()
        logger.info(
            "Scheduled follow-up email to %s in %d seconds",
            to_email, delay_seconds,
        )
    except Exception:
        logger.exception("schedule_email_follow_up failed for %s", to_email)
