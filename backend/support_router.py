"""
Support-SMS router — Vapi-independent backup channel.

Tier 1-B of the airtight stack: when a customer in distress texts the Umuve
number, this module detects it and forwards directly to ADMIN_PHONE +
ADMIN_EMAIL, bypassing Vapi entirely. The point is to have ONE escalation
path that does not depend on the AI line working — single failure mode, no
AI in the middle, no transfer logic to fail.

Wired into routes/sms_webhook.inbound_sms() BEFORE the Vapi forward step.

Never raises — every failure is logged and the caller-facing flow continues
to its normal Vapi/keyword fallback.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


# Phrases that indicate a customer is having a problem, not casual chit-chat.
# Kept deliberately broad — false positives cost sevs a forwarded SMS, false
# negatives cost a bad review or chargeback. Bias is to over-forward.
SUPPORT_TRIGGER_PHRASES = (
    "help",
    "issue",
    "problem",
    "complaint",
    "refund",
    "missed",
    "no show",
    "no-show",
    "noshow",
    "didn't show",
    "didnt show",
    "nobody came",
    "no one came",
    "nobody showed",
    "no one showed",
    "where is",
    "where's my",
    "wheres my",
    "still waiting",
    "urgent",
    "frustrat",  # frustrated, frustrating
    "angry",
    "upset",
    "disappoint",
    "broken",
    "damaged",
    "stole",
    "cancel my",
    "speak to",
    "talk to someone",
    "talk to a person",
    "talk to a human",
    "manager",
    "owner",
    "dispute",
    "chargeback",
    "scam",
    "rip off",
    "ripoff",
    "lawyer",
    "review",  # often "I will leave a review"
    "1 star",
    "bad service",
    "terrible",
    "worst",
    "never again",
)


def is_support_request(body, from_phone=None):
    """Return True if this inbound SMS looks like a customer in trouble.

    Two signals (either is enough):
      1. Body contains a known support-trigger phrase (case-insensitive).
      2. Sender has a Job scheduled within ±24h and current status is still
         pending/confirmed/accepted/assigned (i.e. unresolved real-world job
         — the texter is likely chasing it).

    Phrase check is fast/local. Job-correlation check tries the DB but
    fails-open (returns False) if the lookup errors.
    """
    if not body:
        return False

    lower = body.lower()
    for phrase in SUPPORT_TRIGGER_PHRASES:
        if phrase in lower:
            return True

    # Heuristic 2: this sender has an open job — they're probably chasing it
    if from_phone:
        try:
            from models import db, Job, User  # noqa: F401
            now = datetime.now(timezone.utc)
            window_start = now - timedelta(hours=24)
            window_end = now + timedelta(hours=24)

            user = User.query.filter_by(phone=from_phone).first()
            if user is None:
                # Normalize: try with/without leading +1
                stripped = from_phone.lstrip("+").lstrip("1")
                user = (
                    User.query.filter(User.phone.like("%" + stripped)).first()
                )
            if user is not None:
                open_job = Job.query.filter(
                    Job.customer_id == user.id,
                    Job.scheduled_at >= window_start,
                    Job.scheduled_at <= window_end,
                    Job.status.in_((
                        "pending", "confirmed", "accepted", "assigned", "in_progress",
                    )),
                ).first()
                if open_job is not None:
                    return True
        except Exception:
            logger.exception(
                "Support-request job-correlation check errored for %s",
                from_phone,
            )

    return False


def forward_to_admin(from_phone, body):
    """SMS + email the inbound message straight to the owner.

    Fires on both channels independently. Never raises. Returns True if at
    least one channel was attempted, False if no admin contact is configured.
    """
    admin_phone = os.environ.get("ADMIN_PHONE", "")
    admin_email = os.environ.get("ADMIN_EMAIL", "")

    if not admin_phone and not admin_email:
        logger.error(
            "Support SMS from %s but NO ADMIN_PHONE/ADMIN_EMAIL configured — "
            "message will be invisible to operator. Body: %r",
            from_phone, body[:200],
        )
        return False

    body_snippet = (body or "")[:280]

    if admin_phone:
        try:
            from sms_service import send_sms_async
            sms_body = (
                "📩 umuve SUPPORT TEXT from {}:\n\n{}\n\n"
                "Reply directly to the customer's number to respond."
            ).format(from_phone or "unknown", body_snippet)
            send_sms_async(admin_phone, sms_body)
        except Exception:
            logger.exception("Failed to forward support SMS to admin phone")

    if admin_email:
        try:
            from email_service import send_email_async
            subject = "📩 umuve support text from {}".format(
                from_phone or "unknown",
            )
            html = (
                "<h2>Inbound support text</h2>"
                "<p><b>This bypassed the AI line and came in as a direct SMS.</b> "
                "Treat it as a customer trying to reach a human. Reply to their "
                "number directly.</p>"
                "<table cellpadding='6' style='font-family:sans-serif;font-size:14px'>"
                "<tr><td><b>From</b></td><td>{phone}</td></tr>"
                "<tr><td><b>Message</b></td>"
                "<td style='white-space:pre-wrap'>{body}</td></tr>"
                "<tr><td><b>Received</b></td><td>{when}</td></tr>"
                "</table>"
            ).format(
                phone=from_phone or "unknown",
                body=body or "(empty)",
                when=datetime.now(timezone.utc).isoformat(),
            )
            send_email_async(admin_email, subject, html)
        except Exception:
            logger.exception("Failed to email support text to admin")

    return True
