"""Ownership state for the work queue.

The desk already detects trouble: stranded jobs, unpaid haulers, missed calls,
callbacks coming due. What it could not do was say who is dealing with any of
it, which is why a $307 job sat assigned for 18 days and a hauler went unpaid
without anyone noticing.

The items themselves stay where they live — a Job is the source of truth about
a job. This table holds only the part the source cannot know: who picked it
up, whether it was dealt with, and when to stop asking. One row per
(kind, ref_id), created lazily the first time a human touches an item.
"""
from datetime import datetime, timezone

from models import db, generate_uuid

from sqlalchemy import Column, String, DateTime, Text, UniqueConstraint, Index


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class WorkItemState(db.Model):
    __tablename__ = "work_item_state"
    __table_args__ = (
        UniqueConstraint("kind", "ref_id", name="uq_work_item_kind_ref"),
        Index("ix_work_item_open", "done_at", "snoozed_until"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    kind = Column(String(32), nullable=False, index=True)
    ref_id = Column(String(64), nullable=False, index=True)

    claimed_by = Column(String(80), nullable=True)
    claimed_at = Column(DateTime, nullable=True)
    snoozed_until = Column(DateTime, nullable=True)
    done_at = Column(DateTime, nullable=True)
    done_by = Column(String(80), nullable=True)
    note = Column(Text, nullable=True)

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    def to_dict(self):
        return {
            "claimed_by": self.claimed_by,
            "claimed_at": (self.claimed_at.isoformat() + "Z") if self.claimed_at else None,
            "snoozed_until": (self.snoozed_until.isoformat() + "Z") if self.snoozed_until else None,
            "done_at": (self.done_at.isoformat() + "Z") if self.done_at else None,
            "done_by": self.done_by,
            "note": self.note,
        }
