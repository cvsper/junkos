"""Call Desk compliance (Phase 2): do-not-call registry, calling-hours guard,
recording/consent policy, data retention, and data-rights export/erase.

Desk endpoints (JWT or legacy passcode — see desk_auth):
  POST /api/va/compliance/dnc          {phone, note?, prospect_id?, source?}
                                       → blocks the number; kills the prospect
  POST /api/va/compliance/dnc-remove   {phone}                       (manager)
  POST /api/va/compliance/check        {phone} → {dnc, source, since, ...}
  POST /api/va/compliance/window       → call_window(): is it OK to dial now?
  POST /api/va/compliance/policy       → recording notice + consent states

Manager endpoints:
  GET  /api/admin/compliance/retention          last nightly run + config
  GET  /api/admin/compliance/export?phone=       everything we hold on a number
  POST /api/admin/compliance/erase {phone, confirm: "ERASE"}

Helpers the rest of the desk calls:
  text_allowed(digits) / call_allowed(digits) → (bool, reason)
  register_opt_out(digits, source, note=None) → DoNotCall (does not commit)
  filter_rows(rows)                           → import rows minus DNC numbers
  compliance_for_card(prospect)               → dict the desk card carries
  call_window(now=None)                       → {open, opens_at, closes_at, ...}
  run_retention(now=None)                     → summary dict (nightly job)

Config (env):
  DESK_CALL_HOURS="08:00-20:00"  DESK_CALL_DAYS="1-6"   (ISO weekdays, Mon=1)
  RETENTION_TRANSCRIPT_DAYS=90  RETENTION_CALL_BODY_DAYS=180  RETENTION_AUDIT_DAYS=400
  DESK_TWO_PARTY_STATES  (comma list; default is the all-party-consent states)
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, time as dtime, timedelta, timezone

from flask import Blueprint, jsonify, request
from sqlalchemy import String as SAString, cast, or_

from desk_auth import MANAGER_ROLES, audit, require_desk
from models import (AuditEvent, CallAttempt, CallProspect, DeskActivity, DeskSetting,
                    DeskTranscriptLine, db)
from models_compliance import DNC_SOURCES, DoNotCall
from timeutils import BUSINESS_TZ, BUSINESS_TZ_NAME, local_now, to_local

logger = logging.getLogger(__name__)
compliance_bp = Blueprint("compliance", __name__)

RETENTION_KEY = "retention:last"
DEFAULT_CALL_HOURS = "08:00-20:00"
DEFAULT_CALL_DAYS = "1-6"
DEFAULT_TRANSCRIPT_DAYS = 90
DEFAULT_CALL_BODY_DAYS = 180
DEFAULT_AUDIT_DAYS = 400

# All-party ("two-party") consent states for call recording. Florida is one,
# which is why the desk's outbound whisper always plays the notice.
DEFAULT_TWO_PARTY_STATES = ("CA", "CT", "DE", "FL", "IL", "MD", "MA", "MI", "MT",
                            "NV", "NH", "OR", "PA", "WA")
# Must match the whisper in desk_line.twilio_voice_whisper.
RECORDING_NOTICE_TEXT = "This call may be recorded for quality."

# Tests patch this to freeze the clock.
_local_now = local_now


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _digits(phone):
    d = re.sub(r"\D", "", str(phone or ""))
    return d[-10:] if len(d) >= 10 else d


def _utcnow():
    return datetime.now(timezone.utc)


def _now_naive():
    return _utcnow().replace(tzinfo=None)


def _append_note(existing, line):
    stamp = _utcnow().strftime("%Y-%m-%d %H:%M")
    entry = "[{}] {}".format(stamp, line)
    return (existing + "\n" + entry) if existing else entry


def _env_int(name, default):
    try:
        return max(1, int(os.environ.get(name, "") or default))
    except (TypeError, ValueError):
        return default


def _find_prospect(digits):
    """The prospect a number belongs to: front-desk number first, then a
    decision-maker cell (direct_phone)."""
    if len(digits) != 10:
        return None
    p = CallProspect.query.filter_by(phone_digits=digits).first()
    if p:
        return p
    for cand in (CallProspect.query
                 .filter(CallProspect.direct_phone.isnot(None),
                         CallProspect.direct_phone.like("%{}%".format(digits[-4:])))
                 .limit(50).all()):
        if _digits(cand.direct_phone) == digits:
            return cand
    return None


# ---------------------------------------------------------------------------
# do-not-call registry
# ---------------------------------------------------------------------------
def dnc_for(digits):
    digits = _digits(digits)
    if len(digits) != 10:
        return None
    return DoNotCall.query.filter_by(phone_digits=digits).first()


def is_dnc(digits):
    return dnc_for(digits) is not None


def register_opt_out(digits, source="manual", note=None, created_by=None):
    """Put a number on the list (idempotent). Adds to the session; the caller
    commits — record_inbound_text and the endpoints both commit right after."""
    digits = _digits(digits)
    if len(digits) != 10:
        return None
    if source not in DNC_SOURCES:
        source = "manual"
    row = dnc_for(digits)
    if row is not None:
        if note and not row.note:
            row.note = str(note)[:500]
        return row
    row = DoNotCall(phone_digits=digits, source=source,
                    note=(str(note)[:500] if note else None),
                    created_by=(str(created_by)[:120] if created_by else None))
    db.session.add(row)
    return row


def text_allowed(digits):
    """(True, "") when the desk may text this number."""
    digits = _digits(digits)
    if len(digits) != 10:
        return False, "not a 10-digit US number"
    row = dnc_for(digits)
    if row is not None:
        return False, "on the do-not-call list ({})".format(row.source)
    # Opt-outs recorded before the registry existed live on the prospect.
    p = CallProspect.query.filter_by(phone_digits=digits).first()
    if p is not None and p.last_outcome == "opted_out":
        return False, "they opted out"
    return True, ""


def call_allowed(digits, now=None):
    """(True, "") when the desk may dial this number right now."""
    ok, why = text_allowed(digits)
    if not ok:
        return False, why
    w = call_window(now)
    if not w["open"]:
        return False, "calling window is closed until {}".format(w["opens_label"] or "the next calling day")
    return True, ""


def filter_rows(rows):
    """Import rows (dicts with a 'phone') minus any number on the list.
    Wired into va_calls.merge_rows so a re-import can't resurrect an opt-out."""
    rows = list(rows or [])
    wanted = {_digits(r.get("phone")) for r in rows if isinstance(r, dict)}
    wanted = {d for d in wanted if len(d) == 10}
    if not wanted:
        return rows
    blocked = set()
    wanted = sorted(wanted)
    for i in range(0, len(wanted), 500):
        chunk = wanted[i:i + 500]
        blocked.update(d for (d,) in db.session.query(DoNotCall.phone_digits)
                       .filter(DoNotCall.phone_digits.in_(chunk)).all())
    if not blocked:
        return rows
    return [r for r in rows if not (isinstance(r, dict) and _digits(r.get("phone")) in blocked)]


def compliance_for_card(p):
    """What the desk card needs to know: is this number blocked, may we dial now."""
    row = dnc_for(getattr(p, "phone_digits", "") or "")
    w = call_window()
    return {"dnc": row is not None, "dnc_source": row.source if row else None,
            "window_open": w["open"], "window_note": w["note"]}


# ---------------------------------------------------------------------------
# calling-hours window
# ---------------------------------------------------------------------------
def _parse_hours(raw):
    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*$", raw or "")
    if not m:
        m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*$", DEFAULT_CALL_HOURS)
    h1, m1, h2, m2 = (int(x) for x in m.groups())
    try:
        return dtime(h1, m1), dtime(h2, m2)
    except ValueError:
        return dtime(8, 0), dtime(20, 0)


def _parse_days(raw):
    days = set()
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(\d)\s*-\s*(\d)$", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            days.update(range(min(a, b), max(a, b) + 1))
        elif part.isdigit():
            days.add(int(part))
    days = {d for d in days if 1 <= d <= 7}
    if not days and raw != DEFAULT_CALL_DAYS:   # unreadable env value → the default week
        return _parse_days(DEFAULT_CALL_DAYS)
    return days


def _clock_label(dt, today):
    """'8:00 AM' when it's today, else 'Mon 8:00 AM'."""
    if dt is None:
        return None
    h = dt.hour % 12 or 12
    t = "{}:{:02d} {}".format(h, dt.minute, "PM" if dt.hour >= 12 else "AM")
    return t if dt.date() == today else "{} {}".format(dt.strftime("%a"), t)


def call_window(now=None):
    """Whether outbound B2B calls are allowed right now (business timezone).

    Returns {open, opens_at, closes_at, opens_label, closes_label, now_local,
    hours, days, tz, note}. `opens_at`/`closes_at` describe the current window
    when open, otherwise the next one."""
    now_local = to_local(now) if now is not None else _local_now()
    open_t, close_t = _parse_hours(os.environ.get("DESK_CALL_HOURS", DEFAULT_CALL_HOURS))
    days = _parse_days(os.environ.get("DESK_CALL_DAYS", DEFAULT_CALL_DAYS))
    today = now_local.date()

    def span(day):
        return (datetime.combine(day, open_t, tzinfo=BUSINESS_TZ),
                datetime.combine(day, close_t, tzinfo=BUSINESS_TZ))

    opens = closes = None
    is_open = False
    if today.isoweekday() in days:
        o, c = span(today)
        if o <= now_local < c:
            is_open, opens, closes = True, o, c
    if not is_open:
        for i in range(0, 8):
            day = today + timedelta(days=i)
            if day.isoweekday() not in days:
                continue
            o, c = span(day)
            if o > now_local:
                opens, closes = o, c
                break
    opens_label = _clock_label(opens, today)
    closes_label = _clock_label(closes, today)
    if is_open:
        note = "Calling window is open until {}.".format(closes_label)
    elif opens is not None:
        note = "Calling window is closed until {} — texting still works.".format(opens_label)
    else:
        note = "Calling window is closed — texting still works."
    return {
        "open": is_open,
        "opens_at": opens.isoformat() if opens else None,
        "closes_at": closes.isoformat() if closes else None,
        "opens_label": opens_label,
        "closes_label": closes_label,
        "now_local": now_local.isoformat(),
        "hours": "{:02d}:{:02d}-{:02d}:{:02d}".format(open_t.hour, open_t.minute, close_t.hour, close_t.minute),
        "days": sorted(days),
        "tz": BUSINESS_TZ_NAME,
        "note": note,
    }


# ---------------------------------------------------------------------------
# recording / consent policy
# ---------------------------------------------------------------------------
def policy():
    raw = os.environ.get("DESK_TWO_PARTY_STATES", "")
    states = [s.strip().upper() for s in raw.split(",") if s.strip()] or list(DEFAULT_TWO_PARTY_STATES)
    notice = os.environ.get("DESK_RECORDING_NOTICE", "on").strip().lower() not in ("off", "0", "false", "no")
    return {
        "recording_notice": notice,
        "two_party_states": states,
        "notice_text": RECORDING_NOTICE_TEXT,
        "desk_note": "Copilot: the other side hears a short recording notice before you connect (Florida is all-party consent).",
        "call_hours": os.environ.get("DESK_CALL_HOURS", DEFAULT_CALL_HOURS),
        "call_days": os.environ.get("DESK_CALL_DAYS", DEFAULT_CALL_DAYS),
        "tz": BUSINESS_TZ_NAME,
    }


# ---------------------------------------------------------------------------
# retention
# ---------------------------------------------------------------------------
def retention_config():
    return {
        "transcript_days": _env_int("RETENTION_TRANSCRIPT_DAYS", DEFAULT_TRANSCRIPT_DAYS),
        "call_body_days": _env_int("RETENTION_CALL_BODY_DAYS", DEFAULT_CALL_BODY_DAYS),
        "audit_days": _env_int("RETENTION_AUDIT_DAYS", DEFAULT_AUDIT_DAYS),
    }


def run_retention(now=None):
    """Nightly sweep. Deletes old transcript lines, blanks the body/recording
    on old call activities (rows stay for stats), and deletes old audit events.
    Stores the summary in DeskSetting 'retention:last' and audits the run."""
    now = now or _utcnow()
    now_naive = now.astimezone(timezone.utc).replace(tzinfo=None) if now.tzinfo else now
    cfg = retention_config()
    cut_t = now_naive - timedelta(days=cfg["transcript_days"])
    cut_c = now_naive - timedelta(days=cfg["call_body_days"])
    cut_a = now_naive - timedelta(days=cfg["audit_days"])

    transcripts = (DeskTranscriptLine.query
                   .filter(DeskTranscriptLine.created_at < cut_t)
                   .delete(synchronize_session=False))
    call_bodies = (DeskActivity.query
                   .filter(DeskActivity.kind == "call", DeskActivity.created_at < cut_c,
                           or_(DeskActivity.body.isnot(None), DeskActivity.recording_url.isnot(None)))
                   .update({"body": None, "recording_url": None}, synchronize_session=False))
    audits = (AuditEvent.query
              .filter(AuditEvent.created_at < cut_a)
              .delete(synchronize_session=False))
    summary = {
        "ran_at": now_naive.replace(tzinfo=timezone.utc).isoformat(),
        "transcripts_deleted": int(transcripts or 0),
        "call_bodies_blanked": int(call_bodies or 0),
        "audit_deleted": int(audits or 0),
        "cutoffs": {"transcripts": cut_t.isoformat(), "call_bodies": cut_c.isoformat(),
                    "audit": cut_a.isoformat()},
        "days": cfg,
    }
    DeskSetting.put(RETENTION_KEY, json.dumps(summary))  # commits
    audit("retention_run", "system", "retention", summary, via="system",
          actor={"name": "retention", "role": "system"})
    logger.info("compliance retention: %s", summary)
    return summary


def last_retention():
    raw = DeskSetting.get(RETENTION_KEY)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# data rights: export + erase
# ---------------------------------------------------------------------------
def _activity_filter(digits, p):
    conds = [DeskActivity.phone_digits == digits]
    if p is not None:
        conds.append(DeskActivity.prospect_id == p.id)
        direct = _digits(p.direct_phone) if p.direct_phone else ""
        if len(direct) == 10 and direct != digits:
            conds.append(DeskActivity.phone_digits == direct)
    return or_(*conds)


def export_bundle(digits):
    """Everything the desk holds on a number, as plain JSON."""
    digits = _digits(digits)
    p = _find_prospect(digits)
    acts = (DeskActivity.query.filter(_activity_filter(digits, p))
            .order_by(DeskActivity.created_at.asc()).all())
    attempts, lines, events = [], [], []
    if p is not None:
        attempts = (CallAttempt.query.filter_by(prospect_id=p.id)
                    .order_by(CallAttempt.created_at.asc()).all())
        lines = (DeskTranscriptLine.query.filter_by(prospect_id=p.id)
                 .order_by(DeskTranscriptLine.created_at.asc(), DeskTranscriptLine.seq.asc()).all())
        try:
            events = (AuditEvent.query
                      .filter(or_(AuditEvent.target_id == p.id, AuditEvent.target_id == digits,
                                  cast(AuditEvent.meta, SAString).like("%{}%".format(p.id))))
                      .order_by(AuditEvent.created_at.asc()).all())
        except Exception:  # a dialect that can't cast JSON: fall back to targets only
            db.session.rollback()
            events = (AuditEvent.query
                      .filter(or_(AuditEvent.target_id == p.id, AuditEvent.target_id == digits))
                      .order_by(AuditEvent.created_at.asc()).all())
    else:
        events = (AuditEvent.query.filter(AuditEvent.target_id == digits)
                  .order_by(AuditEvent.created_at.asc()).all())
    row = dnc_for(digits)
    return {
        "phone_digits": digits,
        "generated_at": _utcnow().isoformat(),
        "prospect": p.to_dict() if p else None,
        "attempts": [{"id": a.id, "outcome": a.outcome, "note": a.note, "va_name": a.va_name,
                      "at": a.created_at.isoformat() if a.created_at else None} for a in attempts],
        "activities": [a.to_dict() for a in acts],
        "transcript_lines": [dict(l.to_dict(), call_sid=l.call_sid) for l in lines],
        "dnc": row.to_dict() if row else None,
        "audit_events": [e.to_dict() for e in events],
    }


def erase(digits, created_by=None):
    """Delete activities/transcripts/attempts, anonymize the prospect (keeping
    only phone_digits so dedupe still blocks a re-import), and block the number."""
    digits = _digits(digits)
    p = _find_prospect(digits)
    counts = {"activities": 0, "transcripts": 0, "attempts": 0}
    register_opt_out(digits, "erase", note="data erasure request", created_by=created_by)
    if p is not None:
        direct = _digits(p.direct_phone) if p.direct_phone else ""
        if len(direct) == 10 and direct != digits:
            register_opt_out(direct, "erase", note="data erasure request (direct line)", created_by=created_by)
        counts["activities"] = int(DeskActivity.query.filter(_activity_filter(digits, p))
                                   .delete(synchronize_session=False) or 0)
        counts["transcripts"] = int(DeskTranscriptLine.query.filter_by(prospect_id=p.id)
                                    .delete(synchronize_session=False) or 0)
        counts["attempts"] = int(CallAttempt.query.filter_by(prospect_id=p.id)
                                 .delete(synchronize_session=False) or 0)
        p.company = "Erased"
        p.phone = ""
        p.city = None
        p.contact_name = None
        p.why = None
        p.angle = None
        p.email = None
        p.direct_phone = None
        p.last_note = None
        p.status = "dead"
        p.last_outcome = "erased"
        p.next_followup_at = None
    else:
        counts["activities"] = int(DeskActivity.query.filter_by(phone_digits=digits)
                                   .delete(synchronize_session=False) or 0)
    db.session.commit()
    return {"phone_digits": digits, "prospect_id": p.id if p else None, "erased": counts, "dnc": True}


# ---------------------------------------------------------------------------
# desk endpoints
# ---------------------------------------------------------------------------
def _phone_from(data):
    return _digits((data or {}).get("phone"))


@compliance_bp.route("/api/va/compliance/dnc", methods=["POST"])
@require_desk()
def dnc_add(ident):
    data = request.get_json(silent=True) or {}
    p = db.session.get(CallProspect, data.get("prospect_id") or "") if data.get("prospect_id") else None
    digits = _phone_from(data) or (p.phone_digits if p else "")
    if len(digits) != 10:
        return jsonify({"error": "That doesn't look like a valid US number."}), 400
    if p is None:
        p = _find_prospect(digits)
    note = (data.get("note") or "").strip()[:500]
    source = data.get("source") if data.get("source") in ("call_request", "manual", "import") else "call_request"
    already = dnc_for(digits) is not None
    row = register_opt_out(digits, source, note=note or None, created_by=ident.get("name"))
    if p is not None:
        p.status = "dead"
        p.last_outcome = "opted_out"
        p.next_followup_at = None
        p.last_note = _append_note(p.last_note, "DO NOT CALL — asked not to be contacted"
                                   + (": " + note if note else ""))
        if source == "call_request":
            p.attempts = (p.attempts or 0) + 1
            p.last_called_at = _now_naive()
            db.session.add(CallAttempt(prospect_id=p.id, outcome="opted_out",
                                       note=note or None, va_name=ident.get("name") or None))
    db.session.commit()
    audit("dnc_add", "phone", digits, {"source": source, "prospect_id": p.id if p else None,
                                       "note": note or None, "already": already})
    return jsonify({"ok": True, "dnc": row.to_dict(), "already": already,
                    "prospect_id": p.id if p else None}), 200


@compliance_bp.route("/api/va/compliance/dnc-remove", methods=["POST"])
@require_desk(MANAGER_ROLES)
def dnc_remove(ident):
    data = request.get_json(silent=True) or {}
    digits = _phone_from(data)
    if len(digits) != 10:
        return jsonify({"error": "That doesn't look like a valid US number."}), 400
    row = dnc_for(digits)
    if row is None:
        return jsonify({"error": "That number isn't on the list."}), 404
    source = row.source
    db.session.delete(row)
    p = CallProspect.query.filter_by(phone_digits=digits).first()
    if p is not None and p.last_outcome == "opted_out":
        # The block is lifted; the prospect stays dead until someone re-queues it.
        p.last_outcome = None
        p.last_note = _append_note(p.last_note, "Do-not-call removed by {}".format(ident.get("name") or "a manager"))
    db.session.commit()
    audit("dnc_remove", "phone", digits, {"was_source": source, "prospect_id": p.id if p else None})
    return jsonify({"ok": True, "removed": digits, "prospect_id": p.id if p else None}), 200


@compliance_bp.route("/api/va/compliance/check", methods=["POST"])
@require_desk()
def dnc_check(ident):
    data = request.get_json(silent=True) or {}
    digits = _phone_from(data)
    if len(digits) != 10:
        return jsonify({"error": "That doesn't look like a valid US number."}), 400
    row = dnc_for(digits)
    ok_text, why_text = text_allowed(digits)
    ok_call, why_call = call_allowed(digits)
    return jsonify({"dnc": row is not None, "source": row.source if row else None,
                    "since": row.created_at.isoformat() if row and row.created_at else None,
                    "note": row.note if row else None,
                    "text_allowed": ok_text, "text_reason": why_text or None,
                    "call_allowed": ok_call, "call_reason": why_call or None}), 200


@compliance_bp.route("/api/va/compliance/window", methods=["POST"])
@require_desk()
def window_endpoint(ident):
    return jsonify(call_window()), 200


@compliance_bp.route("/api/va/compliance/policy", methods=["POST"])
@require_desk()
def policy_endpoint(ident):
    return jsonify(policy()), 200


# ---------------------------------------------------------------------------
# manager endpoints
# ---------------------------------------------------------------------------
@compliance_bp.route("/api/admin/compliance/retention", methods=["GET"])
@require_desk(MANAGER_ROLES)
def retention_endpoint(ident):
    return jsonify({"last": last_retention(), "config": retention_config()}), 200


@compliance_bp.route("/api/admin/compliance/export", methods=["GET"])
@require_desk(MANAGER_ROLES)
def export_endpoint(ident):
    digits = _digits(request.args.get("phone"))
    if len(digits) != 10:
        return jsonify({"error": "Pass ?phone= with a 10-digit US number."}), 400
    bundle = export_bundle(digits)
    audit("export", "phone", digits, {"prospect_id": (bundle["prospect"] or {}).get("id"),
                                      "activities": len(bundle["activities"])})
    return jsonify(bundle), 200


@compliance_bp.route("/api/admin/compliance/erase", methods=["POST"])
@require_desk(MANAGER_ROLES)
def erase_endpoint(ident):
    data = request.get_json(silent=True) or {}
    digits = _phone_from(data)
    if len(digits) != 10:
        return jsonify({"error": "That doesn't look like a valid US number."}), 400
    if (data.get("confirm") or "") != "ERASE":
        return jsonify({"error": "Type ERASE to confirm — this can't be undone."}), 400
    result = erase(digits, created_by=ident.get("name"))
    audit("erase", "phone", digits, {"prospect_id": result["prospect_id"], "erased": result["erased"]})
    return jsonify(dict(result, ok=True)), 200
