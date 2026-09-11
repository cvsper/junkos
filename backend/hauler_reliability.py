"""Who actually shows up.

Twenty-one haulers read "online". Fifty-two got a standby text and none
replied. The one who was handed a real job had zero completed jobs and never
turned up, and the customer waited nineteen days. The pool is unproven, and
the dispatcher was treating "approved" as "reliable".

This module answers one question per hauler from evidence the system already
holds: offered, accepted, completed, no-showed. From that, a tier:

  proven   at least one completed job and no no-shows
  new      zero completed jobs — not distrusted, just unproven
  flagged  no-showed with nothing completed, or no-showed twice

The tier is advisory everywhere except silent auto-assignment, where a "new"
hauler is not handed a job without a person confirming first. Offer waves and
manual assignment still reach them (with a warning) — otherwise, with an
all-new pool, nobody would get any work.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from models import db, Job, JobOffer, Contractor

logger = logging.getLogger(__name__)

TIER_PROVEN = "proven"
TIER_NEW = "new"
TIER_FLAGGED = "flagged"

COMPLETED_STATUSES = ("completed", "paid", "closed")


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def stats(contractor_id, days=180):
    """Counts for one hauler over the window. Never raises."""
    since = _now() - timedelta(days=days)
    out = {"offered": 0, "accepted": 0, "completed": 0, "no_shows": 0, "last_completed_at": None}
    if not contractor_id:
        return out
    try:
        offers = JobOffer.query.filter(JobOffer.contractor_id == contractor_id,
                                       JobOffer.created_at >= since).all()
        out["offered"] = len(offers)
        out["accepted"] = sum(1 for o in offers if (o.status or "") == "accepted")
    except Exception:
        logger.exception("offer stats failed for %s", contractor_id)
    try:
        done = (Job.query.filter(Job.driver_id == contractor_id,
                                 Job.status.in_(COMPLETED_STATUSES))
                .order_by(Job.completed_at.desc().nullslast()).all())
        out["completed"] = len(done)
        if done and done[0].completed_at:
            out["last_completed_at"] = done[0].completed_at.isoformat() + "Z"
    except Exception:
        logger.exception("completed stats failed for %s", contractor_id)
    try:
        out["no_shows"] = Job.query.filter(Job.noshow_contractor_id == contractor_id).count()
    except Exception:
        logger.exception("no-show stats failed for %s", contractor_id)
    return out


def tier(contractor_id, s=None):
    s = s or stats(contractor_id)
    if s["no_shows"] >= 2 or (s["no_shows"] >= 1 and s["completed"] == 0):
        return TIER_FLAGGED
    if s["completed"] == 0:
        return TIER_NEW
    return TIER_PROVEN


def profile(contractor):
    """Tier + counts, safe for the desk. Never raises."""
    cid = getattr(contractor, "id", contractor)
    s = stats(cid)
    t = tier(cid, s)
    return {
        "tier": t,
        "label": {"proven": "Proven", "new": "First job", "flagged": "No-show history"}[t],
        "offered": s["offered"], "accepted": s["accepted"],
        "completed": s["completed"], "no_shows": s["no_shows"],
        "last_completed_at": s["last_completed_at"],
    }


def record_no_show(job, contractor_id, reason="unconfirmed_at_t30"):
    """Stamp a no-show on the job so it counts against the hauler. Does not commit."""
    job.noshow_contractor_id = contractor_id
    job.noshow_reason = (reason or "")[:80]
    job.noshow_redispatched_at = _now()


def roster(limit=100):
    """Every approved hauler with their tier — for the dispatch board."""
    rows = []
    for c in Contractor.query.filter(Contractor.approval_status == "approved").limit(limit).all():
        p = profile(c)
        user = getattr(c, "user", None)
        rows.append(dict(p, contractor_id=c.id,
                         name=(getattr(c, "business_name", None) or (user.name if user else None) or "Hauler"),
                         phone=(user.phone if user else None),
                         concierge=bool(getattr(c, "is_concierge", False))))
    order = {TIER_PROVEN: 0, TIER_NEW: 1, TIER_FLAGGED: 2}
    rows.sort(key=lambda r: (order[r["tier"]], -r["completed"], r["name"]))
    return rows
