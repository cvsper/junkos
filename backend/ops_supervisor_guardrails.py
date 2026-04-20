"""
Ops Supervisor — guardrail layer (spec 11 §8).

EVERY autonomous action passes through this file BEFORE being executed.
Prompt-side instructions are advisory; this module is the enforcement point.

Spec-mandated hard limits (§8):
  * credit max: $100  (10_000 cents)
  * refund max: $50   (5_000  cents)
  * 1 customer SMS per situation
  * confidence < 0.60 → auto-escalate
  * reassign forbidden if driver.status == 'on_location'

Every violation is logged to ``AgentAction`` with status
``blocked_by_guardrail`` by the caller (routes/ops_supervisor.py). Validators
here return a ``GuardrailResult`` — ``ok=True/False`` and a human-readable
``reason``. They do not touch the database.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Hard caps (cents). Exposed as constants so ops can dump them in the
# dashboard. Changing these here changes enforcement; prompts do not control
# the limits.
# ---------------------------------------------------------------------------
CREDIT_MAX_CENTS = 10_000   # $100
REFUND_MAX_CENTS = 5_000    # $50
MIN_AUTONOMOUS_CONFIDENCE = 0.60


@dataclass
class GuardrailResult:
    ok: bool
    reason: Optional[str] = None
    code: Optional[str] = None  # machine-readable category

    def __bool__(self) -> bool:  # allow `if guardrail_result:` shorthand
        return self.ok


def _bad(code: str, reason: str) -> GuardrailResult:
    logger.info("Guardrail blocked: %s — %s", code, reason)
    return GuardrailResult(ok=False, reason=reason, code=code)


def _ok() -> GuardrailResult:
    return GuardrailResult(ok=True)


# ---------------------------------------------------------------------------
# Credit / refund caps
# ---------------------------------------------------------------------------
def validate_credit(amount_cents: int) -> GuardrailResult:
    """Reject issue_credit calls above the autonomous cap ($100)."""
    if amount_cents is None:
        return _bad("credit_missing_amount", "credit amount required")
    try:
        amount_cents = int(amount_cents)
    except (TypeError, ValueError):
        return _bad("credit_bad_amount", "credit amount must be an integer")
    if amount_cents <= 0:
        return _bad("credit_non_positive", "credit must be positive")
    if amount_cents > CREDIT_MAX_CENTS:
        return _bad(
            "credit_cap_exceeded",
            "credit ${:.2f} exceeds autonomous cap ${:.2f}".format(
                amount_cents / 100.0, CREDIT_MAX_CENTS / 100.0
            ),
        )
    return _ok()


def validate_refund(amount_cents: int) -> GuardrailResult:
    """Reject issue_refund calls above the autonomous cap ($50)."""
    if amount_cents is None:
        return _bad("refund_missing_amount", "refund amount required")
    try:
        amount_cents = int(amount_cents)
    except (TypeError, ValueError):
        return _bad("refund_bad_amount", "refund amount must be an integer")
    if amount_cents <= 0:
        return _bad("refund_non_positive", "refund must be positive")
    if amount_cents > REFUND_MAX_CENTS:
        return _bad(
            "refund_cap_exceeded",
            "refund ${:.2f} exceeds autonomous cap ${:.2f}".format(
                amount_cents / 100.0, REFUND_MAX_CENTS / 100.0
            ),
        )
    return _ok()


# ---------------------------------------------------------------------------
# SMS rate limit — 1 customer SMS per situation
# ---------------------------------------------------------------------------
def validate_sms_rate(db_session, situation_id: str) -> GuardrailResult:
    """Block a second customer-SMS for the same situation.

    Driver-SMS is not rate-limited here — we only gate the customer comms
    channel because it's what creates the "agent spam" failure mode.
    """
    # Local import to avoid a circular dep when this module is imported from
    # ops_supervisor_models-adjacent code.
    from ops_supervisor_models import AgentAction, AgentDecision

    if not situation_id:
        return _bad("sms_rate_missing_situation", "situation_id required for rate gate")

    existing = (
        db_session.query(AgentAction)
        .join(AgentDecision, AgentAction.decision_id == AgentDecision.id)
        .filter(AgentDecision.situation_id == situation_id)
        .filter(AgentAction.tool == "send_customer_sms")
        .filter(AgentAction.status == "executed")
        .first()
    )
    if existing is not None:
        return _bad(
            "sms_rate_limit",
            "customer SMS already sent for situation {}".format(situation_id),
        )
    return _ok()


# ---------------------------------------------------------------------------
# Reassign — cannot pull a driver already on location
# ---------------------------------------------------------------------------
def validate_reassign(booking) -> GuardrailResult:
    """Block ``reassign_driver`` if the driver is on-site."""
    if booking is None:
        return _bad("reassign_no_booking", "booking required")

    driver = getattr(booking, "driver", None)
    if driver is not None:
        driver_status = (getattr(driver, "status", None) or "").lower()
        if driver_status == "on_location":
            return _bad(
                "reassign_driver_on_location",
                "driver already on_location — cannot reassign",
            )

    # Fall back to booking.status — some fleets don't model driver status
    # directly but mark the job as on_location.
    job_status = (getattr(booking, "status", None) or "").lower()
    if job_status in {"on_location", "arrived"}:
        return _bad(
            "reassign_job_on_location",
            "job status is {} — cannot reassign driver".format(job_status),
        )

    return _ok()


# ---------------------------------------------------------------------------
# Confidence floor
# ---------------------------------------------------------------------------
def check_confidence(confidence: Optional[float]) -> GuardrailResult:
    """Reject any decision with confidence below the autonomous floor.

    Caller should auto-escalate on rejection.
    """
    if confidence is None:
        return _bad("confidence_missing", "confidence required")
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        return _bad("confidence_bad", "confidence must be numeric")
    if confidence < MIN_AUTONOMOUS_CONFIDENCE:
        return _bad(
            "confidence_below_floor",
            "confidence {:.2f} below autonomous floor {:.2f}".format(
                confidence, MIN_AUTONOMOUS_CONFIDENCE
            ),
        )
    return _ok()


__all__ = [
    "GuardrailResult",
    "CREDIT_MAX_CENTS",
    "REFUND_MAX_CENTS",
    "MIN_AUTONOMOUS_CONFIDENCE",
    "validate_credit",
    "validate_refund",
    "validate_sms_rate",
    "validate_reassign",
    "check_confidence",
]
