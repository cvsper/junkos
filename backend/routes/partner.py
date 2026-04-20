"""
Partner (Driver) Acquisition Agent — routes (spec 07).

72h-MVP scope (spec §9):
  * Craigslist scraper → POST /internal/leads/ingest  (service-token guarded)
  * Twilio SMS outreach via existing sms_service.send_sms
  * Twilio inbound webhook (STOP → opt-out)
  * Manual qualification form endpoint (Retool)
  * Manual state-transition endpoint (whitelisted transitions only)
  * Manual Checkr write-back endpoint (Ops runs Checkr by hand for MVP)
  * Manual onboarding-step tracker (Stripe link sent/KYC done/etc.)
  * Ops dashboard list endpoint

Every mutation writes a DriverOnboardingAudit row.

Compliance rails (spec §8):
  * Hard limit: 3 outbound SMS per lead per 48h → 429.
  * Opt-out (body contains 'STOP') → opted_out=True + state=REJECTED.
  * Checkr row requires consent_checkr=True + ssn_last_4 captured.
  * "Reply STOP to opt out" baked into the initial outreach template.
"""

import datetime as _dt
import hashlib
import hmac
import json
import logging
import os
import re
from functools import wraps

from flask import Blueprint, jsonify, request

from models import db
from partner_models import (
    DriverLead,
    LeadSource,
    OutreachAttempt,
    Qualification,
    BackgroundCheck,
    OnboardingStep,
    DriverOnboardingAudit,
)
import sms_service

logger = logging.getLogger(__name__)

partner_bp = Blueprint("partner", __name__, url_prefix="/partner/v1")


# ---------------------------------------------------------------------------
# Auth — service-token for internal endpoints.
# ---------------------------------------------------------------------------
def _service_token():
    return os.environ.get("PARTNER_SERVICE_TOKEN", "")


def require_service_token(f):
    """Gate internal endpoints (scrapers, Twilio bridges, Ops tooling)."""

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
# State machine — spec 07 §2 flow whitelist.
# ---------------------------------------------------------------------------
STATE_TRANSITIONS = {
    "NEW": {"OUTREACHED", "REJECTED"},
    "OUTREACHED": {"RESPONDED", "REJECTED", "HUMAN_REVIEW"},
    "RESPONDED": {"QUALIFIED", "REJECTED", "HUMAN_REVIEW"},
    "QUALIFIED": {"ONBOARDING", "REJECTED"},
    "ONBOARDING": {"ACTIVE", "REJECTED"},
    "ACTIVE": set(),
    "REJECTED": set(),
    "HUMAN_REVIEW": {"QUALIFIED", "REJECTED", "RESPONDED"},
}


def _valid_transition(before, after):
    return after in STATE_TRANSITIONS.get(before, set())


def _audit(lead_id, actor, action, before_state, after_state, payload=None):
    """Append-only audit log. Never raises into the request."""
    try:
        entry = DriverOnboardingAudit(
            lead_id=lead_id,
            actor=actor,
            action=action,
            before_state=before_state,
            after_state=after_state,
            payload_json=payload,
        )
        db.session.add(entry)
    except Exception as exc:  # pragma: no cover
        logger.warning("audit log failed for %s/%s: %s", lead_id, action, exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _normalize_phone(raw):
    """Reduce to digits (for dedupe-hash input). Empty-string safe."""
    if not raw:
        return ""
    return re.sub(r"\D", "", raw)


def _compute_dedupe_hash(phone, name_guess):
    """sha256(normalized_phone || '|' || normalized_name_guess)."""
    phone_norm = _normalize_phone(phone)
    name_norm = (name_guess or "").strip().lower()
    basis = "{}|{}".format(phone_norm, name_norm)
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _get_or_create_source(platform, search_url=None, metro=None):
    src = db.session.query(LeadSource).filter_by(platform=platform, metro=metro).first()
    if src:
        return src
    src = LeadSource(
        platform=platform,
        search_url=search_url or "https://example.com",
        metro=metro,
    )
    db.session.add(src)
    db.session.flush()
    return src


# ---------------------------------------------------------------------------
# POST /internal/leads/ingest — scraper sink. Idempotent on dedupe_hash.
# ---------------------------------------------------------------------------
@partner_bp.route("/internal/leads/ingest", methods=["POST"])
@require_service_token
def ingest_lead():
    data = request.get_json(silent=True) or {}
    platform = (data.get("source") or data.get("platform") or "").strip().lower()
    if platform not in {"fb_marketplace", "craigslist", "thumbtack", "nextdoor", "indeed"}:
        return jsonify({"error": "invalid source/platform"}), 400

    phone_raw = data.get("phone") or data.get("phone_e164") or ""
    name_guess = data.get("name_guess") or data.get("name") or ""
    metro = (data.get("metro") or "miami").strip().lower()
    external_ref = data.get("external_ref")
    raw = data.get("raw") or data.get("raw_listing_json")

    phone_e164 = sms_service.format_phone(phone_raw) if phone_raw else None

    if not phone_raw and not external_ref:
        return jsonify({"error": "phone or external_ref required"}), 400

    dedupe_hash = _compute_dedupe_hash(phone_raw, name_guess)

    existing = db.session.query(DriverLead).filter_by(dedupe_hash=dedupe_hash).first()
    if existing:
        return jsonify({
            "lead_id": existing.id,
            "state": existing.state,
            "deduped": True,
        }), 200

    source = _get_or_create_source(platform, search_url=data.get("search_url"), metro=metro)

    lead = DriverLead(
        source_id=source.id,
        external_ref=external_ref,
        raw_listing_json=raw,
        name_guess=name_guess or None,
        phone_e164=phone_e164,
        email=data.get("email"),
        metro=metro,
        platform=platform,
        state="NEW",
        dedupe_hash=dedupe_hash,
    )
    db.session.add(lead)
    db.session.flush()

    _audit(lead.id, actor="system", action="lead.ingest",
           before_state=None, after_state="NEW",
           payload={"platform": platform, "metro": metro, "external_ref": external_ref})
    db.session.commit()

    return jsonify({"lead_id": lead.id, "state": lead.state, "deduped": False}), 201


# ---------------------------------------------------------------------------
# POST /internal/leads/<id>/outreach — send initial Twilio SMS.
# ---------------------------------------------------------------------------
OUTREACH_TEMPLATE = (
    "Hey — saw your Craigslist ad in {metro}. Umuve routes junk/hauling jobs "
    "to drivers: $80-180/load, no fees. Interested in a 3-min qualifier? "
    "Reply YES. (Reply STOP to opt out.)"
)

# Compliance rail: hard max 3 outbound per lead per 48h (spec §8).
OUTREACH_MAX_PER_WINDOW = 3
OUTREACH_WINDOW_HOURS = 48


def _recent_outbound_count(lead_id):
    cutoff = _dt.datetime.utcnow() - _dt.timedelta(hours=OUTREACH_WINDOW_HOURS)
    return (
        db.session.query(OutreachAttempt)
        .filter(
            OutreachAttempt.lead_id == lead_id,
            OutreachAttempt.direction == "out",
            OutreachAttempt.created_at >= cutoff,
        )
        .count()
    )


@partner_bp.route("/internal/leads/<lead_id>/outreach", methods=["POST"])
@require_service_token
def send_outreach(lead_id):
    lead = db.session.get(DriverLead, lead_id)
    if not lead:
        return jsonify({"error": "lead not found"}), 404
    if lead.opted_out:
        return jsonify({"error": "lead has opted out"}), 409

    recent = _recent_outbound_count(lead.id)
    if recent >= OUTREACH_MAX_PER_WINDOW:
        return jsonify({
            "error": "outreach rate limit exceeded (3 per 48h)",
            "recent_outbound": recent,
        }), 429

    if not lead.phone_e164:
        return jsonify({"error": "lead has no phone"}), 400

    metro_display = (lead.metro or "your area").title()
    body = OUTREACH_TEMPLATE.format(metro=metro_display)

    # send_sms returns a SID or None; never raises.
    sid = sms_service.send_sms(lead.phone_e164, body)

    attempt = OutreachAttempt(
        lead_id=lead.id,
        channel="sms",
        direction="out",
        body=body,
        twilio_sid=sid,
    )
    db.session.add(attempt)

    before = lead.state
    if lead.state == "NEW":
        lead.state = "OUTREACHED"

    _audit(lead.id, actor="system", action="lead.outreach",
           before_state=before, after_state=lead.state,
           payload={"sid": sid, "attempt_id": attempt.id})
    db.session.commit()

    return jsonify({
        "lead_id": lead.id,
        "state": lead.state,
        "attempt_id": attempt.id,
        "sid": sid,
    }), 200


# ---------------------------------------------------------------------------
# POST /internal/twilio/inbound — Twilio inbound SMS webhook.
# ---------------------------------------------------------------------------
@partner_bp.route("/internal/twilio/inbound", methods=["POST"])
@require_service_token
def twilio_inbound():
    # Twilio posts form-encoded; accept JSON too for test convenience.
    payload = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})
    from_phone = payload.get("From") or payload.get("from") or ""
    body = payload.get("Body") or payload.get("body") or ""

    if not from_phone:
        return jsonify({"error": "From required"}), 400

    formatted = sms_service.format_phone(from_phone)
    lead = db.session.query(DriverLead).filter_by(phone_e164=formatted).first()
    if not lead:
        # Also try raw-phone fallback (e.g. if stored without +1).
        digits = _normalize_phone(from_phone)
        if digits:
            lead = (
                db.session.query(DriverLead)
                .filter(DriverLead.phone_e164.like("%{}".format(digits[-10:])))
                .first()
            )
        if not lead:
            return jsonify({"error": "lead not found", "phone": formatted}), 404

    attempt = OutreachAttempt(
        lead_id=lead.id,
        channel="sms",
        direction="in",
        body=body,
    )
    db.session.add(attempt)

    before = lead.state
    is_stop = "STOP" in (body or "").upper()

    if is_stop:
        lead.opted_out = True
        if lead.state != "REJECTED":
            lead.state = "REJECTED"
        action = "lead.opt_out"
    else:
        if lead.state == "OUTREACHED":
            lead.state = "RESPONDED"
        action = "lead.inbound_reply"

    _audit(lead.id, actor="system", action=action,
           before_state=before, after_state=lead.state,
           payload={"body": body, "attempt_id": attempt.id, "stop": is_stop})
    db.session.commit()

    return jsonify({
        "lead_id": lead.id,
        "state": lead.state,
        "opted_out": lead.opted_out,
    }), 200


# ---------------------------------------------------------------------------
# GET /partner/v1/leads — ops dashboard (service-token guard).
# ---------------------------------------------------------------------------
@partner_bp.route("/leads", methods=["GET"])
@require_service_token
def list_leads():
    q = db.session.query(DriverLead)

    state = request.args.get("state")
    metro = request.args.get("metro")
    if state:
        q = q.filter(DriverLead.state == state)
    if metro:
        q = q.filter(DriverLead.metro == metro.lower())

    try:
        limit = min(max(int(request.args.get("limit", 50)), 1), 200)
        offset = max(int(request.args.get("offset", 0)), 0)
    except (TypeError, ValueError):
        return jsonify({"error": "invalid limit/offset"}), 400

    total = q.count()
    rows = (
        q.order_by(DriverLead.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return jsonify({
        "leads": [r.to_dict() for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    })


# ---------------------------------------------------------------------------
# POST /partner/v1/leads/<id>/qualify — manual Retool form.
# ---------------------------------------------------------------------------
REQUIRED_QUAL_FIELDS_TRUTHY = ("has_truck", "has_insurance", "has_license")


@partner_bp.route("/leads/<lead_id>/qualify", methods=["POST"])
@require_service_token
def record_qualify(lead_id):
    lead = db.session.get(DriverLead, lead_id)
    if not lead:
        return jsonify({"error": "lead not found"}), 404
    data = request.get_json(silent=True) or {}

    qual = Qualification(
        lead_id=lead.id,
        has_truck=data.get("has_truck"),
        truck_type=data.get("truck_type"),
        has_insurance=data.get("has_insurance"),
        has_license=data.get("has_license"),
        past_hauling_years=data.get("past_hauling_years"),
        self_reported_availability_hours=data.get("self_reported_availability_hours"),
        consent_checkr=bool(data.get("consent_checkr", False)),
        consent_sms=bool(data.get("consent_sms", False)),
        ssn_last_4=data.get("ssn_last_4"),
    )
    qual.completed_at = _dt.datetime.utcnow()
    db.session.add(qual)

    all_required = all(bool(data.get(k)) for k in REQUIRED_QUAL_FIELDS_TRUTHY)
    consents_ok = bool(data.get("consent_sms")) and bool(data.get("consent_checkr"))

    before = lead.state
    transitioned = False
    if all_required and consents_ok:
        # Allow transition from RESPONDED or HUMAN_REVIEW; also from OUTREACHED/NEW
        # if Ops is filling the form directly.
        if lead.state in ("RESPONDED", "HUMAN_REVIEW", "OUTREACHED", "NEW"):
            lead.state = "QUALIFIED"
            transitioned = True

    _audit(lead.id, actor="ops", action="lead.qualify",
           before_state=before, after_state=lead.state,
           payload={"qualification_id": qual.id, "transitioned": transitioned})
    db.session.commit()

    return jsonify({
        "qualification_id": qual.id,
        "lead_id": lead.id,
        "state": lead.state,
        "qualified": lead.state == "QUALIFIED",
    }), 201


# ---------------------------------------------------------------------------
# POST /partner/v1/leads/<id>/state — manual state transition.
# ---------------------------------------------------------------------------
@partner_bp.route("/leads/<lead_id>/state", methods=["POST"])
@require_service_token
def transition_state(lead_id):
    lead = db.session.get(DriverLead, lead_id)
    if not lead:
        return jsonify({"error": "lead not found"}), 404

    data = request.get_json(silent=True) or {}
    to_state = (data.get("to_state") or data.get("state") or "").strip()
    if not to_state:
        return jsonify({"error": "to_state required"}), 400

    before = lead.state
    if not _valid_transition(before, to_state):
        return jsonify({
            "error": "invalid state transition",
            "from": before,
            "to": to_state,
            "allowed": sorted(STATE_TRANSITIONS.get(before, set())),
        }), 400

    lead.state = to_state
    _audit(lead.id, actor=data.get("actor") or "ops", action="lead.transition",
           before_state=before, after_state=to_state,
           payload={"reason": data.get("reason")})
    db.session.commit()

    return jsonify({"lead_id": lead.id, "state": lead.state, "from": before}), 200


# ---------------------------------------------------------------------------
# POST /partner/v1/leads/<id>/bg-check — Ops writes Checkr result by hand.
# ---------------------------------------------------------------------------
def _add_business_days(start, n):
    """Skip weekends. Rough FCRA 5-business-day helper."""
    d = start
    added = 0
    while added < n:
        d += _dt.timedelta(days=1)
        if d.weekday() < 5:  # Mon-Fri
            added += 1
    return d


@partner_bp.route("/leads/<lead_id>/bg-check", methods=["POST"])
@require_service_token
def record_bg_check(lead_id):
    lead = db.session.get(DriverLead, lead_id)
    if not lead:
        return jsonify({"error": "lead not found"}), 404

    data = request.get_json(silent=True) or {}
    status = (data.get("status") or "pending").strip().lower()
    if status not in ("pending", "clear", "consider", "suspended"):
        return jsonify({"error": "invalid status"}), 400

    # Compliance rail: no Checkr row without consent_checkr + ssn_last_4 (§8).
    qual = (
        db.session.query(Qualification)
        .filter_by(lead_id=lead.id)
        .order_by(Qualification.created_at.desc())
        .first()
    )
    if status != "pending":
        if not qual or not qual.consent_checkr or not qual.ssn_last_4:
            return jsonify({
                "error": "missing Checkr consent or ssn_last_4 for this lead",
            }), 412

    bg = BackgroundCheck(
        lead_id=lead.id,
        checkr_candidate_id=data.get("checkr_candidate_id"),
        checkr_report_id=data.get("checkr_report_id"),
        status=status,
        mvr_status=data.get("mvr_status"),
        criminal_status=data.get("criminal_status"),
        raw_webhook_json=data.get("raw_webhook_json"),
    )
    if status == "consider":
        bg.adverse_action_due_at = _add_business_days(_dt.datetime.utcnow(), 5)

    db.session.add(bg)
    _audit(lead.id, actor="ops", action="bg_check.record",
           before_state=lead.state, after_state=lead.state,
           payload={"bg_id": bg.id, "status": status})
    db.session.commit()

    return jsonify({
        "bg_check_id": bg.id,
        "lead_id": lead.id,
        "status": bg.status,
        "adverse_action_due_at": bg.adverse_action_due_at.isoformat() if bg.adverse_action_due_at else None,
    }), 201


# ---------------------------------------------------------------------------
# POST /partner/v1/leads/<id>/onboarding-step — Ops marks a step complete.
# ---------------------------------------------------------------------------
@partner_bp.route("/leads/<lead_id>/onboarding-step", methods=["POST"])
@require_service_token
def record_onboarding_step(lead_id):
    lead = db.session.get(DriverLead, lead_id)
    if not lead:
        return jsonify({"error": "lead not found"}), 404

    data = request.get_json(silent=True) or {}
    step = (data.get("step") or "").strip()
    if step not in ("stripe_link_sent", "stripe_kyc_done", "app_installed", "sim_dispatch_done"):
        return jsonify({"error": "invalid step"}), 400

    row = OnboardingStep(
        lead_id=lead.id,
        step=step,
        completed_at=_dt.datetime.utcnow() if data.get("completed", True) else None,
        payload_json=data.get("payload"),
    )
    db.session.add(row)

    _audit(lead.id, actor="ops", action="onboarding.step",
           before_state=lead.state, after_state=lead.state,
           payload={"step": step})
    db.session.commit()

    return jsonify({
        "step_id": row.id,
        "lead_id": lead.id,
        "step": step,
    }), 201


# ---------------------------------------------------------------------------
# Error handlers — keep JSON shape consistent.
# ---------------------------------------------------------------------------
@partner_bp.errorhandler(404)
def _404(e):
    return jsonify({"error": "not_found"}), 404


@partner_bp.errorhandler(405)
def _405(e):
    return jsonify({"error": "method_not_allowed"}), 405
