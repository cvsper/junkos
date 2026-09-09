"""Maya pre-qualification for the Call Desk (Phase 5 — Growth).

Before Tracy dials a fresh supply-side card, Maya can ring the hauler first
and ask the two questions that matter (do you have a truck, do you want paid
jobs). Warm answers pin an immediate callback on the desk with Maya's
summary; cold answers close the card; no-answer / voicemail follow the
desk's normal retry cadence. Tracy only spends her minutes on people who
already said yes.

SAFETY — this places real outbound phone calls. Every one of these must hold
before a call goes out:
    flag maya_prequal            (desk feature flag, default OFF)
    PREQUAL_ENABLED=true         (env kill switch)
    VAPI_API_KEY, VAPI_PHONE_NUMBER_ID
    PREQUAL_ASSISTANT_ID         (falls back to RECRUITER_ASSISTANT_ID)
Plus: calls only 10:00-16:00 America/New_York Mon-Sat, capped at
PREQUAL_DAILY_CAP (25) per ET day, never twice for the same prospect.

Results come back on POST /api/growth/prequal/result (growth.py) either as
the simple {prospect_id, disposition, summary, transcript} shape or as a raw
Vapi end-of-call-report whose metadata carries prequal_prospect_id.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from models import db, CallProspect
from models_growth import PrequalCall

logger = logging.getLogger(__name__)

try:  # the same Vapi outbound endpoint the recruiter uses
    from recruiter_calls import VAPI_CALL_URL
except Exception:  # pragma: no cover
    VAPI_CALL_URL = "https://api.vapi.ai/call/phone"

ET = ZoneInfo("America/New_York")
WINDOW_START_HOUR = 10       # 10:00 ET
WINDOW_END_HOUR = 16         # until 16:00 ET (exclusive)
WINDOW_DAYS = (0, 1, 2, 3, 4, 5)   # Mon-Sat

DISPOSITIONS = ("warm", "cold", "no_answer", "voicemail")
DEFAULT_DAILY_CAP = 25


def _now():
    return datetime.now(timezone.utc)


def daily_cap():
    try:
        return max(0, int(os.environ.get("PREQUAL_DAILY_CAP", DEFAULT_DAILY_CAP)))
    except (TypeError, ValueError):
        return DEFAULT_DAILY_CAP


def assistant_id():
    return os.environ.get("PREQUAL_ASSISTANT_ID") or os.environ.get("RECRUITER_ASSISTANT_ID") or ""


def flag_on():
    try:
        from flags import flag
        return bool(flag("maya_prequal"))
    except Exception:
        return False


def enabled():
    """(ok, reason). Every gate must pass or we stay dark."""
    if not flag_on():
        return False, "flag maya_prequal off"
    if os.environ.get("PREQUAL_ENABLED", "").lower() != "true":
        return False, "PREQUAL_ENABLED != true"
    if not os.environ.get("VAPI_API_KEY"):
        return False, "VAPI_API_KEY unset"
    if not os.environ.get("VAPI_PHONE_NUMBER_ID"):
        return False, "VAPI_PHONE_NUMBER_ID unset"
    if not assistant_id():
        return False, "PREQUAL_ASSISTANT_ID unset"
    return True, ""


def in_window(now=None):
    local = (now or _now()).astimezone(ET)
    return local.weekday() in WINDOW_DAYS and WINDOW_START_HOUR <= local.hour < WINDOW_END_HOUR


def _et_day_start(now=None):
    local = (now or _now()).astimezone(ET).replace(hour=0, minute=0, second=0, microsecond=0)
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def called_today(now=None):
    return PrequalCall.query.filter(PrequalCall.created_at >= _et_day_start(now)).count()


def already_called(prospect):
    return PrequalCall.query.filter_by(prospect_id=prospect.id).first() is not None


def eligible(prospect, extra_filter=None):
    """Supply side, still queued, never dialed by anyone, never dialed by Maya."""
    if prospect is None or prospect.status != "queued" or (prospect.attempts or 0) != 0:
        return False
    if len(prospect.phone_digits or "") != 10:
        return False
    try:
        from call_kit import detect_side
        if detect_side(prospect) != "supply":
            return False
    except Exception:
        return False
    if already_called(prospect):
        return False
    if extra_filter is not None and not extra_filter(prospect):
        return False
    return True


def candidates(limit, extra_filter=None):
    q = (CallProspect.query
         .filter(CallProspect.status == "queued", CallProspect.attempts == 0,
                 CallProspect.next_followup_at.is_(None))
         .order_by(CallProspect.tier.asc(), CallProspect.created_at.asc()))
    out = []
    for p in q.limit(max(limit * 6, 30)).all():
        if eligible(p, extra_filter):
            out.append(p)
            if len(out) >= limit:
                break
    return out


class _ProspectAsLead:
    """Adapter: what the Vapi payload builder needs from a CallProspect."""

    def __init__(self, prospect):
        self.id = prospect.id
        self.phone_e164 = "+1" + prospect.phone_digits
        self.name_guess = (prospect.contact_name or "").split(" ")[0] or None
        self.company = prospect.company


def build_call_payload(prospect, metadata=None):
    lead = _ProspectAsLead(prospect)
    md = {"prequal_prospect_id": prospect.id, "purpose": "prequal"}
    md.update(metadata or {})
    return {
        "assistantId": assistant_id(),
        "phoneNumberId": os.environ.get("VAPI_PHONE_NUMBER_ID", ""),
        "customer": {"number": lead.phone_e164, "name": lead.name_guess or "there"},
        "assistantOverrides": {
            "voicemailDetectionEnabled": True,
            "voicemailMessage": (
                "Hi, this is Maya with Umuve. We send paid junk-removal jobs to "
                "local haulers, paid same day, no app needed. If you'd like jobs "
                "in your area, call us back or reply to our text. Thanks!"
            ),
            "endCallMessage": "Thanks for your time — have a great day!",
            "metadata": md,
        },
    }


def place_call(prospect, metadata=None):
    """Place one Vapi pre-qual call. Returns the Vapi call id or None. Never raises."""
    try:
        import requests
        resp = requests.post(
            VAPI_CALL_URL, json=build_call_payload(prospect, metadata),
            headers={"Authorization": "Bearer " + os.environ.get("VAPI_API_KEY", ""),
                     "Content-Type": "application/json"},
            timeout=30,
        )
        if resp.status_code in (200, 201):
            return (resp.json() or {}).get("id")
        logger.error("Prequal call failed for %s: %d %s", prospect.id, resp.status_code, resp.text[:200])
    except Exception:
        logger.exception("Prequal call crashed for %s", prospect.id)
    return None


def _brief(p):
    return {"prospect_id": p.id, "company": p.company, "phone": p.phone, "tier": p.tier,
            "category": p.category, "city": p.city}


def run_prequal(dry_run=False, now=None, extra_filter=None):
    """One scheduled tick. Returns {"would_call"|"called": [...], "reason": ...}."""
    now = now or _now()
    ok, reason = enabled()
    if not ok and not dry_run:
        return {"called": [], "reason": reason, "enabled": False}
    if not in_window(now):
        return {"called": [], "would_call": [], "reason": "outside_window", "enabled": ok}
    room = daily_cap() - called_today(now)
    if room <= 0:
        return {"called": [], "would_call": [], "reason": "daily_cap", "enabled": ok}
    picks = candidates(room, extra_filter)
    if dry_run:
        return {"would_call": [_brief(p) for p in picks], "reason": "" if ok else reason,
                "enabled": ok, "room": room}
    called = []
    for p in picks:
        call_id = place_call(p)
        row = PrequalCall(prospect_id=p.id, vapi_call_id=call_id,
                          disposition="pending" if call_id else "failed",
                          created_at=now.astimezone(timezone.utc).replace(tzinfo=None))
        db.session.add(row)
        if call_id:
            called.append(dict(_brief(p), vapi_call_id=call_id))
    db.session.commit()
    logger.info("Prequal: placed %d/%d (room %d)", len(called), len(picks), room)
    return {"called": called, "attempted": len(picks), "reason": "", "enabled": True}


def run_prequal_job(app=None):
    """Scheduler entry point. Never raises."""
    def _do():
        return run_prequal()
    try:
        if app is not None:
            with app.app_context():
                return _do()
        return _do()
    except Exception:
        logger.exception("prequal job failed")
        return {"called": [], "reason": "error"}


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

def _from_vapi_report(data):
    """Map a raw Vapi end-of-call-report to the simple result shape, or None."""
    message = data.get("message") if isinstance(data, dict) else None
    if not isinstance(message, dict):
        return None
    call = message.get("call", {}) or {}
    md = ((call.get("assistantOverrides", {}) or {}).get("metadata", {}) or {}) or (call.get("metadata", {}) or {})
    pid = md.get("prequal_prospect_id") if isinstance(md, dict) else None
    if not pid:
        return None
    analysis = message.get("analysis", {}) or {}
    structured = analysis.get("structuredData", {}) or {}
    raw = (structured.get("disposition") or structured.get("outcome") or "").lower()
    ended = (message.get("endedReason") or "").lower()
    if raw in ("interested", "warm", "yes"):
        disp = "warm"
    elif raw in ("not_interested", "cold", "no", "wrong_number"):
        disp = "cold"
    elif raw == "voicemail" or "voicemail" in ended:
        disp = "voicemail"
    elif raw in ("no_answer", "no-answer") or "no-answer" in ended or "busy" in ended:
        disp = "no_answer"
    else:
        disp = "no_answer"
    transcript = message.get("transcript") or ""
    if not transcript and isinstance(message.get("artifact"), dict):
        transcript = message["artifact"].get("transcript") or ""
    return {"prospect_id": pid, "disposition": disp,
            "summary": message.get("summary") or analysis.get("summary") or "",
            "transcript": transcript, "vapi_call_id": call.get("id")}


def handle_result(data):
    """Apply a pre-qual result to the prospect. Returns (ok, info)."""
    from va_calls import apply_outcome, schedule_callback

    if not isinstance(data, dict):
        return False, {"error": "bad payload"}
    payload = data if data.get("prospect_id") else _from_vapi_report(data)
    if not payload:
        return False, {"error": "prospect_id required"}
    disposition = (payload.get("disposition") or "").strip().lower()
    if disposition not in DISPOSITIONS:
        return False, {"error": "disposition must be one of " + ", ".join(DISPOSITIONS)}
    prospect = db.session.get(CallProspect, str(payload.get("prospect_id")))
    if prospect is None:
        return False, {"error": "prospect not found"}

    summary = (payload.get("summary") or "").strip()[:2000]
    transcript = (payload.get("transcript") or "")[:20000]
    call_id = payload.get("vapi_call_id")

    row = None
    if call_id:
        row = PrequalCall.query.filter_by(vapi_call_id=call_id).first()
    if row is None:
        row = (PrequalCall.query.filter_by(prospect_id=prospect.id)
               .filter(PrequalCall.disposition.in_(("pending", None)))
               .order_by(PrequalCall.created_at.desc()).first())
    if row is None:
        row = PrequalCall(prospect_id=prospect.id, vapi_call_id=call_id)
        db.session.add(row)
    row.disposition = disposition
    row.summary = summary or None
    row.transcript = transcript or None
    row.resolved_at = _now().replace(tzinfo=None)

    note = "MAYA: " + (summary or disposition.replace("_", " "))
    if disposition == "warm":
        schedule_callback(prospect, _now(), note, "Maya")
        prospect.status = "interested"
    elif disposition == "cold":
        apply_outcome(prospect, "not_interested", note, "Maya")
    else:
        apply_outcome(prospect, "voicemail", note, "Maya")
    db.session.commit()
    return True, {"prospect_id": prospect.id, "disposition": disposition, "status": prospect.status}


def latest_for(prospect_id):
    row = (PrequalCall.query.filter_by(prospect_id=prospect_id)
           .order_by(PrequalCall.created_at.desc()).first())
    return row.to_dict() if row else None


def stats(now=None):
    from sqlalchemy import func
    now = now or _now()
    by = dict(db.session.query(PrequalCall.disposition, func.count(PrequalCall.id))
              .group_by(PrequalCall.disposition).all())
    ok, reason = enabled()
    return {
        "enabled": ok, "reason": reason, "in_window": in_window(now),
        "daily_cap": daily_cap(), "called_today": called_today(now),
        "total": sum(by.values()), "by_disposition": {k or "unknown": v for k, v in by.items()},
    }
