"""Phase 4 tables: call scorecards for coaching.

Kept out of models.py so the desk's analytics/coaching layer can ship
without touching the shared model file. Imported by server.py before
create_all so the table exists everywhere the app boots.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text, JSON

from models import db, generate_uuid

SCORE_DIMENSIONS = ("opener", "discovery", "objection", "close", "compliance")


class CallScore(db.Model):
    """One rubric score per desk call (keyed by the Twilio CallSid).

    Five dimensions, 0–5 each, total out of 25. `strengths` / `fixes` are
    short lists the VA reads after the call; `reviewed_*` is the manager's
    pass over the queue.
    """
    __tablename__ = "call_scores"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    call_sid = Column(String(64), nullable=False, unique=True, index=True)
    prospect_id = Column(String(36), nullable=True, index=True)
    va_name = Column(String(80), nullable=True, index=True)
    opener = Column(Integer, nullable=False, default=0)
    discovery = Column(Integer, nullable=False, default=0)
    objection = Column(Integer, nullable=False, default=0)
    close = Column(Integer, nullable=False, default=0)
    compliance = Column(Integer, nullable=False, default=0)
    total = Column(Integer, nullable=False, default=0, index=True)
    strengths = Column(JSON, nullable=True)
    fixes = Column(JSON, nullable=True)
    source = Column(String(12), nullable=True)          # claude | heuristic
    line_count = Column(Integer, nullable=True)
    reviewed_by = Column(String(120), nullable=True)
    review_note = Column(Text, nullable=True)
    review_tags = Column(JSON, nullable=True)
    reviewed_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "call_sid": self.call_sid,
            "prospect_id": self.prospect_id,
            "va_name": self.va_name,
            "scores": {d: getattr(self, d) for d in SCORE_DIMENSIONS},
            "total": self.total,
            "strengths": self.strengths or [],
            "fixes": self.fixes or [],
            "source": self.source,
            "line_count": self.line_count,
            "reviewed": self.reviewed_at is not None,
            "reviewed_by": self.reviewed_by,
            "review_note": self.review_note,
            "review_tags": self.review_tags or [],
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
