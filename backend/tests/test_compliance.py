"""Call Desk Phase 2 — compliance (compliance.py): do-not-call registry,
calling-hours window, recording policy, retention, export + erase.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from unittest import mock
from zoneinfo import ZoneInfo

import pytest

import compliance
from compliance import (call_allowed, call_window, compliance_for_card, filter_rows,
                        register_opt_out, run_retention, text_allowed)
from desk_auth import create_desk_user
from models import (db, AuditEvent, CallAttempt, CallProspect, DeskActivity, DeskSetting,
                    DeskTranscriptLine)
from models_compliance import DoNotCall

NY = ZoneInfo("America/New_York")


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {
        "TRIXIE_ASSISTANT_PASSCODE": "test-code", "JWT_SECRET": "unit",
        "TWILIO_AUTH_TOKEN": "", "DESK_TWILIO_NUMBER": "+15615550999",
        "DESK_FORWARD_NUMBER": "+15615550777", "BACKEND_URL": "https://api.test",
    }):
        yield


@pytest.fixture()
def prospect():
    p = CallProspect(tier=1, category="property management", company="Test Property Co",
                     phone="(561) 555-0100", phone_digits="5615550100", city="West Palm Beach",
                     contact_name="Pat Smith", direct_phone="(561) 555-0101", status="queued")
    db.session.add(p)
    db.session.commit()
    return p


@pytest.fixture()
def tokens(client):
    create_desk_user("cva@goumuve.com", "Cara VA", "va", "pw-cva")
    create_desk_user("cmgr@goumuve.com", "Max Manager", "manager", "pw-cmgr")
    va = client.post("/api/desk/login", json={"email": "cva@goumuve.com", "password": "pw-cva"}).get_json()["token"]
    mgr = client.post("/api/desk/login", json={"email": "cmgr@goumuve.com", "password": "pw-cmgr"}).get_json()["token"]
    return {"va": {"Authorization": "Bearer " + va}, "mgr": {"Authorization": "Bearer " + mgr}}


def _va(client, path, payload=None):
    base = {"code": "test-code", "va_name": "Tracy"}
    base.update(payload or {})
    return client.post(path, json=base)


# ------------------------------------------------------------------ DNC registry
def test_dnc_add_kills_prospect_and_audits(client, prospect):
    r = _va(client, "/api/va/compliance/dnc", {"phone": "561-555-0100", "note": "owner said stop calling"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] and body["dnc"]["source"] == "call_request" and body["prospect_id"] == prospect.id
    db.session.refresh(prospect)
    assert prospect.status == "dead" and prospect.last_outcome == "opted_out"
    assert prospect.next_followup_at is None and "DO NOT CALL" in prospect.last_note
    assert prospect.attempts == 1
    assert CallAttempt.query.filter_by(prospect_id=prospect.id, outcome="opted_out").count() == 1
    row = DoNotCall.query.filter_by(phone_digits="5615550100").one()
    assert row.created_by == "Tracy" and row.note == "owner said stop calling"
    ev = AuditEvent.query.filter_by(action="dnc_add").one()
    assert ev.target_id == "5615550100" and ev.meta["prospect_id"] == prospect.id and ev.actor_name == "Tracy"
    # check reports it
    c = _va(client, "/api/va/compliance/check", {"phone": "+1 (561) 555-0100"}).get_json()
    assert c["dnc"] is True and c["source"] == "call_request" and c["since"]
    assert c["text_allowed"] is False and c["call_allowed"] is False
    # adding again is idempotent
    r2 = _va(client, "/api/va/compliance/dnc", {"phone": "5615550100"}).get_json()
    assert r2["already"] is True and DoNotCall.query.count() == 1


def test_dnc_add_unknown_number_and_bad_input(client):
    assert _va(client, "/api/va/compliance/dnc", {"phone": "123"}).status_code == 400
    r = _va(client, "/api/va/compliance/dnc", {"phone": "9545550100"})
    assert r.status_code == 200 and r.get_json()["prospect_id"] is None
    assert DoNotCall.query.filter_by(phone_digits="9545550100").one().source == "call_request"
    assert client.post("/api/va/compliance/dnc", json={"phone": "9545550100"}).status_code == 401


def test_dnc_remove_is_manager_only(client, prospect, tokens):
    _va(client, "/api/va/compliance/dnc", {"phone": "5615550100"})
    assert client.post("/api/va/compliance/dnc-remove", json={"phone": "5615550100"},
                       headers=tokens["va"]).status_code == 403
    assert client.post("/api/va/compliance/dnc-remove", json={"phone": "5615550100"}).status_code == 401
    r = client.post("/api/va/compliance/dnc-remove", json={"phone": "5615550100"}, headers=tokens["mgr"])
    assert r.status_code == 200 and r.get_json()["removed"] == "5615550100"
    assert DoNotCall.query.count() == 0
    db.session.refresh(prospect)
    assert prospect.last_outcome is None and prospect.status == "dead"   # block lifted, not re-queued
    assert text_allowed("5615550100") == (True, "")
    ev = AuditEvent.query.filter_by(action="dnc_remove").one()
    assert ev.actor_name == "Max" and ev.meta["was_source"] == "call_request"
    assert client.post("/api/va/compliance/dnc-remove", json={"phone": "5615550100"},
                       headers=tokens["mgr"]).status_code == 404


def test_stop_text_lands_on_registry_via_webhook(client, prospect):
    with mock.patch("desk_line._client", return_value=None):
        resp = client.post("/api/desk/twilio/sms", data={
            "From": "+15615550100", "To": "+15615550999", "Body": "STOP",
            "NumMedia": "0", "MessageSid": "SMstop1"})
    assert resp.status_code == 200
    row = DoNotCall.query.filter_by(phone_digits="5615550100").one()
    assert row.source == "sms_stop"
    db.session.refresh(prospect)
    assert prospect.status == "dead" and prospect.last_outcome == "opted_out"
    # an unknown sender texting STOP is blocked too
    with mock.patch("desk_line._client", return_value=None):
        client.post("/api/desk/twilio/sms", data={"From": "+19545550123", "Body": "Unsubscribe",
                                                  "NumMedia": "0", "MessageSid": "SMstop2"})
    assert DoNotCall.query.filter_by(phone_digits="9545550123").one().source == "sms_stop"


def test_text_allowed_blocks_and_send_desk_text_returns_none(client, prospect):
    from desk_line import send_desk_text
    register_opt_out("5615550100", "manual", note="by hand")
    db.session.commit()
    ok, why = text_allowed("(561) 555-0100")
    assert ok is False and "do-not-call" in why
    assert text_allowed("12")[0] is False
    with mock.patch("desk_line._client") as cl:
        cl.return_value.messages.create.return_value = mock.Mock(sid="SMx")
        assert send_desk_text("5615550100", "hello?", prospect=prospect) is None
        cl.return_value.messages.create.assert_not_called()
        # a clean number still goes out
        assert send_desk_text("5615550200", "hello") == "SMx"
    assert DeskActivity.query.filter_by(phone_digits="5615550100", direction="out").count() == 0
    # legacy opt-outs (prospect flag, no registry row) are honored too
    other = CallProspect(tier=2, category="x", company="Legacy", phone="5615550300",
                         phone_digits="5615550300", last_outcome="opted_out", status="dead")
    db.session.add(other); db.session.commit()
    assert text_allowed("5615550300") == (False, "they opted out")


def test_filter_rows_drops_dnc_numbers(client):
    register_opt_out("5615550100", "import")
    db.session.commit()
    rows = [{"company": "A", "phone": "(561) 555-0100"}, {"company": "B", "phone": "561-555-0200"},
            {"company": "C", "phone": ""}, {"company": "D", "phone": "+1 561 555 0100"}]
    out = filter_rows(rows)
    assert [r["company"] for r in out] == ["B", "C"]
    assert filter_rows([]) == []


# ------------------------------------------------------------------ calling window
def test_call_window_open_and_closed_with_frozen_clock(client):
    mon_10 = datetime(2026, 9, 7, 10, 0, tzinfo=NY)          # Monday
    w = call_window(mon_10)
    assert w["open"] is True and w["closes_label"] == "8:00 PM" and w["days"] == [1, 2, 3, 4, 5, 6]
    assert w["opens_at"].startswith("2026-09-07T08:00:00") and w["closes_at"].startswith("2026-09-07T20:00:00")
    sat_21 = datetime(2026, 9, 12, 21, 0, tzinfo=NY)         # Saturday after close → Monday
    w = call_window(sat_21)
    assert w["open"] is False and w["opens_label"] == "Mon 8:00 AM"
    assert w["opens_at"].startswith("2026-09-14T08:00:00")
    assert w["note"] == "Calling window is closed until Mon 8:00 AM — texting still works."
    sun = datetime(2026, 9, 13, 12, 0, tzinfo=NY)
    assert call_window(sun)["open"] is False and call_window(sun)["opens_label"] == "Mon 8:00 AM"
    tue_6 = datetime(2026, 9, 8, 6, 30, tzinfo=NY)           # same day, before open
    w = call_window(tue_6)
    assert w["open"] is False and w["opens_label"] == "8:00 AM"
    # UTC input is converted (Mon 23:30 UTC = Mon 19:30 NY → open)
    assert call_window(datetime(2026, 9, 7, 23, 30, tzinfo=timezone.utc))["open"] is True
    # env override: weekdays 9-17
    with mock.patch.dict(os.environ, {"DESK_CALL_HOURS": "09:00-17:00", "DESK_CALL_DAYS": "1-5"}):
        assert call_window(datetime(2026, 9, 12, 10, 0, tzinfo=NY))["open"] is False   # Saturday
        assert call_window(datetime(2026, 9, 11, 16, 59, tzinfo=NY))["open"] is True
        assert call_window(datetime(2026, 9, 11, 17, 0, tzinfo=NY))["open"] is False
    with mock.patch.dict(os.environ, {"DESK_CALL_DAYS": "garbage"}):
        assert call_window(mon_10)["days"] == [1, 2, 3, 4, 5, 6]


def test_window_endpoint_and_call_allowed(client, prospect):
    with mock.patch.object(compliance, "_local_now", return_value=datetime(2026, 9, 13, 12, 0, tzinfo=NY)):
        r = _va(client, "/api/va/compliance/window")
        assert r.status_code == 200
        b = r.get_json()
        assert b["open"] is False and b["opens_label"] == "Mon 8:00 AM" and b["tz"] == "America/New_York"
        ok, why = call_allowed("5615550100")
        assert ok is False and "closed until Mon 8:00 AM" in why
        card = compliance_for_card(prospect)
        assert card == {"dnc": False, "dnc_source": None, "window_open": False,
                        "window_note": "Calling window is closed until Mon 8:00 AM — texting still works."}
    with mock.patch.object(compliance, "_local_now", return_value=datetime(2026, 9, 7, 10, 0, tzinfo=NY)):
        assert call_allowed("5615550100") == (True, "")
        register_opt_out("5615550100", "manual"); db.session.commit()
        assert call_allowed("5615550100")[0] is False
        assert compliance_for_card(prospect)["dnc"] is True
    assert client.post("/api/va/compliance/window", json={}).status_code == 401


def test_card_payload_carries_compliance(client, prospect):
    with mock.patch.object(compliance, "_local_now", return_value=datetime(2026, 9, 7, 10, 0, tzinfo=NY)):
        r = _va(client, "/api/va/calls/next")
    assert r.status_code == 200
    card = r.get_json()["card"]
    assert card["id"] == prospect.id
    assert card["compliance"] == {"dnc": False, "dnc_source": None, "window_open": True,
                                  "window_note": "Calling window is open until 8:00 PM."}


# ------------------------------------------------------------------ policy
def test_policy_endpoint(client):
    r = _va(client, "/api/va/compliance/policy")
    assert r.status_code == 200
    b = r.get_json()
    assert b["recording_notice"] is True and "FL" in b["two_party_states"]
    assert b["notice_text"] == "This call may be recorded for quality."
    assert "records the call" in b["desk_note"] and b["notice_text"] in b["desk_note"]
    with mock.patch.dict(os.environ, {"DESK_TWO_PARTY_STATES": "fl, ca"}):
        assert _va(client, "/api/va/compliance/policy").get_json()["two_party_states"] == ["FL", "CA"]


# ------------------------------------------------------------------ retention
def test_retention_deletes_only_what_it_should(client, prospect, tokens):
    now = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
    old = (now - timedelta(days=500)).replace(tzinfo=None)
    mid = (now - timedelta(days=200)).replace(tzinfo=None)
    fresh = (now - timedelta(days=5)).replace(tzinfo=None)
    db.session.add_all([
        DeskTranscriptLine(call_sid="CA1", prospect_id=prospect.id, track="them", text="old", seq=0, created_at=old),
        DeskTranscriptLine(call_sid="CA1", prospect_id=prospect.id, track="them", text="mid", seq=1, created_at=mid),
        DeskTranscriptLine(call_sid="CA2", prospect_id=prospect.id, track="va", text="fresh", seq=0, created_at=fresh),
        DeskActivity(prospect_id=prospect.id, phone_digits="5615550100", kind="call", direction="out",
                     body="old vm transcript", recording_url="https://r/old", status="completed", created_at=old),
        DeskActivity(prospect_id=prospect.id, phone_digits="5615550100", kind="call", direction="in",
                     body="mid vm", recording_url="https://r/mid", status="voicemail", created_at=mid),
        DeskActivity(prospect_id=prospect.id, phone_digits="5615550100", kind="call", direction="out",
                     body="fresh", status="completed", created_at=fresh),
        DeskActivity(prospect_id=prospect.id, phone_digits="5615550100", kind="sms", direction="in",
                     body="old text stays", status="received", created_at=old),
        AuditEvent(action="old_thing", created_at=old), AuditEvent(action="mid_thing", created_at=mid),
    ])
    db.session.commit()
    summary = run_retention(now=now)
    assert summary["transcripts_deleted"] == 2 and summary["call_bodies_blanked"] == 2 and summary["audit_deleted"] == 1
    assert [t.text for t in DeskTranscriptLine.query.all()] == ["fresh"]
    calls = DeskActivity.query.filter_by(kind="call").order_by(DeskActivity.created_at.asc()).all()
    assert len(calls) == 3                                              # rows kept
    assert [(c.body, c.recording_url) for c in calls] == [(None, None), (None, None), ("fresh", None)]
    assert DeskActivity.query.filter_by(kind="sms").one().body == "old text stays"
    actions = {e.action for e in AuditEvent.query.all()}
    assert "old_thing" not in actions and "mid_thing" in actions and "retention_run" in actions
    assert json.loads(DeskSetting.get("retention:last"))["transcripts_deleted"] == 2
    # manager reads the last run; a VA can't
    assert client.get("/api/admin/compliance/retention", headers=tokens["va"]).status_code == 403
    r = client.get("/api/admin/compliance/retention", headers=tokens["mgr"]).get_json()
    assert r["last"]["audit_deleted"] == 1 and r["config"] == {"transcript_days": 90, "call_body_days": 180, "audit_days": 400}
    # the scheduler wrapper runs it under an app context and swallows nothing silently
    from scheduler import _run_retention
    from flask import current_app
    _run_retention(current_app._get_current_object())
    assert AuditEvent.query.filter_by(action="retention_run").count() == 2


# ------------------------------------------------------------------ export + erase
def test_export_bundle_shape(client, prospect, tokens):
    db.session.add_all([
        CallAttempt(prospect_id=prospect.id, outcome="voicemail", va_name="Tracy"),
        DeskActivity(prospect_id=prospect.id, phone_digits="5615550100", kind="sms", direction="out", body="hi"),
        DeskActivity(prospect_id=None, phone_digits="5615550101", kind="call", direction="in", status="voicemail"),
        DeskTranscriptLine(call_sid="CA9", prospect_id=prospect.id, track="them", text="we might", seq=0),
    ])
    db.session.commit()
    _va(client, "/api/va/calls/log", {"prospect_id": prospect.id, "outcome": "interested"})   # audits "outcome"
    _va(client, "/api/va/compliance/dnc", {"phone": "5615550100"})
    assert client.get("/api/admin/compliance/export?phone=5615550100", headers=tokens["va"]).status_code == 403
    assert client.get("/api/admin/compliance/export?phone=12", headers=tokens["mgr"]).status_code == 400
    r = client.get("/api/admin/compliance/export?phone=(561)%20555-0100", headers=tokens["mgr"])
    assert r.status_code == 200
    b = r.get_json()
    assert set(b) == {"phone_digits", "generated_at", "prospect", "attempts", "activities",
                      "transcript_lines", "dnc", "audit_events"}
    assert b["prospect"]["id"] == prospect.id and b["dnc"]["source"] == "call_request"
    assert {a["outcome"] for a in b["attempts"]} == {"voicemail", "interested", "opted_out"}
    assert len(b["activities"]) == 2                   # front desk + direct-line activity
    assert b["transcript_lines"][0]["text"] == "we might" and b["transcript_lines"][0]["call_sid"] == "CA9"
    assert {e["action"] for e in b["audit_events"]} >= {"outcome", "dnc_add"}
    assert AuditEvent.query.filter_by(action="export").one().target_id == "5615550100"
    # a number we hold nothing on still returns a valid (empty) bundle
    e = client.get("/api/admin/compliance/export?phone=9545550999", headers=tokens["mgr"]).get_json()
    assert e["prospect"] is None and e["activities"] == [] and e["dnc"] is None


def test_erase_anonymizes_blocks_and_audits(client, prospect, tokens):
    db.session.add_all([
        CallAttempt(prospect_id=prospect.id, outcome="voicemail"),
        DeskActivity(prospect_id=prospect.id, phone_digits="5615550100", kind="sms", direction="in", body="secret"),
        DeskActivity(prospect_id=None, phone_digits="5615550101", kind="call", direction="in"),
        DeskTranscriptLine(call_sid="CA9", prospect_id=prospect.id, track="them", text="secret", seq=0),
    ])
    prospect.email = "pat@example.com"; prospect.last_note = "notes"
    db.session.commit()
    pid = prospect.id
    assert client.post("/api/admin/compliance/erase", json={"phone": "5615550100", "confirm": "ERASE"},
                       headers=tokens["va"]).status_code == 403
    assert client.post("/api/admin/compliance/erase", json={"phone": "5615550100", "confirm": "yes"},
                       headers=tokens["mgr"]).status_code == 400
    r = client.post("/api/admin/compliance/erase", json={"phone": "5615550100", "confirm": "ERASE"},
                    headers=tokens["mgr"])
    assert r.status_code == 200
    b = r.get_json()
    assert b["ok"] and b["prospect_id"] == pid and b["erased"] == {"activities": 2, "transcripts": 1, "attempts": 1}
    p = db.session.get(CallProspect, pid)
    assert p.company == "Erased" and p.phone == "" and p.phone_digits == "5615550100"
    assert p.status == "dead" and p.last_outcome == "erased"
    for f in ("city", "contact_name", "why", "angle", "email", "direct_phone", "last_note", "next_followup_at"):
        assert getattr(p, f) is None, f
    assert DeskActivity.query.count() == 0 and DeskTranscriptLine.query.count() == 0 and CallAttempt.query.count() == 0
    assert {d.phone_digits: d.source for d in DoNotCall.query.all()} == {"5615550100": "erase", "5615550101": "erase"}
    ev = AuditEvent.query.filter_by(action="erase").one()
    assert ev.target_id == "5615550100" and ev.meta["prospect_id"] == pid and ev.actor_name == "Max"
    # dedupe still blocks a re-import, and so does the registry
    from va_calls import merge_rows
    assert merge_rows([{"company": "Test Property Co", "phone": "5615550100"}]) == (0, 1, 0)
    assert filter_rows([{"company": "Test Property Co", "phone": "5615550100"}]) == []


# ------------------------------------------------------------------ desk wiring
def test_desk_page_loads_compliance_script_before_calls_js(client):
    html = client.get("/va/calls").data.decode()
    a = html.index('<script src="/static/desk-compliance.js?v=1"></script>')
    b = html.index('<script src="/va/calls.js?v=')
    assert a < b
    js = client.get("/static/desk-compliance.js")
    assert js.status_code == 200
    src = js.data.decode()
    for needle in ("/api/va/compliance/dnc", "/api/va/compliance/window", "/api/va/compliance/policy",
                   "__deskCallsBlocked", "desk:refresh", "They asked not to be called", "DO NOT CALL"):
        assert needle in src, needle
    assert client.get("/static/desk-compliance.css").status_code == 200
