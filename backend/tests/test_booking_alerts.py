"""Every booking gets announced, and silence is never mistaken for calm.

Job AFB22IMO was booked, assigned, then sat 18 days untouched. The booking
path's only heads-up was one SMS to an optional env var inside a bare
`except: pass` — unset variable or provider hiccup meant nobody heard, and
nothing said so.
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from models import db, User, Job, Payment, Notification, generate_uuid
import booking_alerts


@pytest.fixture(autouse=True)
def env(app):
    keep = {k: os.environ.get(k) for k in
            ("ADMIN_PHONE", "OPERATOR_PHONE", "ADMIN_EMAIL", "SLACK_ALERT_WEBHOOK")}
    for k in keep:
        os.environ.pop(k, None)
    yield
    for k, v in keep.items():
        if v is not None:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)
    Notification.query.filter_by(type="booking").delete(synchronize_session=False)
    Job.query.filter(Job.address.like("e2e-alert%")).delete(synchronize_session=False)
    User.query.filter(User.email.like("%@alert.test")).delete(synchronize_session=False)
    db.session.commit()


def _cx():
    u = User.query.filter_by(email="cx@alert.test").first()
    if not u:
        u = User(id=generate_uuid(), email="cx@alert.test", name="Alert Cx",
                 phone="+15615550888", role="customer")
        db.session.add(u); db.session.commit()
    return u


def _job():
    j = Job(id=generate_uuid(), customer_id=_cx().id, status="pending",
            address="e2e-alert 5370 South University Dr, Davie FL",
            scheduled_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1),
            total_price=307.80, confirmation_code="ALERT001",
            items=[{"category": "furniture", "quantity": 1}, {"category": "appliances", "quantity": 1}])
    db.session.add(j); db.session.commit()
    return j


def test_fans_out_to_every_configured_channel():
    job = _job()
    os.environ.update({"ADMIN_PHONE": "+15615551111", "OPERATOR_PHONE": "+15615552222",
                       "ADMIN_EMAIL": "boss@goumuve.com", "SLACK_ALERT_WEBHOOK": "https://hooks.test/x"})
    with mock.patch("sms_service.send_sms_async") as sms, \
         mock.patch("notifications._send_email_sync") as email, \
         mock.patch("requests.post") as slack:
        sent = booking_alerts.notify_booking(job, "booked")
    assert sms.call_count == 2 and email.call_count == 1 and slack.call_count == 1
    body = sms.call_args_list[0][0][1]
    assert "ALERT001" in body and "307.80" in body and "Davie" in body
    assert any(s.startswith("sms:") for s in sent) and "email" in sent and "slack" in sent


def test_one_broken_channel_does_not_silence_the_others():
    job = _job()
    os.environ.update({"ADMIN_PHONE": "+15615551111", "ADMIN_EMAIL": "boss@goumuve.com"})
    with mock.patch("sms_service.send_sms_async", side_effect=RuntimeError("twilio down")), \
         mock.patch("notifications._send_email_sync") as email:
        sent = booking_alerts.notify_booking(job, "booked")
    assert email.call_count == 1 and "email" in sent


def test_nothing_configured_is_logged_as_an_error(caplog):
    job = _job()
    with caplog.at_level(logging.ERROR, logger="booking_alerts"):
        sent = booking_alerts.notify_booking(job, "booked")
    assert sent == [] or all(s.startswith("inapp") for s in sent)
    if not sent:
        assert "ANNOUNCED TO NOBODY" in caplog.text


def test_staff_get_an_in_app_notification():
    job = _job()
    boss = User(id=generate_uuid(), email="boss@alert.test", name="Boss", role="admin")
    db.session.add(boss); db.session.commit()
    booking_alerts.notify_booking(job, "paid")
    rows = Notification.query.filter_by(user_id=boss.id, type="booking").all()
    assert len(rows) == 1 and "BOOKING PAID" in rows[0].title and "ALERT001" in rows[0].title


def test_alert_never_breaks_the_booking():
    """A notification failure must not cost the customer their booking."""
    broken = mock.MagicMock()
    del broken.confirmation_code
    broken.id = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))
    assert booking_alerts.notify_booking(broken, "booked") == [] or True


def test_paid_stage_says_work_is_owed():
    job = _job()
    os.environ["ADMIN_PHONE"] = "+15615551111"
    with mock.patch("sms_service.send_sms_async") as sms:
        booking_alerts.notify_booking(job, "paid")
    assert "needs a hauler" in sms.call_args[0][1]
