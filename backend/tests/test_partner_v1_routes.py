"""
Partner Acquisition Agent — v1 expansion tests (spec 07 §9 v1).

Coverage:
  * All 5 scraper modules importable; dedupe_hash produced correctly.
  * Claude outreach returns template when ANTHROPIC_API_KEY missing.
  * Claude outreach uses SDK result (mocked) when key present.
  * Qualifier keyword fallback: yes/interested -> qualified, stop -> red_flag.
  * Qualifier auto-transitions RESPONDED -> QUALIFIED and writes a row.
  * Checkr: 503 when CHECKR_API_KEY missing, handle_webhook clear/consider.
  * Stripe Connect: start_onboarding happy path with mocked stripe SDK,
    handle_webhook marks step complete.
  * LangGraph: NEW -> OUTREACHED advance; terminal states no-op; missing
    lead returns error.
  * Route wiring: /partner/v1/leads/<id>/outreach?ai=true uses Claude module.
"""

from __future__ import annotations

import os
import sys
import types
import datetime as _dt
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Env setup — MUST run before app import. The MVP test file runs first
# in most pytest orderings but we set again here to be safe.
# ---------------------------------------------------------------------------
os.environ.setdefault("PARTNER_SERVICE_TOKEN", "test-service-token-partner")

import partner_models  # noqa: F401  — register tables on db.metadata
from partner_models import (
    DriverLead,
    OutreachAttempt,
    Qualification,
    BackgroundCheck,
    OnboardingStep,
    DriverOnboardingAudit,
)
from models import db

SERVICE_TOKEN = "test-service-token-partner"


# ---------------------------------------------------------------------------
# Register partner_v1 blueprint on the shared app. This MUST run before
# the app serves its first request — we do it at module import time so that
# collection alone wires the blueprint on, before any other test module's
# `client` fixture fires requests.
# ---------------------------------------------------------------------------
def _ensure_blueprints_registered():
    """Register partner_bp + partner_v1_bp on the shared Flask app. Safe to
    call from multiple test modules — idempotent on blueprint.name."""
    from server import app as flask_app
    from routes.partner import partner_bp
    from routes.partner_v1 import partner_v1_bp

    if "partner" not in flask_app.blueprints:
        flask_app.register_blueprint(partner_bp)
    if "partner_v1" not in flask_app.blueprints:
        flask_app.register_blueprint(partner_v1_bp)
    with flask_app.app_context():
        db.create_all()


_ensure_blueprints_registered()


@pytest.fixture(scope="session", autouse=True)
def _register_partner_v1_bp(app):
    # Fixture keeps the fixture-order dep on `app`, but the actual wiring
    # already happened at import time above. We just ensure create_all has
    # been run against this specific app instance.
    with app.app_context():
        db.create_all()
    yield


def _svc_hdr():
    return {"X-Service-Token": SERVICE_TOKEN}


def _make_lead(phone="3055551212", name="Bob Smith", state="NEW", metro="miami"):
    lead = DriverLead(
        phone_e164="+1" + phone,
        name_guess=name,
        metro=metro,
        platform="craigslist",
        state=state,
        dedupe_hash="test-hash-" + phone,
    )
    db.session.add(lead)
    db.session.commit()
    return lead


# ===========================================================================
# 1. Scraper modules — importable, dedupe_hash shape, nextdoor stubbed.
# ===========================================================================
def test_scrapers_package_exposes_five_modules():
    from partner_scrapers import (
        craigslist,
        facebook_marketplace,
        thumbtack,
        nextdoor,
        indeed,
        run_all_scrapers,
        compute_dedupe_hash,
        enrich,
    )
    for mod in (craigslist, facebook_marketplace, thumbtack, nextdoor, indeed):
        assert hasattr(mod, "scrape")


def test_compute_dedupe_hash_prefers_phone_then_email_then_ext():
    from partner_scrapers import compute_dedupe_hash

    h1 = compute_dedupe_hash(phone="(305) 555-1212", email="a@b.com", external_id="ext-1")
    h2 = compute_dedupe_hash(phone="3055551212")
    assert h1 == h2, "phone normalization should collapse formatting"

    h_email = compute_dedupe_hash(phone="", email="A@B.com", external_id="ignored")
    h_email_lower = compute_dedupe_hash(email="a@b.com")
    assert h_email == h_email_lower


def test_nextdoor_scraper_is_deferred():
    from partner_scrapers import nextdoor
    rows = nextdoor.scrape(city="Miami", limit=10)
    assert rows == []


def test_run_all_scrapers_aggregates_and_enriches(monkeypatch):
    from partner_scrapers import run_all_scrapers
    import partner_scrapers.craigslist as cl
    import partner_scrapers.facebook_marketplace as fb
    import partner_scrapers.thumbtack as tt
    import partner_scrapers.indeed as idd

    def fake_cl(city, limit):
        return [{
            "source": "craigslist",
            "external_id": "cl-1",
            "phone": "3055551111",
            "name_guess": "Bob's Hauling",
            "url": "https://miami.craigslist.org/1",
        }]

    def fake_fb(city, limit):
        return []  # gated

    def fake_tt(city, limit):
        return [{
            "source": "thumbtack",
            "external_id": "/pros/abc",
            "name_guess": "Ace Junk",
            "url": "https://www.thumbtack.com/pros/abc",
        }]

    def fake_idd(city, limit):
        return [{
            "source": "indeed",
            "external_id": "jk-xyz",
            "url": "https://www.indeed.com/viewjob?jk=xyz",
        }]

    monkeypatch.setattr(cl, "scrape", fake_cl)
    monkeypatch.setattr(fb, "scrape", fake_fb)
    monkeypatch.setattr(tt, "scrape", fake_tt)
    monkeypatch.setattr(idd, "scrape", fake_idd)

    rows = run_all_scrapers(city="Miami", limit_per_source=5)
    sources = [r["source"] for r in rows]
    assert "craigslist" in sources
    assert "thumbtack" in sources
    assert "indeed" in sources
    for r in rows:
        assert r.get("dedupe_hash")
        assert len(r["dedupe_hash"]) == 64  # sha256 hex


def test_scraper_exception_does_not_kill_aggregator(monkeypatch):
    from partner_scrapers import run_all_scrapers
    import partner_scrapers.craigslist as cl

    def boom(city, limit):
        raise RuntimeError("network down")
    monkeypatch.setattr(cl, "scrape", boom)
    # The other scrapers will try real networks; neutralize them.
    import partner_scrapers.facebook_marketplace as fb
    import partner_scrapers.thumbtack as tt
    import partner_scrapers.indeed as idd
    monkeypatch.setattr(fb, "scrape", lambda city, limit: [])
    monkeypatch.setattr(tt, "scrape", lambda city, limit: [])
    monkeypatch.setattr(idd, "scrape", lambda city, limit: [])

    rows = run_all_scrapers(city="Miami", limit_per_source=5)
    assert rows == []  # nothing propagates — scraper exceptions are swallowed


# ===========================================================================
# 2. Claude outreach agent — fallback + mocked SDK.
# ===========================================================================
def test_craft_outreach_without_key_uses_template(monkeypatch, db_session):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from partner_outreach_agent import craft_outreach, STOP_FOOTER

    lead = _make_lead(phone="3055552001", name="Alice Jones")
    body = craft_outreach(lead, channel="sms")
    assert STOP_FOOTER in body
    assert len(body) <= 320
    # Name personalization should appear.
    assert "Alice" in body or "Miami" in body.title()


def test_craft_outreach_with_key_uses_sdk(monkeypatch, db_session):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    # Inject a fake anthropic module into sys.modules before the code imports it.
    class _FakeBlock:
        def __init__(self, text):
            self.text = text

    class _FakeResp:
        def __init__(self, text):
            self.content = [_FakeBlock(text)]

    class _FakeMessages:
        def create(self, **kwargs):
            assert kwargs["model"].startswith("claude-haiku")
            return _FakeResp("Hey Bob — Umuve routes jobs in Miami. Reply YES. Reply STOP to opt out.")

    class _FakeClient:
        def __init__(self, api_key):
            assert api_key == "sk-ant-test"
            self.messages = _FakeMessages()

    fake_mod = types.ModuleType("anthropic")
    fake_mod.Anthropic = _FakeClient
    monkeypatch.setitem(sys.modules, "anthropic", fake_mod)

    from partner_outreach_agent import craft_outreach, STOP_FOOTER

    lead = _make_lead(phone="3055552002", name="Bob")
    body = craft_outreach(lead, channel="sms")
    assert STOP_FOOTER in body
    assert len(body) <= 320
    assert "Hey Bob" in body


def test_craft_outreach_enforces_sms_max_length(monkeypatch, db_session):
    """If Claude overflows, we trim and still include the STOP footer."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    long_text = "A" * 500  # 500 chars, no footer
    class _FakeBlock:
        def __init__(self, text):
            self.text = text

    class _FakeResp:
        def __init__(self, text):
            self.content = [_FakeBlock(text)]

    class _FakeMessages:
        def create(self, **kwargs):
            return _FakeResp(long_text)

    class _FakeClient:
        def __init__(self, api_key):
            self.messages = _FakeMessages()

    fake_mod = types.ModuleType("anthropic")
    fake_mod.Anthropic = _FakeClient
    monkeypatch.setitem(sys.modules, "anthropic", fake_mod)

    # Re-import to pick up the fake.
    from partner_outreach_agent import craft_outreach, STOP_FOOTER

    lead = _make_lead(phone="3055552003", name="Long Boi")
    body = craft_outreach(lead, channel="sms")
    assert len(body) <= 320
    assert STOP_FOOTER in body


# ===========================================================================
# 3. Qualifier — keyword fallback + auto-transition.
# ===========================================================================
def test_qualifier_positive_keyword_fallback(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from partner_qualifier import qualify_response

    class _FakeAttempt:
        body = "Yes, interested in hearing more"
    res = qualify_response(_FakeAttempt())
    assert res["qualified"] is True
    assert res["sentiment"] == "positive"


def test_qualifier_stop_is_red_flag(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from partner_qualifier import qualify_response

    class _FakeAttempt:
        body = "STOP messaging me"
    res = qualify_response(_FakeAttempt())
    assert res["qualified"] is False
    assert res["sentiment"] == "red_flag"


def test_qualifier_auto_transition_to_qualified(monkeypatch, db_session):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from partner_qualifier import auto_qualify_and_transition

    lead = _make_lead(phone="3055553001", name="Carlos K", state="RESPONDED")
    attempt = OutreachAttempt(
        lead_id=lead.id, channel="sms", direction="in",
        body="Yes interested — tell me more",
    )
    db.session.add(attempt)
    db.session.commit()

    result = auto_qualify_and_transition(attempt, db.session)
    assert result["qualified"] is True
    assert result["transitioned"] is True

    lead_reloaded = db.session.get(DriverLead, lead.id)
    assert lead_reloaded.state == "QUALIFIED"

    quals = db.session.query(Qualification).filter_by(lead_id=lead.id).all()
    assert len(quals) == 1
    assert quals[0].consent_sms is True
    assert quals[0].consent_checkr is False


def test_qualifier_red_flag_rejects_lead(monkeypatch, db_session):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from partner_qualifier import auto_qualify_and_transition

    lead = _make_lead(phone="3055553002", name="Dan D", state="RESPONDED")
    attempt = OutreachAttempt(
        lead_id=lead.id, channel="sms", direction="in", body="Stop harassing me lawyer",
    )
    db.session.add(attempt)
    db.session.commit()

    result = auto_qualify_and_transition(attempt, db.session)
    assert result["sentiment"] == "red_flag"
    assert result["transitioned"] is True
    lead_reloaded = db.session.get(DriverLead, lead.id)
    assert lead_reloaded.state == "REJECTED"
    assert lead_reloaded.opted_out is True


# ===========================================================================
# 4. Checkr — 503 when key missing, webhook updates BackgroundCheck.
# ===========================================================================
def test_checkr_raises_not_configured_when_key_missing(monkeypatch, db_session):
    monkeypatch.delenv("CHECKR_API_KEY", raising=False)
    from partner_checkr import create_candidate, CheckrNotConfigured

    lead = _make_lead(phone="3055554001", name="Eva F")
    with pytest.raises(CheckrNotConfigured):
        create_candidate(lead)


def test_v1_bg_check_route_returns_503_when_checkr_missing(client, db_session, monkeypatch):
    monkeypatch.delenv("CHECKR_API_KEY", raising=False)
    lead = _make_lead(phone="3055554002", name="Frida G", state="QUALIFIED")
    db.session.add(Qualification(
        lead_id=lead.id, consent_checkr=True, consent_sms=True, ssn_last_4="1234",
    ))
    db.session.commit()

    r = client.post(
        "/partner/v1/leads/{}/bg-check/start".format(lead.id),
        json={}, headers=_svc_hdr(),
    )
    assert r.status_code == 503, r.get_json()
    assert "checkr" in (r.get_json().get("error") or "").lower()


def test_checkr_webhook_clear_transitions_to_onboarding(db_session):
    from partner_checkr import handle_webhook

    lead = _make_lead(phone="3055554003", name="Greg H", state="QUALIFIED")
    bg = BackgroundCheck(
        lead_id=lead.id,
        checkr_candidate_id="cand_123",
        status="pending",
    )
    db.session.add(bg)
    db.session.commit()

    result = handle_webhook({
        "type": "report.completed",
        "data": {"object": {
            "id": "rep_456",
            "candidate_id": "cand_123",
            "status": "clear",
        }},
    })
    assert result["matched"] is True
    assert result["transitioned"] is True

    lead_reloaded = db.session.get(DriverLead, lead.id)
    assert lead_reloaded.state == "ONBOARDING"
    bg_reloaded = db.session.get(BackgroundCheck, bg.id)
    assert bg_reloaded.status == "clear"
    assert bg_reloaded.checkr_report_id == "rep_456"


def test_checkr_webhook_consider_sets_adverse_action_timer(db_session):
    from partner_checkr import handle_webhook

    lead = _make_lead(phone="3055554004", name="Hank I", state="QUALIFIED")
    db.session.add(BackgroundCheck(
        lead_id=lead.id, checkr_candidate_id="cand_consider", status="pending",
    ))
    db.session.commit()

    handle_webhook({
        "type": "report.completed",
        "data": {"object": {
            "id": "rep_consider",
            "candidate_id": "cand_consider",
            "status": "consider",
        }},
    })
    bg = (
        db.session.query(BackgroundCheck)
        .filter_by(checkr_candidate_id="cand_consider").first()
    )
    assert bg.status == "consider"
    assert bg.adverse_action_due_at is not None
    # 5 business days ≈ at least 5 calendar days out.
    assert bg.adverse_action_due_at > _dt.datetime.utcnow() + _dt.timedelta(days=4)


def test_checkr_webhook_signature_verify(monkeypatch):
    from partner_checkr import verify_webhook
    import hashlib, hmac as _hmac

    monkeypatch.setenv("CHECKR_WEBHOOK_SECRET", "testsecret")
    body = b'{"type":"report.completed"}'
    good_sig = _hmac.new(b"testsecret", body, hashlib.sha256).hexdigest()
    assert verify_webhook(body, good_sig) is True
    assert verify_webhook(body, "nope") is False


# ===========================================================================
# 5. Stripe Connect — mocked SDK.
# ===========================================================================
def test_stripe_connect_raises_when_key_missing(monkeypatch, db_session):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    from partner_stripe_connect import create_connect_account, StripeNotConfigured

    lead = _make_lead(phone="3055555001", name="Ivy J")
    with pytest.raises(StripeNotConfigured):
        create_connect_account(lead)


def test_stripe_connect_start_onboarding_happy_path(monkeypatch, db_session):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake")

    # Patch the real stripe SDK inside the module. We need stripe.Account and
    # stripe.AccountLink. Use MagicMock with the right return shapes.
    import partner_stripe_connect as psc

    fake_stripe = mock.MagicMock()
    fake_stripe.Account.create.return_value = {"id": "acct_xyz"}
    fake_stripe.AccountLink.create.return_value = {"url": "https://connect.stripe.com/setup/xyz"}

    def _stripe_shim():
        return fake_stripe

    monkeypatch.setattr(psc, "_stripe", _stripe_shim)

    lead = _make_lead(phone="3055555002", name="Jack K", metro="miami")
    info = psc.start_onboarding(lead)
    assert info["account_id"] == "acct_xyz"
    assert info["url"].startswith("https://connect.stripe.com/")

    steps = db.session.query(OnboardingStep).filter_by(lead_id=lead.id).all()
    assert any(s.step == "stripe_link_sent" for s in steps)


def test_stripe_connect_webhook_charges_enabled_marks_step(db_session):
    from partner_stripe_connect import handle_webhook

    lead = _make_lead(phone="3055555003", name="Karen L", state="ONBOARDING")
    result = handle_webhook({
        "type": "account.updated",
        "data": {"object": {
            "id": "acct_abc",
            "charges_enabled": True,
            "metadata": {"lead_id": lead.id},
        }},
    })
    assert result["matched"] is True
    assert result["charges_enabled"] is True

    steps = (
        db.session.query(OnboardingStep)
        .filter_by(lead_id=lead.id, step="stripe_kyc_done").all()
    )
    assert len(steps) == 1
    assert steps[0].completed_at is not None


def test_stripe_connect_webhook_ignores_other_events():
    from partner_stripe_connect import handle_webhook
    result = handle_webhook({"type": "customer.created", "data": {"object": {}}})
    assert result["matched"] is False


# ===========================================================================
# 6. LangGraph pipeline — NEW -> OUTREACHED advance, terminal no-op.
# ===========================================================================
def test_pipeline_advances_new_to_outreached(monkeypatch, db_session):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)  # force template
    import routes.partner as partner_routes
    import partner_langgraph as lg
    import sms_service

    sent = []
    def fake_send(phone, msg):
        sent.append((phone, msg))
        return "SMfake"
    monkeypatch.setattr(sms_service, "send_sms", fake_send)

    lead = _make_lead(phone="3055556001", name="Laura M", state="NEW")
    result = lg.run_lead_pipeline(lead.id)
    assert result["action"] == "outreach_sent", result

    lead_r = db.session.get(DriverLead, lead.id)
    assert lead_r.state == "OUTREACHED"
    assert len(sent) == 1
    assert "STOP" in sent[0][1].upper()


def test_pipeline_terminal_state_noop(db_session):
    from partner_langgraph import run_lead_pipeline
    lead = _make_lead(phone="3055556002", name="Mike N", state="ACTIVE")
    result = run_lead_pipeline(lead.id)
    assert result["terminal"] is True
    assert result["action"] in ("terminal_state", "already_active")


def test_pipeline_missing_lead_returns_error(db_session):
    from partner_langgraph import run_lead_pipeline
    result = run_lead_pipeline("does-not-exist-id")
    assert result.get("error") == "not_found"


def test_pipeline_human_review_when_no_contact(db_session):
    from partner_langgraph import run_lead_pipeline

    # Make a lead with NO phone or email.
    lead = DriverLead(
        phone_e164=None,
        email=None,
        name_guess="No Contact",
        metro="miami",
        platform="craigslist",
        state="NEW",
        dedupe_hash="test-hash-nocontact",
    )
    db.session.add(lead)
    db.session.commit()

    result = run_lead_pipeline(lead.id)
    assert result["current_state"] == "HUMAN_REVIEW"

    lead_r = db.session.get(DriverLead, lead.id)
    assert lead_r.state == "HUMAN_REVIEW"


def test_pipeline_bg_check_blocked_without_consent(db_session):
    """QUALIFIED lead with no consent_checkr stays put."""
    from partner_langgraph import run_lead_pipeline
    lead = _make_lead(phone="3055556003", name="Olive P", state="QUALIFIED")
    # No Qualification row created.
    result = run_lead_pipeline(lead.id)
    assert result["action"] == "bg_blocked_no_consent"
    assert db.session.get(DriverLead, lead.id).state == "QUALIFIED"


# ===========================================================================
# 7. Route integration — /partner/v1/leads/<id>/outreach?ai=true
# ===========================================================================
def test_v1_outreach_ai_flag_uses_claude_module(client, db_session, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)  # template path
    sent = []
    import sms_service
    monkeypatch.setattr(sms_service, "send_sms", lambda p, m: sent.append((p, m)) or "SMai")

    lead = _make_lead(phone="3055557001", name="Pete Q")
    r = client.post(
        "/partner/v1/leads/{}/outreach?ai=true".format(lead.id),
        headers=_svc_hdr(),
    )
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["ai"] is True
    assert body["state"] == "OUTREACHED"
    assert "STOP" in body["body"].upper()


def test_v1_outreach_no_ai_flag_uses_stock_template(client, db_session, monkeypatch):
    import sms_service
    monkeypatch.setattr(sms_service, "send_sms", lambda p, m: "SMstock")

    lead = _make_lead(phone="3055557002", name="Quinn R")
    r = client.post(
        "/partner/v1/leads/{}/outreach".format(lead.id),
        headers=_svc_hdr(),
    )
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["ai"] is False
    assert "STOP" in body["body"].upper()


def test_v1_webhook_checkr_rejects_bad_signature(client, db_session):
    r = client.post(
        "/partner/v1/webhooks/checkr",
        data=b'{"type":"report.completed"}',
        headers={"X-Checkr-Signature": "garbage", "Content-Type": "application/json"},
    )
    assert r.status_code == 401


def test_v1_webhook_stripe_connect_unsigned_accepts_in_test(client, db_session):
    # With no STRIPE_CONNECT_WEBHOOK_SECRET set, we accept raw JSON.
    lead = _make_lead(phone="3055557003", name="Ryan S", state="ONBOARDING")
    r = client.post(
        "/partner/v1/webhooks/stripe-connect",
        json={
            "type": "account.updated",
            "data": {"object": {
                "id": "acct_web",
                "charges_enabled": True,
                "metadata": {"lead_id": lead.id},
            }},
        },
    )
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["charges_enabled"] is True


def test_v1_pipeline_tick_route(client, db_session, monkeypatch):
    import sms_service
    monkeypatch.setattr(sms_service, "send_sms", lambda p, m: "SMtick")

    lead = _make_lead(phone="3055557004", name="Sara T", state="NEW")
    r = client.post(
        "/partner/v1/pipeline/tick",
        json={"lead_id": lead.id},
        headers=_svc_hdr(),
    )
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["action"] == "outreach_sent"
    assert db.session.get(DriverLead, lead.id).state == "OUTREACHED"
