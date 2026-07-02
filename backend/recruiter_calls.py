"""
Maya Recruiter — outbound call driver (kill-switched).

Reads NEW DriverLead rows and places Vapi recruiting calls, one small batch at
a time, only inside a sane local calling window. A warm outcome is handled in
routes/vapi.py (_handle_recruiter_outcome), which auto-registers the hauler as
a concierge operator and texts the setup link.

SAFETY — this places real outbound phone calls to real businesses. It stays
fully dark until ALL of these are set on Render:
    RECRUITER_CALLS_ENABLED=true        # the master kill switch
    VAPI_API_KEY=...                    # already used by inbound Maya
    RECRUITER_ASSISTANT_ID=...          # from recruiter_assistant.py --create
    VAPI_PHONE_NUMBER_ID=...            # the Vapi outbound caller id
Absent any one of them, run_recruiter_calls() logs why and no-ops. Additional
guards: a per-run cap, a per-day cap, and a 9am-7pm ET calling window.
"""

import logging
import os
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

VAPI_CALL_URL = "https://api.vapi.ai/call/phone"

# Conservative defaults — tune via env.
try:
    PER_RUN_CAP = int(os.environ.get("RECRUITER_PER_RUN_CAP", "10"))
except (TypeError, ValueError):
    PER_RUN_CAP = 10
try:
    PER_DAY_CAP = int(os.environ.get("RECRUITER_PER_DAY_CAP", "40"))
except (TypeError, ValueError):
    PER_DAY_CAP = 40

# Calling window in US Eastern (no DST math — a 1h edge is harmless).
CALL_WINDOW_START_ET = 9   # 9am
CALL_WINDOW_END_ET = 19    # 7pm
_ET = timezone(timedelta(hours=-5))

# Only recruit in metros we can actually fulfill in. DriverLead.metro values.
TARGET_METROS = {m.strip() for m in os.environ.get(
    "RECRUITER_METROS", "PBC,WPB,BROWARD").split(",") if m.strip()}


def _enabled():
    """Return (ok, reason). Every gate must pass or we stay dark."""
    if os.environ.get("RECRUITER_CALLS_ENABLED", "").lower() != "true":
        return False, "RECRUITER_CALLS_ENABLED != true"
    if not os.environ.get("VAPI_API_KEY"):
        return False, "VAPI_API_KEY unset"
    if not os.environ.get("RECRUITER_ASSISTANT_ID"):
        return False, "RECRUITER_ASSISTANT_ID unset"
    if not os.environ.get("VAPI_PHONE_NUMBER_ID"):
        return False, "VAPI_PHONE_NUMBER_ID unset"
    return True, ""


def _in_window(now_utc):
    et_hour = now_utc.astimezone(_ET).hour
    return CALL_WINDOW_START_ET <= et_hour < CALL_WINDOW_END_ET


def _called_today(DriverLead, now_utc):
    """How many recruiting calls we've already placed today (since ET midnight)."""
    et_midnight = now_utc.astimezone(_ET).replace(
        hour=0, minute=0, second=0, microsecond=0)
    try:
        return DriverLead.query.filter(
            DriverLead.last_recruiter_call_at >= et_midnight.astimezone(timezone.utc),
        ).count()
    except Exception:
        return 0


def _place_call(lead):
    """Place one Vapi recruiting call. Returns call_id or None. Never raises."""
    try:
        import requests
        payload = {
            "assistantId": os.environ["RECRUITER_ASSISTANT_ID"],
            "phoneNumberId": os.environ["VAPI_PHONE_NUMBER_ID"],
            "customer": {
                "number": lead.phone_e164,
                "name": lead.name_guess or "there",
            },
            "assistantOverrides": {
                "voicemailDetectionEnabled": True,
                "voicemailMessage": (
                    "Hi, this is Maya, an AI assistant with Umuve. We send "
                    "paid junk-removal jobs to local haulers, paid same day, "
                    "no app needed. If you'd like jobs in your area, call us "
                    "back or reply to our text. Thanks!"
                ),
                "endCallMessage": "Thanks for your time — have a great day!",
                # Stash the lead id so the outcome handler can find it back.
                "metadata": {"driver_lead_id": lead.id, "purpose": "recruit"},
            },
        }
        resp = requests.post(
            VAPI_CALL_URL, json=payload,
            headers={"Authorization": "Bearer " + os.environ["VAPI_API_KEY"],
                     "Content-Type": "application/json"},
            timeout=30,
        )
        if resp.status_code in (200, 201):
            return resp.json().get("id")
        logger.error("Recruiter call failed for lead %s: %d %s",
                     lead.id, resp.status_code, resp.text[:200])
    except Exception:
        logger.exception("Recruiter call crashed for lead %s", lead.id)
    return None


def run_recruiter_calls(app=None):
    """Place a capped batch of recruiting calls to NEW leads. Never raises."""
    ok, reason = _enabled()
    if not ok:
        logger.info("Recruiter calls dark: %s", reason)
        return {"placed": 0, "reason": reason}

    def _do():
        from models import db
        from partner_models import DriverLead
        from models import utcnow

        now = datetime.now(timezone.utc)
        if not _in_window(now):
            logger.info("Recruiter calls: outside calling window (ET)")
            return {"placed": 0, "reason": "outside_window"}

        already = _called_today(DriverLead, now)
        room = max(0, PER_DAY_CAP - already)
        if room == 0:
            logger.info("Recruiter calls: daily cap %d reached", PER_DAY_CAP)
            return {"placed": 0, "reason": "daily_cap"}

        q = DriverLead.query.filter(
            DriverLead.state == "NEW",
            DriverLead.opted_out.is_(False),
            DriverLead.phone_e164.isnot(None),
        )
        if TARGET_METROS:
            q = q.filter(DriverLead.metro.in_(TARGET_METROS))
        leads = q.order_by(DriverLead.created_at.asc()).limit(
            min(PER_RUN_CAP, room)).all()

        placed = 0
        for lead in leads:
            call_id = _place_call(lead)
            lead.last_recruiter_call_at = now
            if call_id:
                lead.state = "OUTREACHED"
                lead.updated_at = utcnow()
                placed += 1
        db.session.commit()
        logger.info("Recruiter calls: placed %d/%d (daily %d/%d)",
                    placed, len(leads), already + placed, PER_DAY_CAP)
        return {"placed": placed, "attempted": len(leads)}

    try:
        if app:
            with app.app_context():
                return _do()
        return _do()
    except Exception:
        logger.exception("run_recruiter_calls failed")
        return {"placed": 0, "reason": "error"}
