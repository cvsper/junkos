"""
Ops Supervisor Agent — v1 HTTP surface (spec 11 §9).

Blueprint: ``ops_supervisor_v1_bp`` (``/ops-supervisor/v1alpha``). The MVP
blueprint at ``/ops-supervisor/v1`` is left untouched; this prefix keeps the
v1 endpoints isolated so both can coexist during migration.

Endpoints
---------
    POST /ops-supervisor/v1alpha/internal/events
        Service-token-guarded event ingestion. Persists the OpsEvent,
        classifies it via Claude Haiku (with rule fallback), publishes to
        the Redis event bus. If REDIS_URL is missing the publish path runs
        the LangGraph workflow inline (degraded single-process mode).

    POST /ops-supervisor/v1alpha/workflow/run
        Service-token-guarded debug hook. Runs the workflow synchronously
        for an existing event_id. Used by worker/one-shot tests.

The module never touches ``server.py`` — registration is identical to the
MVP blueprint: add ``app.register_blueprint(ops_supervisor_v1_bp)`` to
``server.py`` when ready.
"""

from __future__ import annotations

import hmac
import logging
import os
from typing import Optional

from flask import Blueprint, jsonify, request

from models import db, Job
from ops_supervisor_models import OpsEvent, Situation, AgentDecision, AgentAction, EscalationTicket
from ops_classifier import classify_event
from ops_event_bus import publish as bus_publish
from ops_langgraph import run_situation_workflow

logger = logging.getLogger(__name__)

ops_supervisor_v1_bp = Blueprint(
    "ops_supervisor_v1", __name__, url_prefix="/ops-supervisor/v1alpha"
)


def _service_token() -> str:
    return os.environ.get("OPS_SUPERVISOR_SERVICE_TOKEN", "")


def _require_service_token():
    token = _service_token()
    if not token:
        return jsonify({"error": "ops supervisor service token not configured"}), 503
    provided = request.headers.get("X-Service-Token", "")
    if not hmac.compare_digest(provided, token):
        return jsonify({"error": "unauthorized"}), 401
    return None


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


@ops_supervisor_v1_bp.route("/internal/events", methods=["POST"])
def ingest_event_v1():
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

    event = OpsEvent(
        type=event_type,
        booking_id=booking_id,
        payload_json=payload,
        source=source,
    )
    db.session.add(event)
    db.session.flush()

    # Classify early so the dashboard can show the tag even if the workflow
    # queues behind other events.
    booking = None
    if booking_id:
        booking = db.session.query(Job).filter_by(id=booking_id).first()

    classifier_result = classify_event(event, booking=booking)
    db.session.commit()

    # Publish. Returns a message id (Redis) or ``inline:<event_id>``.
    message_ref = bus_publish(event)

    # Re-read situation bundle (if the inline path ran, one exists).
    situation = (
        db.session.query(Situation)
        .filter(Situation.booking_id == booking_id)
        .order_by(Situation.opened_at.desc())
        .first()
        if booking_id else None
    )

    body_out = {
        "event": event.to_dict(),
        "classifier": classifier_result.to_dict(),
        "message_ref": message_ref,
        "situation_bundle": _situation_bundle(situation) if situation else None,
    }
    return jsonify(body_out), 201


@ops_supervisor_v1_bp.route("/workflow/run", methods=["POST"])
def run_workflow_debug():
    auth_err = _require_service_token()
    if auth_err is not None:
        return auth_err

    body = request.get_json(silent=True) or {}
    event_id = body.get("event_id")
    if not event_id:
        return jsonify({"error": "missing: event_id"}), 400

    state = run_situation_workflow(event_id)
    return jsonify({"state": state}), 200


__all__ = ["ops_supervisor_v1_bp"]
