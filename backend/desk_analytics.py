"""Desk analytics — the whole desk on one page.

/va/manager grew up around outbound dialing (dials, reached, wins, cost per
win). The desk now runs inbound too: the desk line, the Google and Meta
numbers, Maya, bookings, dump fees, hauler confirmations. This is the page
that answers "how is the desk doing" across all of it, for a period, and
optionally for one VA.

    POST /api/va/analytics/desk   {period | days, va}
    GET  /va/analytics            the page

Scoping matches the other analytics endpoints: managers and the shared
passcode see everyone; a VA on her own login sees her own calls and
outcomes, and the business-wide blocks (money, haulers, Maya, hours) are
withheld.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import timedelta

from flask import Blueprint, Response, jsonify, request

from analytics import (_hours, _key, _local, _no_cache, _ratelimit, _sees_everyone, cached, funnel,
                       hourly_rate, window)
from desk_auth import desk_identity
from models import db, Job, Payment, CallLog
from models_inbound import InboundCall
from models_leads import LeadTouch

logger = logging.getLogger(__name__)
deskstats_bp = Blueprint("deskstats", __name__)

SOURCES = ("desk", "google", "meta", "maya", "unknown")
DISPOSITIONS = ("answered_by_human", "to_maya", "voicemail", "missed", "ringing")
OUTCOMES = ("booked", "quoted", "callback", "not_fit", "spam", "none")
SPEED_TARGET_SECONDS = 120
LIVE_STATUSES = ("pending", "accepted", "assigned", "en_route", "arrived", "in_progress", "started", "completed")


def _pct(n, d):
    return round(100.0 * n / d, 1) if d else None


def _channel(lead_source):
    s = (lead_source or "").strip().lower()
    if s.startswith("phone"):
        sub = s[6:] if s.startswith("phone_") else ""
        return "phone", (sub or "desk")
    if s in ("maya", "vapi"):
        return "maya", "maya"
    if s == "no_coverage_waitlist":
        return "waitlist", s
    return "web", (s or "direct")


def _median(vals):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return None
    m = len(vals) // 2
    return vals[m] if len(vals) % 2 else (vals[m - 1] + vals[m]) / 2.0


def _p90(vals):
    vals = sorted(v for v in vals if v is not None)
    return vals[min(len(vals) - 1, int(len(vals) * 0.9))] if vals else None


def inbound_block(start, end, va=None):
    q = InboundCall.query.filter(InboundCall.created_at >= start, InboundCall.created_at < end)
    if va:
        q = q.filter(db.or_(InboundCall.answered_by == va, InboundCall.va_name == va))
    rows = q.all()
    by_source = {s: 0 for s in SOURCES}
    by_disp = {d: 0 for d in DISPOSITIONS}
    by_outcome = {o: 0 for o in OUTCOMES}
    lead_outcomes = defaultdict(int)
    by_va = defaultdict(lambda: {"answered": 0, "booked": 0, "quoted": 0, "seconds": 0})
    in_hours = after_hours = 0
    durations = []
    quote_total = 0.0
    for r in rows:
        by_source[r.source if r.source in by_source else "unknown"] += 1
        by_disp[r.disposition if r.disposition in by_disp else "ringing"] += 1
        by_outcome[r.outcome if r.outcome in by_outcome else "none"] += 1
        if r.lead_outcome:
            lead_outcomes[r.lead_outcome] += 1
        if r.in_hours == 1:
            in_hours += 1
        elif r.in_hours == 0:
            after_hours += 1
        if r.duration:
            durations.append(r.duration)
        if r.quote_total:
            quote_total += float(r.quote_total)
        who = r.answered_by or r.va_name
        if who:
            b = by_va[who]
            b["answered"] += 1
            b["booked"] += int(r.outcome == "booked")
            b["quoted"] += int(r.outcome == "quoted")
            b["seconds"] += int(r.duration or 0)
    total = len(rows)
    human = by_disp["answered_by_human"]
    return {
        "calls": total,
        "answered_by_human": human,
        "human_rate": _pct(human, total),
        "to_maya": by_disp["to_maya"],
        "missed": by_disp["missed"] + by_disp["voicemail"],
        "in_hours": in_hours, "after_hours": after_hours,
        "booked": by_outcome["booked"], "quoted": by_outcome["quoted"],
        "book_rate": _pct(by_outcome["booked"], human),
        "avg_seconds": round(sum(durations) / len(durations)) if durations else None,
        "quote_total": round(quote_total, 2),
        "by_source": [{"source": s, "calls": n} for s, n in by_source.items() if n or s in ("desk", "google", "meta")],
        "by_disposition": by_disp,
        "by_outcome": by_outcome,
        "lead_outcomes": dict(lead_outcomes),
        "by_va": [dict(v, va=k, book_rate=_pct(v["booked"], v["answered"]))
                  for k, v in sorted(by_va.items(), key=lambda kv: -kv[1]["answered"])],
    }


def speed_block(start, end, va=None):
    """How fast a new lead got a human, from LeadTouch rows opened in the window."""
    q = LeadTouch.query.filter(LeadTouch.created_at >= start, LeadTouch.created_at < end)
    if va:
        q = q.filter(LeadTouch.touched_by == va)
    rows = q.all()
    call_refs = [r.ref_id for r in rows if r.kind == "call"]
    born = {}
    if call_refs:
        for c in InboundCall.query.filter(db.or_(InboundCall.call_sid.in_(call_refs), InboundCall.id.in_(call_refs))).all():
            born[c.call_sid] = c.created_at
            born[c.id] = c.created_at
    secs, untouched, auto_texted = [], 0, 0
    for r in rows:
        opened = born.get(r.ref_id) if r.kind == "call" else r.created_at
        opened = opened or r.created_at
        if r.auto_text_at:
            auto_texted += 1
        if r.touched_at and opened:
            secs.append(max(0.0, (r.touched_at - opened).total_seconds()))
        elif not r.touched_at:
            untouched += 1
    within = sum(1 for s in secs if s <= SPEED_TARGET_SECONDS)
    return {
        "leads": len(rows), "touched": len(secs), "untouched": untouched, "auto_texted": auto_texted,
        "median_seconds": round(_median(secs)) if secs else None,
        "p90_seconds": round(_p90(secs)) if secs else None,
        "within_target_pct": _pct(within, len(secs)),
        "target_seconds": SPEED_TARGET_SECONDS,
    }


def bookings_block(start, end):
    jobs = Job.query.filter(Job.created_at >= start, Job.created_at < end).all()
    ids = [j.id for j in jobs]
    pays = {}
    if ids:
        for i in range(0, len(ids), 900):
            for p in Payment.query.filter(Payment.job_id.in_(ids[i:i + 900])).all():
                pays[p.job_id] = p
    by_channel = defaultdict(lambda: {"jobs": 0, "paid": 0, "revenue": 0.0})
    by_source = defaultdict(int)
    paid = completed = cancelled = 0
    revenue = dump_fees = tips = refunded = 0.0
    tickets = []
    for j in jobs:
        ch, sub = _channel(j.lead_source)
        by_channel[ch]["jobs"] += 1
        by_source[sub] += 1
        if j.status == "completed":
            completed += 1
        if j.status == "cancelled":
            cancelled += 1
        p = pays.get(j.id)
        if p is not None and p.payment_status == "succeeded":
            paid += 1
            amt = float(p.amount or 0.0)
            revenue += amt
            tickets.append(amt)
            tips += float(p.tip_amount or 0.0)
            refunded += float(p.refunded_amount or 0.0)
            dump_fees += float(getattr(j, "disposal_fee", 0.0) or 0.0)
            by_channel[ch]["paid"] += 1
            by_channel[ch]["revenue"] += amt
    return {
        "jobs": len(jobs), "paid": paid, "completed": completed, "cancelled": cancelled,
        "revenue": round(revenue, 2), "avg_ticket": round(sum(tickets) / len(tickets), 2) if tickets else None,
        "dump_fees": round(dump_fees, 2), "tips": round(tips, 2), "refunded": round(refunded, 2),
        "pay_rate": _pct(paid, len(jobs)),
        "by_channel": [dict(jobs=v["jobs"], paid=v["paid"], revenue=round(v["revenue"], 2), channel=k)
                       for k, v in sorted(by_channel.items(), key=lambda kv: -kv[1]["jobs"])],
        "by_source": [{"source": k, "jobs": n} for k, n in sorted(by_source.items(), key=lambda kv: -kv[1])[:8]],
    }


def haulers_block(start, end):
    """Jobs on the calendar in the window that had a hauler: did they confirm, did they show."""
    jobs = Job.query.filter(Job.scheduled_at >= start, Job.scheduled_at < end, Job.driver_id.isnot(None)).all()
    confirmed = sum(1 for j in jobs if getattr(j, "hauler_confirmed_at", None))
    no_shows = Job.query.filter(Job.noshow_redispatched_at >= start, Job.noshow_redispatched_at < end).count() \
        if hasattr(Job, "noshow_redispatched_at") else 0
    completed = sum(1 for j in jobs if j.status == "completed")
    by_hauler = defaultdict(lambda: {"jobs": 0, "confirmed": 0, "completed": 0})
    for j in jobs:
        b = by_hauler[j.driver_id]
        b["jobs"] += 1
        b["confirmed"] += int(bool(getattr(j, "hauler_confirmed_at", None)))
        b["completed"] += int(j.status == "completed")
    names = {}
    if by_hauler:
        from models import Contractor, User
        for c in Contractor.query.filter(Contractor.id.in_(list(by_hauler))).all():
            u = db.session.get(User, c.user_id)
            names[c.id] = (u.name if u else None) or "Hauler " + c.id[:6]
    owed = None
    try:
        from sameday_pay import owed_rows
        o = owed_rows()
        today = [r for r in o.get("rows", []) if r.get("today")]
        owed = {"count": len(today), "total": float(o.get("today_total") or 0.0)}
    except Exception:
        pass
    return {
        "assigned": len(jobs), "confirmed": confirmed, "confirm_rate": _pct(confirmed, len(jobs)),
        "no_shows": no_shows, "completed": completed,
        "by_hauler": [dict(v, name=names.get(k, k), confirm_rate=_pct(v["confirmed"], v["jobs"]))
                      for k, v in sorted(by_hauler.items(), key=lambda kv: -kv[1]["jobs"])[:10]],
        "owed_today": owed,
    }


def maya_block(days):
    try:
        from maya_report import report
        r = report(days=days, samples=0)
        r.pop("lost_samples", None)
        return r
    except Exception:
        logger.debug("maya block unavailable", exc_info=True)
        return None


def series_block(start, end, va=None):
    days = {}
    d = _local(start).date()
    last = _local(end).date()
    while d <= last:
        days[d.isoformat()] = {"day": d.isoformat(), "calls": 0, "human": 0, "bookings": 0, "revenue": 0.0}
        d += timedelta(days=1)
    q = InboundCall.query.filter(InboundCall.created_at >= start, InboundCall.created_at < end)
    if va:
        q = q.filter(db.or_(InboundCall.answered_by == va, InboundCall.va_name == va))
    for r in q.all():
        if r.created_at:
            k = _local(r.created_at).date().isoformat()
            if k in days:
                days[k]["calls"] += 1
                days[k]["human"] += int(r.disposition == "answered_by_human")
    if not va:
        for j, p in (db.session.query(Job, Payment).outerjoin(Payment, Payment.job_id == Job.id)
                     .filter(Job.created_at >= start, Job.created_at < end).all()):
            k = _local(j.created_at).date().isoformat() if j.created_at else None
            if k in days:
                days[k]["bookings"] += 1
                if p is not None and p.payment_status == "succeeded":
                    days[k]["revenue"] += float(p.amount or 0.0)
    return [dict(v, revenue=round(v["revenue"], 2)) for v in days.values()]


def classes_block(weeks=6, va=None):
    from models_analytics import CoachingClass
    q = CoachingClass.query.order_by(CoachingClass.week_start.desc(), CoachingClass.va_name.asc())
    if va:
        q = q.filter(CoachingClass.va_name == va)
    rows = q.limit(weeks * 6).all()
    return [{"id": r.id, "va": r.va_name, "week": r.week_start, "status": r.status, "calls": r.calls,
             "avg_total": (r.avg_total or 0) / 10.0 if r.avg_total is not None else None, "weakest": r.weakest,
             "quiz": r.quiz_score, "quiz_total": len((r.lesson or {}).get("quiz", [])),
             "reflection": r.reflection, "completed_at": r.completed_at.isoformat() + "Z" if r.completed_at else None,
             "due_at": r.due_at.isoformat() + "Z" if r.due_at else None} for r in rows]


def desk_report(start, end, label, days, va=None, everyone=True):
    out = {
        "label": label, "days": days, "start": start.isoformat(), "end": end.isoformat(),
        "va": va, "scope": "va" if va else "all", "manager": everyone,
        "inbound": inbound_block(start, end, va),
        "speed": speed_block(start, end, va),
        "series": series_block(start, end, va),
    }
    try:
        f = funnel(start, end, va)
        out["outbound"] = {k: f.get(k) for k in ("dials", "connects", "interested", "wins", "connect_rate",
                                                  "interest_rate", "win_rate") if k in f}
    except Exception:
        logger.debug("outbound block unavailable", exc_info=True)
        out["outbound"] = None
    if everyone:
        out["bookings"] = bookings_block(start, end)
        out["haulers"] = haulers_block(start, end)
        out["maya"] = maya_block(days)
        try:
            out["classes"] = classes_block(va=va)
        except Exception:
            logger.debug("classes block unavailable", exc_info=True)
            out["classes"] = []
        secs = _hours(start, end, va)
        rate = hourly_rate()
        hours = round(sum(secs.values()) / 3600.0, 2)
        out["hours"] = {"rate": rate, "hours": hours, "cost": round(hours * rate, 2),
                        "by_va": [{"va": k, "hours": round(v / 3600.0, 2)} for k, v in sorted(secs.items())]}
    return out


@deskstats_bp.route("/api/va/analytics/desk", methods=["POST"])
@_ratelimit
def api_desk():
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    everyone = _sees_everyone(ident)
    va = (data.get("va") or "").strip()[:80] or None
    if not everyone:
        va = ident.get("name") or "—"
    start, end, label, days = window(data)
    res = cached(_key("desk", start, va, period=(data.get("period") or ""), days=days, all=int(everyone)),
                 lambda: desk_report(start, end, label, days, va, everyone))
    return jsonify(res), 200


@deskstats_bp.route("/va/analytics", methods=["GET"])
def analytics_page():
    return _no_cache(Response(PAGE_HTML, mimetype="text/html"))


PAGE_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<meta name="robots" content="noindex, nofollow" />
<meta name="theme-color" content="#0B0E12" />
<title>Umuve — Desk analytics</title>
<link rel="stylesheet" href="/va/app.css?v=5" />
<link rel="stylesheet" href="/static/manager.css?v=2" />
<link rel="stylesheet" href="/static/desk-stats.css?v=1" />
</head>
<body class="mgr">
<div id="app">
  <section id="gate" class="mg-gate" hidden>
    <div class="mg-gatewrap">
      <img class="brand-lg" src="/va/logo.png" alt="Umuve" />
      <h1 class="display">ANALYTICS</h1>
      <p class="sub">This page reads your desk sign-in. Sign in on the Call Desk, then come back.</p>
      <a class="btn mg-btn-link" href="/va/calls">Open the Call Desk</a>
    </div>
  </section>
  <section id="tool" hidden>
    <header class="mg-bar">
      <a class="back" href="/va/calls" aria-label="Back to the Call Desk">‹</a>
      <span class="wordmark">UMUVE<span class="dot"></span></span>
      <span class="mg-title">Desk analytics</span>
      <a class="ds-link" href="/va/manager" id="mgr-link" hidden>Outbound manager →</a>
      <span class="bar-sub" id="who"></span>
    </header>
    <div class="mg-wrap">
      <div class="mg-controls">
        <div class="mg-seg" role="group" aria-label="Period" id="period">
          <button type="button" data-p="today">Today</button>
          <button type="button" data-p="week">This week</button>
          <button type="button" data-d="7">7 days</button>
          <button type="button" data-d="30" class="is-on">30 days</button>
          <button type="button" data-d="90">90 days</button>
        </div>
        <label class="mg-va" id="va-wrap" hidden><span>Person</span><select id="va-pick"><option value="">Everyone</option></select></label>
        <span class="mg-stamp" id="stamp"></span>
      </div>
      <p class="mg-err" id="err" hidden></p>

      <div class="mg-kpis ds-kpis" id="kpis">
        <div class="mg-kpi"><b id="k-calls">–</b><span>Calls in</span></div>
        <div class="mg-kpi"><b id="k-human">–</b><span>Answered by a person</span></div>
        <div class="mg-kpi"><b id="k-speed">–</b><span>Median speed to lead</span></div>
        <div class="mg-kpi"><b id="k-booked">–</b><span>Booked from calls</span></div>
        <div class="mg-kpi" data-mgr><b id="k-rev">–</b><span>Paid revenue</span></div>
        <div class="mg-kpi" data-mgr><b id="k-noshow">–</b><span>Hauler no-shows</span></div>
      </div>

      <section class="mg-sec">
        <div class="mg-sec-h"><h2>Calls and bookings, by day</h2>
          <div class="mg-legend"><i class="sw sw-dials"></i>Calls in <i class="sw sw-int"></i>Answered by a person <i class="sw sw-book"></i>Bookings</div></div>
        <div class="mg-chart" id="chart"></div>
        <div class="mg-tip" id="tip" hidden></div>
      </section>

      <div class="mg-cols">
        <section class="mg-sec">
          <div class="mg-sec-h"><h2>Where calls come from</h2><span class="mg-note">Which number they dialled</span></div>
          <div class="mg-tablewrap"><table class="mg-table" id="t-source"></table></div>
        </section>
        <section class="mg-sec">
          <div class="mg-sec-h"><h2>What happened to them</h2><span class="mg-note" id="disp-note"></span></div>
          <div class="mg-tablewrap"><table class="mg-table" id="t-disp"></table></div>
        </section>
      </div>

      <section class="mg-sec">
        <div class="mg-sec-h"><h2>Speed to lead</h2><span class="mg-note" id="speed-note">Target: a person on the line inside 2 minutes</span></div>
        <div class="mg-facts ds-facts" id="speed"></div>
      </section>

      <section class="mg-sec">
        <div class="mg-sec-h"><h2>By person</h2><span class="mg-note">Inbound calls answered and what came of them</span></div>
        <div class="mg-tablewrap"><table class="mg-table" id="t-va"></table></div>
      </section>

      <div class="mg-cols" data-mgr>
        <section class="mg-sec">
          <div class="mg-sec-h"><h2>Bookings and money</h2><span class="mg-note" id="book-note"></span></div>
          <div class="mg-facts ds-facts" id="money"></div>
          <div class="mg-tablewrap ds-gap"><table class="mg-table" id="t-channel"></table></div>
        </section>
        <section class="mg-sec">
          <div class="mg-sec-h"><h2>Haulers</h2><span class="mg-note" id="haul-note"></span></div>
          <div class="mg-facts ds-facts" id="haulers"></div>
          <div class="mg-tablewrap ds-gap"><table class="mg-table" id="t-hauler"></table></div>
        </section>
      </div>

      <div class="mg-cols">
        <section class="mg-sec" data-mgr>
          <div class="mg-sec-h"><h2>Maya</h2><span class="mg-note" id="maya-note">Calls the AI took</span></div>
          <div class="mg-facts ds-facts" id="maya"></div>
        </section>
        <section class="mg-sec">
          <div class="mg-sec-h"><h2>Outbound</h2><span class="mg-note"><a class="ds-link" href="/va/manager">Full breakdown on the manager page →</a></span></div>
          <div class="mg-facts ds-facts" id="outbound"></div>
        </section>
      </div>

      <section class="mg-sec" data-mgr>
        <div class="mg-sec-h"><h2>Weekly classes</h2><span class="mg-note">Built from her scored calls every Friday at 5pm; the desk holds it until it's done</span></div>
        <div class="mg-tablewrap"><table class="mg-table" id="t-classes"></table></div>
      </section>

      <section class="mg-sec" data-mgr>
        <div class="mg-sec-h"><h2>Hours on the clock</h2><span class="mg-note" id="hours-note"></span></div>
        <div class="mg-tablewrap"><table class="mg-table" id="t-hours"></table></div>
      </section>
    </div>
  </section>
</div>
<script src="/static/desk-stats.js?v=2"></script>
</body>
</html>
"""
