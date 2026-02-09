"""
JunkOS SQLAlchemy Models
All database entities for the on-demand junk removal marketplace.
"""

import uuid
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

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    contractor_profile = relationship("Contractor", back_populates="user", uselist=False, lazy="joined")
    notifications = relationship("Notification", back_populates="user", lazy="dynamic")
    ratings_given = relationship("Rating", foreign_keys="Rating.from_user_id", back_populates="from_user", lazy="dynamic")
    ratings_received = relationship("Rating", foreign_keys="Rating.to_user_id", back_populates="to_user", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def to_dict(self, include_private=False):
        data = {
            "id": self.id,
            "email": self.email,
            "phone": self.phone,
            "name": self.name,
            "role": self.role,
            "avatar_url": self.avatar_url,
            "status": self.status,
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

    # Operator fields
    is_operator = Column(Boolean, default=False)
    operator_id = Column(String(36), ForeignKey("contractors.id", ondelete="SET NULL"), nullable=True, index=True)
    operator_commission_rate = Column(Float, default=0.15)

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
            "is_online": self.is_online,
            "current_lat": self.current_lat,
            "current_lng": self.current_lng,
            "avg_rating": self.avg_rating,
            "total_jobs": self.total_jobs,
            "approval_status": self.approval_status,
            "availability_schedule": self.availability_schedule or {},
            "is_operator": self.is_operator or False,
            "operator_id": self.operator_id,
            "operator_commission_rate": self.operator_commission_rate or 0.15,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
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

    scheduled_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    base_price = Column(Float, default=0.0)
    item_total = Column(Float, default=0.0)
    volume_price = Column(Float, default=0.0)
    service_fee = Column(Float, default=0.0)
    surge_multiplier = Column(Float, default=1.0)
    total_price = Column(Float, default=0.0)

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    customer = relationship("User", foreign_keys=[customer_id], backref="customer_jobs")
    driver = relationship("Contractor", foreign_keys=[driver_id], back_populates="jobs")
    operator_rel = relationship("Contractor", foreign_keys=[operator_id], backref="operator_jobs")
    payment = relationship("Payment", back_populates="job", uselist=False, lazy="joined")
    rating = relationship("Rating", back_populates="job", uselist=False, lazy="joined")

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
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "base_price": self.base_price,
            "item_total": self.item_total,
            "volume_price": self.volume_price,
            "service_fee": self.service_fee,
            "surge_multiplier": self.surge_multiplier,
            "total_price": self.total_price,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
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
