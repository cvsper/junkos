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
    (r"\b(already|got|have|use|using|work with)\b.{0,30}\b(a guy|someone|somebody|a company|a vendor|our own|in.?house|waste management|the city|public works|a contract)\b|\bwe'?re (good|set|fine|covered)\b", "We already have someone."),
    (r"\bmaintenance\b.{0,25}\b(does|do|handles?|takes? care|got it)\b|\bour (guys|team|crew) (do|does|handle)\b", "Maintenance handles it."),
    (r"\bcorporate\b|\bapproved vendor\b|\bvendor (list|portal|approval)\b|\bcompliance depot\b|\bvendor ?cafe\b|\bnet ?vendor\b|\bregional\b.{0,20}\b(approv|decid)", "Corporate approves vendors."),
    (r"\b(send|email|shoot)\b.{0,20}\b(me|us)\b.{0,20}\b(something|info|information|details|an email|your info|a flyer)\b|\binfo@|\bemail it\b", "Just send me your info."),
    (r"\bhow much\b|\bwhat('s| is| does| are)\b.{0,15}\b(cost|price|charge|rate)|\bpricing\b|\bper unit\b", "How much?"),
    (r"\bnot interested\b|\bno thank|\bnot (right )?now\b|\bnot a priority\b|\bwe don'?t need\b", "Not interested / not now."),
    (r"\bwho (is|are) (this|you)\b|\bhow did you get\b|\bwhere did you get my\b|\bwhere are you calling from\b|\bwhat company\b", "Who is this?"),
    (r"\bcall (me )?back\b|\bbusy right now\b|\bbad time\b|\bnot a good time\b|\bin a meeting\b|\blater\b", "Call me back later."),
    (r"\bdumpster\b|\broll.?off\b", "We use a dumpster."),
    (r"\binsur(ed|ance)\b|\blicens(ed|e)\b|\bcoi\b|\bw-?9\b|\bcertificate\b", "Are you insured? Send the COI."),
    (r"\bleasing\b.{0,20}\b(office|agent)\b|\bi'?m (just|only) (the|a)\b|\bi don'?t handle\b|\bnot my (department|call)\b", "I'm not the right person."),
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


_SPELLED = re.compile(r"\bu[\s\-\.]*m[\s\-\.]*u[\s\-\.]*v[\s\-\.]*e\b|\bu\.m\.u\.v\.e\b|\byou[\s\-]*move\b.{0,12}\bu\b", re.I)
_DISCLOSED = re.compile(r"\brecord(ed|ing)\b|\bon a recorded line\b|\bthis call (is|may be) recorded\b", re.I)
_MISHEARD = re.compile(r"\byou ?move\b|\bu ?move\b|\bemove\b|\bamove\b|\bimmove\b|\bwho(se)? (is|was) (this|that)\b", re.I)


def caller_cues(lines, seconds_in=None):
    """Cues about the VA's own side of the call, from what she has said so far.
    Brand misheard on 9 of 21 scored calls ("you move", "EMOV"); recording
    notice given on 0 of 21. → list of {"cue", "say"}; empty when fine."""
    you = " ".join(l.get("text", "") for l in (lines or []) if l.get("track") == "va")
    them = " ".join(l.get("text", "") for l in (lines or []) if l.get("track") == "them")
    out = []
    started = bool(you.strip())
    late = (seconds_in is None) or (seconds_in >= 20)
    if started and late and not _SPELLED.search(you):
        out.append({"cue": "spell it", "say": "…with Umuve — that's U-M-U-V-E, our trucks are in West Palm."})
    if started and late and not _DISCLOSED.search(you):
        out.append({"cue": "disclosure", "say": "Quick heads-up, this call's recorded for quality."})
    if _MISHEARD.search(them) and not any(c["cue"] == "spell it" for c in out):
        out.append({"cue": "spell it", "say": "They didn't catch the name — Umuve, U-M-U-V-E."})
    return out


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
