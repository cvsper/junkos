"""Weekly improvement class — AI coaching Tracy has to take.

Every scored call already carries a rubric, strengths and fixes
(coaching.py). At the end of each week this rolls one VA's week into a
short class: what she did well (with her own words quoted back), what to
fix (with the line and what to say instead), a 60-second drill, and a
three-question check. It's assigned Friday at 5pm business time, due the
following Monday night, and the desk holds an overlay until it's done.

    POST /api/va/coaching/class/current   {va?}                 her open class (manager: any VA)
    POST /api/va/coaching/class/complete  {class_id, answers, reflection}
    POST /api/va/coaching/class/history   {va?, limit}
    POST /api/va/coaching/class/build     {va, week_start?, force?}   manager; (re)build now
    POST /api/va/coaching/class/waive     {class_id, note}             manager

Claude writes the lesson when ANTHROPIC_API_KEY is set (COPILOT_MODEL,
strict JSON); otherwise a rubric-driven template does, so the class always
exists even if the model is down. One class per VA per week.
"""
from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from desk_auth import desk_identity, is_manager, audit
from models import db, CallProspect
from models_analytics import CallScore, CoachingClass, SCORE_DIMENSIONS

try:
    from extensions import limiter
except Exception:  # pragma: no cover
    limiter = None

logger = logging.getLogger(__name__)
class_bp = Blueprint("coaching_class", __name__)
_ratelimit = (limiter.limit("240 per hour; 60 per minute") if limiter is not None else (lambda f: f))

ASSIGN_WEEKDAY, ASSIGN_HOUR = 4, 17          # Friday 5pm business time
DUE_DAYS_AFTER_WEEK = 1                       # Monday 23:59 of the following week
MIN_CALLS = 1
QUIZ_N = 3
LABEL = {"opener": "the opener", "discovery": "discovery questions", "objection": "handling objections",
         "close": "the close", "compliance": "the recording notice"}

# What good sounds like, per dimension — used when Claude isn't available and
# as the drill line the VA repeats out loud.
DRILL = {
    "opener": "Hi, this is Tracy with Umuve — quick heads up, this call's recorded. I'm calling because we take "
              "cleanouts off property managers' plates in Palm Beach. Got a minute?",
    "discovery": "Before I tell you anything — who handles move-out cleanouts for you today, and how many doors "
                 "are you running?",
    "objection": "Totally fair, most people have someone. The reason folks add us is one number for every unit, "
                 "quoted up front from photos — can I leave that on file for the next time your guy's booked?",
    "close": "Can I put a rate card on file so your managers have the number? Who should I send it to?",
    "compliance": "Quick heads up before we start — this call is recorded, is that alright?",
}
QUIZ_BANK = {
    "opener": [
        {"q": "What are the three things a strong opener does in the first ten seconds?",
         "options": ["Name, company, and the price", "Name, company, why you're calling, and asks for a moment",
                     "Asks how their day is going", "Explains everything Umuve offers"], "answer": 1,
         "why": "They decide in ten seconds whether to keep listening. Who you are, why you're calling, and permission to continue."},
        {"q": "The prospect says 'who is this?' after your hello. What went wrong?",
         "options": ["Nothing, that's normal", "You skipped your name and Umuve", "They're rude", "You called too early"], "answer": 1,
         "why": "'Who is this' means the opener didn't land. Lead with name and company every time."},
        {"q": "Best way to ask for their time?",
         "options": ["'Is this a bad time?'", "'Got a minute?'", "Don't ask, just pitch", "'Can I have ten minutes?'"], "answer": 1,
         "why": "Short and easy to say yes to. 'Bad time?' invites a no; ten minutes is too big an ask."},
    ],
    "discovery": [
        {"q": "When should the first real question come?",
         "options": ["After the full pitch", "Before you say what Umuve costs", "Only if they object", "At the close"], "answer": 1,
         "why": "Questions first. You can't pitch what matters to them until you know what they deal with."},
        {"q": "Which is a discovery question?",
         "options": ["'We're the cheapest, right?'", "'Who handles move-out cleanouts for you today?'",
                     "'Can I send a rate card?'", "'Are you the owner?'"], "answer": 1,
         "why": "It asks about their world and gets them talking about the problem you solve."},
        {"q": "They say 'about two hundred doors'. What's the next move?",
         "options": ["Pitch immediately", "Ask how often units turn over", "Ask for the email", "Thank them and hang up"], "answer": 1,
         "why": "Two hundred doors is volume — one more question sizes the opportunity and shows you listened."},
    ],
    "objection": [
        {"q": "'We already have a guy.' Best response?",
         "options": ["'Okay, thanks anyway.'", "'Totally fair — the reason people add us is one up-front number for every unit. Can I leave it on file for when your guy's booked?'",
                     "'He's probably more expensive.'", "'Are you sure?'"], "answer": 1,
         "why": "Acknowledge, then give a concrete reason to keep a second option. Never argue with the current guy."},
        {"q": "'How much does it cost?' early in the call. You should:",
         "options": ["Say you don't know", "Give a real anchor number and one benefit, then ask a question",
                     "Refuse until you've pitched", "Send them to the website"], "answer": 1,
         "why": "A price question is interest. Answer it plainly, attach the benefit, and keep the conversation going."},
        {"q": "The prospect pushes back twice. When do you stop?",
         "options": ["Never", "After the second clean no — ask if you can leave a rate card and go", "After the first no", "When they hang up"], "answer": 1,
         "why": "One answer to an objection is selling; three is pestering. Leave something on file and exit well."},
    ],
    "close": [
        {"q": "Which is a concrete next step?",
         "options": ["'Keep us in mind.'", "'Can I put a rate card on file — who should I send it to?'",
                     "'Check out our website.'", "'Have a good one.'"], "answer": 1,
         "why": "A close names the action and who does it. Everything else is a polite goodbye."},
        {"q": "They said yes to the rate card. What do you confirm before hanging up?",
         "options": ["Nothing", "The email address and their name, read back", "Their budget", "Their address"], "answer": 1,
         "why": "A yes with a wrong email is a no. Read it back."},
        {"q": "The call went well but you never asked for anything. Score for close?",
         "options": ["5", "0–1", "3", "Depends on their mood"], "answer": 1,
         "why": "A good conversation without an ask is a missed close, however friendly it felt."},
    ],
    "compliance": [
        {"q": "Why do we say the call is recorded?",
         "options": ["It sounds professional", "Florida is two-party consent — recording without notice is illegal",
                     "The manager likes it", "It isn't required"], "answer": 1,
         "why": "Florida requires all parties to consent. The notice protects you and the company."},
        {"q": "When does the notice go?",
         "options": ["At the end", "Near the start, before the conversation gets going", "Only if they ask", "In the follow-up text"], "answer": 1,
         "why": "Consent has to come before the recorded conversation, not after."},
        {"q": "Shortest way to say it that still counts?",
         "options": ["'This call may be monitored.'", "'Quick heads up, this call's recorded.'", "'Legal stuff, ignore it.'", "Don't say it"], "answer": 1,
         "why": "Plain and quick. It doesn't need to sound like a disclaimer."},
    ],
}


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _local(dt_naive):
    from timeutils import to_local
    return to_local(dt_naive.replace(tzinfo=timezone.utc))


def _to_utc(local_naive):
    from timeutils import local_naive_to_utc
    return local_naive_to_utc(local_naive).replace(tzinfo=None)


def week_bounds(day):
    """(start_utc_naive, end_utc_naive, monday_iso) for the business week containing `day`."""
    monday = day - timedelta(days=day.weekday())
    start = _to_utc(datetime.combine(monday, datetime.min.time()))
    end = _to_utc(datetime.combine(monday + timedelta(days=7), datetime.min.time()))
    return start, end, monday.isoformat()


def class_week_for(now=None):
    """Which week's class should be open right now: this week from Friday 5pm
    on, otherwise last week."""
    loc = _local(now or _now())
    today = loc.date()
    if loc.weekday() > ASSIGN_WEEKDAY or (loc.weekday() == ASSIGN_WEEKDAY and loc.hour >= ASSIGN_HOUR):
        return today
    return today - timedelta(days=7)


def _due_for(monday_iso):
    monday = datetime.fromisoformat(monday_iso).date()
    return _to_utc(datetime.combine(monday + timedelta(days=7 + DUE_DAYS_AFTER_WEEK), datetime.min.time())
                   - timedelta(minutes=1))


def _excerpt(call_sid, n=8):
    from coaching import _excerpt as ex
    return ex(call_sid, n=n)


def _company(score):
    p = db.session.get(CallProspect, score.prospect_id) if score.prospect_id else None
    return p.company if p else None


def _heuristic_lesson(va, week_iso, scores, dims, weakest, best, worst):
    strengths = Counter(s for sc in scores for s in (sc.strengths or []))
    fixes = Counter(f for sc in scores for f in (sc.fixes or []))
    went_well = [{"point": s, "quote": None} for s, _ in strengths.most_common(3)]
    if best is not None:
        lines = [l["text"] for l in _excerpt(best.call_sid) if l["track"] == "va"]
        if lines and went_well:
            went_well[0]["quote"] = max(lines, key=len)[:200]
    fix = [{"point": f, "quote": None, "say_instead": DRILL[weakest]} for f, _ in fixes.most_common(3)]
    if worst is not None:
        lines = [l["text"] for l in _excerpt(worst.call_sid) if l["track"] == "va"]
        if lines and fix:
            fix[0]["quote"] = max(lines, key=len)[:200]
    if not fix:
        fix = [{"point": "Work on {}.".format(LABEL[weakest]), "quote": None, "say_instead": DRILL[weakest]}]
    return {
        "title": "Week of {}: sharpen {}".format(week_iso, LABEL[weakest]),
        "summary": "{n} scored call{s}, averaging {avg}/25. Strongest: {best}. Weakest: {weak} — that's this week's focus.".format(
            n=len(scores), s="" if len(scores) == 1 else "s", avg=round(sum(s.total for s in scores) / len(scores), 1),
            best=LABEL[max(dims, key=dims.get)], weak=LABEL[weakest]),
        "went_well": went_well, "fix": fix,
        "drill": {"line": DRILL[weakest], "why": "Say it out loud five times before your first call Monday. "
                                                 "It should come out without thinking."},
        "quiz": list(QUIZ_BANK[weakest])[:QUIZ_N],
    }


def _claude_lesson(va, week_iso, scores, dims, weakest, best, worst):
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return None
    def convo(sc):
        return "\n".join("{}: {}".format("PROSPECT" if l["track"] == "them" else "VA", l["text"]) for l in _excerpt(sc.call_sid, n=14))
    notes = "\n".join("- call {} ({}): {}/25; strengths: {}; fixes: {}".format(
        i + 1, _company(sc) or "unknown", sc.total, "; ".join(sc.strengths or []) or "—", "; ".join(sc.fixes or []) or "—")
        for i, sc in enumerate(scores[:12]))
    prompt = (
        "You are a warm, direct sales coach writing a short weekly improvement class for {va}, a virtual assistant "
        "who cold-calls property managers, HOAs and haulers for Umuve, a junk-removal marketplace in Florida. "
        "Week of {week}. She made {n} scored calls. Rubric averages out of 5: {dims}. Weakest: {weak}.\n\n"
        "Per-call notes:\n{notes}\n\nHer best call:\n{best}\n\nHer weakest call:\n{worst}\n\n"
        "Write the class as ONLY a JSON object with these keys:\n"
        "title (under 60 chars, names the one focus), summary (2 sentences, second person, honest and encouraging),\n"
        "went_well: [2-3 of {{point, quote}}] where quote is her actual words from a transcript above (or null),\n"
        "fix: [2-3 of {{point, quote, say_instead}}] most important first; quote = what she said, say_instead = the exact better line,\n"
        "drill: {{line, why}} one line she should say out loud before Monday's first call,\n"
        "quiz: [3 of {{q, options[4], answer (0-3), why}}] about the focus area, answerable from this class.\n"
        "Keep quotes verbatim and short. No markdown."
    ).format(va=va, week=week_iso, n=len(scores), dims=", ".join("{} {:.1f}".format(d, dims[d]) for d in SCORE_DIMENSIONS),
             weak=weakest, notes=notes, best=convo(best) if best else "—", worst=convo(worst) if worst else "—")
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(model=os.environ.get("COPILOT_MODEL", "claude-haiku-4-5-20251001"),
                                      max_tokens=1400, messages=[{"role": "user", "content": prompt}])
        text = "".join(getattr(b, "text", "") for b in resp.content)
        m = re.search(r"\{.*\}", text, re.S)
        data = json.loads(m.group(0)) if m else None
        if not isinstance(data, dict) or not data.get("quiz") or not data.get("fix"):
            return None
        quiz = []
        for q in data["quiz"][:QUIZ_N]:
            opts = [str(o)[:160] for o in (q.get("options") or [])][:4]
            if len(opts) == 4 and isinstance(q.get("answer"), int) and 0 <= q["answer"] < 4:
                quiz.append({"q": str(q.get("q"))[:240], "options": opts, "answer": q["answer"], "why": str(q.get("why") or "")[:300]})
        if len(quiz) < 2:
            return None
        clean = lambda items, keys: [{k: (str(it.get(k))[:300] if it.get(k) is not None else None) for k in keys}  # noqa: E731
                                     for it in (items or []) if isinstance(it, dict)][:3]
        return {
            "title": str(data.get("title") or "")[:80] or "This week's class",
            "summary": str(data.get("summary") or "")[:500],
            "went_well": clean(data.get("went_well"), ("point", "quote")),
            "fix": clean(data.get("fix"), ("point", "quote", "say_instead")),
            "drill": {"line": str((data.get("drill") or {}).get("line") or DRILL[weakest])[:300],
                      "why": str((data.get("drill") or {}).get("why") or "")[:300]},
            "quiz": quiz,
        }
    except Exception:
        logger.exception("coaching class: Claude failed; using template")
        return None


def build_class(va, week_start_iso, force=False):
    """Build (or rebuild) one VA's class for the week starting Monday `week_start_iso`.
    Returns the row, or None when she had no scored calls that week."""
    monday = datetime.fromisoformat(week_start_iso).date()
    start, end, week_iso = week_bounds(monday)
    existing = CoachingClass.query.filter_by(va_name=va, week_start=week_iso).first()
    if existing and not force:
        return existing
    scores = (CallScore.query.filter(CallScore.va_name == va, CallScore.created_at >= start, CallScore.created_at < end)
              .order_by(CallScore.created_at.asc()).all())
    if len(scores) < MIN_CALLS:
        return None
    dims = {d: round(sum(getattr(s, d) for s in scores) / len(scores), 2) for d in SCORE_DIMENSIONS}
    weakest = min(SCORE_DIMENSIONS, key=lambda d: (dims[d], SCORE_DIMENSIONS.index(d)))
    best = max(scores, key=lambda s: s.total)
    worst = min(scores, key=lambda s: s.total)
    lesson = _claude_lesson(va, week_iso, scores, dims, weakest, best, worst)
    source = "claude"
    if lesson is None:
        lesson = _heuristic_lesson(va, week_iso, scores, dims, weakest, best, worst)
        source = "heuristic"
    row = existing or CoachingClass(va_name=va, week_start=week_iso)
    row.calls = len(scores)
    row.avg_total = int(round(10 * sum(s.total for s in scores) / len(scores)))
    row.dims = dims
    row.weakest = weakest
    row.lesson = lesson
    row.source = source
    row.due_at = _due_for(week_iso)
    if existing and force:
        row.status, row.answers, row.quiz_score, row.reflection, row.completed_at = "assigned", None, None, None, None
    db.session.add(row)
    db.session.commit()
    return row


def vas_with_calls(start, end):
    return sorted({s.va_name for s in CallScore.query.filter(CallScore.created_at >= start, CallScore.created_at < end).all()
                   if s.va_name})


def assign_week(day=None):
    """Build the class for every VA who had scored calls in the class week.
    Scheduler: Friday 17:00 business time (idempotent, safe to rerun)."""
    day = day or class_week_for()
    start, end, week_iso = week_bounds(day)
    built = []
    for va in vas_with_calls(start, end):
        try:
            row = build_class(va, week_iso)
            if row is not None:
                built.append(row)
        except Exception:
            logger.exception("coaching class: build failed for %s", va)
    if built:
        _notify(built)
    return built


def _notify(rows):
    hook = os.environ.get("SLACK_ALERT_WEBHOOK", "").strip()
    if not hook:
        return
    try:
        import requests
        lines = ["*Weekly class ready* — due Monday night, the desk holds it until it's done."]
        for r in rows:
            lines.append("• {} — {} · {} calls · {}/25 · focus: {}".format(
                r.va_name, r.week_start, r.calls, (r.avg_total or 0) / 10.0, LABEL.get(r.weakest, r.weakest)))
        requests.post(hook, json={"text": "\n".join(lines)}, timeout=10)
    except Exception:
        logger.debug("coaching class: slack notify failed", exc_info=True)


def current_for(va):
    """The class a VA should be looking at now: the open one for the class
    week (built on demand), else the most recent unfinished one."""
    day = class_week_for()
    start, end, week_iso = week_bounds(day)
    row = CoachingClass.query.filter_by(va_name=va, week_start=week_iso).first()
    if row is None:
        try:
            row = build_class(va, week_iso)
        except Exception:
            logger.exception("coaching class: on-demand build failed for %s", va)
            row = None
    if row is None or row.status != "assigned":
        older = (CoachingClass.query.filter_by(va_name=va, status="assigned")
                 .order_by(CoachingClass.week_start.desc()).first())
        return older or row
    return row


def grade(row, answers):
    quiz = (row.lesson or {}).get("quiz") or []
    results, correct = [], 0
    for i, q in enumerate(quiz):
        a = answers[i] if i < len(answers) else None
        ok = isinstance(a, int) and a == q.get("answer")
        correct += int(ok)
        results.append({"q": q.get("q"), "your": a, "answer": q.get("answer"), "correct": ok, "why": q.get("why")})
    return correct, results


# ---------------------------------------------------------------------------
# endpoints
# ---------------------------------------------------------------------------

def _ident_or_401():
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return None, data, (jsonify({"error": "Sign in to the desk first."}), 401)
    return ident, data, None


def _sees_everyone(ident):
    return is_manager(ident) or ident.get("via") == "passcode"


def _scope_va(ident, data):
    if _sees_everyone(ident):
        return (data.get("va") or "").strip()[:80] or ident.get("name") or "—"
    return ident.get("name") or "—"


@class_bp.route("/api/va/coaching/class/current", methods=["POST"])
@_ratelimit
def api_current():
    ident, data, err = _ident_or_401()
    if err:
        return err
    va = _scope_va(ident, data)
    row = current_for(va)
    blocking = bool(row and row.status == "assigned" and not _sees_everyone(ident))
    return jsonify({"class": row.to_dict() if row else None, "blocking": blocking, "va": va,
                    "overdue": bool(row and row.status == "assigned" and row.due_at and row.due_at < _now())}), 200


@class_bp.route("/api/va/coaching/class/complete", methods=["POST"])
@_ratelimit
def api_complete():
    ident, data, err = _ident_or_401()
    if err:
        return err
    row = db.session.get(CoachingClass, (data.get("class_id") or "").strip())
    if row is None:
        return jsonify({"error": "No such class."}), 404
    if not _sees_everyone(ident) and row.va_name != (ident.get("name") or ""):
        return jsonify({"error": "That class isn't yours."}), 403
    answers = data.get("answers") or []
    if not isinstance(answers, list):
        return jsonify({"error": "answers must be a list"}), 400
    answers = [a if isinstance(a, int) else None for a in answers]
    reflection = (data.get("reflection") or "").strip()[:1000]
    if len(reflection) < 10:
        return jsonify({"error": "Write a sentence about what you'll do differently — that's the point of the class."}), 400
    correct, results = grade(row, answers)
    row.answers = answers
    row.quiz_score = correct
    row.reflection = reflection
    row.status = "completed"
    row.completed_at = _now()
    db.session.commit()
    audit("coaching_class_completed", "coaching_class", row.id,
          {"va": row.va_name, "week": row.week_start, "score": correct, "of": len(results)})
    return jsonify({"ok": True, "score": correct, "of": len(results), "results": results, "class": row.to_dict(with_answers=True)}), 200


@class_bp.route("/api/va/coaching/class/history", methods=["POST"])
@_ratelimit
def api_history():
    ident, data, err = _ident_or_401()
    if err:
        return err
    q = CoachingClass.query
    if _sees_everyone(ident):
        va = (data.get("va") or "").strip()[:80]
        if va:
            q = q.filter_by(va_name=va)
    else:
        q = q.filter_by(va_name=ident.get("name") or "—")
    limit = min(max(int(data.get("limit") or 12), 1), 52)
    rows = q.order_by(CoachingClass.week_start.desc(), CoachingClass.va_name.asc()).limit(limit).all()
    return jsonify({"classes": [r.to_dict(with_answers=_sees_everyone(ident)) for r in rows]}), 200


@class_bp.route("/api/va/coaching/class/build", methods=["POST"])
@_ratelimit
def api_build():
    ident, data, err = _ident_or_401()
    if err:
        return err
    if not _sees_everyone(ident):
        return jsonify({"error": "That needs a manager."}), 403
    va = (data.get("va") or "").strip()[:80]
    if not va:
        return jsonify({"error": "va is required"}), 400
    week = (data.get("week_start") or "").strip() or class_week_for().isoformat()
    try:
        _, _, week_iso = week_bounds(datetime.fromisoformat(week).date())
    except ValueError:
        return jsonify({"error": "week_start must be YYYY-MM-DD"}), 400
    row = build_class(va, week_iso, force=bool(data.get("force")))
    if row is None:
        return jsonify({"error": "{} had no scored calls the week of {}.".format(va, week_iso)}), 404
    audit("coaching_class_built", "coaching_class", row.id, {"va": va, "week": week_iso, "force": bool(data.get("force"))})
    return jsonify({"class": row.to_dict(with_answers=True)}), 200


@class_bp.route("/api/va/coaching/class/waive", methods=["POST"])
@_ratelimit
def api_waive():
    ident, data, err = _ident_or_401()
    if err:
        return err
    if not _sees_everyone(ident):
        return jsonify({"error": "That needs a manager."}), 403
    row = db.session.get(CoachingClass, (data.get("class_id") or "").strip())
    if row is None:
        return jsonify({"error": "No such class."}), 404
    row.status = "waived"
    row.manager_note = (data.get("note") or "").strip()[:500] or None
    db.session.commit()
    audit("coaching_class_waived", "coaching_class", row.id, {"va": row.va_name, "week": row.week_start})
    return jsonify({"class": row.to_dict(with_answers=True)}), 200
