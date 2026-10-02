"""Close Desk: a win is a dated next step, texts go only where they land,
the queue follows the hours that connect, and bots don't bury people.

Context (1 Oct 2026): 124 "interested" / 0 jobs. 62 of 93 win logs had no
call behind them, 90 had no note, 27% of texts bounced, and "interested"
calls all ended with "can I leave a card on file?" These tests hold the
rules that replace that.
"""
import os
from datetime import datetime, timezone
from unittest import mock

import pytest

import close_desk
from models import db, CallProspect, DeskSetting


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code",
                                      "TWILIO_ACCOUNT_SID": "AC_test", "TWILIO_AUTH_TOKEN": "tok"}):
        yield


# --- required fields -----------------------------------------------------------
def test_packet_needs_a_named_person_and_their_own_line():
    assert close_desk.missing_for("packet_requested", {}) == ["the person's name", "their role",
                                                              "a cell number or their own email"]
    assert close_desk.missing_for("packet_requested", {"contact_name": "Dana", "role": "community_manager",
                                                       "email": "info@thelofts.com"}) == \
        ["their own email, not a shared mailbox like info@"]
    assert close_desk.missing_for("packet_requested", {"contact_name": "Dana", "role": "community_manager",
                                                       "cell": "(561) 555-0101"}) == []
    assert close_desk.missing_for("packet_requested", {"contact_name": "Dana", "role": "maintenance_supervisor",
                                                       "email": "dana.k@thelofts.com"}) == []


def test_callback_needs_name_role_and_time():
    assert close_desk.missing_for("callback", {"preset": "tomorrow_am"}) == ["who you're calling back", "their role"]
    assert close_desk.missing_for("callback", {"contact_name": "Luis", "role": "maintenance_supervisor",
                                               "preset": "tomorrow_am"}) == []


def test_booked_needs_a_real_booking():
    assert close_desk.missing_for("booked", {}) and "Book it" in close_desk.missing_for("booked", {})[0]
    assert close_desk.missing_for("booked", {"job_id": "job-1"}) == []


def test_bookkeeping_outcomes_need_nothing():
    for o in ("vendor_listed", "no_need_now", "voicemail", "no_answer", "not_interested", "dnc", "bad_number", "skip"):
        assert close_desk.missing_for(o, {}) == []


# --- the log endpoint enforces it ---------------------------------------------
@pytest.fixture()
def prospect(app):
    p = CallProspect(tier=1, category="apartment complex", company="Sunrise Lofts",
                     phone="5615550199", phone_digits="5615550199", city="West Palm Beach")
    db.session.add(p); db.session.commit()
    yield p
    db.session.delete(p); db.session.commit()


def _log(client, body):
    return client.post("/api/va/calls/log", json=dict({"code": "test-code", "va_name": "Tracy"}, **body))


def test_interested_and_sent_link_are_retired(client, prospect):
    for o in ("interested", "sent_link"):
        r = _log(client, {"prospect_id": prospect.id, "outcome": o})
        assert r.status_code == 400 and r.get_json()["code"] == "retired_outcome"


def test_log_refuses_an_empty_packet_and_names_what_is_missing(client, prospect):
    r = _log(client, {"prospect_id": prospect.id, "outcome": "packet_requested"})
    assert r.status_code == 400
    assert r.get_json()["code"] == "missing_fields"
    assert "the person's name" in r.get_json()["missing"]


def test_packet_saves_the_person_schedules_the_48h_call_and_texts_the_cell(client, prospect):
    with mock.patch("va_calls.send_desk_text", create=True) as _unused, \
         mock.patch("desk_line.send_desk_text", return_value="SM123") as send, \
         mock.patch.object(close_desk, "line_type", return_value="mobile"):
        r = _log(client, {"prospect_id": prospect.id, "outcome": "packet_requested", "contact_name": "Dana Ruiz",
                          "role": "community_manager", "cell": "561-555-0102", "send_text": True})
    assert r.status_code == 200, r.get_json()
    db.session.refresh(prospect)
    assert prospect.contact_name == "Dana Ruiz"
    assert prospect.direct_phone == "+15615550102"
    assert prospect.status == "interested" and prospect.next_followup_at is not None
    assert prospect.last_note.startswith("[community_manager]")
    assert send.called
    to, body = send.call_args[0][0], send.call_args[0][1]
    assert to == "+15615550102"                      # her cell, not the office line
    assert len(body) <= 250 and "Dana" in body and "?" in body and "STOP" in body


def test_packet_text_is_blocked_on_a_landline(client, prospect):
    with mock.patch("desk_line.send_desk_text", return_value="SM123") as send, \
         mock.patch.object(close_desk, "line_type", return_value="landline"):
        r = _log(client, {"prospect_id": prospect.id, "outcome": "packet_requested", "contact_name": "Dana",
                          "role": "community_manager", "cell": "561-555-0103", "send_text": True})
    assert r.status_code == 200
    assert not send.called
    assert "landline" in r.get_json()["text_reason"]


def test_no_need_now_and_dnc(client, prospect):
    r = _log(client, {"prospect_id": prospect.id, "outcome": "no_need_now"})
    assert r.status_code == 200
    db.session.refresh(prospect)
    assert prospect.next_followup_at is not None and prospect.status != "dead"
    r = _log(client, {"prospect_id": prospect.id, "outcome": "dnc"})
    db.session.refresh(prospect)
    assert prospect.status == "dead" and prospect.last_outcome == "dnc"


# --- line type cache -----------------------------------------------------------
def test_line_type_is_looked_up_once_then_cached(app):
    DeskSetting.query.filter_by(key=close_desk.LINE_CACHE_PREFIX + "5615550104").delete(); db.session.commit()
    calls = []
    def fake(d): calls.append(d); return "landline"
    assert close_desk.line_type("(561) 555-0104", lookup=fake) == "landline"
    assert close_desk.line_type("5615550104", lookup=fake) == "landline"
    assert calls == ["5615550104"]
    assert close_desk.textable("5615550104", lookup=fake)[0] is False


# --- the text ------------------------------------------------------------------
def test_packet_text_is_short_signed_and_ends_in_two_slots():
    p = CallProspect(company="X", contact_name="Marcus Lee", phone="5615550105", phone_digits="5615550105")
    t = close_desk.packet_text(p, va_name="Tracy Jamesyoung", rate_card_url="https://u.mv/r/abc")
    assert t.startswith("Marcus — Tracy from Umuve")
    assert "https://u.mv/r/abc" in t and " or " in t and t.rstrip().endswith("opt out.")
    assert len(t) <= 250


# --- the window ----------------------------------------------------------------
def _et(y, m, d, h):
    from zoneinfo import ZoneInfo
    return datetime(y, m, d, h, 15, tzinfo=ZoneInfo("America/New_York"))


def test_calling_window_follows_the_hours_that_connect():
    assert close_desk.calling_window(_et(2026, 10, 6, 10))["side"] == "demand"     # Tue 10am
    assert close_desk.calling_window(_et(2026, 10, 6, 12))["side"] == "inbox"      # lunch
    assert close_desk.calling_window(_et(2026, 10, 6, 14))["side"] == "demand"     # 2pm
    assert close_desk.calling_window(_et(2026, 10, 6, 16))["side"] == "supply"     # 4pm
    assert close_desk.calling_window(_et(2026, 10, 10, 10))["side"] == "any"       # Saturday


def test_month_end_priority_window():
    assert close_desk.month_end_priority(_et(2026, 10, 29, 10)) is True    # Thu, 2nd-to-last biz day
    assert close_desk.month_end_priority(_et(2026, 11, 3, 10)) is True     # 3rd of the month
    assert close_desk.month_end_priority(_et(2026, 10, 14, 10)) is False
    assert close_desk.is_multifamily("Apartment complex") and not close_desk.is_multifamily("Restaurant")


# --- bots ----------------------------------------------------------------------
def test_bot_replies_are_flagged_people_are_not():
    bots = ["Thanks for contacting Exchange Lofts. Reply START to receive SMS updates about the inquiries, tours, and services.",
            "Reply YES to consent to text messages from The Enclave Apartments and to agree to our Terms",
            "We're sorry, text messages can't be received by this phone number.",
            "Thank you for contacting The Point. A staff member will respond to you shortly.",
            "Hi again. Saw that you were interested in The District and thought I'd check in. Want to set up a tour? I'm here to help!"]
    people = ["Need price", "stop", "Send me an email please. michael@tpgproperty.com", "YES", "Ok",
              "How much for a sofa and two mattresses at 1200 S Dixie?"]
    assert all(close_desk.is_bot_reply(b) for b in bots)
    assert not any(close_desk.is_bot_reply(p) for p in people)


# --- the kit -------------------------------------------------------------------
def test_kit_has_the_structure_and_the_forbidden_lines(app, prospect):
    from call_kit import build_kit
    k = build_kit(prospect, va_name="Tracy Jamesyoung")
    t = k["track"]
    assert "U-M-U-V-E" in t["opener"] and "recorded" in t["opener"] and "reason for my call" in t["opener"]
    assert "maintenance supervisor" in t["role"].lower()
    assert "sitting in a unit" in t["trigger"]
    assert "$119" in t["price"]
    assert " or " in t["close"] and "which works" in t["close"]
    assert "cell" in t["capture"]
    assert any("card on file" in f["line"] for f in t["forbidden"])
    says = [o["say"] for o in k["objections"]]
    assert "We already have someone." in says and "Corporate approves vendors." in says and "I'm not the right person." in says
    have = [o for o in k["objections"] if o["say"] == "We already have someone."][0]["reply"]
    assert "How's that working out" in have and "one unit" in have


def test_copilot_cues_map_the_new_objections_and_watch_the_caller():
    from copilot import match_objection, caller_cues
    assert match_objection("we already use waste management for that") == "We already have someone."
    assert match_objection("our maintenance guys handle it") == "Maintenance handles it."
    assert match_objection("corporate has to approve any vendor") == "Corporate approves vendors."
    assert match_objection("i'm just the leasing agent, i don't handle that") == "I'm not the right person."
    lines = [{"track": "va", "text": "Hi this is Tracy with you move, the reason for my call is"},
             {"track": "them", "text": "you move? who is this"}]
    cues = {c["cue"] for c in caller_cues(lines, seconds_in=25)}
    assert cues == {"spell it", "disclosure"}
    good = [{"track": "va", "text": "This is Tracy, the booking desk for Umuve, U-M-U-V-E. This call's recorded for quality."}]
    assert caller_cues(good, seconds_in=25) == []
    assert caller_cues(lines, seconds_in=5) == [c for c in caller_cues(lines, seconds_in=5) if c["cue"] == "spell it"]


# --- callbacks need a person --------------------------------------------------
def test_callback_endpoint_needs_who_and_role(client, prospect):
    from models import DeskActivity
    base = {"code": "test-code", "va_name": "Tracy", "prospect_id": prospect.id, "preset": "tomorrow_am"}
    r = client.post("/api/va/calls/callback", json=base)
    assert r.status_code == 400 and r.get_json()["code"] == "missing_fields"
    # Name and role, but nobody picked up: not a callback. (2 Oct: four
    # "David, owner" callbacks on numbers no call had reached.)
    r = client.post("/api/va/calls/callback", json=dict(base, contact_name="David", role="owner"))
    assert r.status_code == 400 and r.get_json()["code"] == "no_conversation"
    db.session.add(DeskActivity(prospect_id=prospect.id, phone_digits=prospect.phone_digits, kind="call",
                                direction="out", status="completed", duration=6))     # a ring-out
    db.session.commit()
    r = client.post("/api/va/calls/callback", json=dict(base, contact_name="David", role="owner"))
    assert r.status_code == 400 and r.get_json()["code"] == "no_conversation"
    db.session.add(DeskActivity(prospect_id=prospect.id, phone_digits=prospect.phone_digits, kind="call",
                                direction="out", status="completed", duration=95))    # a conversation
    db.session.commit()
    r = client.post("/api/va/calls/callback", json=dict(base, contact_name="Luis Ortega", role="maintenance_supervisor"))
    assert r.status_code == 200, r.get_json()
    db.session.refresh(prospect)
    assert prospect.contact_name == "Luis Ortega" and prospect.last_outcome == "callback"
    assert prospect.last_note.startswith("[maintenance_supervisor]")
