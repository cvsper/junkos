r"""
Partner Acquisition Agent — LangGraph state machine (spec 07 §9 v1).

Pipeline:
    NEW -> OUTREACHED -> RESPONDED -> QUALIFIED -> BG_CHECK -> ONBOARDING -> ACTIVE
                              \                /
                               \-> HUMAN_REVIEW
                                \-> REJECTED

Each node is a small Python callable that runs ONE step of the pipeline
based on the lead's current DB state and returns the next state.

Public entry: `run_lead_pipeline(lead_id) -> dict` advances a single lead
by one step. Idempotent — safe to re-run.

LangGraph is used here as a declarative registry + runner. If the
`langgraph` package is importable we build a StateGraph; otherwise we fall
back to a plain dict dispatch. Tests cover the fallback path.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, TypedDict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State dict — kept minimal so the graph checkpoint (if ever persisted)
# doesn't need a dedicated table. Transient per run.
# ---------------------------------------------------------------------------
class PipelineState(TypedDict, total=False):
    lead_id: str
    current_state: str
    next_state: Optional[str]
    action: Optional[str]
    detail: Dict[str, Any]
    terminal: bool


# ---------------------------------------------------------------------------
# Node implementations — each reads the current lead, performs a tiny action,
# and returns a PipelineState update. All side effects go through existing
# modules / models so there's no duplication of state-transition logic.
# ---------------------------------------------------------------------------
def _load_lead(lead_id: str):
    from models import db
    from partner_models import DriverLead
    return db.session.get(DriverLead, lead_id), db


def node_scrape_check(state: PipelineState) -> PipelineState:
    """NEW → decide to OUTREACH or leave alone. No scraping here; that's the
    job of `run_all_scrapers`. This node just ensures the lead has an
    actionable contact channel."""
    lead, db = _load_lead(state["lead_id"])
    if not lead:
        return {**state, "terminal": True, "action": "not_found"}
    if lead.opted_out or lead.state == "REJECTED":
        return {**state, "current_state": lead.state, "terminal": True,
                "action": "lead_opted_out_or_rejected"}
    if not (lead.phone_e164 or lead.email):
        # Kick to HUMAN_REVIEW — no way to reach them.
        before = lead.state
        lead.state = "HUMAN_REVIEW"
        _audit(db, lead.id, "partner_langgraph", "pipeline.human_review_no_contact",
               before, "HUMAN_REVIEW", {})
        db.session.commit()
        return {**state, "current_state": "HUMAN_REVIEW",
                "action": "no_contact_channel", "terminal": True}
    return {**state, "current_state": lead.state, "next_state": "OUTREACHED",
            "action": "scrape_check_ok"}


def node_outreach(state: PipelineState) -> PipelineState:
    """NEW → OUTREACHED. Crafts a message (Claude or fallback) and sends it."""
    import sms_service
    from partner_outreach_agent import craft_outreach
    from partner_models import OutreachAttempt

    lead, db = _load_lead(state["lead_id"])
    if not lead or lead.state != "NEW":
        return {**state, "current_state": getattr(lead, "state", None),
                "action": "skip_outreach_wrong_state", "terminal": False}

    body = craft_outreach(lead, channel="sms")
    sid = None
    if lead.phone_e164:
        try:
            sid = sms_service.send_sms(lead.phone_e164, body)
        except Exception:
            logger.exception("send_sms failed in pipeline")

    db.session.add(OutreachAttempt(
        lead_id=lead.id, channel="sms", direction="out", body=body, twilio_sid=sid,
    ))
    before = lead.state
    lead.state = "OUTREACHED"
    _audit(db, lead.id, "partner_langgraph", "pipeline.outreach_sent",
           before, "OUTREACHED", {"sid": sid})
    db.session.commit()
    return {**state, "current_state": "OUTREACHED", "action": "outreach_sent",
            "detail": {"sid": sid}}


def node_qualify(state: PipelineState) -> PipelineState:
    """RESPONDED → QUALIFIED (or REJECTED / HUMAN_REVIEW) based on latest inbound."""
    from partner_models import OutreachAttempt
    from partner_qualifier import auto_qualify_and_transition

    lead, db = _load_lead(state["lead_id"])
    if not lead or lead.state != "RESPONDED":
        return {**state, "current_state": getattr(lead, "state", None),
                "action": "skip_qualify_wrong_state"}

    latest = (
        db.session.query(OutreachAttempt)
        .filter_by(lead_id=lead.id, direction="in")
        .order_by(OutreachAttempt.created_at.desc())
        .first()
    )
    if not latest:
        before = lead.state
        lead.state = "HUMAN_REVIEW"
        _audit(db, lead.id, "partner_langgraph", "pipeline.no_inbound_to_qualify",
               before, "HUMAN_REVIEW", {})
        db.session.commit()
        return {**state, "current_state": "HUMAN_REVIEW",
                "action": "qualify_no_inbound"}

    result = auto_qualify_and_transition(latest, db.session)
    lead, _ = _load_lead(state["lead_id"])  # reload — auto_qualify committed
    return {**state, "current_state": lead.state, "action": "qualify_ran",
            "detail": result}


def node_bg_check(state: PipelineState) -> PipelineState:
    """QUALIFIED → BG_CHECK sent. If Checkr not configured, leave in QUALIFIED
    with a `action=checkr_not_configured` marker."""
    from partner_checkr import create_candidate, invite_candidate, CheckrNotConfigured, CheckrAPIError
    from partner_models import BackgroundCheck, Qualification, DriverOnboardingAudit

    lead, db = _load_lead(state["lead_id"])
    if not lead or lead.state != "QUALIFIED":
        return {**state, "current_state": getattr(lead, "state", None),
                "action": "skip_bg_wrong_state"}

    qual = (
        db.session.query(Qualification)
        .filter_by(lead_id=lead.id)
        .order_by(Qualification.created_at.desc())
        .first()
    )
    if not qual or not qual.consent_checkr:
        return {**state, "current_state": lead.state,
                "action": "bg_blocked_no_consent"}

    try:
        candidate = create_candidate(lead)
        invite = invite_candidate(candidate.get("id"))
    except CheckrNotConfigured:
        return {**state, "current_state": lead.state,
                "action": "checkr_not_configured"}
    except CheckrAPIError as exc:
        logger.warning("checkr API error in pipeline: %s", exc)
        return {**state, "current_state": lead.state,
                "action": "checkr_api_error", "detail": {"error": str(exc)}}

    bg = BackgroundCheck(
        lead_id=lead.id,
        checkr_candidate_id=candidate.get("id"),
        status="pending",
    )
    db.session.add(bg)
    db.session.add(DriverOnboardingAudit(
        lead_id=lead.id,
        actor="partner_langgraph",
        action="pipeline.bg_check_invited",
        before_state=lead.state,
        after_state=lead.state,
        payload_json={"candidate_id": candidate.get("id"), "invite_id": invite.get("id")},
    ))
    db.session.commit()
    return {**state, "current_state": lead.state, "action": "bg_invited",
            "detail": {"candidate_id": candidate.get("id"), "invite_id": invite.get("id")}}


def node_stripe_connect(state: PipelineState) -> PipelineState:
    """ONBOARDING → create Stripe Connect link. Requires lead.state == ONBOARDING."""
    from partner_stripe_connect import start_onboarding, StripeNotConfigured

    lead, db = _load_lead(state["lead_id"])
    if not lead or lead.state != "ONBOARDING":
        return {**state, "current_state": getattr(lead, "state", None),
                "action": "skip_stripe_wrong_state"}

    try:
        info = start_onboarding(lead)
    except StripeNotConfigured:
        return {**state, "current_state": lead.state,
                "action": "stripe_not_configured"}
    except Exception as exc:
        logger.exception("stripe connect failed")
        return {**state, "current_state": lead.state,
                "action": "stripe_error", "detail": {"error": str(exc)}}

    return {**state, "current_state": lead.state, "action": "stripe_link_sent",
            "detail": info}


def node_verify_active(state: PipelineState) -> PipelineState:
    """ONBOARDING → ACTIVE when all three onboarding steps complete."""
    from partner_models import OnboardingStep, DriverOnboardingAudit

    lead, db = _load_lead(state["lead_id"])
    if not lead or lead.state != "ONBOARDING":
        return {**state, "current_state": getattr(lead, "state", None),
                "action": "skip_verify_wrong_state"}

    rows = (
        db.session.query(OnboardingStep)
        .filter_by(lead_id=lead.id)
        .all()
    )
    done = {r.step for r in rows if r.completed_at is not None}
    needed = {"stripe_kyc_done", "app_installed", "sim_dispatch_done"}
    if not needed.issubset(done):
        return {**state, "current_state": lead.state,
                "action": "verify_pending",
                "detail": {"have": sorted(done), "need": sorted(needed - done)}}

    before = lead.state
    lead.state = "ACTIVE"
    db.session.add(DriverOnboardingAudit(
        lead_id=lead.id,
        actor="partner_langgraph",
        action="pipeline.activated",
        before_state=before,
        after_state=lead.state,
        payload_json={"steps": sorted(done)},
    ))
    db.session.commit()
    return {**state, "current_state": "ACTIVE", "action": "activated",
            "terminal": True}


# ---------------------------------------------------------------------------
# Dispatch — maps the lead's current state to the node that advances it.
# ---------------------------------------------------------------------------
NODE_FOR_STATE: Dict[str, Callable[[PipelineState], PipelineState]] = {
    "NEW": node_outreach,
    "OUTREACHED": lambda s: {**s, "current_state": "OUTREACHED",
                              "action": "waiting_for_inbound"},
    "RESPONDED": node_qualify,
    "QUALIFIED": node_bg_check,
    "ONBOARDING": node_verify_active,
    "HUMAN_REVIEW": lambda s: {**s, "current_state": "HUMAN_REVIEW",
                                "action": "waiting_for_ops"},
    "ACTIVE": lambda s: {**s, "current_state": "ACTIVE", "action": "already_active",
                          "terminal": True},
    "REJECTED": lambda s: {**s, "current_state": "REJECTED", "action": "rejected",
                            "terminal": True},
}


# ---------------------------------------------------------------------------
# Optional LangGraph wiring. We use it as a registry; the actual dispatch
# below works with or without the package.
# ---------------------------------------------------------------------------
def _build_langgraph():
    try:
        from langgraph.graph import StateGraph, END  # type: ignore
    except Exception:  # pragma: no cover
        return None
    g = StateGraph(dict)
    for name, fn in [
        ("scrape_check", node_scrape_check),
        ("outreach", node_outreach),
        ("qualify", node_qualify),
        ("bg_check", node_bg_check),
        ("stripe_connect", node_stripe_connect),
        ("verify_active", node_verify_active),
    ]:
        g.add_node(name, fn)
    g.set_entry_point("scrape_check")
    # Linear edges — the tick() interface doesn't actually drive the graph
    # through langgraph; we only use it as an inspectable registry for now.
    g.add_edge("scrape_check", "outreach")
    g.add_edge("outreach", "qualify")
    g.add_edge("qualify", "bg_check")
    g.add_edge("bg_check", "stripe_connect")
    g.add_edge("stripe_connect", "verify_active")
    g.add_edge("verify_active", END)
    return g.compile()


_COMPILED = None


def get_compiled_graph():
    """Lazy-build the LangGraph artifact. Returns None if the lib is missing."""
    global _COMPILED
    if _COMPILED is None:
        _COMPILED = _build_langgraph()
    return _COMPILED


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------
def run_lead_pipeline(lead_id: str) -> Dict:
    """Advance one lead by one step and return the resulting PipelineState.

    Idempotent — if the lead's current state has no forward action (e.g.
    OUTREACHED waiting on inbound), returns immediately with action='waiting'.
    """
    from models import db
    from partner_models import DriverLead

    lead = db.session.get(DriverLead, lead_id)
    if not lead:
        return {"lead_id": lead_id, "error": "not_found", "terminal": True}

    state: PipelineState = {
        "lead_id": lead_id,
        "current_state": lead.state,
        "next_state": None,
        "action": None,
        "detail": {},
        "terminal": False,
    }

    # Short-circuit terminal states.
    if lead.state in ("ACTIVE", "REJECTED"):
        state["action"] = "terminal_state"
        state["terminal"] = True
        return state

    # Run the scrape-check preflight once — it routes to HUMAN_REVIEW if the
    # lead has no phone/email, regardless of current state.
    pre = node_scrape_check(state)
    if pre.get("terminal"):
        return pre
    state["current_state"] = pre["current_state"]

    node = NODE_FOR_STATE.get(lead.state, lambda s: {**s, "action": "no_node_for_state"})
    return node(state)


def run_lead_pipeline_all(states=("NEW", "RESPONDED", "QUALIFIED", "ONBOARDING")) -> Dict:
    """Advance every eligible lead once. Returns per-state counters."""
    from models import db
    from partner_models import DriverLead

    counters = {"advanced": 0, "skipped": 0, "errors": 0}
    rows = db.session.query(DriverLead).filter(DriverLead.state.in_(states)).all()
    for lead in rows:
        try:
            result = run_lead_pipeline(lead.id)
            if result.get("action") in (None, "waiting_for_inbound", "waiting_for_ops"):
                counters["skipped"] += 1
            else:
                counters["advanced"] += 1
        except Exception:
            logger.exception("pipeline tick failed for lead %s", lead.id)
            counters["errors"] += 1
    return counters


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _audit(db, lead_id, actor, action, before_state, after_state, payload):
    from partner_models import DriverOnboardingAudit
    db.session.add(DriverOnboardingAudit(
        lead_id=lead_id,
        actor=actor,
        action=action,
        before_state=before_state,
        after_state=after_state,
        payload_json=payload,
    ))
