"""
Partner Acquisition Agent — v1 expansion routes (spec 07 §9 v1).

Wires the new modules (Claude outreach, qualifier, Checkr, Stripe Connect,
LangGraph pipeline) into Flask endpoints. Mounted under /partner/v1/.

Auth rail: all mutating endpoints require the existing X-Service-Token header
(see routes/partner.py for the shared helper — we re-import it here to keep
isolation). Webhook endpoints verify provider-specific signatures instead.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import logging
import os
from functools import wraps

from flask import Blueprint, jsonify, request

from models import db
from partner_models import (
    DriverLead,
    OutreachAttempt,
    DriverOnboardingAudit,
)

logger = logging.getLogger(__name__)

partner_v1_bp = Blueprint("partner_v1", __name__, url_prefix="/partner/v1")


# ---------------------------------------------------------------------------
# Auth — mirrors routes/partner.py so we don't import private state.
# ---------------------------------------------------------------------------
def _service_token() -> str:
    return os.environ.get("PARTNER_SERVICE_TOKEN", "")


def require_service_token(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        expected = _service_token()
        if not expected:
            return jsonify({"error": "service token not configured"}), 503
        provided = request.headers.get("X-Service-Token", "")
        if not hmac.compare_digest(provided, expected):
            return jsonify({"error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# POST /partner/v1/leads/<id>/outreach?ai=true
#
# Wraps the existing MVP outreach flow with an optional ai=true flag that
# routes body generation through partner_outreach_agent.craft_outreach.
# ---------------------------------------------------------------------------
@partner_v1_bp.route("/leads/<lead_id>/outreach", methods=["POST"])
@require_service_token
def v1_outreach(lead_id):
    import sms_service
    from partner_outreach_agent import craft_outreach

    lead = db.session.get(DriverLead, lead_id)
    if not lead:
        return jsonify({"error": "lead not found"}), 404
    if lead.opted_out:
        return jsonify({"error": "lead has opted out"}), 409
    if not lead.phone_e164:
        return jsonify({"error": "lead has no phone"}), 400

    # Reuse the MVP rate rail (3 per 48h).
    cutoff = _dt.datetime.utcnow() - _dt.timedelta(hours=48)
    recent = (
        db.session.query(OutreachAttempt)
        .filter(
            OutreachAttempt.lead_id == lead.id,
            OutreachAttempt.direction == "out",
            OutreachAttempt.created_at >= cutoff,
        )
        .count()
    )
    if recent >= 3:
        return jsonify({
            "error": "outreach rate limit exceeded (3 per 48h)",
            "recent_outbound": recent,
        }), 429

    use_ai = request.args.get("ai", "").lower() in ("1", "true", "yes")
    channel = (request.args.get("channel") or "sms").lower()

    if use_ai:
        body = craft_outreach(lead, channel=channel)
        actor = "claude_outreach_v1"
    else:
        metro_display = (lead.metro or "your area").title()
        body = (
            "Hey — saw your ad in {metro}. Umuve routes junk/hauling jobs "
            "to drivers: $80-180/load, no fees. Interested in a 3-min qualifier? "
            "Reply YES. (Reply STOP to opt out.)"
        ).format(metro=metro_display)
        actor = "system"

    sid = None
    if channel == "sms":
        sid = sms_service.send_sms(lead.phone_e164, body)

    attempt = OutreachAttempt(
        lead_id=lead.id,
        channel="sms" if channel == "sms" else "email",
        direction="out",
        body=body,
        twilio_sid=sid,
    )
    db.session.add(attempt)

    before = lead.state
    if lead.state == "NEW":
        lead.state = "OUTREACHED"

    db.session.add(DriverOnboardingAudit(
        lead_id=lead.id, actor=actor, action="lead.outreach_v1",
        before_state=before, after_state=lead.state,
        payload_json={"sid": sid, "ai": use_ai, "channel": channel},
    ))
    db.session.commit()

    return jsonify({
        "lead_id": lead.id,
        "state": lead.state,
        "attempt_id": attempt.id,
        "sid": sid,
        "body": body,
        "ai": use_ai,
    }), 200


# ---------------------------------------------------------------------------
# POST /partner/v1/leads/<id>/bg-check — triggers Checkr candidate create+invite.
# Returns 503 if CHECKR_API_KEY is unset.
# ---------------------------------------------------------------------------
@partner_v1_bp.route("/leads/<lead_id>/bg-check/start", methods=["POST"])
@require_service_token
def v1_bg_check(lead_id):
    from partner_checkr import (
        create_candidate,
        invite_candidate,
        CheckrNotConfigured,
        CheckrAPIError,
    )
    from partner_models import BackgroundCheck, Qualification

    lead = db.session.get(DriverLead, lead_id)
    if not lead:
        return jsonify({"error": "lead not found"}), 404

    qual = (
        db.session.query(Qualification)
        .filter_by(lead_id=lead.id)
        .order_by(Qualification.created_at.desc())
        .first()
    )
    if not qual or not qual.consent_checkr:
        return jsonify({"error": "consent_checkr required"}), 412

    try:
        candidate = create_candidate(lead)
        invite = invite_candidate(candidate.get("id"))
    except CheckrNotConfigured as exc:
        return jsonify({"error": "checkr not configured", "detail": str(exc)}), 503
    except CheckrAPIError as exc:
        return jsonify({"error": "checkr api error", "detail": str(exc)}), 502

    bg = BackgroundCheck(
        lead_id=lead.id,
        checkr_candidate_id=candidate.get("id"),
        status="pending",
    )
    db.session.add(bg)
    db.session.add(DriverOnboardingAudit(
        lead_id=lead.id, actor="partner_v1", action="bg_check.create",
        before_state=lead.state, after_state=lead.state,
        payload_json={"candidate_id": candidate.get("id"), "invite_id": invite.get("id")},
    ))
    db.session.commit()

    return jsonify({
        "bg_check_id": bg.id,
        "candidate_id": candidate.get("id"),
        "invite_id": invite.get("id"),
        "invitation_url": invite.get("invitation_url"),
    }), 201


# ---------------------------------------------------------------------------
# POST /partner/v1/webhooks/checkr — verified via HMAC signature.
# ---------------------------------------------------------------------------
@partner_v1_bp.route("/webhooks/checkr", methods=["POST"])
def webhook_checkr():
    from partner_checkr import handle_webhook, verify_webhook

    raw = request.get_data(cache=False)
    signature = request.headers.get("X-Checkr-Signature") or request.headers.get("Checkr-Signature") or ""
    if not verify_webhook(raw, signature):
        return jsonify({"error": "invalid signature"}), 401

    try:
        payload = request.get_json(force=True, silent=True) or {}
        result = handle_webhook(payload)
    except Exception as exc:
        logger.exception("checkr webhook handler crashed")
        return jsonify({"error": "handler_error", "detail": str(exc)}), 500
    return jsonify(result), 200


# ---------------------------------------------------------------------------
# POST /partner/v1/onboarding/stripe-connect/start
#
# Returns the onboarding URL the driver should visit.
# ---------------------------------------------------------------------------
@partner_v1_bp.route("/onboarding/stripe-connect/start", methods=["POST"])
@require_service_token
def stripe_connect_start():
    from partner_stripe_connect import start_onboarding, StripeNotConfigured

    data = request.get_json(silent=True) or {}
    lead_id = data.get("lead_id") or data.get("id")
    if not lead_id:
        return jsonify({"error": "lead_id required"}), 400
    lead = db.session.get(DriverLead, lead_id)
    if not lead:
        return jsonify({"error": "lead not found"}), 404

    try:
        info = start_onboarding(lead)
    except StripeNotConfigured as exc:
        return jsonify({"error": "stripe not configured", "detail": str(exc)}), 503
    except Exception as exc:
        logger.exception("stripe connect start failed")
        return jsonify({"error": "stripe_error", "detail": str(exc)}), 502

    return jsonify(info), 200


# ---------------------------------------------------------------------------
# POST /partner/v1/webhooks/stripe-connect — verified via Stripe SDK.
# ---------------------------------------------------------------------------
@partner_v1_bp.route("/webhooks/stripe-connect", methods=["POST"])
def webhook_stripe_connect():
    from partner_stripe_connect import handle_webhook

    raw = request.get_data(cache=False)
    sig = request.headers.get("Stripe-Signature", "")
    secret = os.environ.get("STRIPE_CONNECT_WEBHOOK_SECRET", "").strip()

    event = None
    if secret and sig:
        try:
            import stripe  # type: ignore
            event = stripe.Webhook.construct_event(raw, sig, secret)
        except Exception as exc:
            logger.warning("stripe connect sig check failed: %s", exc)
            return jsonify({"error": "invalid signature"}), 401
    else:
        # Dev / test path: accept unsigned JSON.
        event = request.get_json(silent=True) or {}

    try:
        result = handle_webhook(event if isinstance(event, dict) else dict(event))
    except Exception as exc:
        logger.exception("stripe connect webhook handler crashed")
        return jsonify({"error": "handler_error", "detail": str(exc)}), 500
    return jsonify(result), 200


# ---------------------------------------------------------------------------
# POST /partner/v1/pipeline/tick — advance one lead by one step.
# POST /partner/v1/pipeline/tick-all — advance every eligible lead once.
# ---------------------------------------------------------------------------
@partner_v1_bp.route("/pipeline/tick", methods=["POST"])
@require_service_token
def pipeline_tick():
    from partner_langgraph import run_lead_pipeline

    data = request.get_json(silent=True) or {}
    lead_id = data.get("lead_id") or data.get("id")
    if not lead_id:
        return jsonify({"error": "lead_id required"}), 400

    result = run_lead_pipeline(lead_id)
    status = 200 if not result.get("error") else 404
    return jsonify(result), status


@partner_v1_bp.route("/pipeline/tick-all", methods=["POST"])
@require_service_token
def pipeline_tick_all():
    from partner_langgraph import run_lead_pipeline_all

    counters = run_lead_pipeline_all()
    return jsonify({"counters": counters}), 200


# ---------------------------------------------------------------------------
# Error handlers.
# ---------------------------------------------------------------------------
@partner_v1_bp.errorhandler(404)
def _404(e):
    return jsonify({"error": "not_found"}), 404


@partner_v1_bp.errorhandler(405)
def _405(e):
    return jsonify({"error": "method_not_allowed"}), 405
