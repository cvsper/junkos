"""Phase 6 — inbound customer calls on the Call Desk.

Inbound calls ring every clocked-in VA (desk-<slug>) plus the legacy desk
identity and the forward cell; nobody answering (or after hours) hands the
caller to Maya, or voicemail when the flag is off. The desk identifies the
caller, quotes with the pricing engine, books through the dispatch desk's
log-job (pay link texted), texts quotes, schedules callbacks, and a manager
sees the numbers.
"""
import os
from datetime import datetime, timedelta, timezone
from unittest import mock
from zoneinfo import ZoneInfo

import pytest

from models import db, CallProspect, DeskActivity, DeskSetting, User, Job, VaShift, AuditEvent, generate_uuid
from models_inbound import InboundCall, CallbackRequest
import inbound

FL = ZoneInfo("America/New_York")


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {
        "TRIXIE_ASSISTANT_PASSCODE": "test-code",
        "TWILIO_AUTH_TOKEN": "",
        "DESK_TWILIO_NUMBER": "+15615550999",
        "DESK_FORWARD_NUMBER": "+15615550777",
        "BACKEND_URL": "https://api.test",
        "INBOUND_HUMAN_HOURS": "08:00-20:00",
        "MAYA_NUMBER": "+15619441636",
        "FEATURE_INBOUND_CUSTOMERS": "on",
        "FEATURE_MAYA_FALLBACK": "on",
    }):
        yield
    for m in (InboundCall, CallbackRequest, DeskActivity, VaShift, CallProspect, AuditEvent, DeskSetting):
        m.query.delete()
    db.session.commit()


def _va(client, path, payload, name="Tracy"):
    base = {"code": "test-code", "va_name": name}
    base.update(payload)
    return client.post(path, json=base)


def _clock_in(name):
    db.session.add(VaShift(va_name=name, started_at=datetime.now(timezone.utc).replace(tzinfo=None)))
    db.session.commit()


def _at(hour):
    """Business-local clock pinned to today at `hour`."""
    return mock.patch("inbound._now_local",
                      return_value=datetime(2026, 9, 9, hour, 30, tzinfo=FL))


def _customer(name="Jane Rivera", phone="+15615550142"):
    u = User(id=generate_uuid(), name=name, phone=phone, role="customer",
             email="{}@test.local".format(generate_uuid()[:8]))
    db.session.add(u)
    db.session.flush()
    j = Job(id=generate_uuid(), customer_id=u.id, status="completed", address="9 Palm Way, Lake Worth",
            total_price=134.57, confirmation_code=generate_uuid()[:8].upper(),
            created_at=datetime(2026, 7, 1, 12, 0))
    db.session.add(j)
    db.session.commit()
    return u


# ----------------------------------------------------------------- TwiML
def test_inbound_rings_each_clocked_in_va_plus_desk_and_cell(client):
    _clock_in("Tracy Jamesyoung")
    _clock_in("Damien")
    with _at(10):
        resp = client.post("/api/desk/twilio/voice/inbound", data={
            "CallSid": "CAp6a", "From": "+15615550142", "To": "+15615550999"})
    xml = resp.data.decode()
    assert "Thanks for calling Umuve" in xml
    assert "<Client>desk-tracy-jamesyoung</Client>" in xml
    assert "<Client>desk-damien</Client>" in xml
    assert "<Client>desk</Client>" in xml
    assert "<Number>+15615550777</Number>" in xml
    assert 'timeout="20"' in xml
    assert "/api/desk/twilio/voice/after-in" in xml
    row = InboundCall.query.filter_by(call_sid="CAp6a").one()
    assert row.kind == "unknown" and row.disposition == "ringing" and row.in_hours == 1
    assert DeskActivity.query.filter_by(twilio_sid="CAp6a").one().status == "ringing"


def test_inbound_outside_hours_goes_straight_to_maya(client):
    _clock_in("Tracy")
    with _at(22):
        resp = client.post("/api/desk/twilio/voice/inbound", data={
            "CallSid": "CAp6b", "From": "+15615550142"})
    xml = resp.data.decode()
    assert "<Client>" not in xml
    assert "Connecting you to our booking line" in xml
    assert "<Number>+15619441636</Number>" in xml
    assert "/api/desk/twilio/voice/after-maya" in xml
    assert DeskActivity.query.filter_by(twilio_sid="CAp6b").one().status == "to_maya"
    assert InboundCall.query.filter_by(call_sid="CAp6b").one().disposition == "to_maya"


def test_inbound_outside_hours_voicemail_when_maya_off(client):
    with mock.patch.dict(os.environ, {"FEATURE_MAYA_FALLBACK": "off"}), _at(6):
        resp = client.post("/api/desk/twilio/voice/inbound", data={
            "CallSid": "CAp6c", "From": "+15615550142"})
    xml = resp.data.decode()
    assert "<Record" in xml and "<Dial" not in xml
    assert DeskActivity.query.filter_by(twilio_sid="CAp6c").one().status == "voicemail"


def test_after_in_no_answer_dials_maya_when_flag_on(client):
    with _at(11):
        client.post("/api/desk/twilio/voice/inbound", data={"CallSid": "CAp6d", "From": "+15615550142"})
        resp = client.post("/api/desk/twilio/voice/after-in", data={
            "CallSid": "CAp6d", "DialCallStatus": "no-answer"})
    xml = resp.data.decode()
    assert "Connecting you to our booking line" in xml
    assert "<Number>+15619441636</Number>" in xml and "<Record" not in xml
    assert DeskActivity.query.filter_by(twilio_sid="CAp6d").one().status == "to_maya"
    assert InboundCall.query.filter_by(call_sid="CAp6d").one().disposition == "to_maya"
    # Maya's leg didn't pick up either → mailbox, never dead air
    resp = client.post("/api/desk/twilio/voice/after-maya", data={
        "CallSid": "CAp6d", "DialCallStatus": "busy"})
    assert "<Record" in resp.data.decode()
    assert InboundCall.query.filter_by(call_sid="CAp6d").one().disposition == "voicemail"


def test_after_in_no_answer_voicemail_when_flag_off(client):
    with mock.patch.dict(os.environ, {"FEATURE_MAYA_FALLBACK": "off"}), _at(11):
        client.post("/api/desk/twilio/voice/inbound", data={"CallSid": "CAp6e", "From": "+15615550142"})
        resp = client.post("/api/desk/twilio/voice/after-in", data={
            "CallSid": "CAp6e", "DialCallStatus": "no-answer"})
    xml = resp.data.decode()
    assert "<Record" in xml and "+15619441636" not in xml
    assert DeskActivity.query.filter_by(twilio_sid="CAp6e").one().status == "voicemail"


def test_after_in_answered_marks_human(client):
    with _at(11):
        client.post("/api/desk/twilio/voice/inbound", data={"CallSid": "CAp6f", "From": "+15615550142"})
        resp = client.post("/api/desk/twilio/voice/after-in", data={
            "CallSid": "CAp6f", "DialCallStatus": "completed", "DialCallDuration": "95",
            "DialCallTo": "client:desk-tracy"})
    assert "<Hangup" in resp.data.decode()
    act = DeskActivity.query.filter_by(twilio_sid="CAp6f").one()
    assert act.status == "answered_by_human" and act.duration == 95
    row = InboundCall.query.filter_by(call_sid="CAp6f").one()
    assert row.disposition == "answered_by_human" and row.duration == 95


def test_flag_off_restores_legacy_line(client):
    with mock.patch.dict(os.environ, {"FEATURE_INBOUND_CUSTOMERS": "off"}), _at(23):
        resp = client.post("/api/desk/twilio/voice/inbound", data={"CallSid": "CAp6g", "From": "+15615550142"})
    xml = resp.data.decode()
    assert 'timeout="25"' in xml and "<Client>desk</Client>" in xml and "Thanks for calling" not in xml
    assert InboundCall.query.filter_by(call_sid="CAp6g").first() is None


def test_human_hours_parse_and_always_window():
    with mock.patch.dict(os.environ, {"INBOUND_HUMAN_HOURS": "09:00-17:30"}):
        assert inbound.human_hours() == (540, 1050)
        assert inbound.in_human_hours(datetime(2026, 9, 9, 17, 29, tzinfo=FL))
        assert not inbound.in_human_hours(datetime(2026, 9, 9, 17, 30, tzinfo=FL))
    with mock.patch.dict(os.environ, {"INBOUND_HUMAN_HOURS": "00:00-24:00"}):
        assert inbound.in_human_hours(datetime(2026, 9, 9, 3, 0, tzinfo=FL))
    with mock.patch.dict(os.environ, {"INBOUND_HUMAN_HOURS": "garbage"}):
        assert inbound.human_hours() == (480, 1200)


# ----------------------------------------------------------------- token
def test_token_identity_is_per_va(client):
    with mock.patch.dict(os.environ, {
        "TWILIO_ACCOUNT_SID": "AC" + "0" * 32, "TWILIO_API_KEY_SID": "SK" + "1" * 32,
        "TWILIO_API_KEY_SECRET": "s3cret" * 5, "TWILIO_TWIML_APP_SID": "AP" + "2" * 32}):
        body = _va(client, "/api/va/desk/token", {}, name="Tracy Jamesyoung").get_json()
        assert body["enabled"] and body["identity"] == "desk-tracy-jamesyoung"
        import jwt as pyjwt
        claims = pyjwt.decode(body["token"], options={"verify_signature": False})
        assert claims["grants"]["identity"] == "desk-tracy-jamesyoung"
        with mock.patch.dict(os.environ, {"FEATURE_INBOUND_CUSTOMERS": "off"}):
            assert _va(client, "/api/va/desk/token", {}).get_json()["identity"] == "desk"


# ----------------------------------------------------------------- whois
def test_whois_customer_prospect_unknown(client):
    _customer()
    p = CallProspect(tier=1, category="property management", company="Palm Coast PG",
                     phone="(561) 555-0100", phone_digits="5615550100", city="WPB")
    db.session.add(p)
    db.session.commit()
    who = _va(client, "/api/va/inbound/whois", {"phone": "(561) 555-0142"}).get_json()
    assert who["kind"] == "customer"
    assert who["customer"]["name"] == "Jane Rivera" and who["customer"]["prior_jobs"] == 1
    assert who["customer"]["last_job"]["address"].startswith("9 Palm Way")
    who = _va(client, "/api/va/inbound/whois", {"phone": "5615550100"}).get_json()
    assert who["kind"] == "prospect" and who["prospect"]["company"] == "Palm Coast PG"
    who = _va(client, "/api/va/inbound/whois", {"phone": "+19545550199"}).get_json()
    assert who["kind"] == "unknown" and who["customer"] is None and who["prospect"] is None
    assert client.post("/api/va/inbound/whois", json={"phone": "5615550142"}).status_code == 401


def test_whois_returns_the_ringing_call(client):
    with _at(11):
        client.post("/api/desk/twilio/voice/inbound", data={"CallSid": "CAp6w", "From": "+15615550142"})
    who = _va(client, "/api/va/inbound/whois", {"phone": "5615550142"}).get_json()
    assert who["call"]["call_sid"] == "CAp6w" and who["call"]["disposition"] == "ringing"


# ----------------------------------------------------------------- quote
def test_quote_matches_the_pricing_engine(client):
    from routes.booking import calculate_estimate
    items = [{"category": "sofa", "quantity": 2}, {"category": "hot_tub", "quantity": 1, "size": "large"}]
    r = _va(client, "/api/va/inbound/quote", {"items": items, "zip": "33460", "date": "2026-10-20"})
    assert r.status_code == 200
    q = r.get_json()
    est = calculate_estimate(items, scheduled_date="2026-10-20")
    assert q["total"] == round(est["total"], 2)
    assert q["service_fee"] == est["service_fee"]
    assert len(q["items"]) == len(est["items"])
    assert "2x sofa" in q["items_text"] and "hot tub (large)" in q["items_text"]
    assert _va(client, "/api/va/inbound/quote", {"items": []}).status_code == 400
    assert _va(client, "/api/va/inbound/quote", {"items": [{"category": "sofa", "quantity": 999}]}).status_code == 400


# ----------------------------------------------------------------- book
def test_book_creates_job_texts_pay_link_and_logs(client):
    with _at(11):
        client.post("/api/desk/twilio/voice/inbound", data={"CallSid": "CAp6k", "From": "+15615550142"})
        client.post("/api/desk/twilio/voice/after-in", data={
            "CallSid": "CAp6k", "DialCallStatus": "completed", "DialCallDuration": "120"})
    items = [{"category": "sofa", "quantity": 1}, {"category": "mattress", "quantity": 2}]
    with mock.patch("notifications.send_booking_sms", return_value="SMbook") as sms, \
         mock.patch("routes.vapi._build_checkout_url", return_value="https://checkout.stripe.test/s") as pay:
        r = _va(client, "/api/va/inbound/book", {
            "call_sid": "CAp6k", "name": "Jane Rivera", "phone": "(561) 555-0142",
            "address": "9 Palm Way, Lake Worth", "zip": "33460", "items": items,
            "date": "2026-10-20", "window": "2-4", "notes": "gate code 1234"})
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["ok"] and body["texted"] is True
    job = db.session.get(Job, body["job"]["id"])
    assert job.status == "pending" and job.lead_source == "phone"
    assert job.items == items
    assert job.total_price == body["total"] > 0
    assert inbound._digits(job.customer.phone) == "5615550142" and job.customer.name == "Jane Rivera"
    assert "Arrival window: 2–4 PM" in job.notes and "gate code 1234" in job.notes
    # 2pm Florida in October = 18:00 UTC
    assert job.scheduled_at.hour == 18
    assert pay.call_args.args == (job.id, body["total"])
    kwargs = sms.call_args.kwargs
    assert kwargs["pay_url"].startswith("https://checkout.stripe.test")
    assert inbound._digits(sms.call_args.args[0]) == "5615550142"
    row = InboundCall.query.filter_by(call_sid="CAp6k").one()
    assert row.outcome == "booked" and row.job_id == job.id and row.quote_total == body["total"]
    assert row.va_name == "Tracy"
    act = DeskActivity.query.filter_by(twilio_sid="CAp6k").one()
    assert "Booked" in act.body and act.read_at is not None
    ev = AuditEvent.query.filter_by(action="inbound_book").one()
    assert ev.target_id == job.id and ev.actor_name == "Tracy"


def test_book_validates_and_honours_price_override(client):
    r = _va(client, "/api/va/inbound/book", {"phone": "123", "address": "x", "items": [{"category": "sofa"}]})
    assert r.status_code == 400
    r = _va(client, "/api/va/inbound/book", {"phone": "5615550142", "address": "", "items": [{"category": "sofa"}]})
    assert r.status_code == 400
    with mock.patch("notifications.send_booking_sms", return_value=None), \
         mock.patch("routes.vapi._build_checkout_url", return_value="u"):
        r = _va(client, "/api/va/inbound/book", {
            "phone": "5615550142", "address": "9 Palm Way", "items": [{"category": "sofa"}],
            "price": 400, "send_text": False})
    body = r.get_json()
    assert r.status_code == 200 and body["total"] == 400 and body["texted"] is False
    job = db.session.get(Job, body["job"]["id"])
    assert job.total_price == 400 and "Price set by Tracy" in job.notes
    row = InboundCall.query.filter_by(phone_digits="5615550142").one()
    assert row.call_sid is None and row.outcome == "booked" and row.disposition == "answered_by_human"


# ----------------------------------------------------------------- quote text
def test_quote_text_sends_and_records(client):
    with mock.patch("inbound._send_text", return_value="SMq") as tx:
        r = _va(client, "/api/va/inbound/quote-text", {
            "phone": "5615550142", "name": "Jane Rivera",
            "items": [{"category": "sofa", "quantity": 1}]})
    body = r.get_json()
    assert r.status_code == 200 and body["texted"] and body["total"] > 0
    digits, text = tx.call_args.args[:2]
    assert digits == "5615550142" and "Hi Jane!" in text and "1x sofa" in text and "all-in" in text
    row = InboundCall.query.filter_by(phone_digits="5615550142").one()
    assert row.outcome == "quoted" and row.quote_total == body["total"]
    assert AuditEvent.query.filter_by(action="inbound_quote_text").count() == 1


# ----------------------------------------------------------------- callback
def test_callback_request_lands_in_inbox(client):
    with _at(11):
        r = _va(client, "/api/va/inbound/callback", {
            "phone": "5615550142", "name": "Jane", "when": "tomorrow_pm", "note": "wants hot tub quote"})
    assert r.status_code == 200
    cb = CallbackRequest.query.one()
    assert cb.status == "open" and cb.name == "Jane"
    assert cb.requested_for == datetime(2026, 9, 10, 18, 0)          # 2pm FL → 18:00 UTC
    act = DeskActivity.query.filter_by(kind="callback").one()
    assert act.read_at is None and "CALLBACK" in act.body and "hot tub" in act.body
    inbox = _va(client, "/api/va/desk/inbox", {}).get_json()
    assert inbox["unread"] == 1 and inbox["items"][0]["preview"].startswith("CALLBACK")
    recent = _va(client, "/api/va/inbound/recent", {}).get_json()
    assert recent["callbacks"][0]["phone"] == "(561) 555-0142"
    # closing it
    r = _va(client, "/api/va/inbound/outcome", {"phone": "5615550142", "outcome": "done"})
    assert r.get_json()["closed"] == 1
    assert CallbackRequest.query.one().status == "done"
    assert _va(client, "/api/va/desk/inbox", {}).get_json()["unread"] == 0


def test_not_fit_and_spam_outcomes(client):
    with _at(11):
        client.post("/api/desk/twilio/voice/inbound", data={"CallSid": "CAp6s", "From": "+19545550199"})
    r = _va(client, "/api/va/inbound/outcome", {"call_sid": "CAp6s", "phone": "9545550199", "outcome": "spam"})
    assert r.status_code == 200
    assert InboundCall.query.filter_by(call_sid="CAp6s").one().outcome == "spam"
    assert _va(client, "/api/va/inbound/outcome", {"phone": "9545550199", "outcome": "nope"}).status_code == 400


# ----------------------------------------------------------------- recent / missed
def test_recent_flags_missed_customer_calls(client):
    _customer()
    with _at(22):
        client.post("/api/desk/twilio/voice/inbound", data={"CallSid": "CAp6m", "From": "+15615550142"})
    recent = _va(client, "/api/va/inbound/recent", {}).get_json()
    call = [c for c in recent["calls"] if c["call_sid"] == "CAp6m"][0]
    assert call["missed"] is True and call["name"] == "Jane Rivera" and call["kind"] == "customer"


# ----------------------------------------------------------------- stats
def test_stats_for_managers_only(client, app):
    from desk_auth import create_desk_user
    from auth_routes import generate_token
    boss, _ = create_desk_user("boss@p6.test", "Boss", "manager", "boss-pass")
    hdr = {"Authorization": "Bearer " + generate_token(boss.id)}
    _customer()
    with _at(11):
        client.post("/api/desk/twilio/voice/inbound", data={"CallSid": "CAst1", "From": "+15615550142"})
        client.post("/api/desk/twilio/voice/after-in", data={"CallSid": "CAst1", "DialCallStatus": "completed",
                                                              "DialCallDuration": "80"})
        client.post("/api/desk/twilio/voice/inbound", data={"CallSid": "CAst2", "From": "+19545550199"})
        client.post("/api/desk/twilio/voice/after-in", data={"CallSid": "CAst2", "DialCallStatus": "no-answer"})
    with mock.patch("notifications.send_booking_sms", return_value="s"), \
         mock.patch("routes.vapi._build_checkout_url", return_value="u"):
        _va(client, "/api/va/inbound/book", {"call_sid": "CAst1", "phone": "5615550142", "address": "9 Palm Way",
                                            "items": [{"category": "sofa"}], "price": 250})
    assert _va(client, "/api/va/inbound/stats", {"days": 7}).status_code == 403
    r = client.post("/api/va/inbound/stats", json={"days": 7}, headers=hdr)
    assert r.status_code == 200
    s = r.get_json()
    assert s["counts"]["calls"] == 2 and s["counts"]["answered_by_human"] == 1 and s["counts"]["to_maya"] == 1
    assert s["counts"]["booked"] == 1 and s["revenue_booked"] == 250.0
    assert s["answer_rate"] == 0.5 and s["close_rate"] == 1.0
    assert sum(h["calls"] for h in s["by_hour"]) == 2 and len(s["by_hour"]) == 24


# ----------------------------------------------------------------- humans-online
def test_humans_online_is_public_and_honest(client):
    with _at(11):
        r = client.get("/api/inbound/humans-online")
        assert r.status_code == 200 and r.get_json() == {"online": False, "count": 0, "in_hours": True}
        _clock_in("Tracy")
        assert client.get("/api/inbound/humans-online").get_json() == {"online": True, "count": 1, "in_hours": True}
    with _at(23):
        assert client.get("/api/inbound/humans-online").get_json()["online"] is False
    # a shift forgotten open for a day doesn't count
    VaShift.query.delete()
    db.session.add(VaShift(va_name="Ghost", started_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=30)))
    db.session.commit()
    with _at(11):
        assert client.get("/api/inbound/humans-online").get_json()["count"] == 0
