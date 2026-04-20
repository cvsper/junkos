"""
Partner (Driver) Acquisition Agent — SQLAlchemy models (spec 07 §4).

Isolation rule: models are declared in this separate module so that multiple
parallel build agents can work against the same `models.py` without stomping
on each other's diffs. At import time the model classes register themselves
on the canonical `db.metadata` from `models.py`, so `db.create_all()` (as
invoked by `conftest.py`) picks them up the same as built-in models.

Convention follows the rest of the backend:
  * String(36) UUID primary keys
  * CheckConstraint-based enum columns (never SA Enum types)
  * JSON columns for free-form payloads
  * Append-only audit table for every state transition

Wiring for `migrate.py` lives in `partner_migrations.py` (dict of SQL DDL).
The orchestrator merges those into `migrate.py`'s NEW_TABLES_* lists.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    Boolean,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    CheckConstraint,
    Index,
    UniqueConstraint,
)

# Reuse the canonical metadata + helpers from models.py so create_all() picks
# these up in the same single-metadata world.
from models import db, generate_uuid, utcnow


# ---------------------------------------------------------------------------
# LeadSource — a configured scraper target (per-platform, per-metro).
# ---------------------------------------------------------------------------
class LeadSource(db.Model):
    __tablename__ = "lead_sources"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    platform = Column(String(24), nullable=False)
    search_url = Column(Text, nullable=False)
    metro = Column(String(16), nullable=True, index=True)
    last_scraped_at = Column(DateTime, nullable=True)
    health_status = Column(String(24), nullable=False, default="healthy")
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "platform IN ('fb_marketplace','craigslist','thumbtack','nextdoor','indeed')",
            name="ck_lead_source_platform",
        ),
        CheckConstraint(
            "health_status IN ('healthy','rate_limited','banned')",
            name="ck_lead_source_health",
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "platform": self.platform,
            "search_url": self.search_url,
            "metro": self.metro,
            "last_scraped_at": self.last_scraped_at.isoformat() if self.last_scraped_at else None,
            "health_status": self.health_status,
        }


# ---------------------------------------------------------------------------
# DriverLead — the core row.
# ---------------------------------------------------------------------------
class DriverLead(db.Model):
    __tablename__ = "driver_leads"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    source_id = Column(String(36), ForeignKey("lead_sources.id", ondelete="SET NULL"),
                       nullable=True, index=True)
    external_ref = Column(String(255), nullable=True, index=True)  # e.g. CL post id
    raw_listing_json = Column(JSON, nullable=True)
    name_guess = Column(String(255), nullable=True)
    phone_e164 = Column(String(20), nullable=True, index=True)
    email = Column(String(255), nullable=True)
    metro = Column(String(16), nullable=True, index=True)
    state = Column(String(24), nullable=False, default="NEW", index=True)
    qualification_score = Column(Integer, nullable=True)  # 0-100 int for simplicity
    assigned_agent_run_id = Column(String(36), nullable=True)
    dedupe_hash = Column(String(64), nullable=False, index=True)
    opted_out = Column(Boolean, nullable=False, default=False)
    platform = Column(String(24), nullable=True)  # denormalized for fast filters
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("dedupe_hash", name="uq_driver_leads_dedupe_hash"),
        CheckConstraint(
            "state IN ('NEW','OUTREACHED','RESPONDED','QUALIFIED','ONBOARDING','ACTIVE','REJECTED','HUMAN_REVIEW')",
            name="ck_driver_lead_state",
        ),
        Index("ix_driver_leads_state_metro", "state", "metro"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "source_id": self.source_id,
            "external_ref": self.external_ref,
            "name_guess": self.name_guess,
            "phone_e164": self.phone_e164,
            "email": self.email,
            "metro": self.metro,
            "platform": self.platform,
            "state": self.state,
            "qualification_score": self.qualification_score,
            "opted_out": self.opted_out,
            "dedupe_hash": self.dedupe_hash,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ---------------------------------------------------------------------------
# OutreachAttempt — one row per outbound / inbound message.
# ---------------------------------------------------------------------------
class OutreachAttempt(db.Model):
    __tablename__ = "outreach_attempts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    lead_id = Column(String(36), ForeignKey("driver_leads.id", ondelete="CASCADE"),
                    nullable=False, index=True)
    channel = Column(String(16), nullable=False)
    direction = Column(String(4), nullable=False)
    body = Column(Text, nullable=True)
    claude_prompt_hash = Column(String(64), nullable=True)
    response_latency_sec = Column(Integer, nullable=True)
    sentiment = Column(String(16), nullable=True)
    twilio_sid = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    __table_args__ = (
        CheckConstraint(
            "channel IN ('sms','email','fb_msg')",
            name="ck_outreach_channel",
        ),
        CheckConstraint(
            "direction IN ('out','in')",
            name="ck_outreach_direction",
        ),
        CheckConstraint(
            "sentiment IS NULL OR sentiment IN ('positive','neutral','negative','red_flag')",
            name="ck_outreach_sentiment",
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "lead_id": self.lead_id,
            "channel": self.channel,
            "direction": self.direction,
            "body": self.body,
            "sentiment": self.sentiment,
            "twilio_sid": self.twilio_sid,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Qualification — captured via manual Retool form in MVP.
# ---------------------------------------------------------------------------
class Qualification(db.Model):
    __tablename__ = "driver_qualifications"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    lead_id = Column(String(36), ForeignKey("driver_leads.id", ondelete="CASCADE"),
                    nullable=False, index=True)
    has_truck = Column(Boolean, nullable=True)
    truck_type = Column(String(24), nullable=True)
    has_insurance = Column(Boolean, nullable=True)
    has_license = Column(Boolean, nullable=True)
    past_hauling_years = Column(Integer, nullable=True)
    self_reported_availability_hours = Column(Integer, nullable=True)
    consent_checkr = Column(Boolean, nullable=False, default=False)
    consent_sms = Column(Boolean, nullable=False, default=False)
    ssn_last_4 = Column(String(8), nullable=True)  # stored only after secure link
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "truck_type IS NULL OR truck_type IN ('pickup','box','flatbed','van','other')",
            name="ck_qualification_truck_type",
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "lead_id": self.lead_id,
            "has_truck": self.has_truck,
            "truck_type": self.truck_type,
            "has_insurance": self.has_insurance,
            "has_license": self.has_license,
            "past_hauling_years": self.past_hauling_years,
            "self_reported_availability_hours": self.self_reported_availability_hours,
            "consent_checkr": self.consent_checkr,
            "consent_sms": self.consent_sms,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


# ---------------------------------------------------------------------------
# BackgroundCheck — manually populated after Ops runs Checkr by hand in MVP.
# ---------------------------------------------------------------------------
class BackgroundCheck(db.Model):
    __tablename__ = "background_checks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    lead_id = Column(String(36), ForeignKey("driver_leads.id", ondelete="CASCADE"),
                    nullable=False, index=True)
    checkr_candidate_id = Column(String(128), nullable=True)
    checkr_report_id = Column(String(128), nullable=True)
    status = Column(String(16), nullable=False, default="pending")
    mvr_status = Column(String(32), nullable=True)
    criminal_status = Column(String(32), nullable=True)
    adverse_action_sent_at = Column(DateTime, nullable=True)
    adverse_action_due_at = Column(DateTime, nullable=True)  # FCRA 5 business-day window
    raw_webhook_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','clear','consider','suspended')",
            name="ck_bg_check_status",
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "lead_id": self.lead_id,
            "checkr_candidate_id": self.checkr_candidate_id,
            "checkr_report_id": self.checkr_report_id,
            "status": self.status,
            "mvr_status": self.mvr_status,
            "criminal_status": self.criminal_status,
            "adverse_action_sent_at": self.adverse_action_sent_at.isoformat() if self.adverse_action_sent_at else None,
            "adverse_action_due_at": self.adverse_action_due_at.isoformat() if self.adverse_action_due_at else None,
        }


# ---------------------------------------------------------------------------
# OnboardingStep — one row per manual step completion in MVP.
# ---------------------------------------------------------------------------
class OnboardingStep(db.Model):
    __tablename__ = "driver_onboarding_steps"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    lead_id = Column(String(36), ForeignKey("driver_leads.id", ondelete="CASCADE"),
                    nullable=False, index=True)
    step = Column(String(32), nullable=False)
    completed_at = Column(DateTime, nullable=True)
    payload_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "step IN ('stripe_link_sent','stripe_kyc_done','app_installed','sim_dispatch_done')",
            name="ck_onboarding_step",
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "lead_id": self.lead_id,
            "step": self.step,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


# ---------------------------------------------------------------------------
# DriverOnboardingAudit — append-only log of every state transition + action.
# ---------------------------------------------------------------------------
class DriverOnboardingAudit(db.Model):
    __tablename__ = "driver_onboarding_audits"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    lead_id = Column(String(36), ForeignKey("driver_leads.id", ondelete="CASCADE"),
                    nullable=False, index=True)
    actor = Column(String(64), nullable=False)  # 'system', 'ops', 'claude_outreach_v1'
    action = Column(String(64), nullable=False)
    before_state = Column(String(24), nullable=True)
    after_state = Column(String(24), nullable=True)
    payload_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "lead_id": self.lead_id,
            "actor": self.actor,
            "action": self.action,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
