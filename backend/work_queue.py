"""One list of what needs a human right now.

Every operational failure this desk has had was the same shape: something was
detected and then nobody owned it. A $307 job sat in "assigned" for eighteen
days. A hauler finished work and went unpaid. A call rang and was never
returned. Fifty-two haulers were asked for standby and none were chased. The
detectors all worked. There was simply no place where "this needs a person"
became "this is mine".

So the queue derives its items from the systems that already know, and adds
the only thing they cannot: ownership. Sources, in the order they cost money:

  unassigned_paid  Customer paid, nobody is coming. The worst state we have.
  stranded_job     An open job with no movement — the AFB22IMO case.
  hauler_owed      Work finished, payout parked. People quit over this.
  missed_call      Rang, no human, no callback. Straight lost revenue.
  callback_due     A promise with a time on it, now due.

Nothing here writes to the source systems. Marking an item done records that a
human dealt with it; it does not pretend the underlying job changed. When the
source recovers on its own, the item simply stops being generated.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from models import db
from models_work import WorkItemState
from desk_auth import desk_identity, desk_va_name, audit

try:
    from extensions import limiter
except Exception:  # pragma: no cover
    limiter = None

logger = logging.getLogger(__name__)
work_bp = Blueprint("work_queue", __name__)
_ratelimit = (limiter.limit("240 per hour; 60 per minute") if limiter is not None else (lambda f: f))

# How long a claim holds before the item returns to the pool. A VA who claims
# something and goes to lunch must not hide it forever.
CLAIM_HOURS = 4
# Anything older than this is abandoned or seed data, not work waiting on a
# person. Matches the stranded-job census so the two agree.
RECENT_DAYS = 60
MAX_SNOOZE_MINUTES = 60 * 24

KINDS = ("unassigned_paid", "stranded_job", "hauler_owed", "missed_call", "callback_due")

# Base weight per kind; age adds to it so nothing rots quietly at the bottom.
_WEIGHT = {
    "unassigned_paid": 1000,
    "stranded_job": 700,
    "hauler_owed": 600,
    "missed_call": 500,
    "callback_due": 400,
}


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _aware(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def _hours_since(dt):
    dt = _aware(dt)
    if not dt:
        return 0.0
    return max(0.0, (_now() - dt).total_seconds() / 3600.0)


def _pretty_phone(digits):
    d = "".join(ch for ch in (digits or "") if ch.isdigit())[-10:]
    return "({}) {}-{}".format(d[:3], d[3:6], d[6:]) if len(d) == 10 else (digits or "")


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------
def _unassigned_paid():
    """Customer paid and no hauler is assigned. Nobody is coming."""
    from models import Job, Payment

    out = []
    # Bounded on BOTH sides. Without a floor the first live run put a February
    # seed row ("fvsdfvsdfvsdfvsdfv", $89) at the top of the queue — and a
    # queue whose worst item is junk is a queue people learn to ignore.
    floor = _now() - timedelta(days=RECENT_DAYS)
    rows = (db.session.query(Job, Payment).join(Payment, Payment.job_id == Job.id)
            .filter(Job.driver_id.is_(None),
                    Job.status.in_(("confirmed", "pending")),
                    Payment.payment_status == "succeeded")
            .all())
    for job, payment in rows:
        anchor = _aware(job.scheduled_at) or _aware(job.created_at)
        if anchor and anchor > _now() + timedelta(days=14):
            continue                                    # far future, not urgent yet
        if anchor and anchor < floor:
            continue                                    # abandoned or seed data
        if (job.notes or "").upper().startswith("SYNTHETIC"):
            continue
        out.append({
            "kind": "unassigned_paid",
            "ref_id": job.id,
            "title": "Paid job with no hauler",
            "detail": "{} · ${:.2f} · {}".format(
                job.confirmation_code or job.id[:8], job.total_price or 0.0,
                (job.address or "").split(",")[0][:40]),
            "why": "The customer has paid and nobody is assigned.",
            "age_hours": round(_hours_since(anchor), 1),
            "link": "/api/jobs/lookup/" + job.id,
        })
    return out


def _stranded_jobs():
    """Open jobs with no forward movement (ops_sentinel keeps the definition)."""
    from ops_sentinel import stranded_summary

    rep = stranded_summary()
    out = []
    for row in rep.get("recent", []):
        out.append({
            "kind": "stranded_job",
            "ref_id": row["code"],
            "title": "Job stuck in {}".format(row["status"]),
            "detail": "{} · {} days with no movement{}".format(
                row["code"], row["age_days"], " · hauler assigned" if row.get("has_driver") else ""),
            "why": ("A hauler is assigned but nothing has happened — the customer is waiting "
                    "or the hauler finished and never marked it."
                    if row.get("has_driver") else
                    "Nobody has picked this up and the date is passing."),
            "age_hours": round(row["age_days"] * 24, 1),
            "link": "/api/jobs/lookup/" + row["code"],
        })
    return out


def _haulers_owed():
    """Completed work whose payout is parked or failed."""
    from sameday_pay import owed_rows

    rep = owed_rows(days=30)
    out = []
    for row in rep.get("rows", []):
        out.append({
            "kind": "hauler_owed",
            "ref_id": row["payment_id"],
            "title": "Hauler owed ${:.2f}".format(row["amount"]),
            "detail": "{} · {} · {}".format(row["hauler"], row["job_code"],
                                            "no Stripe — pay by Zelle" if not row["has_stripe"]
                                            else "transfer failed"),
            "why": "The work is done and the money has not reached them.",
            "age_hours": round(_hours_since(
                datetime.fromisoformat(row["completed_at"].replace("Z", ""))
                if row.get("completed_at") else None), 1),
            "link": "/va/manager",
        })
    return out


def _missed_calls():
    """Rang, no human took it, and no callback was logged for that number."""
    try:
        from models_inbound import InboundCall, CallbackRequest
    except Exception:
        return []

    since = _now() - timedelta(days=3)
    rows = (InboundCall.query
            .filter(InboundCall.created_at >= since,
                    InboundCall.disposition.in_(("ringing", "no_answer", "missed", "voicemail")),
                    InboundCall.answered_by.is_(None))
            .order_by(InboundCall.created_at.desc()).limit(50).all())
    if not rows:
        return []
    # a callback already promised for that number closes it
    digits = {r.phone_digits for r in rows}
    promised = {c.phone_digits for c in
                CallbackRequest.query.filter(CallbackRequest.phone_digits.in_(digits),
                                             CallbackRequest.status == "open").all()}
    out = []
    for row in rows:
        if row.phone_digits in promised:
            continue
        out.append({
            "kind": "missed_call",
            "ref_id": row.call_sid or row.id,
            "title": "Missed call, never returned",
            "detail": "{} · {}".format(_pretty_phone(row.phone_digits), row.kind),
            "why": "Somebody called and nobody called back.",
            "age_hours": round(_hours_since(row.created_at), 1),
            "phone": _pretty_phone(row.phone_digits),
            "link": None,
        })
    return out


def _callbacks_due():
    """Promises with a time on them, now due."""
    try:
        from models_inbound import CallbackRequest
    except Exception:
        return []

    rows = (CallbackRequest.query
            .filter(CallbackRequest.status == "open")
            .order_by(CallbackRequest.created_at.asc()).limit(50).all())
    out = []
    for row in rows:
        due = _aware(row.requested_for)
        if due and due > _now():
            continue                                    # not yet
        out.append({
            "kind": "callback_due",
            "ref_id": row.id,
            "title": "Callback due",
            "detail": "{}{}".format(_pretty_phone(row.phone_digits),
                                    " · " + row.name if row.name else ""),
            "why": row.note or "We promised to call back.",
            "age_hours": round(_hours_since(due or row.created_at), 1),
            "phone": _pretty_phone(row.phone_digits),
            "link": None,
        })
    return out


# Held by NAME, not by reference: a tuple of functions binds whatever existed
# at import, which makes the set impossible to substitute and reports the
# original name even when a source has been replaced.
_SOURCES = ("_unassigned_paid", "_stranded_jobs", "_haulers_owed",
            "_missed_calls", "_callbacks_due")


def collect():
    """Every derived item. A broken source must not empty the whole queue."""
    items, broken = [], []
    for name in _SOURCES:
        source = globals().get(name)
        if source is None:
            continue
        try:
            items.extend(source())
        except Exception:
            logger.exception("work queue source %s failed", name)
            broken.append(name.lstrip("_"))
    return items, broken


def urgency(item):
    """Base weight for the kind, plus age so nothing rots quietly."""
    return round(_WEIGHT.get(item["kind"], 100) + min(item.get("age_hours", 0) * 2, 400), 1)


def _state_map(items):
    if not items:
        return {}
    kinds = {i["kind"] for i in items}
    refs = {i["ref_id"] for i in items}
    rows = WorkItemState.query.filter(WorkItemState.kind.in_(kinds),
                                      WorkItemState.ref_id.in_(refs)).all()
    return {(r.kind, r.ref_id): r for r in rows}


def build(include_done=False, va_name=None):
    """The queue: derived items, their ownership, sorted by what hurts most."""
    items, broken = collect()
    states = _state_map(items)
    now = _now()
    out, hidden = [], 0
    for item in items:
        state = states.get((item["kind"], item["ref_id"]))
        if state and state.done_at and not include_done:
            hidden += 1
            continue
        if state and state.snoozed_until and _aware(state.snoozed_until) > now and not include_done:
            hidden += 1
            continue
        claimed_by, claim_stale = None, False
        if state and state.claimed_by and not state.done_at:
            if _hours_since(state.claimed_at) < CLAIM_HOURS:
                claimed_by = state.claimed_by
            else:
                claim_stale = True          # held too long — back in the pool
        row = dict(item)
        row["urgency"] = urgency(item)
        row["claimed_by"] = claimed_by
        row["claim_stale"] = claim_stale
        row["mine"] = bool(claimed_by and va_name and claimed_by == va_name)
        row["note"] = state.note if state else None
        out.append(row)
    out.sort(key=lambda r: (-r["urgency"], -r.get("age_hours", 0)))
    counts = {k: sum(1 for r in out if r["kind"] == k) for k in KINDS}
    return {
        "items": out,
        "total": len(out),
        "unclaimed": sum(1 for r in out if not r["claimed_by"]),
        "mine": sum(1 for r in out if r["mine"]),
        "counts": counts,
        "hidden": hidden,
        "sources_failed": broken,
        "claim_hours": CLAIM_HOURS,
    }


def _get_or_create(kind, ref_id):
    if kind not in KINDS:
        return None
    row = WorkItemState.query.filter_by(kind=kind, ref_id=ref_id).first()
    if row is None:
        row = WorkItemState(kind=kind, ref_id=ref_id)
        db.session.add(row)
        try:
            db.session.commit()
        except Exception:                    # concurrent claim — reuse theirs
            db.session.rollback()
            row = WorkItemState.query.filter_by(kind=kind, ref_id=ref_id).first()
    return row


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
def _who(data):
    ident = desk_identity(data)
    if not ident:
        return None, None
    return ident, (desk_va_name(data) or (ident.get("name") if ident else None) or "someone")


@work_bp.route("/api/va/work/list", methods=["POST"])
@_ratelimit
def work_list():
    data = request.get_json(silent=True) or {}
    ident, va = _who(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    return jsonify(build(include_done=bool(data.get("include_done")), va_name=va)), 200


@work_bp.route("/api/va/work/claim", methods=["POST"])
@_ratelimit
def work_claim():
    data = request.get_json(silent=True) or {}
    ident, va = _who(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    row = _get_or_create((data.get("kind") or "").strip(), (data.get("ref_id") or "").strip())
    if row is None:
        return jsonify({"error": "Unknown item."}), 400
    if row.claimed_by and row.claimed_by != va and _hours_since(row.claimed_at) < CLAIM_HOURS:
        return jsonify({"error": "{} is already on this one.".format(row.claimed_by),
                        "claimed_by": row.claimed_by}), 409
    row.claimed_by = va
    row.claimed_at = _now()
    row.done_at = None
    db.session.commit()
    audit("work_claim", row.kind, row.ref_id, {"by": va})
    return jsonify({"ok": True, "queue": build(va_name=va)}), 200


@work_bp.route("/api/va/work/release", methods=["POST"])
@_ratelimit
def work_release():
    data = request.get_json(silent=True) or {}
    ident, va = _who(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    row = WorkItemState.query.filter_by(kind=(data.get("kind") or ""),
                                        ref_id=(data.get("ref_id") or "")).first()
    if row:
        row.claimed_by = None
        row.claimed_at = None
        db.session.commit()
    return jsonify({"ok": True, "queue": build(va_name=va)}), 200


@work_bp.route("/api/va/work/done", methods=["POST"])
@_ratelimit
def work_done():
    data = request.get_json(silent=True) or {}
    ident, va = _who(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    row = _get_or_create((data.get("kind") or "").strip(), (data.get("ref_id") or "").strip())
    if row is None:
        return jsonify({"error": "Unknown item."}), 400
    note = (data.get("note") or "").strip()[:500]
    if not note:
        # "Done" with no word about what happened is how things get lost twice.
        return jsonify({"error": "Say what you did, so the next person knows."}), 400
    row.done_at = _now()
    row.done_by = va
    row.note = note
    db.session.commit()
    audit("work_done", row.kind, row.ref_id, {"by": va, "note": note})
    return jsonify({"ok": True, "queue": build(va_name=va)}), 200


@work_bp.route("/api/va/work/snooze", methods=["POST"])
@_ratelimit
def work_snooze():
    data = request.get_json(silent=True) or {}
    ident, va = _who(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    row = _get_or_create((data.get("kind") or "").strip(), (data.get("ref_id") or "").strip())
    if row is None:
        return jsonify({"error": "Unknown item."}), 400
    try:
        minutes = int(data.get("minutes") or 60)
    except (TypeError, ValueError):
        minutes = 60
    minutes = max(5, min(minutes, MAX_SNOOZE_MINUTES))
    row.snoozed_until = _now() + timedelta(minutes=minutes)
    db.session.commit()
    audit("work_snooze", row.kind, row.ref_id, {"by": va, "minutes": minutes})
    return jsonify({"ok": True, "minutes": minutes, "queue": build(va_name=va)}), 200
