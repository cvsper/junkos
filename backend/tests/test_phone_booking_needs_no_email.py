"""Maya must be able to book a caller who never gives an email.

`create_booking` required an email address and refused without one. Nobody
reads out an email on a 56-second phone call, so in 30 days the tool was never
successfully called and Maya booked nothing. The desk has always created
phone-only customers with a placeholder address; the phone line now does too.
"""
import os
from unittest import mock

import pytest

from models import db, User, Job
import notifications


@pytest.fixture(autouse=True)
def clean(app):
    yield
    Job.query.delete()
    User.query.delete()
    db.session.commit()


def _args(**over):
    a = {
        "customer_name": "Rod Montgomery",
        "address": "812 NW 4th Ave, Boynton Beach FL 33426",
        "items": [{"category": "furniture", "quantity": 2}],
        "scheduled_date": "2099-01-14",
        "scheduled_time": "10-12",
    }
    a.update(over)
    return a


def _call_data(number="+15612819925"):
    return {"message": {"call": {"customer": {"number": number}}}}


def _book(args, data=None):
    from routes.vapi import _handle_create_booking
    return _handle_create_booking(args, data if data is not None else _call_data())


def test_a_caller_with_no_email_still_gets_a_job():
    result = _book(_args())
    assert Job.query.count() == 1, result
    job = Job.query.one()
    assert job.customer_id
    user = db.session.get(User, job.customer_id)
    assert user.email == "5612819925@phone.goumuve.com"
    assert user.name == "Rod Montgomery"


def test_a_volunteered_email_is_still_used():
    _book(_args(email="rod@example.com"))
    user = User.query.one()
    assert user.email == "rod@example.com"


def test_a_returning_caller_is_not_duplicated():
    existing = User(id="u-rod", email="rod@example.com", phone="+15612819925",
                    name="Rod Montgomery", role="customer")
    db.session.add(existing)
    db.session.commit()

    _book(_args())

    assert User.query.count() == 1
    assert User.query.one().email == "rod@example.com"
    assert Job.query.one().customer_id == "u-rod"


def test_no_email_and_no_caller_id_asks_for_a_number():
    result = _book(_args(), data={"message": {"call": {}}})
    assert Job.query.count() == 0
    assert "callback number" in str(result).lower()


def test_address_and_items_are_still_required():
    assert Job.query.count() == 0
    _book(_args(address=""))
    _book(_args(items=[]))
    assert Job.query.count() == 0


# --------------------------------------------------------------------------
# The placeholder address must never be mailed.
# --------------------------------------------------------------------------
def test_placeholder_addresses_are_recognised():
    assert notifications.is_placeholder_email("5612819925@phone.goumuve.com")
    assert notifications.is_placeholder_email("5612819925@PHONE.GOUMUVE.COM")
    assert not notifications.is_placeholder_email("rod@example.com")
    assert not notifications.is_placeholder_email("")


def test_sending_to_a_placeholder_is_skipped_before_the_provider():
    with mock.patch.dict(os.environ, {"RESEND_API_KEY": "re_test"}), \
            mock.patch("notifications._send_email_resend") as resend:
        notifications._send_email_sync("5612819925@phone.goumuve.com", "Hi", "<p>x</p>")
    assert not resend.called


def test_a_real_address_still_sends():
    with mock.patch("notifications.RESEND_API_KEY", "re_test"), \
            mock.patch("notifications._send_email_resend") as resend:
        notifications._send_email_sync("rod@example.com", "Hi", "<p>x</p>")
    assert resend.called
