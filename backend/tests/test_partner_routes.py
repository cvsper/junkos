"""
Partner Acquisition Agent — route tests (spec 07 MVP).

Covers the 72h MVP compliance rails and state-machine happy paths:
  1. Service-token gate on ingest
  2. Ingest idempotency on dedupe_hash
  3. Outreach sends SMS + logs attempt + state NEW -> OUTREACHED
  4. Outreach blocked at 3 outbound in 48h (hard rail per §8)
  5. Twilio inbound matches phone -> state OUTREACHED -> RESPONDED
  6. Inbound 'STOP' flips opted_out + moves to REJECTED
  7. List leads filters by state / metro
  8. Qualify creates Qualification row + moves to QUALIFIED when complete
  9. Invalid state transition (NEW -> ACTIVE) rejected with 400
 10. Audit row created on every transition
"""

import os
import datetime as _dt
import pytest

# ---------------------------------------------------------------------------
# Env setup — MUST run before app import so partner.py sees the token.
# ---------------------------------------------------------------------------
os.environ.setdefault("PARTNER_SERVICE_TOKEN", "test-service-token-partner")

# Importing partner_models at module load registers the tables on db.metadata
# before conftest's `app` fixture calls _db.create_all().
import partner_models  # noqa: F401
from partner_models import (
    DriverLead,
    OutreachAttempt,
    Qualification,
    DriverOnboardingAudit,
)
from models import db


SERVICE_TOKEN = "test-service-token-partner"


# ---------------------------------------------------------------------------
# Ensure the partner blueprint is registered on the shared app. server.py
# does not import it (orchestrator merges that separately), so we wire it
# here so the test client can actually hit /partner/v1/* URLs.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def _register_partner_bp(app):
    from routes.partner import partner_bp

    if "partner" not in app.blueprints:
        app.register_blueprint(partner_bp)
    # create_all again now that partner_models is in metadata, in case the
    # app fixture ran before the import chain settled.
    with app.app_context():
        db.create_all()
    yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _svc_hdr():
    return {"X-Service-Token": SERVICE_TOKEN}


def _ingest(client, phone="3055551212", name="Bob Jones", metro="miami",
            external_ref="cl-123", source="craigslist"):
    return client.post(
        "/partner/v1/internal/leads/ingest",
        json={
            "source": source,
            "external_ref": external_ref,
            "phone": phone,
            "name_guess": name,
            "metro": metro,
            "raw": {"title": "Junk hauling $100/load"},
        },
        headers=_svc_hdr(),
    )


# ---------------------------------------------------------------------------
# 1. Service token required on ingest
# ---------------------------------------------------------------------------
def test_ingest_requires_service_token(client, db_session):
    resp = client.post(
        "/partner/v1/internal/leads/ingest",
        json={"source": "craigslist", "phone": "3055550000"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 2. Ingest creates lead, idempotent on dedupe_hash
# ---------------------------------------------------------------------------
def test_ingest_is_idempotent_on_dedupe_hash(client, db_session):
    r1 = _ingest(client, phone="3055551111", name="Alice Smith")
    assert r1.status_code == 201, r1.get_json()
    body1 = r1.get_json()
    assert body1["state"] == "NEW"
    assert body1["deduped"] is False

    # Second ingest with same phone+name should return the same lead id.
    r2 = _ingest(client, phone="(305) 555-1111", name="Alice Smith")
    assert r2.status_code == 200, r2.get_json()
    body2 = r2.get_json()
    assert body2["lead_id"] == body1["lead_id"]
    assert body2["deduped"] is True

    # Only one row exists.
    rows = db.session.query(DriverLead).filter_by(phone_e164="+13055551111").all()
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# 3. Outreach sends SMS, records attempt, moves NEW -> OUTREACHED
# ---------------------------------------------------------------------------
def test_outreach_sends_sms_and_transitions_state(client, db_session, monkeypatch):
    sent = []

    def fake_send(phone, msg):
        sent.append((phone, msg))
        return "SMxxx123"

    # Patch in the partner routes module where it's bound.
    import routes.partner as partner_routes
    monkeypatch.setattr(partner_routes.sms_service, "send_sms", fake_send)

    r1 = _ingest(client, phone="3055552222", name="Carl Ray")
    lead_id = r1.get_json()["lead_id"]

    r2 = client.post(
        "/partner/v1/internal/leads/{}/outreach".format(lead_id),
        headers=_svc_hdr(),
    )
    assert r2.status_code == 200, r2.get_json()
    body = r2.get_json()
    assert body["state"] == "OUTREACHED"
    assert body["sid"] == "SMxxx123"
    assert len(sent) == 1
    phone, msg = sent[0]
    assert phone == "+13055552222"
    assert "STOP" in msg.upper()  # compliance rail: opt-out baked into template

    attempts = db.session.query(OutreachAttempt).filter_by(lead_id=lead_id).all()
    assert len(attempts) == 1
    assert attempts[0].direction == "out"


# ---------------------------------------------------------------------------
# 4. Outreach blocked after 3 outbound in 48h (hard rail)
# ---------------------------------------------------------------------------
def test_outreach_rate_limited_after_three_in_48h(client, db_session, monkeypatch):
    import routes.partner as partner_routes
    monkeypatch.setattr(partner_routes.sms_service, "send_sms", lambda p, m: "SM1")

    r1 = _ingest(client, phone="3055553333", name="Dan Drake")
    lead_id = r1.get_json()["lead_id"]

    # Seed 3 recent outbound attempts.
    for _ in range(3):
        db.session.add(OutreachAttempt(
            lead_id=lead_id, channel="sms", direction="out", body="hi",
        ))
    db.session.commit()

    r = client.post(
        "/partner/v1/internal/leads/{}/outreach".format(lead_id),
        headers=_svc_hdr(),
    )
    assert r.status_code == 429, r.get_json()


# ---------------------------------------------------------------------------
# 5. Twilio inbound matches phone, records response, OUTREACHED -> RESPONDED
# ---------------------------------------------------------------------------
def test_twilio_inbound_moves_outreached_to_responded(client, db_session):
    r1 = _ingest(client, phone="3055554444", name="Eve Evans")
    lead_id = r1.get_json()["lead_id"]

    # Flip to OUTREACHED manually (outreach endpoint would do this, but keep
    # this test focused on inbound handling).
    lead = db.session.get(DriverLead, lead_id)
    lead.state = "OUTREACHED"
    db.session.commit()

    r = client.post(
        "/partner/v1/internal/twilio/inbound",
        data={"From": "+13055554444", "Body": "Yes interested"},
        headers=_svc_hdr(),
    )
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["state"] == "RESPONDED"
    assert body["opted_out"] is False

    attempts = db.session.query(OutreachAttempt).filter_by(
        lead_id=lead_id, direction="in"
    ).all()
    assert len(attempts) == 1
    assert "Yes" in (attempts[0].body or "")


# ---------------------------------------------------------------------------
# 6. Inbound 'STOP' marks opted_out + REJECTED
# ---------------------------------------------------------------------------
def test_twilio_inbound_stop_opts_out_and_rejects(client, db_session):
    r1 = _ingest(client, phone="3055555555", name="Frank Green")
    lead_id = r1.get_json()["lead_id"]
    lead = db.session.get(DriverLead, lead_id)
    lead.state = "OUTREACHED"
    db.session.commit()

    r = client.post(
        "/partner/v1/internal/twilio/inbound",
        data={"From": "+13055555555", "Body": "STOP"},
        headers=_svc_hdr(),
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["state"] == "REJECTED"
    assert body["opted_out"] is True

    lead = db.session.get(DriverLead, lead_id)
    assert lead.opted_out is True
    assert lead.state == "REJECTED"


# ---------------------------------------------------------------------------
# 7. List leads filters by state and metro
# ---------------------------------------------------------------------------
def test_list_leads_filters_by_state_and_metro(client, db_session):
    _ingest(client, phone="3055556660", name="G One", metro="miami",
            external_ref="cl-a1")
    _ingest(client, phone="3055556661", name="G Two", metro="ftl",
            external_ref="cl-a2")
    # Move the second to REJECTED.
    ftl_lead = db.session.query(DriverLead).filter_by(metro="ftl").first()
    ftl_lead.state = "REJECTED"
    db.session.commit()

    r_all = client.get("/partner/v1/leads", headers=_svc_hdr())
    assert r_all.status_code == 200
    assert r_all.get_json()["total"] >= 2

    r_miami = client.get("/partner/v1/leads?metro=miami", headers=_svc_hdr())
    data = r_miami.get_json()
    assert all(l["metro"] == "miami" for l in data["leads"])

    r_new = client.get("/partner/v1/leads?state=NEW&metro=miami", headers=_svc_hdr())
    new_data = r_new.get_json()
    assert all(l["state"] == "NEW" and l["metro"] == "miami" for l in new_data["leads"])


# ---------------------------------------------------------------------------
# 8. Qualify records Qualification + moves RESPONDED -> QUALIFIED
# ---------------------------------------------------------------------------
def test_qualify_transitions_to_qualified_when_complete(client, db_session):
    r1 = _ingest(client, phone="3055557777", name="Hank Irving")
    lead_id = r1.get_json()["lead_id"]
    lead = db.session.get(DriverLead, lead_id)
    lead.state = "RESPONDED"
    db.session.commit()

    payload = {
        "has_truck": True,
        "truck_type": "pickup",
        "has_insurance": True,
        "has_license": True,
        "past_hauling_years": 3,
        "self_reported_availability_hours": 30,
        "consent_checkr": True,
        "consent_sms": True,
        "ssn_last_4": "1234",
    }
    r = client.post(
        "/partner/v1/leads/{}/qualify".format(lead_id),
        json=payload,
        headers=_svc_hdr(),
    )
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body["qualified"] is True
    assert body["state"] == "QUALIFIED"

    quals = db.session.query(Qualification).filter_by(lead_id=lead_id).all()
    assert len(quals) == 1
    assert quals[0].has_truck is True
    assert quals[0].consent_checkr is True


# ---------------------------------------------------------------------------
# 9. Manual state transition rejects invalid transitions
# ---------------------------------------------------------------------------
def test_invalid_state_transition_rejected(client, db_session):
    r1 = _ingest(client, phone="3055558888", name="Ivy Jones")
    lead_id = r1.get_json()["lead_id"]

    # NEW -> ACTIVE is not on the whitelist.
    r = client.post(
        "/partner/v1/leads/{}/state".format(lead_id),
        json={"to_state": "ACTIVE"},
        headers=_svc_hdr(),
    )
    assert r.status_code == 400
    body = r.get_json()
    assert body["from"] == "NEW"
    assert body["to"] == "ACTIVE"

    # Lead state unchanged.
    lead = db.session.get(DriverLead, lead_id)
    assert lead.state == "NEW"


# ---------------------------------------------------------------------------
# 10. Every state transition writes an audit row
# ---------------------------------------------------------------------------
def test_state_transition_writes_audit_row(client, db_session):
    r1 = _ingest(client, phone="3055559999", name="Jane Kilo")
    lead_id = r1.get_json()["lead_id"]

    pre_count = db.session.query(DriverOnboardingAudit).filter_by(
        lead_id=lead_id
    ).count()

    r = client.post(
        "/partner/v1/leads/{}/state".format(lead_id),
        json={"to_state": "OUTREACHED", "actor": "ops-test", "reason": "manual"},
        headers=_svc_hdr(),
    )
    assert r.status_code == 200, r.get_json()

    post_count = db.session.query(DriverOnboardingAudit).filter_by(
        lead_id=lead_id
    ).count()
    assert post_count == pre_count + 1

    latest = (
        db.session.query(DriverOnboardingAudit)
        .filter_by(lead_id=lead_id)
        .order_by(DriverOnboardingAudit.created_at.desc())
        .first()
    )
    assert latest.before_state == "NEW"
    assert latest.after_state == "OUTREACHED"
    assert latest.actor == "ops-test"
    assert latest.action == "lead.transition"
