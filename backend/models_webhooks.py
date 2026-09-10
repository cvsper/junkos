"""Provider webhook bookkeeping: one row per (provider, event id) we have seen.

Twilio (MessageSid), Vapi (call id), Meta Lead Ads (leadgen_id) and the portal
Stripe webhook (event id) all retry deliveries. Without a durable record a
retried delivery re-runs side effects (a second quote text, a second Maya
call, a duplicate org activation). ``webhook_guard.record_provider_event``
inserts here under a savepoint; the unique constraint is the deduplication.

Imported for ``db.create_all()`` via ``webhook_guard`` (which every guarded
webhook module imports), the same way ``models_sameday`` is pulled in by
``server.py``. ``migrate.py`` carries the matching DDL for existing databases.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Text, UniqueConstraint

from models import db, generate_uuid


class ProviderEvent(db.Model):
    """A provider-supplied event/message id we have already accepted."""
    __tablename__ = "provider_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_provider_event"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    provider = Column(String(32), nullable=False, index=True)   # twilio | vapi | meta_leads | stripe_portal
    event_id = Column(String(128), nullable=False)
    event_type = Column(String(64), nullable=True)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "provider": self.provider,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
