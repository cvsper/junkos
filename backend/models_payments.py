"""Money-path ledger tables (audit F06 / F13 / F14).

PaymentAttempt — one immutable row per PaymentIntent we asked Stripe for.
    Persisted BEFORE the Stripe call so a crash / retry / second tab can never
    produce an untracked payable intent; the Stripe idempotency key is derived
    from the row id.  Payment.stripe_payment_intent_id stays "the current
    one" for existing readers; this table is the history.

Payout — one row per (job, recipient) obligation: driver, fleet operator,
    referral.  Carries the Stripe transfer id, so a transfer that happened is
    never just a status label on the Payment row.

Imported by routes.payments at module load so db.create_all() (server.py /
tests) sees the tables; migrate.py carries the matching DDL for standalone
runs, mirroring models_sameday's hauler_standby.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, UniqueConstraint, Index

from models import db, generate_uuid


def _now():
    return datetime.now(timezone.utc)


ATTEMPT_OPEN = ("created", "requires_action")
ATTEMPT_TERMINAL = ("succeeded", "canceled", "failed", "superseded", "cancel_failed")


class PaymentAttempt(db.Model):
    __tablename__ = "payment_attempts"
    __table_args__ = (
        UniqueConstraint("job_id", "client_submission_key", name="uq_attempt_job_submission"),
        Index("ix_payment_attempts_job_status", "job_id", "status"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_id = Column(String(36), nullable=False, index=True)
    payment_id = Column(String(36), nullable=True, index=True)
    client_submission_key = Column(String(64), nullable=False)
    stripe_intent_id = Column(String(255), nullable=True, unique=True)
    client_secret = Column(String(255), nullable=True)
    amount_cents = Column(Integer, nullable=False, default=0)
    currency = Column(String(8), nullable=False, default="usd")
    # created | requires_action | succeeded | canceled | failed | superseded | cancel_failed
    status = Column(String(24), nullable=False, default="created", index=True)
    actor = Column(String(24), nullable=True)          # owner | checkout_token
    user_id = Column(String(36), nullable=True)
    superseded_by = Column(String(36), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    @property
    def is_open(self):
        return self.status in ATTEMPT_OPEN

    def to_dict(self):
        return {
            "id": self.id, "job_id": self.job_id, "payment_id": self.payment_id,
            "submission_key": self.client_submission_key,
            "stripe_intent_id": self.stripe_intent_id,
            "amount_cents": self.amount_cents, "currency": self.currency,
            "status": self.status, "superseded_by": self.superseded_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Payout(db.Model):
    __tablename__ = "payouts"
    __table_args__ = (
        UniqueConstraint("job_id", "recipient_type", name="uq_payout_job_recipient"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_id = Column(String(36), nullable=False, index=True)
    payment_id = Column(String(36), nullable=True, index=True)
    recipient_type = Column(String(16), nullable=False)       # driver | operator | referral
    contractor_id = Column(String(36), nullable=True, index=True)
    operator_id = Column(String(36), nullable=True, index=True)
    amount_cents = Column(Integer, nullable=False, default=0)
    currency = Column(String(8), nullable=False, default="usd")
    stripe_transfer_id = Column(String(255), nullable=True)
    # pending | transferred | failed | pending_connect | paid_manual | unavailable
    status = Column(String(24), nullable=False, default="pending", index=True)
    method = Column(String(20), nullable=True)                 # transfer | manual | dev
    idempotency_key = Column(String(80), nullable=True)
    reversal_required = Column(Boolean, nullable=False, default=False)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    def to_dict(self):
        return {
            "id": self.id, "job_id": self.job_id, "payment_id": self.payment_id,
            "recipient_type": self.recipient_type,
            "contractor_id": self.contractor_id, "operator_id": self.operator_id,
            "amount_cents": self.amount_cents, "currency": self.currency,
            "stripe_transfer_id": self.stripe_transfer_id, "status": self.status,
            "method": self.method, "reversal_required": bool(self.reversal_required),
            "last_error": self.last_error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
