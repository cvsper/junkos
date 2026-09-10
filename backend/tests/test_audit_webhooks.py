"""Audit F23 — non-core webhooks must fail CLOSED in production.

Four webhooks used to accept unsigned input whenever their secret was absent
(or the validator raised): Twilio inbound SMS, the Vapi tool/webhook pair, the
Meta Lead Ads webhook, and the portal Stripe billing webhook.

These tests pin both halves of the policy:
  * production + missing secret  -> rejected (401/403)
  * development + missing secret -> still accepted (local dev / tests)
and that a repeated provider event id is ignored exactly once.
"""

import json
import os
from unittest import mock

import pytest

from models import db, Org
from models_webhooks import ProviderEvent
import webhook_guard


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
NO_SECRETS = {
    "TWILIO_AUTH_TOKEN": "",
    "VAPI_SERVER_SECRET": "",
    "META_APP_SECRET": "",
    "META_VERIFY_TOKEN": "",
    "STRIPE_WEBHOOK_SECRET_PORTAL": "",
}


def _prod(**extra):
    env = dict(NO_SECRETS)
    env["FLASK_ENV"] = "production"
    env.update(extra)
    webhook_guard.reset_warnings()
    return mock.patch.dict(os.environ, env)


def _dev(**extra):
    env = dict(NO_SECRETS)
    env["FLASK_ENV"] = "development"
    env.update(extra)
    webhook_guard.reset_warnings()
    return mock.patch.dict(os.environ, env)


def _sms(client, sid="SM-test-1", body="JOBS", frm="+15615551234"):
    return client.post("/api/sms/inbound", data={
        "From": frm, "Body": body, "NumMedia": "0", "MessageSid": sid,
    })


# --------------------------------------------------------------------------
# 1. Twilio inbound SMS  (also guards desk_line.py, which reuses the helper)
# --------------------------------------------------------------------------
def test_twilio_webhook_rejects_in_production_without_auth_token(client):
    with _prod():
        r = _sms(client)
    assert r.status_code == 403


def test_twilio_webhook_ignores_validate_off_escape_hatch_in_production(client):
    """SMS_WEBHOOK_VALIDATE=off must not re-open the hole in production."""
    with _prod(SMS_WEBHOOK_VALIDATE="off"):
        r = _sms(client)
    assert r.status_code == 403


def test_twilio_webhook_rejects_in_production_on_bad_signature(client):
    with _prod(TWILIO_AUTH_TOKEN="tok"):
        r = _sms(client)
    assert r.status_code == 403


def test_twilio_webhook_rejects_in_production_when_validator_raises(client):
    with _prod(TWILIO_AUTH_TOKEN="tok"), \
            mock.patch("twilio.request_validator.RequestValidator",
                       side_effect=RuntimeError("boom")):
        r = _sms(client)
    assert r.status_code == 403


def test_twilio_webhook_allows_in_development_without_auth_token(client):
    with _dev(), mock.patch("sms_service.send_sms"):
        r = _sms(client)
    assert r.status_code == 200


def test_twilio_webhook_allows_in_development_when_validator_raises(client):
    with _dev(TWILIO_AUTH_TOKEN="tok"), mock.patch("sms_service.send_sms"), \
            mock.patch("twilio.request_validator.RequestValidator",
                       side_effect=RuntimeError("boom")):
        r = _sms(client)
    assert r.status_code == 200


def test_duplicate_twilio_message_sid_is_ignored(client, db_session):
    """A Twilio redelivery must not register the hauler (or quote) twice."""
    from models import Contractor

    with _dev(), mock.patch("sms_service.send_sms"):
        first = _sms(client, sid="SM-dup", frm="+15615559999")
        second = _sms(client, sid="SM-dup", frm="+15615559999")

    assert first.status_code == 200 and second.status_code == 200
    assert b"paid-jobs list" in first.data       # the real handler ran once
    assert b"paid-jobs list" not in second.data  # the retry was a no-op
    assert ProviderEvent.query.filter_by(provider="twilio",
                                         event_id="SM-dup").count() == 1
    # The keyword signup ran once, so exactly one hauler exists.
    assert Contractor.query.count() == 1


# --------------------------------------------------------------------------
# 2. Vapi tool + webhook
# --------------------------------------------------------------------------
TOOL_PAYLOAD = {"message": {"type": "tool-calls", "toolCallList": []}}


def test_vapi_tool_rejects_in_production_without_secret(client):
    with _prod():
        r = client.post("/api/vapi/tool", json=TOOL_PAYLOAD)
    assert r.status_code == 401


def test_vapi_webhook_rejects_in_production_without_secret(client):
    with _prod():
        r = client.post("/api/vapi/webhook",
                        json={"message": {"type": "status-update"}})
    assert r.status_code == 401


def test_vapi_rejects_in_production_on_wrong_secret(client):
    with _prod(VAPI_SERVER_SECRET="right"):
        r = client.post("/api/vapi/tool", json=TOOL_PAYLOAD,
                        headers={"X-Vapi-Secret": "wrong"})
    assert r.status_code == 401


def test_vapi_accepts_matching_secret_in_production(client):
    with _prod(VAPI_SERVER_SECRET="right"):
        r = client.post("/api/vapi/tool", json=TOOL_PAYLOAD,
                        headers={"X-Vapi-Secret": "right"})
    assert r.status_code == 200


def test_vapi_tool_allows_in_development_without_secret(client):
    with _dev():
        r = client.post("/api/vapi/tool", json=TOOL_PAYLOAD)
    assert r.status_code == 200


def test_duplicate_vapi_call_report_is_ignored(client, db_session):
    payload = {"message": {"type": "end-of-call-report",
                           "call": {"id": "call-abc"}}}
    with _dev(), mock.patch("routes.vapi._handle_end_of_call_report") as handler:
        first = client.post("/api/vapi/webhook", json=payload)
        second = client.post("/api/vapi/webhook", json=payload)

    assert first.status_code == second.status_code == 200
    assert handler.call_count == 1
    assert second.get_json().get("duplicate") is True
    assert ProviderEvent.query.filter_by(provider="vapi",
                                         event_id="call-abc").count() == 1


# --------------------------------------------------------------------------
# 3. Meta Lead Ads webhook
# --------------------------------------------------------------------------
LEAD_PAYLOAD = {"entry": [{"changes": [
    {"field": "leadgen", "value": {"leadgen_id": "lead-1"}}]}]}


def test_meta_leads_rejects_in_production_without_app_secret(client):
    with _prod():
        r = client.post("/api/vapi/meta-leads", json=LEAD_PAYLOAD)
    assert r.status_code == 401


def test_meta_leads_rejects_in_production_on_bad_signature(client):
    with _prod(META_APP_SECRET="s3cret"):
        r = client.post("/api/vapi/meta-leads", json=LEAD_PAYLOAD,
                        headers={"X-Hub-Signature-256": "sha256=nope"})
    assert r.status_code == 403


def test_meta_leads_allows_in_development_without_app_secret(client, db_session):
    with _dev(), mock.patch("routes.vapi._process_meta_lead"):
        r = client.post("/api/vapi/meta-leads", json=LEAD_PAYLOAD)
    assert r.status_code == 200


def test_duplicate_meta_leadgen_id_is_ignored(client, db_session):
    with _dev(), mock.patch("routes.vapi._process_meta_lead") as proc:
        client.post("/api/vapi/meta-leads", json=LEAD_PAYLOAD)
        client.post("/api/vapi/meta-leads", json=LEAD_PAYLOAD)
    # The lead is fetched + called once, no matter how often Meta redelivers.
    assert proc.call_count <= 1
    assert ProviderEvent.query.filter_by(provider="meta_leads",
                                         event_id="lead-1").count() == 1


def test_meta_verify_challenge_still_refused_without_token(client):
    with _dev():
        r = client.get("/api/vapi/meta-leads?hub.mode=subscribe"
                       "&hub.verify_token=x&hub.challenge=123")
    assert r.status_code == 403


# --------------------------------------------------------------------------
# 4. Portal Stripe billing webhook
# --------------------------------------------------------------------------
def _org(**kw):
    org = Org(name=kw.get("name", "Webhook Co"), slug=kw.get("slug", "webhook-co"),
              billing_email="wh@x.example", tier="pro", status="trial")
    db.session.add(org)
    db.session.commit()
    return org


def _stripe_event(event_id, org_id):
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {"object": {
            "metadata": {"org_id": org_id, "tier": "pro"},
            "customer": "cus_test", "subscription": "sub_test",
        }},
    }


def test_portal_billing_webhook_rejects_in_production_without_secret(client, db_session):
    org = _org()
    with _prod():
        r = client.post("/portal/v1/billing/webhook",
                        data=json.dumps(_stripe_event("evt_1", org.id)),
                        content_type="application/json")
    assert r.status_code == 401
    db.session.refresh(org)
    assert org.status == "trial"          # unsigned payload changed nothing


def test_portal_billing_webhook_allows_in_development_without_secret(client, db_session):
    org = _org(slug="webhook-dev-co")
    with _dev():
        r = client.post("/portal/v1/billing/webhook",
                        data=json.dumps(_stripe_event("evt_2", org.id)),
                        content_type="application/json")
    assert r.status_code == 200
    db.session.refresh(org)
    assert org.status == "active"


def test_duplicate_stripe_event_id_is_ignored(client, db_session):
    org = _org(slug="webhook-dup-co")
    payload = json.dumps(_stripe_event("evt_dup", org.id))
    with _dev():
        first = client.post("/portal/v1/billing/webhook", data=payload,
                            content_type="application/json")
        # Org churns between deliveries; a replay must not resurrect it.
        org.status = "churned"
        db.session.commit()
        second = client.post("/portal/v1/billing/webhook", data=payload,
                             content_type="application/json")

    assert first.status_code == second.status_code == 200
    assert second.get_json().get("duplicate") is True
    db.session.refresh(org)
    assert org.status == "churned"
    assert ProviderEvent.query.filter_by(provider="stripe_portal",
                                         event_id="evt_dup").count() == 1


# --------------------------------------------------------------------------
# 5. Readiness probe
# --------------------------------------------------------------------------
def test_webhook_secrets_ready_reports_every_guarded_secret():
    from webhook_guard import webhook_secrets_ready, WEBHOOK_SECRET_ENV

    with mock.patch.dict(os.environ, dict(NO_SECRETS, STRIPE_WEBHOOK_SECRET="")):
        ready = webhook_secrets_ready()
    assert set(ready) == set(WEBHOOK_SECRET_ENV)
    assert all(v is False for v in ready.values())

    with mock.patch.dict(os.environ, dict(NO_SECRETS, VAPI_SERVER_SECRET="set")):
        ready = webhook_secrets_ready()
    assert ready["vapi"] is True
    assert ready["twilio"] is False


def test_record_provider_event_is_true_once_then_false(db_session):
    from webhook_guard import record_provider_event

    assert record_provider_event("twilio", "SM-once") is True
    assert record_provider_event("twilio", "SM-once") is False
    # Different provider, same id -> a genuinely different event.
    assert record_provider_event("vapi", "SM-once") is True
    # No id supplied -> nothing to dedupe on, always process.
    assert record_provider_event("twilio", "") is True
