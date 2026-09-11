"""Confirm the hauler before the job. Re-dispatch when they go quiet.

Job AFB22IMO: booked Saturday for Sunday noon, assigned to a hauler with zero
completed jobs, and nobody asked him whether he was coming. He wasn't. The
customer waited nineteen days. Every safety net fired *after* the slot; none
of them fired before it, and none of them re-dispatched.

Two things, in the order a real dispatcher does them:

  The evening before   every job scheduled in the next ~36h with a hauler on
                       it appears in the work queue until a person has heard
                       "yes, I'm coming" from that hauler and pressed Confirmed.
                       "Can't make it" releases the hauler and re-dispatches.

  Thirty minutes out   if the hauler has not started moving:
                         unconfirmed → release them, count the no-show, wave
                                       the job to the nearest live haulers,
                                       page a person.
                         confirmed   → page a person and put it at the top of
                                       the queue with a one-tap re-dispatch;
                                       a confirmed hauler running late is a
                                       judgement, not an automatic drop.

Nothing here texts the customer; the late-start watchdog already does that at
T+15 and two reassurance texts is worse than one.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from models import db, Job, Contractor, User
from desk_auth import desk_identity, desk_va_name, audit

try:
    from extensions import limiter
except Exception:  # pragma: no cover
    limiter = None

logger = logging.getLogger(__name__)
confirm_bp = Blueprint("hauler_confirm", __name__)
_ratelimit = (limiter.limit("240 per hour; 60 per minute") if limiter is not None else (lambda f: f))

CONFIRM_WINDOW_HOURS = 36        # how far ahead the "confirm tomorrow" list looks
PRESLOT_MIN = 25                 # same width as the no-show watchdog so a missed tick can't skip a job
PRESLOT_MAX = 35
MOVING_STATUSES = ("en_route", "arrived", "started", "in_progress", "completed", "paid")
ASSIGNED_STATUSES = ("assigned", "accepted", "confirmed")


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _naive(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def _pretty(digits):
    d = "".join(ch for ch in (digits or "") if ch.isdigit())[-10:]
    return "({}) {}-{}".format(d[:3], d[3:6], d[6:]) if len(d) == 10 else (digits or "")


def _hauler(job):
    c = db.session.get(Contractor, job.driver_id) if job.driver_id else None
    u = c.user if c else None
    name = (getattr(c, "business_name", None) or (u.name if u else None) or "Hauler") if c else None
    return c, name, (_pretty(u.phone) if u and u.phone else None)


def _customer_first_name(job):
    try:
        u = db.session.get(User, job.customer_id) if job.customer_id else None
        return ((u.name if u else "") or "the customer").split()[0]
    except Exception:
        return "the customer"


# ---------------------------------------------------------------------------
# The list
# ---------------------------------------------------------------------------
def upcoming(hours=CONFIRM_WINDOW_HOURS):
    """Jobs with a hauler, scheduled within ``hours``, that still need a person
    to hear "yes, I'm coming". Sorted soonest first."""
    from timeutils import fmt_local
    from hauler_reliability import profile

    now = _now()
    until = now + timedelta(hours=hours)
    rows = (Job.query.filter(Job.driver_id.isnot(None),
                             Job.status.in_(ASSIGNED_STATUSES),
                             Job.scheduled_at.isnot(None),
                             Job.scheduled_at >= now - timedelta(minutes=30),
                             Job.scheduled_at <= until)
            .order_by(Job.scheduled_at.asc()).limit(100).all())
    out = []
    for job in rows:
        c, hauler_name, hauler_phone = _hauler(job)
        hours_out = round((_naive(job.scheduled_at) - now).total_seconds() / 3600.0, 1)
        rel = profile(c) if c else {"tier": "new", "label": "First job", "completed": 0, "no_shows": 0}
        out.append({
            "job_id": job.id,
            "code": job.confirmation_code or job.id[:8],
            "when": fmt_local(job.scheduled_at, "%a %b %-d, %-I:%M %p", "TBD"),
            "hours_out": hours_out,
            "address": (job.address or "").split(",")[0][:48],
            "customer": _customer_first_name(job),
            "total": round(float(job.total_price or 0.0), 2),
            "hauler": hauler_name, "hauler_phone": hauler_phone, "contractor_id": job.driver_id,
            "tier": rel["tier"], "tier_label": rel["label"],
            "completed_jobs": rel["completed"], "no_shows": rel["no_shows"],
            "confirmed": bool(job.hauler_confirmed_at),
            "confirmed_by": job.hauler_confirmed_by,
            "confirmed_at": (job.hauler_confirmed_at.isoformat() + "Z") if job.hauler_confirmed_at else None,
            "note": job.hauler_confirm_note,
            "paged_at": (job.preslot_alerted_at.isoformat() + "Z") if job.preslot_alerted_at else None,
            "status": job.status,
        })
    return out


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------
def mark_confirmed(job, va_name, note=None):
    job.hauler_confirmed_at = _now()
    job.hauler_confirmed_by = (va_name or "someone")[:80]
    if note:
        job.hauler_confirm_note = note[:500]
    job.updated_at = _now()


def redispatch(job, actor, reason, va_name=None, count_no_show=True):
    """Release the assigned hauler and wave the job to the nearest live ones.

    Returns a summary dict. Never raises past logging; the caller decides
    whether to commit."""
    from hauler_reliability import record_no_show

    had = job.driver_id
    result = {"released": None, "waved": 0, "reason": reason}
    if had:
        try:
            from assignment import release_job
            release_job(job, actor, reason=reason, source="preslot", new_status="confirmed")
            result["released"] = had
        except Exception:
            logger.exception("release_job failed for %s — falling back to a direct release", job.id)
            job.driver_id = None
            job.status = "confirmed"
            job.updated_at = _now()
            result["released"] = had
        if count_no_show:
            record_no_show(job, had, reason)
    job.hauler_confirmed_at = None
    job.hauler_confirmed_by = None
    try:
        from sameday import wave
        w = wave(job, va_name=va_name)
        result["waved"] = len(w.get("sent") or [])
        result["wave_reason"] = w.get("reason")
    except Exception:
        logger.exception("wave failed for %s after release", job.id)
    return result


def _page(subject, lines):
    """Tell a person on every configured private channel. Never raises."""
    body = "\n".join(lines)
    try:
        from ops_contacts import alert_sms
        alert_sms(subject + "\n" + body, why=subject)
    except Exception:
        logger.exception("alert sms failed: %s", subject)
    try:
        from desk_health import _send_alert
        _send_alert(subject, body)
    except Exception:
        logger.exception("alert fan-out failed: %s", subject)


# ---------------------------------------------------------------------------
# T-30 sweep
# ---------------------------------------------------------------------------
def preslot_check():
    """Jobs 25–35 minutes out with a hauler assigned and no movement."""
    now = _now()
    rows = (Job.query.filter(Job.driver_id.isnot(None),
                             Job.status.in_(ASSIGNED_STATUSES),
                             Job.scheduled_at >= now + timedelta(minutes=PRESLOT_MIN),
                             Job.scheduled_at <= now + timedelta(minutes=PRESLOT_MAX),
                             Job.preslot_alerted_at.is_(None),
                             Job.noshow_redispatched_at.is_(None))
            .all())
    acted = []
    for job in rows:
        code = job.confirmation_code or job.id[:8]
        c, hauler_name, hauler_phone = _hauler(job)
        try:
            if job.hauler_confirmed_at:
                # A confirmed hauler with no "on my way" yet is a judgement call.
                job.preslot_alerted_at = now
                db.session.commit()
                _page("Hauler not moving yet — {}".format(code), [
                    "{} confirmed for {} but has not started moving, 30 min out.".format(
                        hauler_name, code),
                    "Hauler: {}".format(hauler_phone or "no phone on file"),
                    "It is at the top of the desk work queue with a one-tap re-dispatch.",
                ])
                acted.append((code, "paged"))
            else:
                res = redispatch(job, "system", "unconfirmed_at_t30", count_no_show=True)
                job.preslot_alerted_at = now
                db.session.commit()
                _page("Re-dispatched — {} (hauler never confirmed)".format(code), [
                    "{} was assigned but never confirmed and has not moved, 30 min out.".format(
                        hauler_name),
                    "Released and offered to {} nearby hauler(s).".format(res.get("waved", 0)),
                    "Customer: {} · {}".format(_customer_first_name(job), (job.address or "")[:48]),
                ])
                acted.append((code, "redispatched"))
            audit("preslot_check", "job", job.id, {"hauler": job.noshow_contractor_id or job.driver_id,
                                                    "action": acted[-1][1]}, via="system")
        except Exception:
            logger.exception("preslot handling failed for %s", job.id)
            db.session.rollback()
    return acted


# ---------------------------------------------------------------------------
# Endpoints (desk)
# ---------------------------------------------------------------------------
def _ident(data):
    ident = desk_identity(data)
    return ident, (desk_va_name(data) or (ident.get("name") if ident else None) or "someone")


@confirm_bp.route("/api/va/confirm/list", methods=["POST"])
@_ratelimit
def confirm_list():
    data = request.get_json(silent=True) or {}
    ident, _ = _ident(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    rows = upcoming(int(data.get("hours") or CONFIRM_WINDOW_HOURS))
    return jsonify({"jobs": rows, "total": len(rows),
                    "unconfirmed": sum(1 for r in rows if not r["confirmed"])}), 200


@confirm_bp.route("/api/va/confirm/mark", methods=["POST"])
@_ratelimit
def confirm_mark():
    data = request.get_json(silent=True) or {}
    ident, va = _ident(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    job = db.session.get(Job, data.get("job_id") or "")
    if not job or not job.driver_id:
        return jsonify({"error": "That job has no hauler to confirm."}), 404
    note = (data.get("note") or "").strip()
    if data.get("confirmed", True):
        mark_confirmed(job, va, note)
        db.session.commit()
        audit("hauler_confirmed", "job", job.id, {"by": va, "hauler": job.driver_id, "note": note})
        return jsonify({"ok": True, "confirmed": True, "job_id": job.id}), 200
    # "Can't make it": release and re-dispatch now, from a person, not a timer.
    res = redispatch(job, "va", "hauler_declined_on_confirm", va_name=va, count_no_show=False)
    if note:
        job.hauler_confirm_note = note[:500]
    db.session.commit()
    audit("hauler_cant_make_it", "job", job.id, {"by": va, "released": res.get("released"),
                                                  "waved": res.get("waved"), "note": note})
    return jsonify({"ok": True, "confirmed": False, "job_id": job.id, "redispatch": res}), 200


@confirm_bp.route("/api/va/confirm/redispatch", methods=["POST"])
@_ratelimit
def confirm_redispatch():
    data = request.get_json(silent=True) or {}
    ident, va = _ident(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    job = db.session.get(Job, data.get("job_id") or "")
    if not job:
        return jsonify({"error": "Job not found."}), 404
    if job.status in MOVING_STATUSES:
        return jsonify({"error": "The hauler is already {} — call them instead.".format(
            job.status.replace("_", " "))}), 409
    res = redispatch(job, "va", (data.get("reason") or "redispatched_from_desk")[:80],
                     va_name=va, count_no_show=bool(data.get("no_show", True)))
    db.session.commit()
    audit("redispatch", "job", job.id, {"by": va, **{k: v for k, v in res.items() if k != "wave_reason"}})
    return jsonify({"ok": True, "job_id": job.id, "redispatch": res}), 200
