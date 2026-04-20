"""
Ops Supervisor Agent — HTTP surface (spec 11 §§4–8, 72h MVP).

Blueprint: ``ops_supervisor_bp`` (``/ops-supervisor/v1``).

Endpoints
---------
  POST /ops-supervisor/v1/internal/events
        Service-token-guarded event ingestion. Runs the matching rule-based
        detector and, if it fires, opens a Situation + records
        AgentDecision + runs the hard-coded action through the guardrail
        layer. Returns the full chain for the caller to inspect.

  POST /ops-supervisor/v1/situations/<id>/close
        Ops-user close with outcome note.

  GET  /ops-supervisor/v1/situations?severity=&open=
        Dashboard list.

  GET  /ops-supervisor/v1/situations/<id>
        Full situation + decisions + actions + escalations.

  POST /ops-supervisor/v1/escalations/<id>/resolve
        Human resolution of an escalation ticket.

The blueprint avoids editing ``server.py``. To activate it, add this to
``server.py`` after the existing blueprint block:

    try:
        from routes.ops_supervisor import ops_supervisor_bp
        app.register_blueprint(ops_supervisor_bp)
    except Exception as _o_exc:
        logging.getLogger(__name__).warning(
            "ops_supervisor_bp not registered: %s", _o_exc
        )
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import time
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from sqlalchemy import desc

from models import db, Job, User
from ops_supervisor_models import (
    OpsEvent,
    Situation,
    AgentDecision,
    AgentAction,
    EscalationTicket,
)
from ops_supervisor_detectors import run_detector_for_event
from ops_supervisor_guardrails import (
    CREDIT_MAX_CENTS,
    validate_credit,
    validate_refund,
    validate_sms_rate,
    validate_reassign,
    check_confidence,
)
from ops_supervisor_sms import craft_sms

try:
    import sms_service  # type: ignore
except Exception:  # pragma: no cover - sms_service always present in repo
    sms_service = None  # type: ignore

logger = logging.getLogger(__name__)

ops_supervisor_bp = Blueprint(
    "ops_supervisor", __name__, url_prefix="/ops-supervisor/v1"
)


# ---------------------------------------------------------------------------
# Auth — service token for /internal/*, open for dashboard endpoints
# (dashboard auth is deferred to v1 where we wire the staff JWT).
# ---------------------------------------------------------------------------
def _service_token() -> str:
    return os.environ.get("OPS_SUPERVISOR_SERVICE_TOKEN", "")


def _require_service_token():
    """Return an error response if the service token is missing/invalid,
    else ``None``."""
    token = _service_token()
    if not token:
        return jsonify({"error": "ops supervisor service token not configured"}), 503
    provided = request.headers.get("X-Service-Token", "")
    if not hmac.compare_digest(provided, token):
        return jsonify({"error": "unauthorized"}), 401
    return None


# ---------------------------------------------------------------------------
# Hard-coded action templates (spec §2 / §7 MVP subset)
# ---------------------------------------------------------------------------
# For the MVP these are literal dicts. v1 replaces this with the Opus
# decision agent emitting the same shape.

FLAT_LATE_CREDIT_CENTS = 1500  # $15

ACTION_TEMPLATES = {
    "truck_late": {
        "rationale": "Job is >15 min late. Issue flat $15 credit and apology SMS per MVP template.",
        "confidence": 0.90,
        "steps": [
            {"tool": "issue_credit", "amount_cents": FLAT_LATE_CREDIT_CENTS},
            {"tool": "send_customer_sms"},
        ],
    },
    "payment_failed_post_job": {
        "rationale": "Completed job with failed charge. Send retry-link SMS. NO credit, NO refund.",
        "confidence": 0.90,
        "steps": [
            {"tool": "send_customer_sms"},
        ],
    },
    "gps_deviation": {
        "rationale": "Driver >2 mi off route for >8 min. Check in via driver SMS; escalate if no reply.",
        "confidence": 0.90,
        "steps": [
            {"tool": "send_driver_sms"},
            # 5-minute reply wait is deferred to v1 (async loop). For the
            # MVP we open a P2 escalation synchronously so the situation is
            # visible to humans right away.
            {"tool": "open_escalation", "priority": "p2"},
        ],
    },
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _booking_summary(booking) -> dict:
    if booking is None:
        return {}
    customer = getattr(booking, "customer", None)
    customer_name = getattr(customer, "name", None) if customer else None
    customer_phone = getattr(customer, "phone", None) if customer else None
    driver = getattr(booking, "driver", None)
    driver_user = getattr(driver, "user", None) if driver else None
    driver_phone = getattr(driver_user, "phone", None) if driver_user else None
    return {
        "booking_id": getattr(booking, "id", None),
        "status": getattr(booking, "status", None),
        "scheduled_at": (
            booking.scheduled_at.isoformat()
            if getattr(booking, "scheduled_at", None) else None
        ),
        "address": getattr(booking, "address", None),
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "driver_phone": driver_phone,
    }


def _write_action(
    decision: AgentDecision,
    tool: str,
    args: dict,
    status: str,
    external_ref: str = None,
    error_message: str = None,
) -> AgentAction:
    action = AgentAction(
        decision_id=decision.id,
        tool=tool,
        args_json=args or {},
        status=status,
        external_ref=external_ref,
        error_message=error_message,
        executed_at=datetime.now(timezone.utc) if status == "executed" else None,
    )
    db.session.add(action)
    db.session.flush()
    return action


def _open_escalation(
    situation: Situation,
    priority: str,
    summary_md: str,
    assignee: str = "ops-on-call",
) -> EscalationTicket:
    ticket = EscalationTicket(
        situation_id=situation.id,
        priority=priority,
        assignee=assignee,
        summary_md=summary_md,
    )
    db.session.add(ticket)
    db.session.flush()
    return ticket


def _situation_bundle(situation: Situation) -> dict:
    decisions = (
        db.session.query(AgentDecision)
        .filter(AgentDecision.situation_id == situation.id)
        .order_by(AgentDecision.created_at)
        .all()
    )
    actions_by_decision: dict[str, list] = {}
    if decisions:
        decision_ids = [d.id for d in decisions]
        actions = (
            db.session.query(AgentAction)
            .filter(AgentAction.decision_id.in_(decision_ids))
            .order_by(AgentAction.created_at)
            .all()
        )
        for a in actions:
            actions_by_decision.setdefault(a.decision_id, []).append(a.to_dict())

    escalations = (
        db.session.query(EscalationTicket)
        .filter(EscalationTicket.situation_id == situation.id)
        .order_by(EscalationTicket.created_at)
        .all()
    )
    return {
        "situation": situation.to_dict(),
        "decisions": [
            {**d.to_dict(), "actions": actions_by_decision.get(d.id, [])}
            for d in decisions
        ],
        "escalations": [t.to_dict() for t in escalations],
    }


# ---------------------------------------------------------------------------
# Orchestration — detector fires -> decision -> gated action chain
# ---------------------------------------------------------------------------
def _execute_action_chain(situation: Situation, booking, detection):
    """Walk the template steps for a detection, applying guardrails at each
    step. Returns the ``AgentDecision`` row (decisions are ALWAYS written
    first per spec §7 audit rule).
    """
    template = ACTION_TEMPLATES.get(detection.tag)
    if template is None:
        # Unknown tag -> escalate so nothing falls on the floor.
        decision = AgentDecision(
            situation_id=situation.id,
            rationale="No template for tag {}".format(detection.tag),
            confidence=detection.confidence,
            decision_json={"tag": detection.tag, "reason": "no_template"},
            status="failed",
        )
        db.session.add(decision)
        db.session.flush()
        _open_escalation(
            situation, "p2",
            "No automated playbook for tag `{}`.".format(detection.tag),
        )
        return decision

    start_ts = time.time()
    decision = AgentDecision(
        situation_id=situation.id,
        rationale=template["rationale"],
        confidence=template["confidence"],
        decision_json={
            "tag": detection.tag,
            "severity": detection.severity,
            "steps": [s["tool"] for s in template["steps"]],
            "detector_details": detection.details,
        },
        status="pending",
    )
    db.session.add(decision)
    db.session.flush()

    # Confidence floor -- violates => escalate and bail.
    conf_check = check_confidence(decision.confidence)
    if not conf_check.ok:
        _write_action(
            decision, "log_decision", {"reason": conf_check.reason},
            status="blocked_by_guardrail",
            error_message=conf_check.reason,
        )
        _open_escalation(
            situation, "p1",
            "Confidence below autonomous floor -- {}".format(conf_check.reason),
        )
        decision.status = "blocked_by_guardrail"
        decision.latency_ms = int((time.time() - start_ts) * 1000)
        return decision

    # Walk steps.
    credit_already_applied_cents = 0
    for step in template["steps"]:
        tool = step["tool"]

        if tool == "issue_credit":
            amount_cents = int(step.get("amount_cents") or 0)
            gate = validate_credit(amount_cents)
            if not gate.ok:
                _write_action(
                    decision, tool, {"amount_cents": amount_cents},
                    status="blocked_by_guardrail",
                    error_message=gate.reason,
                )
                _open_escalation(
                    situation, "p1",
                    "Credit blocked: {}".format(gate.reason),
                )
                continue
            # MVP: we do NOT call Stripe yet -- just record that the credit
            # was "issued" so the downstream SMS can reference the amount.
            # v1 swaps this for a real balance_transaction API call.
            credit_already_applied_cents = amount_cents
            _write_action(
                decision, tool,
                {"amount_cents": amount_cents, "reason": "late_apology"},
                status="executed",
                external_ref="mvp-stub-credit-{}".format(decision.id[:8]),
            )

        elif tool == "issue_refund":
            amount_cents = int(step.get("amount_cents") or 0)
            gate = validate_refund(amount_cents)
            if not gate.ok:
                _write_action(
                    decision, tool, {"amount_cents": amount_cents},
                    status="blocked_by_guardrail",
                    error_message=gate.reason,
                )
                _open_escalation(
                    situation, "p1",
                    "Refund blocked: {}".format(gate.reason),
                )
                continue
            _write_action(
                decision, tool,
                {"amount_cents": amount_cents},
                status="executed",
                external_ref="mvp-stub-refund-{}".format(decision.id[:8]),
            )

        elif tool == "send_customer_sms":
            gate = validate_sms_rate(db.session, situation.id)
            if not gate.ok:
                _write_action(
                    decision, tool, {"situation_id": situation.id},
                    status="blocked_by_guardrail",
                    error_message=gate.reason,
                )
                continue

            summary = _booking_summary(booking)
            action_context = {
                "credit_dollars": credit_already_applied_cents / 100.0
                    if credit_already_applied_cents else None,
                "minutes_late": detection.details.get("minutes_late"),
                "retry_link": "https://goumuve.com/pay/{}".format(
                    getattr(booking, "id", "")[:8] if booking else ""
                ),
            }
            body = craft_sms(detection.tag, summary, action_context)
            phone = summary.get("customer_phone")
            external_ref = None
            send_status = "executed"
            error_message = None
            if sms_service is not None and phone:
                try:
                    external_ref = sms_service.send_sms(phone, body)
                except Exception as exc:
                    send_status = "failed"
                    error_message = str(exc)
            elif not phone:
                # No phone on file -- log as executed-but-noop so we still
                # rate-limit correctly (don't fire a second).
                send_status = "executed"
                error_message = "no customer phone on file"

            _write_action(
                decision, tool,
                {"to": phone, "body": body, "situation_id": situation.id},
                status=send_status,
                external_ref=str(external_ref) if external_ref else None,
                error_message=error_message,
            )

        elif tool == "send_driver_sms":
            summary = _booking_summary(booking)
            phone = summary.get("driver_phone")
            body = (
                "Umuve check-in: our GPS shows you 2+mi off route for 8min."
                " Confirm you're OK and still heading to the job."
            )
            external_ref = None
            send_status = "executed"
            error_message = None
            if sms_service is not None and phone:
                try:
                    external_ref = sms_service.send_sms(phone, body)
                except Exception as exc:
                    send_status = "failed"
                    error_message = str(exc)
            elif not phone:
                send_status = "executed"
                error_message = "no driver phone on file"
            _write_action(
                decision, tool,
                {"to": phone, "body": body},
                status=send_status,
                external_ref=str(external_ref) if external_ref else None,
                error_message=error_message,
            )

        elif tool == "reassign_driver":
            gate = validate_reassign(booking)
            if not gate.ok:
                _write_action(
                    decision, tool, {"booking_id": getattr(booking, "id", None)},
                    status="blocked_by_guardrail",
                    error_message=gate.reason,
                )
                _open_escalation(
                    situation, "p1",
                    "Reassign blocked: {}".format(gate.reason),
                )
                continue
            # MVP does not actually reassign -- deferred to v1 dispatcher.
            _write_action(
                decision, tool, {"booking_id": getattr(booking, "id", None)},
                status="executed",
                external_ref="mvp-stub-reassign",
            )

        elif tool == "open_escalation":
            priority = step.get("priority", "p2")
            summary_md = (
                "Auto-opened escalation for situation `{sit}` (tag `{tag}`)."
            ).format(sit=situation.id, tag=detection.tag)
            ticket = _open_escalation(situation, priority, summary_md)
            _write_action(
                decision, tool,
                {"ticket_id": ticket.id, "priority": priority},
                status="executed",
                external_ref=ticket.id,
            )

        else:
            logger.warning("Unknown tool in template: %s", tool)
            _write_action(
                decision, tool, dict(step),
                status="failed",
                error_message="unknown tool",
            )

    # Final decision status = executed unless ALL actions were blocked.
    actions = db.session.query(AgentAction).filter_by(decision_id=decision.id).all()
    if actions and all(a.status == "blocked_by_guardrail" for a in actions):
        decision.status = "blocked_by_guardrail"
    elif actions and any(a.status == "executed" for a in actions):
        decision.status = "executed"
    else:
        decision.status = "failed"

    decision.latency_ms = int((time.time() - start_ts) * 1000)
    return decision


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@ops_supervisor_bp.route("/internal/events", methods=["POST"])
def ingest_event():
    """Service-token guarded event ingestion.

    Body: ``{"type": "booking.late", "booking_id": "...", "payload": {...},
              "source": "gps_tracker"}``
    """
    auth_err = _require_service_token()
    if auth_err is not None:
        return auth_err

    body = request.get_json(silent=True) or {}
    event_type = body.get("type")
    booking_id = body.get("booking_id")
    payload = body.get("payload") or {}
    source = body.get("source") or "unknown"

    if not event_type:
        return jsonify({"error": "missing: type"}), 400

    # Record the raw event first. This is audit-critical -- even if no
    # detector fires, we want the signal on disk.
    event = OpsEvent(
        type=event_type,
        booking_id=booking_id,
        payload_json=payload,
        source=source,
    )
    db.session.add(event)
    db.session.flush()

    booking = None
    if booking_id:
        booking = db.session.query(Job).filter_by(id=booking_id).first()

    detection = run_detector_for_event(event_type, booking, payload)
    response = {
        "event": event.to_dict(),
        "detection": None,
        "situation": None,
        "decisions": [],
        "escalations": [],
    }

    if detection is None:
        db.session.commit()
        return jsonify(response), 202

    # Tag the event for dashboards.
    event.classifier_tag = detection.tag
    event.classifier_confidence = detection.confidence

    # Open a Situation and freeze context at decision time (spec §4).
    context_snapshot = {
        "booking": _booking_summary(booking),
        "detector_details": detection.details,
        "event_type": event_type,
        "event_id": event.id,
    }
    situation = Situation(
        booking_id=booking_id,
        primary_event_id=event.id,
        tag=detection.tag,
        context_snapshot_json=context_snapshot,
        severity=detection.severity,
    )
    db.session.add(situation)
    db.session.flush()

    decision = _execute_action_chain(situation, booking, detection)

    db.session.commit()

    response["detection"] = {
        "tag": detection.tag,
        "severity": detection.severity,
        "confidence": detection.confidence,
        "details": detection.details,
    }
    response["situation"] = situation.to_dict()
    response["decisions"] = [
        {
            **decision.to_dict(),
            "actions": [a.to_dict() for a in decision.actions],
        }
    ]
    response["escalations"] = [t.to_dict() for t in situation.escalations]
    return jsonify(response), 201


@ops_supervisor_bp.route("/situations", methods=["GET"])
def list_situations():
    severity = request.args.get("severity")
    open_only_raw = request.args.get("open")
    open_only = None
    if open_only_raw is not None:
        open_only = open_only_raw.lower() in {"1", "true", "yes"}

    q = db.session.query(Situation)
    if severity:
        q = q.filter(Situation.severity == severity)
    if open_only is True:
        q = q.filter(Situation.closed_at.is_(None))
    elif open_only is False:
        q = q.filter(Situation.closed_at.isnot(None))

    q = q.order_by(desc(Situation.opened_at)).limit(200)
    return jsonify({"situations": [s.to_dict() for s in q.all()]}), 200


@ops_supervisor_bp.route("/situations/<sid>", methods=["GET"])
def get_situation(sid: str):
    situation = db.session.query(Situation).filter_by(id=sid).first()
    if situation is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(_situation_bundle(situation)), 200


@ops_supervisor_bp.route("/situations/<sid>/close", methods=["POST"])
def close_situation(sid: str):
    situation = db.session.query(Situation).filter_by(id=sid).first()
    if situation is None:
        return jsonify({"error": "not found"}), 404
    if situation.closed_at is not None:
        return jsonify({"error": "already closed"}), 409

    body = request.get_json(silent=True) or {}
    outcome = body.get("outcome") or "manual_close"
    situation.closed_at = datetime.now(timezone.utc)
    situation.outcome = outcome
    db.session.commit()
    return jsonify(_situation_bundle(situation)), 200


@ops_supervisor_bp.route("/escalations/<tid>/resolve", methods=["POST"])
def resolve_escalation(tid: str):
    ticket = db.session.query(EscalationTicket).filter_by(id=tid).first()
    if ticket is None:
        return jsonify({"error": "not found"}), 404
    if ticket.resolved_at is not None:
        return jsonify({"error": "already resolved"}), 409

    body = request.get_json(silent=True) or {}
    ticket.resolved_at = datetime.now(timezone.utc)
    ticket.resolution_note = body.get("note") or "resolved"
    db.session.commit()
    return jsonify(ticket.to_dict()), 200


__all__ = ["ops_supervisor_bp"]
