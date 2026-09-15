"""Thumbtack leads and the messages under them, as Thumbtack posts them to
our webhook. One row per lead; customer messages append to `messages`."""
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, Float, Boolean, JSON, Index

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
    status = Column(String(24), nullable=False, default="new")   # new | replied | booked | lost | test
    # is this a lead we could actually do? Thumbtack charges either way, so the
    # ones we can't serve are money to claw back by fixing their targeting.
    serviceable = Column(Boolean, nullable=True, index=True)
    service_note = Column(String(200), nullable=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    county = Column(String(40), nullable=True)
    job_id = Column(String(36), nullable=True, index=True)        # it turned into work
    booked_value = Column(Float, nullable=True)
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
            "serviceable": self.serviceable, "service_note": self.service_note,
            "county": self.county, "job_id": self.job_id, "booked_value": self.booked_value,
            "lead_price": self.lead_price,
            "text_sent_at": self.text_sent_at.isoformat() + "Z" if self.text_sent_at else None,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
        }


class ThumbtackReview(db.Model):
    """A review Thumbtack told us about — the only public proof we're building
    while the Google profile is unclaimed."""
    __tablename__ = "thumbtack_reviews"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    review_id = Column(String(80), nullable=True, unique=True, index=True)
    lead_id = Column(String(80), nullable=True, index=True)
    rating = Column(Float, nullable=True)
    text = Column(Text, nullable=True)
    reviewer = Column(String(120), nullable=True)
    raw = Column(JSON, nullable=True)
    asked_for_google_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now, nullable=False, index=True)

    def to_dict(self):
        return {"id": self.id, "review_id": self.review_id, "lead_id": self.lead_id,
                "rating": self.rating, "text": self.text, "reviewer": self.reviewer,
                "created_at": self.created_at.isoformat() + "Z" if self.created_at else None}
