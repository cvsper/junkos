"""Drill-down behind every number on the analytics pages.

A KPI is only useful if you can see what's inside it. POST
/api/va/analytics/detail takes the metric a number represents and the same
window/VA scope the page used, and returns the rows that made it up —
each with when it happened, who it was, what came of it, and a link to
the record on the desk.

    POST /api/va/analytics/detail  {metric, period|days, va, limit, offset}

Metrics (all honour the window; VA-scoped ones honour `va`):
  inbound:  calls, human, maya, missed, in_hours, after_hours, booked_calls,
            quoted_calls, source:<desk|google|meta|maya|unknown>,
            disposition:<...>, outcome:<...>
  speed:    leads, leads_touched, leads_untouched, leads_auto_texted
  outbound: dials, connects, interested, wins, callbacks
  manager:  jobs, paid, completed, cancelled, revenue, dump_fees, refunded,
            channel:<phone|web|maya|waitlist>, assigned, confirmed,
            unconfirmed, no_shows, hauler_completed, maya_calls, maya_quoted,
            maya_booked, maya_lost, shifts, classes
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from analytics import (_attempts, _local, _ratelimit, _sees_everyone, window, CONNECT_OUTCOMES,
                       INTERESTED_OUTCOMES, WIN_OUTCOMES)
from desk_auth import desk_identity
from models import db, Job, Payment, CallLog, CallProspect, Contractor, User, VaShift
from models_inbound import InboundCall
from models_leads import LeadTouch

logger = logging.getLogger(__name__)
drill_bp = Blueprint("analytics_drill", __name__)

MAX_LIMIT = 300
SOURCE_LABEL = {"desk": "Desk line", "google": "Google LSA", "meta": "Meta ads", "maya": "Maya", None: "Unknown", "": "Unknown"}
DISP_LABEL = {"answered_by_human": "Answered by a person", "to_maya": "Went to Maya", "voicemail": "Voicemail",
              "missed": "Missed", "ringing": "Unknown"}
OUTCOME_LABEL = {"booked": "Booked", "quoted": "Quoted", "callback": "Callback set", "not_fit": "Not a fit",
                 "spam": "Spam", "none": "No outcome logged", "interested": "Interested", "sent_link": "Sent the link",
                 "vendor_listed": "On their vendor list", "converted": "Converted", "not_interested": "Not interested",
                 "no_answer": "No answer", "voicemail": "Voicemail", "bad_number": "Bad number", "skip": "Skipped",
                 "do_not_call": "Asked not to be called"}


def _when(dt):
    if not dt:
        return None, None
    loc = _local(dt)
    return dt.isoformat() + "Z", loc.strftime("%a %b %-d, %-I:%M %p")


def _pretty(d):
    d = "".join(ch for ch in (d or "") if ch.isdigit())
    if len(d) == 11 and d[0] == "1":
        d = d[1:]
    return "({}) {}-{}".format(d[:3], d[3:6], d[6:]) if len(d) == 10 else (d or None)


def _row(at, what, who=None, result=None, note=None, link=None, amount=None, **extra):
    iso, label = _when(at)
    r = {"at": iso, "when": label, "what": what, "who": who, "result": result, "note": note, "link": link, "amount": amount}
    r.update(extra)
    return r


def _customer(job):
    for a in ("customer_name",):
        v = getattr(job, a, None)
        if v:
            return v
    u = db.session.get(User, job.customer_id) if getattr(job, "customer_id", None) else None
    return (u.name if u else None) or "Customer"


def _hauler_name(cid):
    if not cid:
        return None
    c = db.session.get(Contractor, cid)
    u = db.session.get(User, c.user_id) if c else None
    return (u.name if u else None) or ("Hauler " + cid[:6])


# ---------------------------------------------------------------------------
# row builders
# ---------------------------------------------------------------------------

def inbound_rows(metric, start, end, va):
    q = InboundCall.query.filter(InboundCall.created_at >= start, InboundCall.created_at < end)
    if va:
        q = q.filter(db.or_(InboundCall.answered_by == va, InboundCall.va_name == va))
    key, _, arg = metric.partition(":")
    if key == "human":
        q = q.filter(InboundCall.disposition == "answered_by_human")
    elif key == "maya":
        q = q.filter(InboundCall.disposition == "to_maya")
    elif key == "missed":
        q = q.filter(InboundCall.disposition.in_(("missed", "voicemail")))
    elif key == "in_hours":
        q = q.filter(InboundCall.in_hours == 1)
    elif key == "after_hours":
        q = q.filter(InboundCall.in_hours == 0)
    elif key == "booked_calls":
        q = q.filter(InboundCall.outcome == "booked")
    elif key == "quoted_calls":
        q = q.filter(InboundCall.outcome == "quoted")
    elif key == "source":
        q = q.filter(InboundCall.source.is_(None)) if arg == "unknown" else q.filter(InboundCall.source == arg)
    elif key == "disposition":
        q = q.filter(InboundCall.disposition == arg)
    elif key == "outcome":
        q = q.filter(InboundCall.outcome == arg)
    rows = q.order_by(InboundCall.created_at.desc()).all()
    out = []
    for r in rows:
        result = DISP_LABEL.get(r.disposition, r.disposition)
        if r.outcome and r.outcome != "none":
            result += " → " + OUTCOME_LABEL.get(r.outcome, r.outcome)
        out.append(_row(r.created_at, _pretty(r.phone_digits) or "Unknown number",
                        who=r.answered_by or r.va_name or ("Maya" if r.disposition == "to_maya" else None),
                        result=result, note=(r.outcome_note or r.notes or None),
                        link="/va/calls?q=" + (r.phone_digits or ""), amount=r.quote_total,
                        source=SOURCE_LABEL.get(r.source, r.source), duration=r.duration, job_id=r.job_id))
    return out


def speed_rows(metric, start, end, va):
    q = LeadTouch.query.filter(LeadTouch.created_at >= start, LeadTouch.created_at < end)
    if va:
        q = q.filter(LeadTouch.touched_by == va)
    if metric == "leads_touched":
        q = q.filter(LeadTouch.touched_at.isnot(None))
    elif metric == "leads_untouched":
        q = q.filter(LeadTouch.touched_at.is_(None))
    elif metric == "leads_auto_texted":
        q = q.filter(LeadTouch.auto_text_at.isnot(None))
    rows = q.order_by(LeadTouch.created_at.desc()).all()
    refs = [r.ref_id for r in rows if r.kind == "call"]
    born = {}
    if refs:
        for c in InboundCall.query.filter(db.or_(InboundCall.call_sid.in_(refs), InboundCall.id.in_(refs))).all():
            born[c.call_sid] = c.created_at
            born[c.id] = c.created_at
    out = []
    for r in rows:
        opened = (born.get(r.ref_id) if r.kind == "call" else None) or r.created_at
        secs = int((r.touched_at - opened).total_seconds()) if r.touched_at and opened else None
        if r.touched_at:
            result = "Touched by {} after {}".format(r.touched_by or "someone", _fmt_secs(secs))
        else:
            result = "Never touched" + (" · auto-text sent" if r.auto_text_at else "")
        out.append(_row(opened, _pretty(r.phone_digits) or r.ref_id, who=r.touched_by, result=result,
                        note=(r.outcome or None) and OUTCOME_LABEL.get(r.outcome, r.outcome),
                        link="/va/calls?q=" + (r.phone_digits or ""), source=SOURCE_LABEL.get(r.source, r.source),
                        kind=r.kind, seconds=secs))
    return out


def _fmt_secs(s):
    if s is None:
        return "—"
    if s < 90:
        return "{}s".format(s)
    if s < 3600:
        return "{} min".format(round(s / 60))
    return "{:.1f} h".format(s / 3600)


def outbound_rows(metric, start, end, va):
    want = {"dials": None, "connects": CONNECT_OUTCOMES, "interested": INTERESTED_OUTCOMES,
            "wins": WIN_OUTCOMES, "callbacks": ("callback",)}.get(metric)
    out = []
    for a, p in _attempts(start, end, va):
        if want is not None and a.outcome not in want:
            continue
        out.append(_row(a.created_at, p.company or "Unknown business", who=a.va_name,
                        result=OUTCOME_LABEL.get(a.outcome, a.outcome), note=a.note,
                        link="/va/calls?prospect=" + p.id, category=p.category, city=getattr(p, "city", None),
                        phone=_pretty(p.phone_digits), prospect_id=p.id, tier=p.tier))
    out.sort(key=lambda r: r["at"] or "", reverse=True)
    return out


def _channel(lead_source):
    s = (lead_source or "").strip().lower()
    if s.startswith("phone"):
        return "phone"
    if s in ("maya", "vapi"):
        return "maya"
    if s == "no_coverage_waitlist":
        return "waitlist"
    return "web"


def jobs_rows(metric, start, end):
    key, _, arg = metric.partition(":")
    jobs = Job.query.filter(Job.created_at >= start, Job.created_at < end).order_by(Job.created_at.desc()).all()
    ids = [j.id for j in jobs]
    pays = {}
    for i in range(0, len(ids), 900):
        for p in Payment.query.filter(Payment.job_id.in_(ids[i:i + 900])).all():
            pays[p.job_id] = p
    out = []
    for j in jobs:
        p = pays.get(j.id)
        paid = p is not None and p.payment_status == "succeeded"
        if key == "paid" and not paid:
            continue
        if key == "revenue" and not paid:
            continue
        if key == "dump_fees" and not (paid and (getattr(j, "disposal_fee", 0) or 0) > 0):
            continue
        if key == "refunded" and not (p is not None and (p.refunded_amount or 0) > 0):
            continue
        if key == "completed" and j.status != "completed":
            continue
        if key == "cancelled" and j.status != "cancelled":
            continue
        if key == "channel" and _channel(j.lead_source) != arg:
            continue
        amount = float(p.amount) if paid else None
        if key == "dump_fees":
            amount = float(getattr(j, "disposal_fee", 0) or 0)
        if key == "refunded":
            amount = float(p.refunded_amount or 0)
        result = ("Paid ${:.2f}".format(p.amount) if paid else "Unpaid") + " · " + (j.status or "pending")
        out.append(_row(j.created_at, "{} — {}".format(_customer(j), (j.address or "")[:60]), who=_hauler_name(j.driver_id),
                        result=result, note=(j.notes or None), link="/va/dispatch", amount=amount,
                        code=getattr(j, "confirmation_code", None), job_id=j.id, channel=_channel(j.lead_source),
                        lead_source=j.lead_source, scheduled_at=(j.scheduled_at.isoformat() + "Z") if j.scheduled_at else None,
                        total=j.total_price))
    return out


def hauler_rows(metric, start, end):
    if metric == "no_shows":
        jobs = Job.query.filter(Job.noshow_redispatched_at >= start, Job.noshow_redispatched_at < end).all()
    else:
        jobs = Job.query.filter(Job.scheduled_at >= start, Job.scheduled_at < end, Job.driver_id.isnot(None)).all()
    out = []
    for j in jobs:
        confirmed = bool(getattr(j, "hauler_confirmed_at", None))
        if metric == "confirmed" and not confirmed:
            continue
        if metric == "unconfirmed" and confirmed:
            continue
        if metric == "hauler_completed" and j.status != "completed":
            continue
        if metric == "no_shows":
            who = _hauler_name(getattr(j, "noshow_contractor_id", None))
            result = "No-show: {}".format((getattr(j, "noshow_reason", None) or "").replace("_", " ") or "unconfirmed")
            at = j.noshow_redispatched_at
        else:
            who = _hauler_name(j.driver_id)
            result = ("Confirmed by {}".format(getattr(j, "hauler_confirmed_by", None) or "hauler") if confirmed else "Not confirmed") + " · " + (j.status or "")
            at = j.scheduled_at
        out.append(_row(at, "{} — {}".format(_customer(j), (j.address or "")[:60]), who=who, result=result,
                        note=(getattr(j, "hauler_confirmed_note", None) or None), link="/va/dispatch",
                        code=getattr(j, "confirmation_code", None), job_id=j.id, amount=j.total_price))
    out.sort(key=lambda r: r["at"] or "", reverse=True)
    return out


def maya_rows(metric, start, end):
    calls = CallLog.query.filter(CallLog.created_at >= start, CallLog.created_at < end).order_by(CallLog.created_at.desc()).limit(1000).all()
    out = []
    for c in calls:
        tools = c.tools_used or []
        quoted = "get_price_estimate" in tools
        if metric == "maya_quoted" and not quoted:
            continue
        if metric == "maya_booked" and not c.booking_created:
            continue
        if metric == "maya_lost" and not (quoted and not c.booking_created):
            continue
        result = ("Booked" if c.booking_created else ("Got a price, didn't book" if quoted else (c.status or "ended")))
        if c.sentiment:
            result += " · " + c.sentiment
        out.append(_row(c.created_at, _pretty(c.phone_number) or "Unknown number", who="Maya", result=result,
                        note=(c.summary or "")[:300] or None, link=("/va/calls?q=" + "".join(ch for ch in (c.phone_number or "") if ch.isdigit())[-10:]),
                        duration=c.duration_seconds, tools=tools))
    return out


def shift_rows(start, end, va):
    q = VaShift.query.filter(VaShift.started_at < end, db.or_(VaShift.ended_at.is_(None), VaShift.ended_at >= start))
    if va:
        q = q.filter(VaShift.va_name == va)
    out = []
    for sh in q.order_by(VaShift.started_at.desc()).all():
        end_at = sh.ended_at
        secs = int(((end_at or _now_naive()) - sh.started_at).total_seconds())
        out.append(_row(sh.started_at, "Shift", who=sh.va_name,
                        result=("Ended {}".format(_when(end_at)[1]) if end_at else "Still clocked in") + " · " + _fmt_secs(secs),
                        seconds=secs))
    return out


def class_rows(va):
    from models_analytics import CoachingClass
    q = CoachingClass.query.order_by(CoachingClass.week_start.desc())
    if va:
        q = q.filter_by(va_name=va)
    out = []
    for c in q.limit(60).all():
        out.append(_row(c.completed_at or c.created_at, "Week of {}".format(c.week_start), who=c.va_name,
                        result="{} · {}".format(c.status, "quiz {}/{}".format(c.quiz_score, len((c.lesson or {}).get("quiz", []))) if c.quiz_score is not None else "not taken"),
                        note=c.reflection, weakest=c.weakest, calls=c.calls))
    return out


def _now_naive():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(tzinfo=None)


INBOUND = ("calls", "human", "maya", "missed", "in_hours", "after_hours", "booked_calls", "quoted_calls")
SPEED = ("leads", "leads_touched", "leads_untouched", "leads_auto_texted")
OUTBOUND = ("dials", "connects", "interested", "wins", "callbacks")
JOBS = ("jobs", "paid", "completed", "cancelled", "revenue", "dump_fees", "refunded")
HAULERS = ("assigned", "confirmed", "unconfirmed", "no_shows", "hauler_completed")
MAYA = ("maya_calls", "maya_quoted", "maya_booked", "maya_lost")


def detail(metric, start, end, va, everyone):
    key = metric.partition(":")[0]
    if key in INBOUND or key in ("source", "disposition", "outcome"):
        return inbound_rows(metric, start, end, va), "inbound"
    if key in SPEED:
        return speed_rows(metric, start, end, va), "speed"
    if key in OUTBOUND:
        return outbound_rows(metric, start, end, va), "outbound"
    if not everyone:
        return None, None
    if key in JOBS or key == "channel":
        return jobs_rows(metric, start, end), "jobs"
    if key in HAULERS:
        return hauler_rows(metric, start, end), "haulers"
    if key in MAYA:
        return maya_rows(metric, start, end), "maya"
    if key == "shifts":
        return shift_rows(start, end, va), "shifts"
    if key == "classes":
        return class_rows(va), "classes"
    return None, None


@drill_bp.route("/api/va/analytics/detail", methods=["POST"])
@_ratelimit
def api_detail():
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    everyone = _sees_everyone(ident)
    va = (data.get("va") or "").strip()[:80] or None
    if not everyone:
        va = ident.get("name") or "—"
    metric = (data.get("metric") or "").strip()[:60]
    if not metric:
        return jsonify({"error": "metric is required"}), 400
    start, end, label, days = window(data)
    try:
        rows, kind = detail(metric, start, end, va, everyone)
    except Exception:
        logger.exception("analytics detail failed for %s", metric)
        return jsonify({"error": "couldn't load that breakdown"}), 500
    if rows is None:
        return jsonify({"error": "unknown metric" if everyone else "That needs a manager."}), 404 if everyone else 403
    limit = min(max(int(data.get("limit") or 100), 1), MAX_LIMIT)
    offset = max(int(data.get("offset") or 0), 0)
    total_amount = round(sum(float(r["amount"] or 0) for r in rows), 2) if any(r.get("amount") for r in rows) else None
    return jsonify({"metric": metric, "kind": kind, "label": label, "va": va, "total": len(rows),
                    "total_amount": total_amount, "offset": offset,
                    "rows": rows[offset:offset + limit]}), 200
