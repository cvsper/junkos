"""
Ops Supervisor — rule-based detectors (spec 11, 72h MVP).

Three pure-Python detectors. Each takes the booking (a ``Job`` row) plus
optional extra context and returns either ``None`` (no anomaly) or a
``Detection`` named-tuple carrying ``(tag, severity, confidence, details)``.

Why pure functions and NOT agents
---------------------------------
The 72h MVP is plumbing validation. Using Claude here would add latency,
flakiness, and cost before we've even proven the event bus. v1 replaces
these with a Haiku classifier.

Dependencies: datetime + math only. No network.
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tunables (MVP — match spec §7 hard rules)
# ---------------------------------------------------------------------------
LATE_THRESHOLD_MINUTES = 15
GPS_DEVIATION_MILES = 2.0
GPS_DEVIATION_DURATION_MINUTES = 8

# Confidence the rule engine emits. Fixed in the MVP; v1 learns these.
RULE_CONFIDENCE = 0.90


# ---------------------------------------------------------------------------
# Return shape
# ---------------------------------------------------------------------------
@dataclass
class Detection:
    tag: str
    severity: str      # info | low | medium | high | critical
    confidence: float
    details: dict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _as_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Coerce naive datetimes to UTC-aware so arithmetic is comparable.

    Our models store TIMESTAMP WITHOUT TZ on SQLite but WITH TZ on Postgres;
    callers also pass ``datetime.now(tz=UTC)`` for "now". Normalising here
    keeps the detector math correct in both environments.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in statute miles."""
    R_MI = 3958.7613
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R_MI * c


# ---------------------------------------------------------------------------
# Detector 1 — truck late > 15 min
# ---------------------------------------------------------------------------
def detect_truck_late(booking, now: Optional[datetime] = None) -> Optional[Detection]:
    """Fire when an in-progress / scheduled job is > 15 min past its
    ``scheduled_at`` timestamp.

    NOTE on field naming: the ``Job`` model uses ``scheduled_at`` (not
    ``scheduled_time``). We handle both to keep the detector forward-
    compatible with the spec's terminology.

    A job is "late-eligible" while its status is one of:
        pending, scheduled, dispatched, en_route, in_progress
    (``completed`` / ``cancelled`` jobs cannot be late.)
    """
    if booking is None:
        return None

    status = (getattr(booking, "status", None) or "").lower()
    if status in {"completed", "cancelled", "refunded"}:
        return None

    scheduled = getattr(booking, "scheduled_at", None) or getattr(
        booking, "scheduled_time", None
    )
    if scheduled is None:
        return None

    now = _as_aware(now) or datetime.now(timezone.utc)
    scheduled = _as_aware(scheduled)

    minutes_late = (now - scheduled).total_seconds() / 60.0
    if minutes_late <= LATE_THRESHOLD_MINUTES:
        return None

    # Severity climbs with lateness.
    if minutes_late >= 45:
        severity = "high"
    elif minutes_late >= 30:
        severity = "medium"
    else:
        severity = "low"

    return Detection(
        tag="truck_late",
        severity=severity,
        confidence=RULE_CONFIDENCE,
        details={
            "minutes_late": round(minutes_late, 1),
            "scheduled_at": scheduled.isoformat(),
            "now": now.isoformat(),
            "status": status,
        },
    )


# ---------------------------------------------------------------------------
# Detector 2 — payment failed after job completion
# ---------------------------------------------------------------------------
def detect_payment_failed_post_job(
    booking,
    payment_status: Optional[str] = None,
    stripe_event_type: Optional[str] = None,
) -> Optional[Detection]:
    """Fire when a completed job has a failed payment.

    Signal sources we accept (any one triggers):
      * ``payment_status`` arg (injected by the caller / webhook relay) ==
        "failed".
      * ``stripe_event_type`` arg == "charge.failed" or
        "payment_intent.payment_failed".
      * A ``payment`` relationship on the booking with
        ``payment_status == 'failed'``.
    """
    if booking is None:
        return None

    status = (getattr(booking, "status", None) or "").lower()
    if status != "completed":
        return None

    signals = []
    if payment_status and payment_status.lower() == "failed":
        signals.append("payload.payment_status=failed")
    if stripe_event_type in {"charge.failed", "payment_intent.payment_failed"}:
        signals.append("stripe.event={}".format(stripe_event_type))

    payment = getattr(booking, "payment", None)
    if payment is not None:
        pstatus = (getattr(payment, "payment_status", None) or "").lower()
        if pstatus == "failed":
            signals.append("Payment.payment_status=failed")

    if not signals:
        return None

    return Detection(
        tag="payment_failed_post_job",
        severity="high",
        confidence=RULE_CONFIDENCE,
        details={
            "signals": signals,
            "job_status": status,
        },
    )


# ---------------------------------------------------------------------------
# Detector 3 — GPS deviation > 2 mi for > 8 min
# ---------------------------------------------------------------------------
def detect_gps_deviation(
    booking,
    current_lat: float,
    current_lng: float,
    route_polyline: Optional[str] = None,
    last_on_route_at: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> Optional[Detection]:
    """Fire when the driver is > 2 mi off route and has been off-route for
    > 8 min.

    Polyline decoding is out-of-scope for the 72h MVP (we do not want to pull
    in the Google polyline codec and then discover the producer sends a
    different format). Instead, the fallback spec'd path is: measure the
    distance from the current GPS fix to the job's destination (lat/lng on
    the ``Job`` row) and require the deviation to persist for
    ``GPS_DEVIATION_DURATION_MINUTES`` (caller supplies ``last_on_route_at``).

    If ``route_polyline`` IS provided, we log the input for v1 and still run
    the distance-to-destination fallback — simpler is safer for the MVP.
    """
    if booking is None:
        return None
    if current_lat is None or current_lng is None:
        return None

    dest_lat = getattr(booking, "lat", None)
    dest_lng = getattr(booking, "lng", None)
    if dest_lat is None or dest_lng is None:
        # Without a destination we cannot compute deviation; no-op rather
        # than false-positive.
        return None

    distance_mi = _haversine_miles(
        current_lat, current_lng, float(dest_lat), float(dest_lng)
    )
    if distance_mi <= GPS_DEVIATION_MILES:
        return None

    now = _as_aware(now) or datetime.now(timezone.utc)
    last_on = _as_aware(last_on_route_at)
    if last_on is None:
        # Caller has no state for the driver; assume 9-minute window so we
        # still fire a deviation signal on first ping far from destination.
        # The spec-accurate path (poll every 30s) is a v1 concern.
        minutes_off = GPS_DEVIATION_DURATION_MINUTES + 1.0
    else:
        minutes_off = (now - last_on).total_seconds() / 60.0

    if minutes_off < GPS_DEVIATION_DURATION_MINUTES:
        return None

    return Detection(
        tag="gps_deviation",
        severity="medium",
        confidence=RULE_CONFIDENCE,
        details={
            "distance_from_destination_mi": round(distance_mi, 2),
            "minutes_off_route": round(minutes_off, 1),
            "current_lat": current_lat,
            "current_lng": current_lng,
            "dest_lat": float(dest_lat),
            "dest_lng": float(dest_lng),
            "polyline_provided": bool(route_polyline),
        },
    )


# ---------------------------------------------------------------------------
# Dispatcher — router used by the event ingestion route
# ---------------------------------------------------------------------------
def run_detector_for_event(event_type: str, booking, payload: dict) -> Optional[Detection]:
    """Map an incoming ``OpsEvent.type`` string to the right detector."""
    payload = payload or {}
    et = (event_type or "").lower()

    if et in {"booking.late", "booking.scheduled.late", "ops.booking.late"}:
        return detect_truck_late(booking)

    if et in {
        "payment.failed",
        "stripe.charge.failed",
        "stripe.payment_intent.payment_failed",
        "booking.payment.failed",
    }:
        return detect_payment_failed_post_job(
            booking,
            payment_status=payload.get("payment_status"),
            stripe_event_type=payload.get("stripe_event_type") or et,
        )

    if et in {"booking.gps", "booking.gps.deviation", "ops.booking.gps"}:
        # payload carries {lat, lng, route_polyline?, last_on_route_at?}
        last_on = payload.get("last_on_route_at")
        if isinstance(last_on, str):
            try:
                last_on = datetime.fromisoformat(last_on.replace("Z", "+00:00"))
            except ValueError:
                last_on = None
        return detect_gps_deviation(
            booking,
            current_lat=payload.get("lat"),
            current_lng=payload.get("lng"),
            route_polyline=payload.get("route_polyline"),
            last_on_route_at=last_on,
        )

    logger.debug("No detector registered for event type %r", event_type)
    return None


__all__ = [
    "Detection",
    "detect_truck_late",
    "detect_payment_failed_post_job",
    "detect_gps_deviation",
    "run_detector_for_event",
    "LATE_THRESHOLD_MINUTES",
    "GPS_DEVIATION_MILES",
    "GPS_DEVIATION_DURATION_MINUTES",
]
