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

from desk_auth import desk_identity, desk_va_name, audit, is_manager
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

# Hourly pay. Stored per VA in DeskSetting ("va_rate:<name>"), falling back to
# "va_rate:default" then VA_DEFAULT_HOURLY_RATE. Hours were already tracked;
# without a rate the owner was doing the arithmetic by hand every period.
DEFAULT_HOURLY_RATE = float(os.environ.get("VA_DEFAULT_HOURLY_RATE", "0") or 0)


def _rate_key(va_name):
    return "va_rate:" + (va_name or "").strip().lower()


def hourly_rate(va_name):
    """Dollars per hour for this VA. 0 means 'not set' — never guess a wage."""
    from models import DeskSetting
    for key in (_rate_key(va_name), "va_rate:default"):
        try:
            raw = DeskSetting.get(key)
        except Exception:
            raw = None
        if raw:
            try:
                return round(float(raw), 4)
            except (TypeError, ValueError):
                logger.warning("ignoring unparseable %s=%r", key, raw)
    return DEFAULT_HOURLY_RATE


def set_hourly_rate(va_name, rate):
    from models import DeskSetting
    rate = round(float(rate), 4)
    if rate < 0:
        raise ValueError("rate cannot be negative")
    DeskSetting.put(_rate_key(va_name), "{:.4f}".format(rate))
    return rate


def _with_pay(totals, va_name):
    """Add pay figures beside the second counts. Money is derived, never stored."""
    rate = hourly_rate(va_name)
    totals["hourly_rate"] = rate
    for span in ("today", "week", "period"):
        hours = (totals.get(span + "_seconds") or 0) / 3600.0
        totals[span + "_hours"] = round(hours, 2)
        totals[span + "_pay"] = round(hours * rate, 2) if rate else None
    return totals


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


def period_bounds(now_utc=None, periods_back=0):
    """(start_utc_naive, end_utc_naive, label) of a two-week pay period.

    ``periods_back=1`` is the period before the current one, and so on.
    """
    from timeutils import local_naive_to_utc
    now_local = _local(_naive(now_utc or _now_utc()))
    today = now_local.date()
    anchor = _anchor_date()
    offset = (today - anchor).days % PERIOD_DAYS
    start_d = today - timedelta(days=offset + PERIOD_DAYS * max(0, int(periods_back or 0)))
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
    return _with_pay({"today_seconds": today, "week_seconds": week, "period_seconds": period,
                      "period_label": p_label,
                      "period_start": p_start.isoformat(), "period_end": p_end.isoformat()},
                     va_name)


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
    return desk_va_name(data)


@vatime_bp.route("/api/va/time/clock", methods=["POST"])
@_ratelimit
def clock():
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
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
        audit("clock_in", "va", va)
        return jsonify(state_payload(va)), 200
    if action == "out":
        if not sh:
            return jsonify(dict(state_payload(va), already=True)), 200
        sh.ended_at = now
        note = (data.get("note") or "").strip()[:300]
        if note:
            sh.note = note
        db.session.commit()
        from crm import end_of_shift_report; end_of_shift_report(va, sh)  # CRM (Phase 3)
        audit("clock_out", "shift", sh.id, {"seconds": sh.seconds})
        return jsonify(dict(state_payload(va), closed=sh.to_dict())), 200
    return jsonify({"error": "action must be 'in' or 'out'."}), 400


@vatime_bp.route("/api/va/time/status", methods=["POST"])
@_ratelimit
def status():
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
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
        rate = hourly_rate(sh.va_name)
        d["hours"] = round((d.get("seconds") or 0) / 3600.0, 2)
        d["pay"] = round(d["hours"] * rate, 2) if rate else None
        rows.append(d)
    names = sorted({sh.va_name for sh in shifts})
    return {"shifts": rows, "vas": names,
            "totals": {n: totals_for(n) for n in (names if not va_name else [va_name])}}


@vatime_bp.route("/api/va/time/hours", methods=["POST"])
@_ratelimit
def hours():
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    va = _va_name(data)
    if not va:
        return jsonify({"error": "Type your name on the desk first."}), 400
    auto_close_stale(va)
    rep = hours_report(va, data.get("days") or 30)
    rep.update(state_payload(va))
    return jsonify(rep), 200


@vatime_bp.route("/api/va/time/team", methods=["POST"])
@_ratelimit
def team():
    """Everyone's hours (desk passcode) — the owner's view from the same panel."""
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    if ident["via"] == "jwt" and not is_manager(ident):
        return jsonify({"error": "Everyone's hours need a manager login."}), 403
    for name in {sh.va_name for sh in VaShift.query.filter_by(ended_at=None).all()}:
        auto_close_stale(name)
    return jsonify(hours_report(None, data.get("days") or 45)), 200


@vatime_bp.route("/api/admin/va-hours", methods=["GET"])
def admin_hours():
    from va_calls import require_admin

    @require_admin
    def _inner(user_id):
        return jsonify(hours_report(request.args.get("va") or None,
                                    request.args.get("days") or 30)), 200
    return _inner()


@vatime_bp.route("/api/va/time/rate", methods=["POST"])
@_ratelimit
def rate():
    """Read or set a VA's hourly rate. Reading is open to the desk so a VA can
    see their own pay; setting is manager-only and audited."""
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    who = (data.get("va") or _va_name(data) or "").strip()
    if not who:
        return jsonify({"error": "Which VA?"}), 400
    if "rate" in data and data.get("rate") is not None:
        if not is_manager(ident):
            return jsonify({"error": "Only a manager can change pay."}), 403
        try:
            new_rate = set_hourly_rate(who, data["rate"])
        except (TypeError, ValueError) as exc:
            return jsonify({"error": "Rate must be a positive number of dollars per hour."}), 400
        audit("va_rate_set", "va", who, {"rate": new_rate})
        return jsonify({"va": who, "hourly_rate": new_rate, "saved": True}), 200
    return jsonify({"va": who, "hourly_rate": hourly_rate(who)}), 200


# ---------------------------------------------------------------------------
# Reconstructing hours from call activity (pre-clock periods)
# ---------------------------------------------------------------------------
# The time clock launched 2026-09-09, but the VA had been calling since
# August. Those pay periods have no shifts — only call logs. Rather than
# guess a wage from dials-per-hour, rebuild each worked day from the first and
# last logged call, which is evidence the desk already holds.
#
# This is an ESTIMATE and is labelled as one: the span between first and last
# call can overstate a split day (a morning and an evening block with a long
# gap read as one long shift) and understates the wrap-up after the final
# call. GAP_SPLIT_MINUTES breaks a day at any gap longer than the threshold so
# a lunch break or a split shift is not billed.
GAP_SPLIT_MINUTES = 90
TAIL_MINUTES = 5          # a call still takes time after the last one is logged


def reconstruct_days(va_name, start_utc, end_utc, gap_minutes=GAP_SPLIT_MINUTES):
    """Worked blocks rebuilt from CallAttempt timestamps. Returns per-day rows."""
    q = (CallAttempt.query
         .filter(CallAttempt.created_at >= start_utc, CallAttempt.created_at < end_utc,
                 CallAttempt.outcome != "skip")
         .order_by(CallAttempt.created_at.asc()))
    if va_name:
        q = q.filter(db.or_(CallAttempt.va_name == va_name, CallAttempt.va_name.is_(None)))
    by_day = {}
    for row in q.all():
        by_day.setdefault(_local(row.created_at).strftime("%Y-%m-%d"), []).append(row.created_at)

    days, gap = [], timedelta(minutes=gap_minutes)
    for day in sorted(by_day):
        stamps = by_day[day]
        blocks, start, prev = [], stamps[0], stamps[0]
        for ts in stamps[1:]:
            if ts - prev > gap:
                blocks.append((start, prev))
                start = ts
            prev = ts
        blocks.append((start, prev))
        seconds = sum((b - a).total_seconds() + TAIL_MINUTES * 60 for a, b in blocks)
        days.append({
            "day": day,
            "day_label": _local(stamps[0]).strftime("%a %b %-d"),
            "calls": len(stamps),
            "first_local": _local(stamps[0]).strftime("%-I:%M %p"),
            "last_local": _local(stamps[-1]).strftime("%-I:%M %p"),
            "blocks": len(blocks),
            "seconds": int(seconds),
            "hours": round(seconds / 3600.0, 2),
        })
    return days


def reconstructed_period(va_name, periods_back=1):
    """Estimated hours + pay for a pay period that predates the time clock."""
    p_start, p_end, label = period_bounds(periods_back=periods_back)
    days = reconstruct_days(va_name, p_start, p_end)
    seconds = sum(d["seconds"] for d in days)
    hours = round(seconds / 3600.0, 2)
    rate = hourly_rate(va_name)
    logged = sum(_overlap_seconds(sh, p_start, p_end)
                 for sh in VaShift.query.filter(VaShift.va_name == va_name).all())
    return {
        "va_name": va_name, "period_label": label,
        "period_start": p_start.isoformat(), "period_end": p_end.isoformat(),
        "estimated": True,
        "days": days, "days_worked": len(days),
        "calls": sum(d["calls"] for d in days),
        "seconds": seconds, "hours": hours,
        "hourly_rate": rate, "pay": round(hours * rate, 2) if rate else None,
        "clocked_seconds": int(logged),
        "clocked_hours": round(logged / 3600.0, 2),
        "basis": ("first to last logged call each day, split at gaps over "
                  "{} minutes, plus {} minutes after the last call"
                  .format(GAP_SPLIT_MINUTES, TAIL_MINUTES)),
    }


@vatime_bp.route("/api/va/time/reconstruct", methods=["POST"])
@_ratelimit
def reconstruct():
    """Estimated hours for a pay period with no clock records (pre-2026-09-09)."""
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    who = (data.get("va") or _va_name(data) or "").strip()
    if not who:
        return jsonify({"error": "Which VA?"}), 400
    try:
        back = max(0, min(int(data.get("periods_back", 1)), 12))
    except (TypeError, ValueError):
        back = 1
    return jsonify(reconstructed_period(who, back)), 200
