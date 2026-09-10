"""Purpose-scoped, expiring guest tracking tokens (audit F21).

A tracking link used to be ``/track/code/<CODE>`` — the confirmation code
(or job UUID) was a perpetual bearer capability that kept revealing the
hauler's live position long after the job. ``Job.tracking_url()`` now
appends ``?t=<token>`` where the token is an HMAC-SHA256 over
``"track:<job_id>:<exp>"`` keyed with the app secret. The public tracking
endpoints require it (or an authenticated participant) and separately stop
returning driver location once the job is closed or the scheduled window
plus 6 hours has passed.

Token wire format: ``<exp_unix>.<hex signature>``.
"""

import hashlib
import hmac
import os
import time
from datetime import datetime, timedelta, timezone

__all__ = [
    "make_tracking_token", "verify_tracking_token", "tracking_token_for_job",
    "location_window_open", "LOCATION_GRACE_HOURS", "TOKEN_TTL_DAYS",
]

_PURPOSE = "track"
LOCATION_GRACE_HOURS = 6      # driver location stops this long after scheduled time
TOKEN_TTL_DAYS = 14           # how long a tracking link opens the status page
_ACTIVE_LOCATION_STATUSES = {
    "accepted", "assigned", "en_route", "arrived", "in_progress", "started",
}


def _secret():
    key = os.environ.get("TRACKING_TOKEN_SECRET") or os.environ.get("SECRET_KEY")
    if not key:
        from app_config import Config
        key = Config.SECRET_KEY
    return key.encode("utf-8")


def _sign(job_id, exp):
    msg = "{}:{}:{}".format(_PURPOSE, job_id, int(exp)).encode("utf-8")
    return hmac.new(_secret(), msg, hashlib.sha256).hexdigest()


def make_tracking_token(job_id, exp):
    """Build a token for ``job_id`` valid until unix time ``exp``."""
    exp = int(exp)
    return "{}.{}".format(exp, _sign(job_id, exp))


def verify_tracking_token(job_id, token, now=None):
    """True iff ``token`` was minted for ``job_id`` and has not expired."""
    if not token or not job_id or not isinstance(token, str):
        return False
    exp_str, _, sig = token.partition(".")
    if not exp_str.isdigit() or not sig:
        return False
    exp = int(exp_str)
    now = int(now if now is not None else time.time())
    if exp < now:
        return False
    return hmac.compare_digest(_sign(job_id, exp), sig)


def _as_utc(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def tracking_token_for_job(job, now=None):
    """Token whose expiry covers the job's scheduled window plus TOKEN_TTL_DAYS.

    Links are texted before the job; the status page (photos, receipt) stays
    reachable for two weeks after the scheduled time. Live location is gated
    separately by ``location_window_open``.
    """
    now = _as_utc(now) or datetime.now(timezone.utc)
    anchor = _as_utc(getattr(job, "scheduled_at", None)) or now
    if anchor < now:
        anchor = now
    exp = anchor + timedelta(days=TOKEN_TTL_DAYS)
    return make_tracking_token(job.id, int(exp.timestamp()))


def location_window_open(job, now=None):
    """Whether a driver's live position may still be shown for ``job``.

    Closed once the job is completed/cancelled/no-show, when no hauler is
    assigned, when the status is not an active travel/work stage, or more
    than LOCATION_GRACE_HOURS past the scheduled time.
    """
    status = (getattr(job, "status", "") or "").lower()
    if status not in _ACTIVE_LOCATION_STATUSES:
        return False
    if not getattr(job, "driver_id", None):
        return False
    now = _as_utc(now) or datetime.now(timezone.utc)
    scheduled = _as_utc(getattr(job, "scheduled_at", None))
    if scheduled is not None and now > scheduled + timedelta(hours=LOCATION_GRACE_HOURS):
        return False
    return True
