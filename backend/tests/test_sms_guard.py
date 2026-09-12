"""Main-number SMS loop guard (9/11 incident): auto-responders get silence,
desk prospects are Tracy's, and conversational replies are rate-capped.
Follow-up texts go out from the desk line and skip plain no-answers."""
import os
from unittest import mock

import pytest

import sms_guard
import va_calls
from models import db, CallProspect, DeskActivity

EMPTY = "<Response></Response>"


@pytest.fixture(autouse=True)
def env(app):
    sms_guard._reset()
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code", "TWILIO_AUTH_TOKEN": "",
                                      "DESK_TWILIO_NUMBER": "+15617824350", "BACKEND_URL": "https://api.test"}), \
         mock.patch("desk_line._client", return_value=None):
        yield
    sms_guard._reset()


@pytest.fixture()
def prospect():
    p = CallProspect(tier=1, category="property management", company="Vue At Lake Worth",
                     phone="(561) 555-8857", phone_digits="5615558857", city="Lake Worth", contact_name="Sam Lee")
    db.session.add(p); db.session.commit()
    yield p
    DeskActivity.query.delete(); db.session.delete(p); db.session.commit()


def _text(client, frm, body, sid):
    return client.post("/api/sms/inbound", data={"From": frm, "To": "+18444356005", "Body": body,
                                                 "NumMedia": "0", "MessageSid": sid})


REAL_AUTOREPLIES = [
    "Thanks for contacting Vue At 1400. Reply START to receive SMS messages from us.",
    "Thanks for contacting Griffis Pompano Beach. Reply START to receive SMS from our team.",
    "We're sorry, text messages can't be received by this phone number.",
    "Reply YES to consent to text messages from ParkLine Palm Beach. Msg & data rates may apply.",
    "This is an automated response. Our office is closed — we'll get back to you shortly.",
]


def test_recognises_the_auto_responders_from_the_incident():
    for body in REAL_AUTOREPLIES:
        assert sms_guard.looks_automated(body), body
    for body in ["Yes, how much for a sofa and two mattresses?", "Y", "STOP", "Can you come Tuesday?",
                 "Thanks! What time works?", "Tell me more"]:
        assert not sms_guard.looks_automated(body), body


def test_auto_responder_gets_no_reply(client):
    with mock.patch("requests.post") as vapi:
        r = _text(client, "+19545550142", REAL_AUTOREPLIES[0], "SMauto1")
    assert r.status_code == 200 and EMPTY in r.get_data(as_text=True)
    vapi.assert_not_called()


def test_prospect_reply_lands_on_the_desk_and_maya_stays_quiet(client, prospect):
    with mock.patch("requests.post") as vapi:
        r = _text(client, "+15615558857", "Tell me more about the rates", "SMpros1")
    assert EMPTY in r.get_data(as_text=True)
    vapi.assert_not_called()
    act = DeskActivity.query.filter_by(twilio_sid="SMpros1").one()
    assert act.prospect_id == prospect.id and act.direction == "in"


def test_customer_texts_still_get_a_reply_until_the_cap(client):
    with mock.patch("requests.post", side_effect=RuntimeError("vapi down")):
        for i in range(sms_guard.REPLY_CAP):
            r = _text(client, "+13055550199", "hi, do you take couches? {}".format(i), "SMcx{}".format(i))
            assert "<Message>" in r.get_data(as_text=True)
        r = _text(client, "+13055550199", "hello?", "SMcxlast")
    assert EMPTY in r.get_data(as_text=True)
    # a different sender is unaffected by the first one's cap
    with mock.patch("requests.post", side_effect=RuntimeError("vapi down")):
        r = _text(client, "+13055550200", "do you take fridges", "SMcxother")
    assert "<Message>" in r.get_data(as_text=True)


def test_global_cap_silences_a_loop_across_many_numbers(monkeypatch):
    monkeypatch.setattr(sms_guard, "GLOBAL_CAP", 3)
    for n in ("1", "2", "3"):
        assert sms_guard.reply_allowed("555000000" + n); sms_guard.note_reply("555000000" + n)
    assert not sms_guard.reply_allowed("5550000009")


def test_no_answer_gets_no_text_voicemail_and_interested_still_do(prospect):
    assert va_calls.followup_text_for("no_answer", prospect, "Tracy") is None
    assert "just tried you" in va_calls.followup_text_for("voicemail", prospect, "Tracy")
    assert "partners" in va_calls.followup_text_for("interested", prospect, "Tracy")


def test_followup_text_goes_out_from_the_desk_line(client, prospect):
    class _Msg: sid = "SMdesk1"
    fake = mock.Mock(); fake.messages.create.return_value = _Msg()
    with mock.patch("desk_line._client", return_value=fake):
        sent, why = va_calls.maybe_send_followup_text(prospect, "voicemail", "Tracy")
    assert sent, why
    kw = fake.messages.create.call_args.kwargs
    assert kw["from_"] == "+15617824350" and kw["to"] == "+15615558857"
    assert DeskActivity.query.filter_by(twilio_sid="SMdesk1").one().direction == "out"
    assert prospect.last_texted_at is not None


def test_vapi_201_twiml_is_relayed_to_twilio(client):
    class _R: status_code = 201; text = "<Response><Message>Yeah, we take couches!</Message></Response>"
    with mock.patch("requests.post", return_value=_R()):
        r = _text(client, "+13055550300", "do you take couches", "SMvapi201")
    assert "we take couches" in r.get_data(as_text=True)
