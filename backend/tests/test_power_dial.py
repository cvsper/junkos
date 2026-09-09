"""Power dial: AMD on the dialed leg, voicemail-drop recording, machine handling."""
import os
from unittest import mock

import pytest

from models import db, CallProspect, DeskActivity, DeskSetting


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code", "TWILIO_AUTH_TOKEN": "",
                                      "DESK_TWILIO_NUMBER": "+15615550999", "BACKEND_URL": "https://api.test"}):
        yield
    DeskActivity.query.delete(); DeskSetting.query.delete(); CallProspect.query.delete(); db.session.commit()


@pytest.fixture()
def prospect():
    p = CallProspect(tier=1, category="storage", company="Lantana Self Storage", phone="(561) 555-0120",
                     phone_digits="5615550120", city="Lantana")
    db.session.add(p); db.session.commit()
    return p


def _va(client, path, payload):
    base = {"code": "test-code", "va_name": "Tracy"}
    base.update(payload)
    return client.post(path, json=base)


def test_outbound_twiml_adds_amd_only_when_power_dialing(client, prospect):
    plain = client.post("/api/desk/twilio/voice", data={"CallSid": "CA1", "To": "+15615550120",
                                                         "prospect_id": prospect.id, "va_name": "Tracy"}).data.decode()
    assert "machineDetection" not in plain
    amd = client.post("/api/desk/twilio/voice", data={"CallSid": "CA2", "To": "+15615550120",
                                                       "prospect_id": prospect.id, "va_name": "Tracy", "amd": "1"}).data.decode()
    assert 'machineDetection="DetectMessageEnd"' in amd
    assert "amdStatusCallback=" in amd and "parent=CA2" in amd and "va=Tracy" in amd
    assert "<Number" in amd and "+15615550120" in amd


def test_record_vm_mode_returns_record_and_logs_nothing(client):
    xml = client.post("/api/desk/twilio/voice", data={"CallSid": "CAr", "mode": "record_vm", "va_name": "Tracy"}).data.decode()
    assert "<Record" in xml and "vm-recorded?va=Tracy" in xml and 'finishOnKey="#"' in xml
    assert DeskActivity.query.count() == 0
    # Twilio posts the recording back
    xml = client.post("/api/desk/twilio/voice/vm-recorded?va=Tracy",
                      data={"RecordingUrl": "https://api.twilio.com/rec/RE9", "RecordingDuration": "31"}).data.decode()
    assert "Saved" in xml
    st = _va(client, "/api/va/desk/voicemail", {"action": "status"}).get_json()
    assert st["has_voicemail"] and st["seconds"] == 31 and st["play_url"].endswith("RE9.mp3")
    st = _va(client, "/api/va/desk/voicemail", {"action": "clear"}).get_json()
    assert st["has_voicemail"] is False


def test_machine_drops_voicemail_into_child_leg(client, prospect):
    DeskSetting.put("vm_url:tracy", "https://api.twilio.com/rec/RE9")
    client.post("/api/desk/twilio/voice", data={"CallSid": "CApar", "To": "+15615550120",
                                                "prospect_id": prospect.id, "va_name": "Tracy", "amd": "1"})
    with mock.patch("desk_line._client") as cl:
        resp = client.post("/api/desk/twilio/voice/amd?parent=CApar&va=Tracy",
                           data={"CallSid": "CAchild", "AnsweredBy": "machine_end_beep"})
        assert resp.status_code == 204
        cl.return_value.calls.assert_called_with("CAchild")
        twiml = cl.return_value.calls.return_value.update.call_args.kwargs["twiml"]
        assert "<Play>https://api.twilio.com/rec/RE9</Play>" in twiml and "<Hangup" in twiml
    act = DeskActivity.query.filter_by(twilio_sid="CApar").one()
    assert act.status == "vm_dropped" and "AMD: machine_end_beep" in act.body
    # the parent's dial finishing doesn't overwrite the drop
    client.post("/api/desk/twilio/voice/after-out", data={"CallSid": "CApar", "DialCallStatus": "completed",
                                                          "DialCallDuration": "12"})
    db.session.refresh(act)
    assert act.status == "vm_dropped" and act.duration == 12
    last = _va(client, "/api/va/desk/last-call", {"prospect_id": prospect.id}).get_json()
    assert last["call"]["status"] == "vm_dropped"


def test_machine_without_recording_is_flagged_not_dropped(client, prospect):
    client.post("/api/desk/twilio/voice", data={"CallSid": "CApar2", "To": "+15615550120",
                                                "prospect_id": prospect.id, "amd": "1"})
    with mock.patch("desk_line._client") as cl:
        client.post("/api/desk/twilio/voice/amd?parent=CApar2&va=Tracy",
                    data={"CallSid": "CAchild2", "AnsweredBy": "machine_end_silence"})
        cl.return_value.calls.return_value.update.assert_not_called()
    assert DeskActivity.query.filter_by(twilio_sid="CApar2").one().status == "machine"


def test_human_answer_changes_nothing(client, prospect):
    DeskSetting.put("vm_url:tracy", "https://api.twilio.com/rec/RE9")
    client.post("/api/desk/twilio/voice", data={"CallSid": "CApar3", "To": "+15615550120",
                                                "prospect_id": prospect.id, "amd": "1"})
    with mock.patch("desk_line._client") as cl:
        client.post("/api/desk/twilio/voice/amd?parent=CApar3&va=Tracy",
                    data={"CallSid": "CAchild3", "AnsweredBy": "human"})
        cl.return_value.calls.return_value.update.assert_not_called()
    act = DeskActivity.query.filter_by(twilio_sid="CApar3").one()
    assert act.status == "ringing" and "AMD: human" in act.body
