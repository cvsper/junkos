"""Tests for the Call Desk 'vendor_listed' outcome.

Tracy's ask (Aug 2026): a way to log that a prospect added Umuve to their
vendor list / put our rate card on file. It's a soft win — the prospect
stays workable on a light 3-week check-in cadence, counts toward the day's
wins, and gets its own thank-you text with the booking number.
"""

import os
from datetime import timedelta
from unittest import mock

import pytest

from models import db, CallProspect, CallAttempt
import va_calls


@pytest.fixture(autouse=True)
def passcode_env():
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code"}):
        yield


@pytest.fixture()
def prospect(app):
    p = CallProspect(tier=1, category="property management",
                     company="Seacrest Test Services", phone="(561) 555-0142",
                     phone_digits="5615550142", city="West Palm Beach",
                     contact_name="Dana Ortiz")
    db.session.add(p)
    db.session.commit()
    yield p
    CallAttempt.query.filter_by(prospect_id=p.id).delete()
    db.session.delete(p)
    db.session.commit()


def _log(client, prospect, **extra):
    payload = {"code": "test-code", "va_name": "Tracy",
               "prospect_id": prospect.id, "outcome": "vendor_listed"}
    payload.update(extra)
    return client.post("/api/va/calls/log", json=payload)


def test_vendor_listed_is_a_known_outcome():
    assert "vendor_listed" in va_calls.OUTCOMES
    assert "vendor_listed" in va_calls.WIN_OUTCOMES
    assert "vendor_listed" in va_calls.WORKABLE_STATUSES


def test_logging_vendor_listed_sets_status_and_checkin(client, prospect):
    r = _log(client, prospect, note="rate card on file with ops mgr")
    assert r.status_code == 200, r.get_json()
    db.session.refresh(prospect)
    assert prospect.status == "vendor_listed"
    assert prospect.last_outcome == "vendor_listed"
    assert prospect.attempts == 1
    assert prospect.last_note == "rate card on file with ops mgr"
    gap = prospect.next_followup_at - prospect.last_called_at
    assert timedelta(days=va_calls.VENDOR_LISTED_CHECKIN_DAYS - 1) < gap \
        <= timedelta(days=va_calls.VENDOR_LISTED_CHECKIN_DAYS)
    attempt = CallAttempt.query.filter_by(prospect_id=prospect.id).one()
    assert attempt.outcome == "vendor_listed"
    assert r.get_json()["stats"]["interested_today"] >= 1


def test_vendor_listed_prospect_is_served_when_checkin_is_due(client, prospect):
    _log(client, prospect)
    db.session.refresh(prospect)
    # Pull the check-in into the past: the desk must deal this card again.
    prospect.next_followup_at = prospect.next_followup_at - timedelta(
        days=va_calls.VENDOR_LISTED_CHECKIN_DAYS + 1)
    db.session.commit()
    due = va_calls.next_card()
    assert due is not None and due.id == prospect.id


def test_vendor_listed_followup_text_has_rates_and_booking_number(prospect):
    body = va_calls.followup_text_for("vendor_listed", prospect, "Tracy Jamesyoung")
    assert body.startswith("Hi Dana,")
    assert "Tracy" in body
    assert "vendor list" in body
    assert "goumuve.com/partners" in body
    assert "(561) 944-1636" in body
    assert "STOP" in body
    assert len(body) <= 320  # two SMS segments max


def test_vendor_listed_sends_text_when_asked(client, prospect):
    with mock.patch("sms_service.send_sms", return_value="SM123") as send:
        r = _log(client, prospect, send_text=True)
    assert r.status_code == 200
    assert r.get_json()["texted"] is True
    sent_to, body = send.call_args[0]
    assert sent_to == prospect.phone
    assert "(561) 944-1636" in body
