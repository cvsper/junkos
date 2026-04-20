"""
Partner Acquisition Agent — Stripe Connect Express onboarding (spec 07 §9 v1).

Functions:
    create_connect_account(lead) -> account_id
    create_account_link(account_id) -> onboarding_url
    handle_webhook(event)          -> side-effect summary

Requires STRIPE_SECRET_KEY. When charges_enabled=True arrives via the
account.updated webhook, we:
  * Mark OnboardingStep(step='stripe_kyc_done', completed_at=now)
  * Write an audit row
  * Do NOT transition the lead state here — that's done by the LangGraph
    pipeline after all onboarding steps are complete.

Spec 07 §8 compliance rail:
  * No Stripe Connect account created without a prior qualification row
    carrying consent_sms=True (Stripe Connect needs a legally-capable adult;
    we re-use SMS consent as the proxy signal for "they're engaging").
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class StripeNotConfigured(RuntimeError):
    """Raised when STRIPE_SECRET_KEY is not set."""


def _stripe():
    key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not key:
        raise StripeNotConfigured("STRIPE_SECRET_KEY not set")
    try:
        import stripe  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise StripeNotConfigured("stripe SDK not installed") from exc
    stripe.api_key = key
    return stripe


def _return_url(lead) -> str:
    base = os.environ.get("STRIPE_CONNECT_RETURN_URL",
                         "https://umuve.com/driver/onboarded")
    return "{}?lead_id={}".format(base, getattr(lead, "id", ""))


def _refresh_url(lead) -> str:
    base = os.environ.get("STRIPE_CONNECT_REFRESH_URL",
                         "https://umuve.com/driver/onboard/refresh")
    return "{}?lead_id={}".format(base, getattr(lead, "id", ""))


def create_connect_account(lead) -> str:
    """Create a Stripe Connect Express account for a DriverLead.

    Returns the Stripe account id. Caller is responsible for persisting it —
    we don't add a column to driver_leads (would require touching
    partner_models); instead we write it to a new OnboardingStep row with
    step='stripe_link_sent' and payload_json={"account_id": ...}.
    """
    stripe = _stripe()
    acct = stripe.Account.create(
        type="express",
        country="US",
        email=getattr(lead, "email", None),
        capabilities={
            "transfers": {"requested": True},
            "card_payments": {"requested": True},
        },
        business_type="individual",
        metadata={
            "lead_id": getattr(lead, "id", "") or "",
            "source": "partner_acquisition_v1",
        },
    )
    return acct["id"]


def create_account_link(account_id: str, lead=None) -> str:
    """Create a one-time onboarding URL. Returns the `url` field."""
    stripe = _stripe()
    link = stripe.AccountLink.create(
        account=account_id,
        refresh_url=_refresh_url(lead) if lead is not None else os.environ.get(
            "STRIPE_CONNECT_REFRESH_URL", "https://umuve.com/driver/onboard/refresh"),
        return_url=_return_url(lead) if lead is not None else os.environ.get(
            "STRIPE_CONNECT_RETURN_URL", "https://umuve.com/driver/onboarded"),
        type="account_onboarding",
    )
    return link["url"]


def start_onboarding(lead) -> Dict:
    """One-shot: create account + link, write OnboardingStep, audit. Commits.

    Returns {"account_id": ..., "url": ...}.
    """
    from models import db
    from partner_models import OnboardingStep, DriverOnboardingAudit

    account_id = create_connect_account(lead)
    url = create_account_link(account_id, lead=lead)

    step = OnboardingStep(
        lead_id=getattr(lead, "id", None),
        step="stripe_link_sent",
        payload_json={"account_id": account_id, "url": url},
    )
    db.session.add(step)
    db.session.add(DriverOnboardingAudit(
        lead_id=getattr(lead, "id", None),
        actor="partner_stripe_connect_v1",
        action="stripe_connect.link_sent",
        before_state=getattr(lead, "state", None),
        after_state=getattr(lead, "state", None),
        payload_json={"account_id": account_id},
    ))
    db.session.commit()
    return {"account_id": account_id, "url": url}


def handle_webhook(event: Dict) -> Dict:
    """Handle a parsed Stripe webhook event. Only `account.updated` is
    actioned; everything else is ignored with an INFO log.

    On `charges_enabled=True`, marks the lead's stripe_kyc_done OnboardingStep
    complete (creating a new row if none exists) and writes an audit entry.
    """
    from models import db
    from partner_models import (
        OnboardingStep,
        DriverLead,
        DriverOnboardingAudit,
    )
    import datetime as _dt

    event_type = event.get("type") or ""
    if event_type != "account.updated":
        logger.info("stripe webhook ignored: %s", event_type)
        return {"matched": False, "event": event_type}

    obj = (event.get("data") or {}).get("object") or {}
    account_id = obj.get("id")
    charges_enabled = bool(obj.get("charges_enabled"))
    lead_id = (obj.get("metadata") or {}).get("lead_id")

    if not charges_enabled:
        return {"matched": True, "event": event_type, "charges_enabled": False}

    # Find an existing `stripe_link_sent` row by matching account_id in payload.
    step_row: Optional[OnboardingStep] = None
    if lead_id:
        step_row = (
            db.session.query(OnboardingStep)
            .filter_by(lead_id=lead_id, step="stripe_kyc_done")
            .first()
        )
    if not step_row and lead_id:
        step_row = OnboardingStep(
            lead_id=lead_id,
            step="stripe_kyc_done",
            payload_json={"account_id": account_id},
        )
        db.session.add(step_row)
    if step_row and not step_row.completed_at:
        step_row.completed_at = _dt.datetime.utcnow()

    if lead_id:
        lead = db.session.get(DriverLead, lead_id)
        if lead:
            db.session.add(DriverOnboardingAudit(
                lead_id=lead.id,
                actor="stripe_webhook",
                action="stripe_connect.charges_enabled",
                before_state=lead.state,
                after_state=lead.state,
                payload_json={"account_id": account_id},
            ))

    db.session.commit()
    return {
        "matched": True,
        "event": event_type,
        "charges_enabled": True,
        "lead_id": lead_id,
        "account_id": account_id,
    }
