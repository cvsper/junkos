"""Every booking gets announced, on every channel that is configured.

Why this exists: job AFB22IMO ($307.80, Davie) was booked, assigned to a
hauler, and then sat untouched for 18 days — never started, never completed,
no photos. Nobody found out until the owner happened to scroll past it. The
booking path did have an internal heads-up, but it was a single SMS to one
optional env var (``OPERATOR_PHONE``) wrapped in a bare ``except: pass``, so
if that variable was unset or Twilio hiccuped, the booking was silent and
nothing said so.

The rules here:
  * fan out to EVERY configured channel (SMS, email, Slack, in-app) — one
    misconfiguration must not swallow the announcement;
  * if NOTHING is configured, log at error level, because "no alert" and
    "nothing to alert about" must never look the same;
  * never raise into the booking path — a failed notification must not cost
    the customer their booking;
  * announce twice, because they mean different things: ``booked`` (created,
    money not captured yet) and ``paid`` (real work now owed to someone).

Channels, all optional and independent:
  ADMIN_PHONE / OPERATOR_PHONE   SMS
  ADMIN_EMAIL                    email
  SLACK_ALERT_WEBHOOK            Slack
  admin + manager users          in-app Notification rows
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

STAGES = {
    "booked": "NEW BOOKING (awaiting payment)",
    "paid": "BOOKING PAID — needs a hauler",
}


def _env(name):
    return (os.environ.get(name) or "").strip()


def _phones():
    """Every distinct number worth telling. Order is stable for tests."""
    out = []
    for var in ("ADMIN_PHONE", "OPERATOR_PHONE"):
        val = _env(var)
        if val and val not in out:
            out.append(val)
    return out


def _job_lines(job, payment=None):
    """Human summary. Guarded field-by-field so a sparse job still alerts."""
    from timeutils import local_date_str

    code = getattr(job, "confirmation_code", None) or str(getattr(job, "id", ""))[:8]
    address = getattr(job, "address", None) or "no address on file"
    try:
        items = getattr(job, "items", None) or []
        count = sum(int(i.get("quantity", 1) or 1) for i in items if isinstance(i, dict))
    except Exception:
        count = 0
    try:
        total = float(getattr(job, "total_price", 0) or 0)
    except Exception:
        total = 0.0
    when = local_date_str(getattr(job, "scheduled_at", None), "ASAP")
    lines = [
        "{} · ${:.2f}".format(code, total),
        address,
        "{} item{} · scheduled {}".format(count, "" if count == 1 else "s", when),
    ]
    src = getattr(job, "lead_source", None)
    if src:
        lines.append("source: {}".format(src))
    if payment is not None:
        status = getattr(payment, "payment_status", None)
        if status:
            lines.append("payment: {}".format(status))
    return code, lines


def notify_booking(job, stage="booked", payment=None):
    """Announce a booking everywhere. Never raises. Returns the channels used."""
    sent = []
    try:
        headline = STAGES.get(stage, STAGES["booked"])
        code, lines = _job_lines(job, payment)
        subject = "{} · {}".format(headline, code)
        body = "\n".join([headline] + lines)

        for phone in _phones():
            try:
                from sms_service import send_sms_async
                send_sms_async(phone, body)
                sent.append("sms:" + phone[-4:])
            except Exception:
                logger.exception("booking alert SMS to %s failed for job %s", phone[-4:], code)

        if _env("ADMIN_EMAIL"):
            try:
                from notifications import _send_email_sync
                _send_email_sync(_env("ADMIN_EMAIL"), subject,
                                 "<pre style='font:13px/1.5 monospace'>{}</pre>".format(body))
                sent.append("email")
            except Exception:
                logger.exception("booking alert email failed for job %s", code)

        hook = _env("SLACK_ALERT_WEBHOOK")
        if hook:
            try:
                import requests
                requests.post(hook, json={"text": "*{}*\n```{}```".format(subject, body)}, timeout=10)
                sent.append("slack")
            except Exception:
                logger.exception("booking alert slack failed for job %s", code)

        try:
            from models import db, User, Notification, generate_uuid
            staff = User.query.filter(User.role.in_(("admin", "manager"))).all()
            for person in staff:
                db.session.add(Notification(
                    id=generate_uuid(), user_id=person.id, type="booking",
                    title=subject, body="\n".join(lines)[:900],
                    data={"job_id": getattr(job, "id", None), "stage": stage},
                ))
            if staff:
                db.session.commit()
                sent.append("inapp:{}".format(len(staff)))
        except Exception:
            logger.exception("booking alert in-app notification failed for job %s", code)

        if not sent:
            # The failure this module exists to prevent: a booking nobody hears
            # about. Silence must be loud in the logs.
            logger.error(
                "BOOKING %s (%s) ANNOUNCED TO NOBODY — set ADMIN_PHONE, ADMIN_EMAIL or "
                "SLACK_ALERT_WEBHOOK, or bookings will keep going unnoticed", code, stage,
            )
        else:
            logger.info("booking %s (%s) announced via %s", code, stage, ", ".join(sent))
    except Exception:
        logger.exception("booking alert crashed (booking itself is unaffected)")
    return sent
