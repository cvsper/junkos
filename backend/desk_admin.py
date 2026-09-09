"""Desk accounts, flags, audit, health — the management side of the Call Desk.

  POST /api/desk/login            {email,password} → token + who
  GET  /api/desk/me               who am I (JWT or passcode)
  POST /api/va/flags              feature flags the desk should honor
  GET  /api/admin/desk-users      list desk accounts            (manager/admin)
  POST /api/admin/desk-users      create/update a desk account  (manager/admin)
  POST /api/admin/flags           {name, value: true|false|null} (manager/admin)
  GET  /api/admin/audit           ?days=7&actor=&action=       (manager/admin)
  GET  /api/health/desk           dependency status, no secrets (public)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from models import db, User, AuditEvent
from desk_auth import (desk_identity, require_desk, audit, create_desk_user,
                       DESK_ROLES, MANAGER_ROLES)

try:
    from extensions import limiter
except Exception:  # pragma: no cover
    limiter = None

logger = logging.getLogger(__name__)
deskadmin_bp = Blueprint("deskadmin", __name__)
_login_limit = limiter.limit("10 per minute; 60 per hour") if limiter is not None else (lambda f: f)


@deskadmin_bp.route("/api/desk/login", methods=["POST"])
@_login_limit
def desk_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    user = User.query.filter_by(email=email).first() if email else None
    if not user or not user.password_hash or not user.check_password(password):
        audit("login_failed", "user", email, via="jwt", actor={"name": email, "role": None})
        return jsonify({"error": "That email and password didn't match."}), 401
    if user.role not in DESK_ROLES:
        return jsonify({"error": "This account isn't set up for the desk. Ask a manager."}), 403
    if getattr(user, "status", "active") != "active":
        return jsonify({"error": "This account is disabled."}), 403
    from auth_routes import generate_token
    token = generate_token(user.id)
    ident = {"user_id": user.id, "name": (user.name or user.email).split(" ")[0], "role": user.role, "via": "jwt"}
    audit("login", "user", user.id, actor=ident)
    return jsonify({"token": token, "name": ident["name"], "full_name": user.name or "",
                    "email": user.email, "role": user.role,
                    "is_manager": user.role in MANAGER_ROLES}), 200


@deskadmin_bp.route("/api/desk/change-password", methods=["POST"])
@_login_limit
def desk_change_password():
    """{current, new} — account holders only (not the passcode)."""
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident or ident["via"] != "jwt":
        return jsonify({"error": "Sign in with your account to change the password."}), 401
    user = db.session.get(User, ident["user_id"])
    if not user or not user.check_password(data.get("current") or ""):
        audit("password_change_failed", "user", ident["user_id"])
        return jsonify({"error": "Your current password didn't match."}), 401
    new = data.get("new") or ""
    if len(new) < 8:
        return jsonify({"error": "Use at least 8 characters."}), 400
    if new == (data.get("current") or ""):
        return jsonify({"error": "Pick a password you haven't used here."}), 400
    user.set_password(new)
    db.session.commit()
    audit("password_changed", "user", user.id)
    return jsonify({"ok": True}), 200


@deskadmin_bp.route("/api/desk/me", methods=["GET", "POST"])
def desk_me():
    ident = desk_identity(request.get_json(silent=True) or {})
    if not ident:
        return jsonify({"signed_in": False}), 200
    return jsonify(dict(ident, signed_in=True, is_manager=ident["role"] in MANAGER_ROLES)), 200


@deskadmin_bp.route("/api/va/flags", methods=["POST"])
@require_desk()
def va_flags(ident):
    from flags import all_flags
    return jsonify({"flags": {k: v["on"] for k, v in all_flags().items()}}), 200


@deskadmin_bp.route("/api/admin/flags", methods=["GET", "POST"])
@require_desk(MANAGER_ROLES)
def admin_flags(ident):
    from flags import all_flags, set_flag, FLAGS
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        if name not in FLAGS:
            return jsonify({"error": "Unknown flag."}), 400
        value = data.get("value")
        set_flag(name, None if value is None else bool(value))
        audit("flag_set", "flag", name, {"value": value})
    return jsonify({"flags": all_flags()}), 200


@deskadmin_bp.route("/api/admin/desk-users", methods=["GET"])
@require_desk(MANAGER_ROLES)
def list_desk_users(ident):
    rows = User.query.filter(User.role.in_(DESK_ROLES)).order_by(User.created_at.asc()).all()
    return jsonify({"users": [{"id": u.id, "email": u.email, "name": u.name, "role": u.role,
                               "status": getattr(u, "status", "active"),
                               "created_at": u.created_at.isoformat() if u.created_at else None}
                              for u in rows]}), 200


@deskadmin_bp.route("/api/admin/desk-users", methods=["POST"])
def upsert_desk_user():
    """{email, name, role: va|manager, password?, status?} → the account; a
    generated temporary password is returned ONCE when one is created.

    Managers/admins only — except for bootstrap: while no va/manager account
    exists yet, the legacy passcode may create the first one."""
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    if ident["role"] not in MANAGER_ROLES:
        none_yet = User.query.filter(User.role.in_(("va", "manager"))).count() == 0
        if not (ident["via"] == "passcode" and none_yet):
            return jsonify({"error": "That needs a manager."}), 403
    email = (data.get("email") or "").strip().lower()
    if "@" not in email:
        return jsonify({"error": "Enter a valid email."}), 400
    role = (data.get("role") or "va").strip()
    if role == "admin" and ident["role"] != "admin":
        return jsonify({"error": "Only an admin can make admins."}), 403
    try:
        user, temp = create_desk_user(email, data.get("name"), role, data.get("password") or None)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if data.get("status") in ("active", "disabled"):
        user.status = data["status"]
        db.session.commit()
    audit("desk_user_upsert", "user", user.id, {"email": email, "role": user.role, "status": user.status})
    return jsonify({"user": {"id": user.id, "email": user.email, "name": user.name, "role": user.role,
                             "status": user.status}, "temp_password": temp}), 200


@deskadmin_bp.route("/api/admin/audit", methods=["GET"])
@require_desk(MANAGER_ROLES)
def audit_log(ident):
    days = min(max(int(request.args.get("days", 7) or 7), 1), 90)
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    q = AuditEvent.query.filter(AuditEvent.created_at >= since)
    if request.args.get("actor"):
        q = q.filter(AuditEvent.actor_name == request.args["actor"])
    if request.args.get("action"):
        q = q.filter(AuditEvent.action == request.args["action"])
    rows = q.order_by(AuditEvent.created_at.desc()).limit(min(int(request.args.get("limit", 200) or 200), 1000)).all()
    return jsonify({"events": [r.to_dict() for r in rows], "days": days}), 200


@deskadmin_bp.route("/api/health/desk", methods=["GET"])
def desk_health_public():
    from desk_health import check_desk_health
    rep = check_desk_health(alert=False)
    code = 200 if rep["ok"] else 503
    return jsonify(rep), code
