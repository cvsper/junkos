"""Persistent auth state (audit F19, 2026-09-10).

Phone OTP challenges and password-reset tokens used to live in process
memory (``verification_codes`` / ``users_db`` dicts in auth_routes.py), so a
restart or a second gunicorn worker forgot them and the same phone minted a
different user id each time. Both now live in the database, hashed, with a
TTL, attempt counters and per-identity throttling.

Imported by auth_routes.py (the same way server.py imports models_sameday)
so ``db.create_all()`` sees the tables before the first request.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import secrets

from sqlalchemy import Column, String, Integer, DateTime, Index

from models import db, generate_uuid


def _utcnow():
    return _dt.datetime.utcnow()


def hash_secret(salt: str, value: str) -> str:
    """Salted SHA-256 for short-lived one-time secrets (OTP codes, reset
    tokens). These are high-entropy / rate-limited so a KDF is unnecessary;
    the salt stops cross-row comparison of identical codes."""
    return hashlib.sha256("{}:{}".format(salt, value).encode("utf-8")).hexdigest()


class OtpChallenge(db.Model):
    """One SMS login code. ``identity`` is the normalized E.164 phone."""
    __tablename__ = "otp_challenges"
    __table_args__ = (Index("ix_otp_identity_created", "identity", "created_at"),)

    id = Column(String(36), primary_key=True, default=generate_uuid)
    identity = Column(String(32), nullable=False, index=True)
    salt = Column(String(32), nullable=False)
    code_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=5)
    consumed_at = Column(DateTime, nullable=True)     # redeemed, superseded or locked out
    requester_ip = Column(String(45), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow, index=True)

    @classmethod
    def issue(cls, identity: str, code: str, ttl_minutes: int, requester_ip=None, max_attempts: int = 5):
        salt = secrets.token_hex(8)
        now = _utcnow()
        return cls(
            identity=identity,
            salt=salt,
            code_hash=hash_secret(salt, code),
            expires_at=now + _dt.timedelta(minutes=ttl_minutes),
            attempts=0,
            max_attempts=max_attempts,
            requester_ip=requester_ip,
            created_at=now,
        )

    def matches(self, code: str) -> bool:
        return secrets.compare_digest(self.code_hash, hash_secret(self.salt, code or ""))

    @property
    def is_expired(self) -> bool:
        return _utcnow() > self.expires_at

    @property
    def is_locked(self) -> bool:
        return (self.attempts or 0) >= (self.max_attempts or 5)


class PasswordResetToken(db.Model):
    """Single-use, expiring password-reset credential. Only the hash is stored;
    the raw token goes to the account's email and nowhere else."""
    __tablename__ = "password_reset_tokens"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    requester_ip = Column(String(45), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow, index=True)

    # Reset tokens are 32 random bytes; the hash salt is a fixed domain tag
    # so redemption can look the row up by hash without knowing the user.
    _DOMAIN = "umuve-pwreset"

    @classmethod
    def hash_token(cls, raw_token: str) -> str:
        return hash_secret(cls._DOMAIN, raw_token or "")

    @classmethod
    def issue(cls, user_id: str, ttl_minutes: int, requester_ip=None):
        """Return (row, raw_token). Caller persists the row and emails the raw token."""
        raw = secrets.token_urlsafe(32)
        row = cls(
            user_id=user_id,
            token_hash=cls.hash_token(raw),
            expires_at=_utcnow() + _dt.timedelta(minutes=ttl_minutes),
            requester_ip=requester_ip,
        )
        return row, raw

    @property
    def is_valid(self) -> bool:
        return self.used_at is None and _utcnow() <= self.expires_at
