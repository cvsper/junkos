"""Thumbtack leads and the messages under them, as Thumbtack posts them to
our webhook. One row per lead; customer messages append to `messages`."""
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, Float, JSON, Index

from models import db, generate_uuid


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ThumbtackLead(db.Model):
    __tablename__ = "thumbtack_leads"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    lead_id = Column(String(80), nullable=True, index=True)      # Thumbtack's leadID / negotiationID
    business_id = Column(String(80), nullable=True)
    lead_type = Column(String(40), nullable=True)
    lead_price = Column(Float, nullable=True)
    customer_id = Column(String(80), nullable=True)
    customer_name = Column(String(160), nullable=True)
    phone = Column(String(40), nullable=True)
    phone_digits = Column(String(10), nullable=True, index=True)
    email = Column(String(254), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(80), nullable=True)
    state = Column(String(8), nullable=True)
    zip = Column(String(12), nullable=True)
    category = Column(String(120), nullable=True)
    title = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    schedule = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)        # Thumbtack's question/answer pairs
    attachments = Column(JSON, nullable=True)    # [{url, fileName, mimeType}]
    messages = Column(JSON, nullable=True)       # [{at, from, text}]
    raw = Column(JSON, nullable=True)            # the first payload, untouched
    status = Column(String(24), nullable=False, default="new")   # new | replied | booked | lost
    text_sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now, nullable=False, index=True)
    updated_at = Column(DateTime, default=_now, onupdate=_now, nullable=False)

    __table_args__ = (Index("ix_thumbtack_leads_lead_id_kind", "lead_id"),)

    def to_dict(self):
        return {
            "id": self.id, "lead_id": self.lead_id, "lead_type": self.lead_type, "lead_price": self.lead_price,
            "customer_name": self.customer_name, "phone": self.phone, "email": self.email,
            "address": self.address, "city": self.city, "state": self.state, "zip": self.zip,
            "category": self.category, "title": self.title, "description": self.description,
            "schedule": self.schedule, "details": self.details or [], "attachments": self.attachments or [],
            "messages": self.messages or [], "status": self.status,
            "text_sent_at": self.text_sent_at.isoformat() + "Z" if self.text_sent_at else None,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
        }
