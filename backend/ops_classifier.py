"""
Ops Supervisor — Claude Haiku event classifier (spec 11 §9, v1).

Replaces the rule-only detector dispatch for the classification step. Given
an ``OpsEvent`` (plus a light booking snapshot), we ask Claude Haiku to tag
the event with one of the canonical situation tags and a confidence score.

Design notes
------------
* Strict JSON output. If the model's response is not parseable we fall back
  to the deterministic regex/rules path from ``ops_supervisor_detectors``.
* ``classifier_tag`` + ``classifier_confidence`` are persisted back onto the
  ``OpsEvent`` row so dashboards can see what the model thought without a
  re-call.
* If ``ANTHROPIC_API_KEY`` is unset we short-circuit to the rule-based
  fallback — tests run this way by default.
* No network calls happen at import time. The Anthropic client is lazy.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

# Canonical tag vocabulary — matches spec §9 list. Keep sorted; prompt lists
# them in this order.
VALID_TAGS = (
    "truck_late",
    "payment_failed_post_job",
    "gps_deviation",
    "driver_no_show",
    "customer_cancellation_request",
    "damage_report",
    "complaint",
    "other",
)

# Default severity mapping per tag. Claude may override via suggested_severity
# but we clamp to these unless the model is very confident.
DEFAULT_SEVERITY = {
    "truck_late": "medium",
    "payment_failed_post_job": "high",
    "gps_deviation": "medium",
    "driver_no_show": "high",
    "customer_cancellation_request": "low",
    "damage_report": "high",
    "complaint": "medium",
    "other": "low",
}

VALID_SEVERITIES = ("info", "low", "medium", "high", "critical")


SYSTEM_PROMPT = (
    "You are the classification head of Umuve's autonomous ops supervisor. "
    "Given a raw ops event and a booking snapshot, return a single JSON "
    "object with keys: tag (one of the provided tags), confidence (float "
    "0.0-1.0), suggested_severity (one of info/low/medium/high/critical). "
    "No prose, no markdown fences -- JSON only. If you are unsure, prefer "
    "tag='other' with low confidence rather than guessing."
)


@dataclass
class ClassifierResult:
    tag: str
    confidence: float
    suggested_severity: str
    source: str  # 'claude' | 'fallback_rules' | 'fallback_no_key' | 'fallback_error'

    def to_dict(self) -> dict:
        return {
            "tag": self.tag,
            "confidence": self.confidence,
            "suggested_severity": self.suggested_severity,
            "source": self.source,
        }


# ---------------------------------------------------------------------------
# Fallback: derive a tag from the existing rule-based detectors
# ---------------------------------------------------------------------------
def _rules_fallback(ops_event, booking=None) -> ClassifierResult:
    """Map an OpsEvent to a ClassifierResult via the rule detectors.

    Uses ``run_detector_for_event`` when a booking is available; otherwise we
    infer from the event's ``type`` string alone (best-effort).
    """
    from ops_supervisor_detectors import run_detector_for_event

    event_type = (getattr(ops_event, "type", "") or "").lower()
    payload = getattr(ops_event, "payload_json", None) or {}

    try:
        det = run_detector_for_event(event_type, booking, payload)
    except Exception:  # pragma: no cover - defensive
        det = None

    if det is not None:
        return ClassifierResult(
            tag=det.tag,
            confidence=det.confidence,
            suggested_severity=det.severity,
            source="fallback_rules",
        )

    # No detector fired — classify by event-type keyword.
    if "cancel" in event_type:
        tag = "customer_cancellation_request"
    elif "no_show" in event_type or "no-show" in event_type:
        tag = "driver_no_show"
    elif "damage" in event_type:
        tag = "damage_report"
    elif "complaint" in event_type or "review" in event_type:
        tag = "complaint"
    else:
        tag = "other"

    return ClassifierResult(
        tag=tag,
        confidence=0.40,  # low — pure guess
        suggested_severity=DEFAULT_SEVERITY.get(tag, "low"),
        source="fallback_rules",
    )


# ---------------------------------------------------------------------------
# Parser for Claude's JSON reply
# ---------------------------------------------------------------------------
def _parse_claude_reply(raw: str) -> Optional[dict]:
    if not raw:
        return None
    text = raw.strip()
    # Strip possible markdown fences.
    if text.startswith("```"):
        text = text.strip("`")
        # ``` may be followed by 'json' marker
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find the first {...} blob.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                return None
        return None


def _normalize(parsed: dict) -> Optional[ClassifierResult]:
    if not isinstance(parsed, dict):
        return None

    tag = str(parsed.get("tag") or "").strip().lower()
    if tag not in VALID_TAGS:
        return None

    try:
        conf = float(parsed.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))

    sev = str(parsed.get("suggested_severity")
              or DEFAULT_SEVERITY.get(tag, "low")).strip().lower()
    if sev not in VALID_SEVERITIES:
        sev = DEFAULT_SEVERITY.get(tag, "low")

    return ClassifierResult(
        tag=tag, confidence=conf, suggested_severity=sev, source="claude"
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def classify_event(
    ops_event,
    booking=None,
    *,
    client=None,
    persist: bool = True,
) -> ClassifierResult:
    """Classify ``ops_event`` and (optionally) persist the result on the row.

    Parameters
    ----------
    ops_event : OpsEvent ORM instance
        Must expose ``id``, ``type``, ``payload_json`` attributes.
    booking : Job | None
        Attached booking for richer context.
    client : optional fake Anthropic client (tests inject one).
    persist : if True, writes ``classifier_tag`` and ``classifier_confidence``
        back on the event and flushes the session.

    Returns
    -------
    ClassifierResult
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key and client is None:
        logger.debug("classify_event: no ANTHROPIC_API_KEY -> rules fallback")
        result = _rules_fallback(ops_event, booking)
        result = ClassifierResult(
            tag=result.tag,
            confidence=result.confidence,
            suggested_severity=result.suggested_severity,
            source="fallback_no_key",
        )
        _persist(ops_event, result, persist)
        return result

    # Build the user message with the event payload + booking snapshot.
    booking_snapshot = _booking_snapshot(booking)
    user_payload = {
        "event": {
            "id": getattr(ops_event, "id", None),
            "type": getattr(ops_event, "type", None),
            "source": getattr(ops_event, "source", None),
            "payload": getattr(ops_event, "payload_json", None) or {},
        },
        "booking": booking_snapshot,
        "allowed_tags": list(VALID_TAGS),
    }

    try:
        if client is None:
            import anthropic  # noqa: WPS433 - lazy import
            client = anthropic.Anthropic(api_key=api_key)

        resp = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=200,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user",
                       "content": json.dumps(user_payload, default=str)}],
        )

        text_parts = []
        for block in (getattr(resp, "content", None) or []):
            txt = getattr(block, "text", None)
            if txt:
                text_parts.append(txt)
        raw = "".join(text_parts)

        parsed = _parse_claude_reply(raw)
        result = _normalize(parsed) if parsed else None
        if result is None:
            logger.warning(
                "classify_event: unparseable Claude reply, falling back. raw=%r",
                raw[:200],
            )
            result = _rules_fallback(ops_event, booking)
            result = ClassifierResult(
                tag=result.tag, confidence=result.confidence,
                suggested_severity=result.suggested_severity,
                source="fallback_error",
            )
    except Exception:
        logger.exception("classify_event: Claude call failed, falling back")
        result = _rules_fallback(ops_event, booking)
        result = ClassifierResult(
            tag=result.tag, confidence=result.confidence,
            suggested_severity=result.suggested_severity,
            source="fallback_error",
        )

    _persist(ops_event, result, persist)
    return result


def _persist(ops_event, result: ClassifierResult, persist: bool) -> None:
    if not persist or ops_event is None:
        return
    try:
        ops_event.classifier_tag = result.tag
        ops_event.classifier_confidence = result.confidence
        # Flush if the event is attached to a session.
        from models import db
        if ops_event in db.session:
            db.session.flush()
    except Exception:  # pragma: no cover - defensive persistence layer
        logger.exception("classify_event: failed to persist tag on OpsEvent")


def _booking_snapshot(booking) -> dict:
    if booking is None:
        return {}
    customer = getattr(booking, "customer", None)
    return {
        "id": getattr(booking, "id", None),
        "status": getattr(booking, "status", None),
        "scheduled_at": (
            booking.scheduled_at.isoformat()
            if getattr(booking, "scheduled_at", None) else None
        ),
        "address": getattr(booking, "address", None),
        "total_price": getattr(booking, "total_price", None),
        "customer_name": getattr(customer, "name", None) if customer else None,
    }


__all__ = [
    "classify_event",
    "ClassifierResult",
    "VALID_TAGS",
    "VALID_SEVERITIES",
    "DEFAULT_SEVERITY",
    "ANTHROPIC_MODEL",
]
