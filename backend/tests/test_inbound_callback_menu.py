"""A caller who doesn't want a robot must be offered a person.

In the 30 days to 15 Sep, 18 of 20 inbound calls were handed to Maya, 15 of
her 33 callers hung up inside 20 seconds, and she booked nothing. The only
choice a caller had was the AI or hanging up. Now a miss offers a callback
from a person first, and only falls through to Maya if they say nothing.
"""
import os
from unittest import mock

import pytest

from models import db, DeskActivity
from models_inbound import InboundCall, CallbackRequest
import inbound


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {
        "TRIXIE_ASSISTANT_PASSCODE": "test-code",
        "TWILIO_AUTH_TOKEN": "",
        "DESK_TWILIO_NUMBER": "+15615550999",
        "DESK_FORWARD_NUMBER": "",
        "BACKEND_URL": "https://api.test",
        "FEATURE_INBOUND_CUSTOMERS": "on",
        "INBOUND_HUMAN_HOURS": "08:00-20:00",
    }), mock.patch("booking_alerts.ops_alert"):
        yield
    CallbackRequest.query.delete()
    InboundCall.query.delete()
    DeskActivity.query.delete()
    db.session.commit()


# --------------------------------------------------------------------------
# The TwiML itself
# --------------------------------------------------------------------------
def _twiml_for(attempt=0):
    from twilio.twiml.voice_response import VoiceResponse
    return str(inbound.choice_twiml(VoiceResponse(), "https://api.test", attempt))


def test_the_menu_offers_a_person_before_the_robot():
    xml = _twiml_for()
    assert "<Gather" in xml
    assert "Press 1" in xml
    assert "call you right back" in xml
    assert "Press 2" in xml
    # A person is offered first, which is the whole point.
    assert xml.index("Press 1") < xml.index("Press 2")


def test_silence_does_not_dead_end():
    xml = _twiml_for()
    assert "<Redirect" in xml
    assert "/api/desk/twilio/voice/choice" in xml


def test_the_second_ask_is_shorter():
    assert len(_twiml_for(attempt=1)) < len(_twiml_for(attempt=0))


# --------------------------------------------------------------------------
# Recording the ask
# --------------------------------------------------------------------------
def test_pressing_one_creates_a_task_a_human_must_work():
    cb = inbound.record_phone_callback("5615550100", call_sid="CAmenu1", source="google")
    assert cb is not None and cb.status == "open"
    row = DeskActivity.query.filter_by(kind="callback").one()
    assert row.status == "open"
    assert "pressed 1" in row.body
    assert "(561) 555-0100" in row.body


def test_a_bad_number_is_refused():
    assert inbound.record_phone_callback("555", call_sid="CAmenu2") is None
    assert CallbackRequest.query.count() == 0


def test_the_callback_is_alerted_by_email_not_text():
    with mock.patch("booking_alerts.ops_alert") as alert:
        inbound.record_phone_callback("5615550100", call_sid="CAmenu3")
    assert alert.call_args.kwargs.get("kind") == "callback"


# --------------------------------------------------------------------------
# The webhook
# --------------------------------------------------------------------------
def _ring(client, sid="CAweb1", frm="+15615550100"):
    return client.post("/api/desk/twilio/voice/inbound",
                       data={"CallSid": sid, "From": frm, "To": "+15615550999"})


def test_pressing_one_confirms_and_hangs_up(client):
    _ring(client)
    r = client.post("/api/desk/twilio/voice/choice?attempt=0",
                    data={"CallSid": "CAweb1", "From": "+15615550100", "Digits": "1"})
    xml = r.data.decode()
    assert "call you right back" in xml
    assert "<Hangup" in xml
    assert "<Dial" not in xml
    assert CallbackRequest.query.count() == 1
    assert DeskActivity.query.filter_by(kind="callback").count() == 1


def test_pressing_two_reaches_maya(client):
    _ring(client, sid="CAweb2")
    r = client.post("/api/desk/twilio/voice/choice?attempt=0",
                    data={"CallSid": "CAweb2", "From": "+15615550100", "Digits": "2"})
    xml = r.data.decode()
    assert "<Dial" in xml and "after-maya" in xml
    assert CallbackRequest.query.count() == 0


def test_silence_asks_once_more_then_falls_through_to_maya(client):
    _ring(client, sid="CAweb3")
    first = client.post("/api/desk/twilio/voice/choice?attempt=0",
                        data={"CallSid": "CAweb3", "From": "+15615550100"}).data.decode()
    assert "<Gather" in first

    second = client.post("/api/desk/twilio/voice/choice?attempt=1",
                         data={"CallSid": "CAweb3", "From": "+15615550100"}).data.decode()
    assert "<Gather" not in second
    assert "after-maya" in second


def test_an_unanswered_ring_offers_the_menu_instead_of_silently_dialling_maya(client):
    _ring(client, sid="CAweb4")
    r = client.post("/api/desk/twilio/voice/after-in",
                    data={"CallSid": "CAweb4", "From": "+15615550100",
                          "DialCallStatus": "no-answer"})
    xml = r.data.decode()
    assert "<Gather" in xml and "Press 1" in xml
    assert "after-maya" not in xml


def test_the_flag_restores_the_old_straight_to_maya_behaviour(client):
    _ring(client, sid="CAweb5")
    real = inbound._flag

    def _off(name, default=True):
        return False if name == "inbound_callback_menu" else real(name, default)

    with mock.patch.object(inbound, "_flag", _off):
        r = client.post("/api/desk/twilio/voice/after-in",
                        data={"CallSid": "CAweb5", "From": "+15615550100",
                              "DialCallStatus": "no-answer"})
    xml = r.data.decode()
    assert "<Gather" not in xml
    assert "after-maya" in xml


def test_an_answered_call_never_sees_the_menu(client):
    _ring(client, sid="CAweb6")
    r = client.post("/api/desk/twilio/voice/after-in",
                    data={"CallSid": "CAweb6", "From": "+15615550100",
                          "DialCallStatus": "completed", "DialCallDuration": "61"})
    xml = r.data.decode()
    assert "<Gather" not in xml and "<Hangup" in xml
