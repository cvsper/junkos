"""
Socket.IO event handlers for Umuve real-time features.
- Driver GPS location streaming
- Job status broadcasts
- New-job alerts to nearby drivers
- Job chat (send / typing / read)

Audit F03 — every connection is authenticated with the same JWT the REST
API uses and every event is authorised against the SERVER-derived identity:

  handshake: ``auth: {token}`` (web), ``?token=`` (iOS connectParams) or an
  ``Authorization: Bearer`` header. No / bad / expired token, an unknown
  user or a non-active account => connection refused.

  rooms:     ``admin``            -> role admin
             ``driver:<cid>``     -> that contractor's own user (or admin)
             ``operator:<cid>``   -> that contractor's own user (or admin)
             ``<job_id>``         -> the job's customer, its assigned hauler /
                                     operator, or admin

  driver:location  contractor id comes from the session, never the payload;
                   the job (if given) must be assigned to that contractor and
                   active; coordinates are range-checked; >= 1s between writes
                   per contractor.
  chat:*           sender id/role come from the session via the REST chat
                   membership predicate (routes.chat.get_sender_role).

Event names and payload shapes are unchanged so the web platform and the
Umuve Pro / customer iOS apps keep working.
"""

import logging
import threading
import time
from datetime import datetime, timezone
from math import radians, cos, sin, asin, sqrt

from flask_socketio import SocketIO, emit, join_room, leave_room
from flask import request

from models import db, Contractor, Job, User

logger = logging.getLogger(__name__)

socketio = SocketIO()

EARTH_RADIUS_KM = 6371.0
DRIVER_BROADCAST_RADIUS_KM = 30.0
LOCATION_MIN_INTERVAL_SECONDS = 1.0
ACTIVE_JOB_STATUSES = {
    "accepted", "assigned", "en_route", "arrived", "in_progress", "started",
}

# request.sid -> {"user_id", "role", "contractor_id", "is_admin"}
_SESSIONS = {}
# contractor_id -> monotonic time of last accepted location write
_LAST_LOCATION_WRITE = {}
_LOCK = threading.Lock()


def _haversine(lat1, lng1, lat2, lng2):
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
def _extract_token(auth):
    if isinstance(auth, dict):
        token = auth.get("token") or auth.get("Authorization") or ""
        if isinstance(token, str) and token:
            return token[7:] if token.startswith("Bearer ") else token
    header = request.headers.get("Authorization", "") if request else ""
    if header.startswith("Bearer "):
        return header[7:].strip()
    query = request.args.get("token") if request else None
    return query or ""


def _resolve_identity(token):
    """JWT -> identity dict, or None if the principal must be refused."""
    from auth_routes import verify_token  # reuses the REST secret handling

    if not token:
        return None
    user_id = verify_token(token)
    if not user_id:
        return None
    user = db.session.get(User, user_id)
    if user is None or (user.status or "active") != "active":
        return None
    profile = user.contractor_profile
    return {
        "user_id": user.id,
        "role": user.role or "customer",
        "is_admin": user.role == "admin",
        "contractor_id": profile.id if profile else None,
    }


def current_identity():
    """Server-side identity for the emitting socket, or None."""
    return _SESSIONS.get(request.sid)


def _deny(reason, event="error"):
    emit(event, {"error": reason}, room=request.sid)


# ---------------------------------------------------------------------------
# Authorisation helpers (shared with REST predicates where they exist)
# ---------------------------------------------------------------------------
def _job_access(identity, job):
    """True if identity may observe ``job`` (customer, assigned hauler/operator, admin)."""
    if identity is None or job is None:
        return False
    if identity["is_admin"] or job.customer_id == identity["user_id"]:
        return True
    cid = identity.get("contractor_id")
    return bool(cid and cid in (job.driver_id, job.operator_id))


def can_join_room(identity, room):
    if identity is None or not isinstance(room, str) or not room:
        return False
    if room == "admin":
        return identity["is_admin"]
    for prefix in ("driver:", "operator:"):
        if room.startswith(prefix):
            cid = room[len(prefix):]
            return identity["is_admin"] or (cid and cid == identity.get("contractor_id"))
    if ":" in room:
        return False
    return _job_access(identity, db.session.get(Job, room))


def _chat_role(identity, job):
    """'customer' | 'driver' | None via the REST chat membership predicate."""
    from routes.chat import get_sender_role
    return get_sender_role(identity["user_id"], job) if identity else None


# ---------------------------------------------------------------------------
# Connection lifecycle
# ---------------------------------------------------------------------------
@socketio.on("connect")
def handle_connect(auth=None):
    identity = _resolve_identity(_extract_token(auth))
    if identity is None:
        logger.info("[socket] refused unauthenticated connection %s", request.sid)
        return False  # flask-socketio: reject the handshake
    with _LOCK:
        _SESSIONS[request.sid] = identity
    logger.info("[socket] connected %s user=%s role=%s", request.sid, identity["user_id"], identity["role"])


@socketio.on("disconnect")
def handle_disconnect(*_args):
    with _LOCK:
        _SESSIONS.pop(request.sid, None)
    logger.info("[socket] disconnected %s", request.sid)


# ---------------------------------------------------------------------------
# Rooms
# ---------------------------------------------------------------------------
@socketio.on("join")
def handle_join(data):
    """Join a room. data = { room: "<job_id>" | "driver:<id>" | "operator:<id>" | "admin" }"""
    room = (data or {}).get("room")
    identity = current_identity()
    if not room:
        return
    if not can_join_room(identity, room):
        _deny("Not authorized to join room", "join:denied")
        return
    join_room(room)
    emit("joined", {"room": room}, room=request.sid)


@socketio.on("leave")
def handle_leave(data):
    room = (data or {}).get("room")
    if room:
        leave_room(room)


@socketio.on("admin:join")
def handle_admin_join(*_args):
    """Admin clients join the admin room for live map updates."""
    identity = current_identity()
    if not identity or not identity["is_admin"]:
        _deny("Admin only", "join:denied")
        return
    join_room("admin")
    emit("joined", {"room": "admin"}, room=request.sid)


@socketio.on("admin:leave")
def handle_admin_leave(*_args):
    """Admin clients leave the admin room."""
    leave_room("admin")


@socketio.on("operator:join")
def handle_operator_join(data):
    """Operator joins their room to receive delegated job notifications.

    The room is derived from the session; a client-supplied operator_id is
    only honoured when it matches (or the caller is admin).
    """
    identity = current_identity()
    requested = (data or {}).get("operator_id")
    operator_id = requested or (identity or {}).get("contractor_id")
    if not operator_id:
        return
    room = "operator:{}".format(operator_id)
    if not can_join_room(identity, room):
        _deny("Not authorized to join room", "join:denied")
        return
    join_room(room)
    emit("joined", {"room": room}, room=request.sid)


@socketio.on("operator:leave")
def handle_operator_leave(data):
    """Operator leaves their room."""
    operator_id = (data or {}).get("operator_id") or (current_identity() or {}).get("contractor_id")
    if operator_id:
        leave_room("operator:{}".format(operator_id))


@socketio.on("customer:join")
def handle_customer_join(data):
    """Customer joins a job room to receive live tracking updates."""
    job_id = (data or {}).get("job_id")
    if not job_id:
        return
    identity = current_identity()
    if not _job_access(identity, db.session.get(Job, job_id)):
        _deny("Not authorized to join room", "join:denied")
        return
    join_room(job_id)
    emit("joined", {"room": job_id}, room=request.sid)


@socketio.on("customer:leave")
def handle_customer_leave(data):
    """Customer leaves a job room."""
    job_id = (data or {}).get("job_id")
    if job_id:
        leave_room(job_id)


# ---------------------------------------------------------------------------
# Driver GPS
# ---------------------------------------------------------------------------
def _valid_coords(lat, lng):
    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return None
    if lat != lat or lng != lng:  # NaN
        return None
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
        return None
    return lat, lng


def _rate_limited(contractor_id, now=None):
    now = now if now is not None else time.monotonic()
    with _LOCK:
        last = _LAST_LOCATION_WRITE.get(contractor_id)
        if last is not None and now - last < LOCATION_MIN_INTERVAL_SECONDS:
            return True
        _LAST_LOCATION_WRITE[contractor_id] = now
    return False


@socketio.on("driver:location")
def handle_driver_location(data):
    """
    Receive driver GPS updates and broadcast to the job room.
    data = { lat, lng, job_id (optional), contractor_id (ignored: session wins) }
    """
    data = data or {}
    identity = current_identity()
    contractor_id = (identity or {}).get("contractor_id")
    if not contractor_id:
        _deny("Only haulers can publish location")
        return

    claimed = data.get("contractor_id")
    if claimed and claimed != contractor_id:
        _deny("contractor_id does not match session")
        return

    coords = _valid_coords(data.get("lat"), data.get("lng"))
    if coords is None:
        _deny("Invalid coordinates")
        return
    lat, lng = coords

    job_id = data.get("job_id")
    if job_id:
        job = db.session.get(Job, job_id)
        if job is None or job.driver_id != contractor_id or job.status not in ACTIVE_JOB_STATUSES:
            _deny("Job is not assigned to you or not active")
            return

    if _rate_limited(contractor_id):
        return  # silently drop bursts

    try:
        contractor = db.session.get(Contractor, contractor_id)
        if contractor:
            contractor.current_lat = lat
            contractor.current_lng = lng
            contractor.last_heartbeat_at = datetime.now(timezone.utc)
            db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("[socket] failed to persist location for %s", contractor_id)

    payload = {"contractor_id": contractor_id, "lat": lat, "lng": lng}
    if job_id:
        # Everyone in the job room (the customer tracking this job)
        emit("driver:location", payload, room=job_id)

    # Admin live map
    socketio.emit("admin:contractor-location", payload, room="admin")


def broadcast_job_status(job_id, status, extra=None):
    """Utility called from REST routes to push status updates via socket."""
    payload = {"job_id": job_id, "status": status}
    if extra:
        payload.update(extra)
    socketio.emit("job:status", payload, room=job_id)
    # Also notify admin room
    socketio.emit("admin:job-status", payload, room="admin")


def broadcast_job_accepted(job_id, driver_id):
    """
    Broadcast job acceptance to ALL online approved contractors.
    Unlike broadcast_job_status (which targets the job room),
    this targets every driver room so they can remove the job from their feed.
    """
    contractors = Contractor.query.filter_by(
        is_online=True, approval_status="approved", is_operator=False
    ).all()
    payload = {"job_id": job_id, "status": "accepted", "driver_id": driver_id}
    for c in contractors:
        # Emit to each driver's personal room
        socketio.emit("job:accepted", payload, room=f"driver:{c.id}")
    # Also notify admin room
    socketio.emit("admin:job-status", payload, room="admin")


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------
@socketio.on("chat:send")
def handle_chat_send(data):
    """
    Receive a chat message via Socket.IO, persist to DB, and broadcast to job room.
    data = { job_id, message, sender_id/sender_role (ignored: session wins) }
    """
    from models import ChatMessage, generate_uuid

    data = data or {}
    job_id = data.get("job_id")
    message = (data.get("message") or "").strip()
    identity = current_identity()

    if not job_id or not message:
        emit("chat:error", {"error": "Missing required fields"}, room=request.sid)
        return

    if len(message) > 2000:
        emit("chat:error", {"error": "Message too long"}, room=request.sid)
        return

    job = db.session.get(Job, job_id)
    sender_role = _chat_role(identity, job)
    if sender_role is None:
        emit("chat:error", {"error": "You do not have access to this job's chat"}, room=request.sid)
        return

    try:
        msg = ChatMessage(
            id=generate_uuid(),
            job_id=job_id,
            sender_id=identity["user_id"],
            sender_role=sender_role,
            message=message,
        )
        db.session.add(msg)
        db.session.commit()

        msg_dict = msg.to_dict()
        emit("chat:message", msg_dict, room=job_id)
    except Exception:
        db.session.rollback()
        logger.exception("[socket] chat:send failed for job %s", job_id)
        emit("chat:error", {"error": "Failed to save message"}, room=request.sid)


@socketio.on("chat:typing")
def handle_chat_typing(data):
    """
    Broadcast typing indicator to the job room.
    data = { job_id, is_typing }  (sender fields come from the session)
    """
    data = data or {}
    job_id = data.get("job_id")
    if not job_id:
        return
    identity = current_identity()
    sender_role = _chat_role(identity, db.session.get(Job, job_id))
    if sender_role is None:
        return
    emit("chat:typing", {
        "job_id": job_id,
        "sender_id": identity["user_id"],
        "sender_role": sender_role,
        "is_typing": bool(data.get("is_typing", True)),
    }, room=job_id, include_self=False)


@socketio.on("chat:read")
def handle_chat_read(data):
    """
    Mark messages as read and notify the sender.
    data = { job_id }  (reader_role comes from the session)
    """
    from models import ChatMessage

    data = data or {}
    job_id = data.get("job_id")
    if not job_id:
        return
    identity = current_identity()
    reader_role = _chat_role(identity, db.session.get(Job, job_id))
    if reader_role is None:
        return

    other_role = "driver" if reader_role == "customer" else "customer"
    now = datetime.now(timezone.utc)

    try:
        updated = (
            ChatMessage.query
            .filter_by(job_id=job_id, sender_role=other_role)
            .filter(ChatMessage.read_at.is_(None))
            .update({"read_at": now})
        )
        db.session.commit()

        if updated > 0:
            emit("chat:read", {
                "job_id": job_id,
                "read_by": reader_role,
                "read_at": now.isoformat(),
                "count": updated,
            }, room=job_id)
    except Exception:
        db.session.rollback()
        logger.exception("[socket] chat:read failed for job %s", job_id)


# ---------------------------------------------------------------------------
# New-job fan-out
# ---------------------------------------------------------------------------
def notify_nearby_drivers(job):
    """
    Called after a new job is created.
    Emits a job:new event to all online approved contractors within range.
    A job without coordinates can't be matched to anyone, so it goes to the
    admin room only — never to every connected socket (audit F03).
    """
    if job.lat is None or job.lng is None:
        socketio.emit("job:new", job.to_dict(), room="admin")
        return

    contractors = Contractor.query.filter_by(is_online=True, approval_status="approved", is_operator=False).all()
    for c in contractors:
        if c.current_lat is None or c.current_lng is None:
            continue
        dist = _haversine(job.lat, job.lng, c.current_lat, c.current_lng)
        if dist <= DRIVER_BROADCAST_RADIUS_KM:
            socketio.emit("job:new", job.to_dict(), room=f"driver:{c.id}")
