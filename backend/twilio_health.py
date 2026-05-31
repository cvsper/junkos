"""
Twilio account health probe.

Catches the silent-failure class that took down ALL outbound SMS once: a Twilio
billing suspension (error 20003) makes every messages.create() return HTTP 401,
which send_sms() swallows — so alerts, broadcast offers, no-show texts, and
post-call follow-ups all stop delivering with zero visible signal.

This probes the account with a read-only GET (no SMS, no charge) and, on
failure, alerts by EMAIL. Email is deliberate: it does NOT depend on Twilio, so
it still reaches sevs even when Twilio itself is the thing that's down.

Run standalone (cron) or via the scheduler:
    python twilio_health.py
"""

import os
import logging
import json

import requests

logger = logging.getLogger(__name__)

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"


def check_twilio_health():
    """Probe the Twilio account. Returns a dict; never raises.

    {
      "configured": bool,     # are creds even set?
      "ok": bool,             # account reachable AND active
      "http_status": int|None,
      "account_status": str|None,   # 'active' | 'suspended' | 'closed' | ...
      "code": int|None,             # Twilio error code (e.g. 20003) on failure
      "message": str,
    }
    """
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")

    if not sid or not token:
        return {
            "configured": False, "ok": False, "http_status": None,
            "account_status": None, "code": None,
            "message": "TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN not configured",
        }

    url = "{}/Accounts/{}.json".format(TWILIO_API_BASE, sid)

    try:
        resp = requests.get(url, auth=(sid, token), timeout=15)
    except Exception as e:
        logger.exception("Twilio health probe failed to reach the API")
        return {
            "configured": True, "ok": False, "http_status": None,
            "account_status": None, "code": None,
            "message": "Could not reach Twilio API: {}".format(e),
        }

    try:
        body = resp.json()
    except Exception:
        body = {}

    if resp.status_code == 200:
        acct_status = body.get("status")
        ok = acct_status == "active"
        return {
            "configured": True, "ok": ok, "http_status": 200,
            "account_status": acct_status, "code": None,
            "message": (
                "Account active" if ok
                else "Account reachable but status='{}'".format(acct_status)
            ),
        }

    # Non-200 — 401 here is almost always a suspended account (20003) or bad creds.
    code = body.get("code")
    msg = "HTTP {} — Twilio {} ({})".format(
        resp.status_code, code, body.get("message", "")) if code else "HTTP {}".format(resp.status_code)
    return {
        "configured": True, "ok": False, "http_status": resp.status_code,
        "account_status": None, "code": code, "message": msg,
    }


def _alert_admin_twilio_down(result):
    """Email the admin that Twilio is down. Email only — it must not depend on
    the very channel that's failing. Never raises.
    """
    admin_email = os.environ.get("ADMIN_EMAIL", "")
    if not admin_email:
        logger.error(
            "TWILIO DOWN (%s) but no ADMIN_EMAIL configured — cannot alert. "
            "ALL outbound SMS is failing.", result.get("message"),
        )
        return

    hint = ""
    if result.get("code") == 20003 or result.get("http_status") == 401:
        hint = (
            "<p><b>Most likely cause:</b> the Twilio account is <b>suspended</b> "
            "(unpaid balance / billing hold). Error 20003 = auth refused on a "
            "suspended account. Fix: log into console.twilio.com, clear any "
            "balance/suspension, and SMS resumes automatically.</p>"
        )

    try:
        from email_service import send_email_async
        send_email_async(
            admin_email,
            "🚨 umuve — Twilio is DOWN, all SMS is failing",
            (
                "<h2>Outbound SMS is not being delivered</h2>"
                "<p>The Twilio account health check failed. Until this is fixed, "
                "no-show alerts, broadcast job offers, hauler-application pings, "
                "and customer texts are <b>silently not sending</b>.</p>"
                "{hint}"
                "<table cellpadding='6' style='font-family:sans-serif;font-size:14px'>"
                "<tr><td><b>Status</b></td><td>{msg}</td></tr>"
                "<tr><td><b>HTTP</b></td><td>{http}</td></tr>"
                "<tr><td><b>Twilio code</b></td><td>{code}</td></tr>"
                "</table>"
                "<p>This alert came by email on purpose — SMS can't be trusted "
                "to reach you while Twilio is the thing that's down.</p>"
            ).format(
                hint=hint,
                msg=result.get("message", "unknown"),
                http=result.get("http_status", "—"),
                code=result.get("code", "—"),
            ),
        )
        logger.info("Sent Twilio-down email alert to %s", admin_email)
    except Exception:
        logger.exception("Failed to send Twilio-down email alert")


def run_twilio_health_check(alert=True):
    """Probe Twilio; alert by email if down. Returns the result dict. Never raises."""
    result = check_twilio_health()
    if not result["configured"]:
        logger.info("Twilio health check skipped — creds not configured.")
        return result
    if result["ok"]:
        logger.info("Twilio health OK — account active.")
    else:
        logger.error("TWILIO HEALTH FAILED: %s", result["message"])
        if alert:
            _alert_admin_twilio_down(result)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    r = run_twilio_health_check()
    print(json.dumps(r, indent=2))
    raise SystemExit(0 if r["ok"] or not r["configured"] else 1)
