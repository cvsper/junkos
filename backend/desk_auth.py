"""Desk identity: real accounts with roles, an audit trail, and a passcode
fallback that can be switched off.

Roles on the desk:
  va       — works the queue; sees their own hours
  manager  — everything a VA can do, plus everyone's hours, audit, flags
  admin    — the existing platform admin role; same as manager on the desk

Identity resolution (desk_identity):
  1. Authorization: Bearer <JWT> from /api/desk/login → the User row
     (role must be va/manager/admin, status active).
  2. Otherwise, if the passcode_login flag is on, the legacy shared passcode
     in the JSON body ("code") + a typed va_name. This exists so nothing
     breaks the day accounts roll out; turn the flag off once every VA has
     a login.

Every mutation on the desk calls audit(...). Twilio webhooks audit as
via="twilio"; scheduled jobs as via="system".
"""
from __future__ import annotations

import hmac
import logging
import os
import secrets
from functools import wraps

from flask import g, jsonify, request

from models import db, User, AuditEvent

logger = logging.getLogger(__name__)

DESK_ROLES = ("va", "manager", "admin")
MANAGER_ROLES = ("manager", "admin")


def _passcode_ok(supplied):
    expected = os.environ.get("TRIXIE_ASSISTANT_PASSCODE", "")
    if not expected:
        return False
    return hmac.compare_digest(str(supplied or ""), str(expected))


def _passcode_login_enabled():
    try:
        from flags import flag
        return flag("passcode_login")
    except Exception:
        return True


def _display_name(user):
    if user.name:
        return user.name.strip().split(" ")[0][:80] if len(user.name.strip()) > 0 else user.email
    return (user.email or "").split("@")[0][:80]


def desk_identity(data=None):
    """→ {"user_id","name","role","via"} or None. Cached on the request (not on
    flask.g — the test client reuses one app context across requests)."""
    cached = request.environ.get("desk.ident") if request else None
    if cached is not None:
        return cached or None
    data = data if data is not None else (request.get_json(silent=True) or {})
    ident = None
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if token:
        try:
            from auth_routes import verify_token
            user_id = verify_token(token)
        except Exception:
            user_id = None
        user = db.session.get(User, user_id) if user_id else None
        if user and user.role in DESK_ROLES and getattr(user, "status", "active") == "active":
            ident = {"user_id": user.id, "name": _display_name(user), "full_name": user.name or "",
                     "email": user.email, "role": user.role, "via": "jwt"}
    if ident is None and _passcode_login_enabled() and _passcode_ok(data.get("code")):
        name = (data.get("va_name") or "").strip()[:80]
        ident = {"user_id": None, "name": name, "full_name": name, "email": None,
                 "role": "va", "via": "passcode"}
    request.environ["desk.ident"] = ident or False
    return ident


def desk_va_name(data=None):
    ident = desk_identity(data)
    return (ident or {}).get("name") or ""


def is_manager(ident):
    return bool(ident) and ident.get("role") in MANAGER_ROLES


def require_desk(roles=None):
    """Decorator for JSON desk endpoints. Passes ident=... to the view."""
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            ident = desk_identity()
            if not ident:
                return jsonify({"error": "Sign in to the desk first."}), 401
            if roles and ident["role"] not in roles:
                return jsonify({"error": "That needs a manager."}), 403
            return f(*args, ident=ident, **kwargs)
        return wrapper
    return deco


def audit(action, target_type=None, target_id=None, meta=None, via=None, actor=None):
    """Append an audit event. Never raises; never blocks the request."""
    try:
        ident = actor if actor is not None else (request.environ.get("desk.ident") or None if request else None)
        ev = AuditEvent(
            actor_user_id=(ident or {}).get("user_id"),
            actor_name=(ident or {}).get("name") or ((ident or {}).get("email")),
            actor_role=(ident or {}).get("role"),
            via=via or (ident or {}).get("via") or "system",
            action=str(action)[:60],
            target_type=(str(target_type)[:40] if target_type else None),
            target_id=(str(target_id)[:64] if target_id else None),
            meta=meta or None,
            ip=(request.headers.get("X-Forwarded-For", request.remote_addr or "") or "").split(",")[0].strip()[:64]
            if request else None,
        )
        db.session.add(ev)
        db.session.commit()
    except Exception:
        logger.exception("audit write failed for %s", action)
        try:
            db.session.rollback()
        except Exception:
            pass


def create_desk_user(email, name, role="va", password=None):
    """Create or update a desk account. Returns (user, temp_password_or_None)."""
    email = (email or "").strip().lower()
    if role not in DESK_ROLES:
        raise ValueError("role must be va or manager")
    user = User.query.filter_by(email=email).first()
    temp = None
    if user is None:
        user = User(email=email, name=(name or "").strip()[:255] or None, role=role, status="active")
        temp = password or secrets.token_urlsafe(9)
        user.set_password(temp)
        db.session.add(user)
    else:
        if name:
            user.name = name.strip()[:255]
        if user.role not in ("admin",):
            user.role = role
        user.status = "active"
        if password:
            user.set_password(password)
            temp = password
    db.session.commit()
    return user, temp
