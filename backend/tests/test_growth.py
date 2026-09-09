"""Call Desk Phase 5 — Growth (growth.py): sourced leads flow into the queue
once each, Web Push subscribe/notify/prune, the calendar feed, the HubSpot
export, and the installable-desk plumbing (manifest, service worker)."""
import json
import os
import sys
import types
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from models import db, User, AuditEvent, DeskSetting, CallProspect, CallAttempt, OperatorLead, B2BLead
from models_growth import IngestLog, PrequalCall, PushSubscription
from desk_auth import create_desk_user
import growth


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code", "JWT_SECRET": "unit",
                                      "SECRET_KEY": "unit-secret", "BACKEND_URL": "https://api.test"}):
        yield
    for m in (IngestLog, PrequalCall, PushSubscription, CallAttempt, AuditEvent, DeskSetting):
        m.query.delete()
    CallProspect.query.delete(); OperatorLead.query.delete(); B2BLead.query.delete()
    User.query.filter(User.email.in_(["boss@goumuve.com", "tracy@goumuve.com"])).delete(synchronize_session=False)
    db.session.commit()


def _va(client, path, payload=None, name="Tracy"):
    base = {"code": "test-code", "va_name": name}
    base.update(payload or {})
    return client.post(path, json=base)


def _manager(client):
    create_desk_user("boss@goumuve.com", "Shamar", "manager", "pw-boss")
    tok = client.post("/api/desk/login", json={"email": "boss@goumuve.com", "password": "pw-boss"}).get_json()["token"]
    return {"Authorization": "Bearer " + tok}


def _operator(phone="(561) 555-0101", **kw):
    row = OperatorLead(business_name=kw.pop("name", "Rob's Hauling"), phone=phone, category=kw.pop("category", "junk_removal"),
                       city=kw.pop("city", "Lake Worth"), source="places", **kw)
    db.session.add(row); db.session.commit(); return row


def _b2b(phone="(561) 555-0202", **kw):
    row = B2BLead(business_name=kw.pop("name", "Palm Coast Property Group"), phone=phone,
                  category=kw.pop("category", "property_mgmt"), city=kw.pop("city", "West Palm Beach"),
                  source="places", notes=kw.pop("notes", "340 doors, monthly turnovers"), **kw)
    db.session.add(row); db.session.commit(); return row


# ------------------------------------------------------------------ ingest
def test_ingest_makes_prospects_with_tiers_and_runs_once(app):
    _operator(); _b2b()
    res = growth.ingest_leads(force=True)
    assert res["added"] == 2 and res["seen"] == 2 and res["invalid"] == 0
    sup = CallProspect.query.filter_by(phone_digits="5615550101").one()
    dem = CallProspect.query.filter_by(phone_digits="5615550202").one()
    assert (sup.tier, sup.category) == (2, "junk removal") and sup.angle == growth.SUPPLY_ANGLE
    assert (dem.tier, dem.category) == (1, "property management") and dem.angle == growth.DEMAND_ANGLE
    assert dem.why.startswith("Sourced by places outreach") and "340 doors" in dem.why
    assert IngestLog.query.count() == 2
    # idempotent: nothing left to see, nothing added twice
    again = growth.ingest_leads(force=True)
    assert again["added"] == 0 and again["seen"] == 0
    assert CallProspect.query.count() == 2 and IngestLog.query.count() == 2


def test_ingest_merges_into_existing_prospect_and_skips_bad_phones(app):
    db.session.add(CallProspect(tier=1, category="hoa", company="Existing HOA", phone="(561) 555-0303",
                                phone_digits="5615550303", why="from the June list")); db.session.commit()
    lead = _b2b(phone="561-555-0303", name="Existing HOA (Places)")
    bad = _operator(phone="555", name="Bad Row")
    res = growth.ingest_leads(force=True)
    assert res["added"] == 0 and res["merged"] == 1 and res["invalid"] == 1
    existing = CallProspect.query.filter_by(phone_digits="5615550303").one()
    assert existing.why == "from the June list"          # history untouched
    assert IngestLog.query.filter_by(lead_id=lead.id).one().prospect_id == existing.id
    assert IngestLog.query.filter_by(lead_id=bad.id).one().prospect_id is None
    assert growth.ingest_leads(force=True)["seen"] == 0    # neither is retried


def test_ingest_flag_off_skips_scheduled_run_but_manager_can_force(client):
    from flags import set_flag
    set_flag("auto_ingest", False)
    _operator()
    assert growth.run_auto_ingest()["skipped"] is True
    assert CallProspect.query.count() == 0
    assert _va(client, "/api/admin/growth/ingest-run").status_code == 403       # VA can't
    resp = client.post("/api/admin/growth/ingest-run", json={}, headers=_manager(client))
    assert resp.status_code == 200 and resp.get_json()["added"] == 1
    assert AuditEvent.query.filter_by(action="growth.ingest_run").count() == 1


def test_ingest_uses_compliance_filter_when_present(app):
    _operator(); _b2b()
    fake = types.ModuleType("compliance")
    fake.filter_rows = lambda rows: [r for r in rows if r["tier"] == 1]
    with mock.patch.dict(sys.modules, {"compliance": fake}):
        res = growth.ingest_leads(force=True)
    assert res["added"] == 1 and res["filtered"] == 1
    assert CallProspect.query.one().tier == 1
    assert IngestLog.query.filter_by(result="filtered").count() == 1


# ------------------------------------------------------------------ push
VAPID = {"VAPID_PUBLIC_KEY": "BPubKeyTest", "VAPID_PRIVATE_KEY": "privkey", "VAPID_SUBJECT": "ops@goumuve.com"}
SUB = {"endpoint": "https://push.example/sub/abc", "keys": {"p256dh": "p", "auth": "a"}}


def test_push_public_key_reports_off_until_env_is_set(client):
    with mock.patch.dict(os.environ, {"VAPID_PUBLIC_KEY": "", "VAPID_PRIVATE_KEY": ""}):
        b = client.get("/api/va/growth/push/public-key").get_json()
    assert b["enabled"] is False and b["key"] == ""
    with mock.patch.dict(os.environ, VAPID):
        b = client.get("/api/va/growth/push/public-key").get_json()
    assert b["enabled"] is True and b["key"] == "BPubKeyTest"


def test_push_subscribe_and_unsubscribe(client):
    with mock.patch.dict(os.environ, VAPID):
        assert client.post("/api/va/growth/push/subscribe", json={"subscription": SUB}).status_code == 401
        assert _va(client, "/api/va/growth/push/subscribe", {"subscription": {"endpoint": "http://x"}}).status_code == 400
        r = _va(client, "/api/va/growth/push/subscribe", {"subscription": SUB})
        assert r.status_code == 200 and r.get_json()["count"] == 1
        _va(client, "/api/va/growth/push/subscribe", {"subscription": SUB})          # same endpoint: upsert
        row = PushSubscription.query.one()
        assert row.va_name == "Tracy" and row.keys == {"p256dh": "p", "auth": "a"}
        r = _va(client, "/api/va/growth/push/unsubscribe", {"endpoint": SUB["endpoint"]})
        assert r.get_json()["removed"] == 1 and PushSubscription.query.count() == 0
    assert AuditEvent.query.filter(AuditEvent.action.in_(["growth.push_subscribe", "growth.push_unsubscribe"])).count() == 3


def test_notify_reply_pushes_to_everyone_and_prunes_gone_endpoints(app):
    import pywebpush
    db.session.add_all([
        PushSubscription(va_name="Tracy", endpoint="https://push.example/a", keys={"p256dh": "p", "auth": "a"}),
        PushSubscription(va_name="Tracy", endpoint="https://push.example/gone", keys={"p256dh": "p", "auth": "a"}),
    ])
    p = CallProspect(tier=1, category="property management", company="Palm Coast Property Group",
                     phone="(561) 555-0142", phone_digits="5615550142")
    db.session.add(p); db.session.commit()

    def fake_webpush(subscription_info, data, **kw):
        if subscription_info["endpoint"].endswith("/gone"):
            exc = pywebpush.WebPushException("gone")
            exc.response = mock.Mock(status_code=410)
            raise exc
        return mock.Mock(status_code=201)

    with mock.patch.dict(os.environ, VAPID), mock.patch("pywebpush.webpush", side_effect=fake_webpush) as wp:
        res = growth.notify_reply(p, "Yes send me the info")
    assert res == {"sent": 1, "pruned": 1, "failed": 0}
    assert wp.call_count == 2
    payload = json.loads(wp.call_args_list[0].kwargs["data"])
    assert payload["title"] == "Palm Coast Property Group replied" and payload["body"] == "Yes send me the info"
    assert payload["data"]["url"] == "/va/calls"
    assert wp.call_args_list[0].kwargs["vapid_claims"] == {"sub": "mailto:ops@goumuve.com"}
    assert [s.endpoint for s in PushSubscription.query.all()] == ["https://push.example/a"]


def test_notify_reply_respects_flag_and_unconfigured_env(app):
    from flags import set_flag
    db.session.add(PushSubscription(endpoint="https://push.example/a", keys={"p256dh": "p", "auth": "a"})); db.session.commit()
    with mock.patch("pywebpush.webpush") as wp:
        with mock.patch.dict(os.environ, {"VAPID_PUBLIC_KEY": "", "VAPID_PRIVATE_KEY": ""}):
            assert growth.notify_reply(None, "hi")["sent"] == 0
        set_flag("push_notifications", False)
        with mock.patch.dict(os.environ, VAPID):
            assert growth.notify_reply(None, "hi")["sent"] == 0
    assert wp.call_count == 0


def test_inbound_text_on_the_desk_line_fires_notify_reply(client):
    p = CallProspect(tier=1, category="property management", company="Test Property Co",
                     phone="(561) 555-0100", phone_digits="5615550100")
    db.session.add(p); db.session.commit()
    with mock.patch.dict(os.environ, {"TWILIO_AUTH_TOKEN": "", "DESK_TWILIO_NUMBER": "+15615550999", "DESK_FORWARD_NUMBER": ""}), \
            mock.patch("growth.notify_reply") as nr:
        resp = client.post("/api/desk/twilio/sms", data={"From": "+15615550100", "To": "+15615550999",
                                                          "Body": "Yes send it", "NumMedia": "0", "MessageSid": "SMx1"})
    assert resp.status_code == 200
    nr.assert_called_once()
    assert nr.call_args.args[0].id == p.id and nr.call_args.args[1] == "Yes send it"


# ------------------------------------------------------------------ calendar
def _prospect(company, digits, followup, **kw):
    p = CallProspect(tier=1, category=kw.pop("category", "property management"), company=company,
                     phone="({}) {}-{}".format(digits[:3], digits[3:6], digits[6:]), phone_digits=digits,
                     status=kw.pop("status", "interested"), next_followup_at=followup, **kw)
    db.session.add(p); db.session.commit(); return p


def test_calendar_link_and_ics_feed(client):
    soon = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0, tzinfo=None)
    mine = _prospect("Palm Coast Property Group", "5615550142", soon, last_note="Ask for Marcus; wants a rate card", city="West Palm Beach")
    theirs = _prospect("Robs Hauling", "9545550100", soon + timedelta(hours=1))
    past = _prospect("Old Co", "5615550999", soon - timedelta(days=3))
    db.session.add_all([CallAttempt(prospect_id=mine.id, outcome="callback", va_name="Tracy"),
                        CallAttempt(prospect_id=theirs.id, outcome="callback", va_name="Sam"),
                        CallAttempt(prospect_id=past.id, outcome="callback", va_name="Tracy")])
    db.session.commit()

    r = _va(client, "/api/va/growth/calendar-link")
    assert r.status_code == 200
    url = r.get_json()["url"]
    assert url.startswith("https://api.test/va/calendar/") and url.endswith(".ics")
    token = url.rsplit("/", 1)[1][:-4]
    assert len(token) == 24 and token == growth.calendar_token("Tracy")

    ics = client.get("/va/calendar/{}.ics".format(token))
    assert ics.status_code == 200 and ics.mimetype == "text/calendar"
    body = ics.get_data(as_text=True)
    assert body.startswith("BEGIN:VCALENDAR\r\n") and body.rstrip().endswith("END:VCALENDAR")
    assert body.count("BEGIN:VEVENT") == 1
    assert "SUMMARY:Call back Palm Coast Property Group" in body
    assert "DTSTART:" + soon.strftime("%Y%m%dT%H%M%SZ") in body
    assert "DTEND:" + (soon + timedelta(minutes=15)).strftime("%Y%m%dT%H%M%SZ") in body
    assert "Phone: (561) 555-0142" in body and "Ask for Marcus" in body
    assert "Robs Hauling" not in body and "Old Co" not in body

    # a VA with no logged calls sees every upcoming callback
    sam_free = _va(client, "/api/va/growth/calendar-link", name="Newbie").get_json()["url"]
    body = client.get(sam_free.replace("https://api.test", "")).get_data(as_text=True)
    assert body.count("BEGIN:VEVENT") == 2
    assert client.get("/va/calendar/000000000000000000000000.ics").status_code == 404


# ------------------------------------------------------------------ export
def test_hubspot_export_header_rows_and_gate(client):
    soon = (datetime.now(timezone.utc) + timedelta(days=1)).replace(tzinfo=None)
    _prospect("Palm Coast Property Group", "5615550142", soon, contact_name="Marcus Bell", email="marcus@pcpg.com",
              city="West Palm Beach", why="340 doors", last_note="wants a rate card")
    _prospect("Done Deal LLC", "5615550777", None, status="converted")
    _prospect("Nope Inc", "5615550888", None, status="dead")
    assert client.get("/api/admin/growth/export/prospects.csv").status_code == 401
    r = client.get("/api/admin/growth/export/prospects.csv", headers=_manager(client))
    assert r.status_code == 200 and r.mimetype == "text/csv"
    lines = r.get_data(as_text=True).strip().split("\r\n")
    assert lines[0] == "Company name,Phone number,City,Contact,Email,Lifecycle stage,Notes"
    assert len(lines) == 4
    import csv, io
    rows = {row[0]: row for row in csv.reader(io.StringIO("\r\n".join(lines[1:])))}
    pc = rows["Palm Coast Property Group"]
    assert pc[1:6] == ["(561) 555-0142", "West Palm Beach", "Marcus Bell", "marcus@pcpg.com", "opportunity"]
    assert "Why: 340 doors" in pc[6] and "Last: wants a rate card" in pc[6]
    assert rows["Done Deal LLC"][5] == "customer" and rows["Nope Inc"][5] == "other"
    assert AuditEvent.query.filter_by(action="growth.export").count() == 1


# ------------------------------------------------------------------ installable desk
def test_service_worker_route_headers(client):
    r = client.get("/va/desk-sw.js")
    assert r.status_code == 200
    assert r.headers["Service-Worker-Allowed"] == "/va/"
    assert r.mimetype == "application/javascript"
    body = r.get_data(as_text=True)
    assert "showNotification" in body and "notificationclick" in body and "/va/calls" in body


def test_manifest_icons_and_page_wiring(client):
    r = client.get("/static/desk-manifest.json")
    assert r.status_code == 200
    m = json.loads(r.get_data(as_text=True))
    assert m["name"] == "Umuve Call Desk" and m["short_name"] == "Call Desk"
    assert m["start_url"] == "/va/calls" and m["display"] == "standalone"
    assert m["background_color"] == "#0B0E12" and m["theme_color"] == "#0B0E12"
    assert {i["sizes"] for i in m["icons"]} == {"192x192", "512x512"}
    for icon in m["icons"]:
        assert client.get(icon["src"]).status_code == 200
    page = client.get("/va/calls").get_data(as_text=True)
    assert '<link rel="manifest" href="/static/desk-manifest.json" />' in page
    assert page.index('src="/static/desk-growth.js') < page.index('src="/va/calls.js')
    assert client.get("/static/desk-growth.js").status_code == 200


def test_card_lookup_by_phone_then_company(client):
    p = _prospect("Palm Coast Property Group", "5615550142", None, status="queued")
    r = _va(client, "/api/va/growth/card-lookup", {"company": "Palm Coast Property Group", "phone": "(561) 555-0142"})
    assert r.status_code == 200 and r.get_json()["prospect_id"] == p.id and r.get_json()["side"] == "demand"
    r = _va(client, "/api/va/growth/card-lookup", {"company": "Palm Coast Property Group", "phone": ""})
    assert r.get_json()["prospect_id"] == p.id
    assert _va(client, "/api/va/growth/card-lookup", {"company": "Nobody", "phone": "000"}).status_code == 404
    assert client.post("/api/va/growth/card-lookup", json={"company": "x"}).status_code == 401
