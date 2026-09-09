"""Personalized PDF rate card: build, signed URL, text link, email attachment."""
import os
from unittest import mock

import pytest

from models import db, CallProspect
from rate_card import build_rate_card_pdf, sign, check_sig, public_url


@pytest.fixture(autouse=True)
def env():
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code",
                                      "RATE_CARD_SECRET": "unit-secret",
                                      "BACKEND_URL": "https://api.test"}):
        yield


@pytest.fixture()
def prospect(app):
    p = CallProspect(tier=1, category="property management", company="Palm Coast Property Group",
                     phone="(561) 555-0142", phone_digits="5615550142", city="West Palm Beach",
                     contact_name="Marcus Bell", direct_phone="(561) 555-0199")
    db.session.add(p); db.session.commit()
    yield p
    db.session.delete(p); db.session.commit()


def _va(client, payload):
    base = {"code": "test-code", "va_name": "Tracy"}
    base.update(payload)
    return client.post("/api/va/calls/rate-card", json=base)


def _pdf_text(pdf):
    """Inflate every content stream so we can grep the drawn text."""
    import re, zlib
    out = b""
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", pdf, re.S):
        try:
            out += zlib.decompress(m.group(1))
        except Exception:
            out += m.group(1)
    return out


def test_pdf_builds_with_company_and_prices(prospect):
    pdf = build_rate_card_pdf(prospect, va_name="Tracy", desk_number="+15617824350")
    assert pdf[:5] == b"%PDF-" and len(pdf) > 5000
    text = _pdf_text(pdf)
    assert b"Palm Coast Property Group" in text
    assert b"782-4350" in text
    assert b"Sofa" in text and b"Small loads" in text
    assert b"per bag" not in text                       # minimum-charge rows don't print as per-unit


def test_signed_url_and_public_endpoint(client, prospect):
    assert check_sig(prospect.id, sign(prospect.id))
    assert not check_sig(prospect.id, "nope")
    url = public_url(prospect.id)
    assert url.startswith("https://api.test/rate-card/{}.pdf?s=".format(prospect.id))
    ok = client.get("/rate-card/{}.pdf?s={}".format(prospect.id, sign(prospect.id)))
    assert ok.status_code == 200 and ok.mimetype == "application/pdf" and ok.data[:5] == b"%PDF-"
    assert "Palm-Coast" in ok.headers["Content-Disposition"]
    assert client.get("/rate-card/{}.pdf?s=bad".format(prospect.id)).status_code == 404
    assert client.get("/rate-card/missing.pdf?s={}".format(sign("missing"))).status_code == 404


def test_text_sends_link_from_desk_line(client, prospect):
    with mock.patch("desk_line.send_desk_text", return_value="SM123") as send:
        resp = _va(client, {"prospect_id": prospect.id, "channel": "text"})
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["to"].endswith("0199")                      # direct cell preferred
    to, text = send.call_args[0][0], send.call_args[0][1]
    assert to == "5615550199" and "rate-card/{}.pdf?s=".format(prospect.id) in text
    assert "Marcus" in text and "STOP" in text


def test_email_attaches_pdf(client, prospect):
    with mock.patch("notifications._send_email_resend", return_value="re_1") as send:
        resp = _va(client, {"prospect_id": prospect.id, "channel": "email", "to": "marcus@example.com"})
    assert resp.status_code == 200, resp.get_json()
    kwargs = send.call_args.kwargs
    att = kwargs["attachments"][0]
    assert att["filename"].endswith(".pdf") and att["content"][:5] == b"%PDF-"
    assert send.call_args[0][0] == "marcus@example.com"
    db.session.refresh(prospect)
    assert prospect.email == "marcus@example.com" and prospect.last_emailed_at


def test_preview_and_guards(client, prospect):
    body = _va(client, {"prospect_id": prospect.id, "channel": "preview"}).get_json()
    assert body["url"].endswith("&va=Tracy") and "?s=" in body["url"]
    assert _va(client, {"prospect_id": prospect.id, "channel": "email", "to": "not-an-email"}).status_code == 400
    assert _va(client, {"prospect_id": prospect.id, "channel": "fax"}).status_code == 400
    assert client.post("/api/va/calls/rate-card", json={"code": "wrong"}).status_code == 401
