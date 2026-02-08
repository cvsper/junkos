"""
Socket.IO event handlers for JunkOS real-time features.
- Driver GPS location streaming
- Job status broadcasts
- New-job alerts to nearby drivers
"""

from math import radians, cos, sin, asin, sqrt
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask import request

from models import db, Contractor, Job

socketio = SocketIO()

EARTH_RADIUS_KM = 6371.0
DRIVER_BROADCAST_RADIUS_KM = 30.0


def _haversine(lat1, lng1, lat2, lng2):
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


@socketio.on("connect")
def handle_connect():
    print("[socket] Client connected: {}".format(request.sid))


@socketio.on("disconnect")
def handle_disconnect():
    print("[socket] Client disconnected: {}".format(request.sid))


@socketio.on("join")
def handle_join(data):
    """Join a room. data = { room: "<job_id>" }"""
    room = data.get("room")
    if room:
        join_room(room)
        emit("joined", {"room": room}, room=request.sid)


@socketio.on("leave")
def handle_leave(data):
    room = data.get("room")
    if room:
        leave_room(room)


@socketio.on("admin:join")
def handle_admin_join():
    """Admin clients join the admin room for live map updates."""
    join_room("admin")
    emit("joined", {"room": "admin"}, room=request.sid)


@socketio.on("admin:leave")
def handle_admin_leave():
    """Admin clients leave the admin room."""
    leave_room("admin")


@socketio.on("driver:location")
def handle_driver_location(data):
    """
    Receive driver GPS updates and broadcast to the job room.
    data = { contractor_id, lat, lng, job_id (optional) }
    """
    contractor_id = data.get("contractor_id")
    lat = data.get("lat")
    lng = data.get("lng")
    job_id = data.get("job_id")

    if not contractor_id or lat is None or lng is None:
        return

    try:
        contractor = db.session.get(Contractor, contractor_id)
        if contractor:
            contractor.current_lat = float(lat)
            contractor.current_lng = float(lng)
            db.session.commit()
    except Exception:
        db.session.rollback()

    if job_id:
        emit("driver:location", {
            "contractor_id": contractor_id,
            "lat": lat,
            "lng": lng,
        }, room=job_id)

    # Broadcast to admin room for live map
    socketio.emit("admin:contractor-location", {
        "contractor_id": contractor_id,
        "lat": lat,
        "lng": lng,
    }, room="admin")


def broadcast_job_status(job_id, status, extra=None):
    """Utility called from REST routes to push status updates via socket."""
    payload = {"job_id": job_id, "status": status}
    if extra:
        payload.update(extra)
    socketio.emit("job:status", payload, room=job_id)
    # Also notify admin room
    socketio.emit("admin:job-status", payload, room="admin")


def notify_nearby_drivers(job):
    """
    Called after a new job is created.
    Emits a job:new event to all online approved contractors within range.
    """
    if job.lat is None or job.lng is None:
        socketio.emit("job:new", job.to_dict(), namespace="/")
        return

    contractors = Contractor.query.filter_by(is_online=True, approval_status="approved").all()
    for c in contractors:
        if c.current_lat is None or c.current_lng is None:
            continue
        dist = _haversine(job.lat, job.lng, c.current_lat, c.current_lng)
        if dist <= DRIVER_BROADCAST_RADIUS_KM:
            socketio.emit("job:new", job.to_dict(), room=c.id)
