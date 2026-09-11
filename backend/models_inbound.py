"""Tables for inbound customer calls on the Call Desk (Phase 6).

Imported by server.py before create_all so the tables exist wherever the
desk runs. Kept out of models.py so the desk phases can ship in parallel.

InboundCall      one row per call that hit the desk line (keyed by Twilio
                 CallSid), plus how it was handled and what came of it.
CallbackRequest  a caller asked for a call back; surfaces in the desk inbox
                 until a VA closes it.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from models import db, generate_uuid


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class InboundCall(db.Model):
    __tablename__ = "inbound_calls"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    call_sid = Column(String(64), nullable=True, unique=True, index=True)
    phone_digits = Column(String(10), nullable=False, index=True)
    kind = Column(String(12), nullable=False, default="unknown")     # customer | prospect | unknown
    # How the line handled it: ringing → answered_by_human | to_maya | voicemail | missed
    disposition = Column(String(24), nullable=False, default="ringing")
    # What the VA did with it: none | booked | quoted | callback | not_fit | spam
    outcome = Column(String(16), nullable=False, default="none")
    answered_by = Column(String(80), nullable=True)                  # VA name
    job_id = Column(String(36), nullable=True, index=True)
    quote_total = Column(Float, nullable=True)
    duration = Column(Integer, nullable=True)                         # seconds on the human leg
    va_name = Column(String(80), nullable=True)
    notes = Column(Text, nullable=True)
    in_hours = Column(Integer, nullable=True)                         # 1 inside human hours, 0 outside
    # Lead handling (leads.py): which number they dialled tells us the channel;
    # the outcome is what lets a junk Google lead be disputed for a refund.
    source = Column(String(20), nullable=True, index=True)            # desk | google | meta | maya
    lead_outcome = Column(String(20), nullable=True)                  # booked | not_a_fit | spam | no_answer | quoted
    outcome_note = Column(String(300), nullable=True)
    created_at = Column(DateTime, default=_utcnow, index=True)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "call_sid": self.call_sid,
            "phone_digits": self.phone_digits,
            "kind": self.kind,
            "disposition": self.disposition,
            "outcome": self.outcome,
            "answered_by": self.answered_by,
            "job_id": self.job_id,
            "quote_total": self.quote_total,
            "duration": self.duration,
            "va_name": self.va_name,
            "notes": self.notes,
            "in_hours": bool(self.in_hours) if self.in_hours is not None else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CallbackRequest(db.Model):
    __tablename__ = "callback_requests"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    phone_digits = Column(String(10), nullable=False, index=True)
    name = Column(String(120), nullable=True)
    call_sid = Column(String(64), nullable=True, index=True)
    requested_for = Column(DateTime, nullable=True)                  # naive UTC
    note = Column(Text, nullable=True)
    status = Column(String(12), nullable=False, default="open")      # open | done
    va_name = Column(String(80), nullable=True)
    created_at = Column(DateTime, default=_utcnow, index=True)
    closed_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "phone_digits": self.phone_digits,
            "name": self.name,
            "call_sid": self.call_sid,
            "requested_for": self.requested_for.isoformat() if self.requested_for else None,
            "note": self.note,
            "status": self.status,
            "va_name": self.va_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
