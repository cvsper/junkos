"""The owner's reminder that the desk line is running short.

On 30 Sep 2026 the Twilio account ran dry. Nothing told anyone: the health
job emailed an address that isn't set, the Slack hook isn't set, and the desk
kept minting dialer tokens because that endpoint never asks Twilio. The first
sign was the VA's dial button not appearing the next morning.

This turns the runway number (twilio_capacity: days of calling left, from real
spend) into something that reaches a person:

  low    fewer than DESK_LOW_DAYS of calling left   → text + email + Slack + in-app
  empty  nothing left                               → same, worded as "off"
  ok     back above the mark after being low        → one "topped up" note

Rules that keep it from being noise:
  * one alert when the state changes, then one reminder a day while it stays
    low or empty (DESK_RUNWAY_NAG_HOURS, default 24);
  * the text goes to the private alert number (ALERT_PHONE / ADMIN_PHONE), never
    to a published line, and goes out first — while there is still balance to
    send it with; email and Slack follow because they don't need Twilio.

The desk health check calls this every 30 minutes with the fresh capacity read.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

STATE_KEY = "runway:state"
NAG_KEY = "runway:last_alert_at"
CONSOLE_URL = "https://console.twilio.com/us1/billing/manage-billing/billing-overview"


def _now():
    return datetime.now(timezone.utc)


def _nag_hours():
    try:
        return max(float(os.environ.get("DESK_RUNWAY_NAG_HOURS", "24") or 24), 1.0)
    except ValueError:
        return 24.0


def _state_of(cap):
    """ok | low | empty | unknown — the line's runway, not its reachability."""
    if not cap or not cap.get("configured"):
        return "unknown"
    if not cap.get("ok"):
        return "unknown"
    return cap.get("level") or "unknown"


def describe(cap, balance=None):
    """One plain sentence about how much line is left. Balance is included
    only here, for the owner — the desk itself never sees a dollar figure."""
    if not cap or not cap.get("ok"):
        return "Twilio isn't answering — the desk line may be suspended."
    days, minutes, texts = cap.get("days"), cap.get("minutes"), cap.get("texts")
    bits = []
    if days is not None:
        bits.append("about {} day{} of calling left".format(
            int(days) if float(days).is_integer() else days, "" if days == 1 else "s"))
    units = []
    if minutes is not None:
        units.append("{:,} min".format(minutes))
    if texts is not None:
        units.append("{:,} texts".format(texts))
    if units:
        bits.append("≈ " + " or ".join(units))
    if balance is not None:
        bits.append("${:.2f} on the account".format(float(balance)))
    return ", ".join(bits) if bits else "runway unknown"


def _message(state, cap, balance):
    what = describe(cap, balance)
    if state == "empty":
        return ("Umuve desk line is OFF — nothing left on Twilio. Calls and texts aren't going out. "
                "Top up now: " + CONSOLE_URL)
    if state == "low":
        return ("Umuve desk line is getting low: {}. Top up or turn on auto-recharge: {}"
                .format(what, CONSOLE_URL))
    return "Umuve desk line topped up: {}.".format(what)


def _send(subject, body):
    """Text first (needs Twilio, so go while there's balance), then the
    channels that don't. Never raises; returns the channels that took it."""
    sent = []
    try:
        from ops_contacts import alert_phone
        phone = alert_phone()
    except Exception:
        phone = ""
    if phone:
        try:
            from sms_service import send_sms
            if send_sms(phone, body):
                sent.append("sms")
        except Exception:
            logger.exception("runway alert text failed")
    else:
        logger.warning("desk runway alert: no ALERT_PHONE/ADMIN_PHONE set — nobody gets the text")
    try:
        from desk_health import _send_alert
        _send_alert(subject, body)
        sent.append("desk_health")
    except Exception:
        logger.exception("runway alert fan-out failed")
    return sent


def check_and_alert(cap, balance=None, alert=True):
    """Compare the runway with the last reading; alert on change, nag daily
    while short, note the recovery once. Returns a health-check style dict.
    Never raises."""
    from models import DeskSetting

    state = _state_of(cap)
    days = (cap or {}).get("days")
    level = (cap or {}).get("level")
    what = describe(cap, None)

    if state == "unknown":
        # Reachability is desk_health's twilio_account check; don't double-alert.
        return {"state": "warn", "reason": "runway unknown — " + what, "days": days, "level": level}

    prev = DeskSetting.get(STATE_KEY) or "unknown"
    last_raw = DeskSetting.get(NAG_KEY)
    try:
        last = datetime.fromisoformat(last_raw) if last_raw else None
        if last is not None and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
    except ValueError:
        last = None

    changed = state != prev
    short = state in ("low", "empty")
    due_again = short and last is not None and (_now() - last).total_seconds() >= _nag_hours() * 3600
    recovered = state == "ok" and prev in ("low", "empty")

    if changed:
        DeskSetting.put(STATE_KEY, state)

    if alert and (recovered or (short and (changed or due_again))):
        subject = {"empty": "🔴 Umuve desk line is OFF",
                   "low": "🟠 Umuve desk line is getting low"}.get(state, "🟢 Umuve desk line topped up")
        sent = _send(subject, _message(state, cap, balance))
        DeskSetting.put(NAG_KEY, _now().isoformat())
        logger.warning("desk runway %s (%s) → alerted via %s", state, what, ",".join(sent) or "nothing")

    health = {"ok": "ok", "low": "warn", "empty": "fail"}[state]
    reason = what if state == "ok" else (
        "OFF — nothing left, calls and texts stopped" if state == "empty" else "low — " + what)
    # Say whether the reminder has anywhere to go. This check is public, so
    # only the fact, never the number.
    try:
        from ops_contacts import alert_phone
        has_phone = bool(alert_phone())
    except Exception:
        has_phone = False
    if not has_phone:
        reason += " · no ALERT_PHONE/ADMIN_PHONE set, so the low-line text has nobody to go to"
        if health == "ok":
            health = "warn"
    return {"state": health, "reason": reason, "days": days, "level": level, "text_alerts": has_phone}
