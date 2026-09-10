"""Same-day dispatch: capacity, offer wave + live status, standby roster, Maya hook."""
import json
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from models import db, User, Contractor, Job, JobOffer, DeskSetting
from models_sameday import HaulerStandby
import sameday


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code", "GOOGLE_PLACES_API_KEY": ""}):
        yield
    JobOffer.query.delete(); HaulerStandby.query.delete(); DeskSetting.query.delete()
    Job.query.filter(Job.address.like("e2e-sd%")).delete(synchronize_session=False)
    for c in Contractor.query.all():
        db.session.delete(c)
    User.query.filter(User.email.like("%@sd.test")).delete(synchronize_session=False)
    db.session.commit()


def _hauler(name, phone, lat, lng, online=True, approved="approved"):
    u = User(email=name.lower().replace(" ", "") + "@sd.test", name=name, phone=phone, role="driver")
    db.session.add(u); db.session.flush()
    c = Contractor(user_id=u.id, is_online=online, approval_status=approved, current_lat=lat, current_lng=lng,
                   avg_rating=4.5, truck_capacity=12.0)
    db.session.add(c); db.session.commit()
    return c


def _customer():
    u = User.query.filter_by(email="cx@sd.test").first()
    if not u:
        u = User(email="cx@sd.test", name="Test Cx", phone="+15619990000", role="customer")
        db.session.add(u); db.session.commit()
    return u


def _job(lat=26.62, lng=-80.05, when=None, status="confirmed"):
    j = Job(customer_id=_customer().id, address="e2e-sd 123 Lake Ave, Lake Worth FL", lat=lat, lng=lng, status=status,
            scheduled_at=when or (datetime.now(timezone.utc) + timedelta(hours=3)).replace(tzinfo=None),
            total_price=189.0)
    for k, v in {"customer_name": "Test Cx", "customer_phone": "5615550100", "customer_email": "cx@sd.test"}.items():
        if hasattr(Job, k):
            setattr(j, k, v)
    db.session.add(j); db.session.commit()
    return j


def _va(client, path, payload):
    base = {"code": "test-code", "va_name": "Tracy"}
    base.update(payload or {})
    return client.post(path, json=base)


# ------------------------------------------------------------------ capacity
def test_capacity_counts_online_and_standby_within_radius():
    near = _hauler("Rob Near", "+15615550001", 26.63, -80.06)                 # ~1 mi
    far = _hauler("Far Guy", "+15615550002", 27.90, -82.50)                   # Tampa
    offline = _hauler("Off Line", "+15615550003", 26.60, -80.05, online=False)
    cap = sameday.capacity(26.62, -80.05)
    assert cap["count"] == 1 and cap["nearest"]["name"] == "Rob Near" and cap["level"] == "amber"
    # standby makes an offline hauler count
    db.session.add(HaulerStandby(day=sameday._local_today(), contractor_id=offline.id, available=True)); db.session.commit()
    cap = sameday.capacity(26.62, -80.05)
    assert cap["count"] == 2 and cap["standby_total"] == 1
    # no location → everyone available counts (Far Guy too)
    assert sameday.capacity(None, None)["count"] == 3 and "no location" in sameday.capacity(None, None)["note"]
    assert sameday.capacity(30.0, -84.0)["level"] == "red"


def test_capacity_endpoint_geocodes_zip_with_cache(client):
    _hauler("Rob Near", "+15615550001", 26.63, -80.06)
    with mock.patch("sameday.geocode", return_value=(26.62, -80.05)) as g:
        r = _va(client, "/api/va/sameday/capacity", {"zip": "33460"}).get_json()
    assert r["count"] == 1 and r["geocoded"] is True and g.call_args[0][0] == "33460"
    # real geocode path: Places text search mocked, then served from cache without the API
    with mock.patch.dict(os.environ, {"GOOGLE_PLACES_API_KEY": "k"}), \
         mock.patch("sameday._places_search_text", return_value=[{"location": {"latitude": 26.61, "longitude": -80.04}}]) as ts:
        assert sameday.geocode("33460") == (26.61, -80.04)
        assert ts.call_args[0][1] == "33460, FL"
        assert sameday.geocode("33460") == (26.61, -80.04)
        assert ts.call_count == 1


# ------------------------------------------------------------------ wave + status
def test_wave_texts_nearest_three_then_widens(client):
    for i, (name, lat) in enumerate([("A", 26.63), ("B", 26.64), ("C", 26.65), ("D", 26.66), ("E", 26.70)]):
        _hauler("Hauler " + name, "+1561555010%d" % i, lat, -80.05)
    job = _job()
    with mock.patch("dispatcher._sms_broadcast_offer") as sms:
        r = _va(client, "/api/va/sameday/find", {"job_id": job.id, "limit": 3})
        assert r.status_code == 200, r.get_json()
        b = r.get_json()
        assert [s["name"] for s in b["sent"]] == ["Hauler A", "Hauler B", "Hauler C"]
        assert sms.call_count == 3 and b["status"]["assigned"] is False
        assert JobOffer.query.filter_by(job_id=job.id).count() == 3
        db.session.refresh(job); assert job.status == "broadcasting"
        # widen → next two only (E is ~5.5 mi, still in range)
        b2 = _va(client, "/api/va/sameday/find", {"job_id": job.id, "limit": 3}).get_json()
        assert [s["name"] for s in b2["sent"]] == ["Hauler D", "Hauler E"]
        assert JobOffer.query.filter_by(job_id=job.id).count() == 5
    st = _va(client, "/api/va/sameday/status", {"job_id": job.id}).get_json()
    assert len(st["offers"]) == 5 and st["accepted"] is None and all(o["status"] == "sent" for o in st["offers"])
    assert st["offers"][0]["eta_minutes"] >= 10
    # a hauler accepts → status shows who and an ETA
    o = JobOffer.query.filter_by(job_id=job.id).first(); o.status = "accepted"; job.driver_id = o.contractor_id; db.session.commit()
    st = _va(client, "/api/va/sameday/status", {"job_id": job.id}).get_json()
    assert st["assigned"] and st["accepted"]["status"] == "accepted"
    # no more offers once assigned
    b3 = _va(client, "/api/va/sameday/find", {"job_id": job.id}).get_json()
    assert b3["sent"] == [] and b3["reason"] == "already assigned"


def test_wave_includes_standby_offline_haulers_and_geocodes_job(client):
    off = _hauler("Standby Sam", "+15615550201", 26.63, -80.05, online=False)
    db.session.add(HaulerStandby(day=sameday._local_today(), contractor_id=off.id, available=True)); db.session.commit()
    job = _job(lat=None, lng=None)
    with mock.patch("sameday.geocode", return_value=(26.62, -80.05)), mock.patch("dispatcher._sms_broadcast_offer"):
        b = _va(client, "/api/va/sameday/find", {"job_id": job.id}).get_json()
    assert [s["name"] for s in b["sent"]] == ["Standby Sam"]
    db.session.refresh(job); assert job.lat == 26.62


def test_wave_flag_and_guards(client):
    job = _job()
    DeskSetting.put("flag:sameday_wave", "off")
    assert _va(client, "/api/va/sameday/find", {"job_id": job.id}).status_code == 403
    DeskSetting.put("flag:sameday_wave", None)
    assert _va(client, "/api/va/sameday/find", {"job_id": "nope"}).status_code == 404
    assert client.post("/api/va/sameday/find", json={"code": "wrong", "job_id": job.id}).status_code == 401
    with mock.patch("dispatcher._sms_broadcast_offer"):
        b = _va(client, "/api/va/sameday/find", {"job_id": job.id}).get_json()
    assert b["sent"] == [] and "nobody" in b["reason"]


# ------------------------------------------------------------------ standby roster
def test_standby_ask_texts_approved_haulers_once(app):
    _hauler("Rob", "+15615550301", 26.6, -80.0)
    _hauler("Pending Pete", "+15615550302", 26.6, -80.0, approved="pending")
    with mock.patch("sms_service.send_sms") as send:
        n = sameday.ask_standby()
        assert n == 1 and send.call_args[0][0] == "+15615550301" and "Reply Y or N" in send.call_args[0][1]
        assert sameday.ask_standby() == 0                       # same day: no repeat
    assert json.loads(DeskSetting.get("standby:last"))["asked"] == 1


def test_standby_reply_via_main_sms_webhook(client):
    c = _hauler("Rob", "+15615550301", 26.6, -80.0, online=False)
    with mock.patch.dict(os.environ, {"SMS_WEBHOOK_VALIDATE": "off"}):
        r = client.post("/api/sms/inbound", data={"From": "+15615550301", "Body": "Y", "NumMedia": "0"})
    assert r.status_code == 200 and b"same-day list" in r.data
    row = HaulerStandby.query.filter_by(contractor_id=c.id).one()
    assert row.available is True and row.via == "sms"
    with mock.patch.dict(os.environ, {"SMS_WEBHOOK_VALIDATE": "off"}):
        client.post("/api/sms/inbound", data={"From": "+15615550301", "Body": "no", "NumMedia": "0"})
    db.session.refresh(row); assert row.available is False
    # unknown number / unrelated text → not a standby answer
    assert sameday.record_standby_reply("+15619990000", "Y") is None
    assert sameday.record_standby_reply("+15615550301", "what time is it") is None
    roster = _va(client, "/api/va/sameday/standby", {}).get_json()
    assert roster["available"] == 0 and roster["haulers"][0]["name"] == "Rob"


def test_parse_replies():
    assert sameday.parse_standby_reply("Y") is True and sameday.parse_standby_reply("yes!") is True
    assert sameday.parse_standby_reply("N") is False and sameday.parse_standby_reply("Not today") is False
    assert sameday.parse_standby_reply("JOBS") is None and sameday.parse_standby_reply("") is None


# ------------------------------------------------------------------ Maya hook
def test_wave_async_only_for_today(app):
    _hauler("Rob", "+15615550301", 26.63, -80.05)
    today = _job()
    tomorrow = _job(when=(datetime.now(timezone.utc) + timedelta(days=2)).replace(tzinfo=None))
    with mock.patch("sameday.wave") as w, mock.patch("threading.Thread") as th:
        th.side_effect = lambda target, daemon: mock.MagicMock(start=lambda: target())
        sameday.wave_async(today.id, app)
        sameday.wave_async(tomorrow.id, app)
    assert w.call_count == 1 and w.call_args[0][0].id == today.id


def test_geocode_failure_is_not_cached_forever():
    with mock.patch.dict(os.environ, {"GOOGLE_PLACES_API_KEY": "k"}):
        with mock.patch("sameday._places_search_text", side_effect=RuntimeError("400 INVALID_ARGUMENT")):
            assert sameday.geocode("33461") is None
        # a stale negative entry (no timestamp, as written by the first deploy) is retried
        DeskSetting.put("geo:33462, fl", json.dumps({"lat": None}))
        with mock.patch("sameday._places_search_text", return_value=[{"location": {"latitude": 26.6, "longitude": -80.1}}]) as ts:
            assert sameday.geocode("33462") == (26.6, -80.1)
            assert ts.call_count == 1
            # fresh negative entry within the hour is honored
            assert sameday.geocode("33461") is None and ts.call_count == 1
        # radius sent to Google stays within its 50 km limit
        with mock.patch("requests.post") as post:
            post.return_value.json.return_value = {"places": []}
            post.return_value.raise_for_status = lambda: None
            sameday._places_search_text("k", "33463, FL")
            assert post.call_args.kwargs["json"]["locationBias"]["circle"]["radius"] <= 50000
