"""Who a call reaches, and who gets told about it — two different things.

Maya's prompt told her to transfer both routine questions AND complaints to a
hardcoded personal mobile, and three operator-alert paths fell back to that
same number when ``OPERATOR_PHONE`` was unset. So an angry customer calling
the published line was connected directly to the owner's cell, and there was
no way to change that without editing code.

The distinction this module enforces:

``human_line()``   A number PEOPLE are connected to or told to call. It must
                   be a business line that somebody staffs — the desk line.
                   Never a personal mobile, and never a silent fallback: if
                   it isn't configured, callers stay with the assistant or go
                   to voicemail rather than being pushed at someone's phone.

``alert_phone()``  A private number that RECEIVES one-way notifications. It is
                   never published, never dialled into, never handed to a
                   customer or hauler. Returns "" when unset so callers log
                   the gap instead of defaulting to whoever was hardcoded.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_warned = set()


def _warn_once(key, msg, *args):
    if key not in _warned:
        _warned.add(key)
        logger.warning(msg, *args)


def _clean(value):
    return (value or "").strip()


def human_line():
    """The staffed business line a caller may be transferred to. "" if none."""
    for var in ("DESK_TWILIO_NUMBER", "PUBLIC_PHONE_NUMBER", "TWILIO_FROM_NUMBER"):
        val = _clean(os.environ.get(var))
        if val:
            return val
    _warn_once(
        "human_line",
        "No staffed line configured (DESK_TWILIO_NUMBER) — transfers will be "
        "declined rather than routed to a personal phone.",
    )
    return ""


def alert_phone():
    """Private number for one-way operational alerts. "" if none configured."""
    for var in ("ALERT_PHONE", "ADMIN_PHONE", "OPERATOR_PHONE"):
        val = _clean(os.environ.get(var))
        if val:
            return val
    _warn_once(
        "alert_phone",
        "No ALERT_PHONE/ADMIN_PHONE set — operational SMS alerts are going "
        "nowhere. Set one, or rely on email and the desk inbox.",
    )
    return ""


def alert_sms(message, why=""):
    """Send a one-way operational alert. Never raises. True if it went out."""
    to = alert_phone()
    if not to:
        logger.warning("operational alert not sent (no alert phone configured): %s", why or message[:80])
        return False
    try:
        from sms_service import send_sms_async
        send_sms_async(to, message)
        return True
    except Exception:
        logger.exception("operational alert SMS failed: %s", why or "")
        return False
