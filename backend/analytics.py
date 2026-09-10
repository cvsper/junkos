"""Call Desk analytics — funnel, economics, list quality, daily series, and
the manager page that reads them.

Everything is computed from the tables the desk already writes
(CallAttempt, CallProspect, DeskActivity, VaShift, AuditEvent); nothing new
is logged. Buckets are in business time (America/New_York), storage is
naive UTC like the rest of the desk.

Endpoints (JSON POST; identity like the desk — Bearer JWT or {code, va_name}):
  POST /api/va/analytics/funnel      {days|period, va}  VA → own numbers; manager → any/all
  POST /api/va/analytics/timeseries  {days|period, va}  daily dials/connects/interested/wins
  POST /api/va/analytics/economics   {days}             manager; cost per dial/connect/interested/win
  POST /api/va/analytics/lists       {days}             manager; per import batch (by created_at day)
  GET  /va/manager                                      the manager page

Definitions (shared with the desk's vocabulary):
  dial       any logged attempt except "skip"
  connect    a human answered: interested, sent_link, vendor_listed,
             not_interested, converted, callback
  interested interested or sent_link (they asked for more)
  win        converted or vendor_listed (we're on their list or booked)
  reach rate connects / dials; conversion = wins / dials

Results are cached in-process for ANALYTICS_CACHE_SECONDS (default 60),
keyed by the exact arguments.
"""
from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from flask import Blueprint, Response, jsonify, request

from desk_auth import desk_identity, is_manager
from models import db, AuditEvent, CallAttempt, CallProspect, DeskActivity, VaShift

try:
    from extensions import limiter
except Exception:  # pragma: no cover
    limiter = None

logger = logging.getLogger(__name__)
analytics_bp = Blueprint("analytics", __name__)

_ratelimit = (limiter.limit("240 per hour; 60 per minute") if limiter is not None
              else (lambda f: f))

CONNECT_OUTCOMES = ("interested", "sent_link", "vendor_listed", "not_interested", "converted", "callback")
INTERESTED_OUTCOMES = ("interested", "sent_link")
WIN_OUTCOMES = ("converted", "vendor_listed")
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
CALLBACK_GRACE = timedelta(hours=2)   # calling a bit before the agreed time still counts as kept
MAX_DAYS = 365


# ---------------------------------------------------------------------------
# time helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _local(dt_naive_utc):
    from timeutils import to_local
    return to_local(dt_naive_utc)


def _local_day_start_utc(local_date):
    from timeutils import local_naive_to_utc
    return local_naive_to_utc(datetime.combine(local_date, datetime.min.time())).replace(tzinfo=None)


def _clamp_days(raw, default):
    try:
        d = int(raw)
    except (TypeError, ValueError):
        d = default
    return min(max(d, 1), MAX_DAYS)


def window(data, default_days=30):
    """→ (start_utc_naive, end_utc_naive, label, days). `period` wins over `days`:
    today | week (Mon–) | pay_period; otherwise the last N local days including today."""
    now = _now()
    today = _local(now).date()
    period = (data.get("period") or "").strip().lower()
    if period == "today":
        return _local_day_start_utc(today), now, "Today", 1
    if period == "week":
        start_d = today - timedelta(days=today.weekday())
        return _local_day_start_utc(start_d), now, "This week", (today - start_d).days + 1
    if period == "pay_period":
        from va_time import period_bounds
        s, e, label = period_bounds()
        return s, min(e, now), label, (min(e, now) - s).days + 1
    days = _clamp_days(data.get("days"), default_days)
    start_d = today - timedelta(days=days - 1)
    return _local_day_start_utc(start_d), now, "Last {} days".format(days), days


# ---------------------------------------------------------------------------
# cache
# ---------------------------------------------------------------------------

_CACHE = {}


def _ttl():
    try:
        return max(0, int(os.environ.get("ANALYTICS_CACHE_SECONDS", "60")))
    except ValueError:
        return 60


def cached(key, build):
    """In-process memo keyed by the exact args. A window's `end` is `now`, so
    callers pass a bucketed key (see _key) rather than the raw datetime."""
    ttl = _ttl()
    hit = _CACHE.get(key)
    if hit and hit[0] > time.monotonic() and ttl:
        return hit[1]
    val = build()
    if ttl:
        _CACHE[key] = (time.monotonic() + ttl, val)
    return val


def cache_clear():
    _CACHE.clear()


def _key(name, start, va=None, **extra):
    return (name, start.isoformat(), va or "", tuple(sorted(extra.items())))


# ---------------------------------------------------------------------------
# core queries
# ---------------------------------------------------------------------------

def _attempts(start, end, va=None):
    """[(CallAttempt, CallProspect)] in the window, skips excluded."""
    q = (db.session.query(CallAttempt, CallProspect)
         .join(CallProspect, CallProspect.id == CallAttempt.prospect_id)
         .filter(CallAttempt.created_at >= start, CallAttempt.created_at < end,
                 CallAttempt.outcome != "skip"))
    if va:
        q = q.filter(CallAttempt.va_name == va)
    return q.order_by(CallAttempt.created_at.asc()).all()


def _bucket():
    return {"dials": 0, "connects": 0, "interested": 0, "wins": 0}


def _tally(b, outcome):
    b["dials"] += 1
    if outcome in CONNECT_OUTCOMES:
        b["connects"] += 1
    if outcome in INTERESTED_OUTCOMES:
        b["interested"] += 1
    if outcome in WIN_OUTCOMES:
        b["wins"] += 1


def _pct(n, d):
    return round(100.0 * n / d, 1) if d else 0.0


def _with_rates(b):
    b = dict(b)
    b["reach_rate"] = _pct(b["connects"], b["dials"])
    b["conversion"] = _pct(b["wins"], b["dials"])
    return b


def _texts(start, end, va=None):
    q = DeskActivity.query.filter(DeskActivity.kind == "sms", DeskActivity.created_at >= start,
                                  DeskActivity.created_at < end)
    rows = q.all()
    if va:
        mine = [r for r in rows if r.direction == "out" and r.va_name == va]
        phones = {r.phone_digits for r in mine}
        sent = len(mine)
        received = sum(1 for r in rows if r.direction == "in" and r.phone_digits in phones)
    else:
        sent = sum(1 for r in rows if r.direction == "out")
        received = sum(1 for r in rows if r.direction == "in")
    return {"sent": sent, "received": received}


def _parse_iso_naive(s):
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


def _callbacks(pairs, end):
    """Set vs kept. A callback is *kept* when the same prospect got another
    attempt after the agreed time (the audit event carries it; otherwise after
    the callback itself). Callbacks whose time hasn't come are *pending*."""
    cbs = [(a, p) for a, p in pairs if a.outcome == "callback"]
    if not cbs:
        return {"set": 0, "kept": 0, "pending": 0, "kept_rate": 0.0}
    pids = {p.id for _, p in cbs}
    later = defaultdict(list)
    for a in (CallAttempt.query.filter(CallAttempt.prospect_id.in_(pids), CallAttempt.outcome != "skip")
              .order_by(CallAttempt.created_at.asc()).all()):
        later[a.prospect_id].append(a)
    sched = defaultdict(list)
    for ev in (AuditEvent.query.filter(AuditEvent.action == "callback", AuditEvent.target_id.in_(pids)).all()):
        at = _parse_iso_naive((ev.meta or {}).get("at"))
        if at and ev.created_at:
            sched[ev.target_id].append((ev.created_at, at))
    now = _now()
    kept = pending = 0
    for a, p in cbs:
        when = None
        for ev_at, at in sched.get(p.id, []):
            if a.created_at and abs((ev_at - a.created_at).total_seconds()) <= 120:
                when = at
                break
        threshold = (when - CALLBACK_GRACE) if when else a.created_at
        followed = any(o.id != a.id and o.created_at > a.created_at and o.created_at >= threshold
                       for o in later.get(p.id, []))
        if followed:
            kept += 1
        elif when and when > now:
            pending += 1
    due = len(cbs) - pending
    return {"set": len(cbs), "kept": kept, "pending": pending, "kept_rate": _pct(kept, due)}


def funnel(start, end, va=None):
    from call_kit import detect_side
    pairs = _attempts(start, end, va)
    total = _bucket()
    by_outcome = defaultdict(int)
    by_tier = defaultdict(_bucket)
    by_cat = defaultdict(_bucket)
    by_side = {"demand": _bucket(), "supply": _bucket()}
    by_va = defaultdict(_bucket)
    by_hour = [_bucket() for _ in range(24)]
    by_wd = [_bucket() for _ in range(7)]
    heat = [[0] * 24 for _ in range(7)]
    heat_connects = [[0] * 24 for _ in range(7)]
    side_cache = {}
    for a, p in pairs:
        o = a.outcome
        _tally(total, o)
        by_outcome[o] += 1
        _tally(by_tier[p.tier or 0], o)
        _tally(by_cat[(p.category or "").strip().lower() or "uncategorized"], o)
        if p.id not in side_cache:
            side_cache[p.id] = detect_side(p)
        _tally(by_side[side_cache[p.id]], o)
        _tally(by_va[a.va_name or "—"], o)
        if a.created_at:
            loc = _local(a.created_at)
            _tally(by_hour[loc.hour], o)
            _tally(by_wd[loc.weekday()], o)
            heat[loc.weekday()][loc.hour] += 1
            if o in CONNECT_OUTCOMES:
                heat_connects[loc.weekday()][loc.hour] += 1
    cats = sorted(by_cat.items(), key=lambda kv: (-kv[1]["dials"], kv[0]))[:10]
    out = _with_rates(total)
    out.update({
        "va": va or None,
        "by_outcome": dict(by_outcome),
        "by_tier": [dict(_with_rates(b), tier=t) for t, b in sorted(by_tier.items())],
        "by_category": [dict(_with_rates(b), category=c) for c, b in cats],
        "by_side": {s: _with_rates(b) for s, b in by_side.items()},
        "by_va": [dict(_with_rates(b), va=n) for n, b in sorted(by_va.items(), key=lambda kv: -kv[1]["dials"])],
        "by_hour": [dict(_with_rates(b), hour=h) for h, b in enumerate(by_hour)],
        "by_weekday": [dict(_with_rates(b), weekday=WEEKDAYS[i]) for i, b in enumerate(by_wd)],
        "heatmap": {"weekdays": list(WEEKDAYS), "dials": heat, "connects": heat_connects},
        "texts": _texts(start, end, va),
        "callbacks": _callbacks(pairs, end),
    })
    return out


def timeseries(start, end, va=None):
    days = {}
    d = _local(start).date()
    last = _local(end).date()
    while d <= last:
        days[d.isoformat()] = _bucket()
        d += timedelta(days=1)
    for a, p in _attempts(start, end, va):
        if not a.created_at:
            continue
        k = _local(a.created_at).date().isoformat()
        if k in days:
            _tally(days[k], a.outcome)
    return [dict(b, day=k) for k, b in days.items()]


def _hours(start, end, va=None):
    """Seconds on the clock per VA inside the window (open shifts count to now)."""
    from va_time import _overlap_seconds
    q = VaShift.query.filter(VaShift.started_at < end,
                             db.or_(VaShift.ended_at.is_(None), VaShift.ended_at >= start))
    if va:
        q = q.filter(VaShift.va_name == va)
    out = defaultdict(int)
    for sh in q.all():
        out[sh.va_name] += _overlap_seconds(sh, start, end)
    return out


def hourly_rate():
    try:
        return round(float(os.environ.get("VA_HOURLY_RATE", "6.00")), 2)
    except ValueError:
        return 6.0


def _cost_per(cost, n):
    return round(cost / n, 2) if n else None


def economics_window(start, end, label):
    rate = hourly_rate()
    secs = _hours(start, end)
    per = defaultdict(_bucket)
    for a, p in _attempts(start, end):
        _tally(per[a.va_name or "—"], a.outcome)
    names = sorted(set(per) | set(secs))
    rows, tot, tot_secs = [], _bucket(), 0
    for n in names:
        b = per.get(n, _bucket())
        h = round(secs.get(n, 0) / 3600.0, 2)
        cost = round(h * rate, 2)
        rows.append(dict(_with_rates(b), va=n, hours=h, cost=cost,
                         cost_per_dial=_cost_per(cost, b["dials"]), cost_per_connect=_cost_per(cost, b["connects"]),
                         cost_per_interested=_cost_per(cost, b["interested"]), cost_per_win=_cost_per(cost, b["wins"]),
                         dials_per_hour=round(b["dials"] / h, 1) if h else None))
        for k in tot:
            tot[k] += b[k]
        tot_secs += secs.get(n, 0)
    h = round(tot_secs / 3600.0, 2)
    cost = round(h * rate, 2)
    totals = dict(_with_rates(tot), hours=h, cost=cost,
                  cost_per_dial=_cost_per(cost, tot["dials"]), cost_per_connect=_cost_per(cost, tot["connects"]),
                  cost_per_interested=_cost_per(cost, tot["interested"]), cost_per_win=_cost_per(cost, tot["wins"]),
                  dials_per_hour=round(tot["dials"] / h, 1) if h else None)
    return {"label": label, "start": start.isoformat(), "end": end.isoformat(), "vas": rows, "totals": totals}


def economics(days=30):
    from va_time import period_bounds
    now = _now()
    ps, pe, plabel = period_bounds()
    start, end, label, days = window({"days": days})
    return {"rate": hourly_rate(),
            "period": economics_window(ps, min(pe, now), plabel),
            "window": economics_window(start, end, label)}


def lists(days=90):
    """Each import batch ≈ the prospects created on one local day."""
    start, end, label, days = window({"days": days}, default_days=90)
    prospects = CallProspect.query.filter(CallProspect.created_at >= start).all()
    if not prospects:
        return {"label": label, "lists": []}
    groups = defaultdict(list)
    for p in prospects:
        groups[_local(p.created_at).date().isoformat() if p.created_at else "unknown"].append(p)
    pid_to_day = {p.id: d for d, ps in groups.items() for p in ps}
    per = {d: _bucket() for d in groups}
    ids = list(pid_to_day)
    for i in range(0, len(ids), 900):     # sqlite bind-parameter ceiling
        chunk = ids[i:i + 900]
        for a in CallAttempt.query.filter(CallAttempt.prospect_id.in_(chunk), CallAttempt.outcome != "skip").all():
            _tally(per[pid_to_day[a.prospect_id]], a.outcome)
    out = []
    for d in sorted(groups, reverse=True):
        ps = groups[d]
        worked = sum(1 for p in ps if (p.attempts or 0) > 0)
        cats = defaultdict(int)
        for p in ps:
            cats[(p.category or "").strip().lower() or "uncategorized"] += 1
        top = sorted(cats.items(), key=lambda kv: -kv[1])[:3]
        statuses = defaultdict(int)
        for p in ps:
            statuses[p.status or "queued"] += 1
        b = _with_rates(per[d])
        out.append(dict(b, day=d, size=len(ps), worked=worked, worked_pct=_pct(worked, len(ps)),
                        reach=b["connects"], tiers={str(t): sum(1 for p in ps if (p.tier or 0) == t)
                                                     for t in sorted({p.tier or 0 for p in ps})},
                        categories=[{"category": c, "n": n} for c, n in top], statuses=dict(statuses)))
    return {"label": label, "lists": out}


# ---------------------------------------------------------------------------
# endpoints
# ---------------------------------------------------------------------------

def _sees_everyone(ident):
    """Managers/admins, plus the legacy shared passcode (the owner's view —
    same rule as /api/va/time/team). A VA on a real login sees only herself."""
    return is_manager(ident) or ident.get("via") == "passcode"


def _ident_or_401():
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return None, data, (jsonify({"error": "Sign in to the desk first."}), 401)
    return ident, data, None


def _scope(ident, data):
    """Which VA a funnel-style request may see."""
    va = (data.get("va") or "").strip()[:80] or None
    if not _sees_everyone(ident):
        return ident.get("name") or "—"
    return va


@analytics_bp.route("/api/va/analytics/funnel", methods=["POST"])
@_ratelimit
def api_funnel():
    ident, data, err = _ident_or_401()
    if err:
        return err
    va = _scope(ident, data)
    start, end, label, days = window(data)
    res = cached(_key("funnel", start, va, period=(data.get("period") or ""), days=days),
                 lambda: funnel(start, end, va))
    return jsonify(dict(res, label=label, days=days, start=start.isoformat(), end=end.isoformat(),
                        scope="all" if not va else "va")), 200


@analytics_bp.route("/api/va/analytics/timeseries", methods=["POST"])
@_ratelimit
def api_timeseries():
    ident, data, err = _ident_or_401()
    if err:
        return err
    va = _scope(ident, data)
    start, end, label, days = window(data)
    series = cached(_key("timeseries", start, va, period=(data.get("period") or ""), days=days),
                    lambda: timeseries(start, end, va))
    return jsonify({"label": label, "days": days, "va": va, "series": series}), 200


@analytics_bp.route("/api/va/analytics/economics", methods=["POST"])
@_ratelimit
def api_economics():
    ident, data, err = _ident_or_401()
    if err:
        return err
    if not _sees_everyone(ident):
        return jsonify({"error": "That needs a manager."}), 403
    days = _clamp_days(data.get("days"), 30)
    start = _local_day_start_utc(_local(_now()).date())
    res = cached(_key("economics", start, None, days=days), lambda: economics(days))
    return jsonify(res), 200


@analytics_bp.route("/api/va/analytics/lists", methods=["POST"])
@_ratelimit
def api_lists():
    ident, data, err = _ident_or_401()
    if err:
        return err
    if not _sees_everyone(ident):
        return jsonify({"error": "That needs a manager."}), 403
    days = _clamp_days(data.get("days"), 90)
    start = _local_day_start_utc(_local(_now()).date())
    res = cached(_key("lists", start, None, days=days), lambda: lists(days))
    return jsonify(res), 200


# ---------------------------------------------------------------------------
# manager page
# ---------------------------------------------------------------------------

def _no_cache(resp):
    resp.headers["Cache-Control"] = "no-cache, must-revalidate"
    return resp


@analytics_bp.route("/va/manager", methods=["GET"])
def manager_page():
    return _no_cache(Response(MANAGER_HTML, mimetype="text/html"))


MANAGER_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<meta name="robots" content="noindex, nofollow" />
<meta name="theme-color" content="#0B0E12" />
<title>Umuve — Desk manager</title>
<link rel="stylesheet" href="/va/app.css?v=4" />
<link rel="stylesheet" href="/static/manager.css?v=1" />
</head>
<body class="mgr">
<div id="app">
  <section id="gate" class="mg-gate" hidden>
    <div class="mg-gatewrap">
      <img class="brand-lg" src="/va/logo.png" alt="Umuve" />
      <h1 class="display">MANAGER</h1>
      <p class="sub">This page reads your desk sign-in. Sign in on the Call Desk, then come back.</p>
      <a class="btn mg-btn-link" href="/va/calls">Open the Call Desk</a>
    </div>
  </section>
  <section id="tool" hidden>
    <header class="mg-bar">
      <a class="back" href="/va/calls" aria-label="Back to the Call Desk">‹</a>
      <span class="wordmark">UMUVE<span class="dot"></span></span>
      <span class="mg-title">Desk manager</span>
      <span class="bar-sub" id="who"></span>
    </header>
    <div class="mg-wrap">
      <div class="mg-controls">
        <div class="mg-seg" role="group" aria-label="Period" id="period">
          <button type="button" data-d="7">7 days</button>
          <button type="button" data-d="14">14 days</button>
          <button type="button" data-d="30" class="is-on">30 days</button>
          <button type="button" data-d="90">90 days</button>
        </div>
        <label class="mg-va"><span>Caller</span><select id="va-pick"><option value="">Everyone</option></select></label>
        <span class="mg-stamp" id="stamp"></span>
      </div>
      <p class="mg-err" id="err" hidden></p>

      <div class="mg-kpis" id="kpis">
        <div class="mg-kpi"><b id="k-dials">–</b><span>Dials</span></div>
        <div class="mg-kpi"><b id="k-reach">–</b><span>Reached</span></div>
        <div class="mg-kpi"><b id="k-int">–</b><span>Interested</span></div>
        <div class="mg-kpi"><b id="k-wins">–</b><span>Wins</span></div>
        <div class="mg-kpi"><b id="k-cpw">–</b><span>Cost per win</span></div>
        <div class="mg-kpi"><b id="k-hours">–</b><span>Hours on the clock</span></div>
      </div>

      <section class="mg-sec">
        <div class="mg-sec-h"><h2>Dials and interested, by day</h2>
          <div class="mg-legend"><i class="sw sw-dials"></i>Dials <i class="sw sw-int"></i>Interested</div></div>
        <div class="mg-chart" id="chart"></div>
        <div class="mg-tip" id="tip" hidden></div>
      </section>

      <div class="mg-cols">
        <section class="mg-sec">
          <div class="mg-sec-h"><h2>By caller</h2></div>
          <div class="mg-tablewrap"><table class="mg-table" id="t-va"></table></div>
        </section>
        <section class="mg-sec">
          <div class="mg-sec-h"><h2>By category</h2><span class="mg-note" id="side-note"></span></div>
          <div class="mg-tablewrap"><table class="mg-table" id="t-cat"></table></div>
        </section>
      </div>

      <section class="mg-sec">
        <div class="mg-sec-h"><h2>When people pick up</h2><span class="mg-note">Connects by hour and weekday · darker is more</span></div>
        <div class="mg-heat" id="heat"></div>
      </section>

      <section class="mg-sec">
        <div class="mg-sec-h"><h2>Callbacks and texts</h2></div>
        <div class="mg-facts" id="facts"></div>
      </section>

      <section class="mg-sec">
        <div class="mg-sec-h"><h2>Cost per result</h2><span class="mg-note" id="econ-note"></span></div>
        <div class="mg-tablewrap"><table class="mg-table" id="t-econ"></table></div>
      </section>

      <section class="mg-sec">
        <div class="mg-sec-h"><h2>Lists</h2><span class="mg-note">One row per import day</span></div>
        <div class="mg-tablewrap"><table class="mg-table" id="t-lists"></table></div>
      </section>

      <section class="mg-sec" id="review-sec">
        <div class="mg-sec-h"><h2>Calls to review</h2><span class="mg-note" id="rq-note">Lowest score first</span></div>
        <div id="rq"></div>
      </section>

      <section class="mg-sec">
        <div class="mg-sec-h"><h2>Coaching trend</h2><span class="mg-note">Weekly average score, out of 25</span></div>
        <div class="mg-tablewrap"><table class="mg-table" id="t-trend"></table></div>
      </section>
    </div>
  </section>
</div>
<script src="/static/manager.js?v=1"></script>
</body>
</html>
"""
