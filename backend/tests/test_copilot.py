"""Copilot: transcription TwiML + consent whisper, transcript ingestion, cues, summary."""
import json
import os
from unittest import mock

import pytest

from models import db, CallProspect, DeskActivity, DeskTranscriptLine
from copilot import match_objection, cue_for, summarize


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code", "TWILIO_AUTH_TOKEN": "",
                                      "DESK_TWILIO_NUMBER": "+15615550999", "BACKEND_URL": "https://api.test",
                                      "ANTHROPIC_API_KEY": ""}):
        yield
    DeskTranscriptLine.query.delete(); DeskActivity.query.delete(); CallProspect.query.delete(); db.session.commit()


@pytest.fixture()
def prospect():
    p = CallProspect(tier=1, category="property management", company="Palm Coast PM",
                     phone="(561) 555-0142", phone_digits="5615550142", city="West Palm Beach")
    db.session.add(p); db.session.commit()
    return p


def _va(client, path, payload):
    base = {"code": "test-code", "va_name": "Tracy"}
    base.update(payload)
    return client.post(path, json=base)


def _content(client, parent, track, text, seq, final="true"):
    return client.post("/api/desk/twilio/transcript-rt?parent=" + parent, data={
        "TranscriptionEvent": "transcription-content", "CallSid": parent, "Track": track,
        "Final": final, "SequenceId": str(seq),
        "TranscriptionData": json.dumps({"transcript": text, "confidence": 0.9})})


def test_copilot_twiml_starts_transcription_and_whispers_consent(client, prospect):
    xml = client.post("/api/desk/twilio/voice", data={"CallSid": "CAcp", "To": "+15615550142",
                                                       "prospect_id": prospect.id, "va_name": "Tracy",
                                                       "copilot": "1"}).data.decode()
    assert xml.index("<Start><Transcription") < xml.index("<Dial")
    assert 'track="both_tracks"' in xml and "transcript-rt?parent=CAcp" in xml and 'name="desk-CAcp"' in xml
    assert 'url="https://api.test/api/desk/twilio/voice/whisper"' in xml
    plain = client.post("/api/desk/twilio/voice", data={"CallSid": "CAnc", "To": "+15615550142",
                                                         "prospect_id": prospect.id}).data.decode()
    assert "<Transcription" not in plain and "whisper" not in plain
    w = client.post("/api/desk/twilio/voice/whisper", data={}).data.decode()
    assert "recorded" in w


def test_transcript_ingest_and_live_cue(client, prospect):
    client.post("/api/desk/twilio/voice", data={"CallSid": "CAcp", "To": "+15615550142",
                                                "prospect_id": prospect.id, "copilot": "1"})
    assert client.post("/api/desk/twilio/transcript-rt?parent=CAcp",
                       data={"TranscriptionEvent": "transcription-started", "CallSid": "CAcp"}).status_code == 204
    _content(client, "CAcp", "inbound_track", "Hi, this is Tracy with Umuve.", 1)
    _content(client, "CAcp", "outbound_track", "partial words", 2, final="false")      # ignored
    _content(client, "CAcp", "outbound_track", "Yeah we already have a guy for that.", 3)
    r = _va(client, "/api/va/desk/transcript", {"prospect_id": prospect.id, "after_seq": -1}).get_json()
    assert r["call_sid"] == "CAcp" and [l["track"] for l in r["lines"]] == ["va", "them"]
    assert r["cue"]["say"] == "We already have a guy." and "Keep him" in r["cue"]["reply"]
    assert r["cue"]["quote"].startswith("Yeah we already")
    # incremental fetch returns only new lines
    _content(client, "CAcp", "outbound_track", "How much does it cost?", 4)
    r2 = _va(client, "/api/va/desk/transcript", {"prospect_id": prospect.id, "after_seq": 3}).get_json()
    assert [l["seq"] for l in r2["lines"]] == [4] and r2["total"] == 3
    assert r2["cue"]["say"] == "How much?"
    line = DeskTranscriptLine.query.filter_by(seq=3).one()
    assert line.prospect_id == prospect.id


def test_triggers_by_side():
    assert match_objection("we use a dumpster for that", "demand") == "We use a dumpster."
    assert match_objection("what's the catch, what do you take", "supply") == "What's the catch? What do you take?"
    assert match_objection("I don't really do apps", "supply") == "I don't do apps."
    assert match_objection("sounds great", "demand") is None
    kit = {"objections": [{"say": "Call me back later.", "reply": "Sure. When's better?"}]}
    cue = cue_for([{"track": "va", "text": "call me back"}, {"track": "them", "text": "can you call me back later"}], kit, "demand")
    assert cue and cue["reply"].startswith("Sure")
    assert cue_for([{"track": "va", "text": "call me back later"}], kit, "demand") is None


def test_summarize_heuristic_without_api_key(client, prospect):
    client.post("/api/desk/twilio/voice", data={"CallSid": "CAs", "To": "+15615550142",
                                                "prospect_id": prospect.id, "copilot": "1"})
    _content(client, "CAs", "inbound_track", "Hi it's Tracy with Umuve.", 1)
    _content(client, "CAs", "outbound_track", "Sure, send me the info and call me back next week.", 2)
    r = _va(client, "/api/va/desk/summarize", {"prospect_id": prospect.id}).get_json()
    assert r["lines"] == 2 and r["reason"] == "heuristic"
    assert r["outcome"] == "callback" and "send me the info" in r["note"]
    act = DeskActivity.query.filter_by(twilio_sid="CAs").one()
    assert act.body.startswith("Transcript:") and "[them]" in act.body
    empty = _va(client, "/api/va/desk/summarize", {"prospect_id": prospect.id}).get_json()
    assert empty["lines"] == 2


def test_summarize_uses_claude_when_configured(prospect):
    fake = mock.MagicMock()
    fake.messages.create.return_value = mock.MagicMock(content=[mock.MagicMock(
        text='{"outcome": "interested", "note": "Wants a rate card for 3 buildings; send Tuesday.", "callback": null}')])
    with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k"}), \
         mock.patch("anthropic.Anthropic", return_value=fake):
        r = summarize([{"track": "them", "text": "send me a rate card for our three buildings"}], prospect, "demand")
    assert r["reason"] == "claude" and r["outcome"] == "interested" and "rate card" in r["note"]
    assert "Palm Coast PM" in fake.messages.create.call_args.kwargs["messages"][0]["content"]
