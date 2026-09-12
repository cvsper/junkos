"""Feature flags for the desk: env default, database override, no redeploy.

    flag("power_dial")            → bool
    set_flag("copilot", False)    → DB override (admin/manager only via API)
    all_flags()                   → {name: {"on": bool, "source": env|db|default, "desc": ...}}

Env form: FEATURE_<NAME>=on|off (e.g. FEATURE_COPILOT=off). A DB override in
desk_settings ("flag:<name>" = "on"/"off") wins over env; clearing it falls
back to env, then the default below.
"""
from __future__ import annotations

import os

from models import DeskSetting

FLAGS = {
    "power_dial":     {"default": True,  "desc": "Auto-dial the next card; voicemail drop on machines"},
    "copilot":        {"default": True,  "desc": "Live transcript, objection cues, post-call write-up"},
    "rate_card":      {"default": True,  "desc": "Personalized PDF rate card from the card"},
    "browser_calling": {"default": True, "desc": "Call from the browser on the desk line"},
    "passcode_login": {"default": True,  "desc": "Allow the legacy shared passcode to open the desk (turn off once every VA has an account)"},
    "queue_import":   {"default": True,  "desc": "Load a CSV / add a business from the desk"},
    "maya_prequal":   {"default": False, "desc": "Maya pre-qualifies fresh supply-side cards by phone before a VA dials (also needs PREQUAL_ENABLED=true)"},
    "auto_ingest":    {"default": True,  "desc": "Sourced operator / B2B leads flow into the call queue daily"},
    "push_notifications": {"default": True, "desc": "Web Push to installed desks when a prospect replies"},
    "inbound_customers": {"default": True, "desc": "Inbound calls ring clocked-in VAs first with customer intake on the desk (off = legacy browser + cell ring, then voicemail)"},
    "maya_fallback":  {"default": True,  "desc": "Send unanswered / after-hours inbound calls to Maya instead of voicemail"},
    "sameday_wave":   {"default": True,  "desc": "Desk can text booked same-day jobs to the nearest haulers with one-tap accept"},
    "sameday_standby_text": {"default": False, "desc": "8:45am text to every approved hauler asking if they're available today (off since 9/12 — sevs; the roster can still be asked from the desk)"},
    "sameday_wave_maya": {"default": True, "desc": "Maya's same-day bookings run the same hauler offer wave automatically"},
    "lead_auto_text":  {"default": True,  "desc": "Text an untouched lead once, in the VA's name, after 2 minutes (kill switch for the speed-to-lead sweep)"},
    "auto_instant_payout": {"default": True, "desc": "Push every completed job's payout to the hauler's debit card the same day (Umuve covers the instant fee; standard payout + text if no card)"},
    "completion_pin_required": {"default": False, "desc": "Completing a job requires the customer's 4-digit handoff PIN (texted at assignment); off = PIN is optional proof alongside after-photos"},
}


def _env_value(name):
    raw = os.environ.get("FEATURE_" + name.upper(), "").strip().lower()
    if raw in ("on", "true", "1", "yes"):
        return True
    if raw in ("off", "false", "0", "no"):
        return False
    return None


def _db_value(name):
    try:
        raw = DeskSetting.get("flag:" + name)
    except Exception:
        return None
    if raw is None:
        return None
    return str(raw).strip().lower() in ("on", "true", "1", "yes")


def flag(name):
    spec = FLAGS.get(name)
    if spec is None:
        return False
    v = _db_value(name)
    if v is not None:
        return v
    v = _env_value(name)
    if v is not None:
        return v
    return bool(spec["default"])


def set_flag(name, value):
    if name not in FLAGS:
        raise KeyError(name)
    DeskSetting.put("flag:" + name, None if value is None else ("on" if value else "off"))
    return flag(name)


def all_flags():
    out = {}
    for name, spec in FLAGS.items():
        src = "default"
        if _db_value(name) is not None:
            src = "db"
        elif _env_value(name) is not None:
            src = "env"
        out[name] = {"on": flag(name), "source": src, "desc": spec["desc"]}
    return out
