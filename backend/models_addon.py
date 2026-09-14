"""Extra items found on site: what was added, what it costs, whether the
customer said yes, and how it was billed."""
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, Float, JSON, Index

from models import db, generate_uuid


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class JobAddon(db.Model):
    __tablename__ = "job_addons"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_id = Column(String(36), nullable=False, index=True)
    items = Column(JSON, nullable=True)            # [{category, quantity, name}]
    note = Column(Text, nullable=True)             # what the hauler saw
    amount = Column(Float, nullable=False, default=0.0)     # the difference, all in
    new_total = Column(Float, nullable=True)       # job total if this is approved

    requested_by = Column(String(80), nullable=True)        # hauler name or VA
    requested_by_id = Column(String(36), nullable=True)     # contractor id when we have it

    # pending → approved → charged | failed ; or declined | expired
    status = Column(String(16), nullable=False, default="pending", index=True)
    asked_at = Column(DateTime, nullable=True)
    replied_at = Column(DateTime, nullable=True)
    reply_text = Column(Text, nullable=True)
    approved_via = Column(String(16), nullable=True)        # sms | link | desk

    intent_id = Column(String(255), nullable=True)
    charged_at = Column(DateTime, nullable=True)
    pay_url = Column(Text, nullable=True)                   # when the saved card can't be used
    last_error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=_now, nullable=False, index=True)
    updated_at = Column(DateTime, default=_now, onupdate=_now, nullable=False)

    __table_args__ = (Index("ix_job_addons_job_status", "job_id", "status"),)

    def to_dict(self):
        return {"id": self.id, "job_id": self.job_id, "items": self.items or [], "note": self.note,
                "amount": self.amount, "new_total": self.new_total, "status": self.status,
                "requested_by": self.requested_by, "approved_via": self.approved_via,
                "pay_url": self.pay_url, "last_error": self.last_error,
                "asked_at": self.asked_at.isoformat() + "Z" if self.asked_at else None,
                "replied_at": self.replied_at.isoformat() + "Z" if self.replied_at else None,
                "charged_at": self.charged_at.isoformat() + "Z" if self.charged_at else None,
                "created_at": self.created_at.isoformat() + "Z" if self.created_at else None}
