"""
B2B Commercial Portal — v1 audit decorator (Spec 04 §9.4).

`@audit_mutation(entity_type)` wraps a portal mutation view.  It:

  1. Captures a "before" snapshot (by re-fetching the row referenced in
     `kwargs` or in the JSON body's `id`).
  2. Runs the view.
  3. On a 2xx response, captures an "after" snapshot and writes a row to
     `portal_v1_audit_log`.

The decorator never raises into the request: audit failures are logged
and swallowed.  Writing-through-the-response-body lets us capture the
canonical post-mutation shape without duplicating the DB read.

The `entity_type` string doubles as the SQLAlchemy class name — we
resolve it via a small registry so callers don't have to pass the class.
"""

import json
import logging
from functools import wraps

from flask import g, request

from models import db
from portal_v1_models import PortalV1AuditLog, PortalUnit, PortalRecurringSchedule

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Entity registry: entity_type string -> SQLAlchemy model class.
# Extend as new mutation targets come online.
# ---------------------------------------------------------------------------
_ENTITY_REGISTRY = {
    "portal_unit": PortalUnit,
    "portal_recurring_schedule": PortalRecurringSchedule,
}


def register_entity(entity_type, model_cls):
    """Register a new entity_type -> model class mapping."""
    _ENTITY_REGISTRY[entity_type] = model_cls


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _snapshot(obj):
    """Best-effort JSON snapshot of a SQLAlchemy row."""
    if obj is None:
        return None
    if hasattr(obj, "to_dict"):
        try:
            return obj.to_dict()
        except Exception:  # pragma: no cover
            pass
    # Fallback — pluck simple attributes off the mapper
    try:
        mapper = db.inspect(obj).mapper
        return {
            c.key: getattr(obj, c.key)
            for c in mapper.column_attrs
            if not callable(getattr(obj, c.key, None))
        }
    except Exception:  # pragma: no cover
        return {"repr": repr(obj)}


def _pick_entity_id(kwargs):
    """Pull the likely PK from URL kwargs or JSON body."""
    for key in ("id", "unit_id", "schedule_id", "entity_id"):
        if key in kwargs and kwargs[key]:
            return kwargs[key]
    body = request.get_json(silent=True) or {}
    return body.get("id") or body.get("unit_id") or body.get("schedule_id")


def _infer_action(method):
    if method == "POST":
        return "create"
    if method == "DELETE":
        return "delete"
    return "update"


def _write_log(org_id, actor_member_id, entity_type, entity_id, action,
               before, after):
    """Append to portal_v1_audit_log.  Never raises."""
    try:
        entry = PortalV1AuditLog(
            org_id=org_id,
            actor_member_id=actor_member_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before_json=before,
            after_json=after,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception as exc:  # pragma: no cover
        logger.warning("audit_mutation write failed: %s", exc)
        db.session.rollback()


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------
def audit_mutation(entity_type):
    """Decorate a portal mutation view to emit a v1 audit log entry.

    Usage:
        @portal_v1_bp.route("/units/<unit_id>", methods=["PATCH"])
        @portal_auth
        @require_role("owner", "admin", "operator")
        @audit_mutation("portal_unit")
        def update_unit(unit_id): ...
    """

    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            model_cls = _ENTITY_REGISTRY.get(entity_type)
            entity_id = _pick_entity_id(kwargs)
            action = _infer_action(request.method)

            # 1) Before snapshot (only meaningful for update / delete)
            before = None
            if model_cls is not None and entity_id and action != "create":
                try:
                    obj = db.session.get(model_cls, entity_id)
                    before = _snapshot(obj)
                except Exception as exc:  # pragma: no cover
                    logger.warning("audit before-snapshot failed: %s", exc)

            # 2) Run the view
            response = f(*args, **kwargs)

            # 3) Extract the (Response, status) tuple & only log on 2xx
            body = response
            status = 200
            if isinstance(response, tuple):
                if len(response) >= 2:
                    body, status = response[0], response[1]
                else:
                    body = response[0]
            if not (200 <= int(status) < 300):
                return response

            # 4) After snapshot — prefer the response payload (canonical).
            after = None
            try:
                json_data = body.get_json() if hasattr(body, "get_json") else None
                if isinstance(json_data, dict):
                    after = json_data
                    # If the view returned the new entity, pick up its id.
                    if not entity_id:
                        entity_id = (
                            json_data.get("id")
                            or (json_data.get("unit") or {}).get("id")
                            or (json_data.get("schedule") or {}).get("id")
                        )
            except Exception:  # pragma: no cover
                pass

            # For deletes the response body is typically {"ok": true} — use
            # the `before` snapshot as the after=None signal.
            if action == "delete":
                after = None

            _write_log(
                org_id=getattr(g, "org_id", None),
                actor_member_id=getattr(g, "member_id", None)
                or getattr(g, "user_id", None),
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                before=before,
                after=after,
            )

            return response

        return wrapper

    return deco
