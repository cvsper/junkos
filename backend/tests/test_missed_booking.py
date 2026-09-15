"""A caller who says yes must never leave without a job or a callback.

The case this is built from is real. On 5 Sep 2026 a caller asked about two
projection TVs in Pembroke Pines, Maya quoted $119, and Vapi's own summary
records that he agreed to schedule before the call ended. No job was created,
he got a generic "book online" text, and nobody called him. It was the closest
Umuve came to revenue in 30 days.
"""
import os
from unittest import mock

import pytest

from models import db, DeskActivity, User, Job
from models_inbound import CallbackRequest
import missed_booking


# The summary Vapi actually returned for that call, verbatim from
# /api/va/maya/report on 15 Sep.
REAL_SUMMARY = (
    "The user called to inquire about disposing of one, then two, projecting TVs in "
    "Pembroke Pines/Miramar. The AI quoted a flat rate of $119, which is their minimum "
    "job price, covering both TVs and all associated costs. Despite the user's initial "
    "hesitation about the price, the AI confirmed it was a final, all-inclusive cost, "
    "leading the user to agree to schedule the pickup before the call abruptly en"
)


@pytest.fixture(autouse=True)
def clean(app):
    yield
    CallbackRequest.query.delete()
    DeskActivity.query.delete()
    Job.query.delete()
    User.query.delete()
    db.session.commit()


@pytest.fixture(autouse=True)
def no_alerts():
    with mock.patch("booking_alerts.ops_alert"):
        yield


def test_the_real_lost_call_is_caught():
    assert missed_booking.was_priced("", REAL_SUMMARY)
    assert missed_booking.looks_like_yes("", REAL_SUMMARY)
    assert missed_booking.should_capture("", REAL_SUMMARY, booking_created=False)


def test_a_call_that_booked_is_not_captured():
    assert not missed_booking.should_capture("", REAL_SUMMARY, booking_created=True)


def test_price_shopping_without_a_yes_is_left_alone():
    t = "Caller asked what it would cost for a couch. The AI quoted $119. Caller said they would think about it."
    assert missed_booking.was_priced(t)
    assert not missed_booking.looks_like_yes(t)
    assert not missed_booking.should_capture(t, "", False)


def test_a_yes_with_no_price_is_left_alone():
    # Nothing to call them back about yet.
    t = "Caller said sounds good and asked where we are located."
    assert missed_booking.looks_like_yes(t)
    assert not missed_booking.was_priced(t)
    assert not missed_booking.should_capture(t, "", False)


@pytest.mark.parametrize("said", [
    "okay let's do it, when can you come",
    "yeah go ahead and schedule me for Thursday",
    "that works, put me down",
    "sign me up",
])
def test_ordinary_ways_people_say_yes(said):
    assert missed_booking.looks_like_yes(said)


@pytest.mark.parametrize("said", [
    "that's too expensive, I'll shop around",
    "sounds good but I'll think about it",
    "let's do it -- actually no thanks, changed my mind",
])
def test_a_no_is_never_read_as_a_yes(said):
    assert not missed_booking.looks_like_yes(said)


def test_price_in_takes_the_quote_not_a_stray_number():
    assert missed_booking.price_in("minimum is $119 and this job is $389.00") == 389.0
    assert missed_booking.price_in("no figures here") is None
    assert missed_booking.price_in("that's $1,250 all in") == 1250.0


def test_capture_puts_a_real_task_on_the_desk():
    cb = missed_booking.capture("+15612819925", call_id="call-abc",
                                summary=REAL_SUMMARY, transcript="")
    assert cb is not None
    assert cb.phone_digits == "5612819925"
    assert cb.status == "open"
    row = DeskActivity.query.filter_by(kind="callback").one()
    assert "MISSED BOOKING" in row.body
    assert "$119" in row.body
    assert row.status == "open"


def test_capture_is_idempotent_when_vapi_reposts_the_report():
    missed_booking.capture("+15612819925", call_id="call-abc", summary=REAL_SUMMARY)
    missed_booking.capture("+15612819925", call_id="call-abc", summary=REAL_SUMMARY)
    assert DeskActivity.query.filter_by(kind="callback").count() == 1
    assert CallbackRequest.query.count() == 1


def test_capture_alerts_the_team_by_email_not_text():
    with mock.patch("booking_alerts.ops_alert") as alert:
        missed_booking.capture("+15612819925", call_id="c1", summary=REAL_SUMMARY)
    assert alert.called
    kwargs = alert.call_args.kwargs
    assert kwargs.get("kind") == "missed_booking"


def test_a_call_with_no_usable_number_is_skipped_quietly():
    assert missed_booking.capture("", call_id="c2", summary=REAL_SUMMARY) is None
    assert CallbackRequest.query.count() == 0


def test_the_flag_turns_it_off():
    with mock.patch("flags.flag", return_value=False):
        assert not missed_booking.should_capture("", REAL_SUMMARY, False)
