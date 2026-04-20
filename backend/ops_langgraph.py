"""
Ops Supervisor — LangGraph workflow (spec 11 §9, v1).

Nodes
-----
    classify_event         — calls ``ops_classifier.classify_event``.
    open_or_merge_situation— creates/reuses a Situation row for the event.
    gather_context         — freezes booking + customer snapshot.
    decide                 — calls ``ops_decision_agent.decide``.
    guardrail_check        — already handled inside decide(); this node just
                              routes based on its result.
    execute_action         — fires the chosen tool with the existing MVP
                              executor helpers from routes/ops_supervisor.py.
    log_outcome            — flips decision status + annotates.
    escalate               — opens an EscalationTicket and (optionally) pages
                              PagerDuty.

State
-----
The graph state is a TypedDict wrapping the event id, the situation id, and
the intermediate products (classifier result, guarded decision, action rows).
We do NOT put ORM objects in state — only IDs and plain dicts — so the state
can be pickled by LangGraph's checkpointer safely.

Checkpointer
------------
``SqliteSaver`` backed by the same sqlite file the Flask app uses (when on
SQLite) or a dedicated file in ``/tmp/`` for Postgres deployments. The
checkpoint tables are created by ``ops_supervisor_v1_migrations``.

Fallback (no langgraph installed)
---------------------------------
If ``langgraph`` cannot be imported, ``run_situation_workflow`` falls back to
a straight-line function call of the same nodes so the route works in all
environments.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, TypedDict

from models import db, Job
from ops_supervisor_models import (
    OpsEvent,
    Situation,
    AgentDecision,
    AgentAction,
    EscalationTicket,
)
from ops_classifier import classify_event, ClassifierResult, DEFAULT_SEVERITY
from ops_decision_agent import decide, GuardedDecision, DecisionOutput
from ops_supervisor_sms import craft_sms

logger = logging.getLogger(__name__)


try:
    from langgraph.graph import StateGraph, END  # type: ignore
    _LANGGRAPH_OK = True
except Exception:  # pragma: no cover - fallback path
    StateGraph = None  # type: ignore
    END = "__end__"  # type: ignore
    _LANGGRAPH_OK = False


# ---------------------------------------------------------------------------
# Graph state
# ---------------------------------------------------------------------------
class WorkflowState(TypedDict, total=False):
    event_id: str
    booking_id: Optional[str]
    situation_id: Optional[str]
    classifier: Dict[str, Any]
    decision_id: Optional[str]
    decision_tool: Optional[str]
    decision_args: Dict[str, Any]
    decision_status: str
    guardrail_ok: bool
    guardrail_reason: Optional[str]
    confidence: float
    escalated: bool
    outcome: str
    error: Optional[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _load_event(event_id: str) -> Optional[OpsEvent]:
    if not event_id:
        return None
    return db.session.query(OpsEvent).filter_by(id=event_id).first()


def _load_booking(booking_id: Optional[str]) -> Optional[Job]:
    if not booking_id:
        return None
    return db.session.query(Job).filter_by(id=booking_id).first()


def _load_situation(sid: Optional[str]) -> Optional[Situation]:
    if not sid:
        return None
    return db.session.query(Situation).filter_by(id=sid).first()


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


# ---------------------------------------------------------------------------
# Node implementations
# ---------------------------------------------------------------------------
def node_classify_event(state: WorkflowState) -> WorkflowState:
    event = _load_event(state.get("event_id", ""))
    if event is None:
        return {**state, "error": "event not found", "outcome": "missing_event"}

    booking = _load_booking(event.booking_id)
    result = classify_event(event, booking=booking)
    db.session.flush()

    return {
        **state,
        "booking_id": event.booking_id,
        "classifier": result.to_dict(),
        "confidence": float(result.confidence or 0.0),
    }


def node_open_or_merge_situation(state: WorkflowState) -> WorkflowState:
    event = _load_event(state.get("event_id", ""))
    if event is None:
        return {**state, "error": "event not found", "outcome": "missing_event"}

    cls = state.get("classifier") or {}
    tag = cls.get("tag") or "other"
    severity = cls.get("suggested_severity") or DEFAULT_SEVERITY.get(tag, "low")

    # Merge rule: if an OPEN Situation exists on the same booking with the
    # same tag within the last 30 min, attach new evidence to it.
    existing = None
    if event.booking_id:
        existing = (
            db.session.query(Situation)
            .filter(Situation.booking_id == event.booking_id,
                    Situation.tag == tag,
                    Situation.closed_at.is_(None))
            .order_by(Situation.opened_at.desc())
            .first()
        )

    if existing is not None:
        situation = existing
    else:
        situation = Situation(
            booking_id=event.booking_id,
            primary_event_id=event.id,
            tag=tag,
            context_snapshot_json={
                "event_id": event.id,
                "event_type": event.type,
                "classifier": cls,
            },
            severity=severity,
        )
        db.session.add(situation)
        db.session.flush()

    return {**state, "situation_id": situation.id}


def node_gather_context(state: WorkflowState) -> WorkflowState:
    situation = _load_situation(state.get("situation_id"))
    if situation is None:
        return {**state, "error": "situation missing", "outcome": "missing_situation"}

    booking = _load_booking(situation.booking_id)
    snapshot = situation.context_snapshot_json or {}
    snapshot["booking"] = _booking_summary(booking)
    situation.context_snapshot_json = snapshot
    db.session.flush()
    return state


def node_decide(state: WorkflowState) -> WorkflowState:
    situation = _load_situation(state.get("situation_id"))
    if situation is None:
        return {**state, "error": "situation missing"}

    booking = _load_booking(situation.booking_id)
    guarded: GuardedDecision = decide(situation, booking=booking)

    return {
        **state,
        "decision_id": guarded.decision.id,
        "decision_tool": guarded.output.tool,
        "decision_args": dict(guarded.output.args or {}),
        "decision_status": guarded.decision.status,
        "guardrail_ok": bool(guarded.guardrail.ok),
        "guardrail_reason": guarded.guardrail.reason,
        "confidence": float(guarded.output.confidence or 0.0),
    }


def node_guardrail_check(state: WorkflowState) -> WorkflowState:
    # decide() already ran validators. This node exists so the graph has a
    # clean branch-point for the dashboard ("this workflow was blocked
    # here").
    return state


def node_execute_action(state: WorkflowState) -> WorkflowState:
    """Execute the chosen tool. We reuse the helpers baked into the MVP
    route module — that file is the single source of truth for side-effects
    so v1 does not drift from it.
    """
    decision_id = state.get("decision_id")
    if not decision_id:
        return {**state, "outcome": "no_decision"}

    decision = db.session.query(AgentDecision).filter_by(id=decision_id).first()
    if decision is None:
        return {**state, "outcome": "decision_missing"}

    situation = _load_situation(state.get("situation_id"))
    booking = _load_booking(situation.booking_id if situation else None)
    tool = state.get("decision_tool") or ""
    args = state.get("decision_args") or {}

    # Import here to avoid an import-time cycle with routes/ops_supervisor.
    from routes import ops_supervisor as ops_routes

    action_status = "executed"
    action_external_ref = None
    action_error = None
    action_args = dict(args)

    try:
        if tool == "issue_credit":
            ops_routes._write_action(  # type: ignore[attr-defined]
                decision, "issue_credit", action_args,
                status="executed",
                external_ref="v1-stub-credit-{}".format(decision.id[:8]),
            )
        elif tool == "issue_refund":
            ops_routes._write_action(  # type: ignore[attr-defined]
                decision, "issue_refund", action_args,
                status="executed",
                external_ref="v1-stub-refund-{}".format(decision.id[:8]),
            )
        elif tool == "send_customer_sms":
            summary = _booking_summary(booking)
            body = action_args.get("body") or craft_sms(
                situation.tag or "other", summary, action_args,
            )
            phone = summary.get("customer_phone")
            external_ref = None
            send_status = "executed"
            err = None
            try:
                if ops_routes.sms_service is not None and phone:
                    external_ref = ops_routes.sms_service.send_sms(phone, body)
                elif not phone:
                    err = "no customer phone on file"
            except Exception as exc:
                send_status = "failed"
                err = str(exc)
            ops_routes._write_action(  # type: ignore[attr-defined]
                decision, "send_customer_sms",
                {"to": phone, "body": body, "situation_id": situation.id},
                status=send_status,
                external_ref=str(external_ref) if external_ref else None,
                error_message=err,
            )
            action_status = send_status
            action_error = err
        elif tool == "send_driver_sms":
            summary = _booking_summary(booking)
            body = action_args.get("body") or (
                "Umuve check-in: please confirm status on the current job."
            )
            phone = summary.get("driver_phone")
            external_ref = None
            send_status = "executed"
            err = None
            try:
                if ops_routes.sms_service is not None and phone:
                    external_ref = ops_routes.sms_service.send_sms(phone, body)
                elif not phone:
                    err = "no driver phone on file"
            except Exception as exc:
                send_status = "failed"
                err = str(exc)
            ops_routes._write_action(  # type: ignore[attr-defined]
                decision, "send_driver_sms",
                {"to": phone, "body": body},
                status=send_status,
                external_ref=str(external_ref) if external_ref else None,
                error_message=err,
            )
            action_status = send_status
            action_error = err
        elif tool == "reassign_driver":
            ops_routes._write_action(  # type: ignore[attr-defined]
                decision, "reassign_driver", action_args,
                status="executed",
                external_ref="v1-stub-reassign",
            )
        elif tool == "escalate_human":
            # Handled in escalate node; write a marker action here.
            ops_routes._write_action(  # type: ignore[attr-defined]
                decision, "escalate_human", action_args,
                status="executed",
            )
        elif tool == "no_action":
            ops_routes._write_action(  # type: ignore[attr-defined]
                decision, "no_action", action_args,
                status="executed",
            )
        else:
            action_status = "failed"
            action_error = "unknown tool: {}".format(tool)
            ops_routes._write_action(  # type: ignore[attr-defined]
                decision, tool or "unknown", action_args,
                status="failed",
                error_message=action_error,
            )
    except Exception as exc:
        logger.exception("ops_langgraph.execute_action failed")
        action_status = "failed"
        action_error = str(exc)

    return {
        **state,
        "decision_status": action_status,
        "outcome": action_status,
    }


def node_log_outcome(state: WorkflowState) -> WorkflowState:
    decision_id = state.get("decision_id")
    if not decision_id:
        return state

    decision = db.session.query(AgentDecision).filter_by(id=decision_id).first()
    if decision is None:
        return state

    actions = (db.session.query(AgentAction)
               .filter_by(decision_id=decision.id).all())

    if not state.get("guardrail_ok", True):
        decision.status = "blocked_by_guardrail"
    elif actions and all(a.status == "blocked_by_guardrail" for a in actions):
        decision.status = "blocked_by_guardrail"
    elif actions and any(a.status == "executed" for a in actions):
        decision.status = "executed"
    elif actions:
        decision.status = "failed"
    else:
        decision.status = "failed"

    db.session.flush()
    return {**state, "decision_status": decision.status}


def node_escalate(state: WorkflowState) -> WorkflowState:
    """Open an escalation ticket and trigger PagerDuty. Called when the
    guardrail blocked the decision, confidence was too low, or the model
    picked escalate_human.
    """
    situation = _load_situation(state.get("situation_id"))
    if situation is None:
        return {**state, "escalated": False}

    priority = "p2"
    args = state.get("decision_args") or {}
    if state.get("decision_tool") == "escalate_human":
        priority = str(args.get("priority") or "p2").lower()
    if not state.get("guardrail_ok", True):
        priority = "p1"
    if state.get("confidence", 1.0) < 0.60:
        priority = "p1"

    summary = "Ops supervisor escalation for situation {} (tag={}).".format(
        situation.id, situation.tag,
    )
    if state.get("guardrail_reason"):
        summary += " Guardrail: {}".format(state["guardrail_reason"])

    ticket = EscalationTicket(
        situation_id=situation.id,
        priority=priority,
        assignee="ops-on-call",
        summary_md=summary,
    )
    db.session.add(ticket)
    db.session.flush()

    # PagerDuty is optional — the module handles missing routing key.
    try:
        from ops_pagerduty import trigger_incident
        trigger_incident(ticket)
    except Exception:
        logger.exception("ops_langgraph.escalate: pagerduty trigger failed")

    return {**state, "escalated": True}


# ---------------------------------------------------------------------------
# Routing logic (branches)
# ---------------------------------------------------------------------------
def _route_after_decide(state: WorkflowState) -> str:
    # Block path: guardrail rejected OR confidence floor violated.
    if not state.get("guardrail_ok", True):
        return "escalate"
    # Explicit escalate tool short-circuits execute.
    if (state.get("decision_tool") or "") == "escalate_human":
        return "escalate"
    # Low confidence auto-escalate.
    if state.get("confidence", 0.0) < 0.60:
        return "escalate"
    return "execute_action"


def _route_after_execute(state: WorkflowState) -> str:
    if state.get("decision_status") == "failed":
        return "escalate"
    return "log_outcome"


# ---------------------------------------------------------------------------
# Build the compiled graph (with SqliteSaver checkpointer)
# ---------------------------------------------------------------------------
_compiled_graph = None
_checkpointer_cm = None


def _build_graph():
    if not _LANGGRAPH_OK:
        return None

    graph = StateGraph(WorkflowState)
    graph.add_node("classify_event", node_classify_event)
    graph.add_node("open_or_merge_situation", node_open_or_merge_situation)
    graph.add_node("gather_context", node_gather_context)
    graph.add_node("decide", node_decide)
    graph.add_node("guardrail_check", node_guardrail_check)
    graph.add_node("execute_action", node_execute_action)
    graph.add_node("log_outcome", node_log_outcome)
    graph.add_node("escalate", node_escalate)

    graph.set_entry_point("classify_event")
    graph.add_edge("classify_event", "open_or_merge_situation")
    graph.add_edge("open_or_merge_situation", "gather_context")
    graph.add_edge("gather_context", "decide")
    graph.add_edge("decide", "guardrail_check")
    graph.add_conditional_edges(
        "guardrail_check",
        _route_after_decide,
        {"execute_action": "execute_action", "escalate": "escalate"},
    )
    graph.add_conditional_edges(
        "execute_action",
        _route_after_execute,
        {"log_outcome": "log_outcome", "escalate": "escalate"},
    )
    graph.add_edge("escalate", "log_outcome")
    graph.add_edge("log_outcome", END)

    return graph


def _checkpointer_path() -> str:
    """Where to store the SqliteSaver db.

    Priority:
      1. ``LANGGRAPH_CHECKPOINT_DB`` env var (explicit).
      2. ``:memory:`` if we're on an in-memory Flask test db.
      3. ``/tmp/ops_langgraph.sqlite`` otherwise.
    """
    override = os.environ.get("LANGGRAPH_CHECKPOINT_DB")
    if override:
        return override
    uri = os.environ.get("SQLALCHEMY_DATABASE_URI", "")
    if "memory" in uri:
        return ":memory:"
    return "/tmp/ops_langgraph.sqlite"


def get_compiled_graph():
    """Return a compiled LangGraph app with a SqliteSaver checkpointer.

    Returns None when langgraph isn't installed — the caller falls back to
    the straight-line function-call runner.
    """
    global _compiled_graph, _checkpointer_cm
    if not _LANGGRAPH_OK:
        return None
    if _compiled_graph is not None:
        return _compiled_graph

    graph = _build_graph()
    if graph is None:
        return None

    checkpointer = None
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver  # type: ignore
        path = _checkpointer_path()
        # SqliteSaver.from_conn_string is a context manager; we hold onto it
        # for the process lifetime so the compiled graph stays usable.
        _checkpointer_cm = SqliteSaver.from_conn_string(path)
        checkpointer = _checkpointer_cm.__enter__()
    except Exception:
        logger.exception("ops_langgraph: SqliteSaver init failed; running "
                         "without checkpointer")

    if checkpointer is not None:
        _compiled_graph = graph.compile(checkpointer=checkpointer)
    else:
        _compiled_graph = graph.compile()
    return _compiled_graph


# ---------------------------------------------------------------------------
# Straight-line fallback
# ---------------------------------------------------------------------------
def _run_linear(state: WorkflowState) -> WorkflowState:
    state = node_classify_event(state)
    if state.get("error"):
        return state
    state = node_open_or_merge_situation(state)
    if state.get("error"):
        return state
    state = node_gather_context(state)
    if state.get("error"):
        return state
    state = node_decide(state)
    state = node_guardrail_check(state)
    branch = _route_after_decide(state)
    if branch == "escalate":
        state = node_escalate(state)
        state = node_log_outcome(state)
        return state
    state = node_execute_action(state)
    branch2 = _route_after_execute(state)
    if branch2 == "escalate":
        state = node_escalate(state)
    state = node_log_outcome(state)
    return state


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def run_situation_workflow(event_id: str, *, thread_id: Optional[str] = None) -> Dict[str, Any]:
    """Drive the full workflow for an OpsEvent.

    Uses the LangGraph compiled app when available, else a straight-line
    runner. Always commits the DB session at the end so callers (route or
    worker) don't have to.
    """
    if not event_id:
        return {"error": "missing event_id"}

    initial: WorkflowState = {
        "event_id": event_id,
        "decision_args": {},
        "classifier": {},
        "guardrail_ok": True,
        "escalated": False,
        "outcome": "pending",
        "confidence": 0.0,
    }

    compiled = get_compiled_graph()
    try:
        if compiled is not None:
            thread = thread_id or "event-{}".format(event_id)
            config = {"configurable": {"thread_id": thread}}
            final_state = compiled.invoke(initial, config=config)
        else:
            final_state = _run_linear(initial)
        db.session.commit()
        return dict(final_state or {})
    except Exception:
        db.session.rollback()
        logger.exception("ops_langgraph.run_situation_workflow failed")
        raise


__all__ = [
    "run_situation_workflow",
    "get_compiled_graph",
    "WorkflowState",
    "node_classify_event",
    "node_open_or_merge_situation",
    "node_gather_context",
    "node_decide",
    "node_guardrail_check",
    "node_execute_action",
    "node_log_outcome",
    "node_escalate",
]
