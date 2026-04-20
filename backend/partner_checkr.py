"""
Partner Acquisition Agent — Checkr API client (spec 07 §9 v1).

Thin wrapper around the Checkr REST API (https://api.checkr.com/v1).
API reference: https://docs.checkr.com/v1.0/reference

Functions:
    create_candidate(lead) -> {"id": "...", ...}
    invite_candidate(candidate_id, package="tasker_pro") -> {"id": "...", "invitation_url": "..."}
    handle_webhook(payload) -> action-taken summary; updates BackgroundCheck
                               rows on `report.completed` events and transitions
                               the lead to ONBOARDING when status=clear.

Compliance rails:
  * If CHECKR_API_KEY is not set, all API functions raise CheckrNotConfigured.
  * Webhook signatures verified via CHECKR_WEBHOOK_SECRET (HMAC-SHA256 of raw
    request body).
  * FCRA adverse-action timer: on `status=consider`, BackgroundCheck row gets
    `adverse_action_due_at = now + 5 business days`.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import json
import logging
import os
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

CHECKR_BASE_URL = os.environ.get("CHECKR_BASE_URL", "https://api.checkr.com/v1")
CHECKR_TIMEOUT_SEC = 15


class CheckrNotConfigured(RuntimeError):
    """Raised when CHECKR_API_KEY is missing."""


class CheckrAPIError(RuntimeError):
    """Raised on 4xx/5xx from Checkr."""


def _api_key() -> str:
    key = os.environ.get("CHECKR_API_KEY", "").strip()
    if not key:
        raise CheckrNotConfigured("CHECKR_API_KEY not set")
    return key


def _auth():
    # Checkr uses HTTP basic with the API key as the username and an empty
    # password. See https://docs.checkr.com/v1.0/reference#authentication
    return (_api_key(), "")


def create_candidate(lead) -> Dict:
    """Create a Checkr candidate from a DriverLead. Returns the Checkr JSON."""
    first, last = _split_name(getattr(lead, "name_guess", None))
    payload = {
        "first_name": first,
        "last_name": last,
        "email": getattr(lead, "email", None) or _synth_email(lead),
        "phone": getattr(lead, "phone_e164", None),
        "zipcode": _lead_zip(lead),
        "dob": None,  # captured later via secure-link flow
        "ssn": None,  # only last-4 ever stored; full SSN collected by Checkr
        "no_middle_name": True,
    }
    # Drop None values — Checkr 422s on nulls.
    payload = {k: v for k, v in payload.items() if v is not None}

    resp = requests.post(
        "{}/candidates".format(CHECKR_BASE_URL),
        auth=_auth(),
        json=payload,
        timeout=CHECKR_TIMEOUT_SEC,
    )
    if resp.status_code >= 400:
        raise CheckrAPIError("checkr candidate create failed: {} {}".format(
            resp.status_code, resp.text[:500]))
    return resp.json()


def invite_candidate(candidate_id: str, package: str = "tasker_pro") -> Dict:
    """Send a Checkr invitation; returns the invitation object (includes URL)."""
    resp = requests.post(
        "{}/invitations".format(CHECKR_BASE_URL),
        auth=_auth(),
        json={"candidate_id": candidate_id, "package": package},
        timeout=CHECKR_TIMEOUT_SEC,
    )
    if resp.status_code >= 400:
        raise CheckrAPIError("checkr invitation failed: {} {}".format(
            resp.status_code, resp.text[:500]))
    return resp.json()


def verify_webhook(raw_body: bytes, signature: str) -> bool:
    """HMAC-SHA256 with CHECKR_WEBHOOK_SECRET. Timing-safe compare.

    Returns False (not raise) if the secret is missing — caller should 401.
    """
    secret = os.environ.get("CHECKR_WEBHOOK_SECRET", "").strip()
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip())


def handle_webhook(payload: Dict) -> Dict:
    """Process a parsed Checkr webhook payload. Returns an action summary.

    Recognised event types:
      * report.created — creates/updates BackgroundCheck with status='pending'
      * report.completed — terminal event; writes final status and, if clear,
        transitions the lead to ONBOARDING.
    """
    from models import db
    from partner_models import (
        BackgroundCheck,
        DriverLead,
        DriverOnboardingAudit,
    )

    event_type = payload.get("type") or payload.get("event") or ""
    data = payload.get("data") or {}
    obj = data.get("object") or data  # some Checkr webhooks embed object in data
    candidate_id = obj.get("candidate_id") or data.get("candidate_id")
    report_id = obj.get("id") if event_type.startswith("report.") else obj.get("report_id")
    status = (obj.get("status") or "pending").lower()

    # Locate the lead via the candidate_id we stashed during invite.
    bg = (
        db.session.query(BackgroundCheck)
        .filter_by(checkr_candidate_id=candidate_id)
        .order_by(BackgroundCheck.created_at.desc())
        .first()
    )
    created_new = False
    if not bg:
        # No pre-existing row — e.g. webhook arrived before our local insert.
        lead = (
            db.session.query(DriverLead)
            .filter(DriverLead.id == obj.get("lead_id", ""))
            .first()
        )
        if not lead:
            logger.warning(
                "checkr webhook: no matching candidate %s and no lead_id, skipping",
                candidate_id,
            )
            return {"matched": False, "event": event_type}
        bg = BackgroundCheck(
            lead_id=lead.id,
            checkr_candidate_id=candidate_id,
            checkr_report_id=report_id,
            status="pending",
        )
        db.session.add(bg)
        created_new = True

    if report_id:
        bg.checkr_report_id = report_id
    if status in ("pending", "clear", "consider", "suspended"):
        bg.status = status
    bg.raw_webhook_json = payload

    lead = db.session.get(DriverLead, bg.lead_id)
    transitioned = False
    if event_type == "report.completed" and lead:
        before = lead.state
        if status == "clear" and lead.state in ("QUALIFIED", "HUMAN_REVIEW"):
            lead.state = "ONBOARDING"
            transitioned = True
            db.session.add(DriverOnboardingAudit(
                lead_id=lead.id,
                actor="checkr_webhook",
                action="bg_check.clear",
                before_state=before,
                after_state=lead.state,
                payload_json={"report_id": report_id},
            ))
        elif status == "consider":
            bg.adverse_action_due_at = _add_business_days(_dt.datetime.utcnow(), 5)
            db.session.add(DriverOnboardingAudit(
                lead_id=lead.id,
                actor="checkr_webhook",
                action="bg_check.consider",
                before_state=before,
                after_state=lead.state,
                payload_json={"report_id": report_id, "adverse_action_due_at": bg.adverse_action_due_at.isoformat()},
            ))
        elif status == "suspended":
            lead.state = "REJECTED"
            transitioned = True
            db.session.add(DriverOnboardingAudit(
                lead_id=lead.id,
                actor="checkr_webhook",
                action="bg_check.suspended",
                before_state=before,
                after_state=lead.state,
                payload_json={"report_id": report_id},
            ))

    db.session.commit()
    return {
        "matched": True,
        "event": event_type,
        "status": status,
        "bg_check_id": bg.id,
        "lead_id": bg.lead_id,
        "transitioned": transitioned,
        "created": created_new,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _split_name(name: Optional[str]):
    if not name:
        return "Driver", "Prospect"
    parts = [p for p in name.strip().split() if p]
    if len(parts) == 1:
        return parts[0], "Prospect"
    return parts[0], parts[-1]


def _synth_email(lead) -> str:
    # Checkr requires an email; if we don't have one yet, synthesise a
    # placeholder using the phone digits. The ops team replaces this after
    # the secure-link qualifier.
    phone = getattr(lead, "phone_e164", None) or ""
    digits = "".join(c for c in phone if c.isdigit()) or "unknown"
    return "lead-{}@placeholder.umuve.com".format(digits[-10:] if len(digits) >= 10 else digits)


def _lead_zip(lead) -> Optional[str]:
    raw = getattr(lead, "raw_listing_json", None) or {}
    if isinstance(raw, dict):
        z = raw.get("zip") or raw.get("zipcode")
        if z:
            return str(z)
    # Fallback to metro default (spec targets FL metros).
    metro = (getattr(lead, "metro", None) or "miami").lower()
    return {
        "miami": "33101",
        "ftl": "33301",
        "wpb": "33401",
        "tpa": "33601",
    }.get(metro, "33101")


def _add_business_days(start: _dt.datetime, n: int) -> _dt.datetime:
    d = start
    added = 0
    while added < n:
        d += _dt.timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return d
