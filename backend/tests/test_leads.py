"""Incoming leads, all channels, one list — and nothing waits.

A customer who calls gets a good experience; everyone else leaked. Web quotes
and Meta forms never reached the VA, a phone quote that didn't book was never
followed up, a phone booking didn't record its source, and Maya's transfer
summary went out as an SMS instead of onto the screen.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from models import db, User, AbandonedBooking, DeskActivity, DeskSetting, generate_uuid
from models_leads import LeadTouch, QuoteFollowup
import leads


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code",
                                      "GOOGLE_LSA_NUMBER": "+15617820001",
                                      "META_ADS_NUMBER": "+15617820002",
                                      "INBOUND_SOURCE_NUMBERS": ""}):
        yield
    from models_inbound import InboundCall, CallbackRequest
    LeadTouch.query.delete(); QuoteFollowup.query.delete()
    InboundCall.query.delete(); CallbackRequest.query.delete()
    AbandonedBooking.query.filter(AbandonedBooking.email.like("%lead.test%")).delete(synchronize_session=False)
    DeskActivity.query.filter(DeskActivity.phone_digits.like("95455501%")).delete(synchronize_session=False)
    DeskSetting.query.filter(DeskSetting.key.like("maya_ctx:%")).delete(synchronize_session=False)
    User.query.filter(User.email.like("%@lead.test")).delete(synchronize_session=False)
    db.session.commit()


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _call(digits, source="desk", disposition="ringing", minutes_ago=0, answered=None):
    from models_inbound import InboundCall
    r = InboundCall(id=generate_uuid(), call_sid="CA" + generate_uuid()[:18], phone_digits=digits,
                    kind="unknown", disposition=disposition, source=source, answered_by=answered,
                    created_at=_now() - timedelta(minutes=minutes_ago))
    db.session.add(r); db.session.commit()
    return r


def _va(client, path, payload=None):
    base = {"code": "test-code", "va_name": "Tracy"}
    base.update(payload or {})
    return client.post(path, json=base)


# ---------------------------------------------------------------------------
def test_the_number_they_dialled_is_the_channel():
    assert leads.source_for_number("+15617820001") == "google"
    assert leads.source_for_number("(561) 782-0002") == "meta"
    assert leads.source_for_number("+15617824350") == "desk"
    with mock.patch.dict(os.environ, {"INBOUND_SOURCE_NUMBERS": json.dumps({"+15617820009": "google"})}):
        assert leads.source_for_number("5617820009") == "google"


def test_one_list_from_every_channel_paid_first():
    _call("9545550101", source="google", minutes_ago=1)
    _call("9545550102", source="desk", minutes_ago=30)
    db.session.add(AbandonedBooking(id=generate_uuid(), email="web@lead.test", phone="+19545550103",
                                    name="Web Wendy", items=[{"name": "Couch / Sofa"}], estimated_price=210.0,
                                    lead_source="meta", converted=False, created_at=_now() - timedelta(minutes=5)))
    db.session.add(DeskActivity(id=generate_uuid(), prospect_id=None, phone_digits="9545550104", kind="sms",
                                direction="in", body="how much for a fridge and a couch?",
                                created_at=_now() - timedelta(minutes=3)))
    db.session.commit()
    out, broken = leads.collect()
    assert broken == []
    kinds = {l["phone_digits"]: (l["kind"], l["source"]) for l in out}
    assert kinds["9545550101"] == ("call", "google")
    assert kinds["9545550103"] == ("web", "meta") and any("Couch" in (l["what"] or "") for l in out)
    assert kinds["9545550104"] == ("text", "text")
    assert kinds["9545550102"] == ("call", "desk")
    # paid channels sort first
    assert [l["source"] for l in out[:2]] == ["google", "meta"]


def test_a_lead_nobody_touched_gets_one_text_in_the_vas_name_then_a_person():
    _call("9545550110", source="google", minutes_ago=3)          # older than the window
    _call("9545550111", source="google", minutes_ago=0)          # too fresh
    _call("9545550112", source="desk", minutes_ago=5, disposition="answered_by_human", answered="Tracy")
    with mock.patch("desk_line.send_desk_text") as sms:
        sent = leads.speed_to_lead_sweep()
    assert sent == ["9545550110"], "only the untouched, old-enough, unanswered one"
    body = sms.call_args[0][1]
    assert "Tracy" in body and "reached out" in body
    # never a second automatic text — the follow-up is a human
    with mock.patch("desk_line.send_desk_text") as sms2:
        assert leads.speed_to_lead_sweep() == []
    assert sms2.call_count == 0
    # and it escalates into the work queue with a call button
    import work_queue
    item = next(i for i in work_queue.build()["items"] if i["kind"] == "new_lead")
    assert item["phone"] == "(954) 555-0110" and item["actions"][0]["key"] == "lead_touch"


def test_touching_a_lead_takes_it_off_the_clock(client):
    c = _call("9545550120", source="google", minutes_ago=4)
    r = _va(client, "/api/va/leads/touch", {"kind": "call", "ref_id": c.call_sid, "phone": "9545550120"})
    assert r.status_code == 200
    with mock.patch("desk_line.send_desk_text") as sms:
        assert leads.speed_to_lead_sweep() == []
    assert sms.call_count == 0
    assert all(i["kind"] != "new_lead" for i in __import__("work_queue").build()["items"])


def test_google_lead_outcomes_build_the_dispute_list(client):
    spam = _call("9545550130", source="google", minutes_ago=10)
    fit = _call("9545550131", source="google", minutes_ago=10)
    organic = _call("9545550132", source="desk", minutes_ago=10)
    for c, o in ((spam, "spam"), (fit, "booked"), (organic, "spam")):
        assert _va(client, "/api/va/leads/touch", {"kind": "call", "ref_id": c.call_sid,
                                                   "phone": c.phone_digits, "outcome": o}).status_code == 200
    bad = _va(client, "/api/va/leads/touch", {"kind": "call", "ref_id": spam.call_sid, "outcome": "meh"})
    assert bad.status_code == 400
    rows = leads.dispute_list()
    assert [r["phone"] for r in rows] == ["(954) 555-0130"], "only paid Google leads marked spam/not a fit"
    assert rows[0]["days_left"] <= 30
    # booked / spam leads leave the open list
    assert all(l["phone_digits"] not in ("9545550130", "9545550131") for l in leads.collect()[0])
    # the dispute list is manager-only
    assert _va(client, "/api/va/leads/disputes", {}).status_code == 403


def test_quoted_but_not_booked_gets_two_texts_then_a_person():
    leads.schedule_followup("9545550140", "Quoted Quinn", 289.0, items=[{"name": "Sofa"}], va_name="Tracy")
    row = QuoteFollowup.query.filter_by(phone_digits="9545550140").one()
    assert row.step == 0 and row.next_at > _now() + timedelta(hours=1, minutes=50)
    # nothing due yet
    with mock.patch("desk_line.send_desk_text") as sms:
        assert leads.followup_sweep() == []
    # +2h
    row.next_at = _now() - timedelta(minutes=1); db.session.commit()
    with mock.patch("desk_line.send_desk_text") as sms:
        acted = leads.followup_sweep()
    assert acted == [("0140", "step1")] and "289" in sms.call_args[0][1] and "Tracy" in sms.call_args[0][1]
    # +24h
    row.next_at = _now() - timedelta(minutes=1); db.session.commit()
    with mock.patch("desk_line.send_desk_text") as sms:
        assert leads.followup_sweep() == [("0140", "step2")]
    assert "stop bugging you" in sms.call_args[0][1]
    # day 3: no third text — a person decides
    row.next_at = _now() - timedelta(minutes=1); db.session.commit()
    with mock.patch("desk_line.send_desk_text") as sms:
        assert leads.followup_sweep() == [("0140", "queued")]
    assert sms.call_count == 0
    assert leads.day3_followups()[0]["phone"] == "(954) 555-0140"


def test_followups_stop_when_they_book_or_say_stop():
    leads.schedule_followup("9545550150", "Booker Bob", 150.0)
    u = User(id=generate_uuid(), email="bob@lead.test", name="Booker Bob", phone="+19545550150", role="customer")
    db.session.add(u); db.session.commit()
    from models import Job
    db.session.add(Job(id=generate_uuid(), customer_id=u.id, status="confirmed", address="e2e-lead 1 St",
                       total_price=150.0, scheduled_at=_now() + timedelta(days=1)))
    db.session.commit()
    row = QuoteFollowup.query.filter_by(phone_digits="9545550150").one()
    row.next_at = _now() - timedelta(minutes=1); db.session.commit()
    with mock.patch("desk_line.send_desk_text") as sms:
        assert leads.followup_sweep() == [("0150", "booked")]
    assert sms.call_count == 0 and row.stop_reason == "booked"

    leads.schedule_followup("9545550151", "Stopper Sue", 99.0)
    assert leads.stop_followups("+19545550151", "stop") == 1
    assert QuoteFollowup.query.filter_by(phone_digits="9545550151").one().stop_reason == "stop"
    assert leads.schedule_followup("9545550151", "Stopper Sue", 99.0).step == 0, "a fresh quote starts a fresh sequence"


def test_mayas_summary_is_on_screen_for_thirty_minutes():
    assert leads.remember_maya_handoff("+19545550160", "Wants a fridge and a couch gone Saturday, Davie.")
    ex = leads.whois_extras("9545550160")
    assert ex["banner"] == "Transferred from Maya" and "Davie" in ex["maya_context"]["summary"]
    DeskSetting.put("maya_ctx:9545550160", json.dumps({"at": (_now() - timedelta(minutes=45)).isoformat(),
                                                      "summary": "old"}))
    assert leads.whois_extras("9545550160")["maya_context"] is None
    _call("9545550161", source="google")
    assert leads.whois_extras("9545550161")["banner"] == "Google lead — paid"


def test_a_meta_form_becomes_a_lead_the_desk_can_see():
    row = leads.record_form_lead("+19545550170", "Form Fiona", source="meta", items=[{"name": "TV"}])
    assert row is not None
    out, _ = leads.collect()
    l = next(x for x in out if x["phone_digits"] == "9545550170")
    assert l["source"] == "meta" and l["name"] == "Form Fiona" and "TV" in l["what"]


def test_our_own_numbers_and_autoresponders_are_not_leads():
    """First live run listed the toll-free line's own test text and a business
    autoresponder ('Thanks for contacting - ...') as leads — and the sweep
    would have texted them back."""
    for digits, body in (("8444356005", "Desk line test from the Umuve number"),
                         ("9545550180", "Thanks for contacting - The Outdoor Solutions. We'll get back to you."),
                         ("9545550181", "how much for a couch pickup?")):
        db.session.add(DeskActivity(id=generate_uuid(), prospect_id=None, phone_digits=digits, kind="sms",
                                    direction="in", body=body, created_at=_now() - timedelta(minutes=5)))
    db.session.commit()
    phones = {l["phone_digits"] for l in leads.collect()[0]}
    assert "9545550181" in phones
    assert "8444356005" not in phones and "9545550180" not in phones


def test_a_call_the_desk_answered_is_touched_even_without_a_name_on_it():
    _call("9545550190", source="desk", disposition="answered_by_human", minutes_ago=120, answered=None)
    l = next(x for x in leads.collect()[0] if x["phone_digits"] == "9545550190")
    assert l["touched_at"], "spoke to the desk two hours ago — not an untouched lead"
    with mock.patch("desk_line.send_desk_text") as sms:
        assert leads.speed_to_lead_sweep() == []
    assert sms.call_count == 0


def test_the_auto_text_has_an_age_cap():
    """Speed-to-lead is a two-minute reflex, not 'text a two-day-old thread at 9pm'."""
    _call("9545550191", source="desk", minutes_ago=60 * 30)           # 30 hours old
    with mock.patch("desk_line.send_desk_text") as sms:
        assert leads.speed_to_lead_sweep() == []
    assert sms.call_count == 0
    # it still shows in the list and the queue for a person
    assert any(l["phone_digits"] == "9545550191" for l in leads.collect()[0])



def test_the_promise_matches_whether_anyone_is_actually_on_shift():
    """'Calling you in a minute' was sent at 6pm to four people with nobody
    clocked in, because the posted hours were unset and read as always-open.
    The wording keys off a clocked-in human, not the clock."""
    _call("9545550195", source="google", minutes_ago=3)
    with mock.patch("inbound.humans_online", return_value=[]), \
         mock.patch("desk_line.send_desk_text") as sms:
        assert leads.speed_to_lead_sweep() == ["9545550195"]
    assert "first thing" in sms.call_args[0][1] and "in a minute" not in sms.call_args[0][1]

    _call("9545550196", source="google", minutes_ago=3)
    with mock.patch("inbound.humans_online", return_value=["Tracy"]), \
         mock.patch("desk_line.send_desk_text") as sms:
        assert leads.speed_to_lead_sweep() == ["9545550196"]
    assert "in a minute" in sms.call_args[0][1]


def test_the_auto_text_has_a_kill_switch():
    _call("9545550197", source="google", minutes_ago=3)
    with mock.patch.dict(os.environ, {"FEATURE_LEAD_AUTO_TEXT": "false"}), \
         mock.patch("desk_line.send_desk_text") as sms:
        assert leads.speed_to_lead_sweep() == []
    assert sms.call_count == 0
