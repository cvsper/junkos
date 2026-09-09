"""Call scorecards — a five-part rubric on every transcribed desk call, a
review queue for the manager, and a weekly trend per VA.

Scoring runs right after the post-call write-up (desk_line.desk_summarize
calls score_call_async). Claude scores when ANTHROPIC_API_KEY is set (model
COPILOT_MODEL, default claude-haiku-4-5-20251001, strict JSON); otherwise a
plain heuristic reads the transcript. Calls under MIN_LINES lines aren't
scored — there's nothing to coach on a voicemail. One score per CallSid.

Rubric (0–5 each, 25 total):
  opener      named herself and Umuve, said why she's calling, asked for a minute
  discovery   asked real questions before pitching
  objection   heard the pushback and answered it
  close       asked for a concrete next step
  compliance  gave the recording notice (Florida is two-party consent)

Endpoints (JSON POST, desk identity):
  POST /api/va/coaching/scorecard     {prospect_id | call_sid | company, phone}  VA own / manager any
  POST /api/va/coaching/review-queue  {days, limit}                              manager
  POST /api/va/coaching/review        {call_sid, note, tags}                     manager; audited
  POST /api/va/coaching/trend         {days, va}                                 VA own / manager any
"""
from __future__ import annotations

import json
import logging
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from desk_auth import desk_identity, is_manager, audit
from models import db, CallProspect, DeskActivity, DeskTranscriptLine
from models_analytics import CallScore, SCORE_DIMENSIONS

try:
    from extensions import limiter
except Exception:  # pragma: no cover
    limiter = None

logger = logging.getLogger(__name__)
coaching_bp = Blueprint("coaching", __name__)

_ratelimit = (limiter.limit("240 per hour; 60 per minute") if limiter is not None
              else (lambda f: f))

MIN_LINES = 6
DIMENSION_LABELS = {"opener": "Opener", "discovery": "Discovery", "objection": "Objections",
                    "close": "Close", "compliance": "Recording notice"}

_OBJECTION_RX = re.compile(
    r"\bnot interested\b|\bno thank|\balready (have|got|use)\b|\bhow much\b|\bcost\b|\bprice\b|"
    r"\bbusy\b|\bbad time\b|\bcall (me )?back\b|\bsend (me|us)\b|\bwho is this\b|\bhow did you get\b|"
    r"\bdumpster\b|\binsur|\blicens|\bcatch\b|\benough work\b|\bapps?\b|\bget paid\b", re.I)
_OPENER_NAME_RX = re.compile(r"\b(this is|it's|it is|i'm|i am|my name is)\b", re.I)
_OPENER_WHY_RX = re.compile(r"\b(calling|reason|quick question|reaching out|because|about)\b", re.I)
_OPENER_ASK_RX = re.compile(r"\b(minute|second|moment|bad time|good time|catch you)\b", re.I)
_CLOSE_RX = re.compile(
    r"\bcan i (send|put|text|email|get)\b|\bwho should i\b|\bwhat'?s the best (email|number)\b|"
    r"\brate card\b|\bsend (you|it|that) over\b|\bfollow up\b|\bwhen'?s (a )?good\b|\bput (you|us) on\b|"
    r"\bon file\b|\bnext step\b|\bwould (it be|you be) (ok|okay|open)\b|\bcan i get\b|\bshall i\b", re.I)
_YES_RX = re.compile(r"\b(yes|yeah|sure|ok|okay|sounds good|go ahead|please do|that works)\b", re.I)
_RECORDED_RX = re.compile(r"\brecord(ed|ing)\b", re.I)


def _norm_lines(lines):
    out = []
    for l in lines or []:
        if isinstance(l, dict):
            track, text = l.get("track"), l.get("text")
        else:
            track, text = getattr(l, "track", None), getattr(l, "text", None)
        if text:
            out.append({"track": "them" if track == "them" else "va", "text": str(text)})
    return out


def _clamp(v):
    try:
        return max(0, min(5, int(round(float(v)))))
    except (TypeError, ValueError):
        return 0


def _words(s):
    return len(re.findall(r"\w+", s or ""))


def heuristic_score(lines):
    """Transcript → {dimension: 0-5, strengths: [...], fixes: [...]}."""
    lines = _norm_lines(lines)
    va = [l["text"] for l in lines if l["track"] == "va"]
    va_blob = " ".join(va)
    # opener: her first two lines
    head = " ".join(va[:2])
    opener = 0
    if re.search(r"\bumuve\b", head, re.I):
        opener += 2
    if _OPENER_NAME_RX.search(head):
        opener += 1
    if _OPENER_WHY_RX.search(head):
        opener += 1
    if head and (_OPENER_ASK_RX.search(head) or _words(head) <= 45):
        opener += 1
    # discovery: real questions from the VA
    questions = sum(1 for t in va if "?" in t)
    discovery = {0: 0, 1: 2, 2: 3, 3: 4}.get(questions, 5)
    # objections: did they push back, and did she answer with substance
    objections = 0
    answered = 0
    for i, l in enumerate(lines):
        if l["track"] == "them" and _OBJECTION_RX.search(l["text"]):
            objections += 1
            nxt = next((m for m in lines[i + 1:] if m["track"] == "va"), None)
            if nxt and _words(nxt["text"]) >= 6:
                answered += 1
    if objections == 0:
        objection = 3          # nothing to handle — neutral
    else:
        objection = 1 + round(4 * answered / objections)
    # close: asked for a next step; better if they said yes after
    close = 1
    for i, l in enumerate(lines):
        if l["track"] == "va" and _CLOSE_RX.search(l["text"]):
            close = 4
            after = next((m for m in lines[i + 1:] if m["track"] == "them"), None)
            if after and _YES_RX.search(after["text"]):
                close = 5
            break
    compliance = 5 if _RECORDED_RX.search(va_blob) else 2
    scores = {"opener": _clamp(opener), "discovery": _clamp(discovery), "objection": _clamp(objection),
              "close": _clamp(close), "compliance": _clamp(compliance)}
    strengths, fixes = [], []
    # the recording notice is the one legal requirement — it leads the list
    if scores["compliance"] < 5:
        fixes.append("Say the call is recorded before the conversation starts.")
    else:
        strengths.append("Recording notice given.")
    if scores["opener"] >= 4:
        strengths.append("Clean opener: who you are, why you're calling.")
    elif scores["opener"] <= 2:
        fixes.append("Open with your name, Umuve, and the reason in one breath.")
    if scores["discovery"] >= 4:
        strengths.append("Asked {} questions before pitching.".format(questions))
    elif scores["discovery"] <= 2:
        fixes.append("Ask two questions before the pitch — who handles hauling today, how often.")
    if objections and scores["objection"] >= 4:
        strengths.append("Answered their pushback instead of retreating.")
    elif objections and scores["objection"] <= 2:
        fixes.append("When they push back, answer it in a full sentence, then ask a question.")
    if scores["close"] >= 4:
        strengths.append("Asked for a concrete next step.")
    else:
        fixes.append("End by asking for one thing: a rate card on file, an email, or a time.")
    return dict(scores, strengths=strengths[:3], fixes=fixes[:3])


def claude_score(lines, prospect):
    """→ same shape as heuristic_score, or None when Claude isn't configured / fails."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return None
    lines = _norm_lines(lines)
    convo = "\n".join("{}: {}".format("PROSPECT" if l["track"] == "them" else "VA", l["text"])
                      for l in lines)[-7000:]
    prompt = (
        "You are a sales coach grading one cold call made by a virtual assistant for Umuve, a "
        "junk-removal marketplace in South Florida. Company called: {co} ({cat}). Contact: {contact}.\n\n"
        "Transcript:\n{convo}\n\n"
        "Score each dimension 0-5 (integers):\n"
        "- opener: named herself and Umuve, said why she's calling, asked for a moment\n"
        "- discovery: asked real questions about their situation before pitching\n"
        "- objection: heard pushback and answered it with substance (score 3 if there was none)\n"
        "- close: asked for a concrete next step (rate card on file, email, callback time)\n"
        "- compliance: told them the call is recorded near the start\n"
        "Return ONLY a JSON object: {{\"opener\":n,\"discovery\":n,\"objection\":n,\"close\":n,"
        "\"compliance\":n,\"strengths\":[up to 3 short specific sentences],"
        "\"fixes\":[up to 3 short specific sentences, most important first]}}"
    ).format(co=prospect.company if prospect else "unknown", cat=(prospect.category if prospect else "") or "",
             contact=(prospect.contact_name if prospect else None) or "unknown", convo=convo)
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(model=os.environ.get("COPILOT_MODEL", "claude-haiku-4-5-20251001"),
                                      max_tokens=500, messages=[{"role": "user", "content": prompt}])
        text = "".join(getattr(b, "text", "") for b in resp.content)
        m = re.search(r"\{.*\}", text, re.S)
        data = json.loads(m.group(0)) if m else None
        if not isinstance(data, dict):
            return None
        out = {d: _clamp(data.get(d)) for d in SCORE_DIMENSIONS}
        out["strengths"] = [str(s)[:200] for s in (data.get("strengths") or []) if s][:3]
        out["fixes"] = [str(s)[:200] for s in (data.get("fixes") or []) if s][:3]
        return out
    except Exception:
        logger.exception("coaching: Claude scoring failed; using heuristic")
        return None


def score_call(act, lines, prospect):
    """Score one call. Idempotent per CallSid; None when the call is too short
    to coach or has no CallSid."""
    call_sid = getattr(act, "twilio_sid", None) if act is not None else None
    if not call_sid:
        return None
    existing = CallScore.query.filter_by(call_sid=call_sid).first()
    if existing:
        return existing
    lines = _norm_lines(lines)
    if len(lines) < MIN_LINES:
        return None
    res = claude_score(lines, prospect)
    source = "claude"
    if res is None:
        res = heuristic_score(lines)
        source = "heuristic"
    row = CallScore(call_sid=call_sid,
                    prospect_id=(prospect.id if prospect is not None else getattr(act, "prospect_id", None)),
                    va_name=getattr(act, "va_name", None),
                    strengths=res.get("strengths") or [], fixes=res.get("fixes") or [],
                    source=source, line_count=len(lines))
    for d in SCORE_DIMENSIONS:
        setattr(row, d, _clamp(res.get(d)))
    row.total = sum(getattr(row, d) for d in SCORE_DIMENSIONS)
    db.session.add(row)
    db.session.commit()
    return row


def score_call_async(act, lines, prospect):
    """Fire-and-forget wrapper for desk_summarize; never raises."""
    try:
        return score_call(act, lines, prospect)
    except Exception:
        logger.exception("coaching: score_call failed")
        try:
            db.session.rollback()
        except Exception:
            pass
        return None


# ---------------------------------------------------------------------------
# helpers for the endpoints
# ---------------------------------------------------------------------------

def _sees_everyone(ident):
    return is_manager(ident) or ident.get("via") == "passcode"


def _ident_or_401():
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return None, data, (jsonify({"error": "Sign in to the desk first."}), 401)
    return ident, data, None


def _digits(s):
    d = re.sub(r"\D", "", s or "")
    return d[-10:] if len(d) >= 10 else d


def _find_prospect(data):
    pid = (data.get("prospect_id") or "").strip()
    if pid:
        return db.session.get(CallProspect, pid)
    phone = _digits(data.get("phone"))
    if len(phone) == 10:
        p = CallProspect.query.filter_by(phone_digits=phone).first()
        if p:
            return p
    company = (data.get("company") or "").strip()
    if company:
        return (CallProspect.query.filter(db.func.lower(CallProspect.company) == company.lower())
                .order_by(CallProspect.last_called_at.desc().nullslast()).first())
    return None


def _lines_for(call_sid):
    return (DeskTranscriptLine.query.filter_by(call_sid=call_sid)
            .order_by(DeskTranscriptLine.seq.asc(), DeskTranscriptLine.created_at.asc()).all())


def _latest_call(p):
    from desk_line import _last_out_call
    return _last_out_call(p)


def _excerpt(call_sid, n=6):
    return [{"track": l.track, "text": l.text[:200]} for l in _lines_for(call_sid)[:n]]


def top_fix(score):
    fixes = score.fixes or []
    return fixes[0] if fixes else None


def _payload(score, with_excerpt=False):
    d = score.to_dict()
    d["top_fix"] = top_fix(score)
    p = db.session.get(CallProspect, score.prospect_id) if score.prospect_id else None
    d["company"] = p.company if p else None
    d["category"] = p.category if p else None
    if with_excerpt:
        d["excerpt"] = _excerpt(score.call_sid)
    return d


# ---------------------------------------------------------------------------
# endpoints
# ---------------------------------------------------------------------------

@coaching_bp.route("/api/va/coaching/scorecard", methods=["POST"])
@_ratelimit
def api_scorecard():
    ident, data, err = _ident_or_401()
    if err:
        return err
    score = None
    call_sid = (data.get("call_sid") or "").strip()
    if call_sid:
        score = CallScore.query.filter_by(call_sid=call_sid).first()
    p = _find_prospect(data) if not score else None
    if score is None and p is not None:
        act = _latest_call(p)
        if act and act.twilio_sid:
            score = CallScore.query.filter_by(call_sid=act.twilio_sid).first()
            if score is None:
                # the write-up may not have run yet — score on demand
                score = score_call_async(act, _lines_for(act.twilio_sid), p)
    if score is None:
        return jsonify({"score": None, "reason": "no scored call yet"}), 200
    if not _sees_everyone(ident) and score.va_name and score.va_name != ident.get("name"):
        return jsonify({"error": "That call isn't yours."}), 403
    return jsonify({"score": _payload(score)}), 200


@coaching_bp.route("/api/va/coaching/review-queue", methods=["POST"])
@_ratelimit
def api_review_queue():
    ident, data, err = _ident_or_401()
    if err:
        return err
    if not _sees_everyone(ident):
        return jsonify({"error": "That needs a manager."}), 403
    try:
        days = min(max(int(data.get("days") or 30), 1), 365)
        limit = min(max(int(data.get("limit") or 25), 1), 100)
    except (TypeError, ValueError):
        days, limit = 30, 25
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    q = CallScore.query.filter(CallScore.reviewed_at.is_(None), CallScore.created_at >= since)
    va = (data.get("va") or "").strip()
    if va:
        q = q.filter(CallScore.va_name == va)
    rows = q.order_by(CallScore.total.asc(), CallScore.created_at.asc()).limit(limit).all()
    return jsonify({"queue": [_payload(s, with_excerpt=True) for s in rows],
                    "unreviewed": q.count()}), 200


@coaching_bp.route("/api/va/coaching/review", methods=["POST"])
@_ratelimit
def api_review():
    ident, data, err = _ident_or_401()
    if err:
        return err
    if not _sees_everyone(ident):
        return jsonify({"error": "That needs a manager."}), 403
    call_sid = (data.get("call_sid") or "").strip()
    score = CallScore.query.filter_by(call_sid=call_sid).first() if call_sid else None
    if score is None:
        return jsonify({"error": "No scorecard for that call."}), 404
    tags = data.get("tags") or []
    if isinstance(tags, str):
        tags = [t for t in re.split(r"[,\s]+", tags) if t]
    tags = [str(t).strip().lower()[:30] for t in tags if str(t).strip()][:8]
    score.review_note = (data.get("note") or "").strip()[:1000] or None
    score.review_tags = tags
    score.reviewed_by = ident.get("name") or ident.get("email")
    score.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    audit("call_reviewed", "call", call_sid, {"va": score.va_name, "total": score.total, "tags": tags,
                                              "note": (score.review_note or "")[:200]})
    return jsonify({"score": _payload(score)}), 200


def trend(days=56, va=None):
    """Per-VA weekly averages per dimension (weeks start Monday, business time)."""
    from timeutils import to_local
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=min(max(int(days or 56), 7), 365))
    q = CallScore.query.filter(CallScore.created_at >= since)
    if va:
        q = q.filter(CallScore.va_name == va)
    buckets = defaultdict(lambda: defaultdict(list))
    for s in q.all():
        if not s.created_at:
            continue
        d = to_local(s.created_at).date()
        week = (d - timedelta(days=d.weekday())).isoformat()
        buckets[s.va_name or "—"][week].append(s)
    out = {}
    for name, weeks in buckets.items():
        rows = []
        for week in sorted(weeks):
            ss = weeks[week]
            n = len(ss)
            row = {"week": week, "n": n,
                   "total": round(sum(x.total for x in ss) / n, 1)}
            for dim in SCORE_DIMENSIONS:
                row[dim] = round(sum(getattr(x, dim) for x in ss) / n, 1)
            rows.append(row)
        out[name] = rows
    return out


@coaching_bp.route("/api/va/coaching/trend", methods=["POST"])
@_ratelimit
def api_trend():
    ident, data, err = _ident_or_401()
    if err:
        return err
    va = (data.get("va") or "").strip()[:80] or None
    if not _sees_everyone(ident):
        va = ident.get("name") or "—"
    return jsonify({"days": data.get("days") or 56, "va": va, "dimensions": list(SCORE_DIMENSIONS),
                    "labels": DIMENSION_LABELS, "vas": trend(data.get("days") or 56, va)}), 200
