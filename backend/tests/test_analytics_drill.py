"""Every number on the analytics page opens to the records that made it."""
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from analytics import cache_clear
from desk_auth import create_desk_user
from models import db, User, Contractor, Job, Payment, CallProspect, CallAttempt, VaShift, generate_uuid
from models_inbound import InboundCall
from models_leads import LeadTouch


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture(autouse=True)
def env(app, db_session):
    cache_clear()
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code", "JWT_SECRET": "unit"}):
        yield


def _va(client, payload, name="Dommo"):
    base = {"code": "test-code", "va_name": name}
    base.update(payload)
    return client.post("/api/va/analytics/detail", json=base)


def _seed():
    p = CallProspect(tier=1, category="property management", company="Palm Coast PM", phone="5615550142", phone_digits="5615550142",
                     city="Lantana", created_at=_now())
    db.session.add(p); db.session.flush()
    db.session.add(CallAttempt(prospect_id=p.id, outcome="converted", note="rate card on file", va_name="Tracy", created_at=_now() - timedelta(hours=2)))
    db.session.add(CallAttempt(prospect_id=p.id, outcome="no_answer", va_name="Tracy", created_at=_now() - timedelta(hours=3)))
    db.session.add(InboundCall(id=generate_uuid(), call_sid="CAdrill1", phone_digits="9545550100", kind="customer", source="google",
                               disposition="answered_by_human", outcome="booked", answered_by="Tracy", duration=240, in_hours=1,
                               quote_total=250.0, created_at=_now() - timedelta(minutes=30)))
    db.session.add(InboundCall(id=generate_uuid(), call_sid="CAdrill2", phone_digits="9545550101", kind="customer", source="meta",
                               disposition="to_maya", outcome="none", in_hours=0, created_at=_now() - timedelta(minutes=20)))
    db.session.add(LeadTouch(kind="call", ref_id="CAdrill2", phone_digits="9545550101", source="meta", created_at=_now() - timedelta(minutes=20)))
    cx = User(id=generate_uuid(), email="cx@drill.test", name="Cary", phone="+15615550999", role="customer")
    db.session.add(cx); db.session.flush()
    u = User(id=generate_uuid(), email="h@drill.test", name="Hank Hauler", phone="+15615550777", role="driver")
    db.session.add(u); db.session.flush()
    c = Contractor(user_id=u.id, approval_status="approved"); db.session.add(c); db.session.flush()
    j = Job(id=generate_uuid(), customer_id=cx.id, status="completed", address="5370 S University Dr", total_price=307.8,
            lead_source="phone_google", disposal_fee=40.0, driver_id=c.id, scheduled_at=_now() - timedelta(hours=1),
            hauler_confirmed_at=_now(), confirmation_code="AFB22IMO")
    db.session.add(j); db.session.flush()
    db.session.add(Payment(id=generate_uuid(), job_id=j.id, amount=307.8, payment_status="succeeded", refunded_amount=307.8))
    db.session.add(VaShift(va_name="Tracy", started_at=_now() - timedelta(hours=4), ended_at=_now() - timedelta(hours=1)))
    db.session.commit()
    return p, j


def test_wins_open_to_the_calls_that_won(client):
    _seed()
    r = _va(client, {"metric": "wins", "days": 7}).get_json()
    assert r["total"] == 1 and r["kind"] == "outbound"
    row = r["rows"][0]
    assert row["what"] == "Palm Coast PM" and row["who"] == "Tracy" and row["result"] == "Converted"
    assert row["note"] == "rate card on file" and row["when"] and row["link"].startswith("/va/calls?prospect=")
    assert _va(client, {"metric": "dials", "days": 7}).get_json()["total"] == 2


def test_inbound_speed_and_money_metrics(client):
    _seed()
    calls = _va(client, {"metric": "calls", "days": 7}).get_json()
    assert calls["total"] == 2 and calls["rows"][0]["source"] in ("Meta ads", "Google LSA")
    booked = _va(client, {"metric": "booked_calls", "days": 7}).get_json()
    assert booked["total"] == 1 and "Booked" in booked["rows"][0]["result"] and booked["rows"][0]["amount"] == 250.0
    assert _va(client, {"metric": "source:google", "days": 7}).get_json()["total"] == 1
    assert _va(client, {"metric": "after_hours", "days": 7}).get_json()["total"] == 1
    unt = _va(client, {"metric": "leads_untouched", "days": 7}).get_json()
    assert unt["total"] == 1 and "Never touched" in unt["rows"][0]["result"]
    rev = _va(client, {"metric": "revenue", "days": 7}).get_json()
    assert rev["total"] == 1 and rev["total_amount"] == 307.8 and rev["rows"][0]["code"] == "AFB22IMO" and "Cary" in rev["rows"][0]["what"]
    assert _va(client, {"metric": "dump_fees", "days": 7}).get_json()["rows"][0]["amount"] == 40.0
    assert _va(client, {"metric": "refunded", "days": 7}).get_json()["total_amount"] == 307.8
    assert _va(client, {"metric": "channel:phone", "days": 7}).get_json()["total"] == 1
    conf = _va(client, {"metric": "confirmed", "days": 7}).get_json()
    assert conf["total"] == 1 and conf["rows"][0]["who"] == "Hank Hauler"
    sh = _va(client, {"metric": "shifts", "days": 7}).get_json()
    assert sh["total"] == 1 and sh["rows"][0]["who"] == "Tracy" and "3.0 h" in sh["rows"][0]["result"]


def test_scoping_paging_and_errors(client):
    _seed()
    assert client.post("/api/va/analytics/detail", json={"metric": "wins"}).status_code == 401
    assert _va(client, {"metric": "nope", "days": 7}).status_code == 404
    assert _va(client, {"days": 7}).status_code == 400
    r = _va(client, {"metric": "dials", "days": 7, "limit": 1}).get_json()
    assert r["total"] == 2 and len(r["rows"]) == 1
    r2 = _va(client, {"metric": "dials", "days": 7, "limit": 1, "offset": 1}).get_json()
    assert len(r2["rows"]) == 1 and r2["rows"][0]["result"] != r["rows"][0]["result"]
    # a VA on her own login sees her own outbound, and money is off limits
    create_desk_user("sam@goumuve.com", "Sam", "va", "pw-sam-11")
    tok = client.post("/api/desk/login", json={"email": "sam@goumuve.com", "password": "pw-sam-11"}).get_json()["token"]
    h = {"Authorization": "Bearer " + tok}
    assert client.post("/api/va/analytics/detail", json={"metric": "wins", "days": 7}, headers=h).get_json()["total"] == 0
    assert client.post("/api/va/analytics/detail", json={"metric": "revenue", "days": 7}, headers=h).status_code == 403
    assert client.get("/static/desk-drill.js").status_code == 200
