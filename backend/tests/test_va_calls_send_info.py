"""Tests for the Call Desk info-pack sender (/api/va/calls/send-info).

The endpoint exists for the gatekeeper flow: a receptionist answers, says
"send us something for the manager", and hands over a cell number or an
email address. Bodies are server-side templates — the client only ever
supplies the destination.
"""

import os
from unittest import mock

import pytest

from models import db, CallProspect


@pytest.fixture(autouse=True)
def passcode_env():
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code"}):
        yield


@pytest.fixture()
def prospect(app):
    p = CallProspect(tier=1, category="property management",
                     company="Test Property Co", phone="(561) 555-0100",
                     phone_digits="5615550100", city="West Palm Beach",
                     contact_name="Pat Smith")
    db.session.add(p)
    db.session.commit()
    yield p
    db.session.delete(p)
    db.session.commit()


def _post(client, payload):
    base = {"code": "test-code", "va_name": "Tracy"}
    base.update(payload)
    return client.post("/api/va/calls/send-info", json=base)


def test_bad_passcode_rejected(client, prospect):
    resp = client.post("/api/va/calls/send-info",
                       json={"code": "wrong", "prospect_id": prospect.id,
                             "channel": "text"})
    assert resp.status_code == 401


def test_unknown_channel_rejected(client, prospect):
    resp = _post(client, {"prospect_id": prospect.id, "channel": "carrier_pigeon"})
    assert resp.status_code == 400


def test_unknown_prospect_404(client):
    resp = _post(client, {"prospect_id": "nope", "channel": "text"})
    assert resp.status_code == 404


def test_text_defaults_to_prospect_number(client, prospect):
    with mock.patch("sms_service.send_sms", return_value="SM" + "a" * 32) as send:
        resp = _post(client, {"prospect_id": prospect.id, "channel": "text"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] and body["sid"].startswith("SM")
    to_phone, text = send.call_args[0]
    assert to_phone == "+15615550100"
    assert "goumuve.com/partners" in text
    assert "Tracy" in text
    assert "STOP" in text
    db.session.refresh(prospect)
    assert prospect.last_texted_at is not None


def test_text_to_alternate_number(client, prospect):
    """Receptionist gives the boss's cell — the text goes there instead."""
    with mock.patch("sms_service.send_sms", return_value="SM" + "b" * 32) as send:
        resp = _post(client, {"prospect_id": prospect.id, "channel": "text",
                              "to": "(954) 555-0199"})
    assert resp.status_code == 200
    assert send.call_args[0][0] == "+19545550199"


def test_text_invalid_number_rejected(client, prospect):
    resp = _post(client, {"prospect_id": prospect.id, "channel": "text",
                          "to": "12345"})
    assert resp.status_code == 400


def test_text_provider_failure_is_502(client, prospect):
    with mock.patch("sms_service.send_sms", return_value=None):
        resp = _post(client, {"prospect_id": prospect.id, "channel": "text"})
    assert resp.status_code == 502


def test_email_sends_partner_info_and_saves_address(client, prospect):
    with mock.patch("notifications._send_email_sync", return_value="ok") as send:
        resp = _post(client, {"prospect_id": prospect.id, "channel": "email",
                              "to": "Boss@Example.com"})
    assert resp.status_code == 200
    assert resp.get_json()["to"] == "boss@example.com"
    to_email, subject, html = send.call_args[0][:3]
    assert to_email == "boss@example.com"
    assert "Test Property Co" in subject
    assert "goumuve.com/partners" in html
    assert "pass this along" in html          # forwardable framing
    db.session.refresh(prospect)
    assert prospect.email == "boss@example.com"
    assert prospect.last_emailed_at is not None


def test_email_invalid_address_rejected(client, prospect):
    resp = _post(client, {"prospect_id": prospect.id, "channel": "email",
                          "to": "not-an-email"})
    assert resp.status_code == 400


def test_email_unconfigured_is_503(client, prospect):
    with mock.patch("notifications._send_email_sync", return_value=None):
        resp = _post(client, {"prospect_id": prospect.id, "channel": "email",
                              "to": "boss@example.com"})
    assert resp.status_code == 503


def test_card_payload_includes_saved_email(client, prospect):
    prospect.email = "saved@example.com"
    db.session.commit()
    resp = client.post("/api/va/calls/get",
                       json={"code": "test-code", "prospect_id": prospect.id})
    assert resp.status_code == 200
    assert resp.get_json()["card"]["email"] == "saved@example.com"


# ---------------------------------------------------------------------------
# Decision-maker capture (/api/va/calls/contact)
# ---------------------------------------------------------------------------

def test_contact_saves_decision_maker(client, prospect):
    resp = _post_contact(client, {"prospect_id": prospect.id,
                                  "contact_name": "Maria Lopez",
                                  "direct_phone": "(954) 555-0142",
                                  "email": "Maria@Example.com"})
    assert resp.status_code == 200
    card = resp.get_json()["card"]
    assert card["contact_name"] == "Maria Lopez"
    assert card["direct_phone"] == "(954) 555-0142"
    assert card["direct_tel"] == "tel:+19545550142"
    assert card["email"] == "maria@example.com"
    db.session.refresh(prospect)
    assert prospect.direct_phone == "(954) 555-0142"


def test_contact_empty_values_clear_fields(client, prospect):
    prospect.contact_name = "Old Name"
    prospect.direct_phone = "9545550142"
    db.session.commit()
    resp = _post_contact(client, {"prospect_id": prospect.id,
                                  "contact_name": "", "direct_phone": ""})
    assert resp.status_code == 200
    db.session.refresh(prospect)
    assert prospect.contact_name is None
    assert prospect.direct_phone is None


def test_contact_absent_keys_leave_fields_alone(client, prospect):
    prospect.email = "keep@example.com"
    db.session.commit()
    resp = _post_contact(client, {"prospect_id": prospect.id,
                                  "contact_name": "Just A Name"})
    assert resp.status_code == 200
    db.session.refresh(prospect)
    assert prospect.email == "keep@example.com"


def test_contact_bad_direct_phone_rejected(client, prospect):
    resp = _post_contact(client, {"prospect_id": prospect.id,
                                  "direct_phone": "123"})
    assert resp.status_code == 400


def test_contact_bad_email_rejected(client, prospect):
    resp = _post_contact(client, {"prospect_id": prospect.id,
                                  "email": "nope"})
    assert resp.status_code == 400


def test_contact_bad_passcode_rejected(client, prospect):
    resp = client.post("/api/va/calls/contact",
                       json={"code": "wrong", "prospect_id": prospect.id,
                             "contact_name": "X"})
    assert resp.status_code == 401


def _post_contact(client, payload):
    base = {"code": "test-code", "va_name": "Tracy"}
    base.update(payload)
    return client.post("/api/va/calls/contact", json=base)
