"""Call Desk Phase 5 (Growth) tables.

    IngestLog        — one row per sourced lead the auto-ingest job has seen,
                       so a lead is turned into a prospect exactly once.
    PrequalCall      — every Maya pre-qualification call placed against a
                       prospect, with the disposition Vapi reported back.
    PushSubscription — a VA browser's Web Push subscription (VAPID), one per
                       endpoint; pruned when the push service says it is gone.

Imported by server.py before create_all() so the tables exist on boot.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, JSON, UniqueConstraint

from models import db, generate_uuid


def _now():
    return datetime.now(timezone.utc)


class IngestLog(db.Model):
    """Which OperatorLead / B2BLead rows became call prospects (idempotency key)."""
    __tablename__ = "growth_ingest_log"
    __table_args__ = (UniqueConstraint("lead_kind", "lead_id", name="uq_growth_ingest_lead"),)

    id = Column(String(36), primary_key=True, default=generate_uuid)
    lead_kind = Column(String(16), nullable=False, index=True)      # operator | b2b
    lead_id = Column(String(36), nullable=False, index=True)
    prospect_id = Column(String(36), ForeignKey("call_prospects.id", ondelete="SET NULL"),
                         nullable=True, index=True)
    result = Column(String(16), nullable=True)                      # added | merged | invalid | filtered
    created_at = Column(DateTime, default=_now, index=True)


class PrequalCall(db.Model):
    """One Maya pre-qualification call against a CallProspect."""
    __tablename__ = "growth_prequal_calls"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    prospect_id = Column(String(36), ForeignKey("call_prospects.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    vapi_call_id = Column(String(80), nullable=True, index=True)
    disposition = Column(String(20), nullable=True)                 # pending | warm | cold | no_answer | voicemail
    summary = Column(Text, nullable=True)
    transcript = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now, index=True)
    resolved_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "prospect_id": self.prospect_id,
            "vapi_call_id": self.vapi_call_id,
            "disposition": self.disposition,
            "summary": self.summary,
            "transcript": self.transcript,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class PushSubscription(db.Model):
    """A VA browser's Web Push subscription."""
    __tablename__ = "growth_push_subscriptions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    va_name = Column(String(80), nullable=True, index=True)
    endpoint = Column(String(600), nullable=False, unique=True, index=True)
    keys = Column(JSON, nullable=True)                              # {"p256dh": ..., "auth": ...}
    failures = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=_now, index=True)
    last_used_at = Column(DateTime, nullable=True)

    def subscription_info(self):
        return {"endpoint": self.endpoint, "keys": dict(self.keys or {})}
