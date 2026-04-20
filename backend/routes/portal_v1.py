"""
B2B Commercial Portal — v1 expansion routes (Spec 04 §9).

Blueprint: /portal/v1 (same prefix as the MVP `portal_bp` — we share
JWT + RBAC helpers from `routes.portal`).  New endpoints shipped here:

  * Units
    - GET    /properties/<property_id>/units
    - POST   /properties/<property_id>/units
    - PATCH  /units/<unit_id>
    - DELETE /units/<unit_id>

  * Recurring schedules
    - GET    /recurring
    - POST   /recurring
    - PATCH  /recurring/<schedule_id>
    - DELETE /recurring/<schedule_id>

  * ESG
    - GET    /esg/settings
    - PATCH  /esg/settings
    - GET    /esg/report?month=N&year=YYYY

The orchestrator wires `app.register_blueprint(portal_v1_bp)` at merge
time.  We do NOT touch server.py ourselves.
"""

import datetime as _dt
import logging

from flask import Blueprint, g, jsonify, request
from sqlalchemy import and_

from models import db, PortalProperty
from portal_v1_models import (
    PortalUnit, PortalRecurringSchedule, PortalV1AuditLog,
)
from portal_audit import audit_mutation
from portal_esg import (
    build_esg_report, get_org_esg_settings, set_org_esg_settings,
)
from routes.portal import portal_auth, require_role

logger = logging.getLogger(__name__)

portal_v1_bp = Blueprint("portal_v1", __name__, url_prefix="/portal/v1")


# ---------------------------------------------------------------------------
# Tenant guards
# ---------------------------------------------------------------------------
def _property_or_403(property_id):
    """Fetch a property, 403 if it doesn't belong to caller's org."""
    prop = db.session.get(PortalProperty, property_id)
    if not prop or prop.org_id != g.org_id:
        return None
    return prop


def _unit_or_403(unit_id):
    """Fetch a unit, 403 if its property doesn't belong to caller's org."""
    unit = db.session.get(PortalUnit, unit_id)
    if not unit:
        return None
    prop = db.session.get(PortalProperty, unit.property_id)
    if not prop or prop.org_id != g.org_id:
        return None
    return unit


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------
@portal_v1_bp.route("/properties/<property_id>/units", methods=["GET"])
@portal_auth
def list_units(property_id):
    prop = _property_or_403(property_id)
    if not prop:
        return jsonify({"error": "not_found"}), 404
    rows = (
        db.session.query(PortalUnit)
        .filter_by(property_id=property_id)
        .order_by(PortalUnit.unit_number.asc())
        .all()
    )
    return jsonify({"units": [u.to_dict() for u in rows]})


@portal_v1_bp.route("/properties/<property_id>/units", methods=["POST"])
@portal_auth
@require_role("owner", "admin", "operator")
@audit_mutation("portal_unit")
def create_unit(property_id):
    prop = _property_or_403(property_id)
    if not prop:
        return jsonify({"error": "not_found"}), 404

    data = request.get_json(silent=True) or {}
    unit_number = (data.get("unit_number") or "").strip()
    if not unit_number:
        return jsonify({"error": "unit_number required"}), 400
    status = data.get("status", "active")
    if status not in {"active", "inactive"}:
        return jsonify({"error": "invalid status"}), 400

    # Upfront duplicate check for a clean 409 (the DB UQ is the real gate).
    dup = (
        db.session.query(PortalUnit)
        .filter_by(property_id=property_id, unit_number=unit_number)
        .first()
    )
    if dup:
        return jsonify({"error": "unit_number exists on this property"}), 409

    unit = PortalUnit(
        property_id=property_id,
        unit_number=unit_number,
        sqft=data.get("sqft"),
        access_notes=data.get("access_notes"),
        status=status,
    )
    db.session.add(unit)
    db.session.commit()
    return jsonify(unit.to_dict()), 201


@portal_v1_bp.route("/units/<unit_id>", methods=["PATCH"])
@portal_auth
@require_role("owner", "admin", "operator")
@audit_mutation("portal_unit")
def update_unit(unit_id):
    unit = _unit_or_403(unit_id)
    if not unit:
        return jsonify({"error": "not_found"}), 404

    data = request.get_json(silent=True) or {}
    for field in ("unit_number", "sqft", "access_notes", "status"):
        if field in data:
            if field == "status" and data[field] not in {"active", "inactive"}:
                return jsonify({"error": "invalid status"}), 400
            setattr(unit, field, data[field])
    db.session.commit()
    return jsonify(unit.to_dict())


@portal_v1_bp.route("/units/<unit_id>", methods=["DELETE"])
@portal_auth
@require_role("owner", "admin")
@audit_mutation("portal_unit")
def delete_unit(unit_id):
    unit = _unit_or_403(unit_id)
    if not unit:
        return jsonify({"error": "not_found"}), 404
    db.session.delete(unit)
    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Recurring schedules
# ---------------------------------------------------------------------------
def _parse_iso(s):
    if not s:
        return None
    try:
        return _dt.datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


@portal_v1_bp.route("/recurring", methods=["GET"])
@portal_auth
def list_schedules():
    rows = (
        db.session.query(PortalRecurringSchedule)
        .filter_by(org_id=g.org_id)
        .order_by(PortalRecurringSchedule.next_run_at.asc())
        .all()
    )
    return jsonify({"schedules": [s.to_dict() for s in rows]})


@portal_v1_bp.route("/recurring", methods=["POST"])
@portal_auth
@require_role("owner", "admin", "operator")
@audit_mutation("portal_recurring_schedule")
def create_schedule():
    data = request.get_json(silent=True) or {}
    property_id = data.get("property_id")
    cadence = data.get("cadence")
    if not property_id or cadence not in {"weekly", "biweekly", "monthly"}:
        return jsonify({"error": "property_id and valid cadence required"}), 400

    prop = _property_or_403(property_id)
    if not prop:
        return jsonify({"error": "property not_found"}), 404

    unit_id = data.get("unit_id")
    if unit_id:
        if _unit_or_403(unit_id) is None:
            return jsonify({"error": "unit not_found"}), 404

    next_run = _parse_iso(data.get("next_run_at")) or _dt.datetime.utcnow()

    sched = PortalRecurringSchedule(
        org_id=g.org_id,
        property_id=property_id,
        unit_id=unit_id,
        cadence=cadence,
        day_of_week=data.get("day_of_week"),
        day_of_month=data.get("day_of_month"),
        next_run_at=next_run,
        active=True,
    )
    db.session.add(sched)
    db.session.commit()
    return jsonify(sched.to_dict()), 201


@portal_v1_bp.route("/recurring/<schedule_id>", methods=["PATCH"])
@portal_auth
@require_role("owner", "admin", "operator")
@audit_mutation("portal_recurring_schedule")
def update_schedule(schedule_id):
    sched = db.session.get(PortalRecurringSchedule, schedule_id)
    if not sched or sched.org_id != g.org_id:
        return jsonify({"error": "not_found"}), 404
    data = request.get_json(silent=True) or {}
    for field in ("cadence", "day_of_week", "day_of_month", "active"):
        if field in data:
            setattr(sched, field, data[field])
    if "next_run_at" in data:
        parsed = _parse_iso(data["next_run_at"])
        if parsed:
            sched.next_run_at = parsed
    if data.get("paused") is True and sched.paused_at is None:
        sched.paused_at = _dt.datetime.utcnow()
        sched.active = False
    elif data.get("paused") is False:
        sched.paused_at = None
        sched.active = True
    db.session.commit()
    return jsonify(sched.to_dict())


@portal_v1_bp.route("/recurring/<schedule_id>", methods=["DELETE"])
@portal_auth
@require_role("owner", "admin")
@audit_mutation("portal_recurring_schedule")
def delete_schedule(schedule_id):
    sched = db.session.get(PortalRecurringSchedule, schedule_id)
    if not sched or sched.org_id != g.org_id:
        return jsonify({"error": "not_found"}), 404
    db.session.delete(sched)
    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# ESG
# ---------------------------------------------------------------------------
@portal_v1_bp.route("/esg/settings", methods=["GET"])
@portal_auth
def get_esg_settings():
    return jsonify(get_org_esg_settings(g.org_id))


@portal_v1_bp.route("/esg/settings", methods=["PATCH"])
@portal_auth
@require_role("owner", "admin")
def patch_esg_settings():
    data = request.get_json(silent=True) or {}
    set_org_esg_settings(
        g.org_id,
        enabled=data.get("esg_report_enabled"),
        contact_email=data.get("esg_contact_email"),
    )
    return jsonify(get_org_esg_settings(g.org_id))


@portal_v1_bp.route("/esg/report", methods=["GET"])
@portal_auth
def esg_report():
    try:
        month = int(request.args.get("month"))
        year = int(request.args.get("year"))
    except (TypeError, ValueError):
        return jsonify({"error": "month and year are required integers"}), 400
    if not (1 <= month <= 12):
        return jsonify({"error": "month must be 1..12"}), 400
    return jsonify(build_esg_report(g.org_id, month, year))


# ---------------------------------------------------------------------------
# Audit log read — owner/admin only, read-only
# ---------------------------------------------------------------------------
@portal_v1_bp.route("/audit", methods=["GET"])
@portal_auth
@require_role("owner", "admin")
def list_audit():
    limit = min(int(request.args.get("limit", 50)), 200)
    q = (
        db.session.query(PortalV1AuditLog)
        .filter_by(org_id=g.org_id)
        .order_by(PortalV1AuditLog.created_at.desc())
        .limit(limit)
    )
    return jsonify({"entries": [e.to_dict() for e in q.all()]})
