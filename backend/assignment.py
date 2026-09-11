"""Umuve assignment domain — ONE way to put a contractor on a job.

Audit findings F15 / F16 / F17 (2026-09-10) are closed here:

  F15  ``assign_job(job_id, contractor_id, actor, source)`` locks the job row
       (``SELECT ... FOR UPDATE`` on Postgres), flips it with a conditional
       UPDATE (``status = <expected> AND version = <expected> AND driver_id
       IS NULL``), reserves the contractor's time window in
       ``contractor_reservations`` with a conditional INSERT inside the same
       transaction (plus a per-contractor advisory lock on Postgres), writes a
       ``job_events`` row and commits atomically. Every path — dispatcher
       auto-assign, broadcast/offer acceptance, the app's accept button,
       admin + VA-desk manual assignment, fleet delegation, concierge — calls
       it. Terminal jobs are never re-assigned; corrections go through the
       audited ``reassign_job``.

  F16  ``eligibility(job, contractor, at, mode)`` is the single rule set:
       approval, online + fresh heartbeat (sameday.is_live), availability
       schedule, verified documents valid through the slot, capacity (volume
       and weight when both are known — unknown volume is a *warning*, not a
       block), radius / fleet scope, reservation + schedule conflicts, and a
       per-job decline exclusion (job_offers.exclude_until). The dispatcher's
       candidate search, the offer wave, same-day capacity and acceptance all
       use it, so "we have coverage" and "we can assign" agree.

  F17  ``transition_job`` is the versioned state machine behind
       routes/drivers.apply_job_status_transition: conditional UPDATE on
       (status, version) → 409 on a stale writer; actor guards (only the
       assigned contractor, or an admin with an audited override); start needs
       an arrival ack; completion needs proof (after-photo OR the customer's
       handoff PIN OR an audited exception), no open change order, and a
       settled payment. Every transition appends an immutable ``job_events``
       row.

Nothing in this module fires notifications, sockets, SMS or payouts — those
stay with the callers, which run them only after a successful commit.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import List, NamedTuple, Optional

from sqlalchemy import and_, func, literal, select, text

from models import (
    db, Contractor, ContractorReservation, Job, JobEvent, JobOffer,
    OperatorDocumentVerification, generate_uuid, utcnow,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status vocabularies
# ---------------------------------------------------------------------------
TERMINAL_STATUSES = ("completed", "cancelled", "paid", "refunded")
# A driver can be put on a job from these (pending = booked, awaiting payment;
# manual desk/admin assignment of a phone booking is allowed before the pay
# link is settled — the app's self-serve accept is not, see assign_job).
ASSIGNABLE_STATUSES = ("pending", "confirmed", "broadcasting")
# A fleet operator can receive a job for delegation from these.
DELEGATABLE_STATUSES = ("pending", "confirmed", "broadcasting", "delegating")
# Statuses in which a contractor is "on" the job (reservation is live).
ACTIVE_STATUSES = ("assigned", "accepted", "en_route", "arrived", "started")
IN_PROGRESS_STATUSES = ("en_route", "arrived", "started")

VALID_STATUS_TRANSITIONS = {
    "assigned": ["accepted", "cancelled"],
    "accepted": ["en_route", "cancelled"],
    "en_route": ["arrived", "cancelled"],
    "arrived": ["started", "cancelled"],
    "started": ["completed"],
}

ADMIN_ROLES = ("admin", "manager")

# Window a contractor is reserved for per job (hours after scheduled_at).
try:
    RESERVATION_HOURS = float(os.environ.get("RESERVATION_HOURS", "2") or 2)
except (TypeError, ValueError):
    RESERVATION_HOURS = 2.0
# A hauler who declines a job is not re-offered / auto-assigned that job for this long.
try:
    DECLINE_EXCLUSION_MINUTES = int(os.environ.get("DECLINE_EXCLUSION_MINUTES", "120") or 120)
except (TypeError, ValueError):
    DECLINE_EXCLUSION_MINUTES = 120

# How strict eligibility is, by who is asking.
#   auto     silent single-hauler auto-assign: must be live, in radius, not concierge
#   offer    building an SMS offer wave / capacity count: online (or standby) + in radius
#   accept   a hauler redeeming an offer or tapping accept: hard rules only
#   manual   admin / VA desk / fleet operator putting someone on a job: hard rules only
SOURCE_MODE = {
    "auto": "auto",
    "offer": "accept",
    "driver_accept": "accept",
    "admin": "manual",
    "va_desk": "manual",
    "fleet_delegate": "manual",
    "concierge": "manual",
    "reassign": "manual",
}
_STRICT_MODES = ("auto", "offer")

# Reasons an admin may override with ``force=True`` (audited). Never the rest.
FORCEABLE_REASONS = {
    "offline", "stale_heartbeat", "outside_schedule", "out_of_radius",
    "declined_recently", "schedule_conflict", "concierge_needs_offer",
}


class Eligibility(NamedTuple):
    ok: bool
    reasons: List[str]        # hard blockers
    warnings: List[str]       # allowed, but flagged (e.g. volume_unknown)
    distance_miles: Optional[float]


class AssignResult(NamedTuple):
    ok: bool
    code: str                 # assigned | already_assigned | taken | terminal | ineligible | ...
    http_status: int
    reasons: List[str]
    warnings: List[str]
    job: Optional[object]
    contractor: Optional[object]
    pin: Optional[str]        # plaintext handoff PIN, only on a fresh driver assignment
    message: str

    def to_dict(self):
        return {
            "ok": self.ok, "code": self.code, "reasons": list(self.reasons),
            "warnings": list(self.warnings), "message": self.message,
            "job": self.job.to_dict() if self.job is not None else None,
        }


_MESSAGES = {
    "assigned": "Assigned.",
    "already_assigned": "This job is already yours.",
    "taken": "Another hauler already has this job.",
    "terminal": "This job is finished or cancelled and can't be assigned.",
    "cancelled": "This job was cancelled.",
    "not_assignable": "This job can't be assigned in its current status.",
    "version_conflict": "The job changed while you were looking at it — refresh and try again.",
    "reservation_conflict": "That hauler is already booked for an overlapping job.",
    "ineligible": "That hauler isn't eligible for this job.",
    "not_approved": "Contractor is not approved",
    "payment_pending": "Job is awaiting payment and cannot be accepted yet",
    "payment_blocked": "This job's payment was refunded or disputed — it can't be assigned.",
    "offer_expired": "This offer has expired.",
    "offer_mismatch": "This offer doesn't belong to that hauler.",
    "job_not_found": "Job not found",
    "contractor_not_found": "Contractor not found",
    "reason_required": "A reason is required.",
    "error": "Something went wrong. Please try again.",
}
_HTTP = {
    "assigned": 200, "already_assigned": 200, "job_not_found": 404,
    "contractor_not_found": 404, "not_approved": 403, "ineligible": 422,
    "reason_required": 400, "error": 500,
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _naive(dt):
    """DateTime columns round-trip naive UTC; utcnow() is aware. Normalise."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _now(at=None):
    return _naive(at) if at is not None else datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_actor(actor):
    """Accept a dict, a User-like object, a bare string label, or None."""
    if actor is None:
        return {"user_id": None, "role": "system", "name": "system"}
    if isinstance(actor, dict):
        return {
            "user_id": actor.get("user_id") or actor.get("id"),
            "role": (actor.get("role") or "system"),
            "name": actor.get("name") or actor.get("email") or actor.get("role") or "system",
        }
    if isinstance(actor, str):
        return {"user_id": None, "role": "system", "name": actor[:120]}
    return {
        "user_id": getattr(actor, "id", None),
        "role": getattr(actor, "role", None) or "system",
        "name": getattr(actor, "name", None) or getattr(actor, "email", None) or "system",
    }


def is_admin_actor(actor):
    return (normalize_actor(actor).get("role") or "") in ADMIN_ROLES


def job_window(job, at=None):
    """(starts_at, ends_at) naive-UTC window the contractor is reserved for."""
    start = _naive(getattr(job, "scheduled_at", None)) or _now(at)
    return start, start + timedelta(hours=RESERVATION_HOURS)


def payment_status(job):
    p = getattr(job, "payment", None)
    return getattr(p, "payment_status", None) if p is not None else None


def point_job(lat=None, lng=None, scheduled_at=None, volume_estimate=None, operator_id=None):
    """A job-shaped stand-in for coverage / capacity checks before a Job row exists."""
    return SimpleNamespace(
        id=None, lat=lat, lng=lng, scheduled_at=_naive(scheduled_at),
        volume_estimate=volume_estimate, operator_id=operator_id, status="confirmed",
        driver_id=None,
    )


def record_event(job_id, from_status, to_status, actor, reason=None, meta=None):
    """Append a job_events row to the current transaction (no commit)."""
    a = normalize_actor(actor)
    ev = JobEvent(
        id=generate_uuid(), job_id=job_id, from_status=from_status, to_status=to_status,
        actor_user_id=a.get("user_id"), actor_role=(a.get("role") or "system")[:20],
        reason=(reason or None), meta=dict(meta or {}, actor_name=a.get("name")),
    )
    db.session.add(ev)
    return ev


# ---------------------------------------------------------------------------
# Handoff PIN (F17): minted at assignment, stored hashed, texted to the customer
# ---------------------------------------------------------------------------
def _pin_secret():
    return (os.environ.get("JWT_SECRET") or os.environ.get("SECRET_KEY") or "umuve-dev").encode()


def derive_pin(job_id, salt):
    """Deterministic 4-digit PIN from (server secret, job, per-assignment salt).

    Lets the customer text include the PIN at assignment AND at the hauler's
    confirmation without storing plaintext on the job; verification always
    goes through the stored hash (verify_pin), which survives secret rotation.
    """
    if not job_id or not salt:
        return None
    mac = hmac.new(_pin_secret(), "{}:{}".format(job_id, salt).encode(), hashlib.sha256).digest()
    return "{:04d}".format(int.from_bytes(mac[:4], "big") % 10000)


def _pin_hash(salt, pin):
    return hashlib.sha256("{}:{}".format(salt, pin).encode()).hexdigest()


def mint_pin(job_id):
    """(pin, salt, hash) for a fresh assignment."""
    salt = secrets.token_hex(4)
    pin = derive_pin(job_id, salt)
    return pin, salt, _pin_hash(salt, pin)


def current_pin(job):
    """Re-derive the customer's PIN for a text (None when unset / secret rotated)."""
    salt = getattr(job, "completion_pin_salt", None)
    if not salt or not getattr(job, "completion_pin_hash", None):
        return None
    pin = derive_pin(job.id, salt)
    if pin and hmac.compare_digest(_pin_hash(salt, pin), job.completion_pin_hash):
        return pin
    return None


def verify_pin(job, pin):
    salt, h = getattr(job, "completion_pin_salt", None), getattr(job, "completion_pin_hash", None)
    if not salt or not h or not pin:
        return False
    digits = "".join(ch for ch in str(pin) if ch.isdigit())
    if len(digits) != 4:
        return False
    return hmac.compare_digest(_pin_hash(salt, digits), h)


def pin_sms_line(pin):
    """The additive sentence appended to the customer's confirmation text."""
    if not pin:
        return ""
    return " Your handoff PIN is {} — give it to your hauler only once the job is done.".format(pin)


# ---------------------------------------------------------------------------
# F16: eligibility
# ---------------------------------------------------------------------------
def _standby_for(job):
    try:
        import sameday
        when = _naive(getattr(job, "scheduled_at", None))
        day = sameday._local_date_of(when) if when else sameday._local_today()
        return sameday.standby_ids(day)
    except Exception:
        return set()


def _live(contractor, now, on_standby):
    from sameday import is_live
    return is_live(contractor, now, on_standby)


_DAY_KEYS = {
    0: ("mon", "monday"), 1: ("tue", "tues", "tuesday"), 2: ("wed", "wednesday"),
    3: ("thu", "thur", "thurs", "thursday"), 4: ("fri", "friday"),
    5: ("sat", "saturday"), 6: ("sun", "sunday"),
}


def _parse_hhmm(v):
    try:
        parts = str(v).strip().split(":")
        return int(parts[0]) * 60 + (int(parts[1]) if len(parts) > 1 else 0)
    except (TypeError, ValueError, IndexError):
        return None


def schedule_allows(schedule, when_utc):
    """True / False / None(unknown) — does the contractor's availability_schedule
    cover the local time of ``when_utc``?

    Tolerant of the shapes the apps have sent: {"mon": true}, {"monday":
    [{"start": "08:00", "end": "17:00"}]}, {"1": ["08:00-17:00"]}, or
    {"days": [...]} at the top level. Empty / unparseable → None (unknown).
    """
    if not schedule or not isinstance(schedule, dict) or when_utc is None:
        return None
    try:
        from timeutils import to_local
        local = to_local(when_utc.replace(tzinfo=timezone.utc))
    except Exception:
        local = when_utc
    sched = schedule.get("days") if isinstance(schedule.get("days"), dict) else schedule
    if not isinstance(sched, dict):
        return None
    keys = set(_DAY_KEYS[local.weekday()]) | {str(local.weekday()), local.strftime("%A").lower()}
    entry = None
    for k, v in sched.items():
        if str(k).strip().lower() in keys:
            entry = v
            break
    if entry is None:
        # Day not mentioned: only meaningful if the schedule is a per-day map.
        if any(str(k).strip().lower() in sum(_DAY_KEYS.values(), ()) for k in sched):
            return False
        return None
    if isinstance(entry, bool):
        return entry
    if isinstance(entry, dict):
        entry = [entry]
    if not isinstance(entry, (list, tuple)):
        return None
    if not entry:
        return False
    minute = local.hour * 60 + local.minute
    for w in entry:
        if isinstance(w, str) and "-" in w:
            a, b = w.split("-", 1)
            s, e = _parse_hhmm(a), _parse_hhmm(b)
        elif isinstance(w, dict):
            s, e = _parse_hhmm(w.get("start") or w.get("from")), _parse_hhmm(w.get("end") or w.get("to"))
        else:
            continue
        if s is None or e is None:
            continue
        if s <= minute <= e:
            return True
    return False


def documents_status(contractor, through):
    """'ok' | 'expired' | 'rejected' | 'unknown' — are the hauler's verified
    documents valid through ``through`` (the end of the job slot)?"""
    if (getattr(contractor, "documents_verification_status", None) or "") == "failed":
        return "rejected"
    expiries = [
        getattr(contractor, "insurance_expiry", None),
        getattr(contractor, "license_expiry", None),
        getattr(contractor, "vehicle_registration_expiry", None),
    ]
    try:
        rows = OperatorDocumentVerification.query.filter_by(contractor_id=contractor.id).all()
    except Exception:
        rows = []
    for r in rows:
        if r.status == "rejected":
            return "rejected"
        if r.expiry_date:
            expiries.append(r.expiry_date)
    known = [_naive(e) for e in expiries if e]
    if any(e < _naive(through) for e in known):
        return "expired"
    return "ok" if known else "unknown"


def reservation_conflict(contractor_id, starts, ends, exclude_job_id=None):
    """Is there a LIVE reservation for this contractor overlapping [starts, ends)?"""
    return db.session.query(_reservation_conflict_exists(contractor_id, starts, ends, exclude_job_id)).scalar()


def _reservation_conflict_select(contractor_id, starts, ends, exclude_job_id=None):
    R, J = ContractorReservation.__table__, Job.__table__
    conds = [
        R.c.contractor_id == contractor_id,
        R.c.status == "active",
        R.c.starts_at < ends,
        R.c.ends_at > starts,
        J.c.driver_id == contractor_id,
        J.c.status.in_(ACTIVE_STATUSES),
    ]
    if exclude_job_id:
        conds.append(R.c.job_id != exclude_job_id)
    return select(R.c.id).select_from(R.join(J, J.c.id == R.c.job_id)).where(and_(*conds))


def _reservation_conflict_exists(contractor_id, starts, ends, exclude_job_id=None):
    return _reservation_conflict_select(contractor_id, starts, ends, exclude_job_id).exists()


def schedule_conflict(contractor_id, starts, ends, exclude_job_id=None, now=None):
    """Legacy job-row conflict check (jobs assigned before reservations existed
    still count). True if the contractor has an active job whose own window
    overlaps [starts, ends), or is mid-job right now while this slot is now."""
    now = now or _now()
    q = Job.query.filter(Job.driver_id == contractor_id, Job.status.in_(ACTIVE_STATUSES))
    if exclude_job_id:
        q = q.filter(Job.id != exclude_job_id)
    span = timedelta(hours=RESERVATION_HOURS)
    scheduled = q.filter(
        Job.scheduled_at.isnot(None),
        Job.scheduled_at < ends,
        Job.scheduled_at > starts - span,
    ).first()
    if scheduled is not None:
        return True
    if starts <= now + span:
        live = q.filter(Job.status.in_(IN_PROGRESS_STATUSES)).first()
        if live is not None:
            return True
    return False


def declined_recently(job_id, contractor_id, now=None):
    if not job_id:
        return False
    now = now or _now()
    o = JobOffer.query.filter(
        JobOffer.job_id == job_id, JobOffer.contractor_id == contractor_id,
        JobOffer.status == "declined", JobOffer.exclude_until.isnot(None),
    ).order_by(JobOffer.exclude_until.desc()).first()
    return bool(o and _naive(o.exclude_until) > now)


def eligibility(job, contractor, at=None, mode="auto", on_standby=None, radius_miles=None):
    """Can ``contractor`` take ``job`` at ``at``?  → Eligibility(ok, reasons, warnings, distance).

    ``mode`` (see SOURCE_MODE) decides which soft rules are blockers:
    auto/offer treat offline / out-of-radius / declined as blockers, accept and
    manual only flag them. Approval, fleet scope, documents, capacity (when
    both sides are known), and reservation / schedule conflicts always block.
    """
    from dispatcher import haversine, MAX_RADIUS_MILES
    reasons, warnings = [], []
    now = _now(at)
    strict = mode in _STRICT_MODES
    c = contractor
    starts, ends = job_window(job, now)
    job_id = getattr(job, "id", None)

    if getattr(job, "status", None) in TERMINAL_STATUSES:
        reasons.append("job_terminal")
    if (c.approval_status or "") != "approved":
        reasons.append("not_approved")
    if c.is_operator:
        reasons.append("operator_account")          # operators delegate; they don't haul
    op_id = getattr(job, "operator_id", None)
    if op_id and c.operator_id != op_id and c.id != op_id:
        reasons.append("outside_fleet")
    if mode == "auto" and getattr(c, "is_concierge", False):
        reasons.append("concierge_needs_offer")     # can't act on a silent app assignment

    # online + fresh heartbeat (same rule as the same-day desk: sameday.is_live)
    standby = on_standby if on_standby is not None else _standby_for(job)
    on_roster = bool(standby and c.id in standby)
    if not _live(c, now, standby):
        if getattr(c, "is_concierge", False):
            if mode == "auto":
                reasons.append("not_live")
        elif not c.is_online and not on_roster:
            (reasons if strict else warnings).append("offline")
        else:
            (reasons if mode == "auto" else warnings).append("stale_heartbeat")

    # availability schedule (only when the hauler set one)
    allowed = schedule_allows(getattr(c, "availability_schedule", None), starts)
    if allowed is False and not on_roster:
        (reasons if strict else warnings).append("outside_schedule")

    # documents valid through the slot
    docs = documents_status(c, ends)
    if docs == "expired":
        reasons.append("documents_expired")
    elif docs == "rejected":
        reasons.append("documents_rejected")
    elif docs == "unknown":
        warnings.append("documents_unverified")

    # capacity: volume + weight when both sides are known; unknown = warning
    vol = getattr(job, "volume_estimate", None)
    cap = getattr(c, "truck_capacity", None)
    if vol and cap and float(cap) < float(vol):
        reasons.append("truck_too_small")
    elif not vol:
        warnings.append("volume_unknown")
    elif not cap:
        warnings.append("truck_capacity_unknown")
    wj = getattr(job, "weight_estimate", None)
    wc = getattr(c, "truck_max_weight", None)
    if wj and wc and float(wc) < float(wj):
        reasons.append("truck_weight_exceeded")

    # radius
    dist = None
    radius = float(radius_miles) if radius_miles else MAX_RADIUS_MILES
    lat, lng = getattr(job, "lat", None), getattr(job, "lng", None)
    if lat is not None and lng is not None and c.current_lat is not None and c.current_lng is not None:
        dist = round(haversine(c.current_lat, c.current_lng, lat, lng), 1)
        if dist > radius:
            (reasons if strict else warnings).append("out_of_radius")
    else:
        warnings.append("location_unknown")

    # conflicting work (reservations first, then legacy job rows)
    if reservation_conflict(c.id, starts, ends, exclude_job_id=job_id):
        reasons.append("reservation_conflict")
    elif schedule_conflict(c.id, starts, ends, exclude_job_id=job_id, now=now):
        reasons.append("schedule_conflict")

    # per-job decline exclusion
    if declined_recently(job_id, c.id, now):
        (reasons if strict else warnings).append("declined_recently")
    # reliability (hauler_reliability): a hauler with no completed job is not
    # handed work by a SILENT auto-assignment — a person confirms them first.
    # Offer waves and manual assignment still reach them, flagged, because an
    # all-new pool would otherwise get no work at all. A no-show history blocks
    # in strict modes and warns elsewhere.
    try:
        from hauler_reliability import tier as _tier, TIER_NEW, TIER_FLAGGED
        t = _tier(c.id)
        if t == TIER_FLAGGED:
            (reasons if strict else warnings).append("no_show_history")
        elif t == TIER_NEW:
            (reasons if mode == "auto" else warnings).append("first_job_needs_call")
    except Exception:
        pass
    return Eligibility(not reasons, reasons, warnings, dist)


def contractor_pool(job):
    """Approved, non-operator contractors in scope for ``job`` (fleet-scoped
    when the job belongs to an operator). Eligibility does the real work."""
    q = Contractor.query.filter_by(approval_status="approved")
    op_id = getattr(job, "operator_id", None)
    if op_id:
        q = q.filter_by(operator_id=op_id)
    else:
        q = q.filter(Contractor.is_operator.is_(False))
    return q.all()


def assignable_contractors(job, at=None, mode="offer", on_standby=None, radius_miles=None, pool=None):
    """[{contractor, verdict, distance_miles}] eligible for ``job`` under
    ``mode``, nearest first (unknown distance last). The coverage / capacity
    number and the dispatcher's candidate list both come from here."""
    now = _now(at)
    standby = on_standby if on_standby is not None else _standby_for(job)
    out = []
    for c in (pool if pool is not None else contractor_pool(job)):
        v = eligibility(job, c, now, mode=mode, on_standby=standby, radius_miles=radius_miles)
        if v.ok:
            out.append({"contractor": c, "verdict": v, "distance_miles": v.distance_miles})
    out.sort(key=lambda e: e["distance_miles"] if e["distance_miles"] is not None else 1e9)
    return out


def count_assignable(job, at=None, mode="offer", **kw):
    return len(assignable_contractors(job, at, mode=mode, **kw))


# ---------------------------------------------------------------------------
# F15: assign_job
# ---------------------------------------------------------------------------
def _fail(code, reasons=None, warnings=None, job=None, contractor=None, message=None):
    return AssignResult(
        ok=False, code=code, http_status=_HTTP.get(code, 409),
        reasons=list(reasons or []), warnings=list(warnings or []),
        job=job, contractor=contractor, pin=None,
        message=message or _MESSAGES.get(code, _MESSAGES["error"]),
    )


def _lock_job(job_id):
    """Row-lock the job on Postgres; a plain read on SQLite (the conditional
    UPDATE below is the guard there)."""
    q = Job.query.filter(Job.id == job_id)
    try:
        if db.session.get_bind().dialect.name == "postgresql":
            q = q.with_for_update()
    except Exception:
        pass
    return q.first()


def _version_expr():
    return func.coalesce(Job.__table__.c.version, 1)


def _reserve(contractor_id, job_id, starts, ends, source):
    """Reserve [starts, ends) for the contractor inside the current transaction.

    Postgres: per-contractor advisory lock + conditional INSERT (NOT EXISTS an
    overlapping live reservation). SQLite: the same conditional INSERT — the
    write lock taken by the job UPDATE already serialises writers.
    Returns True when the reservation is held.
    """
    R = ContractorReservation.__table__
    try:
        if db.session.get_bind().dialect.name == "postgresql":
            db.session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
                               {"k": "contractor_reservation:{}".format(contractor_id)})
    except Exception:
        logger.exception("advisory lock failed for contractor %s", contractor_id)

    conflict = _reservation_conflict_exists(contractor_id, starts, ends, exclude_job_id=job_id)
    existing = ContractorReservation.query.filter_by(contractor_id=contractor_id, job_id=job_id).first()
    if existing is not None:
        # Re-assignment of the same pair (e.g. declined then re-offered): refresh
        # the window, but only if nothing else moved into it meanwhile.
        if db.session.query(conflict).scalar():
            return False
        existing.starts_at, existing.ends_at = starts, ends
        existing.status, existing.released_at, existing.source = "active", None, source
        db.session.flush()
        return True

    now = _now()
    ins = R.insert().from_select(
        ["id", "contractor_id", "job_id", "starts_at", "ends_at", "status", "source", "created_at"],
        select(
            literal(generate_uuid()), literal(contractor_id), literal(job_id),
            literal(starts), literal(ends), literal("active"), literal(source), literal(now),
        ).where(~conflict),
    )
    res = db.session.execute(ins)
    return res.rowcount == 1


def release_reservation(job_id, contractor_id=None):
    """Mark the job's reservation(s) released (no commit)."""
    q = ContractorReservation.query.filter_by(job_id=job_id, status="active")
    if contractor_id:
        q = q.filter_by(contractor_id=contractor_id)
    n = 0
    for r in q.all():
        r.status, r.released_at = "released", _now()
        n += 1
    return n


def _assign_locked(job, contractor, actor, source, target_status, offer, expected_version, force, reason, at):
    """Body of assign_job once job + contractor are loaded. No commit."""
    a = normalize_actor(actor)
    mode = SOURCE_MODE.get(source, "manual")
    now = utcnow()
    delegation = bool(contractor.is_operator)
    warnings = []

    if (not delegation and job.driver_id == contractor.id and job.status in ACTIVE_STATUSES) or \
            (delegation and job.operator_id == contractor.id and job.status == "delegating" and not job.driver_id):
        return AssignResult(True, "already_assigned", 200, [], [], job, contractor, None, _MESSAGES["already_assigned"])
    if job.status in TERMINAL_STATUSES:
        return _fail("cancelled" if job.status == "cancelled" else "terminal", job=job, contractor=contractor)
    if expected_version is not None and int(expected_version) != int(job.version or 1):
        return _fail("version_conflict", job=job, contractor=contractor)
    # driver_id first: "someone already has this job" is the truer message
    # than "wrong status" when a concurrent path won the race.
    if job.driver_id:
        return _fail("taken", job=job, contractor=contractor)
    if job.status not in (DELEGATABLE_STATUSES if delegation else ASSIGNABLE_STATUSES):
        return _fail("not_assignable", job=job, contractor=contractor)

    pay = payment_status(job)
    if pay in ("refunded", "disputed"):
        return _fail("payment_blocked", job=job, contractor=contractor)
    if source == "driver_accept" and job.status == "pending":
        return _fail("payment_pending", job=job, contractor=contractor)

    if offer is not None:
        if offer.job_id != job.id or offer.contractor_id != contractor.id:
            return _fail("offer_mismatch", job=job, contractor=contractor)
        if offer.expires_at and _naive(offer.expires_at) < _now():
            return _fail("offer_expired", job=job, contractor=contractor)

    if delegation:
        if (contractor.approval_status or "") != "approved":
            return _fail("not_approved", ["not_approved"], job=job, contractor=contractor)
        if job.operator_id and job.operator_id != contractor.id:
            return _fail("ineligible", ["outside_fleet"], job=job, contractor=contractor)
    else:
        v = eligibility(job, contractor, at, mode=mode)
        warnings = list(v.warnings)
        if not v.ok:
            if "not_approved" in v.reasons:
                return _fail("not_approved", v.reasons, v.warnings, job, contractor)
            if force and (a.get("role") in ADMIN_ROLES) and set(v.reasons) <= FORCEABLE_REASONS:
                warnings.extend("forced:" + r for r in v.reasons)
            else:
                return _fail("ineligible", v.reasons, v.warnings, job, contractor,
                             message="{} ({})".format(_MESSAGES["ineligible"], ", ".join(v.reasons)))

    # --- Conditional UPDATE on the job row (the F15 guard) ---
    from_status = job.status
    new_status = target_status or ("delegating" if delegation else "assigned")
    values = {"status": new_status, "updated_at": now, "version": _version_expr() + 1}
    where = [Job.id == job.id, Job.status == from_status, _version_expr() == int(job.version or 1)]
    pin = None
    if delegation:
        values["operator_id"] = contractor.id
        where.append(Job.driver_id.is_(None))
    else:
        values["driver_id"] = contractor.id
        where.append(Job.driver_id.is_(None))
        if contractor.operator_id:
            values["operator_id"] = contractor.operator_id   # fleet driver → operator commission
        if source == "fleet_delegate":
            values["delegated_at"] = now
        pin, salt, h = mint_pin(job.id)
        values.update(completion_pin_salt=salt, completion_pin_hash=h, completion_pin_verified_at=None)

    res = db.session.execute(Job.__table__.update().where(and_(*where)).values(**values))
    if res.rowcount != 1:
        db.session.rollback()
        db.session.refresh(job)
        if job.status == "cancelled":
            return _fail("cancelled", job=job, contractor=contractor)
        if job.driver_id and job.driver_id != contractor.id:
            return _fail("taken", job=job, contractor=contractor)
        if job.driver_id == contractor.id:
            return AssignResult(True, "already_assigned", 200, [], [], job, contractor, None, _MESSAGES["already_assigned"])
        return _fail("version_conflict" if job.status == from_status else "not_assignable", job=job, contractor=contractor)

    if not delegation:
        starts, ends = job_window(job, at)
        if not _reserve(contractor.id, job.id, starts, ends, source):
            db.session.rollback()
            db.session.refresh(job)
            return _fail("reservation_conflict", ["reservation_conflict"], warnings, job, contractor)

        # Offer bookkeeping: the redeemed offer wins, every sibling is superseded.
        if offer is not None:
            offer.status, offer.responded_at = "accepted", now
        siblings = JobOffer.query.filter(JobOffer.job_id == job.id, JobOffer.status == "sent")
        if offer is not None:
            siblings = siblings.filter(JobOffer.id != offer.id)
        siblings.update({"status": "superseded", "responded_at": now}, synchronize_session=False)

    record_event(job.id, from_status, new_status, a, reason=reason, meta={
        "kind": "delegated" if delegation else "assigned", "source": source,
        "contractor_id": contractor.id, "warnings": warnings,
        "offer_id": getattr(offer, "id", None), "forced": bool(force and warnings and any(w.startswith("forced:") for w in warnings)),
    })
    return AssignResult(True, "assigned", 200, [], warnings, job, contractor, pin, _MESSAGES["assigned"])


def assign_job(job_id, contractor_id, actor, source, *, target_status=None, offer=None,
               expected_version=None, force=False, reason=None, at=None):
    """Put ``contractor_id`` on ``job_id`` atomically. Never raises.

    actor   dict/user/label of who is doing it (audited on job_events)
    source  auto | offer | driver_accept | admin | va_desk | fleet_delegate | concierge | reassign
    target_status   'assigned' (default) or 'accepted' for the app's self-claim
    offer   JobOffer being redeemed (status/expiry checked, siblings superseded)
    expected_version   optimistic-lock guard from the caller's view of the job
    force   admin-only override of soft eligibility reasons (audited)
    """
    try:
        contractor = db.session.get(Contractor, contractor_id) if contractor_id else None
        if contractor is None:
            return _fail("contractor_not_found")
        job = _lock_job(job_id)
        if job is None:
            return _fail("job_not_found", contractor=contractor)
        result = _assign_locked(job, contractor, actor, source, target_status, offer,
                                expected_version, force, reason, at)
        if result.ok and result.code == "assigned":
            db.session.commit()
            db.session.refresh(job)
            logger.info("ASSIGN: job %s -> contractor %s via %s (warnings=%s)",
                        job.id, contractor.id, source, result.warnings)
        else:
            # Guard failures did not write; keep the session clean for the caller.
            db.session.rollback()
        return result
    except Exception:
        logger.exception("assign_job failed for job %s / contractor %s", job_id, contractor_id)
        try:
            db.session.rollback()
        except Exception:
            pass
        return _fail("error")


def release_job(job, actor, reason=None, source="release", new_status="confirmed", expected_version=None,
                requeue=True):
    """Take the current contractor off a live job (decline / hauler cancel /
    reassignment) with the same conditional-UPDATE guard, release the
    reservation and record the event. Returns (ok, code). Commits on success."""
    try:
        a = normalize_actor(actor)
        if job.status in TERMINAL_STATUSES:
            return False, "terminal"
        if expected_version is not None and int(expected_version) != int(job.version or 1):
            return False, "version_conflict"
        from_status, prev_driver, prev_operator = job.status, job.driver_id, job.operator_id
        values = {"driver_id": None, "status": new_status if requeue else job.status,
                  "updated_at": utcnow(), "version": _version_expr() + 1,
                  "completion_pin_hash": None, "completion_pin_salt": None}
        res = db.session.execute(
            Job.__table__.update()
            .where(and_(Job.id == job.id, Job.status == from_status, _version_expr() == int(job.version or 1)))
            .values(**values))
        if res.rowcount != 1:
            db.session.rollback()
            db.session.refresh(job)
            return False, "version_conflict"
        release_reservation(job.id, prev_driver)
        record_event(job.id, from_status, values["status"], a, reason=reason, meta={
            "kind": "released", "source": source, "contractor_id": prev_driver, "operator_id": prev_operator,
        })
        db.session.commit()
        db.session.refresh(job)
        return True, "released"
    except Exception:
        logger.exception("release_job failed for job %s", getattr(job, "id", "?"))
        try:
            db.session.rollback()
        except Exception:
            pass
        return False, "error"


def reassign_job(job_id, contractor_id, actor, reason, *, force=False, at=None):
    """Audited correction: move a LIVE (non-terminal) job to another contractor.

    Requires a reason. Releases the current hauler (event 'reassign_release'),
    then runs the normal assign_job guards for the new one in the same
    transaction. Terminal jobs are refused — their assignment and payout
    recipient are history, not state to overwrite.
    """
    if not (reason or "").strip():
        return _fail("reason_required")
    try:
        contractor = db.session.get(Contractor, contractor_id) if contractor_id else None
        if contractor is None:
            return _fail("contractor_not_found")
        job = _lock_job(job_id)
        if job is None:
            return _fail("job_not_found", contractor=contractor)
        if job.status in TERMINAL_STATUSES:
            db.session.rollback()
            return _fail("terminal", job=job, contractor=contractor)
        a = normalize_actor(actor)
        from_status, prev_driver = job.status, job.driver_id
        if prev_driver or job.status not in ASSIGNABLE_STATUSES:
            res = db.session.execute(
                Job.__table__.update()
                .where(and_(Job.id == job.id, Job.status == from_status, _version_expr() == int(job.version or 1)))
                .values(driver_id=None, status="confirmed", updated_at=utcnow(), version=_version_expr() + 1))
            if res.rowcount != 1:
                db.session.rollback()
                db.session.refresh(job)
                return _fail("version_conflict", job=job, contractor=contractor)
            release_reservation(job.id, prev_driver)
            record_event(job.id, from_status, "confirmed", a, reason=reason, meta={
                "kind": "reassign_release", "contractor_id": prev_driver, "new_contractor_id": contractor.id})
            db.session.flush()
            db.session.refresh(job)
        result = _assign_locked(job, contractor, a, "reassign", "assigned", None, None, force, reason, at)
        if result.ok and result.code == "assigned":
            db.session.commit()
            db.session.refresh(job)
            logger.info("REASSIGN: job %s %s -> %s (%s)", job.id, prev_driver, contractor.id, reason)
        else:
            db.session.rollback()
        return result
    except Exception:
        logger.exception("reassign_job failed for job %s", job_id)
        try:
            db.session.rollback()
        except Exception:
            pass
        return _fail("error")


def mark_offer_declined(job, contractor, reason=None, minutes=None):
    """Persist a decline for (job, contractor) so re-dispatch skips them for a
    while. Reuses the live offer row if one exists, else writes one. No commit."""
    now = _now()
    until = now + timedelta(minutes=minutes if minutes is not None else DECLINE_EXCLUSION_MINUTES)
    offer = (JobOffer.query.filter_by(job_id=job.id, contractor_id=contractor.id)
             .order_by(JobOffer.created_at.desc()).first())
    if offer is None:
        offer = JobOffer(id=generate_uuid(), job_id=job.id, contractor_id=contractor.id,
                         accept_token=generate_uuid(), status="sent")
        db.session.add(offer)
    offer.status = "declined"
    offer.responded_at = offer.declined_at = now
    offer.exclude_until = until
    offer.decline_reason = (reason or None) and str(reason)[:200]
    return offer


# ---------------------------------------------------------------------------
# F17: versioned transitions
# ---------------------------------------------------------------------------
def _completion_gates(job, data, actor, is_admin):
    """Return (error_payload, http, meta) — error_payload None when the job may complete."""
    exception_reason = (data.get("exception_reason") or "").strip()
    meta = {}
    pin_raw = str(data.get("handoff_pin") or data.get("pin") or "").strip()
    pin_ok = bool(pin_raw) and verify_pin(job, pin_raw)
    if pin_raw and not pin_ok:
        return {"error": "That handoff PIN is not correct.", "code": "pin_invalid"}, 422, meta
    try:
        from flags import flag
        pin_required = bool(flag("completion_pin_required"))
    except Exception:
        pin_required = False
    if pin_required and not pin_ok and not exception_reason:
        return {"error": "The customer's handoff PIN is required to complete this job.",
                "code": "pin_required"}, 422, meta
    has_after = bool(data.get("after_photos") or job.after_photos)
    if not has_after and not pin_ok and not exception_reason:
        return {"error": "At least one after-photo (or the customer's handoff PIN) is required to complete "
                         "this job. Send exception_reason to complete without proof — it is recorded.",
                "code": "proof_required"}, 422, meta
    if getattr(job, "has_open_change_order", False) or getattr(job, "volume_adjustment_proposed", False):
        return {"error": "A price change is still waiting on the customer — resolve it before completing.",
                "code": "change_order_open"}, 409, meta
    pay = payment_status(job)
    if pay != "succeeded":
        if not (is_admin and exception_reason):
            return {"error": "Payment is not settled for this job (status: {}).".format(pay or "none"),
                    "code": "payment_not_settled", "payment_status": pay}, 409, meta
        meta["payment_exception"] = pay or "none"
    meta.update(pin_verified=pin_ok, after_photo=has_after)
    if exception_reason:
        meta["exception_reason"] = exception_reason
    return None, 200, meta


def transition_job(job, new_status, actor, data=None, contractor=None, expected_version=None):
    """Move ``job`` to ``new_status`` with a conditional UPDATE on (status,
    version). Returns (ok, payload, http). Commits + writes a job_events row on
    success; the caller runs side effects afterwards. Never raises.

    - only the assigned contractor's user may transition (admins may override;
      an override_reason is recorded)
    - 'started' needs arrived_at (or an audited exception_reason)
    - 'completed' needs proof (after-photo | handoff PIN | audited exception),
      no open change order, and a settled payment
    - 'cancelled' by a hauler is a RELEASE, not a cancellation: see release_job
    """
    data = data or {}
    a = normalize_actor(actor)
    is_admin = (a.get("role") or "") in ADMIN_ROLES
    try:
        if not is_admin:
            if contractor is None or job.driver_id != contractor.id:
                return False, {"error": "You are not assigned to this job", "code": "not_assigned"}, 403
        override_reason = (data.get("override_reason") or "").strip()
        if is_admin and (contractor is None or job.driver_id != contractor.id) and not override_reason:
            return False, {"error": "override_reason is required for an admin transition", "code": "override_reason_required"}, 400

        allowed = VALID_STATUS_TRANSITIONS.get(job.status, [])
        if new_status not in allowed:
            return False, {"error": "Cannot transition from {} to {}".format(job.status, new_status),
                           "allowed": allowed, "code": "invalid_transition"}, 409
        cur_version = int(job.version or 1)
        if expected_version is not None and int(expected_version) != cur_version:
            return False, {"error": "Stale job version — refresh and retry.", "code": "stale_version",
                           "version": cur_version, "status": job.status}, 409

        if new_status == "cancelled":
            ok, code = release_job(job, a, reason=(data.get("reason") or data.get("cancellation_reason") or "").strip(),
                                   source="driver_cancel", expected_version=expected_version)
            if not ok:
                return False, {"error": _MESSAGES.get(code, "Could not release this job."), "code": code}, 409
            return True, {"success": True, "job": job.to_dict(), "released": True, "code": "released"}, 200

        now = utcnow()
        meta = {}
        exception_reason = (data.get("exception_reason") or "").strip()
        values = {"status": new_status, "updated_at": now, "version": _version_expr() + 1}
        if data.get("before_photos"):
            values["before_photos"] = data["before_photos"]
        if data.get("after_photos"):
            values["after_photos"] = data["after_photos"]
        if new_status == "arrived":
            values["arrived_at"] = now
        elif new_status == "started":
            if not job.arrived_at and not exception_reason:
                return False, {"error": "Mark arrived before starting the job (or send exception_reason).",
                               "code": "arrival_required"}, 422
            if not job.arrived_at:
                meta["exception"] = "arrival_not_acknowledged"
                meta["exception_reason"] = exception_reason
            values["started_at"] = now
        elif new_status == "completed":
            err, http, meta = _completion_gates(job, data, a, is_admin)
            if err:
                return False, err, http
            values["completed_at"] = now
            if meta.get("pin_verified"):
                values["completion_pin_verified_at"] = now
            if meta.get("exception_reason"):
                values["completion_exception_reason"] = meta["exception_reason"]
        if override_reason:
            meta["override_reason"] = override_reason

        from_status = job.status
        res = db.session.execute(
            Job.__table__.update()
            .where(and_(Job.id == job.id, Job.status == from_status, _version_expr() == cur_version))
            .values(**values))
        if res.rowcount != 1:
            db.session.rollback()
            db.session.refresh(job)
            return False, {"error": "The job changed underneath you — refresh and retry.", "code": "conflict",
                           "status": job.status, "version": job.version}, 409
        if new_status == "completed":
            release_reservation(job.id)
        record_event(job.id, from_status, new_status, a, reason=exception_reason or override_reason or None,
                     meta=dict(meta, contractor_id=getattr(contractor, "id", None) or job.driver_id))
        db.session.commit()
        db.session.refresh(job)
        return True, {"success": True, "job": job.to_dict(), "code": "ok"}, 200
    except Exception:
        logger.exception("transition_job failed for job %s -> %s", getattr(job, "id", "?"), new_status)
        try:
            db.session.rollback()
        except Exception:
            pass
        return False, {"error": "Something went wrong. Please try again.", "code": "error"}, 500


def job_events(job_id, limit=200):
    return (JobEvent.query.filter_by(job_id=job_id)
            .order_by(JobEvent.created_at.asc()).limit(limit).all())
