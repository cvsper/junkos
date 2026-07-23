"""Tests for the VA email template whitelist (/api/va/email).

The setup template exists for signed-up YESes whose phone can't receive
texts (landline) — the setup steps go by email instead.
"""

import os
from unittest import mock

import pytest


@pytest.fixture(autouse=True)
def passcode_env():
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code"}):
        yield


def _post(client, payload):
    base = {"passcode": "test-code", "va_name": "Tracy", "email": "op@example.com"}
    base.update(payload)
    return client.post("/api/va/email", json=base)


def test_unknown_template_rejected(client):
    resp = _post(client, {"template": "phishing"})
    assert resp.status_code == 400


def test_setup_template_sends_setup_email(client):
    sent = {}

    def fake_send(to, subject, html, from_override=None):
        sent.update(to=to, subject=subject, html=html)
        return {"id": "fake"}

    with mock.patch("notifications._send_email_sync", side_effect=fake_send):
        resp = _post(client, {"template": "setup", "company": "Dr. Billiards",
                              "name": "Doc"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["template"] == "setup"
    assert "setup link" in body["subject"].lower()
    assert "Dr. Billiards" in body["subject"]
    # the email must mirror the optext SMS steps
    assert "goumuve.com/operators" in sent["html"]
    assert "apps.apple.com/app/id6759131650" in sent["html"]
    assert "Go Online" in sent["html"]


def test_default_template_is_intro(client):
    sent = {}

    def fake_send(to, subject, html, from_override=None):
        sent.update(subject=subject, html=html)
        return {"id": "fake"}

    with mock.patch("notifications._send_email_sync", side_effect=fake_send):
        resp = _post(client, {"company": "Gator Dumpster"})
    assert resp.status_code == 200
    assert resp.get_json()["template"] == "intro"
    assert "Paying junk-removal jobs" in sent["subject"]


def test_setup_email_page_has_tabs(client):
    resp = client.get("/va/email")
    html = resp.get_data(as_text=True)
    assert 'id="etab-setup"' in html
    assert 'id="etab-intro"' in html


def test_email_js_sends_template(client):
    js = client.get("/va/email.js").get_data(as_text=True)
    assert "template: current" in js
    assert '"setup"' in js or "'setup'" in js
