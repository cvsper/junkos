"""Compliance tables for the Call Desk (Phase 2).

DoNotCall — the desk's opt-out registry. One row per 10-digit US number; the
source records how it got there:

  sms_stop      they texted STOP (or a sibling keyword) to the desk line
  call_request  they asked on a call — the VA pressed "They asked not to be called"
  manual        a manager added it by hand
  import        came in on a suppression list
  erase         a data-erasure request (the number stays blocked so a re-import
                can't quietly resurrect the record)

Import, texting and dialing all consult this table before touching a number
(see compliance.py: filter_rows, text_allowed, call_allowed).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Text

from models import db, generate_uuid

DNC_SOURCES = ("sms_stop", "call_request", "manual", "import", "erase")


class DoNotCall(db.Model):
    __tablename__ = "do_not_call"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    phone_digits = Column(String(10), nullable=False, unique=True, index=True)
    source = Column(String(20), nullable=False, default="manual")
    note = Column(Text, nullable=True)
    created_by = Column(String(120), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "phone_digits": self.phone_digits,
            "source": self.source,
            "note": self.note,
            "created_by": self.created_by,
            "since": self.created_at.isoformat() if self.created_at else None,
        }
