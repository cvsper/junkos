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


class CoachingClass(db.Model):
    """One VA's weekly improvement class: a lesson built from her scored
    calls that week, a short quiz, and a reflection. Assigned at the end of
    the week; the desk holds her to it until it's completed."""
    __tablename__ = "coaching_classes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    va_name = Column(String(80), nullable=False, index=True)
    week_start = Column(String(10), nullable=False, index=True)      # ISO Monday, business time
    status = Column(String(12), nullable=False, default="assigned")  # assigned | completed | waived
    calls = Column(Integer, nullable=False, default=0)
    avg_total = Column(Integer, nullable=True)                        # x10 (e.g. 173 == 17.3 / 25)
    dims = Column(JSON, nullable=True)                                # {dim: avg}
    weakest = Column(String(16), nullable=True)
    lesson = Column(JSON, nullable=True)                              # title, summary, went_well, fix, drill, quiz
    source = Column(String(12), nullable=True)                        # claude | heuristic
    answers = Column(JSON, nullable=True)
    quiz_score = Column(Integer, nullable=True)                       # correct answers
    reflection = Column(Text, nullable=True)
    manager_note = Column(Text, nullable=True)
    due_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self, with_answers=False):
        lesson = dict(self.lesson or {})
        if not with_answers:
            lesson["quiz"] = [{k: v for k, v in q.items() if k not in ("answer", "why")} for q in lesson.get("quiz", [])]
        return {
            "id": self.id, "va_name": self.va_name, "week_start": self.week_start, "status": self.status,
            "calls": self.calls, "avg_total": (self.avg_total or 0) / 10.0 if self.avg_total is not None else None,
            "dims": self.dims or {}, "weakest": self.weakest, "lesson": lesson, "source": self.source,
            "quiz_score": self.quiz_score, "quiz_total": len((self.lesson or {}).get("quiz", [])),
            "reflection": self.reflection, "manager_note": self.manager_note,
            "due_at": self.due_at.isoformat() + "Z" if self.due_at else None,
            "completed_at": self.completed_at.isoformat() + "Z" if self.completed_at else None,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
        }
