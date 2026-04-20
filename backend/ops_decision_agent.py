"""
Ops Supervisor — Claude Opus decision agent (spec 11 §§7, 9, v1).

The decision agent receives a live ``Situation`` and returns a single
``AgentDecision`` whose proposed tool call has been passed through the hard
guardrail layer in ``ops_supervisor_guardrails``.

Model order:
  1. ``claude-opus-4-5-20251001`` — primary; best reasoning.
  2. ``claude-haiku-4-5-20251001`` — fallback if Opus unavailable / 429s.
  3. Hardcoded action templates from ``routes/ops_supervisor`` — ultimate
     fallback when ``ANTHROPIC_API_KEY`` is missing.

Output contract (Claude side)
-----------------------------
Strict JSON:
    {"tool": str, "args": {...}, "rationale": str, "confidence": float}

Tools whitelist (MUST match prompt):
    issue_credit(amount_cents)
    issue_refund(amount_cents)
    send_customer_sms(body)
    send_driver_sms(body)
    reassign_driver(new_driver_id)
    escalate_human(priority)
    no_action

Every decision is persisted with ``status='pending'`` BEFORE any action is
executed. After the guardrail layer runs we flip status to ``executed`` or
``blocked_by_guardrail`` (or ``failed`` for internal errors).

This module does NOT execute the tool side-effects itself; the LangGraph
workflow (``ops_langgraph``) is responsible for the execute step. It does
route every decision through the guardrail validators so the workflow can
short-circuit on a block.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

from models import db
from ops_supervisor_models import AgentDecision
from ops_supervisor_guardrails import (
    GuardrailResult,
    CREDIT_MAX_CENTS,
    REFUND_MAX_CENTS,
    MIN_AUTONOMOUS_CONFIDENCE,
    validate_credit,
    validate_refund,
    validate_sms_rate,
    validate_reassign,
    check_confidence,
)

logger = logging.getLogger(__name__)


OPUS_MODEL = "claude-opus-4-5-20251001"
HAIKU_MODEL = "claude-haiku-4-5-20251001"

ALLOWED_TOOLS = (
    "issue_credit",
    "issue_refund",
    "send_customer_sms",
    "send_driver_sms",
    "reassign_driver",
    "escalate_human",
    "no_action",
)


SYSTEM_PROMPT = (
    "You are Umuve's autonomous ops supervisor. You receive a Situation and "
    "decide a single next action. Return strict JSON with keys tool, args, "
    "rationale, confidence. No prose, no markdown fences.\n\n"
    "Allowed tools (args shape shown in brackets):\n"
    "  - issue_credit [amount_cents]: autonomous cap $100 ("
    + str(CREDIT_MAX_CENTS) + " cents).\n"
    "  - issue_refund [amount_cents]: autonomous cap $50 ("
    + str(REFUND_MAX_CENTS) + " cents).\n"
    "  - send_customer_sms [body]: max 1 per situation.\n"
    "  - send_driver_sms [body].\n"
    "  - reassign_driver [new_driver_id]: forbidden if driver on_location.\n"
    "  - escalate_human [priority: p0|p1|p2]: use when unsure or cost > cap.\n"
    "  - no_action: use when event is false positive or already handled.\n\n"
    "Hard rules (violations = system failure):\n"
    "  - Never invent booking/payment facts not in the input.\n"
    "  - Never propose credit > $100 or refund > $50 autonomously.\n"
    "  - If confidence < 0.60 pick escalate_human with priority p1.\n"
)


@dataclass
class DecisionOutput:
    tool: str
    args: dict = field(default_factory=dict)
    rationale: str = ""
    confidence: float = 0.0
    model: str = "fallback-templates"

    def to_json(self) -> dict:
        return {
            "tool": self.tool,
            "args": self.args,
            "rationale": self.rationale,
            "confidence": self.confidence,
            "model": self.model,
        }


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------
def _situation_prompt_payload(situation, booking=None, customer_history=None) -> dict:
    context = situation.context_snapshot_json or {}
    booking_snapshot = context.get("booking") or {}
    if booking is not None and not booking_snapshot:
        booking_snapshot = {
            "id": getattr(booking, "id", None),
            "status": getattr(booking, "status", None),
            "address": getattr(booking, "address", None),
            "total_price": getattr(booking, "total_price", None),
        }

    return {
        "situation": {
            "id": situation.id,
            "tag": situation.tag,
            "severity": situation.severity,
            "opened_at": (
                situation.opened_at.isoformat()
                if situation.opened_at else None
            ),
            "context_snapshot": context,
        },
        "booking": booking_snapshot,
        "customer_history": customer_history or {},
        "available_tools": list(ALLOWED_TOOLS),
        "guardrails": {
            "credit_max_cents": CREDIT_MAX_CENTS,
            "refund_max_cents": REFUND_MAX_CENTS,
            "min_autonomous_confidence": MIN_AUTONOMOUS_CONFIDENCE,
        },
    }


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
def _parse_reply(raw: str) -> Optional[dict]:
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                return None
    return None


def _normalize_decision(parsed: dict, model: str) -> Optional[DecisionOutput]:
    if not isinstance(parsed, dict):
        return None
    tool = str(parsed.get("tool") or "").strip()
    if tool not in ALLOWED_TOOLS:
        return None
    args = parsed.get("args") or {}
    if not isinstance(args, dict):
        args = {}
    try:
        conf = float(parsed.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))
    rationale = str(parsed.get("rationale") or "")[:2000]
    return DecisionOutput(
        tool=tool, args=args, rationale=rationale,
        confidence=conf, model=model,
    )


# ---------------------------------------------------------------------------
# Template fallback — mirrors the MVP ACTION_TEMPLATES shape
# ---------------------------------------------------------------------------
def _template_fallback(situation) -> DecisionOutput:
    tag = (situation.tag or "").lower()
    if tag == "truck_late":
        return DecisionOutput(
            tool="issue_credit",
            args={"amount_cents": 1500},
            rationale="Fallback template: flat $15 credit for >15min late.",
            confidence=0.90,
            model="fallback-templates",
        )
    if tag == "payment_failed_post_job":
        return DecisionOutput(
            tool="send_customer_sms",
            args={"body": "Umuve: your payment didn't go through. "
                          "Retry at goumuve.com/pay."},
            rationale="Fallback template: retry-link SMS, no credit.",
            confidence=0.90,
            model="fallback-templates",
        )
    if tag == "gps_deviation":
        return DecisionOutput(
            tool="send_driver_sms",
            args={"body": "GPS shows 2+mi off route 8min. Confirm status."},
            rationale="Fallback template: driver check-in SMS.",
            confidence=0.90,
            model="fallback-templates",
        )
    # Unknown tag → escalate so nothing falls on the floor.
    return DecisionOutput(
        tool="escalate_human",
        args={"priority": "p2"},
        rationale="Fallback template: no playbook for tag={}".format(tag),
        confidence=0.85,
        model="fallback-templates",
    )


# ---------------------------------------------------------------------------
# Guardrail layer — applied to the parsed DecisionOutput
# ---------------------------------------------------------------------------
@dataclass
class GuardedDecision:
    """Container for (decision_row, parsed_output, guardrail_result)."""
    decision: AgentDecision
    output: DecisionOutput
    guardrail: GuardrailResult
    latency_ms: int = 0


def _guardrail_for(output: DecisionOutput, situation, booking) -> GuardrailResult:
    # Confidence floor is always checked first.
    conf_res = check_confidence(output.confidence)
    if not conf_res.ok:
        return conf_res

    tool = output.tool
    args = output.args or {}

    if tool == "issue_credit":
        return validate_credit(args.get("amount_cents"))
    if tool == "issue_refund":
        return validate_refund(args.get("amount_cents"))
    if tool == "send_customer_sms":
        return validate_sms_rate(db.session, situation.id)
    if tool == "reassign_driver":
        return validate_reassign(booking)

    # send_driver_sms / escalate_human / no_action have no guardrail.
    return GuardrailResult(ok=True)


# ---------------------------------------------------------------------------
# Claude invocation (opus → haiku fallback)
# ---------------------------------------------------------------------------
def _call_claude(payload: dict, *, client=None) -> Optional[DecisionOutput]:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key and client is None:
        return None

    try:
        if client is None:
            import anthropic  # noqa: WPS433 - lazy import
            client = anthropic.Anthropic(api_key=api_key)
    except Exception:
        logger.exception("ops_decision_agent: failed to build Anthropic client")
        return None

    user_msg = json.dumps(payload, default=str)

    # Opus first, then Haiku.
    for model_id in (OPUS_MODEL, HAIKU_MODEL):
        try:
            resp = client.messages.create(
                model=model_id,
                max_tokens=600,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
            text_parts = []
            for block in (getattr(resp, "content", None) or []):
                txt = getattr(block, "text", None)
                if txt:
                    text_parts.append(txt)
            raw = "".join(text_parts)
            parsed = _parse_reply(raw)
            normalized = _normalize_decision(parsed, model_id) if parsed else None
            if normalized is not None:
                return normalized
            logger.warning(
                "ops_decision_agent: unparseable reply from %s raw=%r",
                model_id, raw[:200],
            )
        except Exception as exc:
            logger.warning(
                "ops_decision_agent: %s call failed (%s); trying fallback model",
                model_id, exc,
            )
            continue

    return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def decide(situation, booking=None, customer_history=None,
           *, client=None, persist: bool = True) -> GuardedDecision:
    """Run the decision chain for ``situation`` and return a GuardedDecision.

    Caller is responsible for executing the tool when
    ``guardrail.ok is True`` — typically the LangGraph ``execute_action``
    node.

    Behaviour:
      1. Build prompt payload from situation + booking + customer_history.
      2. Ask Claude (Opus → Haiku fallback). Missing API key → template.
      3. Persist AgentDecision row with status='pending'.
      4. Run guardrail validators; if blocked, flip status to
         'blocked_by_guardrail' and return.
      5. Caller flips to 'executed' / 'failed' when the action runs.
    """
    start = time.time()

    payload = _situation_prompt_payload(situation, booking, customer_history)

    output = _call_claude(payload, client=client)
    if output is None:
        output = _template_fallback(situation)

    latency_ms = int((time.time() - start) * 1000)

    decision = AgentDecision(
        situation_id=situation.id,
        model=output.model,
        decision_json={
            "tool": output.tool,
            "args": output.args,
            "situation_tag": situation.tag,
        },
        rationale=output.rationale,
        confidence=output.confidence,
        status="pending",
        latency_ms=latency_ms,
    )
    if persist:
        db.session.add(decision)
        db.session.flush()

    guardrail = _guardrail_for(output, situation, booking)

    if not guardrail.ok:
        decision.status = "blocked_by_guardrail"
        # Annotate decision_json with the guardrail reason so dashboards see it.
        existing = decision.decision_json or {}
        existing["guardrail"] = {
            "code": guardrail.code,
            "reason": guardrail.reason,
        }
        decision.decision_json = existing
        if persist:
            db.session.flush()

    return GuardedDecision(
        decision=decision,
        output=output,
        guardrail=guardrail,
        latency_ms=latency_ms,
    )


__all__ = [
    "decide",
    "DecisionOutput",
    "GuardedDecision",
    "ALLOWED_TOOLS",
    "OPUS_MODEL",
    "HAIKU_MODEL",
]
