"""One row per photo quote, so a firm price can be kept, answered, and checked
against what the job actually cost."""
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, Float, Integer, JSON, Boolean, Index

from models import db, generate_uuid


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PhotoQuote(db.Model):
    __tablename__ = "photo_quotes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    ref = Column(String(10), nullable=False, unique=True, index=True)   # short code in the text
    phone_digits = Column(String(10), nullable=False, index=True)
    name = Column(String(120), nullable=True)

    media_urls = Column(JSON, nullable=True)
    body = Column(Text, nullable=True)                 # what they typed with the photo

    items = Column(JSON, nullable=True)                # [{category, quantity, description, confidence}]
    confidence = Column(Float, nullable=True)          # 0-1, the model's own read
    unclear = Column(JSON, nullable=True)              # why a human should look

    addons = Column(JSON, nullable=True)               # {stair_flights, disassembly_items}
    price = Column(Float, nullable=True)               # the firm number we texted
    breakdown = Column(JSON, nullable=True)

    # new → quoted (firm price sent) | needs_human (Tracy prices it) | answered
    # (they told us about stairs/extras and we re-quoted) | booked | expired
    status = Column(String(16), nullable=False, default="new", index=True)
    asked = Column(Boolean, nullable=False, default=False)     # the two questions went out
    answer_text = Column(Text, nullable=True)
    answered_at = Column(DateTime, nullable=True)

    job_id = Column(String(36), nullable=True, index=True)
    final_price = Column(Float, nullable=True)         # what the job actually billed
    drift = Column(Float, nullable=True)               # final - quoted, the honesty check

    seconds_to_quote = Column(Integer, nullable=True)  # the promise is "within minutes"
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now, nullable=False, index=True)
    updated_at = Column(DateTime, default=_now, onupdate=_now, nullable=False)

    __table_args__ = (Index("ix_photo_quotes_phone_created", "phone_digits", "created_at"),)

    def to_dict(self):
        return {
            "id": self.id, "ref": self.ref, "phone_digits": self.phone_digits, "name": self.name,
            "items": self.items or [], "confidence": self.confidence, "unclear": self.unclear or [],
            "addons": self.addons or {}, "price": self.price, "status": self.status,
            "asked": self.asked, "answer_text": self.answer_text,
            "photos": len(self.media_urls or []), "job_id": self.job_id,
            "final_price": self.final_price, "drift": self.drift,
            "seconds_to_quote": self.seconds_to_quote,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
            "sent_at": self.sent_at.isoformat() + "Z" if self.sent_at else None,
        }
