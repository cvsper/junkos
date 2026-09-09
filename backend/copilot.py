"""Live call copilot — transcript in, objection cues + a written-up call out.

Mechanics:
  * When the VA has Copilot on, the outbound TwiML starts Twilio Real-Time
    Transcription on the browser leg (both tracks: the VA and the bridged
    prospect) and the callee hears a short recording notice before the
    bridge (Florida is two-party consent).
  * Twilio POSTs transcript sentences to /api/desk/twilio/transcript-rt;
    each becomes a DeskTranscriptLine keyed to the parent CallSid.
  * The desk polls for new lines during the call; the prospect's lines are
    matched against objection triggers so the matching reply from the Call
    Kit lights up while they're still talking.
  * After the call, summarize() turns the transcript into a note + a
    suggested outcome (Claude Haiku when ANTHROPIC_API_KEY is set; a plain
    heuristic otherwise). The VA confirms with one tap — nothing is logged
    on her behalf.
"""
from __future__ import annotations

import json
import logging
import os
import re

logger = logging.getLogger(__name__)

# (regex on what the PROSPECT said, objection "say" text in call_kit)
_TRIGGERS_DEMAND = [
    (r"\b(already|got|have)\b.{0,25}\b(a guy|someone|somebody|a company|a vendor|our own|in.?house)\b", "We already have a guy."),
    (r"\b(send|email|shoot)\b.{0,20}\b(me|us)\b.{0,20}\b(something|info|information|details|an email)\b", "Just send me something."),
    (r"\bhow much\b|\bwhat('s| is| does)\b.{0,15}\b(cost|price|charge|rate)", "How much?"),
    (r"\bnot interested\b|\bno thank", "Not interested."),
    (r"\bwho (is|are) (this|you)\b|\bhow did you get\b|\bwhere did you get my\b", "Who is this? How did you get my number?"),
    (r"\bcall (me )?back\b|\bbusy right now\b|\bbad time\b|\bnot a good time\b|\blater\b", "Call me back later."),
    (r"\bdumpster\b|\broll.?off\b", "We use a dumpster."),
    (r"\binsur(ed|ance)\b|\blicens(ed|e)\b", "Are you insured?"),
]
_TRIGGERS_SUPPLY = [
    (r"\bcatch\b|\bwhat do you (take|charge|get)\b|\byour cut\b|\bpercent", "What's the catch? What do you take?"),
    (r"\benough work\b|\bbusy enough\b|\bslammed\b|\bbooked (up|out)\b", "I've got enough work."),
    (r"\btaskrabbit\b|\bthumbtack\b|\bangi\b|\bhomeadvisor\b|\bleads?\b.{0,15}\b(pay|fee|cost)", "Is this like TaskRabbit / Thumbtack? I pay for leads?"),
    (r"\bapps?\b", "I don't do apps."),
    (r"\b(when|how) (do|would) (i|we) get paid\b|\bpay(ment|out)s?\b", "When do I get paid?"),
    (r"\binsur(ed|ance)\b|\blicens(ed|e)\b", "Do I need insurance?"),
    (r"\bsend (me|us)\b.{0,20}\b(info|information|details|something|the link)\b", "Send me the info."),
    (r"\bnot interested\b|\bno thank", "Not interested."),
]

_OUTCOMES = ("interested", "sent_link", "vendor_listed", "voicemail", "no_answer",
             "not_interested", "bad_number", "callback")


def match_objection(text, side="demand"):
    """First objection whose trigger appears in the prospect's words."""
    t = (text or "").lower()
    for rx, say in (_TRIGGERS_SUPPLY if side == "supply" else _TRIGGERS_DEMAND):
        if re.search(rx, t):
            return say
    return None


def cue_for(lines, kit, side):
    """Given transcript lines (dicts with track/text) and the kit's objection
    list, return {"say", "reply", "quote"} for the latest prospect line that
    trips a trigger, else None."""
    replies = {o["say"]: o["reply"] for o in (kit or {}).get("objections", [])}
    for ln in reversed(lines or []):
        if ln.get("track") != "them":
            continue
        say = match_objection(ln.get("text", ""), side)
        if say and say in replies:
            return {"say": say, "reply": replies[say], "quote": ln.get("text", "")[:160]}
    return None


def _heuristic(lines, prospect):
    them = [l["text"] for l in lines if l.get("track") == "them"]
    you = [l["text"] for l in lines if l.get("track") == "va"]
    blob = " ".join(them).lower()
    if not them and not you:
        return {"outcome": None, "note": "", "reason": "no transcript"}
    outcome = None
    if re.search(r"\bnot interested\b|\bno thank|\bdon'?t call\b|\bremove\b", blob):
        outcome = "not_interested"
    elif re.search(r"\bcall (me )?back\b|\btomorrow\b|\bnext week\b|\blater\b", blob):
        outcome = "callback"
    elif re.search(r"\bsend\b.{0,20}\b(info|information|link|something|email)\b|\bsure\b|\bsounds good\b|\byes\b|\binterested\b", blob):
        outcome = "interested"
    elif re.search(r"\bwe (already )?(have|use|got)\b.{0,20}\b(guy|company|vendor|someone)", blob):
        outcome = "vendor_listed"
    note = " / ".join(t.strip() for t in them[-3:])[:280]
    return {"outcome": outcome, "note": ("They said: " + note) if note else "", "reason": "heuristic"}


def summarize(lines, prospect, side="demand"):
    """→ {"outcome": one of _OUTCOMES or None, "note": str, "callback": str|None, "reason": str}"""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not lines:
        return {"outcome": None, "note": "", "callback": None, "reason": "no transcript"}
    if not api_key:
        h = _heuristic(lines, prospect)
        h["callback"] = None
        return h
    convo = "\n".join("{}: {}".format("PROSPECT" if l.get("track") == "them" else "TRACY", l.get("text", ""))
                      for l in lines)[-6000:]
    goal = ("recruiting this hauling company to take paid jobs from Umuve"
            if side == "supply" else "selling Umuve's junk-removal service to this business")
    prompt = (
        "You are writing up a sales call for a CRM card. Goal of the call: {goal}.\n"
        "Company: {co} ({cat}, {city}). Contact: {contact}.\n\n"
        "Transcript:\n{convo}\n\n"
        "Return ONLY JSON with keys: outcome (one of interested, sent_link, vendor_listed, voicemail, "
        "no_answer, not_interested, bad_number, callback, or null if unclear), note (<=220 chars, "
        "what they said and what to do next, no fluff), callback (if they named a time, the day/time "
        "as they said it, else null)."
    ).format(goal=goal, co=prospect.company, cat=prospect.category or "", city=prospect.city or "",
             contact=prospect.contact_name or "unknown", convo=convo)
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(model=os.environ.get("COPILOT_MODEL", "claude-haiku-4-5-20251001"),
                                      max_tokens=300, messages=[{"role": "user", "content": prompt}])
        text = "".join(getattr(b, "text", "") for b in resp.content)
        m = re.search(r"\{.*\}", text, re.S)
        data = json.loads(m.group(0)) if m else {}
        outcome = data.get("outcome")
        return {"outcome": outcome if outcome in _OUTCOMES else None,
                "note": str(data.get("note") or "")[:300],
                "callback": (str(data.get("callback"))[:80] if data.get("callback") else None),
                "reason": "claude"}
    except Exception:
        logger.exception("copilot summarize failed; using heuristic")
        h = _heuristic(lines, prospect)
        h["callback"] = None
        return h
