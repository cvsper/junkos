"""Lead-handling state (leads.py).

Leads are derived from where they already live — inbound calls, callback
requests, abandoned web bookings, Meta form submissions, customer texts. This
holds only what those sources cannot know: whether a person has touched the
lead, whether the desk already texted them automatically, and what came of it.

QuoteFollowup is the one piece of scheduled state: a phone quote that did not
turn into a booking gets two texts and then a queue item.
"""
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Integer, Float, Text, UniqueConstraint

from models import db, generate_uuid


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class LeadTouch(db.Model):
    __tablename__ = "lead_touch"
    __table_args__ = (UniqueConstraint("kind", "ref_id", name="uq_lead_touch_kind_ref"),)

    id = Column(String(36), primary_key=True, default=generate_uuid)
    kind = Column(String(24), nullable=False, index=True)
    ref_id = Column(String(64), nullable=False, index=True)
    phone_digits = Column(String(10), nullable=True, index=True)
    source = Column(String(20), nullable=True)

    auto_text_at = Column(DateTime, nullable=True)
    touched_at = Column(DateTime, nullable=True)
    touched_by = Column(String(80), nullable=True)
    outcome = Column(String(20), nullable=True)
    note = Column(String(300), nullable=True)

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class QuoteFollowup(db.Model):
    __tablename__ = "quote_followups"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    phone_digits = Column(String(10), nullable=False, index=True)
    name = Column(String(120), nullable=True)
    quote_total = Column(Float, nullable=True)
    items = Column(Text, nullable=True)
    va_name = Column(String(80), nullable=True)

    step = Column(Integer, nullable=False, default=0)        # 0 scheduled, 1 sent +2h, 2 sent +24h, 3 queued day 3
    next_at = Column(DateTime, nullable=True, index=True)
    last_sent_at = Column(DateTime, nullable=True)
    stopped_at = Column(DateTime, nullable=True)
    stop_reason = Column(String(40), nullable=True)          # booked | stop | replied | manual

    created_at = Column(DateTime, default=_utcnow)
