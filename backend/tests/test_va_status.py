"""Tests for the VA hub delivery-status endpoint (/api/va/status).

Twilio reports "sent" the moment a carrier accepts a message; landlines and
filtered numbers fail after that. The status endpoint is what lets the VA
tool surface the real outcome instead of a false "sent".
"""

import os
from unittest import mock

import pytest

VALID_SID = "SM" + "a" * 32


class FakeMsg:
    def __init__(self, status, error_code=None):
        self.status = status
        self.error_code = error_code


class FakeClient:
    def __init__(self, msg):
        self._msg = msg

    def messages(self, sid):
        fetcher = mock.Mock()
        fetcher.fetch.return_value = self._msg
        return fetcher


@pytest.fixture(autouse=True)
def passcode_env():
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code"}):
        yield


def _post(client, payload):
    return client.post("/api/va/status", json=payload)


def test_rejects_bad_passcode(client):
    resp = _post(client, {"passcode": "wrong", "sid": VALID_SID})
    assert resp.status_code == 401


def test_rejects_malformed_sid(client):
    resp = _post(client, {"passcode": "test-code", "sid": "not-a-sid"})
    assert resp.status_code == 400


def test_delivered_status_passes_through(client):
    with mock.patch("sms_service._get_twilio", return_value=FakeClient(FakeMsg("delivered"))):
        resp = _post(client, {"passcode": "test-code", "sid": VALID_SID})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["status"] == "delivered"
    assert "reason" not in body


def test_landline_failure_gets_human_reason(client):
    msg = FakeMsg("undelivered", error_code=30006)
    with mock.patch("sms_service._get_twilio", return_value=FakeClient(msg)):
        resp = _post(client, {"passcode": "test-code", "sid": VALID_SID})
    body = resp.get_json()
    assert body["status"] == "undelivered"
    assert "landline" in body["reason"].lower()


def test_unknown_error_code_gets_generic_reason(client):
    msg = FakeMsg("failed", error_code=99999)
    with mock.patch("sms_service._get_twilio", return_value=FakeClient(msg)):
        resp = _post(client, {"passcode": "test-code", "sid": VALID_SID})
    body = resp.get_json()
    assert body["status"] == "failed"
    assert body["reason"]


def test_unconfigured_twilio_returns_503(client):
    with mock.patch("sms_service._get_twilio", return_value=None):
        resp = _post(client, {"passcode": "test-code", "sid": VALID_SID})
    assert resp.status_code == 503
