"""Call Desk line (desk_line.py): inbound texts land on the prospect's card,
desk texts go out from the desk number and log to the thread, inbound calls
ring the browser + forward cell together and fall to voicemail, and the
browser-dialer token stays off until the env is provisioned.
"""
import os
from unittest import mock

import pytest

from models import db, CallProspect, DeskActivity


@pytest.fixture(autouse=True)
def env():
    with mock.patch.dict(os.environ, {
        "TRIXIE_ASSISTANT_PASSCODE": "test-code",
        "TWILIO_AUTH_TOKEN": "",          # signature validation skipped in tests
        "DESK_TWILIO_NUMBER": "+15615550999",
        "DESK_FORWARD_NUMBER": "+15615550777",
        "BACKEND_URL": "https://api.test",
    }):
        yield


@pytest.fixture()
def prospect(app):
    p = CallProspect(tier=1, category="property management",
                     company="Test Property Co", phone="(561) 555-0100",
                     phone_digits="5615550100", city="West Palm Beach",
                     contact_name="Pat Smith", direct_phone="(561) 555-0101")
    db.session.add(p)
    db.session.commit()
    yield p
    DeskActivity.query.delete()
    db.session.delete(p)
    db.session.commit()


def _va(client, path, payload):
    base = {"code": "test-code", "va_name": "Tracy"}
    base.update(payload)
    return client.post(path, json=base)


class _FakeMsg:
    sid = "SM" + "b" * 32


# ---------------------------------------------------------------- inbound sms
def test_inbound_text_links_prospect_and_surfaces_card(client, prospect):
    prospect.status = "queued"
    prospect.next_followup_at = None
    db.session.commit()
    with mock.patch("desk_line._client") as cl:
        cl.return_value.messages.create.return_value = _FakeMsg()
        resp = client.post("/api/desk/twilio/sms", data={
            "From": "+15615550100", "To": "+15615550999",
            "Body": "Yes send me the info", "NumMedia": "0", "MessageSid": "SMin1"})
    assert resp.status_code == 200
    assert b"<Response" in resp.data
    act = DeskActivity.query.filter_by(twilio_sid="SMin1").one()
    assert act.direction == "in" and act.kind == "sms"
    assert act.prospect_id == prospect.id
    assert act.read_at is None
    db.session.refresh(prospect)
    assert prospect.status == "interested"
    assert prospect.next_followup_at is not None          # due now
    assert "THEY TEXTED" in prospect.last_note
    # forward ping went to Tracy's cell from the desk number
    kwargs = cl.return_value.messages.create.call_args.kwargs
    assert kwargs["to"] == "+15615550777" and kwargs["from_"] == "+15615550999"
    assert "Test Property Co" in kwargs["body"]


def test_inbound_from_direct_cell_matches_prospect(client, prospect):
    with mock.patch("desk_line._client", return_value=None):
        client.post("/api/desk/twilio/sms", data={
            "From": "+15615550101", "Body": "hi", "NumMedia": "0", "MessageSid": "SMin2"})
    act = DeskActivity.query.filter_by(twilio_sid="SMin2").one()
    assert act.prospect_id == prospect.id


def test_stop_kills_prospect(client, prospect):
    with mock.patch("desk_line._client", return_value=None):
        client.post("/api/desk/twilio/sms", data={
            "From": "+15615550100", "Body": "STOP", "NumMedia": "0", "MessageSid": "SMin3"})
    db.session.refresh(prospect)
    assert prospect.status == "dead" and prospect.last_outcome == "opted_out"
    assert prospect.next_followup_at is None
    resp = _va(client, "/api/va/desk/text", {"prospect_id": prospect.id, "body": "hello?"})
    assert resp.status_code == 409


def test_unknown_sender_still_logged(client, prospect):
    with mock.patch("desk_line._client", return_value=None):
        client.post("/api/desk/twilio/sms", data={
            "From": "+19545550000", "Body": "who dis", "NumMedia": "0", "MessageSid": "SMin4"})
    act = DeskActivity.query.filter_by(twilio_sid="SMin4").one()
    assert act.prospect_id is None and act.phone_digits == "9545550000"


def test_main_number_mirror_records_prospect_reply(client, prospect):
    """Replies to info packs sent from the main Umuve number show in the thread."""
    with mock.patch.dict(os.environ, {"SMS_WEBHOOK_VALIDATE": "off"}), \
         mock.patch("desk_line._client", return_value=None):
        client.post("/api/sms/inbound", data={
            "From": "+15615550100", "To": "+18445550000",
            "Body": "Tell me more", "NumMedia": "0", "MessageSid": "SMmain1"})
    act = DeskActivity.query.filter_by(twilio_sid="SMmain1").first()
    assert act is not None and act.prospect_id == prospect.id


# ---------------------------------------------------------------- outbound sms
def test_desk_text_sends_from_desk_number_and_logs(client, prospect):
    with mock.patch("desk_line._client") as cl:
        cl.return_value.messages.create.return_value = _FakeMsg()
        resp = _va(client, "/api/va/desk/text",
                   {"prospect_id": prospect.id, "body": "Hi Pat, Tracy here."})
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["ok"] and body["to"].endswith("0101")     # direct cell preferred
    kwargs = cl.return_value.messages.create.call_args.kwargs
    assert kwargs["from_"] == "+15615550999" and kwargs["to"] == "+15615550101"
    assert kwargs["status_callback"] == "https://api.test/api/desk/twilio/sms-status"
    assert body["messages"][-1]["direction"] == "out"
    assert body["messages"][-1]["body"] == "Hi Pat, Tracy here."
    db.session.refresh(prospect)
    assert prospect.last_texted_at is not None


def test_desk_text_falls_back_to_main_number_without_desk_line(client, prospect):
    with mock.patch.dict(os.environ, {"DESK_TWILIO_NUMBER": ""}), \
         mock.patch("sms_service.send_sms", return_value="SMfallback") as send:
        resp = _va(client, "/api/va/desk/text",
                   {"prospect_id": prospect.id, "body": "fallback"})
    assert resp.status_code == 200
    assert send.call_args[0][0] == "+15615550101"


def test_desk_text_validation(client, prospect):
    assert _va(client, "/api/va/desk/text", {"prospect_id": prospect.id, "body": ""}).status_code == 400
    assert _va(client, "/api/va/desk/text", {"prospect_id": prospect.id, "body": "x" * 641}).status_code == 400
    assert _va(client, "/api/va/desk/text", {"prospect_id": "nope", "body": "hi"}).status_code == 404
    assert client.post("/api/va/desk/text", json={"code": "wrong"}).status_code == 401


def test_sms_status_callback_updates_activity(client, prospect):
    with mock.patch("desk_line._client") as cl:
        cl.return_value.messages.create.return_value = _FakeMsg()
        _va(client, "/api/va/desk/text", {"prospect_id": prospect.id, "body": "ping"})
    resp = client.post("/api/desk/twilio/sms-status",
                       data={"MessageSid": _FakeMsg.sid, "MessageStatus": "delivered"})
    assert resp.status_code == 204
    assert DeskActivity.query.filter_by(twilio_sid=_FakeMsg.sid).one().status == "delivered"
    client.post("/api/desk/twilio/sms-status",
                data={"MessageSid": _FakeMsg.sid, "MessageStatus": "undelivered", "ErrorCode": "30007"})
    assert DeskActivity.query.filter_by(twilio_sid=_FakeMsg.sid).one().status == "undelivered:30007"


# ---------------------------------------------------------------- thread + inbox
def test_thread_marks_read_and_inbox_counts(client, prospect):
    with mock.patch("desk_line._client", return_value=None):
        for i in range(2):
            client.post("/api/desk/twilio/sms", data={
                "From": "+15615550100", "Body": "msg %d" % i, "NumMedia": "0",
                "MessageSid": "SMt%d" % i})
    inbox = _va(client, "/api/va/desk/inbox", {}).get_json()
    assert inbox["unread"] == 2
    assert len(inbox["items"]) == 1                      # grouped by number
    assert inbox["items"][0]["company"] == "Test Property Co"
    assert inbox["items"][0]["preview"] == "msg 1"       # newest first
    assert inbox["items"][0]["unread"] == 2

    thread = _va(client, "/api/va/desk/thread", {"prospect_id": prospect.id}).get_json()
    assert [m["body"] for m in thread["messages"]] == ["msg 0", "msg 1"]
    assert thread["unread"] == 0
    assert _va(client, "/api/va/desk/unread", {}).get_json()["unread"] == 0


# ---------------------------------------------------------------- voice
def test_outbound_voice_twiml_dials_with_desk_caller_id(client, prospect):
    resp = client.post("/api/desk/twilio/voice", data={
        "CallSid": "CAout1", "To": "+15615550100", "prospect_id": prospect.id,
        "va_name": "Tracy"})
    assert resp.status_code == 200
    xml = resp.data.decode()
    assert 'callerId="+15615550999"' in xml
    assert "<Number>+15615550100</Number>" in xml
    assert "/api/desk/twilio/voice/after-out" in xml
    act = DeskActivity.query.filter_by(twilio_sid="CAout1").one()
    assert act.kind == "call" and act.direction == "out" and act.prospect_id == prospect.id
    assert act.va_name == "Tracy"

    client.post("/api/desk/twilio/voice/after-out", data={
        "CallSid": "CAout1", "DialCallStatus": "completed", "DialCallDuration": "95"})
    db.session.refresh(act)
    assert act.status == "completed" and act.duration == 95
    db.session.refresh(prospect)
    assert prospect.last_called_at is not None


def test_outbound_voice_without_desk_number_hangs_up(client, prospect):
    with mock.patch.dict(os.environ, {"DESK_TWILIO_NUMBER": ""}):
        resp = client.post("/api/desk/twilio/voice", data={"CallSid": "CAx", "To": "+15615550100"})
    assert "<Hangup" in resp.data.decode() and "<Dial" not in resp.data.decode()


def test_inbound_voice_rings_browser_and_cell_then_voicemail(client, prospect):
    resp = client.post("/api/desk/twilio/voice/inbound", data={
        "CallSid": "CAin1", "From": "+15615550100", "To": "+15615550999"})
    xml = resp.data.decode()
    assert "<Client>desk</Client>" in xml
    assert "<Number>+15615550777</Number>" in xml
    assert 'timeout="25"' in xml
    act = DeskActivity.query.filter_by(twilio_sid="CAin1").one()
    assert act.direction == "in" and act.prospect_id == prospect.id and act.read_at is None

    resp = client.post("/api/desk/twilio/voice/after-in", data={
        "CallSid": "CAin1", "DialCallStatus": "no-answer"})
    xml = resp.data.decode()
    assert "<Record" in xml and "/api/desk/twilio/voice/transcript" in xml
    db.session.refresh(act)
    assert act.status == "voicemail"

    with mock.patch("desk_line._client") as cl:
        cl.return_value.messages.create.return_value = _FakeMsg()
        client.post("/api/desk/twilio/voice/transcript", data={
            "CallSid": "CAin1", "TranscriptionText": "call me back please",
            "RecordingUrl": "https://api.twilio.com/rec/RE1"})
        ping = cl.return_value.messages.create.call_args.kwargs["body"]
    db.session.refresh(act)
    assert act.body == "call me back please"
    assert act.recording_url.endswith("RE1")
    assert "Voicemail" in ping

    inbox = _va(client, "/api/va/desk/inbox", {}).get_json()
    assert inbox["unread"] == 1
    assert inbox["items"][0]["preview"].startswith("Voicemail: call me back")


def test_inbound_voice_answered_hangs_up_cleanly(client, prospect):
    client.post("/api/desk/twilio/voice/inbound", data={"CallSid": "CAin2", "From": "+15615550100"})
    resp = client.post("/api/desk/twilio/voice/after-in", data={
        "CallSid": "CAin2", "DialCallStatus": "completed", "DialCallDuration": "40"})
    assert "<Record" not in resp.data.decode()
    act = DeskActivity.query.filter_by(twilio_sid="CAin2").one()
    assert act.status == "completed" and act.duration == 40 and act.read_at is not None


# ---------------------------------------------------------------- token
def test_token_disabled_until_provisioned(client):
    with mock.patch.dict(os.environ, {"TWILIO_TWIML_APP_SID": ""}):
        body = _va(client, "/api/va/desk/token", {}).get_json()
    assert body["enabled"] is False and "TWILIO_TWIML_APP_SID" in body["missing"]


def test_token_issued_when_provisioned(client):
    with mock.patch.dict(os.environ, {
        "TWILIO_ACCOUNT_SID": "AC" + "0" * 32, "TWILIO_API_KEY_SID": "SK" + "1" * 32,
        "TWILIO_API_KEY_SECRET": "s3cret" * 5, "TWILIO_TWIML_APP_SID": "AP" + "2" * 32}):
        body = _va(client, "/api/va/desk/token", {}).get_json()
    assert body["enabled"] is True
    assert body["token"].count(".") == 2                  # a JWT
    assert body["desk_number"] == "+15615550999"
