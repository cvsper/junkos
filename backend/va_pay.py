"""VA pay statement — hours, hauler sign-ups, and bookings for a pay period.

The owner was working pay out by hand from three places every two weeks:
the time clock, the #signups channel, and the job list. This puts the
statement on the desk so the VA sees the same number the owner pays.

Money is derived at read time, never stored. The rules live in DeskSetting
so a manager can change them from the desk:

  va_signup_bonus       dollars per hauler the VA called who is now onboarded
  va_booking_bonus_pct  share of a booked job's price that goes to the VA
  va_booking_bonus_min  floor on that share, per booking
  va_booking_bonus_max  ceiling on that share, per booking

A sign-up counts when a hauler account exists for a number the VA logged a
call to before they signed up, and it is paid in the period the account was created. A booking
counts when the job the VA booked is completed; until then it shows as
pending so nobody is paid for a job that cancels.

VA-facing (passcode / desk JWT):
  POST /api/va/time/pay        {periods_back?: 0, va?}   → statement
  POST /api/va/time/pay-rules  {}                        → rules (manager sets)
Admin:
  GET  /api/admin/va-pay?va=Tracy&periods_back=0
"""
from __future__ import annotations

import logging
import os
import re
from datetime import timedelta

from flask import Blueprint, jsonify, request

from desk_auth import desk_identity, desk_va_name, audit, is_manager
from models import db, CallAttempt, CallProspect, Contractor, Job, User, VaDispatchAction, VaShift
from va_time import (hourly_rate, period_bounds, pay_overlap_seconds, pay_cap_seconds,
                     _naive, _now_utc, _local)

logger = logging.getLogger(__name__)
vapay_bp = Blueprint("vapay", __name__)

WIN_OUTCOMES = ("interested", "sent_link", "vendor_listed", "converted")
COMPLETED_STATUSES = ("completed", "paid")
DEAD_STATUSES = ("cancelled", "canceled", "refunded", "no_show")

_DEFAULTS = {
    "va_signup_bonus": os.environ.get("VA_SIGNUP_BONUS", "1"),
    "va_booking_bonus_pct": os.environ.get("VA_BOOKING_BONUS_PCT", "0.10"),
    "va_booking_bonus_min": os.environ.get("VA_BOOKING_BONUS_MIN", "5"),
    "va_booking_bonus_max": os.environ.get("VA_BOOKING_BONUS_MAX", "50"),
}


def _digits(s):
    return re.sub(r"\D", "", s or "")[-10:]


def _setting(key):
    from models import DeskSetting
    try:
        raw = DeskSetting.get(key)
    except Exception:
        raw = None
    raw = raw if raw not in (None, "") else _DEFAULTS[key]
    try:
        return float(raw)
    except (TypeError, ValueError):
        logger.warning("ignoring unparseable %s=%r", key, raw)
        return float(_DEFAULTS[key])


def pay_rules():
    return {
        "signup_bonus": round(_setting("va_signup_bonus"), 2),
        "booking_pct": round(_setting("va_booking_bonus_pct"), 4),
        "booking_min": round(_setting("va_booking_bonus_min"), 2),
        "booking_max": round(_setting("va_booking_bonus_max"), 2),
    }


def set_pay_rules(data):
    from models import DeskSetting
    keys = {"signup_bonus": "va_signup_bonus", "booking_pct": "va_booking_bonus_pct",
            "booking_min": "va_booking_bonus_min", "booking_max": "va_booking_bonus_max"}
    changed = {}
    for field, key in keys.items():
        if field in data and data[field] is not None:
            val = float(data[field])
            if val < 0:
                raise ValueError(field + " cannot be negative")
            if field == "booking_pct" and val > 1:
                val = val / 100.0          # "10" means 10%
            DeskSetting.put(key, "{:.4f}".format(val))
            changed[field] = val
    return changed


def booking_bonus(job_total, rules=None):
    r = rules or pay_rules()
    share = float(job_total or 0) * r["booking_pct"]
    return round(min(max(share, r["booking_min"]), r["booking_max"]), 2)


def _va_match(col, va_name):
    return db.func.lower(col) == (va_name or "").strip().lower()


def _win_prospect_ids(va_name):
    """Prospects this VA worked, with the time she first logged a call.

    Any logged call counts, not only a logged win: the desk writes the win
    itself (as "system") when the hauler creates an account, so a yes she got
    on a call she logged as voicemail or no-answer is still her sign-up.
    """
    rows = (db.session.query(CallAttempt.prospect_id, db.func.min(CallAttempt.created_at))
            .filter(_va_match(CallAttempt.va_name, va_name),
                    CallAttempt.outcome != "skip")
            .group_by(CallAttempt.prospect_id).all())
    return {pid: first for pid, first in rows}


def signups_for(va_name, start, end):
    """Haulers the VA called who got an account inside [start, end)."""
    wins = _win_prospect_ids(va_name)
    if not wins:
        return []
    made = (db.session.query(Contractor, User)
            .join(User, User.id == Contractor.user_id)
            .filter(Contractor.created_at >= start, Contractor.created_at < end,
                    User.phone.isnot(None)).all())
    if not made:
        return []
    by_digits = {}
    for c, u in made:
        d = _digits(u.phone)
        if len(d) == 10 and d not in by_digits:
            by_digits[d] = (c, u)
    if not by_digits:
        return []
    prospects = (CallProspect.query
                 .filter(CallProspect.id.in_(list(wins.keys())))
                 .filter(db.or_(CallProspect.phone_digits.in_(list(by_digits.keys())),
                                *[CallProspect.direct_phone.like("%" + d[-7:]) for d in by_digits]))
                 .all())
    out, seen = [], set()
    for p in prospects:
        hit = by_digits.get(p.phone_digits) or by_digits.get(_digits(p.direct_phone))
        if not hit:
            continue
        c, u = hit
        if c.id in seen:
            continue
        first_win = wins.get(p.id)
        if first_win and c.created_at and first_win > c.created_at + timedelta(days=1):
            continue      # they signed up before she ever reached them
        seen.add(c.id)
        out.append({
            "company": p.company,
            "hauler": (u.name if hasattr(u, "name") and u.name else None),
            "phone": p.phone_digits,
            "onboarded_at": c.created_at.isoformat() if c.created_at else None,
            "day": _local(c.created_at).strftime("%a %b %-d") if c.created_at else None,
            "approved": (c.approval_status == "approved"),
            "first_win_at": first_win.isoformat() if first_win else None,
        })
    out.sort(key=lambda r: r["onboarded_at"] or "")
    return out


def bookings_for(va_name, start, end, rules=None):
    """Jobs the VA booked, created inside [start, end)."""
    rules = rules or pay_rules()
    job_ids = set()
    wins = _win_prospect_ids(va_name)
    if wins:
        for p in (CallProspect.query.filter(CallProspect.id.in_(list(wins.keys())),
                                            CallProspect.job_id.isnot(None)).all()):
            job_ids.add(p.job_id)
    for a in (VaDispatchAction.query
              .filter(_va_match(VaDispatchAction.va_name, va_name),
                      VaDispatchAction.action == "log_job").all()):
        job_ids.add(a.job_id)
    if not job_ids:
        return []
    jobs = Job.query.filter(Job.id.in_(list(job_ids)),
                            Job.created_at >= start, Job.created_at < end).all()
    out = []
    for j in jobs:
        status = (j.status or "").lower()
        dead = status in DEAD_STATUSES or bool(j.cancelled_at)
        done = status in COMPLETED_STATUSES or bool(j.completed_at)
        bonus = 0.0 if dead else booking_bonus(j.total_price, rules)
        out.append({
            "job_id": j.id, "code": j.confirmation_code,
            "customer": getattr(getattr(j, "customer", None), "name", None),
            "address": j.address, "value": round(float(j.total_price or 0), 2),
            "status": j.status, "booked_at": j.created_at.isoformat() if j.created_at else None,
            "day": _local(j.created_at).strftime("%a %b %-d") if j.created_at else None,
            "bonus": bonus,
            "state": "cancelled" if dead else ("payable" if done else "pending"),
        })
    out.sort(key=lambda r: r["booked_at"] or "")
    return out


def _shift_rows(va_name, start, end):
    shifts = (VaShift.query.filter(VaShift.va_name == va_name, VaShift.started_at < end,
                                   db.or_(VaShift.ended_at.is_(None), VaShift.ended_at >= start))
              .order_by(VaShift.started_at.asc()).all())
    now = _naive(_now_utc())
    rows, paid_secs, unpaid_secs, capped_secs = [], 0, 0, 0
    for sh in shifts:
        raw = max(0, int((min(sh.ended_at or now, end) - max(sh.started_at, start)).total_seconds()))
        pay_secs = pay_overlap_seconds(sh, start, end)
        capped = sh.auto_closed and pay_secs < raw
        if sh.unpaid:
            unpaid_secs += raw
        else:
            paid_secs += pay_secs
            if capped:
                capped_secs += raw - pay_secs
        rows.append({
            "id": sh.id, "day": _local(sh.started_at).strftime("%a %b %-d"),
            "start_local": _local(sh.started_at).strftime("%-I:%M %p"),
            "end_local": _local(sh.ended_at).strftime("%-I:%M %p") if sh.ended_at else None,
            "hours": round(raw / 3600.0, 2), "paid_hours": 0.0 if sh.unpaid else round(pay_secs / 3600.0, 2),
            "unpaid": bool(sh.unpaid), "unpaid_reason": sh.unpaid_reason,
            "auto_closed": bool(sh.auto_closed), "capped": bool(capped and not sh.unpaid),
            "open": sh.ended_at is None, "note": sh.note,
        })
    return rows, paid_secs, unpaid_secs, capped_secs


def pay_statement(va_name, periods_back=0):
    start, end, label = period_bounds(periods_back=periods_back)
    rate = hourly_rate(va_name)
    rules = pay_rules()
    shifts, paid_secs, unpaid_secs, capped_secs = _shift_rows(va_name, start, end)
    hours = round(paid_secs / 3600.0, 2)
    hours_pay = round(hours * rate, 2) if rate else None

    signups = signups_for(va_name, start, end)
    signup_pay = round(len(signups) * rules["signup_bonus"], 2)

    bookings = bookings_for(va_name, start, end, rules)
    booking_pay = round(sum(b["bonus"] for b in bookings if b["state"] == "payable"), 2)
    booking_pending = round(sum(b["bonus"] for b in bookings if b["state"] == "pending"), 2)

    total = round((hours_pay or 0) + signup_pay + booking_pay, 2)
    return {
        "va_name": va_name,
        "period_label": label, "period_start": start.isoformat(), "period_end": end.isoformat(),
        "periods_back": int(periods_back or 0),
        "closed": _naive(_now_utc()) >= end,
        "hourly_rate": rate, "hours": hours, "hours_pay": hours_pay,
        "unpaid_hours": round(unpaid_secs / 3600.0, 2),
        "capped_hours": round(capped_secs / 3600.0, 2),
        "auto_close_pay_hours": round(pay_cap_seconds() / 3600.0, 2),
        "shifts": shifts,
        "rules": rules,
        "signups": signups, "signup_count": len(signups), "signup_pay": signup_pay,
        "bookings": bookings,
        "booking_count": sum(1 for b in bookings if b["state"] != "cancelled"),
        "booking_pay": booking_pay, "booking_pending": booking_pending,
        "total": total,
        "rate_set": bool(rate),
    }


def _periods_back(data):
    try:
        return max(0, min(int(data.get("periods_back", 0) or 0), 12))
    except (TypeError, ValueError):
        return 0


@vapay_bp.route("/api/va/time/pay", methods=["POST"])
def va_pay():
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    mine = desk_va_name(data)
    who = (data.get("va") or mine or "").strip()
    if not who:
        return jsonify({"error": "Type your name on the desk first so the pay is yours."}), 400
    if who.lower() != (mine or "").lower() and not is_manager(ident):
        return jsonify({"error": "You can only see your own pay."}), 403
    from va_time import auto_close_stale
    auto_close_stale(who)
    return jsonify(pay_statement(who, _periods_back(data))), 200


@vapay_bp.route("/api/va/time/team-pay", methods=["POST"])
def va_team_pay():
    """Every VA's statement for a period — the owner's view on /va/manager."""
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    if ident.get("via") == "jwt" and not is_manager(ident):
        return jsonify({"error": "Everyone's pay needs a manager login."}), 403
    from va_time import auto_close_stale
    back = _periods_back(data)
    start, end, label = period_bounds(periods_back=back)
    names = sorted({(n or "").strip() for (n,) in db.session.query(VaShift.va_name)
                    .filter(VaShift.started_at < end,
                            db.or_(VaShift.ended_at.is_(None), VaShift.ended_at >= start))
                    .distinct().all() if (n or "").strip()}, key=str.lower)
    out = []
    for n in names:
        auto_close_stale(n)
        st = pay_statement(n, back)
        if st["rate_set"] or st["total"]:
            out.append(st)          # a clock-in with no wage and nothing earned is not a VA
    return jsonify({"period_label": label, "periods_back": back,
                    "closed": _naive(_now_utc()) >= end, "rules": pay_rules(),
                    "vas": out, "total": round(sum(v["total"] for v in out), 2)}), 200


@vapay_bp.route("/api/va/time/pay-rules", methods=["POST"])
def va_pay_rules():
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    wants_change = any(k in data for k in ("signup_bonus", "booking_pct", "booking_min", "booking_max"))
    if wants_change:
        if not is_manager(ident):
            return jsonify({"error": "Only a manager can change pay rules."}), 403
        try:
            changed = set_pay_rules(data)
        except (TypeError, ValueError) as exc:
            return jsonify({"error": "Rules must be positive numbers ({}).".format(exc)}), 400
        audit("va_pay_rules_set", "desk", "pay", changed)
        return jsonify({"rules": pay_rules(), "saved": True}), 200
    return jsonify({"rules": pay_rules()}), 200


@vapay_bp.route("/api/admin/va-pay", methods=["GET"])
def admin_va_pay():
    from va_calls import require_admin

    @require_admin
    def _inner(user_id):
        who = (request.args.get("va") or "").strip()
        if not who:
            return jsonify({"error": "Pass ?va=<name>."}), 400
        try:
            back = max(0, min(int(request.args.get("periods_back", 0) or 0), 12))
        except (TypeError, ValueError):
            back = 0
        return jsonify(pay_statement(who, back)), 200
    return _inner()
