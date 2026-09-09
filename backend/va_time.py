"""VA time clock — clock in/out on the desk, hours by day / week / pay period.

The desk is passcode-shared, so the VA's typed name is the identity. Pay
periods are two weeks, anchored on VA_PAY_PERIOD_ANCHOR (default 2026-08-06,
the first period Tracy was paid on). All math is in Florida local time;
storage is naive UTC like the rest of the desk.

VA-facing (passcode):
  POST /api/va/time/clock   {action: "in"|"out", note?}  → current state
  POST /api/va/time/status                              → state + totals
  POST /api/va/time/hours   {days?: 30}                 → totals + shift list
Admin:
  GET  /api/admin/va-hours?days=30&va=Tracy              → same, all VAs
"""
from __future__ import annotations

import hmac
import logging
import os
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from models import db, CallAttempt, VaShift

try:
    from extensions import limiter
except Exception:  # pragma: no cover
    limiter = None

logger = logging.getLogger(__name__)
vatime_bp = Blueprint("vatime", __name__)

_ratelimit = (limiter.limit("240 per hour; 30 per minute") if limiter is not None
              else (lambda f: f))

MAX_SHIFT_HOURS = 12          # forgot to clock out → auto-close at this length
PERIOD_DAYS = 14


def _passcode_ok(supplied):
    expected = os.environ.get("TRIXIE_ASSISTANT_PASSCODE", "")
    if not expected:
        return False
    return hmac.compare_digest(str(supplied or ""), str(expected))


def _now_utc():
    return datetime.now(timezone.utc)


def _naive(dt):
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


def _local(dt_naive_utc):
    from timeutils import to_local
    return to_local(dt_naive_utc.replace(tzinfo=timezone.utc))


def _local_day_start_utc(local_dt):
    from timeutils import local_naive_to_utc
    d = local_dt.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    return _naive(local_naive_to_utc(d))


def _anchor_date():
    raw = os.environ.get("VA_PAY_PERIOD_ANCHOR", "2026-08-06").strip()
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return datetime(2026, 8, 6).date()


def period_bounds(now_utc=None):
    """(start_utc_naive, end_utc_naive, label) of the current two-week pay period."""
    from timeutils import local_naive_to_utc
    now_local = _local(_naive(now_utc or _now_utc()))
    today = now_local.date()
    anchor = _anchor_date()
    offset = (today - anchor).days % PERIOD_DAYS
    start_d = today - timedelta(days=offset)
    end_d = start_d + timedelta(days=PERIOD_DAYS)
    start = _naive(local_naive_to_utc(datetime.combine(start_d, datetime.min.time())))
    end = _naive(local_naive_to_utc(datetime.combine(end_d, datetime.min.time())))
    label = "{} – {}".format(start_d.strftime("%b %-d"), (end_d - timedelta(days=1)).strftime("%b %-d"))
    return start, end, label


def _overlap_seconds(shift, start, end):
    s = max(shift.started_at, start)
    e = min(shift.ended_at or _naive(_now_utc()), end)
    return max(0, int((e - s).total_seconds()))


def auto_close_stale(va_name):
    """A shift left open past MAX_SHIFT_HOURS is closed at that limit."""
    now = _naive(_now_utc())
    changed = False
    for sh in VaShift.query.filter_by(va_name=va_name, ended_at=None).all():
        if now - sh.started_at > timedelta(hours=MAX_SHIFT_HOURS):
            sh.ended_at = sh.started_at + timedelta(hours=MAX_SHIFT_HOURS)
            sh.auto_closed = True
            changed = True
    if changed:
        db.session.commit()


def open_shift(va_name):
    return (VaShift.query.filter_by(va_name=va_name, ended_at=None)
            .order_by(VaShift.started_at.desc()).first())


def totals_for(va_name):
    now = _naive(_now_utc())
    now_local = _local(now)
    day_start = _local_day_start_utc(now_local)
    week_start = _local_day_start_utc(now_local - timedelta(days=now_local.weekday()))
    p_start, p_end, p_label = period_bounds()
    since = min(week_start, p_start)
    shifts = VaShift.query.filter(VaShift.va_name == va_name,
                                  db.or_(VaShift.ended_at.is_(None), VaShift.ended_at >= since)).all()
    today = sum(_overlap_seconds(s, day_start, now) for s in shifts)
    week = sum(_overlap_seconds(s, week_start, now) for s in shifts)
    period = sum(_overlap_seconds(s, p_start, min(p_end, now)) for s in shifts)
    return {"today_seconds": today, "week_seconds": week, "period_seconds": period,
            "period_label": p_label,
            "period_start": p_start.isoformat(), "period_end": p_end.isoformat()}


def _calls_during(shift):
    end = shift.ended_at or _naive(_now_utc())
    q = CallAttempt.query.filter(CallAttempt.created_at >= shift.started_at,
                                 CallAttempt.created_at <= end,
                                 CallAttempt.outcome != "skip")
    if shift.va_name:
        q = q.filter(db.or_(CallAttempt.va_name == shift.va_name, CallAttempt.va_name.is_(None)))
    return q.count()


def state_payload(va_name):
    sh = open_shift(va_name)
    d = totals_for(va_name)
    d["on_clock"] = sh is not None
    d["shift"] = sh.to_dict() if sh else None
    d["va_name"] = va_name
    return d


def _va_name(data):
    return (data.get("va_name") or "").strip()[:80]


@vatime_bp.route("/api/va/time/clock", methods=["POST"])
@_ratelimit
def clock():
    data = request.get_json(silent=True) or {}
    if not _passcode_ok(data.get("code")):
        return jsonify({"error": "That code didn't work."}), 401
    va = _va_name(data)
    if not va:
        return jsonify({"error": "Type your name on the desk first so the hours are yours."}), 400
    action = (data.get("action") or "").strip().lower()
    auto_close_stale(va)
    sh = open_shift(va)
    now = _naive(_now_utc())
    if action == "in":
        if sh:
            return jsonify(dict(state_payload(va), already=True)), 200
        db.session.add(VaShift(va_name=va, started_at=now,
                               note=(data.get("note") or "").strip()[:300] or None))
        db.session.commit()
        return jsonify(state_payload(va)), 200
    if action == "out":
        if not sh:
            return jsonify(dict(state_payload(va), already=True)), 200
        sh.ended_at = now
        note = (data.get("note") or "").strip()[:300]
        if note:
            sh.note = note
        db.session.commit()
        return jsonify(dict(state_payload(va), closed=sh.to_dict())), 200
    return jsonify({"error": "action must be 'in' or 'out'."}), 400


@vatime_bp.route("/api/va/time/status", methods=["POST"])
@_ratelimit
def status():
    data = request.get_json(silent=True) or {}
    if not _passcode_ok(data.get("code")):
        return jsonify({"error": "That code didn't work."}), 401
    va = _va_name(data)
    if not va:
        return jsonify({"on_clock": False, "va_name": "", "today_seconds": 0,
                        "week_seconds": 0, "period_seconds": 0, "period_label": period_bounds()[2]}), 200
    auto_close_stale(va)
    return jsonify(state_payload(va)), 200


def hours_report(va_name=None, days=30):
    since = _naive(_now_utc()) - timedelta(days=min(max(int(days or 30), 1), 120))
    q = VaShift.query.filter(db.or_(VaShift.ended_at.is_(None), VaShift.ended_at >= since))
    if va_name:
        q = q.filter(VaShift.va_name == va_name)
    shifts = q.order_by(VaShift.started_at.desc()).limit(200).all()
    rows = []
    for sh in shifts:
        d = sh.to_dict()
        d["calls"] = _calls_during(sh)
        d["day"] = _local(sh.started_at).strftime("%a %b %-d")
        d["start_local"] = _local(sh.started_at).strftime("%-I:%M %p")
        d["end_local"] = _local(sh.ended_at).strftime("%-I:%M %p") if sh.ended_at else None
        rows.append(d)
    names = sorted({sh.va_name for sh in shifts})
    return {"shifts": rows, "vas": names,
            "totals": {n: totals_for(n) for n in (names if not va_name else [va_name])}}


@vatime_bp.route("/api/va/time/hours", methods=["POST"])
@_ratelimit
def hours():
    data = request.get_json(silent=True) or {}
    if not _passcode_ok(data.get("code")):
        return jsonify({"error": "That code didn't work."}), 401
    va = _va_name(data)
    if not va:
        return jsonify({"error": "Type your name on the desk first."}), 400
    auto_close_stale(va)
    rep = hours_report(va, data.get("days") or 30)
    rep.update(state_payload(va))
    return jsonify(rep), 200


@vatime_bp.route("/api/admin/va-hours", methods=["GET"])
def admin_hours():
    from va_calls import require_admin

    @require_admin
    def _inner(user_id):
        return jsonify(hours_report(request.args.get("va") or None,
                                    request.args.get("days") or 30)), 200
    return _inner()
