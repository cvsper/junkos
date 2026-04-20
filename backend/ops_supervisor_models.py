"""
Ops Supervisor Agent — ORM models (spec 11, 72h MVP).

Imports ``db`` from ``models`` so all tables register on the same metadata
used by ``db.create_all()``. This module is additive: it does NOT modify
``models.py``. Tables stood up by this module:

    ops_events             — raw event inbox (GPS pings, payment failures…)
    situations             — grouped, actionable events ("truck late on job X")
    agent_decisions        — every decision chain (hard-coded in MVP, Opus in v1)
    agent_actions          — tool calls gated by the guardrail layer
    escalation_tickets     — human follow-up queue

Conventions (matching models.py / routes/portal.py):
  * String(36) UUID primary keys (default=generate_uuid).
  * CheckConstraint (NOT SQLAlchemy Enum) for status/severity/priority — keeps
    SQLite + Postgres schemas identical and lets us evolve values with a plain
    ALTER TABLE DROP CONSTRAINT in Postgres.
  * JSON columns for flexible payloads (payload_json, decision_json, args_json,
    context_snapshot_json). SQLite stores these as TEXT transparently.
  * Indexes on booking_id + received_at + opened_at — dashboards need them.

The MVP intentionally does NOT add strict event-type CheckConstraints: the
producer side (webhooks, cron pollers) is still in flux and restricting the
vocabulary now would force schema migrations every time we add a detector.
"""

from __future__ import annotations

from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    CheckConstraint,
    Index,
)
from sqlalchemy.orm import relationship

# Reuse the single SQLAlchemy registry from models.py so create_all() sees us.
from models import db, generate_uuid, utcnow


# ---------------------------------------------------------------------------
# OpsEvent — raw event inbox
# ---------------------------------------------------------------------------
class OpsEvent(db.Model):
    __tablename__ = "ops_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    # Free-form event type (e.g. booking.gps.deviation, booking.late,
    # payment.failed). We do not enforce an enum — the vocabulary will grow
    # rapidly through v1 and migrations would be a tax.
    type = Column(String(80), nullable=False)
    booking_id = Column(
        String(36),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    payload_json = Column(JSON, nullable=True)
    source = Column(String(40), nullable=True)  # gps_tracker, stripe, twilio...
    received_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    classifier_tag = Column(String(60), nullable=True)  # e.g. "truck_late"
    classifier_confidence = Column(Float, nullable=True)

    __table_args__ = (
        Index("ix_ops_events_type", "type"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "booking_id": self.booking_id,
            "payload": self.payload_json or {},
            "source": self.source,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "classifier_tag": self.classifier_tag,
            "classifier_confidence": self.classifier_confidence,
        }


# ---------------------------------------------------------------------------
# Situation — a grouped, actionable anomaly on a booking
# ---------------------------------------------------------------------------
class Situation(db.Model):
    __tablename__ = "ops_situations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    booking_id = Column(
        String(36),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    primary_event_id = Column(
        String(36),
        ForeignKey("ops_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    tag = Column(String(60), nullable=True)  # mirrors OpsEvent.classifier_tag
    context_snapshot_json = Column(JSON, nullable=True)
    severity = Column(String(10), nullable=False, default="low")
    opened_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    closed_at = Column(DateTime, nullable=True)
    outcome = Column(String(60), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "severity IN ('info','low','medium','high','critical')",
            name="ck_ops_situation_severity",
        ),
    )

    primary_event = relationship("OpsEvent", foreign_keys=[primary_event_id])
    decisions = relationship(
        "AgentDecision",
        back_populates="situation",
        cascade="all, delete-orphan",
        order_by="AgentDecision.created_at",
    )
    escalations = relationship(
        "EscalationTicket",
        back_populates="situation",
        cascade="all, delete-orphan",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "booking_id": self.booking_id,
            "primary_event_id": self.primary_event_id,
            "tag": self.tag,
            "severity": self.severity,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "outcome": self.outcome,
            "context": self.context_snapshot_json or {},
        }


# ---------------------------------------------------------------------------
# AgentDecision — every decision is logged even if no action fires
# ---------------------------------------------------------------------------
class AgentDecision(db.Model):
    __tablename__ = "ops_agent_decisions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    situation_id = Column(
        String(36),
        ForeignKey("ops_situations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # MVP is rules-based. v1 will set model="claude-opus-4-7" or similar.
    model = Column(String(60), nullable=False, default="rules-mvp-v1")
    prompt_hash = Column(String(64), nullable=True)
    decision_json = Column(JSON, nullable=True)
    rationale = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    status = Column(String(30), nullable=False, default="pending")
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','executed','blocked_by_guardrail','failed')",
            name="ck_ops_decision_status",
        ),
    )

    situation = relationship("Situation", back_populates="decisions")
    actions = relationship(
        "AgentAction",
        back_populates="decision",
        cascade="all, delete-orphan",
        order_by="AgentAction.id",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "situation_id": self.situation_id,
            "model": self.model,
            "rationale": self.rationale,
            "confidence": self.confidence,
            "status": self.status,
            "decision": self.decision_json or {},
            "latency_ms": self.latency_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# AgentAction — the actual tool execution, gated by the guardrail layer
# ---------------------------------------------------------------------------
class AgentAction(db.Model):
    __tablename__ = "ops_agent_actions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    decision_id = Column(
        String(36),
        ForeignKey("ops_agent_decisions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool = Column(String(40), nullable=False)  # issue_credit, send_customer_sms…
    args_json = Column(JSON, nullable=True)
    status = Column(String(30), nullable=False, default="pending")
    external_ref = Column(String(255), nullable=True)  # Twilio SID, Stripe id…
    error_message = Column(Text, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','executed','blocked_by_guardrail','failed')",
            name="ck_ops_action_status",
        ),
    )

    decision = relationship("AgentDecision", back_populates="actions")

    def to_dict(self):
        return {
            "id": self.id,
            "decision_id": self.decision_id,
            "tool": self.tool,
            "args": self.args_json or {},
            "status": self.status,
            "external_ref": self.external_ref,
            "error_message": self.error_message,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# EscalationTicket — human queue. For the MVP we do not integrate PagerDuty;
# we simply record the ticket and surface it on the dashboard.
# ---------------------------------------------------------------------------
class EscalationTicket(db.Model):
    __tablename__ = "ops_escalation_tickets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    situation_id = Column(
        String(36),
        ForeignKey("ops_situations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assignee = Column(String(60), nullable=True)
    priority = Column(String(4), nullable=False, default="p2")
    pagerduty_incident = Column(String(120), nullable=True)
    summary_md = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "priority IN ('p0','p1','p2')",
            name="ck_ops_escalation_priority",
        ),
    )

    situation = relationship("Situation", back_populates="escalations")

    def to_dict(self):
        return {
            "id": self.id,
            "situation_id": self.situation_id,
            "assignee": self.assignee,
            "priority": self.priority,
            "pagerduty_incident": self.pagerduty_incident,
            "summary_md": self.summary_md,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution_note": self.resolution_note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


__all__ = [
    "OpsEvent",
    "Situation",
    "AgentDecision",
    "AgentAction",
    "EscalationTicket",
]
