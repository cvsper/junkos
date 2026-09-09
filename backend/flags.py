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
