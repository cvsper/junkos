"""
Umuve SQLAlchemy Models
All database entities for the on-demand junk removal marketplace.
"""

import uuid
import string
import random
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import (
    Column, String, Float, Boolean, Integer, Text, DateTime, ForeignKey, JSON,
    CheckConstraint, Index
)
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


def generate_uuid():
    return str(uuid.uuid4())


def utcnow():
    return datetime.now(timezone.utc)


def generate_referral_code():
    """Generate a unique 8-character alphanumeric referral code."""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=8))


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------
class User(db.Model):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=True, index=True)
    phone = Column(String(20), unique=True, nullable=True, index=True)
    name = Column(String(255), nullable=True)
    password_hash = Column(String(255), nullable=True)
    role = Column(String(20), nullable=False, default="customer")
    avatar_url = Column(Text, nullable=True)
    stripe_customer_id = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default="active")
    apple_id = Column(String(255), nullable=True, unique=True)
    referral_code = Column(String(8), unique=True, nullable=True, index=True, default=generate_referral_code)

    winback_called = Column(Boolean, default=False)
    last_winback_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    contractor_profile = relationship("Contractor", back_populates="user", uselist=False, lazy="joined")
    referrals_made = relationship("Referral", foreign_keys="Referral.referrer_id", back_populates="referrer", lazy="dynamic")
    referral_received = relationship("Referral", foreign_keys="Referral.referee_id", back_populates="referee", uselist=False, lazy="joined")
    notifications = relationship("Notification", back_populates="user", lazy="dynamic")
    device_tokens = relationship("DeviceToken", back_populates="user", lazy="dynamic", cascade="all, delete-orphan")
    ratings_given = relationship("Rating", foreign_keys="Rating.from_user_id", back_populates="from_user", lazy="dynamic")
    ratings_received = relationship("Rating", foreign_keys="Rating.to_user_id", back_populates="to_user", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify password with Werkzeug and legacy sha256 fallback."""
        if not self.password_hash:
            return False
        
        # Werkzeug hash check
        if ":" in self.password_hash:
            return check_password_hash(self.password_hash, password)
        
        # Legacy sha256 fallback
        import hashlib
        import secrets
        legacy_hash = hashlib.sha256(password.encode()).hexdigest()
        return secrets.compare_digest(self.password_hash, legacy_hash)

    def to_dict(self, include_private=False):
        data = {
            "id": self.id,
            "email": self.email,
            "phone": self.phone,
            "name": self.name,
            "role": self.role,
            "avatar_url": self.avatar_url,
            "status": self.status,
            "referral_code": self.referral_code,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_private:
            data["stripe_customer_id"] = self.stripe_customer_id
        return data


# ---------------------------------------------------------------------------
# Contractor
# ---------------------------------------------------------------------------
class Contractor(db.Model):
    __tablename__ = "contractors"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    license_url = Column(Text, nullable=True)
    insurance_url = Column(Text, nullable=True)
    truck_photos = Column(JSON, nullable=True, default=list)
    truck_type = Column(String(100), nullable=True)
    truck_capacity = Column(Float, nullable=True)
    stripe_connect_id = Column(String(255), nullable=True)
    is_online = Column(Boolean, default=False)
    current_lat = Column(Float, nullable=True)
    current_lng = Column(Float, nullable=True)
    avg_rating = Column(Float, default=0.0)
    total_jobs = Column(Integer, default=0)
    approval_status = Column(String(20), default="pending")
    availability_schedule = Column(JSON, nullable=True, default=dict)

    # Onboarding fields
    onboarding_status = Column(String(20), default="pending")  # pending, documents_submitted, under_review, approved, rejected
    background_check_status = Column(String(20), default="not_started")  # not_started, pending, passed, failed
    insurance_document_url = Column(String(500), nullable=True)
    drivers_license_url = Column(String(500), nullable=True)
    vehicle_registration_url = Column(String(500), nullable=True)
    insurance_expiry = Column(DateTime, nullable=True)
    license_expiry = Column(DateTime, nullable=True)
    onboarding_completed_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # Automated document verification summary (detail rows live in
    # OperatorDocumentVerification). Status: not_checked | verifying | passed |
    # flagged | failed. `vehicle_registration_expiry` completes the trio so the
    # daily expiry sweep can suspend on a lapsed registration too.
    documents_verification_status = Column(String(20), default="not_checked")
    documents_verified_at = Column(DateTime, nullable=True)
    vehicle_registration_expiry = Column(DateTime, nullable=True)

    # Operator fields
    is_operator = Column(Boolean, default=False)
    operator_id = Column(String(36), ForeignKey("contractors.id", ondelete="SET NULL"), nullable=True, index=True)
    operator_commission_rate = Column(Float, default=0.15)

    # Concierge (shadow) hauler: registered by admin with just a name+phone,
    # works jobs through SMS offers + the token-gated /w/ console — no app,
    # no login, no Stripe. Excluded from app auto-assign (they can't act on
    # it); reached via the broadcast offer wave. Payouts settle by hand.
    is_concierge = Column(Boolean, default=False)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="contractor_profile")
    jobs = relationship("Job", back_populates="driver", lazy="dynamic", foreign_keys="Job.driver_id")
    # Self-referential: operator -> fleet contractors
    operator = relationship("Contractor", remote_side="Contractor.id", backref="fleet_contractors", foreign_keys=[operator_id])

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user": self.user.to_dict() if self.user else None,
            "license_url": self.license_url,
            "insurance_url": self.insurance_url,
            "truck_photos": self.truck_photos or [],
            "truck_type": self.truck_type,
            "truck_capacity": self.truck_capacity,
            "stripe_connect_id": self.stripe_connect_id,
            "is_online": self.is_online,
            "current_lat": self.current_lat,
            "current_lng": self.current_lng,
            "avg_rating": self.avg_rating,
            "total_jobs": self.total_jobs,
            "approval_status": self.approval_status,
            "availability_schedule": self.availability_schedule or {},
            "onboarding_status": self.onboarding_status or "pending",
            "background_check_status": self.background_check_status or "not_started",
            "insurance_document_url": self.insurance_document_url,
            "drivers_license_url": self.drivers_license_url,
            "vehicle_registration_url": self.vehicle_registration_url,
            "insurance_expiry": self.insurance_expiry.isoformat() if self.insurance_expiry else None,
            "license_expiry": self.license_expiry.isoformat() if self.license_expiry else None,
            "vehicle_registration_expiry": self.vehicle_registration_expiry.isoformat() if self.vehicle_registration_expiry else None,
            "documents_verification_status": self.documents_verification_status or "not_checked",
            "documents_verified_at": self.documents_verified_at.isoformat() if self.documents_verified_at else None,
            "onboarding_completed_at": self.onboarding_completed_at.isoformat() if self.onboarding_completed_at else None,
            "rejection_reason": self.rejection_reason,
            "is_operator": self.is_operator or False,
            "operator_id": self.operator_id,
            "operator_commission_rate": self.operator_commission_rate or 0.15,
            "is_concierge": self.is_concierge or False,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ---------------------------------------------------------------------------
# OperatorDocumentVerification
#
# One row per (contractor, doc_type) automated verification run. Stores the
# vision-model's extracted fields, the rule-engine verdict, and a short raw
# excerpt for audit. Keeps history (re-runs append/update by doc_type), so an
# admin can always see why a document passed or got flagged.
# ---------------------------------------------------------------------------
class OperatorDocumentVerification(db.Model):
    __tablename__ = "operator_document_verifications"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    contractor_id = Column(
        String(36),
        ForeignKey("contractors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # insurance | drivers_license | vehicle_registration
    doc_type = Column(String(32), nullable=False, index=True)
    document_url = Column(String(500), nullable=True)

    # verified | needs_review | rejected | error | pending
    status = Column(String(20), nullable=False, default="pending")
    reasons = Column(JSON, nullable=True, default=list)   # list[str] human-readable findings
    extracted = Column(JSON, nullable=True, default=dict)  # {full_name, expiration_date, policy_number, ...}
    expiry_date = Column(DateTime, nullable=True)
    name_match_score = Column(Float, nullable=True)        # 0..1 vs applicant name
    confidence = Column(Float, nullable=True)              # 0..1 model legibility/confidence
    engine = Column(String(48), nullable=True)             # e.g. "anthropic:claude-haiku-4-5"
    raw_excerpt = Column(Text, nullable=True)              # trimmed raw model output (audit)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        db.UniqueConstraint("contractor_id", "doc_type", name="uq_contractor_doc_type"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "contractor_id": self.contractor_id,
            "doc_type": self.doc_type,
            "document_url": self.document_url,
            "status": self.status,
            "reasons": self.reasons or [],
            "extracted": self.extracted or {},
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "name_match_score": self.name_match_score,
            "confidence": self.confidence,
            "engine": self.engine,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ---------------------------------------------------------------------------
# PromoCode
# ---------------------------------------------------------------------------
class PromoCode(db.Model):
    __tablename__ = "promo_codes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    code = Column(String(50), unique=True, nullable=False, index=True)
    discount_type = Column(String(20), nullable=False)  # "percentage" or "fixed"
    discount_value = Column(Float, nullable=False)  # e.g., 20 for 20% or 20 for $20
    min_order_amount = Column(Float, default=0.0)
    max_discount = Column(Float, nullable=True)  # cap for percentage discounts
    max_uses = Column(Integer, nullable=True)  # null = unlimited
    use_count = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    created_by = Column(String(36), nullable=True)  # admin user_id

    __table_args__ = (
        CheckConstraint(
            "discount_type IN ('percentage', 'fixed')",
            name="ck_promo_discount_type",
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "discount_type": self.discount_type,
            "discount_value": self.discount_value,
            "min_order_amount": self.min_order_amount or 0.0,
            "max_discount": self.max_discount,
            "max_uses": self.max_uses,
            "use_count": self.use_count or 0,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
        }


# ---------------------------------------------------------------------------
# Job
# ---------------------------------------------------------------------------
class Job(db.Model):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    customer_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    driver_id = Column(String(36), ForeignKey("contractors.id", ondelete="SET NULL"), nullable=True, index=True)
    operator_id = Column(String(36), ForeignKey("contractors.id", ondelete="SET NULL"), nullable=True, index=True)
    # B2B Commercial Portal (spec 04): jobs booked via portal.goumuve.com
    # are stamped with the originating org. NULL = residential one-off.
    org_id = Column(String(36), ForeignKey("orgs.id", ondelete="SET NULL"),
                    nullable=True, index=True)

    status = Column(String(30), nullable=False, default="pending")
    delegated_at = Column(DateTime, nullable=True)

    address = Column(Text, nullable=False)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)

    items = Column(JSON, nullable=True, default=list)
    volume_estimate = Column(Float, nullable=True)
    photos = Column(JSON, nullable=True, default=list)
    before_photos = Column(JSON, nullable=True, default=list)
    after_photos = Column(JSON, nullable=True, default=list)
    proof_submitted_at = Column(DateTime, nullable=True)

    scheduled_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    base_price = Column(Float, default=0.0)
    item_total = Column(Float, default=0.0)
    volume_price = Column(Float, default=0.0)
    service_fee = Column(Float, default=0.0)
    surge_multiplier = Column(Float, default=1.0)
    total_price = Column(Float, default=0.0)

    promo_code_id = Column(String(36), ForeignKey("promo_codes.id", ondelete="SET NULL"), nullable=True)
    discount_amount = Column(Float, default=0.0)

    notes = Column(Text, nullable=True)
    lead_source = Column(String(50), nullable=True, default=None)  # google_ads, craigslist, facebook, nextdoor, referral, organic, direct, google_business, etc.
    confirmation_code = Column(String(8), unique=True, nullable=True, index=True, default=generate_referral_code)

    cancelled_at = Column(DateTime, nullable=True)
    cancellation_fee = Column(Float, default=0.0)
    rescheduled_count = Column(Integer, default=0)

    reminder_sent = Column(Boolean, default=False)
    reminder_call_id = Column(String(255), nullable=True)

    review_requested = Column(Boolean, default=False)
    review_call_id = Column(String(255), nullable=True)

    # No-show watchdog flags — set when each alert fires so we don't double-fire
    noshow_t30_alerted = Column(Boolean, default=False)
    noshow_late_alerted = Column(Boolean, default=False)

    volume_adjustment_proposed = Column(Boolean, default=False)
    adjusted_volume = Column(Float, nullable=True)
    adjusted_price = Column(Float, nullable=True)

    drip_stage = Column(Integer, default=0)  # 0=none, 1=reminder, 2=incentive, 3=final

    # --- Disposition / impact (Rescue Engine v1) ---
    # Customer's preference at booking; driver's marked outcome at completion.
    # Deliberately per-job and lightweight — the advanced per-item resale/
    # donation-receipt schema (ItemValuation/ResaleListing/...) is a separate,
    # partner-dependent feature that stays dormant until real partners exist.
    disposition_preference = Column(String(20), default="best")   # dispose|recycle|donate|best
    disposition_outcome = Column(String(20), nullable=True)       # donated|recycled|disposed|mixed|could_not
    disposition_notes = Column(Text, nullable=True)
    impact_summary = Column(Text, nullable=True)                  # cached customer-facing receipt copy

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    customer = relationship("User", foreign_keys=[customer_id], backref="customer_jobs")
    driver = relationship("Contractor", foreign_keys=[driver_id], back_populates="jobs")
    operator_rel = relationship("Contractor", foreign_keys=[operator_id], backref="operator_jobs")
    payment = relationship("Payment", back_populates="job", uselist=False, lazy="joined")
    rating = relationship("Rating", back_populates="job", uselist=False, lazy="joined")
    promo_code = relationship("PromoCode", foreign_keys=[promo_code_id], backref="jobs")

    __table_args__ = (
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_location", "lat", "lng"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "driver_id": self.driver_id,
            "operator_id": self.operator_id,
            "status": self.status,
            "delegated_at": self.delegated_at.isoformat() if self.delegated_at else None,
            "address": self.address,
            "lat": self.lat,
            "lng": self.lng,
            "items": self.items or [],
            "volume_estimate": self.volume_estimate,
            "photos": self.photos or [],
            "before_photos": self.before_photos or [],
            "after_photos": self.after_photos or [],
            "proof_submitted_at": self.proof_submitted_at.isoformat() if self.proof_submitted_at else None,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "base_price": self.base_price,
            "item_total": self.item_total,
            "volume_price": self.volume_price,
            "service_fee": self.service_fee,
            "surge_multiplier": self.surge_multiplier,
            "total_price": self.total_price,
            "promo_code_id": self.promo_code_id,
            "discount_amount": self.discount_amount or 0.0,
            "notes": self.notes,
            "lead_source": self.lead_source,
            "confirmation_code": self.confirmation_code,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "cancellation_fee": self.cancellation_fee or 0.0,
            "rescheduled_count": self.rescheduled_count or 0,
            "reminder_sent": self.reminder_sent or False,
            "reminder_call_id": self.reminder_call_id,
            "review_requested": self.review_requested or False,
            "review_call_id": self.review_call_id,
            "noshow_t30_alerted": self.noshow_t30_alerted or False,
            "noshow_late_alerted": self.noshow_late_alerted or False,
            "volume_adjustment_proposed": self.volume_adjustment_proposed,
            "adjusted_volume": self.adjusted_volume,
            "adjusted_price": self.adjusted_price,
            "disposition_preference": self.disposition_preference or "best",
            "disposition_outcome": self.disposition_outcome,
            "disposition_notes": self.disposition_notes,
            "impact_summary": self.impact_summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ---------------------------------------------------------------------------
# JobOffer  (marketplace broadcast / first-to-accept)
# ---------------------------------------------------------------------------
class JobOffer(db.Model):
    """A single job broadcast to one contractor.

    When a job is dispatched in broadcast mode, one JobOffer row is created per
    eligible contractor. Each carries an unguessable ``accept_token`` used in the
    SMS accept link. The first contractor to accept wins the job atomically; all
    sibling offers are flipped to ``superseded``. This replaces the single
    auto-assign that let one hauler silently ghost a booking (the Sy failure).
    """

    __tablename__ = "job_offers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    contractor_id = Column(String(36), ForeignKey("contractors.id", ondelete="CASCADE"), nullable=False, index=True)

    # sent -> accepted | declined | expired | superseded
    status = Column(String(20), nullable=False, default="sent", index=True)
    accept_token = Column(String(36), unique=True, nullable=False, default=generate_uuid, index=True)

    distance_miles = Column(Float, nullable=True)   # contractor -> job at send time
    payout_amount = Column(Float, nullable=True)     # contractor take-home for this job

    sent_at = Column(DateTime, default=utcnow)
    responded_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utcnow)

    job = relationship("Job", backref="offers", foreign_keys=[job_id])
    contractor = relationship("Contractor", foreign_keys=[contractor_id])

    __table_args__ = (
        Index("ix_job_offers_job_status", "job_id", "status"),
        CheckConstraint(
            "status IN ('sent', 'accepted', 'declined', 'expired', 'superseded')",
            name="ck_job_offer_status",
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "job_id": self.job_id,
            "contractor_id": self.contractor_id,
            "status": self.status,
            "distance_miles": self.distance_miles,
            "payout_amount": self.payout_amount,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "responded_at": self.responded_at.isoformat() if self.responded_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Rating
# ---------------------------------------------------------------------------
class Rating(db.Model):
    __tablename__ = "ratings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True)
    from_user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    to_user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    stars = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        CheckConstraint("stars >= 1 AND stars <= 5", name="ck_rating_stars"),
    )

    job = relationship("Job", back_populates="rating")
    from_user = relationship("User", foreign_keys=[from_user_id], back_populates="ratings_given")
    to_user = relationship("User", foreign_keys=[to_user_id], back_populates="ratings_received")

    def to_dict(self):
        return {
            "id": self.id,
            "job_id": self.job_id,
            "from_user_id": self.from_user_id,
            "to_user_id": self.to_user_id,
            "stars": self.stars,
            "comment": self.comment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "from_user": self.from_user.to_dict() if self.from_user else None,
        }


# ---------------------------------------------------------------------------
# Payment
# ---------------------------------------------------------------------------
class Payment(db.Model):
    __tablename__ = "payments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True)
    stripe_payment_intent_id = Column(String(255), nullable=True, unique=True)
    amount = Column(Float, nullable=False, default=0.0)
    service_fee = Column(Float, default=0.0)
    commission = Column(Float, default=0.0)
    driver_payout_amount = Column(Float, default=0.0)
    operator_payout_amount = Column(Float, default=0.0)
    payout_status = Column(String(30), default="pending")
    payment_status = Column(String(30), default="pending")
    tip_amount = Column(Float, default=0.0)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    job = relationship("Job", back_populates="payment")

    def to_dict(self):
        return {
            "id": self.id,
            "job_id": self.job_id,
            "stripe_payment_intent_id": self.stripe_payment_intent_id,
            "amount": self.amount,
            "service_fee": self.service_fee,
            "commission": self.commission,
            "driver_payout_amount": self.driver_payout_amount,
            "operator_payout_amount": self.operator_payout_amount or 0.0,
            "payout_status": self.payout_status,
            "payment_status": self.payment_status,
            "tip_amount": self.tip_amount,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ---------------------------------------------------------------------------
# PricingRule
# ---------------------------------------------------------------------------
class PricingRule(db.Model):
    __tablename__ = "pricing_rules"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    item_type = Column(String(100), nullable=False, unique=True)
    base_price = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "item_type": self.item_type,
            "base_price": self.base_price,
            "description": self.description,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ---------------------------------------------------------------------------
# SurgeZone
# ---------------------------------------------------------------------------
class SurgeZone(db.Model):
    __tablename__ = "surge_zones"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    boundary = Column(JSON, nullable=True)
    surge_multiplier = Column(Float, default=1.0)
    is_active = Column(Boolean, default=True)
    start_time = Column(String(5), nullable=True)
    end_time = Column(String(5), nullable=True)
    days_of_week = Column(JSON, nullable=True, default=list)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "boundary": self.boundary,
            "surge_multiplier": self.surge_multiplier,
            "is_active": self.is_active,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "days_of_week": self.days_of_week or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------
class Notification(db.Model):
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=True)
    data = Column(JSON, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="notifications")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "type": self.type,
            "title": self.title,
            "body": self.body,
            "data": self.data,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# OperatorInvite
# ---------------------------------------------------------------------------
class OperatorInvite(db.Model):
    __tablename__ = "operator_invites"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    operator_id = Column(String(36), ForeignKey("contractors.id", ondelete="CASCADE"), nullable=False, index=True)
    invite_code = Column(String(20), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=True)
    max_uses = Column(Integer, default=1)
    use_count = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    operator = relationship("Contractor", foreign_keys=[operator_id])

    def to_dict(self):
        return {
            "id": self.id,
            "operator_id": self.operator_id,
            "invite_code": self.invite_code,
            "email": self.email,
            "max_uses": self.max_uses,
            "use_count": self.use_count,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# DeviceToken (APNs / FCM push notification tokens)
# ---------------------------------------------------------------------------
class DeviceToken(db.Model):
    __tablename__ = "device_tokens"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(512), unique=True, nullable=False)
    platform = Column(String(10), nullable=False, default="ios")  # "ios" or "android"
    created_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        CheckConstraint("platform IN ('ios', 'android')", name="ck_device_token_platform"),
    )

    user = relationship("User", back_populates="device_tokens")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "token": self.token,
            "platform": self.platform,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# PricingConfig (singleton-style key/value for admin-overridable settings)
# ---------------------------------------------------------------------------
class PricingConfig(db.Model):
    __tablename__ = "pricing_config"

    key = Column(String(100), primary_key=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    def to_dict(self):
        return {
            "key": self.key,
            "value": self.value,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ---------------------------------------------------------------------------
# RecurringBooking
# ---------------------------------------------------------------------------
class RecurringBooking(db.Model):
    __tablename__ = "recurring_bookings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    customer_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    frequency = Column(String(20), nullable=False)  # "weekly", "biweekly", "monthly"
    day_of_week = Column(Integer, nullable=True)     # 0=Monday .. 6=Sunday (for weekly/biweekly)
    day_of_month = Column(Integer, nullable=True)    # 1-28 (for monthly)
    preferred_time = Column(String(5), nullable=False, default="09:00")  # "HH:MM"

    address = Column(Text, nullable=False)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)

    items = Column(JSON, nullable=True, default=list)
    notes = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True)
    next_scheduled_at = Column(DateTime, nullable=True)
    total_bookings_created = Column(Integer, default=0)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        CheckConstraint(
            "frequency IN ('weekly', 'biweekly', 'monthly')",
            name="ck_recurring_frequency",
        ),
        CheckConstraint(
            "day_of_week IS NULL OR (day_of_week >= 0 AND day_of_week <= 6)",
            name="ck_recurring_day_of_week",
        ),
        CheckConstraint(
            "day_of_month IS NULL OR (day_of_month >= 1 AND day_of_month <= 28)",
            name="ck_recurring_day_of_month",
        ),
    )

    customer = relationship("User", foreign_keys=[customer_id], backref="recurring_bookings")

    def to_dict(self):
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "frequency": self.frequency,
            "day_of_week": self.day_of_week,
            "day_of_month": self.day_of_month,
            "preferred_time": self.preferred_time,
            "address": self.address,
            "lat": self.lat,
            "lng": self.lng,
            "items": self.items or [],
            "notes": self.notes,
            "is_active": self.is_active,
            "next_scheduled_at": self.next_scheduled_at.isoformat() if self.next_scheduled_at else None,
            "total_bookings_created": self.total_bookings_created,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ---------------------------------------------------------------------------
# Referral
# ---------------------------------------------------------------------------
class Referral(db.Model):
    __tablename__ = "referrals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    referrer_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    referee_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    referral_code = Column(String(8), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending")
    reward_amount = Column(Float, default=10.00)
    # 'customer' = rider-to-rider; 'contractor' = hauler refers a new hauler
    # (supply growth — pays out on the new hauler's first completed job).
    referral_type = Column(String(20), nullable=False, default="customer")
    created_at = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'signed_up', 'completed', 'rewarded')",
            name="ck_referral_status",
        ),
    )

    referrer = relationship("User", foreign_keys=[referrer_id], back_populates="referrals_made")
    referee = relationship("User", foreign_keys=[referee_id], back_populates="referral_received")

    def to_dict(self):
        return {
            "id": self.id,
            "referrer_id": self.referrer_id,
            "referee_id": self.referee_id,
            "referral_code": self.referral_code,
            "status": self.status,
            "reward_amount": self.reward_amount,
            "referral_type": self.referral_type or "customer",
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "referrer_name": self.referrer.name if self.referrer else None,
            "referee_name": self.referee.name if self.referee else None,
        }


# ---------------------------------------------------------------------------
# SupportMessage
# ---------------------------------------------------------------------------
class SupportMessage(db.Model):
    __tablename__ = "support_messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    category = Column(String(50), nullable=False, default="other")
    status = Column(String(20), nullable=False, default="open")

    created_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        CheckConstraint("status IN ('open', 'resolved')", name="ck_support_message_status"),
        Index("ix_support_messages_status", "status"),
    )

    user = relationship("User", foreign_keys=[user_id])

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "email": self.email,
            "message": self.message,
            "category": self.category,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Refund
# ---------------------------------------------------------------------------
class Refund(db.Model):
    __tablename__ = "refunds"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    payment_id = Column(String(36), ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    reason = Column(Text, nullable=True)
    stripe_refund_id = Column(String(255), nullable=True, unique=True)
    status = Column(String(30), nullable=False, default="pending")
    created_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed', 'cancelled')",
            name="ck_refund_status",
        ),
    )

    payment = relationship("Payment", backref="refunds")

    def to_dict(self):
        return {
            "id": self.id,
            "payment_id": self.payment_id,
            "amount": self.amount,
            "reason": self.reason,
            "stripe_refund_id": self.stripe_refund_id,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# WebhookEvent (audit log for all incoming Stripe webhook events)
# ---------------------------------------------------------------------------
class WebhookEvent(db.Model):
    __tablename__ = "webhook_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    stripe_event_id = Column(String(255), nullable=True, unique=True, index=True)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=True)
    status = Column(String(20), nullable=False, default="processed")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "stripe_event_id": self.stripe_event_id,
            "event_type": self.event_type,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# ChatMessage (real-time chat between customer and driver on a job)
# ---------------------------------------------------------------------------
class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = Column(String(36), nullable=False)  # user_id
    sender_role = Column(String(20), nullable=False)  # "customer" or "driver"
    message = Column(Text, nullable=False)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    job = relationship("Job", backref="chat_messages")

    __table_args__ = (
        CheckConstraint("sender_role IN ('customer', 'driver')", name="ck_chat_sender_role"),
        Index("ix_chat_messages_job_created", "job_id", "created_at"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "job_id": self.job_id,
            "sender_id": self.sender_id,
            "sender_role": self.sender_role,
            "message": self.message,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Review (customer review of a completed job)
# ---------------------------------------------------------------------------
class Review(db.Model):
    __tablename__ = "reviews"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    customer_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    contractor_id = Column(String(36), ForeignKey("contractors.id", ondelete="CASCADE"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)  # 1-5
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_review_rating"),
    )

    job = relationship("Job", backref="review")
    customer = relationship("User", foreign_keys=[customer_id])
    contractor = relationship("Contractor", backref="reviews")

    def to_dict(self):
        return {
            "id": self.id,
            "job_id": self.job_id,
            "customer_id": self.customer_id,
            "contractor_id": self.contractor_id,
            "rating": self.rating,
            "comment": self.comment,
            "customer_name": self.customer.name if self.customer else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }



# ---------------------------------------------------------------------------
# OperatorApplication (landing page operator signup form)
# ---------------------------------------------------------------------------
class OperatorApplication(db.Model):
    __tablename__ = "operator_applications"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(20), nullable=False)
    city = Column(String(100), nullable=False)
    trucks = Column(String(20), nullable=True)
    experience = Column(String(50), nullable=True)
    referral_code = Column(String(8), nullable=True)  # referring hauler's code (operator referral)
    status = Column(String(20), nullable=False, default="pending")  # pending, approved, rejected
    rejection_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "phone": self.phone,
            "city": self.city,
            "trucks": self.trucks,
            "experience": self.experience,
            "status": self.status,
            "rejection_reason": self.rejection_reason,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ---------------------------------------------------------------------------
# AbandonedBooking (lead recovery drip)
# ---------------------------------------------------------------------------
class AbandonedBooking(db.Model):
    __tablename__ = "abandoned_bookings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(20), nullable=True)
    name = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    items = Column(JSON, nullable=True)
    step = Column(Integer, nullable=True)  # Which booking step they reached
    estimated_price = Column(Float, nullable=True)
    lead_source = Column(String(100), nullable=True)
    drip_stage = Column(Integer, default=0)  # 0=new, 1=1h sent, 2=24h sent, 3=72h sent
    converted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    last_drip_at = Column(DateTime, nullable=True)
    # No-coverage waitlist: where the customer wanted service + when we told
    # them we're now live in their area (so we never re-notify).
    waitlist_lat = Column(Float, nullable=True)
    waitlist_lng = Column(Float, nullable=True)
    waitlist_notified_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "phone": self.phone,
            "name": self.name,
            "address": self.address,
            "items": self.items,
            "step": self.step,
            "estimated_price": self.estimated_price,
            "lead_source": self.lead_source,
            "drip_stage": self.drip_stage,
            "converted": self.converted,
            "waitlist_notified_at": self.waitlist_notified_at.isoformat() if self.waitlist_notified_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# CallLog (Vapi AI phone call transcripts and summaries)
# ---------------------------------------------------------------------------
class CallLog(db.Model):
    __tablename__ = "call_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    call_id = Column(String(255), unique=True, nullable=False, index=True)
    phone_number = Column(String(20), nullable=True)
    direction = Column(String(10), nullable=False, default="inbound")
    duration_seconds = Column(Integer, nullable=True)
    status = Column(String(50), nullable=True)  # completed, missed, transferred, etc.
    transcript = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    sentiment = Column(String(20), nullable=True)  # positive, neutral, negative
    tools_used = Column(JSON, nullable=True)
    booking_created = Column(Boolean, default=False)
    customer_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=utcnow)
    ended_at = Column(DateTime, nullable=True)

    lead_score = Column(String(10), nullable=True)  # hot, warm, cold
    followup_sent = Column(Boolean, default=False)

    # Lead assignment fields
    assigned_operator_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_driver_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    assignment_status = Column(String(20), default="unassigned")  # unassigned, assigned_operator, assigned_driver, completed
    assigned_at = Column(DateTime, nullable=True)

    customer = relationship("User", foreign_keys=[customer_id])
    assigned_operator = relationship("User", foreign_keys=[assigned_operator_id])
    assigned_driver = relationship("User", foreign_keys=[assigned_driver_id])

    def to_dict(self):
        return {
            "id": self.id,
            "call_id": self.call_id,
            "phone_number": self.phone_number,
            "direction": self.direction,
            "duration_seconds": self.duration_seconds,
            "status": self.status,
            "transcript": self.transcript,
            "summary": self.summary,
            "sentiment": self.sentiment,
            "tools_used": self.tools_used,
            "booking_created": self.booking_created,
            "customer_id": self.customer_id,
            "customer_name": self.customer.name if self.customer else None,
            "lead_score": self.lead_score,
            "followup_sent": self.followup_sent or False,
            "assigned_operator_id": self.assigned_operator_id,
            "assigned_operator_name": self.assigned_operator.name if self.assigned_operator else None,
            "assigned_driver_id": self.assigned_driver_id,
            "assigned_driver_name": self.assigned_driver.name if self.assigned_driver else None,
            "assignment_status": self.assignment_status or "unassigned",
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
        }

    # Helper: link to caller profile
    def get_or_create_caller_profile(self):
        """Get or create the CallerProfile for this call's phone number."""
        if not self.phone_number:
            return None
        profile = CallerProfile.query.filter_by(phone=self.phone_number).first()
        if not profile:
            profile = CallerProfile(
                id=generate_uuid(),
                phone=self.phone_number,
                customer_id=self.customer_id,
                first_call_at=self.created_at,
            )
            db.session.add(profile)
        return profile


# ---------------------------------------------------------------------------
# ScheduledCallback (Vapi AI callback scheduling)
# ---------------------------------------------------------------------------
class ScheduledCallback(db.Model):
    __tablename__ = "scheduled_callbacks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    phone = Column(String(20), nullable=False)
    customer_name = Column(String(255), nullable=True)
    requested_time = Column(String(255), nullable=False)  # raw text from caller
    scheduled_at = Column(DateTime, nullable=True)  # parsed datetime if possible
    status = Column(String(20), nullable=False, default="pending")  # pending, completed, failed
    call_id = Column(String(255), nullable=True)  # Vapi call ID that created this
    created_at = Column(DateTime, default=utcnow)

    # Lead assignment fields
    assigned_operator_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_driver_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    assignment_status = Column(String(20), default="unassigned")  # unassigned, assigned_operator, assigned_driver, completed
    assigned_at = Column(DateTime, nullable=True)

    assigned_operator = relationship("User", foreign_keys=[assigned_operator_id])
    assigned_driver = relationship("User", foreign_keys=[assigned_driver_id])

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'completed', 'failed')",
            name="ck_callback_status",
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "phone": self.phone,
            "customer_name": self.customer_name,
            "requested_time": self.requested_time,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "status": self.status,
            "call_id": self.call_id,
            "assigned_operator_id": self.assigned_operator_id,
            "assigned_operator_name": self.assigned_operator.name if self.assigned_operator else None,
            "assigned_driver_id": self.assigned_driver_id,
            "assigned_driver_name": self.assigned_driver.name if self.assigned_driver else None,
            "assignment_status": self.assignment_status or "unassigned",
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
        }


# ---------------------------------------------------------------------------
# CallerProfile (Maya caller memory — one per phone number)
# ---------------------------------------------------------------------------
class CallerProfile(db.Model):
    __tablename__ = "caller_profiles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    language = Column(String(10), default="en")
    customer_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Cumulative stats
    total_calls = Column(Integer, default=0)
    total_bookings = Column(Integer, default=0)
    total_spent = Column(Float, default=0.0)
    last_call_at = Column(DateTime, nullable=True)
    first_call_at = Column(DateTime, nullable=True)

    # Memory fields — what Maya remembers
    past_items = Column(JSON, nullable=True, default=list)  # ["sofa", "mattress", ...]
    preferences = Column(JSON, nullable=True, default=dict)  # {"preferred_time": "morning", ...}
    notes = Column(Text, nullable=True)  # Free-text notes from calls
    tags = Column(JSON, nullable=True, default=list)  # ["repeat_customer", "spanish_speaker", ...]

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    customer = relationship("User", foreign_keys=[customer_id])
    insights = relationship("CallInsight", back_populates="caller_profile", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "phone": self.phone,
            "name": self.name,
            "email": self.email,
            "address": self.address,
            "language": self.language,
            "total_calls": self.total_calls or 0,
            "total_bookings": self.total_bookings or 0,
            "total_spent": self.total_spent or 0.0,
            "last_call_at": self.last_call_at.isoformat() if self.last_call_at else None,
            "first_call_at": self.first_call_at.isoformat() if self.first_call_at else None,
            "past_items": self.past_items or [],
            "preferences": self.preferences or {},
            "notes": self.notes,
            "tags": self.tags or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ---------------------------------------------------------------------------
# CallInsight (AI-generated per-call analysis)
# ---------------------------------------------------------------------------
class CallInsight(db.Model):
    __tablename__ = "call_insights"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    call_log_id = Column(String(36), ForeignKey("call_logs.id", ondelete="CASCADE"), nullable=False, index=True)
    caller_profile_id = Column(String(36), ForeignKey("caller_profiles.id", ondelete="SET NULL"), nullable=True, index=True)

    # AI analysis fields
    caller_mood = Column(String(30), nullable=True)
    conversion_likelihood = Column(String(10), nullable=True)
    items_discussed = Column(JSON, nullable=True, default=list)
    objections_raised = Column(JSON, nullable=True, default=list)
    what_worked = Column(JSON, nullable=True, default=list)
    what_failed = Column(JSON, nullable=True, default=list)
    competitive_mentions = Column(JSON, nullable=True, default=list)
    recommended_followup = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    language_used = Column(String(10), nullable=True)
    raw_analysis = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=utcnow)

    call_log = relationship("CallLog", backref="insights")
    caller_profile = relationship("CallerProfile", back_populates="insights")

    def to_dict(self):
        return {
            "id": self.id,
            "call_log_id": self.call_log_id,
            "caller_profile_id": self.caller_profile_id,
            "caller_mood": self.caller_mood,
            "conversion_likelihood": self.conversion_likelihood,
            "items_discussed": self.items_discussed or [],
            "objections_raised": self.objections_raised or [],
            "what_worked": self.what_worked or [],
            "what_failed": self.what_failed or [],
            "competitive_mentions": self.competitive_mentions or [],
            "recommended_followup": self.recommended_followup,
            "summary": self.summary,
            "language_used": self.language_used,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Email Campaigns
# ---------------------------------------------------------------------------
class EmailCampaign(db.Model):
    __tablename__ = "email_campaigns"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=False)
    template = Column(String(50), nullable=False)  # e.g. "recruitment_1", "winback"
    status = Column(String(20), nullable=False, default="draft")  # draft, sending, sent, paused
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    total_recipients = Column(Integer, default=0)
    total_sent = Column(Integer, default=0)
    total_failed = Column(Integer, default=0)

    created_at = Column(DateTime, default=utcnow)
    sent_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    recipients = relationship("CampaignRecipient", back_populates="campaign", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "subject": self.subject,
            "template": self.template,
            "status": self.status,
            "total_recipients": self.total_recipients,
            "total_sent": self.total_sent,
            "total_failed": self.total_failed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class CampaignRecipient(db.Model):
    __tablename__ = "campaign_recipients"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    campaign_id = Column(String(36), ForeignKey("email_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=False)
    first_name = Column(String(255), nullable=True)
    company = Column(String(255), nullable=True)
    area = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)

    status = Column(String(20), nullable=False, default="pending")  # pending, sent, failed, bounced
    sent_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow)

    campaign = relationship("EmailCampaign", back_populates="recipients")

    __table_args__ = (
        Index("ix_campaign_recipient_email", "campaign_id", "email", unique=True),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "email": self.email,
            "first_name": self.first_name,
            "company": self.company,
            "area": self.area,
            "phone": self.phone,
            "status": self.status,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "error_message": self.error_message,
        }


# ---------------------------------------------------------------------------
# Vision Quote Engine (spec: 01-vision-quote-engine.md)
# ---------------------------------------------------------------------------
# Quote: customer-facing binding price from vision pipeline
# QuoteItem: per-item breakdown
# VisionInferenceLog: audit log for every Claude/GPT-4o call
# QuoteFeedback: driver ground truth post-job
# CalibrationSample: (photos -> actual) training pairs for fine-tune v2
# ---------------------------------------------------------------------------
class Quote(db.Model):
    __tablename__ = "quotes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)  # null = guest
    guest_phone = Column(String(20), nullable=True, index=True)
    guest_email = Column(String(255), nullable=True)
    zip_code = Column(String(10), nullable=False, index=True)
    zone = Column(String(32), nullable=False)  # 'miami-dade' | 'broward' | 'palm-beach'
    status = Column(String(20), nullable=False, default="draft", index=True)
    # status values: draft, pending_review, binding, buffered, accepted, booked, expired, voided
    origin = Column(String(16), nullable=False, default="vision")  # 'vision' | 'rules'
    price_cents = Column(Integer, nullable=False)              # final binding price
    price_floor_cents = Column(Integer, nullable=True)          # range for pending_review
    price_ceiling_cents = Column(Integer, nullable=True)
    estimated_volume_cubic_yards = Column(Float, nullable=False)
    confidence_score = Column(Float, nullable=False, index=True)  # 0.0-1.0
    hazmat_flag = Column(Boolean, default=False, nullable=False)
    binding = Column(Boolean, default=False, nullable=False)      # true only if confidence>=0.85
    model_version = Column(String(64), nullable=False)            # e.g. "claude-sonnet-4.6-2026-01"
    calibration_version = Column(String(32), nullable=False)      # e.g. "cal-v3-2026-04"
    expires_at = Column(DateTime, nullable=False, index=True)     # now + 48h
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    accepted_at = Column(DateTime, nullable=True)
    booked_at = Column(DateTime, nullable=True)
    # NOTE: spec says ForeignKey("bookings.id") but no bookings table exists in this
    # codebase -- jobs is the booking equivalent. Using jobs.id (flagged to caller).
    booking_id = Column(String(36), ForeignKey("jobs.id"), nullable=True)
    photo_urls = Column(JSON, nullable=False)                     # list[str] of R2 URLs
    raw_inference_id = Column(String(36), ForeignKey("vision_inference_logs.id", use_alter=True, name="fk_quotes_raw_inference"))

    items = relationship("QuoteItem", back_populates="quote", cascade="all, delete-orphan")
    feedback = relationship("QuoteFeedback", back_populates="quote", uselist=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','pending_review','binding','buffered','accepted','booked','expired','voided')",
            name="ck_quote_status",
        ),
        Index("ix_quotes_zone_status", "zone", "status"),
        Index("ix_quotes_created_confidence", "created_at", "confidence_score"),
    )


class QuoteItem(db.Model):
    __tablename__ = "quote_items"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    quote_id = Column(String(36), ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False, index=True)
    label = Column(String(64), nullable=False)                    # "mattress-queen"
    display_name = Column(String(128), nullable=False)            # "Queen mattress"
    count = Column(Integer, default=1, nullable=False)
    volume_cubic_yards = Column(Float, nullable=False)
    unit_price_cents = Column(Integer, nullable=False)
    hazmat = Column(Boolean, default=False, nullable=False)
    photo_index = Column(Integer, nullable=True)                  # which photo it came from
    bbox = Column(JSON, nullable=True)                            # [x, y, w, h] normalized

    quote = relationship("Quote", back_populates="items")


class VisionInferenceLog(db.Model):
    __tablename__ = "vision_inference_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    quote_id = Column(String(36), ForeignKey("quotes.id", use_alter=True, name="fk_vision_log_quote"), nullable=True, index=True)
    model = Column(String(64), nullable=False)                    # "claude-sonnet-4.6" | "gpt-4v-fallback"
    prompt_hash = Column(String(64), nullable=False)              # sha256 of system prompt
    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)
    cost_cents = Column(Float, nullable=False)
    latency_ms = Column(Integer, nullable=False)
    raw_response = Column(JSON, nullable=False)
    error = Column(String(1024), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)


class QuoteFeedback(db.Model):
    __tablename__ = "quote_feedback"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    quote_id = Column(String(36), ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    driver_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    actual_price_cents = Column(Integer, nullable=False)
    actual_volume_cubic_yards = Column(Float, nullable=False)
    actual_labor_minutes = Column(Integer, nullable=False)
    delta_cents = Column(Integer, nullable=False)                 # actual - quoted (can be negative)
    delta_pct = Column(Float, nullable=False, index=True)
    miss_category = Column(String(20), nullable=False)
    # miss_category values: accurate, under, over, hazmat_missed, volume_missed, item_missed
    driver_notes = Column(String(2048), nullable=True)
    post_job_photo_urls = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    quote = relationship("Quote", back_populates="feedback")

    __table_args__ = (
        CheckConstraint(
            "miss_category IN ('accurate','under','over','hazmat_missed','volume_missed','item_missed')",
            name="ck_quote_feedback_miss_category",
        ),
    )


class CalibrationSample(db.Model):
    __tablename__ = "calibration_samples"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    quote_id = Column(String(36), ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False, index=True)
    photo_urls = Column(JSON, nullable=False)
    predicted_items = Column(JSON, nullable=False)                # model output
    actual_items = Column(JSON, nullable=False)                   # driver ground truth
    predicted_price_cents = Column(Integer, nullable=False)
    actual_price_cents = Column(Integer, nullable=False)
    used_for_training = Column(Boolean, default=False, nullable=False, index=True)
    training_run_id = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)


# ---------------------------------------------------------------------------
# Voice AI Inbound (spec: 02-voice-ai-inbound.md)
# ---------------------------------------------------------------------------
# VoiceCall:        one row per inbound PSTN call (Vapi orchestrated)
# VoiceCallTurn:    each caller|agent|tool utterance in a call
# VoiceCallTranscript: 1:1 diarized full transcript + summary + sentiment
# VoiceCallOutcome: 1:1 booking / escalation / abandon result
# VoiceSMSExchange: SMS events tied to an active call (photo req, stripe link)
#
# NOTE: spec uses PG-native types (JSONB, ARRAY, Vector(1024)). This codebase
# targets both SQLite + PostgreSQL with a uniform conventions layer:
#   - UUID/ULID columns stored as String(36) (spec said String(26); we use 36
#     to match codebase convention, ULIDs fit in 26 chars so no truncation)
#   - JSONB -> JSON (portable)
#   - ARRAY(String) -> JSON list
#   - Vector(1024) embedding OMITTED (pgvector not installed; flagged deviation)
#   - Enum-style spec fields -> String + CheckConstraint
#   - FK "bookings.id" -> "jobs.id" (no bookings table; jobs is the equivalent)
# ---------------------------------------------------------------------------
class VoiceCall(db.Model):
    __tablename__ = "voice_calls"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    vapi_call_id = Column(String(64), unique=True, nullable=False, index=True)
    twilio_call_sid = Column(String(64), nullable=True, index=True)
    caller_number = Column(String(20), nullable=False, index=True)   # E.164
    called_number = Column(String(20), nullable=False)               # our TFN
    started_at = Column(DateTime, nullable=False, index=True)
    answered_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    duration_s = Column(Integer, nullable=True)
    cost_usd = Column(Float, nullable=True)
    status = Column(String(24), nullable=True, index=True)
    # status values: in_progress | completed | failed | spam
    outcome_id = Column(String(36), ForeignKey("voice_call_outcomes.id", use_alter=True, name="fk_voice_calls_outcome"), nullable=True)
    recording_url = Column(String(512), nullable=True)
    consent_given = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)

    turns = relationship(
        "VoiceCallTurn",
        back_populates="call",
        order_by="VoiceCallTurn.turn_index",
        cascade="all, delete-orphan",
        foreign_keys="VoiceCallTurn.call_id",
    )
    sms_exchanges = relationship(
        "VoiceSMSExchange",
        back_populates="call",
        cascade="all, delete-orphan",
        foreign_keys="VoiceSMSExchange.call_id",
    )
    transcript = relationship(
        "VoiceCallTranscript",
        back_populates="call",
        uselist=False,
        cascade="all, delete-orphan",
        foreign_keys="VoiceCallTranscript.call_id",
    )
    outcome = relationship(
        "VoiceCallOutcome",
        back_populates="call",
        uselist=False,
        foreign_keys="VoiceCallOutcome.call_id",
    )

    __table_args__ = (
        CheckConstraint(
            "status IS NULL OR status IN ('in_progress','completed','failed','spam')",
            name="ck_voice_calls_status",
        ),
        Index("ix_voice_calls_caller_started", "caller_number", "started_at"),
    )


class VoiceCallTurn(db.Model):
    __tablename__ = "voice_call_turns"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    call_id = Column(String(36), ForeignKey("voice_calls.id", ondelete="CASCADE"), nullable=False, index=True)
    turn_index = Column(Integer, nullable=False)
    role = Column(String(12), nullable=False)          # caller | agent | tool
    text = Column(Text, nullable=False)
    tool_name = Column(String(64), nullable=True)
    tool_input = Column(JSON, nullable=True)
    tool_output = Column(JSON, nullable=True)
    latency_ms = Column(Integer, nullable=True)        # caller_eot -> audio_start
    created_at = Column(DateTime, default=utcnow)

    call = relationship("VoiceCall", back_populates="turns", foreign_keys=[call_id])

    __table_args__ = (
        CheckConstraint(
            "role IN ('caller','agent','tool')",
            name="ck_voice_call_turns_role",
        ),
        Index("ix_voice_call_turns_call_idx", "call_id", "turn_index", unique=True),
    )


class VoiceCallTranscript(db.Model):
    __tablename__ = "voice_call_transcripts"

    # Spec uses call_id as primary key for 1:1 mapping
    call_id = Column(String(36), ForeignKey("voice_calls.id", ondelete="CASCADE"), primary_key=True)
    full_text = Column(Text, nullable=False)           # diarized markdown
    summary = Column(Text, nullable=True)              # 3-sentence Claude summary
    sentiment = Column(String(16), nullable=True)      # positive | neutral | negative | grief
    tags = Column(JSON, nullable=True, default=list)   # ['commercial','priced','booked']
    # NOTE: spec has `embedding = Vector(1024)` via pgvector; omitted because
    # pgvector extension is not installed in this deployment. To enable later:
    # add `pgvector` to requirements.txt, enable CREATE EXTENSION vector in PG,
    # add Column(Vector(1024)) here.

    call = relationship("VoiceCall", back_populates="transcript", foreign_keys=[call_id])

    __table_args__ = (
        CheckConstraint(
            "sentiment IS NULL OR sentiment IN ('positive','neutral','negative','grief')",
            name="ck_voice_call_transcripts_sentiment",
        ),
    )


class VoiceCallOutcome(db.Model):
    __tablename__ = "voice_call_outcomes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    call_id = Column(String(36), ForeignKey("voice_calls.id", ondelete="CASCADE"), nullable=False, unique=True)
    booked = Column(Boolean, default=False, index=True)
    # NOTE: spec says ForeignKey("bookings.id") but no bookings table exists --
    # jobs is the booking equivalent. Using jobs.id.
    booking_id = Column(String(36), ForeignKey("jobs.id"), nullable=True)
    quote_id = Column(String(36), ForeignKey("quotes.id"), nullable=True)
    quoted_amount = Column(Float, nullable=True)
    paid = Column(Boolean, default=False)
    payment_link_url = Column(String(512), nullable=True)
    stripe_session_id = Column(String(128), nullable=True)
    escalated = Column(Boolean, default=False, index=True)
    escalation_reason = Column(String(32), nullable=True)
    # escalation_reason values: commercial | estate | complex | complaint | consent_refused | out_of_area
    abandon_stage = Column(String(32), nullable=True)
    # abandon_stage values: qualify | photo | quote | book | pay | null
    discount_pct = Column(Float, nullable=True)

    call = relationship(
        "VoiceCall",
        back_populates="outcome",
        foreign_keys=[call_id],
    )

    __table_args__ = (
        CheckConstraint(
            "escalation_reason IS NULL OR escalation_reason IN "
            "('commercial','estate','complex','complaint','consent_refused','out_of_area')",
            name="ck_voice_call_outcomes_escalation_reason",
        ),
        CheckConstraint(
            "abandon_stage IS NULL OR abandon_stage IN "
            "('qualify','photo','quote','book','pay')",
            name="ck_voice_call_outcomes_abandon_stage",
        ),
    )


class VoiceSMSExchange(db.Model):
    __tablename__ = "voice_sms_exchanges"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    call_id = Column(String(36), ForeignKey("voice_calls.id", ondelete="CASCADE"), nullable=False, index=True)
    direction = Column(String(4), nullable=False)      # in | out
    purpose = Column(String(24), nullable=False)
    # purpose values: photo_request | quote_link | payment_link | confirmation
    body = Column(Text, nullable=False)
    media_url = Column(String(512), nullable=True)
    twilio_sid = Column(String(64), unique=True, nullable=True)
    delivered = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)

    call = relationship("VoiceCall", back_populates="sms_exchanges", foreign_keys=[call_id])

    __table_args__ = (
        CheckConstraint(
            "direction IN ('in','out')",
            name="ck_voice_sms_exchanges_direction",
        ),
        CheckConstraint(
            "purpose IN ('photo_request','quote_link','payment_link','confirmation')",
            name="ck_voice_sms_exchanges_purpose",
        ),
    )


# ---------------------------------------------------------------------------
# Post-Haul Attach Upsell Engine (spec: 09-post-haul-attach-engine.md)
# ---------------------------------------------------------------------------
# OfferCatalog:     12 canonical upsell offer templates (same_day_return, etc.)
# Offer:            a specific offer extended to a customer on a specific job
# AttachConversion: the Stripe-backed conversion + margin ledger for an Offer
#
# NOTE on spec alignment:
#   - Spec §4 names tables `upsell_*`. We use `attach_*` for clarity (matches
#     the "attach engine" product vernacular) and aligns with the API prefix
#     `/api/attach/*`.
#   - Spec uses PG-native types (UUID, JSONB, ARRAY). We mirror the Umuve
#     portable convention: String(36) + JSON + CheckConstraint.
#   - FK `bookings.id` -> `jobs.id` (no bookings table in this codebase).
#   - `partner_id` (spec §4) is stored as a free-form String(64) tag rather
#     than an FK — no partners table exists in this codebase and spec 09 is
#     launch-phase (partner network not wired). Flagged deviation.
#   - OpportunityDetection (spec §4) is NOT built in this pass — Claude Vision
#     pipeline integration is out of scope for the T2 operator-triggered hero
#     flow. When the Vision worker lands, detections can FK Offers via a
#     `detection_id` column (column-migration, additive).
# ---------------------------------------------------------------------------
class OfferCatalog(db.Model):
    __tablename__ = "offer_catalog"

    code = Column(String(60), primary_key=True)           # 'same_day_return'
    display_name = Column(String(128), nullable=False)    # "Same-Day Return"
    description = Column(Text, nullable=True)
    fulfillment = Column(String(20), nullable=False)      # inhouse | partner | hybrid
    partner_id = Column(String(64), nullable=True)         # free-form tag (e.g. 'broward-hhw')
    base_price_cents = Column(Integer, nullable=False)     # default offer_price
    umuve_margin_cents = Column(Integer, nullable=False)   # $ margin retained
    copy_template = Column(Text, nullable=False)           # rendered w/ {vars}
    active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "fulfillment IN ('inhouse','partner','hybrid')",
            name="ck_offer_catalog_fulfillment",
        ),
    )

    offers = relationship("Offer", back_populates="catalog", lazy="dynamic")

    def to_dict(self):
        return {
            "code": self.code,
            "display_name": self.display_name,
            "description": self.description,
            "fulfillment": self.fulfillment,
            "partner_id": self.partner_id,
            "base_price_cents": self.base_price_cents,
            "umuve_margin_cents": self.umuve_margin_cents,
            "copy_template": self.copy_template,
            "active": self.active,
        }


class Offer(db.Model):
    __tablename__ = "attach_offers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    # FK jobs.id (no bookings table, as flagged).
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)  # null => guest
    catalog_code = Column(String(60), ForeignKey("offer_catalog.code"), nullable=False, index=True)

    offer_price_cents = Column(Integer, nullable=False)
    expected_margin_cents = Column(Integer, nullable=False)  # margin at offer time
    copy_rendered = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="pending", index=True)
    # status values: pending, sent, opened, clicked, accepted, declined, expired, converted, failed
    channel = Column(String(20), nullable=False, default="sms")   # sms | push | email | in_app
    origin = Column(String(20), nullable=False, default="operator")  # operator | vision | rules
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)  # operator who triggered

    accept_token = Column(String(32), nullable=False, unique=True, index=True)
    attributes = Column(JSON, nullable=True)                # detection attrs, pricing tweaks

    scheduled_for = Column(DateTime, nullable=True)         # requested service window
    expires_at = Column(DateTime, nullable=False)           # default now+48h

    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    sent_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    declined_at = Column(DateTime, nullable=True)

    catalog = relationship("OfferCatalog", back_populates="offers")
    conversion = relationship(
        "AttachConversion",
        back_populates="offer",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','sent','opened','clicked','accepted','declined','expired','converted','failed')",
            name="ck_attach_offer_status",
        ),
        CheckConstraint(
            "channel IN ('sms','push','email','in_app')",
            name="ck_attach_offer_channel",
        ),
        CheckConstraint(
            "origin IN ('operator','vision','rules','crew_note')",
            name="ck_attach_offer_origin",
        ),
        Index("ix_attach_offers_job_status", "job_id", "status"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "job_id": self.job_id,
            "customer_id": self.customer_id,
            "catalog_code": self.catalog_code,
            "offer_price_cents": self.offer_price_cents,
            "expected_margin_cents": self.expected_margin_cents,
            "copy_rendered": self.copy_rendered,
            "status": self.status,
            "channel": self.channel,
            "origin": self.origin,
            "accept_token": self.accept_token,
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
            "declined_at": self.declined_at.isoformat() if self.declined_at else None,
        }


class AttachConversion(db.Model):
    __tablename__ = "attach_conversions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    offer_id = Column(String(36), ForeignKey("attach_offers.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    customer_id = Column(String(36), ForeignKey("users.id"), nullable=True)

    stripe_payment_intent_id = Column(String(255), nullable=True, index=True)
    amount_cents = Column(Integer, nullable=False)         # actually collected
    margin_cents = Column(Integer, nullable=False)         # margin locked at acceptance
    scheduled_for = Column(DateTime, nullable=True)
    payment_method_id = Column(String(255), nullable=True)

    fulfilled_at = Column(DateTime, nullable=True)
    fulfillment_notes = Column(Text, nullable=True)
    follow_on_job_id = Column(String(36), ForeignKey("jobs.id"), nullable=True)  # same_day_return spawns a new Job

    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    offer = relationship("Offer", back_populates="conversion")

    def to_dict(self):
        return {
            "id": self.id,
            "offer_id": self.offer_id,
            "job_id": self.job_id,
            "customer_id": self.customer_id,
            "stripe_payment_intent_id": self.stripe_payment_intent_id,
            "amount_cents": self.amount_cents,
            "margin_cents": self.margin_cents,
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None,
            "fulfilled_at": self.fulfilled_at.isoformat() if self.fulfilled_at else None,
            "follow_on_job_id": self.follow_on_job_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Insurance Claims Pipeline (spec: 10-insurance-claims-pipeline.md)
# ---------------------------------------------------------------------------
# ClaimCase:              one row per customer-initiated claim documentation request
# DepreciationSchedule:   per-item depreciation math (ACV = RCV - accumulated depreciation)
# ClaimPhotoDossier:      the rendered documentation packet (PDF + JSON manifest)
# XactimateExport:        Xactimate-compatible JSON export rows (one per generation)
# CarrierIntegration:     stub config for future carrier API push (keys vaulted)
#
# REGULATORY POSITIONING (NON-NEGOTIABLE):
#   Umuve is a DOCUMENTATION-AND-HAUL VENDOR. NOT a public adjuster (FL §626).
#   We do NOT negotiate claims, file claims on behalf of insureds, or settle
#   claims. We document debris + haul it away. Customers consult their own
#   licensed adjuster/attorney. All customer-facing surfaces must show the
#   `REGULATORY_DISCLAIMER` string defined in backend/claims_pipeline.py.
#
# Model conventions (match Voice AI + Vision Quote patterns):
#   - String(36) + generate_uuid() for PKs
#   - JSON (not JSONB) for portability SQLite + PostgreSQL
#   - CheckConstraint (NOT Enum) for enum-ish string fields
#   - auth_secret_vault_key stores a REFERENCE, never raw secret
# ---------------------------------------------------------------------------
class ClaimCase(db.Model):
    __tablename__ = "claim_cases"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)  # null = guest
    guest_phone = Column(String(20), nullable=True, index=True)
    guest_email = Column(String(255), nullable=True)

    # Customer-provided claim context
    claim_number = Column(String(64), nullable=True, index=True)   # insurer claim #, optional at upload
    insurer_name = Column(String(128), nullable=True)              # "State Farm", "Citizens", etc.
    policy_number = Column(String(64), nullable=True)
    adjuster_name = Column(String(128), nullable=True)
    adjuster_email = Column(String(255), nullable=True)
    adjuster_phone = Column(String(20), nullable=True)             # E.164
    loss_type = Column(String(24), nullable=False, default="other")
    # loss_type values: hurricane | tornado | flood | fire | hail | theft | vandalism | other
    loss_date = Column(DateTime, nullable=True)
    situation_narrative = Column(Text, nullable=True)              # customer's story, free text
    property_address = Column(Text, nullable=True)
    property_zip = Column(String(10), nullable=True, index=True)

    # Ties to Vision Quote pipeline
    quote_id = Column(String(36), ForeignKey("quotes.id"), nullable=True, index=True)
    photo_urls = Column(JSON, nullable=False, default=list)        # list[str] R2 URLs

    # Workflow status (spec §4 ClaimsOpportunity status enum adapted for case flow)
    status = Column(String(20), nullable=False, default="new", index=True)
    # status values: new | documenting | dossier_ready | carrier_sent | adjuster_approved | hauled | closed

    # Flags
    regulatory_ack = Column(Boolean, default=False, nullable=False)  # customer acknowledged disclaimer
    carrier_submission_enabled = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    depreciation_schedule = relationship(
        "DepreciationSchedule", back_populates="case", uselist=False,
        cascade="all, delete-orphan",
    )
    dossier = relationship(
        "ClaimPhotoDossier", back_populates="case", uselist=False,
        cascade="all, delete-orphan",
    )
    xactimate_exports = relationship(
        "XactimateExport", back_populates="case",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('new','documenting','dossier_ready','carrier_sent','adjuster_approved','hauled','closed')",
            name="ck_claim_case_status",
        ),
        CheckConstraint(
            "loss_type IN ('hurricane','tornado','flood','fire','hail','theft','vandalism','other')",
            name="ck_claim_case_loss_type",
        ),
        Index("ix_claim_cases_status_created", "status", "created_at"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "claim_number": self.claim_number,
            "insurer_name": self.insurer_name,
            "loss_type": self.loss_type,
            "loss_date": self.loss_date.isoformat() if self.loss_date else None,
            "status": self.status,
            "property_zip": self.property_zip,
            "photo_count": len(self.photo_urls or []),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "has_dossier": self.dossier is not None,
            "regulatory_ack": bool(self.regulatory_ack),
        }


class DepreciationSchedule(db.Model):
    __tablename__ = "depreciation_schedules"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    claim_case_id = Column(
        String(36), ForeignKey("claim_cases.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    # Line items: [{label, category, qty, rcv_cents, useful_life_years,
    #               age_years, annual_depreciation_pct, accumulated_depreciation_cents,
    #               acv_cents, xactimate_code, is_estimate, ...}]
    line_items = Column(JSON, nullable=False, default=list)
    total_rcv_cents = Column(Integer, nullable=False, default=0)          # replacement cost value
    total_depreciation_cents = Column(Integer, nullable=False, default=0)
    total_acv_cents = Column(Integer, nullable=False, default=0)          # actual cash value
    depreciation_table_version = Column(String(32), nullable=False, default="irs-industry-v1-2026")
    disclaimer_text = Column(Text, nullable=False)                        # frozen at generation
    generated_at = Column(DateTime, default=utcnow, nullable=False)

    case = relationship("ClaimCase", back_populates="depreciation_schedule")


class ClaimPhotoDossier(db.Model):
    __tablename__ = "claim_photo_dossiers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    claim_case_id = Column(
        String(36), ForeignKey("claim_cases.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    pdf_url = Column(String(512), nullable=True)     # rendered PDF packet (optional; may be generated lazily)
    json_manifest = Column(JSON, nullable=False)      # full packet payload (items + photos + disclaimer)
    photo_urls = Column(JSON, nullable=False, default=list)
    cover_letter_text = Column(Text, nullable=True)
    disclaimer_text = Column(Text, nullable=False)    # regulatory disclaimer frozen on this dossier
    total_rcv_cents = Column(Integer, nullable=False, default=0)
    total_acv_cents = Column(Integer, nullable=False, default=0)
    generated_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    downloaded_at = Column(DateTime, nullable=True)

    case = relationship("ClaimCase", back_populates="dossier")


class XactimateExport(db.Model):
    __tablename__ = "xactimate_exports"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    claim_case_id = Column(
        String(36), ForeignKey("claim_cases.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    export_format = Column(String(16), nullable=False, default="json")
    # export_format values: json | esx_xml (ESX envelope stubbed; JSON is the v1 primary)
    export_payload = Column(JSON, nullable=False)     # the canonical Xactimate-compatible structure
    total_rcv_cents = Column(Integer, nullable=False, default=0)
    total_acv_cents = Column(Integer, nullable=False, default=0)
    line_item_count = Column(Integer, nullable=False, default=0)
    schema_version = Column(String(32), nullable=False, default="xactimate-compat-v1")
    generated_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    downloaded_at = Column(DateTime, nullable=True)

    case = relationship("ClaimCase", back_populates="xactimate_exports")

    __table_args__ = (
        CheckConstraint(
            "export_format IN ('json','esx_xml')",
            name="ck_xactimate_export_format",
        ),
    )


class CarrierIntegration(db.Model):
    __tablename__ = "carrier_integrations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    carrier_name = Column(String(128), nullable=False, unique=True, index=True)
    webhook_url = Column(String(512), nullable=True)
    xactimate_endpoint = Column(String(512), nullable=True)
    auth_method = Column(String(16), nullable=False, default="none")
    # auth_method values: bearer | hmac | none
    # Vault reference only. Never store raw secrets in this table.
    auth_secret_vault_key = Column(String(128), nullable=True)
    carrier_avg_approval_hours = Column(Integer, nullable=True)
    is_sandbox = Column(Boolean, default=True, nullable=False)       # start in sandbox mode
    is_active = Column(Boolean, default=False, nullable=False)       # must be explicitly flipped by admin
    last_packet_sent_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "auth_method IN ('bearer','hmac','none')",
            name="ck_carrier_integration_auth_method",
        ),
    )


# ---------------------------------------------------------------------------
# Dynamic Surge Pricing (spec: 08-dynamic-surge-pricing.md)
# ---------------------------------------------------------------------------
# SurgeCoefficient:    posterior-mean weights per signal + zone (refreshed
#                      nightly in v1; hand-seeded in MVP). One active row per
#                      (zone, signal_name, variant). Admin overrides carry
#                      an override_reason + override_by + override_at.
# DemandSignal:        append-only raw signal stream (weather, utilization,
#                      landfill queue, etc.) feeding the aggregator. Cache
#                      rows via expires_at so the engine can reuse recent
#                      weather reads within 6h per zone.
# PriceAdjustmentLog:  per-quote audit row — every decision captured with
#                      base price, per-factor breakdown (signed pre-clamp
#                      contributions), final multiplier, and plain-English
#                      explanation. This is the spec §4 pricing_decisions
#                      table, renamed to match Umuve's `*_log` convention.
#
# Conventions match the rest of the codebase:
#   - String(36) UUID PKs via generate_uuid
#   - CheckConstraint (NOT Enum) for signal/variant/outcome enums
#   - JSON (portable) instead of PG-native JSONB
#   - FK to jobs.id (no bookings table)
#   - quote_id FK optional so the engine can price non-quote flows later
#
# Non-obvious: weather_severity carries NEGATIVE prior weight (rain = DISCOUNT,
# not surge) per Flow A2 — historical A/B showed this lifts conversion 18%.
# ---------------------------------------------------------------------------
class SurgeCoefficient(db.Model):
    __tablename__ = "surge_coefficients"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    zone_id = Column(String(32), nullable=False, index=True)
    signal_name = Column(String(40), nullable=False, index=True)
    weight = Column(Float, nullable=False)
    hdi_low = Column(Float, nullable=True)
    hdi_high = Column(Float, nullable=True)
    variant = Column(String(40), nullable=False, default="balanced")
    model_version = Column(String(32), nullable=False, default="v1-static-2026-04")
    active = Column(Boolean, default=True, nullable=False, index=True)
    override_reason = Column(Text, nullable=True)
    override_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    override_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "signal_name IN ('time_of_day','day_of_week','weather_severity',"
            "'truck_utilization','landfill_queue','holiday_flag',"
            "'historical_demand_z')",
            name="ck_surge_coeff_signal",
        ),
        CheckConstraint(
            "variant IN ('conservative','balanced','aggressive')",
            name="ck_surge_coeff_variant",
        ),
        Index("ix_surge_coeff_zone_signal_active", "zone_id", "signal_name", "active"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "zone_id": self.zone_id,
            "signal_name": self.signal_name,
            "weight": self.weight,
            "hdi_low": self.hdi_low,
            "hdi_high": self.hdi_high,
            "variant": self.variant,
            "model_version": self.model_version,
            "active": self.active,
            "override_reason": self.override_reason,
            "override_by": self.override_by,
            "override_at": self.override_at.isoformat() if self.override_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class DemandSignal(db.Model):
    __tablename__ = "demand_signals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    signal_type = Column(String(40), nullable=False, index=True)
    zone_id = Column(String(32), nullable=True, index=True)
    value = Column(Float, nullable=False)
    raw_payload = Column(JSON, nullable=True)
    source = Column(String(40), nullable=True)
    captured_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=True, index=True)

    __table_args__ = (
        Index("ix_demand_signals_zone_type_time", "zone_id", "signal_type", "captured_at"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "signal_type": self.signal_type,
            "zone_id": self.zone_id,
            "value": self.value,
            "source": self.source,
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


class PriceAdjustmentLog(db.Model):
    __tablename__ = "price_adjustment_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    quote_id = Column(String(36), ForeignKey("quotes.id"), nullable=True, index=True)
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=True, index=True)
    customer_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    zone_id = Column(String(32), nullable=False, index=True)
    base_price_cents = Column(Integer, nullable=False)
    multiplier = Column(Float, nullable=False)
    final_price_cents = Column(Integer, nullable=False)
    factor_breakdown = Column(JSON, nullable=False)
    signal_snapshot = Column(JSON, nullable=False)
    explanation = Column(Text, nullable=True)
    dominant_signal = Column(String(40), nullable=True)
    model_version = Column(String(32), nullable=False)
    variant = Column(String(40), nullable=False, default="balanced")
    override_reason = Column(String(40), nullable=True)
    decided_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    outcome = Column(String(20), nullable=True)
    outcome_at = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "outcome IS NULL OR outcome IN ('accepted','abandoned','rebooked')",
            name="ck_price_adj_outcome",
        ),
        CheckConstraint(
            "override_reason IS NULL OR override_reason IN "
            "('b2b_sla','manual','cap_hit','floor_hit','surge_disabled','exempt_account')",
            name="ck_price_adj_override_reason",
        ),
        CheckConstraint(
            "variant IN ('conservative','balanced','aggressive')",
            name="ck_price_adj_variant",
        ),
        Index("ix_price_adj_customer_time", "customer_id", "decided_at"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "quote_id": self.quote_id,
            "job_id": self.job_id,
            "customer_id": self.customer_id,
            "zone_id": self.zone_id,
            "base_price_cents": self.base_price_cents,
            "multiplier": self.multiplier,
            "final_price_cents": self.final_price_cents,
            "factor_breakdown": self.factor_breakdown,
            "signal_snapshot": self.signal_snapshot,
            "explanation": self.explanation,
            "dominant_signal": self.dominant_signal,
            "model_version": self.model_version,
            "variant": self.variant,
            "override_reason": self.override_reason,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "outcome": self.outcome,
            "outcome_at": self.outcome_at.isoformat() if self.outcome_at else None,
        }


# ---------------------------------------------------------------------------
# Donation / Resale Rescue Engine (spec: 05-donation-resale-engine.md)
# ---------------------------------------------------------------------------
# ItemValuation:   Claude-powered per-item resale FMV estimate (audit + training)
# ResaleListing:   candidate / live / sold listing tied to a QuoteItem
# ResaleSplit:     revenue split ledger (customer / umuve) after a sale settles
# DonationReceipt: IRS Form 8283-style receipt for donated items
#
# User-scope deviation from spec §4:
#   - Spec §4 uses {InventoryItem, Listing, Offer, Transaction,
#     DonationReceipt, CharityPartner}; user scope prescribes {ResaleListing,
#     DonationReceipt, ItemValuation, ResaleSplit} — we honor the scope.
#   - InventoryItem collapsed into existing QuoteItem (FK below).
#   - Offer + Transaction merged into ResaleSplit.
#   - CharityPartner simplified to inline fields on DonationReceipt.
#   - Spec says 30/30/40 (cust/umuve/charity); user scope says 40/60
#     (cust/umuve, no charity split) — we honor the scope. Flagged deviation.
# ---------------------------------------------------------------------------
class ItemValuation(db.Model):
    __tablename__ = "item_valuations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    quote_item_id = Column(
        String(36),
        ForeignKey("quote_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quote_id = Column(
        String(36),
        ForeignKey("quotes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_label = Column(String(64), nullable=False)
    display_name = Column(String(128), nullable=False)
    condition_grade = Column(String(1), nullable=True)             # A | B | C | D
    est_fmv_low_cents = Column(Integer, nullable=False, default=0)
    est_fmv_high_cents = Column(Integer, nullable=False, default=0)
    resale_probability = Column(Float, nullable=False, default=0.0)
    donation_eligible = Column(Boolean, default=False, nullable=False)
    hazmat_flag = Column(Boolean, default=False, nullable=False)
    high_value = Column(Boolean, default=False, nullable=False, index=True)
    reasoning = Column(String(512), nullable=True)
    model = Column(String(64), nullable=False)
    prompt_hash = Column(String(64), nullable=False)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    cost_cents = Column(Float, nullable=False, default=0.0)
    latency_ms = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    __table_args__ = (
        CheckConstraint(
            "condition_grade IS NULL OR condition_grade IN ('A','B','C','D')",
            name="ck_item_valuation_condition",
        ),
    )


class ResaleListing(db.Model):
    __tablename__ = "resale_listings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    quote_item_id = Column(
        String(36),
        ForeignKey("quote_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quote_id = Column(
        String(36),
        ForeignKey("quotes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    valuation_id = Column(
        String(36),
        ForeignKey("item_valuations.id", ondelete="SET NULL"),
        nullable=True,
    )
    status = Column(String(20), nullable=False, default="candidate", index=True)
    # status: candidate | approved | declined | listed | sold | expired | donated
    channel = Column(String(20), nullable=False, default="none")
    # channel: none | fb_marketplace | offerup | ebay | habitat | goodwill
    channel_listing_id = Column(String(128), nullable=True)
    channel_listing_url = Column(String(512), nullable=True)
    title = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    list_price_cents = Column(Integer, nullable=True)
    sold_price_cents = Column(Integer, nullable=True)
    photo_urls = Column(JSON, nullable=True)
    est_fmv_low_cents = Column(Integer, nullable=False, default=0)
    est_fmv_high_cents = Column(Integer, nullable=False, default=0)
    customer_approval_at = Column(DateTime, nullable=True)
    listed_at = Column(DateTime, nullable=True)
    sold_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)                   # 14-day hold (spec §2A.6)
    declined_reason = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('candidate','approved','declined','listed','sold','expired','donated')",
            name="ck_resale_listing_status",
        ),
        CheckConstraint(
            "channel IN ('none','fb_marketplace','offerup','ebay','habitat','goodwill')",
            name="ck_resale_listing_channel",
        ),
        Index("ix_resale_listings_quote_status", "quote_id", "status"),
    )


class ResaleSplit(db.Model):
    __tablename__ = "resale_splits"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    listing_id = Column(
        String(36),
        ForeignKey("resale_listings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    quote_id = Column(
        String(36),
        ForeignKey("quotes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    gross_cents = Column(Integer, nullable=False)
    customer_cut_cents = Column(Integer, nullable=False)
    umuve_cut_cents = Column(Integer, nullable=False)
    customer_share = Column(Float, nullable=False, default=0.40)
    umuve_share = Column(Float, nullable=False, default=0.60)
    stripe_payment_intent_id = Column(String(128), nullable=True)
    stripe_transfer_id = Column(String(128), nullable=True)
    customer_payout_status = Column(String(20), nullable=False, default="pending")
    # customer_payout_status: pending | paid | failed
    settled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "customer_payout_status IN ('pending','paid','failed')",
            name="ck_resale_split_payout_status",
        ),
        CheckConstraint(
            "gross_cents >= 0 AND customer_cut_cents >= 0 AND umuve_cut_cents >= 0",
            name="ck_resale_split_nonneg",
        ),
    )


class DonationReceipt(db.Model):
    __tablename__ = "donation_receipts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    quote_item_id = Column(
        String(36),
        ForeignKey("quote_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quote_id = Column(
        String(36),
        ForeignKey("quotes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    listing_id = Column(
        String(36),
        ForeignKey("resale_listings.id", ondelete="SET NULL"),
        nullable=True,
    )
    charity_partner_name = Column(String(128), nullable=False)
    charity_partner_ein = Column(String(32), nullable=True)
    charity_address = Column(String(512), nullable=True)
    item_description = Column(Text, nullable=False)
    condition_grade = Column(String(1), nullable=True)
    fair_market_value_cents = Column(Integer, nullable=False, default=0)
    drop_off_at = Column(DateTime, nullable=True)
    drop_off_photo_url = Column(String(512), nullable=True)
    form_8283_pdf_url = Column(String(512), nullable=True)
    docusign_envelope_id = Column(String(128), nullable=True)
    customer_signed_at = Column(DateTime, nullable=True)
    customer_email = Column(String(255), nullable=True)
    receipt_number = Column(String(32), unique=True, nullable=True, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    __table_args__ = (
        CheckConstraint(
            "condition_grade IS NULL OR condition_grade IN ('A','B','C','D')",
            name="ck_donation_receipt_condition",
        ),
    )


# ---------------------------------------------------------------------------
# Life-Event Demand Trigger Engine (spec 03-life-event-triggers.md)
#
# Positioning guardrail (CRITICAL):
#   Umuve is a documentation-and-haul vendor. We are NOT a Florida-licensed
#   public adjuster (FL 626) and NOT a restoration contractor (FL 489). This
#   schema only records life events for junk-removal outreach. Any copy
#   generated against it must never offer loss-assessment, claim advocacy,
#   rebuild, or structural repair services. The `regulatory_disclaimer` field
#   on OutreachLog is required for every send and surfaced in the admin UI.
# ---------------------------------------------------------------------------


class LifeEvent(db.Model):
    """A public-records event indicating a probable junk-removal need.

    Rows are ingested from county scrapers (see ``backend/workers/``) and
    deduped on (source, source_record_id).
    """

    __tablename__ = "life_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    source = Column(String(32), nullable=False, index=True)
    # regrid | miami_permits | broward_permits | pbc_permits | mls_zillow |
    # probate_miami_dade | probate_broward | probate_pbc | divorce_public |
    # legacy_obits | manual_import
    source_record_id = Column(String(128), nullable=False, index=True)
    event_type = Column(String(32), nullable=False, index=True)
    # deed_transfer | moving_permit | estate | probate_filing | mls_closing |
    # building_permit | divorce_filing | eviction | bankruptcy | obituary
    event_date = Column(DateTime, nullable=True, index=True)

    county = Column(String(32), nullable=False, index=True)
    # miami-dade | broward | palm-beach
    zip_code = Column(String(10), nullable=True, index=True)
    address_line1 = Column(String(255), nullable=True)
    apn = Column(String(64), nullable=True, index=True)

    prospect_name = Column(String(255), nullable=True)
    prospect_phone_e164 = Column(String(20), nullable=True, index=True)
    prospect_email = Column(String(255), nullable=True, index=True)

    raw_payload = Column(JSON, nullable=True)
    pii_hydrated = Column(Boolean, default=False, nullable=False)
    sensitive = Column(Boolean, default=False, nullable=False)
    # sensitive=True for: estate, probate, obituary, divorce, bankruptcy,
    # eviction. Enforced at outreach render time per spec 03 section 7.

    pipeline_status = Column(String(24), default="new", nullable=False, index=True)
    # new | matched | queued | contacted | converted | suppressed | stale
    suppressed_reason = Column(String(64), nullable=True)
    # dnc_federal | dnc_state | opted_out | out_of_area | duplicate |
    # sensitive_cooldown | divorce_shared_address | eviction_party |
    # public_adjuster_scope | restoration_contractor_scope | manual_block

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    pipelines = relationship(
        "LeadPipeline",
        back_populates="life_event",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    outreach_logs = relationship(
        "OutreachLog",
        back_populates="life_event",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "uq_life_events_source_record",
            "source",
            "source_record_id",
            unique=True,
        ),
        CheckConstraint(
            "event_type IN ('deed_transfer','moving_permit','estate',"
            "'probate_filing','mls_closing','building_permit','divorce_filing',"
            "'eviction','bankruptcy','obituary')",
            name="ck_life_events_event_type",
        ),
        CheckConstraint(
            "county IN ('miami-dade','broward','palm-beach')",
            name="ck_life_events_county",
        ),
        CheckConstraint(
            "pipeline_status IN ('new','matched','queued','contacted',"
            "'converted','suppressed','stale')",
            name="ck_life_events_pipeline_status",
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "source": self.source,
            "source_record_id": self.source_record_id,
            "event_type": self.event_type,
            "event_date": self.event_date.isoformat() if self.event_date else None,
            "county": self.county,
            "zip_code": self.zip_code,
            "address_line1": self.address_line1,
            "apn": self.apn,
            "prospect_name": self.prospect_name,
            "prospect_phone_e164": self.prospect_phone_e164,
            "prospect_email": self.prospect_email,
            "pii_hydrated": bool(self.pii_hydrated),
            "sensitive": bool(self.sensitive),
            "pipeline_status": self.pipeline_status,
            "suppressed_reason": self.suppressed_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class LeadPipeline(db.Model):
    """Kanban-style pipeline row for a single outreach opportunity."""

    __tablename__ = "lead_pipelines"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    life_event_id = Column(
        String(36),
        ForeignKey("life_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_operator_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    stage = Column(String(24), default="inbox", nullable=False, index=True)
    # inbox | qualified | outreach_drafted | outreach_sent | replied |
    # booked | closed_won | closed_lost | blocked
    priority = Column(String(10), default="normal", nullable=False)
    # low | normal | high | urgent
    projected_quote_low_cents = Column(Integer, nullable=True)
    projected_quote_high_cents = Column(Integer, nullable=True)
    last_stage_change_at = Column(DateTime, default=utcnow, nullable=False)
    claimed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    life_event = relationship("LifeEvent", back_populates="pipelines")
    assigned_operator = relationship("User", foreign_keys=[assigned_operator_id])
    outreach_logs = relationship(
        "OutreachLog",
        back_populates="pipeline",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "stage IN ('inbox','qualified','outreach_drafted','outreach_sent',"
            "'replied','booked','closed_won','closed_lost','blocked')",
            name="ck_lead_pipelines_stage",
        ),
        CheckConstraint(
            "priority IN ('low','normal','high','urgent')",
            name="ck_lead_pipelines_priority",
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "life_event_id": self.life_event_id,
            "assigned_operator_id": self.assigned_operator_id,
            "stage": self.stage,
            "priority": self.priority,
            "projected_quote_low_cents": self.projected_quote_low_cents,
            "projected_quote_high_cents": self.projected_quote_high_cents,
            "last_stage_change_at": self.last_stage_change_at.isoformat()
            if self.last_stage_change_at
            else None,
            "claimed_at": self.claimed_at.isoformat() if self.claimed_at else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class TCPAConsent(db.Model):
    """Opt-in audit trail for outbound contact.

    Source of truth for TCPA/FTSA compliance (spec 03 section 7). Every
    outbound SMS, call, and email MUST pass the consent check. A revoked
    row (``revoked_at IS NOT NULL``) is a hard block.
    """

    __tablename__ = "tcpa_consents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    # Identifier is EITHER phone (E.164) OR email (lower-cased). The check
    # constraint enforces at least one must be present.
    phone_e164 = Column(String(20), nullable=True, index=True)
    email = Column(String(255), nullable=True, index=True)
    channel = Column(String(16), nullable=False)
    # sms | call | email | direct_mail
    consent_method = Column(String(32), nullable=False)
    # express_written | web_form | sms_double_opt_in | existing_business |
    # inbound_call | manual_admin
    consent_source_url = Column(String(512), nullable=True)
    consent_ip = Column(String(45), nullable=True)
    consent_user_agent = Column(String(512), nullable=True)
    consent_text_hash = Column(String(64), nullable=True)
    # SHA-256 hash of the disclosure the user saw at opt-in.
    granted_at = Column(DateTime, default=utcnow, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    revoked_reason = Column(String(64), nullable=True)
    # sms_stop | email_unsubscribe | admin_block | ftc_dnc | fl_dnc | manual

    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "channel IN ('sms','call','email','direct_mail')",
            name="ck_tcpa_consents_channel",
        ),
        CheckConstraint(
            "consent_method IN ('express_written','web_form',"
            "'sms_double_opt_in','existing_business','inbound_call',"
            "'manual_admin')",
            name="ck_tcpa_consents_method",
        ),
        CheckConstraint(
            "(phone_e164 IS NOT NULL) OR (email IS NOT NULL)",
            name="ck_tcpa_consents_identifier_present",
        ),
        Index("ix_tcpa_consents_phone_channel", "phone_e164", "channel"),
        Index("ix_tcpa_consents_email_channel", "email", "channel"),
    )

    def is_active(self):
        return self.revoked_at is None

    def to_dict(self):
        return {
            "id": self.id,
            "phone_e164": self.phone_e164,
            "email": self.email,
            "channel": self.channel,
            "consent_method": self.consent_method,
            "granted_at": self.granted_at.isoformat() if self.granted_at else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "revoked_reason": self.revoked_reason,
            "active": self.is_active(),
        }


class OutreachLog(db.Model):
    """Every outbound attempt — sent, blocked, or still drafted.

    Blocked attempts are recorded (status='blocked', block_reason set) so
    TCPA audits can prove the gate rejected traffic.
    """

    __tablename__ = "outreach_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    life_event_id = Column(
        String(36),
        ForeignKey("life_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pipeline_id = Column(
        String(36),
        ForeignKey("lead_pipelines.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    channel = Column(String(16), nullable=False)
    # sms | call | email | direct_mail

    # Destination snapshot.
    to_phone_e164 = Column(String(20), nullable=True)
    to_email = Column(String(255), nullable=True)
    to_address_line1 = Column(String(255), nullable=True)

    subject = Column(String(255), nullable=True)
    body_rendered = Column(Text, nullable=True)

    regulatory_disclaimer = Column(Text, nullable=False)
    # Immutable per-send snapshot of the "not a public adjuster, not a
    # restoration contractor" disclosure (spec 03 positioning guardrail).

    tcpa_consent_id = Column(
        String(36),
        ForeignKey("tcpa_consents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status = Column(String(16), nullable=False, default="drafted")
    # drafted | queued | sent | delivered | bounced | opted_out | blocked |
    # failed
    block_reason = Column(String(64), nullable=True)
    # no_tcpa_consent | outside_calling_window | daily_cap_exceeded |
    # sensitive_cooldown | divorce_shared_address | public_adjuster_scope |
    # restoration_contractor_scope | provider_error | manual_block
    provider = Column(String(24), nullable=True)
    # twilio | postmark | lob | vapi
    provider_msg_id = Column(String(128), nullable=True)
    cost_cents = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    sent_at = Column(DateTime, nullable=True)

    life_event = relationship("LifeEvent", back_populates="outreach_logs")
    pipeline = relationship("LeadPipeline", back_populates="outreach_logs")
    tcpa_consent = relationship("TCPAConsent", foreign_keys=[tcpa_consent_id])

    __table_args__ = (
        CheckConstraint(
            "channel IN ('sms','call','email','direct_mail')",
            name="ck_outreach_logs_channel",
        ),
        CheckConstraint(
            "status IN ('drafted','queued','sent','delivered','bounced',"
            "'opted_out','blocked','failed')",
            name="ck_outreach_logs_status",
        ),
        Index("ix_outreach_logs_status_created", "status", "created_at"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "life_event_id": self.life_event_id,
            "pipeline_id": self.pipeline_id,
            "channel": self.channel,
            "to_phone_e164": self.to_phone_e164,
            "to_email": self.to_email,
            "to_address_line1": self.to_address_line1,
            "subject": self.subject,
            "body_rendered": self.body_rendered,
            "regulatory_disclaimer": self.regulatory_disclaimer,
            "tcpa_consent_id": self.tcpa_consent_id,
            "status": self.status,
            "block_reason": self.block_reason,
            "provider": self.provider,
            "provider_msg_id": self.provider_msg_id,
            "cost_cents": self.cost_cents,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
        }


# ---------------------------------------------------------------------------
# Landfill Routing Optimizer (spec: 06-landfill-routing-optimizer.md)
# ---------------------------------------------------------------------------
# LandfillFacility:   disposal sites (transfer station / landfill / MRF / C&D)
# TipFee:             per-category tipping fee snapshot per facility
# RouteOptimization: one solver run for a vehicle on a given day
# RouteStop:          ordered stops within a route (jobs + facility visits)
#
# NOTE: spec §4 uses PG-native enums/arrays. Codebase convention applied:
#   - UUID -> String(36) with generate_uuid default
#   - ENUM -> String + CheckConstraint
#   - JSONB / array -> JSON (portable across SQLite + PostgreSQL)
#   - Spec table `TippingFeeSnapshot` is renamed `TipFee` (build-spec shorthand).
#   - Fee accuracy: seed values are publicly-published or historical estimates;
#     production deployment must reconcile via weigh-ticket OCR (spec §2C).
# ---------------------------------------------------------------------------
class LandfillFacility(db.Model):
    """A disposal site (transfer station, landfill, MRF, WTE, or C&D yard)."""

    __tablename__ = "landfill_facilities"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(128), nullable=False, unique=True)
    # type values: transfer_station | landfill | mrf | c_and_d | wte
    type = Column(String(24), nullable=False, index=True)
    operator = Column(String(128), nullable=True)      # e.g. "Waste Management"
    permit_no = Column(String(64), nullable=True)

    address = Column(String(512), nullable=False)
    lat = Column(Float, nullable=False, index=True)
    lon = Column(Float, nullable=False, index=True)
    # county values: miami-dade | broward | palm-beach
    county = Column(String(32), nullable=False, index=True)

    # JSON list of accepted categories (msw, c_and_d, yard, bulky, metal,
    # appliance_w_freon, mattress, tires, concrete, drywall, mixed).
    accepts_categories = Column(JSON, nullable=False, default=list)

    # hours_json: {dow_int: {"open": "06:00", "close": "17:00"}} (0=Mon..6=Sun)
    hours_json = Column(JSON, nullable=True)
    phone = Column(String(32), nullable=True)
    # scale_method values: per_ton | per_cu_yd | flat
    scale_method = Column(String(16), nullable=False, default="per_ton")

    avg_turnaround_min = Column(Integer, nullable=False, default=25)
    notes = Column(Text, nullable=True)

    # Fee-accuracy gate: False on seed (publicly-published estimate);
    # flipped True after weigh-ticket OCR reconciliation confirms fee data.
    fee_accuracy_validated = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    tip_fees = relationship("TipFee", back_populates="facility", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "type IN ('transfer_station','landfill','mrf','c_and_d','wte')",
            name="ck_landfill_facility_type",
        ),
        CheckConstraint(
            "scale_method IN ('per_ton','per_cu_yd','flat')",
            name="ck_landfill_facility_scale_method",
        ),
        Index("ix_landfill_facility_county_type", "county", "type"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "operator": self.operator,
            "permit_no": self.permit_no,
            "address": self.address,
            "lat": self.lat,
            "lon": self.lon,
            "county": self.county,
            "accepts_categories": self.accepts_categories or [],
            "hours_json": self.hours_json,
            "phone": self.phone,
            "scale_method": self.scale_method,
            "avg_turnaround_min": self.avg_turnaround_min,
            "fee_accuracy_validated": self.fee_accuracy_validated,
            "notes": self.notes,
        }


class TipFee(db.Model):
    """Tipping fee snapshot per facility + waste category.

    Multiple historical snapshots allowed; solver uses the most-recent row
    whose effective window contains `now`.
    """

    __tablename__ = "tip_fees"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    facility_id = Column(
        String(36),
        ForeignKey("landfill_facilities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # category values: msw | c_and_d | yard | bulky | metal | appliance_w_freon |
    #                  mattress | tires | concrete | drywall | mixed
    category = Column(String(24), nullable=False, index=True)
    fee_amount = Column(Float, nullable=False)                     # dollars/unit
    # fee_unit values: per_ton | per_cu_yd | per_item | flat
    fee_unit = Column(String(16), nullable=False, default="per_ton")

    effective_from = Column(DateTime, default=utcnow, nullable=False)
    effective_to = Column(DateTime, nullable=True)                 # null == current

    # source values: scrape | phone | manual | api | seed
    source = Column(String(12), nullable=False, default="seed")
    confidence = Column(Float, nullable=False, default=0.70)       # 0..1

    captured_at = Column(DateTime, default=utcnow, nullable=False)

    facility = relationship("LandfillFacility", back_populates="tip_fees")

    __table_args__ = (
        CheckConstraint(
            "category IN ('msw','c_and_d','yard','bulky','metal','appliance_w_freon',"
            "'mattress','tires','concrete','drywall','mixed')",
            name="ck_tip_fee_category",
        ),
        CheckConstraint(
            "fee_unit IN ('per_ton','per_cu_yd','per_item','flat')",
            name="ck_tip_fee_unit",
        ),
        CheckConstraint(
            "source IN ('scrape','phone','manual','api','seed')",
            name="ck_tip_fee_source",
        ),
        Index(
            "ix_tip_fee_facility_category_captured",
            "facility_id", "category", "captured_at",
        ),
    )


class RouteOptimization(db.Model):
    """One solver run for a vehicle on a given day.

    Persists the chosen plan AND a baseline (closest-facility heuristic) for
    savings telemetry. savings_cents = baseline - predicted (positive = saved).
    """

    __tablename__ = "route_optimizations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    # Vehicle identifier -- contractor.id, fleet tag, or synthetic backtest id.
    # NOT FK'd to avoid hard dependency on contractor rows.
    vehicle_id = Column(String(36), nullable=True, index=True)
    vehicle_label = Column(String(64), nullable=True)              # "Truck #3"
    capacity_tons = Column(Float, nullable=False, default=4.0)     # stake body default

    run_date = Column(DateTime, default=utcnow, nullable=False, index=True)

    # candidates_json: list of
    #   {facility_id, facility_name, total_cost_cents,
    #    tipping_cents, fuel_cents, labor_cents, drive_minutes}
    candidates_json = Column(JSON, nullable=False, default=list)

    chosen_facility_id = Column(
        String(36),
        ForeignKey("landfill_facilities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    predicted_total_cost_cents = Column(Integer, nullable=False, default=0)
    predicted_tipping_cents = Column(Integer, nullable=False, default=0)
    predicted_fuel_cents = Column(Integer, nullable=False, default=0)
    predicted_labor_cents = Column(Integer, nullable=False, default=0)
    predicted_drive_minutes = Column(Integer, nullable=False, default=0)

    # Baseline = closest-facility heuristic (what Umuve does today).
    baseline_total_cost_cents = Column(Integer, nullable=False, default=0)
    baseline_facility_id = Column(
        String(36),
        ForeignKey("landfill_facilities.id", ondelete="SET NULL"),
        nullable=True,
    )

    savings_cents = Column(Integer, nullable=False, default=0)

    # status values: planned | dispatched | completed | voided
    status = Column(String(16), nullable=False, default="planned", index=True)

    solver_version = Column(String(32), nullable=False, default="v1")
    # solver_mode values: ortools_vrp | branch_and_bound_fallback | nearest
    solver_mode = Column(String(32), nullable=False, default="branch_and_bound_fallback")

    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    stops = relationship(
        "RouteStop",
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="RouteStop.sequence",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('planned','dispatched','completed','voided')",
            name="ck_route_optimization_status",
        ),
        CheckConstraint(
            "solver_mode IN ('ortools_vrp','branch_and_bound_fallback','nearest')",
            name="ck_route_optimization_solver_mode",
        ),
        Index("ix_route_opt_vehicle_date", "vehicle_id", "run_date"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "vehicle_id": self.vehicle_id,
            "vehicle_label": self.vehicle_label,
            "capacity_tons": self.capacity_tons,
            "run_date": self.run_date.isoformat() if self.run_date else None,
            "candidates": self.candidates_json or [],
            "chosen_facility_id": self.chosen_facility_id,
            "predicted_total_cost_cents": self.predicted_total_cost_cents,
            "predicted_tipping_cents": self.predicted_tipping_cents,
            "predicted_fuel_cents": self.predicted_fuel_cents,
            "predicted_labor_cents": self.predicted_labor_cents,
            "predicted_drive_minutes": self.predicted_drive_minutes,
            "baseline_total_cost_cents": self.baseline_total_cost_cents,
            "baseline_facility_id": self.baseline_facility_id,
            "savings_cents": self.savings_cents,
            "status": self.status,
            "solver_version": self.solver_version,
            "solver_mode": self.solver_mode,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "stops": [s.to_dict() for s in (self.stops or [])],
        }


class RouteStop(db.Model):
    """Ordered stop within a RouteOptimization.

    A stop is either a customer pickup (job) or a facility disposal visit.
    """

    __tablename__ = "route_stops"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    route_id = Column(
        String(36),
        ForeignKey("route_optimizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence = Column(Integer, nullable=False)                     # 0-based

    # stop_type values: pickup | facility | depot_start | depot_end
    stop_type = Column(String(16), nullable=False)

    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    facility_id = Column(
        String(36),
        ForeignKey("landfill_facilities.id", ondelete="SET NULL"),
        nullable=True,
    )

    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)

    distance_meters = Column(Integer, nullable=True)               # leg distance
    drive_seconds = Column(Integer, nullable=True)                 # leg drive time
    service_seconds = Column(Integer, nullable=True)               # time at stop
    estimated_load_tons = Column(Float, nullable=True)             # running load leaving

    earliest_arrival = Column(DateTime, nullable=True)
    latest_arrival = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)

    route = relationship("RouteOptimization", back_populates="stops")

    __table_args__ = (
        CheckConstraint(
            "stop_type IN ('pickup','facility','depot_start','depot_end')",
            name="ck_route_stop_type",
        ),
        Index("ix_route_stop_route_sequence", "route_id", "sequence", unique=True),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "route_id": self.route_id,
            "sequence": self.sequence,
            "stop_type": self.stop_type,
            "job_id": self.job_id,
            "facility_id": self.facility_id,
            "lat": self.lat,
            "lon": self.lon,
            "distance_meters": self.distance_meters,
            "drive_seconds": self.drive_seconds,
            "service_seconds": self.service_seconds,
            "estimated_load_tons": self.estimated_load_tons,
        }


# Life-Event Demand Trigger Engine models (LifeEvent, LeadPipeline,
# TCPAConsent, OutreachLog) are defined earlier in this file around
# L2311. A duplicate redefinition attempted here in an earlier pass was
# removed to avoid SQLAlchemy MetaData collisions. See spec 03.


# ===========================================================================
# B2B Commercial Portal (Spec 04) — multi-tenant SaaS at portal.goumuve.com
# ===========================================================================
#
# Every row on these tables is tenant-scoped via `org_id`. On Postgres we also
# apply Row-Level Security via migrate.py using `app.current_org_id` session
# var. On SQLite (dev/tests) the app-layer tenant_guard is the sole enforcer.
# Pattern follows the codebase: String(36) IDs + CheckConstraint for enums.


class Org(db.Model):
    __tablename__ = "orgs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(120), nullable=False)
    slug = Column(String(60), unique=True, nullable=False)
    tax_id = Column(String(32), nullable=True)
    billing_email = Column(String(120), nullable=False)
    billing_address = Column(JSON, nullable=True)
    stripe_customer_id = Column(String(64), unique=True, nullable=True)
    stripe_subscription_id = Column(String(64), nullable=True)
    tier = Column(String(20), nullable=False, default="starter")
    status = Column(String(20), nullable=False, default="trial")
    sso_provider = Column(String(32), nullable=True)
    sso_domain = Column(String(120), nullable=True)
    auto_pay = Column(Boolean, default=True)
    net_terms_days = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        CheckConstraint(
            "tier IN ('starter','pro','enterprise')", name="ck_org_tier"
        ),
        CheckConstraint(
            "status IN ('trial','active','past_due','paused','churned')",
            name="ck_org_status",
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "tax_id": self.tax_id,
            "billing_email": self.billing_email,
            "billing_address": self.billing_address,
            "tier": self.tier,
            "status": self.status,
            "sso_provider": self.sso_provider,
            "sso_domain": self.sso_domain,
            "auto_pay": self.auto_pay,
            "net_terms_days": self.net_terms_days,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class OrgMember(db.Model):
    __tablename__ = "org_members"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    org_id = Column(String(36), ForeignKey("orgs.id", ondelete="CASCADE"),
                    nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    role = Column(String(20), nullable=False)
    scopes = Column(JSON, nullable=True, default=list)
    invited_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"),
                        nullable=True)
    invite_token = Column(String(80), unique=True, nullable=True, index=True)
    invited_at = Column(DateTime, default=utcnow)
    joined_at = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "role IN ('owner','admin','operator','viewer')",
            name="ck_orgmember_role",
        ),
        Index("ix_orgmember_org_user", "org_id", "user_id", unique=True),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "org_id": self.org_id,
            "user_id": self.user_id,
            "role": self.role,
            "scopes": self.scopes or [],
            "joined_at": self.joined_at.isoformat() if self.joined_at else None,
        }


class PortalProperty(db.Model):
    """B2B portal property (spec 04). Named PortalProperty to avoid colliding
    with the Python `property` builtin and any future residential model."""
    __tablename__ = "portal_properties"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    org_id = Column(String(36), ForeignKey("orgs.id", ondelete="CASCADE"),
                    nullable=False, index=True)
    name = Column(String(120), nullable=False)
    address_line1 = Column(String(160), nullable=True)
    address_line2 = Column(String(160), nullable=True)
    city = Column(String(60), nullable=True)
    state = Column(String(2), nullable=True)
    zip = Column(String(10), nullable=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    external_ref = Column(String(64), nullable=True)
    source = Column(String(16), nullable=True, default="manual")
    unit_count = Column(Integer, default=1)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    def to_dict(self):
        return {
            "id": self.id, "org_id": self.org_id, "name": self.name,
            "address_line1": self.address_line1,
            "address_line2": self.address_line2,
            "city": self.city, "state": self.state, "zip": self.zip,
            "lat": self.lat, "lng": self.lng,
            "external_ref": self.external_ref, "source": self.source,
            "unit_count": self.unit_count, "active": self.active,
        }


class Contract(db.Model):
    __tablename__ = "contracts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    org_id = Column(String(36), ForeignKey("orgs.id", ondelete="CASCADE"),
                    nullable=False, index=True)
    tier = Column(String(20), nullable=False)
    monthly_base_cents = Column(Integer, nullable=False)
    metered_per_pickup_cents = Column(Integer, default=0)
    metered_per_ton_cents = Column(Integer, default=0)
    included_pickups = Column(Integer, default=0)
    pricing_overrides = Column(JSON, nullable=True, default=dict)
    effective_from = Column(DateTime, nullable=False, default=utcnow)
    effective_to = Column(DateTime, nullable=True)
    signed_pdf_s3_key = Column(String(240), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        CheckConstraint(
            "tier IN ('starter','pro','enterprise')", name="ck_contract_tier"
        ),
    )


def active_contract_for_org(org_id, when=None):
    """Return the org's currently-effective Contract (or None).

    A contract is effective when effective_from <= when and effective_to is
    null or >= when. Newest effective_from wins if several overlap.
    """
    if not org_id:
        return None
    when = when or utcnow()
    return (
        Contract.query
        .filter(Contract.org_id == org_id, Contract.effective_from <= when)
        .filter((Contract.effective_to.is_(None)) | (Contract.effective_to >= when))
        .order_by(Contract.effective_from.desc())
        .first()
    )


class PortalInvoice(db.Model):
    """B2B portal invoice. Named PortalInvoice to avoid conflict with any
    residential invoice in use by the booking engine."""
    __tablename__ = "portal_invoices"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    org_id = Column(String(36), ForeignKey("orgs.id", ondelete="CASCADE"),
                    nullable=False, index=True)
    number = Column(String(24), unique=True, nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    subtotal_cents = Column(Integer, nullable=False, default=0)
    tax_cents = Column(Integer, default=0)
    total_cents = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="draft")
    stripe_invoice_id = Column(String(64), nullable=True)
    due_at = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','open','paid','past_due','void')",
            name="ck_portal_invoice_status",
        ),
    )

    line_items = relationship(
        "PortalInvoiceLineItem", backref="invoice",
        cascade="all, delete-orphan", lazy="joined",
    )

    def to_dict(self, include_lines=False):
        data = {
            "id": self.id, "org_id": self.org_id, "number": self.number,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "subtotal_cents": self.subtotal_cents,
            "tax_cents": self.tax_cents,
            "total_cents": self.total_cents,
            "status": self.status,
            "due_at": self.due_at.isoformat() if self.due_at else None,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
        }
        if include_lines:
            data["line_items"] = [li.to_dict() for li in self.line_items]
        return data


class PortalInvoiceLineItem(db.Model):
    __tablename__ = "portal_invoice_line_items"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    invoice_id = Column(String(36),
                        ForeignKey("portal_invoices.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    job_id = Column(String(36),
                    ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    property_id = Column(String(36),
                         ForeignKey("portal_properties.id", ondelete="SET NULL"),
                         nullable=True)
    description = Column(String(240), nullable=True)
    quantity = Column(Float, default=1.0)
    unit_cents = Column(Integer, nullable=False, default=0)
    amount_cents = Column(Integer, nullable=False, default=0)

    def to_dict(self):
        return {
            "id": self.id, "job_id": self.job_id,
            "property_id": self.property_id,
            "description": self.description,
            "quantity": self.quantity,
            "unit_cents": self.unit_cents,
            "amount_cents": self.amount_cents,
        }


class PortalPaymentMethod(db.Model):
    __tablename__ = "portal_payment_methods"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    org_id = Column(String(36), ForeignKey("orgs.id", ondelete="CASCADE"),
                    nullable=False, index=True)
    kind = Column(String(16), nullable=False)
    stripe_payment_method_id = Column(String(64), nullable=True)
    last4 = Column(String(4), nullable=True)
    bank_name = Column(String(60), nullable=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        CheckConstraint(
            "kind IN ('ach','card','check')", name="ck_portal_pm_kind"
        ),
    )


class PortalAuditLog(db.Model):
    __tablename__ = "portal_audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    org_id = Column(String(36), index=True, nullable=True)
    user_id = Column(String(36), nullable=True)
    action = Column(String(60), nullable=False)
    object_type = Column(String(40), nullable=True)
    object_id = Column(String(36), nullable=True)
    before = Column(JSON, nullable=True)
    after = Column(JSON, nullable=True)
    ip = Column(String(45), nullable=True)
    user_agent = Column(String(240), nullable=True)
    created_at = Column(DateTime, default=utcnow, index=True)


class PortalApiKey(db.Model):
    __tablename__ = "portal_api_keys"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    org_id = Column(String(36), ForeignKey("orgs.id", ondelete="CASCADE"),
                    nullable=False, index=True)
    name = Column(String(80), nullable=True)
    prefix = Column(String(16), nullable=True)
    hashed_key = Column(String(128), nullable=False, unique=True)
    scopes = Column(JSON, nullable=True, default=list)
    last_used_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    created_by = Column(String(36),
                        ForeignKey("users.id", ondelete="SET NULL"),
                        nullable=True)
    created_at = Column(DateTime, default=utcnow)


class OperatorLead(db.Model):
    """A prospective hauler/operator to recruit onto the platform.

    Powers the daily automated outreach engine (operator_outreach.py): sourced
    from Google Places + light website scraping, contacted by compliant B2B
    email on a drip sequence. Suppression is permanent via status.
    """
    __tablename__ = "operator_leads"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    business_name = Column(String(200), nullable=True)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(40), nullable=True)
    website = Column(String(300), nullable=True)
    place_id = Column(String(120), nullable=True, unique=True, index=True)  # Google dedup key
    source = Column(String(16), nullable=False, default="places")  # places|scrape|upload
    category = Column(String(60), nullable=True)
    city = Column(String(80), nullable=True)
    zip = Column(String(10), nullable=True, index=True)
    # new -> qualified -> contacted -> replied -> converted; or skipped/bounced/unsubscribed
    status = Column(String(20), nullable=False, default="new", index=True)
    drip_stage = Column(Integer, nullable=False, default=0)  # touches sent (0..3)
    last_contacted_at = Column(DateTime, nullable=True)
    unsubscribe_token = Column(String(48), nullable=True, unique=True, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, index=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "business_name": self.business_name,
            "email": self.email,
            "phone": self.phone,
            "website": self.website,
            "source": self.source,
            "city": self.city,
            "zip": self.zip,
            "status": self.status,
            "drip_stage": self.drip_stage,
            "last_contacted_at": self.last_contacted_at.isoformat() if self.last_contacted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class B2BLead(db.Model):
    """A prospective COMMERCIAL CUSTOMER for the B2B portal (property managers,
    restaurants, retail, construction, offices — businesses with recurring junk).

    Counterpart to OperatorLead (which recruits haulers); this funnel drives
    portal.goumuve.com signups. Same compliant daily outreach machinery
    (b2b_outreach.py): Places + scrape sourcing, drip email, suppression.
    """
    __tablename__ = "b2b_leads"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    business_name = Column(String(200), nullable=True)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(40), nullable=True)
    website = Column(String(300), nullable=True)
    place_id = Column(String(120), nullable=True, unique=True, index=True)
    source = Column(String(16), nullable=False, default="places")
    category = Column(String(60), nullable=True)  # vertical: property_mgmt|restaurant|retail|...
    city = Column(String(80), nullable=True)
    zip = Column(String(10), nullable=True, index=True)
    status = Column(String(20), nullable=False, default="new", index=True)
    drip_stage = Column(Integer, nullable=False, default=0)
    last_contacted_at = Column(DateTime, nullable=True)
    unsubscribe_token = Column(String(48), nullable=True, unique=True, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, index=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "business_name": self.business_name,
            "email": self.email,
            "phone": self.phone,
            "website": self.website,
            "source": self.source,
            "category": self.category,
            "city": self.city,
            "zip": self.zip,
            "status": self.status,
            "drip_stage": self.drip_stage,
            "last_contacted_at": self.last_contacted_at.isoformat() if self.last_contacted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ReferralPayout(db.Model):
    """Ledger of actual referral-bonus transfers — one row per (referral, role).

    The precise source of truth for referral spend (vs status-based estimates).
    Upserted by payments.pay_referral_bonus(): status 'paid' carries the Stripe
    transfer id; 'deferred'/'failed' mean owed-but-not-sent.
    """
    __tablename__ = "referral_payouts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    referral_id = Column(String(36), ForeignKey("referrals.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"),
                     nullable=True, index=True)
    role = Column(String(12), nullable=False)  # referrer | referee
    amount = Column(Float, nullable=False, default=0.0)
    currency = Column(String(8), nullable=False, default="usd")
    status = Column(String(12), nullable=False, default="deferred")  # paid | failed | deferred
    stripe_transfer_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        Index("ix_referral_payout_ref_role", "referral_id", "role", unique=True),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "referral_id": self.referral_id,
            "user_id": self.user_id,
            "role": self.role,
            "amount": self.amount,
            "status": self.status,
            "stripe_transfer_id": self.stripe_transfer_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AutomationEvent(db.Model):
    """Idempotence markers for automation sends/alerts (ops sentinel, durable
    review sends, referral nudges, trial nudges). One row = this (kind,
    subject) already fired; unique constraint makes every automation
    exactly-once without per-feature Boolean columns on hot tables."""

    __tablename__ = "automation_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    kind = Column(String(60), nullable=False)
    subject_type = Column(String(30), nullable=False, default="job")
    subject_id = Column(String(64), nullable=False)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        db.UniqueConstraint("kind", "subject_type", "subject_id",
                            name="uq_automation_event"),
        db.Index("ix_automation_events_kind_subject", "kind", "subject_id"),
    )


class Subscriber(db.Model):
    """Newsletter / mailing-list capture from the public /api/subscribe
    endpoint (blueprint existed since launch prep but this model was never
    written, so the route 500'd on import and was left unregistered)."""

    __tablename__ = "subscribers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=True)
    source = Column(String(50), nullable=True, default="website")
    list_name = Column(String(50), nullable=True, default="newsletter")
    status = Column(String(20), nullable=False, default="active")  # active|unsubscribed
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "source": self.source,
            "list": self.list_name,
            "status": self.status,
        }


class Partner(db.Model):
    """Partnership-program signups (realtors, property managers, movers…)
    from goumuve.com/partners — same missing-model story as Subscriber."""

    __tablename__ = "partners"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(120), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(40), nullable=True)
    brokerage = Column(String(200), nullable=True)
    coverage_areas = Column(Text, nullable=True)
    partner_type = Column(String(40), nullable=False, default="other")
    status = Column(String(20), nullable=False, default="pending")  # pending|approved|rejected
    referral_code = Column(String(20), unique=True, nullable=True, index=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "brokerage": self.brokerage,
            "coverage_areas": self.coverage_areas,
            "partner_type": self.partner_type,
            "status": self.status,
            "referral_code": self.referral_code,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Agreement(db.Model):
    """B2B service agreement with in-app e-signature.

    Follows the ESIGN/UETA click-to-sign pattern: explicit consent language,
    signer identity + audit trail (IP, user agent, timestamp), and an
    immutable executed snapshot (HTML + SHA-256) retained for both parties.
    """

    __tablename__ = "agreements"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    token = Column(String(64), unique=True, nullable=False, index=True)
    client_company = Column(String(200), nullable=False)
    client_name = Column(String(120), nullable=False)
    client_email = Column(String(255), nullable=False)
    client_phone = Column(String(40), nullable=True)
    template = Column(String(40), nullable=False, default="commercial_v1")
    status = Column(String(20), nullable=False, default="sent")  # sent|viewed|signed|void
    created_at = Column(DateTime, default=utcnow)
    viewed_at = Column(DateTime, nullable=True)
    signed_at = Column(DateTime, nullable=True)
    signer_name = Column(String(120), nullable=True)
    signer_title = Column(String(120), nullable=True)
    signer_ip = Column(String(64), nullable=True)
    signer_user_agent = Column(String(255), nullable=True)
    signature_image = Column(Text, nullable=True)   # drawn signature (PNG data-URL)
    document_sha256 = Column(String(64), nullable=True)
    executed_html = Column(Text, nullable=True)     # immutable signed snapshot

    def to_dict(self):
        return {
            "id": self.id,
            "token": self.token,
            "client_company": self.client_company,
            "client_name": self.client_name,
            "client_email": self.client_email,
            "client_phone": self.client_phone,
            "template": self.template,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "viewed_at": self.viewed_at.isoformat() if self.viewed_at else None,
            "signed_at": self.signed_at.isoformat() if self.signed_at else None,
            "signer_name": self.signer_name,
            "signer_title": self.signer_title,
        }


class CallProspect(db.Model):
    """A demand-side business prospect worked by the VA call desk (/va/calls).

    Seeded from researched call lists via the admin import endpoint. The
    console serves one prospect at a time (due follow-ups first, then fresh
    rows by tier) and every logged outcome updates status + schedules the
    next touch, so the follow-up cadence lives here instead of in a
    spreadsheet.
    """
    __tablename__ = "call_prospects"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tier = Column(Integer, nullable=False, default=2, index=True)  # 1 best
    category = Column(String(60), nullable=False, default="", index=True)
    company = Column(String(200), nullable=False)
    phone = Column(String(40), nullable=False)
    phone_digits = Column(String(10), nullable=False, unique=True, index=True)  # dedup key
    city = Column(String(80), nullable=True)
    contact_name = Column(String(120), nullable=True)
    why = Column(Text, nullable=True)      # why they need hauling
    angle = Column(Text, nullable=True)    # tailored call angle
    # queued -> (interested) -> converted, or dead
    status = Column(String(20), nullable=False, default="queued", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    last_outcome = Column(String(20), nullable=True)
    last_note = Column(Text, nullable=True)
    last_called_at = Column(DateTime, nullable=True)
    last_texted_at = Column(DateTime, nullable=True)
    email = Column(String(254), nullable=True)   # decision-maker email, captured on calls
    direct_phone = Column(String(40), nullable=True)  # decision-maker cell (vs. front desk)
    last_emailed_at = Column(DateTime, nullable=True)
    next_followup_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "tier": self.tier,
            "category": self.category,
            "company": self.company,
            "phone": self.phone,
            "city": self.city,
            "contact_name": self.contact_name,
            "why": self.why,
            "angle": self.angle,
            "status": self.status,
            "attempts": self.attempts,
            "last_outcome": self.last_outcome,
            "last_note": self.last_note,
            "last_called_at": self.last_called_at.isoformat() if self.last_called_at else None,
            "last_texted_at": self.last_texted_at.isoformat() if self.last_texted_at else None,
            "email": self.email,
            "direct_phone": self.direct_phone,
            "last_emailed_at": self.last_emailed_at.isoformat() if self.last_emailed_at else None,
            "next_followup_at": self.next_followup_at.isoformat() if self.next_followup_at else None,
        }


class CallAttempt(db.Model):
    """One logged call against a CallProspect — the audit trail behind stats."""
    __tablename__ = "call_attempts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    prospect_id = Column(String(36), ForeignKey("call_prospects.id"), nullable=False, index=True)
    outcome = Column(String(20), nullable=False)
    note = Column(Text, nullable=True)
    va_name = Column(String(80), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
