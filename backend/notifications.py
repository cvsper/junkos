"""
Notification services for JunkOS.
Twilio SMS for phone verification, SendGrid for booking confirmations.
"""

import os


# ---------------------------------------------------------------------------
# Twilio SMS
# ---------------------------------------------------------------------------
_twilio_client = None

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER", "")


def _get_twilio():
    global _twilio_client
    if _twilio_client is None and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        from twilio.rest import Client
        _twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    return _twilio_client


def send_sms(to_number, body):
    """Send an SMS via Twilio. Returns message SID or None in dev mode."""
    client = _get_twilio()
    if not client or not TWILIO_FROM_NUMBER:
        print("[DEV] SMS to {}: {}".format(to_number, body))
        return None

    message = client.messages.create(
        body=body,
        from_=TWILIO_FROM_NUMBER,
        to=to_number,
    )
    return message.sid


def send_verification_sms(phone_number, code):
    """Send a verification code via SMS."""
    body = "Your JunkOS verification code is: {}. It expires in 10 minutes.".format(code)
    return send_sms(phone_number, body)


def send_booking_sms(phone_number, booking_id, scheduled_date, address):
    """Send booking confirmation via SMS."""
    body = (
        "JunkOS Booking Confirmed!\n"
        "Booking: #{}\n"
        "Date: {}\n"
        "Address: {}\n\n"
        "We'll send a reminder 24h before your pickup."
    ).format(booking_id[:8], scheduled_date, address)
    return send_sms(phone_number, body)


# ---------------------------------------------------------------------------
# SendGrid Email
# ---------------------------------------------------------------------------
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
SENDGRID_FROM_EMAIL = os.environ.get("SENDGRID_FROM_EMAIL", "bookings@junkos.com")
SENDGRID_FROM_NAME = os.environ.get("SENDGRID_FROM_NAME", "JunkOS")


def send_email(to_email, subject, html_content):
    """Send an email via SendGrid. Returns status code or None in dev mode."""
    if not SENDGRID_API_KEY:
        print("[DEV] Email to {}: {} - {}".format(to_email, subject, html_content[:100]))
        return None

    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail

    message = Mail(
        from_email=(SENDGRID_FROM_EMAIL, SENDGRID_FROM_NAME),
        to_emails=to_email,
        subject=subject,
        html_content=html_content,
    )

    sg = SendGridAPIClient(SENDGRID_API_KEY)
    response = sg.send(message)
    return response.status_code


def send_booking_confirmation_email(to_email, customer_name, booking_id, address,
                                     scheduled_date, scheduled_time, total_amount):
    """Send a booking confirmation email."""
    subject = "Your JunkOS Booking is Confirmed! #{}".format(booking_id[:8])

    html = """
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #fafaf8; padding: 40px 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #2d8a6e; font-size: 28px; margin: 0;">JunkOS</h1>
            <p style="color: #6b7280; margin: 5px 0 0;">Premium Junk Removal</p>
        </div>

        <div style="background: white; border-radius: 12px; padding: 30px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            <h2 style="color: #111827; margin-top: 0;">Booking Confirmed!</h2>
            <p style="color: #4b5563;">Hi {name},</p>
            <p style="color: #4b5563;">Your junk removal is scheduled. Here are your details:</p>

            <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 20px; margin: 20px 0;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0; color: #6b7280; font-size: 14px;">Booking ID</td>
                        <td style="padding: 8px 0; color: #111827; font-weight: 600; text-align: right;">#{id}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #6b7280; font-size: 14px;">Address</td>
                        <td style="padding: 8px 0; color: #111827; font-weight: 600; text-align: right;">{address}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #6b7280; font-size: 14px;">Date</td>
                        <td style="padding: 8px 0; color: #111827; font-weight: 600; text-align: right;">{date}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #6b7280; font-size: 14px;">Time</td>
                        <td style="padding: 8px 0; color: #111827; font-weight: 600; text-align: right;">{time}</td>
                    </tr>
                    <tr style="border-top: 1px solid #d1fae5;">
                        <td style="padding: 12px 0 0; color: #111827; font-size: 16px; font-weight: 700;">Total</td>
                        <td style="padding: 12px 0 0; color: #2d8a6e; font-size: 20px; font-weight: 700; text-align: right;">${total}</td>
                    </tr>
                </table>
            </div>

            <p style="color: #4b5563; font-size: 14px;">We'll send you a reminder 24 hours before your appointment. If you need to reschedule, just reply to this email or call us at <strong>(561) 888-3427</strong>.</p>
        </div>

        <div style="text-align: center; margin-top: 30px; color: #9ca3af; font-size: 12px;">
            <p>JunkOS - South Florida's Premium Junk Removal</p>
            <p>Palm Beach & Broward County</p>
        </div>
    </div>
    """.format(
        name=customer_name or "there",
        id=booking_id[:8],
        address=address,
        date=scheduled_date,
        time=scheduled_time,
        total="{:.2f}".format(total_amount),
    )

    return send_email(to_email, subject, html)


def send_password_reset_email(to_email, reset_token):
    """Send a password reset email."""
    subject = "Reset Your JunkOS Password"

    html = """
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #fafaf8; padding: 40px 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #2d8a6e; font-size: 28px; margin: 0;">JunkOS</h1>
        </div>
        <div style="background: white; border-radius: 12px; padding: 30px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            <h2 style="color: #111827; margin-top: 0;">Password Reset</h2>
            <p style="color: #4b5563;">You requested a password reset. Use the code below to reset your password:</p>
            <div style="background: #f3f4f6; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0;">
                <code style="font-size: 24px; font-weight: 700; color: #111827; letter-spacing: 2px;">{token}</code>
            </div>
            <p style="color: #6b7280; font-size: 14px;">This link expires in 1 hour. If you didn't request this, you can safely ignore this email.</p>
        </div>
    </div>
    """.format(token=reset_token)

    return send_email(to_email, subject, html)
