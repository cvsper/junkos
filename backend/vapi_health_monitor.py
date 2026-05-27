"""
Vapi call-health monitor — Tier 2-D of the airtight stack.

Runs hourly. Reads the VoiceCall log for the last 4 hours and computes a
"failed call" signal — calls that look like Maya hung up on the customer
without resolving the issue. If the signal trips a threshold, fires the
URGENT admin alert.

What counts as a "failed" call (heuristic — any of):
  - duration_s < 25 s and no VoiceCallOutcome was created (talked briefly
    and the line dropped before Maya could resolve, transfer, or take a
    message)
  - status in ("failed", "no-answer", "busy")

Thresholds (defaults; tune via env):
  - >= 30% failed AND >= 5 total calls in window → alert
  - 3 consecutive failed calls → alert (the "Sy pattern": same person
    called 3 times in a row and Maya hung up each time)

Usage:
    python vapi_health_monitor.py
    # Render cron (hourly):
    7 * * * *  cd /app && python vapi_health_monitor.py

Designed so it cannot cry wolf: when there's little traffic, low counts
short-circuit the alert. When there's bursty traffic, the consecutive-fail
signal still catches the Sy pattern.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

WINDOW_HOURS = int(os.environ.get("VAPI_HEALTH_WINDOW_HOURS", "4"))
MIN_CALLS_FOR_RATE_CHECK = int(os.environ.get("VAPI_HEALTH_MIN_CALLS", "5"))
FAILED_RATE_THRESHOLD = float(os.environ.get("VAPI_HEALTH_FAILED_RATE", "0.30"))
CONSECUTIVE_FAIL_THRESHOLD = int(os.environ.get("VAPI_HEALTH_CONSEC_FAIL", "3"))

SHORT_CALL_S = 25  # under this and no outcome → counts as failed


def _is_failed(call):
    """Heuristic for whether this call looks like a Maya hang-up / failure."""
    status = (call.status or "").lower()
    if status in ("failed", "no-answer", "noanswer", "busy", "canceled", "cancelled"):
        return True

    # Short call with no outcome record → almost certainly a dropped call
    duration = call.duration_s or 0
    if 0 < duration < SHORT_CALL_S and not call.outcome_id:
        return True

    return False


def check_call_health():
    """Run the call-health check inside the Flask app context."""
    from server import app
    with app.app_context():
        from models import VoiceCall

        now = datetime.now(timezone.utc)
        window_start = now - timedelta(hours=WINDOW_HOURS)

        calls = (
            VoiceCall.query
            .filter(VoiceCall.started_at >= window_start)
            .order_by(VoiceCall.started_at.asc())
            .all()
        )

        if not calls:
            logger.info("No calls in last %dh — nothing to evaluate.", WINDOW_HOURS)
            return None

        total = len(calls)
        failed = [c for c in calls if _is_failed(c)]
        failed_count = len(failed)
        rate = failed_count / total if total else 0.0

        # Consecutive-failure streak (only the tail matters — newest first)
        consecutive = 0
        for c in reversed(calls):
            if _is_failed(c):
                consecutive += 1
            else:
                break

        logger.info(
            "Vapi health: total=%d failed=%d rate=%.0f%% consecutive=%d (window=%dh)",
            total, failed_count, rate * 100, consecutive, WINDOW_HOURS,
        )

        # Decide whether to alert
        alert_reasons = []
        if total >= MIN_CALLS_FOR_RATE_CHECK and rate >= FAILED_RATE_THRESHOLD:
            alert_reasons.append(
                "{:.0f}% failed-call rate ({}/{}) in last {}h".format(
                    rate * 100, failed_count, total, WINDOW_HOURS,
                )
            )
        if consecutive >= CONSECUTIVE_FAIL_THRESHOLD:
            alert_reasons.append(
                "{} consecutive failed calls — the 'Maya hangs up' pattern".format(
                    consecutive,
                )
            )

        if not alert_reasons:
            return None

        _send_health_alert(alert_reasons, total, failed_count, consecutive, calls[-5:])
        return alert_reasons


def _send_health_alert(reasons, total, failed_count, consecutive, last_calls):
    """Dual-channel alert that the support line itself looks broken."""
    admin_phone = os.environ.get("ADMIN_PHONE", "")
    admin_email = os.environ.get("ADMIN_EMAIL", "")

    if not admin_phone and not admin_email:
        logger.error(
            "Vapi-health alert fired (%s) but NO ADMIN_PHONE/ADMIN_EMAIL — "
            "cannot deliver. Reasons: %s",
            "; ".join(reasons), reasons,
        )
        return

    reason_text = " AND ".join(reasons)

    if admin_phone:
        try:
            from sms_service import send_sms_async
            sms_body = (
                "🚨 umuve SUPPORT-LINE HEALTH: {} "
                "(total {} calls, {} looked dropped). "
                "Check Vapi dashboard — Maya may be hanging up."
            ).format(reason_text, total, failed_count)
            send_sms_async(admin_phone, sms_body)
        except Exception:
            logger.exception("Failed to SMS Vapi-health alert")

    if admin_email:
        try:
            from email_service import send_email_async
            last_call_rows = "".join((
                "<tr><td>{started}</td><td>{caller}</td>"
                "<td>{dur}s</td><td>{status}</td></tr>"
            ).format(
                started=c.started_at.strftime("%H:%M:%S") if c.started_at else "?",
                caller=c.caller_number or "?",
                dur=c.duration_s or "?",
                status=c.status or "?",
            ) for c in last_calls)

            html = (
                "<h2>🚨 Vapi support-line health alert</h2>"
                "<p><b>{reason}</b></p>"
                "<p>Total calls in last {hrs}h: {total} • Failed-pattern: "
                "{failed} • Most recent consecutive failures: {consec}</p>"
                "<h3>Last 5 calls</h3>"
                "<table cellpadding='6' style='font-family:sans-serif;font-size:13px;"
                "border-collapse:collapse'>"
                "<thead><tr style='background:#f5f5f5'>"
                "<th align='left'>Started</th><th align='left'>Caller</th>"
                "<th align='left'>Duration</th><th align='left'>Status</th>"
                "</tr></thead><tbody>{rows}</tbody></table>"
                "<p style='margin-top:16px'><b>Action:</b> open the Vapi dashboard "
                "→ Recent Calls → listen to the latest few to confirm whether "
                "Maya is hanging up, looping, or hitting a tool error.</p>"
            ).format(
                reason=reason_text, hrs=WINDOW_HOURS, total=total,
                failed=failed_count, consec=consecutive,
                rows=last_call_rows,
            )
            send_email_async(
                admin_email,
                "🚨 umuve — Vapi support-line health alert",
                html,
            )
        except Exception:
            logger.exception("Failed to email Vapi-health alert")


def main():
    logger.info("=" * 60)
    logger.info("Vapi health check starting")
    logger.info("=" * 60)
    reasons = check_call_health()
    if reasons:
        logger.warning("ALERT FIRED: %s", "; ".join(reasons))
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
