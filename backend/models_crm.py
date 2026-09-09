"""CRM tables behind the Call Desk (Phase 3): pipeline stages, tags, claims,
accounts + contacts.

Imported by server.py so `create_all` builds these alongside the rest of the
schema. Every table hangs off CallProspect by id; nothing here changes the
prospect row itself.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import (Column, String, Text, DateTime, ForeignKey, Index,
                        UniqueConstraint)

from models import db, generate_uuid


def _utcnow():
    return datetime.now(timezone.utc)


STAGES = ("new", "contacted", "engaged", "qualified", "won", "lost", "nurture")
# Forward-only stages; a voicemail after a real conversation doesn't demote
# the prospect. Terminal/lateral stages (won, lost, nurture) always apply.
STAGE_RANK = {"new": 0, "contacted": 1, "engaged": 2, "qualified": 3}
ACCOUNT_KINDS = ("property_mgmt", "storage", "estate", "realtor", "hauler", "other")


class ProspectStage(db.Model):
    """One stage entry per transition — the newest row is the current stage."""
    __tablename__ = "prospect_stages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    prospect_id = Column(String(36), ForeignKey("call_prospects.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    stage = Column(String(16), nullable=False, index=True)
    entered_at = Column(DateTime, nullable=False, default=_utcnow, index=True)
    by = Column(String(80), nullable=True)

    def to_dict(self):
        return {"stage": self.stage, "by": self.by,
                "entered_at": self.entered_at.isoformat() if self.entered_at else None}


class ProspectTag(db.Model):
    __tablename__ = "prospect_tags"
    __table_args__ = (UniqueConstraint("prospect_id", "tag", name="uq_prospect_tag"),)

    id = Column(String(36), primary_key=True, default=generate_uuid)
    prospect_id = Column(String(36), ForeignKey("call_prospects.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    tag = Column(String(40), nullable=False, index=True)
    by = Column(String(80), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class ProspectClaim(db.Model):
    """Who is working a card right now. One row per prospect; expired rows are
    treated as absent and overwritten on the next claim."""
    __tablename__ = "prospect_claims"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    prospect_id = Column(String(36), ForeignKey("call_prospects.id", ondelete="CASCADE"),
                         nullable=False, unique=True, index=True)
    va_name = Column(String(80), nullable=False, index=True)
    claimed_at = Column(DateTime, nullable=False, default=_utcnow)
    expires_at = Column(DateTime, nullable=False, index=True)

    def to_dict(self):
        return {"prospect_id": self.prospect_id, "claimed_by": self.va_name,
                "claimed_at": self.claimed_at.isoformat() if self.claimed_at else None,
                "claimed_until": self.expires_at.isoformat() if self.expires_at else None}


_SUFFIX_RE = re.compile(r"\b(llc|inc|incorporated|co|corp|corporation|ltd|limited|company|group|the)\b")
_NONWORD_RE = re.compile(r"[^a-z0-9 ]+")


def normalize_account_name(name):
    """'The Palm Coast Property Group, LLC' → 'palm coast property'."""
    s = (name or "").lower()
    s = _NONWORD_RE.sub(" ", s)
    s = _SUFFIX_RE.sub(" ", s)
    return " ".join(s.split())[:200]


class Account(db.Model):
    """A business we may have several contacts (and prospects) at."""
    __tablename__ = "crm_accounts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(200), nullable=False)
    norm_name = Column(String(200), nullable=False, index=True)
    domain = Column(String(120), nullable=True)
    city = Column(String(80), nullable=True)
    kind = Column(String(20), nullable=False, default="other")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    contacts = db.relationship("AccountContact", backref="account", lazy="select",
                               cascade="all, delete-orphan")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "domain": self.domain, "city": self.city,
                "kind": self.kind, "notes": self.notes,
                "created_at": self.created_at.isoformat() if self.created_at else None}


class AccountContact(db.Model):
    __tablename__ = "crm_account_contacts"
    __table_args__ = (Index("ix_crm_contact_phone", "phone_digits"),)

    id = Column(String(36), primary_key=True, default=generate_uuid)
    account_id = Column(String(36), ForeignKey("crm_accounts.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    name = Column(String(120), nullable=True)
    phone_digits = Column(String(10), nullable=True)
    email = Column(String(254), nullable=True)
    title = Column(String(80), nullable=True)
    prospect_id = Column(String(36), ForeignKey("call_prospects.id", ondelete="SET NULL"),
                         nullable=True, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    def to_dict(self):
        return {"id": self.id, "account_id": self.account_id, "name": self.name,
                "phone_digits": self.phone_digits, "email": self.email, "title": self.title,
                "prospect_id": self.prospect_id}
