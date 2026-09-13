"""Coach tab — one page for the VA's growth.

    GET  /coach                          the page (desk shell + sign-in gate)
    POST /api/va/coach/home              everything the page needs in one call
    POST /api/va/coaching/my-calls       the VA's own scored calls, newest first
    POST /api/va/coaching/playbook       the whole script kit, no prospect needed

Sections the page renders from /home: this week's numbers and dial streak,
the weekly class (current + last eight), the focus line to practise, calls
to review with the rubric and the manager's notes, the six-week coaching
trend, the playbook, and the chat coach (which /api/coach/chat now feeds
with `coach_context()` so it knows her numbers, her focus, and the kit).

Auth follows the desk convention: Bearer desk JWT or {code, va_name}. A VA
sees only herself; managers and the shared passcode may pass `va`.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, Response, jsonify, request

from desk_auth import desk_identity, is_manager
from models import DeskActivity
from models_analytics import CallScore, CoachingClass, SCORE_DIMENSIONS

coachhub_bp = Blueprint("coachhub", __name__)
logger = logging.getLogger(__name__)

LABEL = {"opener": "the opener", "discovery": "discovery questions", "objection": "handling objections",
         "close": "the close", "compliance": "the recording notice"}


def _sees_everyone(ident):
    return is_manager(ident) or ident.get("via") == "passcode"


def _ident_or_401():
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return None, data, (jsonify({"error": "Sign in to the desk first."}), 401)
    return ident, data, None


def _scope_va(ident, data):
    want = (data.get("va") or "").strip()
    if want and _sees_everyone(ident):
        return want
    return ident.get("name") or ""


def _first(name):
    return (name or "").strip().split(" ")[0] or "Tracy"


# ---------------------------------------------------------------------------
# blocks
# ---------------------------------------------------------------------------
def week_stats(va):
    """This week's funnel for one VA plus a dial streak over the last 14 days."""
    from analytics import window, funnel, timeseries
    start, end, label, _days = window({"period": "week"})
    f = funnel(start, end, va)
    s_start, s_end, _l, _d = window({"days": 14})
    series = timeseries(s_start, s_end, va)
    streak = 0
    rows = list(series)
    if rows and rows[-1]["dials"] == 0:      # today may not have started yet
        rows = rows[:-1]
    for r in reversed(rows):
        wd = date.fromisoformat(r["day"]).weekday()
        if r["dials"] > 0:
            streak += 1
        elif wd >= 5:
            continue                         # a quiet weekend doesn't break a streak
        else:
            break
    hours = 0.0
    try:
        from va_time import totals_for
        hours = round((totals_for(va).get("week_seconds") or 0) / 3600.0, 1)
    except Exception:
        logger.exception("coach: hours for %s failed", va)
    return {"label": label, "dials": f["dials"], "connects": f["connects"], "interested": f["interested"],
            "wins": f["wins"], "reach_rate": f.get("reach_rate"), "conversion": f.get("conversion"),
            "hours": hours, "streak": streak,
            "series": [{"day": r["day"], "dials": r["dials"], "interested": r["interested"]} for r in series]}


def class_block(va, ident):
    from coaching_class import current_for, _now as _cnow
    cur = current_for(va)
    rows = (CoachingClass.query.filter_by(va_name=va)
            .order_by(CoachingClass.week_start.desc()).limit(8).all())
    now = _cnow()
    return {
        "current": cur.to_dict() if cur else None,
        "blocking": bool(cur and cur.status == "assigned" and not _sees_everyone(ident)),
        "overdue": bool(cur and cur.status == "assigned" and cur.due_at and cur.due_at < now),
        "history": [c.to_dict() for c in rows],
    }


def focus_block(klass):
    """The one thing to practise this week, from the newest class that has a lesson."""
    src = klass.get("current") or (klass.get("history") or [None])[0]
    if not src:
        return None
    lesson = src.get("lesson") or {}
    fixes = [{"point": f.get("point"), "say_instead": f.get("say_instead")} for f in (lesson.get("fix") or [])[:3]]
    drill = lesson.get("drill") or {}
    weakest = src.get("weakest")
    return {"week_start": src.get("week_start"), "weakest": weakest, "label": LABEL.get(weakest, weakest),
            "avg_total": src.get("avg_total"), "title": lesson.get("title"), "summary": lesson.get("summary"),
            "fixes": fixes, "drill": {"line": drill.get("line"), "why": drill.get("why")} if drill.get("line") else None}


def my_calls(va, days=14, limit=12):
    from coaching import _payload, top_fix
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    q = CallScore.query.filter(CallScore.va_name == va, CallScore.created_at >= since)
    rows = q.order_by(CallScore.created_at.desc()).limit(limit).all()
    out = []
    for s in rows:
        p = _payload(s, with_excerpt=True)
        act = DeskActivity.query.filter_by(twilio_sid=s.call_sid).first() if s.call_sid else None
        p["recording_url"] = act.recording_url if act else None
        p["duration"] = act.duration if act else None
        p["at"] = s.created_at.isoformat() if s.created_at else None
        p["link"] = "/va/calls?prospect=" + s.prospect_id if s.prospect_id else None
        p["top_fix"] = p.get("top_fix") or top_fix(s)
        out.append(p)
    total = q.count()
    avg = round(sum(s.total for s in rows) / len(rows), 1) if rows else None
    reviewed = sum(1 for s in rows if s.reviewed_at)
    return {"calls": out, "total": total, "avg_total": avg, "reviewed": reviewed, "days": days}


def trend_block(va):
    from coaching import trend
    rows = trend(days=56, va=va).get(va, [])
    return {"dimensions": list(SCORE_DIMENSIONS), "labels": LABEL, "weeks": rows}


def _pairs(rows, a, b):
    out = []
    for r in rows or []:
        if isinstance(r, dict):
            out.append({a: r.get(a), b: r.get(b)})
        elif isinstance(r, (list, tuple)) and len(r) >= 2:
            out.append({a: r[0], b: r[1]})
    return out


def playbook(va_first):
    import call_kit as ck
    from va_calls import OPENERS
    def fmt(s):
        return s.format(va=va_first) if isinstance(s, str) else s
    openers = [{"key": k, "text": fmt(v)} for k, v in OPENERS.items()]
    tracks = {}
    for seg, t in ck._DEMAND_TRACKS.items():
        tracks[seg] = {"discover": list(t.get("discover") or []), "pitch": t.get("pitch"), "close": t.get("close")}
    supply = dict(ck._SUPPLY_TRACK)
    supply["opener"] = fmt(supply.get("opener"))
    prices = []
    try:
        prices = ck.price_sheet()
    except Exception:
        logger.exception("coach: price sheet failed")
    by_label = {r["label"]: r["from"] for r in prices}
    vars_ = {"va": va_first, "sofa": by_label.get("Sofa", "—"), "mattress": by_label.get("Mattress", "—")}
    def fill(rows, a, b):
        out = []
        for r in _pairs(rows, a, b):
            try:
                r[b] = (r[b] or "").format(**vars_)
            except (KeyError, IndexError, ValueError):
                pass
            out.append(r)
        return out
    return {"openers": openers,
            "demand": {"tracks": tracks, "objections": fill(ck._DEMAND_OBJECTIONS, "say", "reply"),
                       "answers": fill(ck._DEMAND_ANSWERS, "q", "a")},
            "supply": {"track": supply, "objections": fill(ck._SUPPLY_OBJECTIONS, "say", "reply"),
                       "answers": fill(ck._SUPPLY_ANSWERS, "q", "a")},
            "prices": prices,
            "price_note": "All-in prices from the live engine. Quote these as 'from' — photos set the exact number."}


def coach_context(va):
    """Plain-text briefing the chat coach reads before answering: her week,
    her focus, her last scored calls, and the essentials of the kit."""
    parts = ["ABOUT " + (va or "the VA").upper() + " (live data — use it, never invent numbers):"]
    try:
        w = week_stats(va)
        parts.append("- This week: {dials} dials, {connects} reached, {interested} interested, {wins} wins, "
                     "{hours}h on the clock. Dial streak: {streak} working days.".format(**w))
    except Exception:
        logger.exception("coach context: week failed")
    try:
        k = class_block(va, {"role": "manager"})
        f = focus_block(k)
        if f:
            parts.append("- Weekly class focus: {} (avg {}/25). Status: {}.".format(
                f["label"], f.get("avg_total"), (k.get("current") or {}).get("status", "none")))
            for fx in f["fixes"]:
                parts.append("  fix: {}{}".format(fx["point"], (" → say: " + fx["say_instead"]) if fx.get("say_instead") else ""))
            if f.get("drill"):
                parts.append("  drill line: " + f["drill"]["line"])
    except Exception:
        logger.exception("coach context: class failed")
    try:
        c = my_calls(va, days=14, limit=4)
        for p in c["calls"]:
            parts.append("- Recent call: {} scored {}/25; next time: {}".format(
                p.get("company") or "unknown company", p.get("total"), p.get("top_fix") or "—"))
    except Exception:
        logger.exception("coach context: calls failed")
    try:
        pb = playbook(_first(va))
        parts.append("PLAYBOOK ESSENTIALS:")
        for o in pb["demand"]["objections"][:8]:
            parts.append("- Demand objection \"{}\" → {}".format(o["say"], o["reply"]))
        for o in pb["supply"]["objections"][:6]:
            parts.append("- Supply objection \"{}\" → {}".format(o["say"], o["reply"]))
        if pb["prices"]:
            parts.append("- Prices (all-in, from): " + "; ".join("{} ${}".format(r["label"], r["from"]) for r in pb["prices"][:14]))
    except Exception:
        logger.exception("coach context: playbook failed")
    return "\n".join(parts)[:7000]


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------
@coachhub_bp.route("/api/va/coach/home", methods=["POST"])
def api_home():
    ident, data, err = _ident_or_401()
    if err:
        return err
    va = _scope_va(ident, data)
    out = {"va": va, "first": _first(va), "manager": _sees_everyone(ident)}
    for key, fn in (("week", lambda: week_stats(va)), ("klass", lambda: class_block(va, ident)),
                    ("calls", lambda: my_calls(va)), ("trend", lambda: trend_block(va)),
                    ("playbook", lambda: playbook(_first(va)))):
        try:
            out[key] = fn()
        except Exception:
            logger.exception("coach home: %s failed", key)
            out[key] = None
    out["focus"] = focus_block(out.get("klass") or {}) if out.get("klass") else None
    if out["manager"]:
        try:
            names = [r[0] for r in CallScore.query.with_entities(CallScore.va_name).distinct().all() if r[0]]
            out["vas"] = sorted(set(names) | ({va} if va else set()))
        except Exception:
            out["vas"] = [va]
    return jsonify(out), 200


@coachhub_bp.route("/api/va/coaching/my-calls", methods=["POST"])
def api_my_calls():
    ident, data, err = _ident_or_401()
    if err:
        return err
    va = _scope_va(ident, data)
    try:
        days = min(max(int(data.get("days") or 14), 1), 120)
        limit = min(max(int(data.get("limit") or 12), 1), 60)
    except (TypeError, ValueError):
        days, limit = 14, 12
    return jsonify(dict(my_calls(va, days, limit), va=va)), 200


@coachhub_bp.route("/api/va/coaching/playbook", methods=["POST"])
def api_playbook():
    ident, data, err = _ident_or_401()
    if err:
        return err
    return jsonify(playbook(_first(ident.get("name")))), 200


# ---------------------------------------------------------------------------
# page
# ---------------------------------------------------------------------------
COACH_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<meta name="robots" content="noindex, nofollow" />
<title>Coach — Umuve desk</title>
<meta name="theme-color" content="#E4E5E9" />
<link rel="stylesheet" href="/va/app.css?v=6" />
<link rel="stylesheet" href="/static/desk-shell.css?v=3" />
<script src="/static/desk-shell.js?v=2" defer></script>
<link rel="stylesheet" href="/static/desk-gate.css?v=2" />
<script src="/static/desk-gate.js?v=2" defer></script>
<link rel="stylesheet" href="/static/desk-class.css?v=3" />
<link rel="stylesheet" href="/static/coach.css?v=2" />
</head>
<body>
<div id="app">
  <section id="gate" class="gate">
    <div class="gatewrap">
      <img class="brand-lg rv" src="/static/brand-logo.png" alt="Umuve" /><div class="eyebrow rv">Internal · VA suite</div>
      <h1 class="display" aria-label="Coach">Coach</h1>
      <p class="sub rv">Your week, your class, your calls, and a coach who has read all of it.</p>
      <form id="gate-form" autocomplete="off" class="rv">
        <label class="lbl" for="va-name">Your first name</label>
        <input id="va-name" type="text" autocomplete="given-name" placeholder="Tracy" />
        <label class="lbl" for="code">Access code</label>
        <input id="code" type="password" autocomplete="off" placeholder="Enter your code" />
        <button class="btn" type="submit">Open the coach</button>
        <p id="gate-err" class="err" hidden></p>
      </form>
      <p class="hint rv">Same code as the Call Desk.</p>
    </div>
  </section>

  <section id="tool" class="tool" hidden>
    <header class="bar">
      <a class="back" href="/va" aria-label="Back to VA tools">←</a>
      <span class="wordmark">Coach</span>
      <span class="bar-sub" id="who"></span>
    </header>
    <div class="body co" id="co">
      <div class="co-va" id="co-va" hidden><span>Coaching</span><select id="co-va-sel"></select></div>

      <section class="co-panel co-week" id="co-week" aria-label="This week"></section>

      <div class="co-two">
        <section class="co-panel co-focus" id="co-class" aria-label="Weekly class"></section>
        <section class="co-panel" id="co-trend" aria-label="Coaching trend">
          <div class="co-h"><h2>How your calls are scoring</h2><span class="co-note">weekly average, last 8 weeks</span></div>
          <svg class="co-trend" id="co-trend-svg" viewBox="0 0 600 150" preserveAspectRatio="none" role="img" aria-label="Weekly rubric averages"></svg>
          <div class="co-legend" id="co-legend"></div>
        </section>
      </div>

      <section class="co-panel" id="co-calls" aria-label="Calls to review"></section>

      <div class="co-two">
        <section class="co-panel" id="co-playbook" aria-label="Playbook">
          <div class="co-h"><h2>Playbook</h2><span class="co-note">the same lines the Call Desk shows, all in one place</span></div>
          <div class="co-search">
            <input id="co-q" type="search" placeholder="Search a line, an objection, a price…" />
            <div class="co-tabs" id="co-pb-tabs">
              <button type="button" data-t="objections" class="on">Objections</button>
              <button type="button" data-t="answers">Answers</button>
              <button type="button" data-t="openers">Openers</button>
              <button type="button" data-t="tracks">Tracks</button>
              <button type="button" data-t="prices">Prices</button>
            </div>
          </div>
          <div class="co-pb" id="co-pb"></div>
        </section>
        <section class="co-panel co-chat" id="co-chat" aria-label="Ask your coach">
          <div class="co-h"><h2>Ask your coach</h2><button type="button" class="co-clear" id="co-clear">Clear</button></div>
          <div class="co-thread" id="co-thread"></div>
          <div class="co-chips" id="co-chips"></div>
          <form class="co-composer" id="co-form">
            <textarea id="co-input" rows="1" placeholder="Ask about a call, an objection, a line to say…"></textarea>
            <button class="co-send" id="co-send" type="submit" aria-label="Send">↑</button>
          </form>
        </section>
      </div>

      <section class="co-panel" id="co-history" aria-label="Past classes"></section>
    </div>
  </section>
</div>
<script src="/static/desk-class.js?v=2" defer></script>
<script src="/static/coach.js?v=1" defer></script>
</body>
</html>
"""


def coach_page():
    resp = Response(COACH_PAGE, mimetype="text/html")
    resp.headers["Cache-Control"] = "no-cache, must-revalidate"
    return resp
