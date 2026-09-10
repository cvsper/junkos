"""Same-day dispatch tables: the daily hauler standby roster."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, String, Boolean, DateTime, Date, UniqueConstraint

from models import db, generate_uuid


class HaulerStandby(db.Model):
    """One hauler's answer to the morning 'available for same-day jobs today?' text."""
    __tablename__ = "hauler_standby"
    __table_args__ = (UniqueConstraint("day", "contractor_id", name="uq_standby_day_contractor"),)

    id = Column(String(36), primary_key=True, default=generate_uuid)
    day = Column(Date, nullable=False, index=True)                 # business-local date
    contractor_id = Column(String(36), nullable=False, index=True)
    available = Column(Boolean, nullable=False, default=False)
    asked_at = Column(DateTime, nullable=True)
    replied_at = Column(DateTime, nullable=True)
    via = Column(String(16), nullable=True)                        # sms | desk | app
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {"id": self.id, "day": self.day.isoformat() if self.day else None,
                "contractor_id": self.contractor_id, "available": self.available,
                "asked_at": self.asked_at.isoformat() if self.asked_at else None,
                "replied_at": self.replied_at.isoformat() if self.replied_at else None, "via": self.via}
