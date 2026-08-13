"""Tests for operator proof-photo attach via the inbound SMS webhook.

A hauler texting photos right after a job is submitting before/after proof,
not asking for a quote — the webhook must attach the photos to their job
and skip the photo-quote engine. Everyone else's photos still get quoted.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from models import db, Contractor, Job, User


HAULER_PHONE = "+15617770001"


@pytest.fixture()
def hauler(app):
    u = User(id=str(uuid.uuid4()), phone=HAULER_PHONE, name="Hank Hauler",
             role="driver")
    db.session.add(u)
    db.session.flush()
    c = Contractor(id=str(uuid.uuid4()), user_id=u.id)
    db.session.add(c)
    db.session.commit()
    yield c
    db.session.delete(c)
    db.session.delete(u)
    db.session.commit()


@pytest.fixture()
def customer(app):
    u = User(id=str(uuid.uuid4()), phone="+15617770002", name="Cass Customer")
    db.session.add(u)
    db.session.commit()
    yield u
    db.session.delete(u)
    db.session.commit()


@pytest.fixture()
def completed_job(app, hauler, customer):
    job = Job(id=str(uuid.uuid4()), customer_id=customer.id,
              driver_id=hauler.id, status="completed",
              address="123 Beach Dr, West Palm Beach, FL",
              total_price=134.0,
              updated_at=datetime.now(timezone.utc))
    db.session.add(job)
    db.session.commit()
    yield job
    db.session.delete(job)
    db.session.commit()


def _post_mms(client, from_phone=HAULER_PHONE, body="", n_media=1):
    data = {"From": from_phone, "To": "+18444356005", "Body": body,
            "NumMedia": str(n_media)}
    for i in range(n_media):
        data["MediaUrl{}".format(i)] = (
            "https://api.twilio.com/media/{}".format(i))
        data["MediaContentType{}".format(i)] = "image/jpeg"
    return client.post("/api/sms/inbound", data=data)


def test_hauler_photo_attaches_as_before_first(client, completed_job):
    with mock.patch("routes.sms_webhook._process_photo_quote") as quote:
        resp = _post_mms(client)
    assert resp.status_code == 200
    assert b"Attached 1 before photo" in resp.data
    quote.assert_not_called()
    db.session.refresh(completed_job)
    assert completed_job.before_photos == ["https://api.twilio.com/media/0"]
    assert completed_job.proof_submitted_at is not None


def test_keyword_after_routes_to_after_photos(client, completed_job):
    resp = _post_mms(client, body="After shot")
    assert b"after photo" in resp.data
    db.session.refresh(completed_job)
    assert completed_job.after_photos == ["https://api.twilio.com/media/0"]
    assert not completed_job.before_photos


def test_second_send_defaults_to_after(client, completed_job):
    completed_job.before_photos = ["existing"]
    db.session.commit()
    resp = _post_mms(client)
    assert b"after photo" in resp.data
    db.session.refresh(completed_job)
    assert completed_job.after_photos == ["https://api.twilio.com/media/0"]
    assert b"good stuff" in resp.data  # full set acknowledged


def test_unknown_sender_still_gets_quoted(client, completed_job):
    with mock.patch("routes.sms_webhook._process_photo_quote") as quote:
        resp = _post_mms(client, from_phone="+19995550000")
    assert b"quote" in resp.data.lower()
    quote.assert_called_once()


def test_stale_job_falls_through_to_quote(client, completed_job):
    completed_job.updated_at = datetime.now(timezone.utc) - timedelta(days=5)
    db.session.commit()
    with mock.patch("routes.sms_webhook._process_photo_quote") as quote:
        _post_mms(client)
    quote.assert_called_once()


# ---------------------------------------------------------------------------
# Review-ask link gating: never send customers a dead link
# ---------------------------------------------------------------------------

def test_review_sms_without_gbp_url_has_no_link(app):
    import os
    from sms_service import send_review_request_sms
    with mock.patch.dict(os.environ, {"GOOGLE_REVIEW_URL": ""}), \
         mock.patch("sms_service.send_sms_async") as send:
        send_review_request_sms("+15617770002", "Cass Customer", "West Palm Beach")
    body = send.call_args[0][1]
    assert "http" not in body
    assert "Reply" in body


def test_review_sms_with_gbp_url_links_it(app):
    import os
    from sms_service import send_review_request_sms
    with mock.patch.dict(os.environ,
                         {"GOOGLE_REVIEW_URL": "https://g.page/r/REAL/review"}), \
         mock.patch("sms_service.send_sms_async") as send:
        send_review_request_sms("+15617770002", "Cass Customer", "West Palm Beach")
    assert "https://g.page/r/REAL/review" in send.call_args[0][1]
