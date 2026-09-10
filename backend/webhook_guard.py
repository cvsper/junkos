"""Fail-closed guard for the non-core provider webhooks (audit F23).

The four "non-core" webhooks — Twilio inbound SMS (``routes/sms_webhook.py``,
reused by ``desk_line.py``), the Vapi tool/webhook endpoints and the Meta Lead
Ads webhook (``routes/vapi.py``), and the portal Stripe billing webhook
(``billing_portal.py``) — used to accept unsigned input whenever their secret
was missing or the validator raised. This module centralises the policy:

* **production** (``app_config.is_production()``): a missing secret or a
  validator exception REJECTS the request (401/403). The gap is logged once
  per webhook so it lands in the incident path instead of authenticating
  strangers.
* **development / testing**: current permissive behaviour is preserved so
  local dev and the test suite keep working without provider secrets.

Also owns provider-id deduplication (``record_provider_event``) backed by
``models_webhooks.ProviderEvent``.

Health / readiness
------------------
``webhook_secrets_ready()`` returns ``{name: bool}`` for every guarded webhook
so ``/api/health`` (or a readiness probe) can report which provider secrets
are configured. In production every ``False`` means that webhook is currently
rejecting traffic. Names → env vars:

    twilio          TWILIO_AUTH_TOKEN            /api/sms/inbound + desk line
    vapi            VAPI_SERVER_SECRET           /api/vapi/tool, /api/vapi/webhook
    meta_leads      META_APP_SECRET              POST /api/vapi/meta-leads
    meta_verify     META_VERIFY_TOKEN            GET  /api/vapi/meta-leads (challenge)
    portal_stripe   STRIPE_WEBHOOK_SECRET_PORTAL /portal/v1/billing/webhook
    stripe          STRIPE_WEBHOOK_SECRET        /api/payments/webhook (core, informational)

Usage from a health route::

    from webhook_guard import webhook_secrets_ready
    ready = webhook_secrets_ready()            # {"twilio": True, ...}
    all_ok = all(ready.values())
"""
from __future__ import annotations

import logging
import os
import threading

from app_config import is_production
# Imported at module level so ``db.create_all()`` knows about the
# provider_events table (same role server.py's models_sameday import plays).
from models_webhooks import ProviderEvent  # noqa: F401

logger = logging.getLogger(__name__)

# name -> env var holding the secret
WEBHOOK_SECRET_ENV = {
    "twilio": "TWILIO_AUTH_TOKEN",
    "vapi": "VAPI_SERVER_SECRET",
    "meta_leads": "META_APP_SECRET",
    "meta_verify": "META_VERIFY_TOKEN",
    "portal_stripe": "STRIPE_WEBHOOK_SECRET_PORTAL",
    "stripe": "STRIPE_WEBHOOK_SECRET",
}

_warned = set()
_warned_lock = threading.Lock()


def _log_once(key, msg, *args):
    """Log ``msg`` at WARNING the first time ``key`` is seen (per process)."""
    with _warned_lock:
        if key in _warned:
            return
        _warned.add(key)
    logger.warning(msg, *args)


def reset_warnings():
    """Test helper: forget which gaps have already been logged."""
    with _warned_lock:
        _warned.clear()


def secret_for(name):
    """Return the configured secret for a guarded webhook ('' if unset)."""
    return os.environ.get(WEBHOOK_SECRET_ENV[name], "") or ""


def webhook_secrets_ready():
    """{webhook name: secret configured?} for every guarded webhook."""
    return {name: bool(os.environ.get(env, "")) for name, env in WEBHOOK_SECRET_ENV.items()}


def allow_when_secret_missing(name, detail=None):
    """Policy for a webhook whose secret is not configured.

    Returns True (accept, dev only) or False (reject). Logs the gap once
    either way so it's visible in both environments.
    """
    env_var = WEBHOOK_SECRET_ENV[name]
    if is_production():
        _log_once(
            ("missing", name),
            "%s is not set — %s webhook is REJECTING all requests (401) until it is "
            "configured on Render. %s",
            env_var, name, detail or "",
        )
        return False
    _log_once(
        ("missing-dev", name),
        "%s is not set — %s webhook accepted WITHOUT verification (development only). %s",
        env_var, name, detail or "",
    )
    return True


def allow_on_validator_error(name, exc=None):
    """Policy when the signature validator itself raised.

    Production: reject (an exception is not a valid signature). Development:
    allow, matching the historical fail-safe so a validator bug can't brick
    local testing.
    """
    if is_production():
        logger.exception("%s signature validation errored — rejecting request", name)
        return False
    logger.warning("%s signature validation errored — allowing (development only): %s",
                   name, exc)
    return True


def record_provider_event(provider, event_id, event_type=None, detail=None):
    """Persist a provider event id. Returns True if it is NEW, False if we have
    already accepted this (provider, event_id) — i.e. the caller should treat
    the request as a duplicate delivery and skip side effects.

    Inserts under a savepoint so a duplicate never poisons the caller's
    session. Never raises: on any unexpected DB error it returns True (process
    the event) and logs — losing dedup is safer than dropping a real webhook.
    """
    if not event_id:
        return True
    from sqlalchemy.exc import IntegrityError
    from models import db

    try:
        with db.session.begin_nested():
            db.session.add(ProviderEvent(
                provider=provider, event_id=str(event_id)[:128],
                event_type=(event_type or None), detail=(detail or None),
            ))
        db.session.commit()
        return True
    except IntegrityError:
        db.session.rollback()
        logger.info("duplicate %s event %s ignored", provider, event_id)
        return False
    except Exception:
        db.session.rollback()
        logger.exception("provider event record failed (%s %s); processing anyway",
                         provider, event_id)
        return True
