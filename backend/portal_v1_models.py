"""
B2B Commercial Portal — v1 expansion models (Spec 04 §9).

Self-contained module.  Ships the new persistent entities added in the
2-week v1 scope without touching `models.py` (which is being edited by
other build agents in parallel).

Added here:
  * Unit                      — subdivision of a PortalProperty
  * RecurringSchedule         — driver for `portal_recurring.py`
  * PortalV1AuditLog          — richer audit trail w/ actor_member_id
                                (complements, does not replace, the
                                existing PortalAuditLog)

Conventions match models.py:
  * String(36) UUID PKs via `generate_uuid`
  * CheckConstraint for enums (we never use the Enum type — SQLite chokes
    on it across Flask-SQLAlchemy versions)
  * `from models import db` — single shared MetaData so create_all works
  * `utcnow` as default timestamp
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, ForeignKey, JSON, Text,
    CheckConstraint, Index,
)

from models import db, generate_uuid


def _utcnow():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Unit — a leasable/serviceable subdivision of a PortalProperty.
# Jobs are optionally stamped with a unit_id for per-unit billing / audit.
# ---------------------------------------------------------------------------
class PortalUnit(db.Model):
    __tablename__ = "portal_units"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    property_id = Column(
        String(36),
        ForeignKey("portal_properties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    unit_number = Column(String(40), nullable=False)
    sqft = Column(Integer, nullable=True)
    access_notes = Column(Text, nullable=True)
    status = Column(String(16), nullable=False, default="active")
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('active','inactive')",
            name="ck_portal_unit_status",
        ),
        Index(
            "ix_portal_unit_property_number",
            "property_id", "unit_number",
            unique=True,
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "property_id": self.property_id,
            "unit_number": self.unit_number,
            "sqft": self.sqft,
            "access_notes": self.access_notes,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# RecurringSchedule — generates Jobs on a cadence.  Designed so a Celery
# Beat task can invoke `generate_jobs_for_due_schedules(now)` every 5 min.
# ---------------------------------------------------------------------------
class PortalRecurringSchedule(db.Model):
    __tablename__ = "portal_recurring_schedules"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    org_id = Column(
        String(36),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    property_id = Column(
        String(36),
        ForeignKey("portal_properties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    unit_id = Column(
        String(36),
        ForeignKey("portal_units.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    cadence = Column(String(12), nullable=False)  # weekly | biweekly | monthly
    day_of_week = Column(Integer, nullable=True)  # 0=Mon .. 6=Sun
    day_of_month = Column(Integer, nullable=True)  # 1-31
    next_run_at = Column(DateTime, nullable=False, index=True)
    active = Column(Boolean, nullable=False, default=True)
    paused_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "cadence IN ('weekly','biweekly','monthly')",
            name="ck_recurring_cadence",
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "org_id": self.org_id,
            "property_id": self.property_id,
            "unit_id": self.unit_id,
            "cadence": self.cadence,
            "day_of_week": self.day_of_week,
            "day_of_month": self.day_of_month,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "active": self.active,
            "paused_at": self.paused_at.isoformat() if self.paused_at else None,
        }


# ---------------------------------------------------------------------------
# PortalV1AuditLog — v1 adds actor_member_id (not just user_id) so we can
# attribute a write to the specific membership that performed it.
# Distinct table from the MVP `portal_audit_logs` to avoid schema conflict.
# ---------------------------------------------------------------------------
class PortalV1AuditLog(db.Model):
    __tablename__ = "portal_v1_audit_log"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    org_id = Column(String(36), nullable=False, index=True)
    actor_member_id = Column(String(36), nullable=True, index=True)
    entity_type = Column(String(40), nullable=False)
    entity_id = Column(String(36), nullable=True, index=True)
    action = Column(String(20), nullable=False)  # create | update | delete
    before_json = Column(JSON, nullable=True)
    after_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_utcnow, index=True)

    __table_args__ = (
        CheckConstraint(
            "action IN ('create','update','delete')",
            name="ck_portal_v1_audit_action",
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "org_id": self.org_id,
            "actor_member_id": self.actor_member_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "action": self.action,
            "before_json": self.before_json,
            "after_json": self.after_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
