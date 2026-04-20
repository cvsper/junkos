"""
Partner Acquisition Agent — automated qualifier (spec 07 §9 v1).

`qualify_response(attempt)` takes an inbound OutreachAttempt (direction='in')
and returns a dict:
    {
        "sentiment": "positive" | "neutral" | "negative" | "red_flag",
        "qualified": bool,
        "reasons": [str, ...]
    }

When `qualified=True`, the caller is expected to:
  1. Transition the lead NEW/OUTREACHED/RESPONDED -> QUALIFIED
  2. Insert a Qualification row with consent_sms=True and the attempt id stored
     in payload.

Backed by Claude Haiku with a strict-JSON schema prompt. When ANTHROPIC_API_KEY
is missing, falls back to a keyword heuristic:
  * Keywords: yes, interested, sure, ok, sounds good, tell me more -> qualified+positive
  * Keywords: stop, no, not interested, unsubscribe, remove -> qualified=False, negative/red_flag
  * Otherwise neutral, qualified=False.

Helper `auto_qualify_and_transition(attempt, session)` does the full side-effect
dance — writes Qualification, advances lead state, commits.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Dict, List

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-haiku-4-5-20251001"

POSITIVE_KEYWORDS = (
    "yes", "interested", "sure", "ok", "okay", "sounds good", "tell me more",
    "let me know", "i'm in", "im in", "sign me up",
)
NEGATIVE_KEYWORDS = (
    "no thanks", "not interested", "unsubscribe", "remove", "not now",
)
RED_FLAG_KEYWORDS = (
    "stop", "harass", "lawyer", "attorney", "sue", "fuck", "leave me alone",
)


def _anthropic_client():
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    try:
        import anthropic  # type: ignore
        return anthropic.Anthropic(api_key=key)
    except Exception:
        logger.warning("anthropic SDK unavailable; using keyword fallback")
        return None


def _keyword_qualify(body: str) -> Dict:
    text = (body or "").strip().lower()
    reasons: List[str] = []

    for kw in RED_FLAG_KEYWORDS:
        if kw in text:
            return {
                "sentiment": "red_flag",
                "qualified": False,
                "reasons": ["red_flag keyword: {}".format(kw)],
            }

    for kw in NEGATIVE_KEYWORDS:
        if kw in text:
            return {
                "sentiment": "negative",
                "qualified": False,
                "reasons": ["negative keyword: {}".format(kw)],
            }

    for kw in POSITIVE_KEYWORDS:
        # Match whole word-ish — avoid matching "yes" inside "eyesore".
        if re.search(r"\b{}\b".format(re.escape(kw)), text):
            reasons.append("positive keyword: {}".format(kw))
            return {
                "sentiment": "positive",
                "qualified": True,
                "reasons": reasons,
            }

    return {"sentiment": "neutral", "qualified": False, "reasons": ["no trigger keywords"]}


def _claude_qualify(body: str) -> Dict:
    client = _anthropic_client()
    if client is None:
        return _keyword_qualify(body)

    prompt = (
        "You classify SMS replies from prospective junk-hauling drivers. "
        "Given the reply text, decide sentiment and whether they are "
        "QUALIFIED to continue onboarding.\n\n"
        "Return STRICT JSON with this exact schema:\n"
        '{\"sentiment\": \"positive|neutral|negative|red_flag\", '
        '\"qualified\": true|false, \"reasons\": [\"...\"]}\n\n'
        "Rules:\n"
        " - 'positive' + qualified=true when they express interest / agreement.\n"
        " - 'negative' + qualified=false when they decline politely.\n"
        " - 'red_flag' + qualified=false on STOP, profanity, legal threats.\n"
        " - 'neutral' + qualified=false for ambiguous replies.\n\n"
        "Reply text: "
    ) + json.dumps(body or "")

    try:
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = []
        for block in getattr(resp, "content", []) or []:
            text = getattr(block, "text", None) or (block.get("text") if isinstance(block, dict) else None)
            if text:
                parts.append(text)
        raw = "".join(parts).strip()
        # Strip any code fences.
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
        parsed = json.loads(raw)
        sentiment = parsed.get("sentiment", "neutral")
        qualified = bool(parsed.get("qualified", False))
        reasons = parsed.get("reasons") or []
        if sentiment not in ("positive", "neutral", "negative", "red_flag"):
            sentiment = "neutral"
        return {"sentiment": sentiment, "qualified": qualified, "reasons": list(reasons)}
    except Exception:
        logger.exception("claude qualifier failed; using keyword fallback")
        return _keyword_qualify(body)


def qualify_response(attempt) -> Dict:
    """Classify an inbound OutreachAttempt. Never raises."""
    body = getattr(attempt, "body", None) or ""
    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        return _claude_qualify(body)
    return _keyword_qualify(body)


def auto_qualify_and_transition(attempt, session) -> Dict:
    """Side-effect helper. When qualified=True, advance lead state to QUALIFIED
    and insert a Qualification row with consent_sms=True (they replied YES in
    an SMS they opted into) and consent_checkr=False (still needs explicit
    consent). Commits the session.

    Returns the classification dict augmented with {transitioned: bool}.
    """
    from partner_models import DriverLead, Qualification, DriverOnboardingAudit

    result = qualify_response(attempt)
    lead_id = getattr(attempt, "lead_id", None)
    if not lead_id:
        result["transitioned"] = False
        return result

    lead = session.get(DriverLead, lead_id)
    if not lead:
        result["transitioned"] = False
        return result

    transitioned = False
    if result["qualified"] and lead.state in ("NEW", "OUTREACHED", "RESPONDED"):
        before = lead.state
        lead.state = "QUALIFIED"
        qual = Qualification(
            lead_id=lead.id,
            consent_sms=True,
            consent_checkr=False,
            has_truck=None,  # to be captured via structured form
            has_insurance=None,
            has_license=None,
        )
        session.add(qual)
        session.add(DriverOnboardingAudit(
            lead_id=lead.id,
            actor="claude_qualifier_v1",
            action="lead.auto_qualify",
            before_state=before,
            after_state="QUALIFIED",
            payload_json={
                "attempt_id": getattr(attempt, "id", None),
                "sentiment": result["sentiment"],
                "reasons": result["reasons"],
            },
        ))
        transitioned = True
        session.commit()
    elif result["sentiment"] == "red_flag" and lead.state != "REJECTED":
        before = lead.state
        lead.state = "REJECTED"
        lead.opted_out = True
        session.add(DriverOnboardingAudit(
            lead_id=lead.id,
            actor="claude_qualifier_v1",
            action="lead.red_flag_reject",
            before_state=before,
            after_state="REJECTED",
            payload_json={
                "attempt_id": getattr(attempt, "id", None),
                "reasons": result["reasons"],
            },
        ))
        transitioned = True
        session.commit()

    result["transitioned"] = transitioned
    return result
