"""E2E tests for the B2B agreement e-signature flow (routes/agreements.py)."""
import pytest

from models import db, Agreement

PASSCODE = "test-code-123"


@pytest.fixture(autouse=True)
def _passcode_env(monkeypatch):
    monkeypatch.setenv("TRIXIE_ASSISTANT_PASSCODE", PASSCODE)


def _create(client, **overrides):
    payload = {
        "passcode": PASSCODE,
        "client_company": "Rivera Demolition LLC",
        "client_name": "Marcos Rivera",
        "client_email": "marcos@example.com",
        "client_phone": "(561) 555-0100",
    }
    payload.update(overrides)
    return client.post("/api/agreements/create", json=payload)


class TestCreate:
    def test_create_returns_sign_url(self, client):
        resp = _create(client)
        assert resp.status_code == 201
        body = resp.get_json()
        assert "/sign/" in body["sign_url"]
        assert body["agreement"]["status"] == "sent"

    def test_bad_passcode_fails_closed(self, client):
        resp = _create(client, passcode="wrong")
        assert resp.status_code == 403

    def test_missing_passcode_env_fails_closed(self, client, monkeypatch):
        monkeypatch.delenv("TRIXIE_ASSISTANT_PASSCODE")
        resp = _create(client)
        assert resp.status_code == 403

    def test_requires_valid_email(self, client):
        resp = _create(client, client_email="not-an-email")
        assert resp.status_code == 400


class TestSignFlow:
    def test_view_marks_viewed(self, client):
        token = _create(client).get_json()["agreement"]["token"]
        resp = client.get("/sign/{}".format(token))
        assert resp.status_code == 200
        assert b"Sign this agreement" in resp.data
        ag = Agreement.query.filter_by(token=token).first()
        assert ag.status == "viewed"
        assert ag.viewed_at is not None

    def test_sign_executes_agreement(self, client):
        token = _create(client).get_json()["agreement"]["token"]
        resp = client.post("/api/sign/{}".format(token), json={
            "signer_name": "Marcos Rivera",
            "signer_title": "Owner",
            "consent": True,
        })
        assert resp.status_code == 200
        ag = Agreement.query.filter_by(token=token).first()
        assert ag.status == "signed"
        assert ag.signed_at is not None
        assert ag.document_sha256 and len(ag.document_sha256) == 64
        assert ag.executed_html and "Signed electronically" in ag.executed_html
        assert "Marcos Rivera" in ag.executed_html

    def test_signed_link_serves_executed_copy(self, client):
        token = _create(client).get_json()["agreement"]["token"]
        client.post("/api/sign/{}".format(token),
                    json={"signer_name": "Marcos Rivera", "consent": True})
        resp = client.get("/sign/{}".format(token))
        assert resp.status_code == 200
        assert b"Signed electronically" in resp.data
        assert b"Sign this agreement" not in resp.data

    def test_double_sign_conflicts(self, client):
        token = _create(client).get_json()["agreement"]["token"]
        client.post("/api/sign/{}".format(token),
                    json={"signer_name": "Marcos Rivera", "consent": True})
        resp = client.post("/api/sign/{}".format(token),
                           json={"signer_name": "Someone Else", "consent": True})
        assert resp.status_code == 409

    def test_consent_required(self, client):
        token = _create(client).get_json()["agreement"]["token"]
        resp = client.post("/api/sign/{}".format(token),
                           json={"signer_name": "Marcos Rivera", "consent": False})
        assert resp.status_code == 400
        assert Agreement.query.filter_by(token=token).first().status != "signed"

    def test_non_png_signature_rejected_silently(self, client):
        token = _create(client).get_json()["agreement"]["token"]
        client.post("/api/sign/{}".format(token), json={
            "signer_name": "Marcos Rivera",
            "consent": True,
            "signature_image": "javascript:alert(1)",
        })
        ag = Agreement.query.filter_by(token=token).first()
        assert ag.signature_image is None
        assert ag.status == "signed"

    def test_unknown_token_404(self, client):
        assert client.get("/sign/nope").status_code == 404
        assert client.post("/api/sign/nope",
                           json={"signer_name": "X Y", "consent": True}).status_code == 404


class TestList:
    def test_list_requires_passcode(self, client):
        resp = client.post("/api/agreements/list", json={"passcode": "wrong"})
        assert resp.status_code == 403

    def test_list_returns_agreements(self, client):
        _create(client)
        resp = client.post("/api/agreements/list", json={"passcode": PASSCODE})
        assert resp.status_code == 200
        rows = resp.get_json()["agreements"]
        assert any(r["client_company"] == "Rivera Demolition LLC" for r in rows)
