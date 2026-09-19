"""The iOS desk app needs the same Voice token as the browser plus a push
credential, or it cannot ring while the phone is locked — which is the only
reason to build it. These pin the token shape for both platforms."""
import base64, json, os
from unittest import mock

import pytest


ENV = {"TRIXIE_ASSISTANT_PASSCODE": "test-code", "TWILIO_ACCOUNT_SID": "AC" + "0" * 32,
       "TWILIO_API_KEY_SID": "SK" + "0" * 32, "TWILIO_API_KEY_SECRET": "s" * 32,
       "TWILIO_TWIML_APP_SID": "AP" + "0" * 32, "DESK_TWILIO_NUMBER": "+15617824350"}


def _grant(jwt):
    body = jwt.split(".")[1]
    body += "=" * (-len(body) % 4)
    return json.loads(base64.urlsafe_b64decode(body))["grants"]["voice"]


def _token(client, **body):
    return client.post("/api/va/desk/token",
                       json=dict({"code": "test-code", "va_name": "Tracy"}, **body)).get_json()


def test_browser_token_is_unchanged(client):
    with mock.patch.dict(os.environ, ENV):
        r = _token(client)
    assert r["enabled"] and r["platform"] == "web" and "push" not in r
    assert "push_credential_sid" not in _grant(r["token"])
    assert r["identity"].startswith("desk")


def test_ios_token_carries_the_push_credential(client):
    with mock.patch.dict(os.environ, dict(ENV, TWILIO_IOS_PUSH_CREDENTIAL_SID="CR" + "1" * 32)):
        r = _token(client, platform="ios")
    assert r["enabled"] and r["platform"] == "ios" and r["push"] is True
    assert _grant(r["token"])["push_credential_sid"] == "CR" + "1" * 32
    assert _grant(r["token"])["incoming"] == {"allow": True}


def test_ios_token_without_push_says_so_instead_of_pretending(client):
    with mock.patch.dict(os.environ, dict(ENV, TWILIO_IOS_PUSH_CREDENTIAL_SID="")):
        r = _token(client, platform="ios")
    assert r["enabled"] and r["push"] is False
    assert "will not ring while locked" in r["push_reason"]
    assert "push_credential_sid" not in _grant(r["token"])


def test_ios_uses_the_same_identity_the_inbound_dial_rings(client):
    """One identity per VA; the app and the browser are the same 'desk-tracy'."""
    with mock.patch.dict(os.environ, ENV):
        web = _token(client)["identity"]; ios = _token(client, platform="ios")["identity"]
    assert web == ios
