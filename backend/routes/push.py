"""
Push Notification API Routes

Endpoints for registering/unregistering APNs device tokens and
sending test push notifications.
"""

import logging
import os

from flask import Blueprint, request, jsonify

from auth_routes import require_auth
from models import db, DeviceToken
from push_notifications import send_push_notification

logger = logging.getLogger(__name__)

push_bp = Blueprint("push", __name__, url_prefix="/api/push")


# ---------------------------------------------------------------------------
# POST /api/push/register-token
# ---------------------------------------------------------------------------
VALID_APPS = ("customer", "driver")
VALID_ENVIRONMENTS = ("sandbox", "production")


def _resolve_app(data):
    """Which of the two iOS apps sent this token.

    Both clients already tell us, in their own casing:
      * Umuve Pro   -> DriverAPIClient.registerPushToken  {"appType": "driver"}
      * Umuve       -> NotificationManager.sendTokenToBackend {"app_type": "customer"}
    Anything unrecognised falls back to "driver", which is the app that has
    been registering tokens in production (F27).
    """
    raw = (
        data.get("app")
        or data.get("app_type")
        or data.get("appType")
        or ""
    )
    value = str(raw).strip().lower()
    if value in VALID_APPS:
        return value, None
    if value:
        return None, "app must be one of {}".format(", ".join(VALID_APPS))
    return "driver", None


def _resolve_environment(data):
    """APNs gateway this token belongs to, defaulting to production."""
    raw = data.get("environment") or data.get("apns_environment") or ""
    value = str(raw).strip().lower()
    if not value:
        return "production", None
    if value in VALID_ENVIRONMENTS:
        return value, None
    # Xcode/TestFlight vocabulary the clients might send.
    if value in ("development", "debug", "dev"):
        return "sandbox", None
    if value in ("release", "prod", "appstore"):
        return "production", None
    return None, "environment must be one of {}".format(", ".join(VALID_ENVIRONMENTS))


@push_bp.route("/register-token", methods=["POST"])
@require_auth
def register_token(user_id):
    """Register an APNs (or FCM) device token for the authenticated user.

    Body JSON:
        token       (str, required) - the device token hex string
        platform    (str, optional) - "ios" (default) or "android"
        app         (str, optional) - "customer" | "driver" (also accepted as
                                      app_type / appType). Selects the APNs
                                      topic: com.goumuve.app / com.goumuve.pro
        environment (str, optional) - "sandbox" | "production" (default)
    """
    data = request.get_json(silent=True) or {}
    token = data.get("token", "").strip()
    platform = data.get("platform", "ios").strip().lower()

    if not token:
        return jsonify({"error": "token is required"}), 400

    if platform not in ("ios", "android"):
        return jsonify({"error": "platform must be 'ios' or 'android'"}), 400

    app_name, app_error = _resolve_app(data)
    if app_error:
        return jsonify({"error": app_error}), 400

    environment, env_error = _resolve_environment(data)
    if env_error:
        return jsonify({"error": env_error}), 400

    # Check if this exact token already exists
    existing = DeviceToken.query.filter_by(token=token).first()

    if existing:
        unchanged = (
            existing.user_id == user_id
            and existing.platform == platform
            and existing.app == app_name
            and existing.environment == environment
            and existing.active
        )
        if unchanged:
            # Already registered for this user -- nothing to do
            logger.info("Device token already registered: user=%s token=%s...", user_id, token[:12])
            return jsonify({"success": True, "device_token": existing.to_dict()}), 200

        # Token exists but something changed -- a different user logged in on
        # the same device, the app was reinstalled from a different build, or
        # a previously deactivated token is live again. Re-bind it.
        logger.info(
            "Re-assigning device token user=%s->%s app=%s->%s env=%s->%s token=%s...",
            existing.user_id, user_id,
            existing.app, app_name,
            existing.environment, environment,
            token[:12],
        )
        existing.user_id = user_id
        existing.platform = platform
        existing.app = app_name
        existing.environment = environment
        existing.active = True
        existing.deactivated_at = None
        db.session.commit()
        return jsonify({"success": True, "device_token": existing.to_dict()}), 200

    # Create new device token record
    dt = DeviceToken(
        user_id=user_id,
        token=token,
        platform=platform,
        app=app_name,
        environment=environment,
        active=True,
    )
    db.session.add(dt)
    db.session.commit()

    logger.info(
        "Device token registered: user=%s platform=%s app=%s env=%s token=%s...",
        user_id, platform, app_name, environment, token[:12],
    )
    if platform == "android":
        # Accepted and stored, but there is no FCM provider in this codebase:
        # push_notifications.py only speaks APNs. Say so instead of implying
        # the device will receive anything (F27).
        logger.warning(
            "Android token registered for user=%s but no FCM provider is "
            "configured — this device is UNDELIVERABLE until one is added.",
            user_id,
        )
    return jsonify({"success": True, "device_token": dt.to_dict()}), 200


# ---------------------------------------------------------------------------
# DELETE /api/push/unregister-token
# ---------------------------------------------------------------------------
@push_bp.route("/unregister-token", methods=["DELETE"])
@require_auth
def unregister_token(user_id):
    """Remove a device token for the authenticated user.

    Body JSON:
        token (str, required) - the device token to remove
    """
    data = request.get_json(silent=True) or {}
    token = data.get("token", "").strip()

    if not token:
        return jsonify({"error": "token is required"}), 400

    dt = DeviceToken.query.filter_by(token=token, user_id=user_id).first()

    if not dt:
        return jsonify({"error": "Token not found"}), 404

    db.session.delete(dt)
    db.session.commit()

    logger.info("Device token unregistered: user=%s token=%s...", user_id, token[:12])
    return jsonify({"success": True, "message": "Token removed"}), 200


# ---------------------------------------------------------------------------
# GET /api/push/test  (development only)
# ---------------------------------------------------------------------------
@push_bp.route("/test", methods=["GET"])
@require_auth
def test_push(user_id):
    """Send a test push notification to the authenticated user.

    Only available when FLASK_ENV=development.
    """
    if os.environ.get("FLASK_ENV", "development") != "development":
        return jsonify({"error": "Test push is only available in development mode"}), 403

    count = send_push_notification(
        user_id=user_id,
        title="Umuve Test",
        body="If you see this, push notifications are working!",
        data={"type": "test"},
    )

    return jsonify({
        "success": True,
        "message": f"Test push sent to {count} device(s)",
        "devices_reached": count,
    }), 200
