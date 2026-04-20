"""
Ops Supervisor — PagerDuty escalation (spec 11 §9, v1).

Wraps the PagerDuty Events API v2 (``/v2/enqueue``). The module exposes two
functions: ``trigger_incident`` and ``resolve_incident``. Both are safe to
call without network access — if ``PAGERDUTY_ROUTING_KEY`` is unset we log a
warning and return a sentinel identifier so the caller's control flow does
not have to branch on env presence.

Severity mapping:
    p0 -> critical
    p1 -> error
    p2 -> warning

The PagerDuty incident ID (dedup_key) is written back onto the
``EscalationTicket`` row. We use ``ticket.id`` as the dedup_key so the same
ticket never spawns two incidents (PagerDuty dedups on that key).
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Optional

logger = logging.getLogger(__name__)


PAGERDUTY_ENQUEUE_URL = "https://events.pagerduty.com/v2/enqueue"

SEVERITY_MAP = {
    "p0": "critical",
    "p1": "error",
    "p2": "warning",
}


def _routing_key() -> str:
    return os.environ.get("PAGERDUTY_ROUTING_KEY", "") or ""


def _sentinel_id() -> str:
    """Return a sentinel identifier when no routing key is configured.

    The caller still records this value so the audit trail shows we tried
    to page and why we did not.
    """
    return "pd_missing_key_{}".format(uuid.uuid4().hex[:12])


def _post_event(payload: dict, *, http_client=None, timeout: float = 5.0) -> Optional[dict]:
    """POST to PagerDuty. Returns parsed JSON body or None on failure."""
    try:
        if http_client is None:
            import httpx  # noqa: WPS433 - lazy import
            resp = httpx.post(PAGERDUTY_ENQUEUE_URL, json=payload, timeout=timeout)
        else:
            resp = http_client.post(PAGERDUTY_ENQUEUE_URL, json=payload, timeout=timeout)
        if resp.status_code >= 400:
            logger.error(
                "pagerduty: non-2xx response %s body=%s",
                resp.status_code, getattr(resp, "text", "")[:400],
            )
            return None
        try:
            return resp.json()
        except Exception:
            logger.warning("pagerduty: non-JSON response body=%s",
                           getattr(resp, "text", "")[:200])
            return {"ok": True}
    except Exception:
        logger.exception("pagerduty: POST failed")
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def trigger_incident(ticket, *, http_client=None, persist: bool = True) -> str:
    """Trigger a PagerDuty incident for the given EscalationTicket.

    Returns the PagerDuty dedup_key (ticket.id on success) or a sentinel
    string if the routing key is not configured. Also writes
    ``pagerduty_incident`` onto the ticket row when ``persist=True``.
    """
    routing_key = _routing_key()
    if not routing_key:
        logger.warning("pagerduty: PAGERDUTY_ROUTING_KEY missing; ticket %s not paged",
                       getattr(ticket, "id", "?"))
        incident_id = _sentinel_id()
        if persist:
            _persist_incident_id(ticket, incident_id)
        return incident_id

    severity = SEVERITY_MAP.get((ticket.priority or "p2").lower(), "warning")
    summary = (ticket.summary_md or
               "Umuve ops situation {}".format(ticket.situation_id))[:1024]

    payload = {
        "routing_key": routing_key,
        "event_action": "trigger",
        "dedup_key": ticket.id,
        "payload": {
            "summary": summary,
            "source": "umuve-ops-supervisor",
            "severity": severity,
            "component": "ops-supervisor-agent",
            "custom_details": {
                "ticket_id": ticket.id,
                "situation_id": ticket.situation_id,
                "priority": ticket.priority,
                "assignee": ticket.assignee,
            },
        },
    }

    body = _post_event(payload, http_client=http_client)
    if body is None:
        incident_id = _sentinel_id()
    else:
        # PagerDuty returns {"status":"success","dedup_key":"..."}. We prefer
        # the server-assigned dedup_key if present, else use our own.
        incident_id = (body.get("dedup_key") or ticket.id)

    if persist:
        _persist_incident_id(ticket, incident_id)
    return incident_id


def resolve_incident(ticket, *, http_client=None) -> bool:
    """Fire a PagerDuty 'resolve' event for the ticket. Returns True on
    success, False if routing key missing or request failed.
    """
    routing_key = _routing_key()
    dedup_key = getattr(ticket, "pagerduty_incident", None) or ticket.id
    if not routing_key:
        logger.warning("pagerduty: PAGERDUTY_ROUTING_KEY missing; resolve skipped "
                       "for ticket %s", ticket.id)
        return False

    payload = {
        "routing_key": routing_key,
        "event_action": "resolve",
        "dedup_key": dedup_key,
    }
    body = _post_event(payload, http_client=http_client)
    return body is not None


# ---------------------------------------------------------------------------
# Persistence helper
# ---------------------------------------------------------------------------
def _persist_incident_id(ticket, incident_id: str) -> None:
    try:
        ticket.pagerduty_incident = incident_id
        from models import db
        if ticket in db.session:
            db.session.flush()
    except Exception:  # pragma: no cover
        logger.exception("pagerduty: failed to persist pagerduty_incident on ticket")


__all__ = [
    "trigger_incident",
    "resolve_incident",
    "SEVERITY_MAP",
    "PAGERDUTY_ENQUEUE_URL",
]
