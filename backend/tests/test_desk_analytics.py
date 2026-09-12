"""The desk analytics page tells the truth about inbound, speed to lead, money and haulers."""
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from analytics import cache_clear
from desk_auth import create_desk_user
from models import db, User, Contractor, Job, Payment, VaShift, generate_uuid
from models_inbound import InboundCall
from models_leads import LeadTouch
import desk_analytics


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture(autouse=True)
def env(app, db_session):
    cache_clear()
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code", "JWT_SECRET": "unit", "VA_HOURLY_RATE": "6.00"}):
        yield
    cache_clear()


def _va(client, payload, name="Tracy"):
    base = {"code": "test-code", "va_name": name}
    base.update(payload)
    return client.post("/api/va/analytics/desk", json=base)


def _call(source, disposition, outcome="none", who=None, minutes_ago=30, duration=None, in_hours=1, sid=None):
    r = InboundCall(id=generate_uuid(), call_sid=sid or "CA" + generate_uuid()[:18], phone_digits="5615550" + str(minutes_ago % 1000).zfill(3),
                    kind="customer", disposition=disposition, outcome=outcome, answered_by=who, va_name=who,
                    duration=duration, in_hours=in_hours, source=source, created_at=_now() - timedelta(minutes=minutes_ago))
    db.session.add(r); db.session.commit()
    return r


def _job(lead_source=None, paid=None, disposal=0.0, driver=None, confirmed=False, status="pending", scheduled_in_hours=6):
    cx = User.query.filter_by(email="cx@stats.test").first()
    if not cx:
        cx = User(id=generate_uuid(), email="cx@stats.test", name="Cx", phone="+15615550999", role="customer")
        db.session.add(cx); db.session.flush()
    j = Job(id=generate_uuid(), customer_id=cx.id, status=status, address="1 Test St", total_price=paid or 150.0,
            lead_source=lead_source, disposal_fee=disposal, driver_id=driver,
            scheduled_at=_now() + timedelta(hours=scheduled_in_hours),
            hauler_confirmed_at=_now() if confirmed else None)
    db.session.add(j); db.session.flush()
    if paid is not None:
        db.session.add(Payment(id=generate_uuid(), job_id=j.id, amount=paid, payment_status="succeeded", disposal_fee=disposal))
    db.session.commit()
    return j


def test_inbound_block_counts_sources_dispositions_and_people():
    _call("google", "answered_by_human", "booked", "Tracy", duration=240)
    _call("google", "answered_by_human", "quoted", "Tracy", duration=120)
    _call("meta", "to_maya")
    _call("desk", "missed", in_hours=0)
    _call("desk", "voicemail")
    start, end = _now() - timedelta(days=1), _now() + timedelta(minutes=1)
    ib = desk_analytics.inbound_block(start, end)
    assert ib["calls"] == 5 and ib["answered_by_human"] == 2 and ib["human_rate"] == 40.0
    assert ib["to_maya"] == 1 and ib["missed"] == 2
    assert ib["booked"] == 1 and ib["quoted"] == 1 and ib["book_rate"] == 50.0
    assert {s["source"]: s["calls"] for s in ib["by_source"]}["google"] == 2
    assert ib["by_va"][0]["va"] == "Tracy" and ib["by_va"][0]["answered"] == 2 and ib["by_va"][0]["seconds"] == 360
    assert ib["in_hours"] == 4 and ib["after_hours"] == 1
    # scoped to one person: only her calls
    assert desk_analytics.inbound_block(start, end, va="Tracy")["calls"] == 2


def test_speed_to_lead_measures_from_the_ring_to_the_touch():
    fast = _call("google", "missed", minutes_ago=60, sid="CAfast")
    slow = _call("meta", "missed", minutes_ago=60, sid="CAslow")
    db.session.add(LeadTouch(kind="call", ref_id="CAfast", phone_digits=fast.phone_digits, source="google",
                             touched_at=fast.created_at + timedelta(seconds=45), touched_by="Tracy", created_at=fast.created_at))
    db.session.add(LeadTouch(kind="call", ref_id="CAslow", phone_digits=slow.phone_digits, source="meta",
                             touched_at=slow.created_at + timedelta(minutes=20), touched_by="Tracy", created_at=slow.created_at,
                             auto_text_at=slow.created_at + timedelta(minutes=2)))
    db.session.add(LeadTouch(kind="web", ref_id="lead-3", phone_digits="5615550003", source="web", created_at=_now() - timedelta(minutes=10)))
    db.session.commit()
    sp = desk_analytics.speed_block(_now() - timedelta(days=1), _now() + timedelta(minutes=1))
    assert sp["leads"] == 3 and sp["touched"] == 2 and sp["untouched"] == 1 and sp["auto_texted"] == 1
    assert sp["median_seconds"] == round((45 + 1200) / 2) and sp["within_target_pct"] == 50.0


def test_bookings_and_haulers_blocks(client):
    u = User(id=generate_uuid(), email="h@stats.test", name="Hank Hauler", phone="+15615550777", role="driver")
    db.session.add(u); db.session.flush()
    c = Contractor(user_id=u.id, approval_status="approved"); db.session.add(c); db.session.commit()
    _job(lead_source="phone_google", paid=300.0, disposal=40.0, driver=c.id, confirmed=True, status="completed")
    _job(lead_source=None, paid=120.0, driver=c.id)
    _job(lead_source="phone_desk")
    start, end = _now() - timedelta(days=1), _now() + timedelta(days=1)
    b = desk_analytics.bookings_block(start, end)
    assert b["jobs"] == 3 and b["paid"] == 2 and b["revenue"] == 420.0 and b["avg_ticket"] == 210.0
    assert b["dump_fees"] == 40.0 and b["completed"] == 1
    assert {x["channel"]: x["jobs"] for x in b["by_channel"]} == {"phone": 2, "web": 1}
    h = desk_analytics.haulers_block(start, end)
    assert h["assigned"] == 2 and h["confirmed"] == 1 and h["confirm_rate"] == 50.0
    assert h["by_hauler"][0]["name"] == "Hank Hauler" and h["by_hauler"][0]["jobs"] == 2


def test_endpoint_scopes_a_va_to_herself_and_hides_money(client):
    _call("google", "answered_by_human", "booked", "Tracy")
    _call("google", "answered_by_human", "quoted", "Sam")
    _job(lead_source="phone_google", paid=200.0)
    db.session.add(VaShift(va_name="Tracy", started_at=_now() - timedelta(hours=2))); db.session.commit()
    # owner view via the shared passcode: everyone, with money
    r = _va(client, {"days": 7})
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["manager"] is True and body["inbound"]["calls"] == 2 and body["bookings"]["revenue"] == 200.0
    assert body["hours"]["hours"] == pytest.approx(2.0, abs=0.05) and body["series"] and body["label"] == "Last 7 days"
    # a VA on her own login: just her, no money block
    create_desk_user("tracy@goumuve.com", "Tracy", role="va", password="pw-tracy-1")
    tok = client.post("/api/desk/login", json={"email": "tracy@goumuve.com", "password": "pw-tracy-1"}).get_json()["token"]
    cache_clear()
    r = client.post("/api/va/analytics/desk", json={"days": 7, "va": "Sam"}, headers={"Authorization": "Bearer " + tok})
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["manager"] is False and body["va"] == "Tracy" and body["inbound"]["calls"] == 1
    assert "bookings" not in body and "hours" not in body
    assert client.post("/api/va/analytics/desk", json={"days": 7}).status_code == 401
    assert client.get("/va/analytics").status_code == 200
    assert client.get("/static/desk-stats.js").status_code == 200
