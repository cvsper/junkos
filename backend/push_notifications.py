"""
Umuve APNs Push Notification Service

Sends iOS push notifications via Apple's HTTP/2 APNs gateway.
Uses a .p8 auth key (token-based authentication) and httpx for HTTP/2 support.

Umuve ships TWO iOS apps with two different APNs topics, and a device token is
only valid for the topic it was minted for:

    customer  Umuve       com.goumuve.app   APNS_BUNDLE_ID_CUSTOMER
    driver    Umuve Pro   com.goumuve.pro   APNS_BUNDLE_ID_DRIVER

The topic and the gateway (sandbox vs production) are chosen per device from
the DeviceToken row, not from one global setting — a single global topic can
only ever reach one of the two apps (audit finding F27).

Required environment variables:
    APNS_KEY_ID             - The 10-character Key ID from Apple Developer portal
    APNS_TEAM_ID            - Your Apple Developer Team ID
    APNS_AUTH_KEY_PATH      - Absolute path to the .p8 private key file

Optional:
    APNS_BUNDLE_ID_CUSTOMER - defaults to com.goumuve.app
    APNS_BUNDLE_ID_DRIVER   - defaults to com.goumuve.pro
    APNS_BUNDLE_ID          - legacy single-topic fallback
"""

import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone

import jwt  # PyJWT

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# APNs endpoints
# ---------------------------------------------------------------------------
APNS_PRODUCTION_URL = "https://api.push.apple.com"
APNS_SANDBOX_URL = "https://api.sandbox.push.apple.com"

# ---------------------------------------------------------------------------
# Configuration (read once at import time; safe to re-read later)
# ---------------------------------------------------------------------------
APNS_KEY_ID = os.environ.get("APNS_KEY_ID", "")
APNS_TEAM_ID = os.environ.get("APNS_TEAM_ID", "")
APNS_AUTH_KEY_PATH = os.environ.get("APNS_AUTH_KEY_PATH", "")
# Legacy single-topic setting, kept as the fallback for both apps so an
# existing deployment does not go dark the moment this ships.
APNS_BUNDLE_ID = os.environ.get("APNS_BUNDLE_ID", "")

DEFAULT_BUNDLE_IDS = {
    "customer": "com.goumuve.app",
    "driver": "com.goumuve.pro",
}

# Delivery expiry. Offers are worthless once stale; receipts and status changes
# should still land after a phone comes back online.
_OFFER_CATEGORIES = {"job_offer", "offer", "broadcast", "dispatch"}
_OFFER_EXPIRATION = "0"                       # fire-and-forget
_DURABLE_EXPIRATION_SECONDS = 24 * 60 * 60    # keep trying for a day

# Retry policy for the scheduler sweep (scheduler.py: _retry_failed_pushes).
MAX_PUSH_ATTEMPTS = 3
_RETRY_BASE_MINUTES = 2                       # 2, 4, 8 ...

# Cache the signing key bytes so we only read the file once
_auth_key_bytes: bytes | None = None
# Cache the bearer token and its issue time so we can reuse it (Apple
# recommends reusing tokens for ~20 minutes before refreshing).
_cached_token: str | None = None
_cached_token_issued_at: float = 0.0
_TOKEN_REFRESH_INTERVAL = 50 * 60  # refresh every 50 minutes (valid for 60)

# One HTTP/2 client per process. Rebuilding it per send threw away the
# connection and the TLS handshake on every notification.
_client = None
_client_lock = threading.Lock()


def _is_configured() -> bool:
    """Return True when the APNs credentials are present."""
    return bool(APNS_KEY_ID and APNS_TEAM_ID and APNS_AUTH_KEY_PATH)


def topic_for_app(app_name: str | None) -> str:
    """The APNs topic (bundle id) for one of our two apps.

    Explicit env wins, then the known bundle id, then the legacy global value.
    """
    key = (app_name or "driver").strip().lower()
    if key not in DEFAULT_BUNDLE_IDS:
        key = "driver"
    env_name = "APNS_BUNDLE_ID_{}".format(key.upper())
    return (
        os.environ.get(env_name, "").strip()
        or DEFAULT_BUNDLE_IDS[key]
        or APNS_BUNDLE_ID
    )


def _base_url_for(environment: str | None) -> str:
    """Sandbox or production gateway, chosen per device token.

    Falls back to FLASK_ENV only when the token predates the environment
    column, which is why existing rows are backfilled to "production".
    """
    env = (environment or "").strip().lower()
    if env == "sandbox":
        return APNS_SANDBOX_URL
    if env == "production":
        return APNS_PRODUCTION_URL
    if os.environ.get("FLASK_ENV", "development") == "development":
        return APNS_SANDBOX_URL
    return APNS_PRODUCTION_URL


def _get_apns_base_url() -> str:
    """Return the APNs gateway URL based on the environment (legacy helper)."""
    return _base_url_for(None)


def _get_client():
    """Process-wide HTTP/2 client, created lazily."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                import httpx
                _client = httpx.Client(
                    http2=True,
                    timeout=10.0,
                    limits=httpx.Limits(
                        max_keepalive_connections=8, max_connections=16
                    ),
                )
    return _client


def _load_auth_key() -> bytes:
    """Load the .p8 private key from disk (cached after first read)."""
    global _auth_key_bytes
    if _auth_key_bytes is not None:
        return _auth_key_bytes
    try:
        with open(APNS_AUTH_KEY_PATH, "rb") as f:
            _auth_key_bytes = f.read()
        logger.info("APNs auth key loaded from %s", APNS_AUTH_KEY_PATH)
        return _auth_key_bytes
    except Exception:
        logger.exception("Failed to load APNs auth key from %s", APNS_AUTH_KEY_PATH)
        raise


def _get_bearer_token() -> str:
    """Create (or return cached) APNs bearer token signed with the .p8 key.

    Apple requires ES256-signed JWTs. The token contains:
        iss  - Team ID
        iat  - Issued-at timestamp
        kid  - Key ID (set in the JWT header)
    """
    global _cached_token, _cached_token_issued_at

    now = time.time()
    if _cached_token and (now - _cached_token_issued_at) < _TOKEN_REFRESH_INTERVAL:
        return _cached_token

    key_data = _load_auth_key()
    issued_at = int(now)

    token = jwt.encode(
        {"iss": APNS_TEAM_ID, "iat": issued_at},
        key_data,
        algorithm="ES256",
        headers={"kid": APNS_KEY_ID},
    )

    _cached_token = token
    _cached_token_issued_at = now
    logger.debug("APNs bearer token generated (iat=%d)", issued_at)
    return token


# ---------------------------------------------------------------------------
# Delivery ledger
# ---------------------------------------------------------------------------
def _record_delivery(**fields):
    """Persist one NotificationDelivery row. Never raises."""
    try:
        from models import db, NotificationDelivery

        row = NotificationDelivery(**fields)
        db.session.add(row)
        db.session.commit()
        return row
    except Exception:
        logger.exception("Failed to record notification delivery")
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass
        return None


def _retry_delay(attempts: int) -> timedelta:
    """Exponential backoff: 2, 4, 8 minutes."""
    return timedelta(minutes=_RETRY_BASE_MINUTES * (2 ** max(0, attempts - 1)))


def _is_retryable(status_code: int | None, reason: str | None) -> bool:
    """Whether APNs is telling us to try again later.

    429 (too many requests), 5xx (Apple-side) and transport errors are
    retryable. 4xx like BadDeviceToken are permanent -- retrying just burns
    quota against a token that will never work again.
    """
    if status_code is None:
        return True                        # transport/exception
    if status_code == 429:
        return True
    return status_code >= 500


def _deactivate_token(token: str, reason: str) -> None:
    """Mark a token undeliverable. Keeps the row for the delivery ledger."""
    try:
        from models import db, DeviceToken

        dt = DeviceToken.query.filter_by(token=token).first()
        if dt and dt.active:
            dt.active = False
            dt.deactivated_at = datetime.now(timezone.utc)
            db.session.commit()
            logger.info(
                "Deactivated device token id=%s app=%s reason=%s token=%s...",
                dt.id, dt.app, reason, token[:12],
            )
    except Exception:
        logger.exception("Failed to deactivate device token=%s...", token[:12])
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass


# Backwards-compatible alias: older callers imported this name.
def _remove_invalid_token(token: str) -> None:
    """Deprecated. Deactivates rather than deletes (keeps the audit trail)."""
    _deactivate_token(token, "invalid_token")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_push_to_token(
    token: str,
    title: str,
    body: str,
    data: dict | None = None,
    badge: int | None = None,
    sound: str = "default",
    category: str | None = None,
    app_name: str | None = None,
    environment: str | None = None,
    record: bool = True,
    device_token_id: str | None = None,
    user_id: str | None = None,
    delivery_id: str | None = None,
    attempts: int = 0,
) -> bool:
    """Send a push notification to a single APNs device token.

    The topic and gateway come from ``app_name`` / ``environment`` (i.e. from
    the DeviceToken row), so both iOS apps are addressable from one process.

    Returns True on success, False on any failure. Never raises.
    """
    topic = topic_for_app(app_name)

    if not _is_configured() or not topic:
        logger.warning(
            "APNs is not configured (missing env vars). Skipping push to token=%s...",
            token[:12] if token else "None",
        )
        if record:
            _record_delivery(
                user_id=user_id, device_token_id=device_token_id,
                token_suffix=(token or "")[-6:], app=app_name,
                environment=environment, platform="ios", topic=topic,
                title=title, payload={"title": title, "body": body, "data": data,
                                      "badge": badge, "category": category},
                status="skipped", reason="apns_not_configured", attempts=attempts,
            )
        return False

    status_code = None
    reason = None

    try:
        base_url = _base_url_for(environment)
        url = f"{base_url}/3/device/{token}"
        bearer = _get_bearer_token()

        # Build the APNs payload
        aps_payload: dict = {
            "alert": {"title": title, "body": body},
            "sound": sound,
        }
        if badge is not None:
            aps_payload["badge"] = badge
        if category:
            aps_payload["category"] = category

        payload: dict = {"aps": aps_payload}
        if data:
            payload.update(data)

        # Time-sensitive offers expire immediately; everything else is worth
        # delivering when the device comes back (F27).
        is_offer = (category or "").lower() in _OFFER_CATEGORIES or (
            (data or {}).get("type", "").lower() in _OFFER_CATEGORIES
        )
        expiration = (
            _OFFER_EXPIRATION if is_offer
            else str(int(time.time()) + _DURABLE_EXPIRATION_SECONDS)
        )

        headers = {
            "authorization": f"bearer {bearer}",
            "apns-topic": topic,
            "apns-push-type": "alert",
            "apns-priority": "10",
            "apns-expiration": expiration,
        }

        logger.info(
            "Sending APNs push: token=%s... app=%s topic=%s title=%r url=%s",
            token[:12], app_name, topic, title, base_url,
        )

        response = _get_client().post(url, json=payload, headers=headers)
        status_code = response.status_code

        if status_code == 200:
            logger.info("APNs push sent successfully to token=%s...", token[:12])
            if record:
                _record_delivery(
                    user_id=user_id, device_token_id=device_token_id,
                    token_suffix=token[-6:], app=app_name, environment=environment,
                    platform="ios", topic=topic, title=title,
                    payload={"title": title, "body": body, "data": data,
                             "badge": badge, "category": category},
                    status="sent", status_code=200, attempts=attempts + 1,
                )
            _mark_delivery_sent(delivery_id)
            _stamp_token_used(token)
            return True

        # APNs returns JSON with a "reason" field on error
        try:
            error_body = response.json()
        except Exception:
            error_body = response.text
        reason = (
            error_body.get("reason") if isinstance(error_body, dict) else str(error_body)
        )

        logger.error(
            "APNs push failed: status=%d token=%s... app=%s reason=%s",
            status_code, token[:12], app_name, error_body,
        )

        # 410 Gone / BadDeviceToken: the token is dead. Deactivate it so we
        # stop paying to send to it, and never retry.
        if status_code == 410 or reason in ("BadDeviceToken", "Unregistered"):
            _deactivate_token(token, reason or "gone")
            if record:
                _record_delivery(
                    user_id=user_id, device_token_id=device_token_id,
                    token_suffix=token[-6:], app=app_name, environment=environment,
                    platform="ios", topic=topic, title=title,
                    payload={"title": title, "body": body, "data": data,
                             "badge": badge, "category": category},
                    status="undeliverable", reason=reason, status_code=status_code,
                    attempts=attempts + 1,
                )
            _close_delivery(delivery_id, "undeliverable", reason, status_code)
            return False

    except Exception as exc:
        reason = str(exc)[:200]
        logger.exception(
            "APNs push failed with exception for token=%s...",
            token[:12] if token else "None",
        )

    # Failure: schedule a retry when it looks transient.
    retryable = _is_retryable(status_code, reason) and (attempts + 1) < MAX_PUSH_ATTEMPTS
    next_attempt = (
        datetime.now(timezone.utc) + _retry_delay(attempts + 1) if retryable else None
    )
    if record:
        _record_delivery(
            user_id=user_id, device_token_id=device_token_id,
            token_suffix=(token or "")[-6:], app=app_name, environment=environment,
            platform="ios", topic=topic, title=title,
            payload={"title": title, "body": body, "data": data,
                     "badge": badge, "category": category},
            status=("pending_retry" if retryable else "failed"),
            reason=reason, status_code=status_code,
            attempts=attempts + 1, next_attempt_at=next_attempt,
        )
    _close_delivery(
        delivery_id,
        "pending_retry" if retryable else "dead",
        reason, status_code, next_attempt_at=next_attempt, attempts=attempts + 1,
    )
    return False


def _stamp_token_used(token: str) -> None:
    try:
        from models import db, DeviceToken
        dt = DeviceToken.query.filter_by(token=token).first()
        if dt:
            dt.last_used_at = datetime.now(timezone.utc)
            db.session.commit()
    except Exception:
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass


def _mark_delivery_sent(delivery_id):
    _close_delivery(delivery_id, "sent", None, 200)


def _close_delivery(delivery_id, status, reason, status_code,
                    next_attempt_at=None, attempts=None):
    """Update an existing (retried) delivery row. No-op without an id."""
    if not delivery_id:
        return
    try:
        from models import db, NotificationDelivery

        row = NotificationDelivery.query.filter_by(id=delivery_id).first()
        if row is None:
            return
        row.status = status
        row.reason = reason
        row.status_code = status_code
        row.next_attempt_at = next_attempt_at
        if attempts is not None:
            row.attempts = attempts
        db.session.commit()
    except Exception:
        logger.exception("Failed to update notification delivery %s", delivery_id)
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass


def send_push_notification(
    user_id: str,
    title: str,
    body: str,
    data: dict | None = None,
    badge: int | None = None,
    category: str | None = None,
) -> int:
    """Send a push notification to all registered devices for a user.

    Each device is addressed with its own APNs topic and gateway, so a user
    who has both apps installed gets the notification in both.

    Returns the number of tokens that were successfully sent to.
    Never raises.
    """
    try:
        from models import DeviceToken

        tokens = DeviceToken.query.filter_by(user_id=user_id, active=True).all()
        ios_tokens = [t for t in tokens if t.platform == "ios"]
        android_tokens = [t for t in tokens if t.platform == "android"]

        if android_tokens:
            # Accepted at registration, but nothing in this codebase speaks
            # FCM. Record it rather than silently dropping it (F27).
            logger.warning(
                "%d Android token(s) for user_id=%s are UNDELIVERABLE: no FCM "
                "provider is configured.", len(android_tokens), user_id,
            )
            for dt in android_tokens:
                _record_delivery(
                    user_id=user_id, device_token_id=dt.id,
                    token_suffix=(dt.token or "")[-6:], app=dt.app,
                    environment=dt.environment, platform="android", topic=None,
                    title=title,
                    payload={"title": title, "body": body, "data": data,
                             "badge": badge, "category": category},
                    status="undeliverable", reason="no_fcm_provider", attempts=0,
                )

        if not ios_tokens:
            logger.info("No active iOS device tokens registered for user_id=%s", user_id)
            return 0

        logger.info(
            "Sending push to %d device(s) for user_id=%s: title=%r",
            len(ios_tokens), user_id, title,
        )

        success_count = 0
        for dt in ios_tokens:
            if send_push_to_token(
                dt.token, title, body, data=data, badge=badge, category=category,
                app_name=dt.app, environment=dt.environment,
                device_token_id=dt.id, user_id=user_id,
            ):
                success_count += 1

        logger.info(
            "Push results for user_id=%s: %d/%d succeeded",
            user_id, success_count, len(ios_tokens),
        )
        return success_count

    except Exception:
        logger.exception("send_push_notification failed for user_id=%s", user_id)
        return 0


def retry_pending_pushes(limit: int = 100) -> dict:
    """Re-send deliveries that failed transiently and are due.

    Called by the scheduler (scheduler.py: _retry_failed_pushes). Gives up
    after MAX_PUSH_ATTEMPTS and marks the row "dead" so it stops being picked
    up and is visible as a genuine loss.
    """
    from models import db, NotificationDelivery, DeviceToken

    now = datetime.now(timezone.utc)
    due = (
        NotificationDelivery.query
        .filter(NotificationDelivery.status == "pending_retry")
        .filter(NotificationDelivery.next_attempt_at.isnot(None))
        .filter(NotificationDelivery.next_attempt_at <= now)
        .order_by(NotificationDelivery.next_attempt_at.asc())
        .limit(limit)
        .all()
    )

    result = {"considered": len(due), "sent": 0, "failed": 0, "dead": 0}

    for row in due:
        if (row.attempts or 0) >= MAX_PUSH_ATTEMPTS:
            row.status = "dead"
            row.next_attempt_at = None
            db.session.commit()
            result["dead"] += 1
            continue

        dt = (
            DeviceToken.query.filter_by(id=row.device_token_id).first()
            if row.device_token_id else None
        )
        if dt is None or not dt.active:
            row.status = "undeliverable"
            row.reason = row.reason or "token_gone"
            row.next_attempt_at = None
            db.session.commit()
            result["dead"] += 1
            continue

        payload = row.payload or {}
        ok = send_push_to_token(
            dt.token,
            payload.get("title") or row.title or "",
            payload.get("body") or "",
            data=payload.get("data"),
            badge=payload.get("badge"),
            category=payload.get("category"),
            app_name=dt.app,
            environment=dt.environment,
            record=False,                 # update this row instead of adding one
            device_token_id=dt.id,
            user_id=row.user_id,
            delivery_id=row.id,
            attempts=row.attempts or 0,
        )
        if ok:
            result["sent"] += 1
        else:
            result["failed"] += 1

    if result["considered"]:
        logger.info("Push retry sweep: %s", result)
    return result
