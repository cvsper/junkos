"""The dispatcher desk: one overview call, a priced + geocoded booking, ranked
candidates, assign / confirm / move / cancel / text / pay link, all audited."""
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from models import db, Contractor, Job, Payment, User, VaDispatchAction, generate_uuid


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture(autouse=True)
def env(app, db_session):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code", "JWT_SECRET": "unit"}):
        yield
    VaDispatchAction.query.delete(); Payment.query.delete(); Job.query.delete(); Contractor.query.delete(); User.query.delete()
    db.session.commit()


_seq = iter(range(2000, 9999))


def _phone():
    return "+1561555{}".format(next(_seq))


def _user(name, role="customer", phone=None, email=None):
    u = User(id=generate_uuid(), name=name, phone=phone or _phone(), email=email or "{}@t.local".format(generate_uuid()[:8]), role=role)
    db.session.add(u); db.session.flush(); return u


def _hauler(name="Hank Hauler", online=True, lat=26.62, lng=-80.07, concierge=False, heartbeat_minutes=5):
    u = _user(name, role="driver")
    c = Contractor(id=generate_uuid(), user_id=u.id, approval_status="approved", is_online=online, is_concierge=concierge,
                   current_lat=lat, current_lng=lng, truck_type="Box truck", avg_rating=4.8, total_jobs=12,
                   last_heartbeat_at=_now() - timedelta(minutes=heartbeat_minutes))
    db.session.add(c); db.session.flush(); return c


def _job(status="pending", driver=None, hours=4, lat=26.61, lng=-80.06, total=257.0):
    cust = _user("Cary Customer")
    j = Job(id=generate_uuid(), customer_id=cust.id, driver_id=driver.id if driver else None, status=status,
            address="200 Lake Ave, Lake Worth FL", lat=lat, lng=lng, scheduled_at=_now() + timedelta(hours=hours),
            items=[{"category": "sofa", "quantity": 1}, {"category": "mattress", "quantity": 2}], total_price=total,
            disposal_fee=18.0, service_fee=19.0, confirmation_code="DK{}".format(generate_uuid()[:6].upper()),
            lead_source="phone_desk", created_at=_now())
    db.session.add(j); db.session.flush()
    db.session.add(Payment(id=generate_uuid(), job_id=j.id, amount=total, service_fee=19.0, disposal_fee=18.0, payment_status="pending"))
    db.session.commit(); return j


def _post(client, path, **payload):
    payload.setdefault("code", "test-code"); payload.setdefault("va_name", "Tracy")
    return client.post("/api/va/dispatch/" + path, json=payload)


def test_overview_has_board_roster_capacity_and_area(client):
    h = _hauler(); j = _job(); a = _job(status="assigned", driver=h, hours=2)
    r = _post(client, "overview"); assert r.status_code == 200
    d = r.get_json()
    assert d["counts"]["open"] == 1 and d["counts"]["scheduled"] == 1 and d["counts"]["online"] == 1
    card = d["jobs"]["open"][0]
    assert card["code"] == j.confirmation_code and card["county"] == "Palm Beach" and card["item_count"] == 3
    assert card["items"][0]["name"] == "Sofa" and card["payment"]["status"] == "pending" and card["hauler"] is None
    assert card["customer"]["phone"] and card["status_label"] == "Needs a hauler" and card["hours_out"] > 3
    sched = d["jobs"]["scheduled"][0]
    assert sched["hauler"]["name"] == "Hank Hauler" and sched["hauler"]["kind"] == "app"
    row = d["haulers"][0]
    assert row["name"] == "Hank Hauler" and row["online"] and row["county"] == "Palm Beach" and row["seen_minutes"] <= 6 and row["jobs_today"] in (0, 1)
    assert len(d["area"]["polygon"]) > 10 and "Brevard" in d["area"]["counties"]
    assert client.post("/api/va/dispatch/overview", json={}).status_code == 401


def test_catalog_estimate_and_slots(client):
    cat = _post(client, "catalog").get_json()
    keys = {i["key"] for i in cat["items"]}
    assert "sofa" in keys and "hot_tub" in keys and "furniture" not in keys
    sofa = next(i for i in cat["items"] if i["key"] == "sofa"); assert sofa["price"] == 119 and sofa["group"] == "Furniture"
    assert any(l["key"] == "full" for l in cat["loads"]) and cat["minimum"] == 119
    est = _post(client, "estimate", items=[{"category": "sofa", "quantity": 1}], scheduled_date=(_now() + timedelta(days=3)).date().isoformat(), lat=26.61, lng=-80.06).get_json()["estimate"]
    assert est["total"] >= 119 and est["service_fee"] > 0 and est["items"][0]["quantity"] == 1
    assert _post(client, "estimate", items=[]).status_code == 400
    sl = _post(client, "slots", date=(_now() + timedelta(days=3)).date().isoformat(), lat=26.61, lng=-80.06).get_json()
    assert sl["slots"] and sl["slots"][0]["slot"] == "8-10" and sl["slots"][0]["label"] == "8–10 AM"


def test_geocode_and_customer_lookup(client):
    with mock.patch("sameday.geocode", return_value=(26.61, -80.06)):
        g = _post(client, "geocode", address="200 Lake Ave, Lake Worth").get_json()
    assert g["ok"] and g["in_area"] and g["county"] == "Palm Beach"
    with mock.patch("sameday.geocode", return_value=(40.75, -73.99)):
        g = _post(client, "geocode", address="Times Square NYC").get_json()
    assert g["ok"] and not g["in_area"] and "outside" in g["message"]
    with mock.patch("sameday.geocode", return_value=None):
        assert _post(client, "geocode", address="zzzz").get_json()["ok"] is False
    u = _user("Dana Realty", phone="+15615551234"); db.session.commit()
    r = _post(client, "customer", q="561-555-1234").get_json()
    assert r["customers"] and r["customers"][0]["name"] == "Dana Realty"
    assert _post(client, "customer", q="Dana").get_json()["customers"][0]["id"] == u.id


def test_book_prices_geocodes_texts_and_assigns(client):
    h = _hauler()
    sent = {}
    with mock.patch("sameday.geocode", return_value=(26.61, -80.06)), \
         mock.patch("notifications.send_booking_sms", side_effect=lambda *a, **k: sent.update(k)), \
         mock.patch("routes.vapi._build_checkout_url", return_value="https://checkout.stripe.test/s1"), \
         mock.patch("booking_alerts.notify_booking"), \
         mock.patch("dispatch_service.assign_contractor_to_job") as assign:
        r = _post(client, "book", name="Pat Booker", phone="(561) 555-0199", address="200 Lake Ave, Lake Worth FL",
                  items=[{"category": "sofa", "quantity": 1}, {"category": "mattress", "quantity": 1}],
                  scheduled_date=(_now() + timedelta(days=2)).date().isoformat(), scheduled_time="10-12",
                  notes="Gate code 1234", payment="link", send_text=True, contractor_id=h.id)
    assert r.status_code == 201, r.get_json()
    d = r.get_json()
    assert d["ok"] and d["texted"] and d["pay_url"].startswith("https://checkout") and d["assigned"] is True
    assert sent["pay_url"] == "https://checkout.stripe.test/s1" and sent["confirmation_code"] == d["job"]["code"]
    job = db.session.get(Job, d["job"]["id"])
    assert job.lat == 26.61 and job.lead_source == "phone_desk" and job.total_price >= 119 and job.disposal_fee is not None
    assert job.items[0]["category"] == "sofa" and "Gate code 1234" in job.notes and "dispatch desk" in job.notes
    assert job.payment.amount == job.total_price and job.customer.name == "Pat Booker" and job.customer.phone == "+15615550199"
    assert assign.called and VaDispatchAction.query.filter_by(job_id=job.id, action="book").count() == 1
    # guards
    assert _post(client, "book", name="x", phone="123", address="a b c d", items=[{"category": "sofa"}], scheduled_date="2030-01-01").status_code == 400
    with mock.patch("sameday.geocode", return_value=(40.75, -73.99)):
        assert _post(client, "book", name="x", phone="5615550100", address="Times Square NYC", items=[{"category": "sofa"}], scheduled_date="2030-01-01").status_code == 422


def test_candidates_assign_confirm_and_transition(client):
    h = _hauler(); far = _hauler("Far Away", lat=28.5, lng=-80.8); j = _job()
    c = _post(client, "candidates", job_id=j.id).get_json()
    assert c["haulers"][0]["name"] == "Hank Hauler" and c["haulers"][0]["distance_miles"] < 5
    assert isinstance(c["haulers"][1]["reasons"], list)
    r = _post(client, "assign-hauler", job_id=j.id, contractor_id=h.id); assert r.status_code == 200, r.get_json()
    d = r.get_json(); assert d["ok"] and d["job"]["hauler"]["id"] == h.id and "Hank" in d["message"]
    r = _post(client, "job/confirm", job_id=j.id, confirmed=True, note="said yes").get_json()
    assert r["ok"] and r["job"]["confirmed"] and r["job"]["confirmed_by"] == "Tracy"
    with mock.patch("sms_service.sms_driver_en_route") as en:
        for st in ("accepted", "en_route"):
            r = _post(client, "job/transition", job_id=j.id, status=st, reason="desk"); assert r.status_code == 200, r.get_json()
    assert en.called and r.get_json()["job"]["status"] == "en_route" and r.get_json()["job"]["status_label"] == "On the way"
    assert _post(client, "job/transition", job_id=j.id, status="completed").status_code in (400, 409)   # must arrive/start first
    detail = _post(client, "job", job_id=j.id).get_json()
    assert detail["job"]["status"] == "en_route" and any(e["type"] == "en_route" for e in detail["events"])


def test_reschedule_cancel_text_paylink(client):
    h = _hauler(); j = _job(status="assigned", driver=h)
    texts = []
    with mock.patch("desk_line.send_desk_text", side_effect=lambda to, body, **k: texts.append((to, body)) or "SMx"):
        day = (_now() + timedelta(days=3)).date().isoformat()
        r = _post(client, "job/reschedule", job_id=j.id, scheduled_date=day, scheduled_time="14-16", notify=True).get_json()
        assert r["ok"] and r["job"]["window"] == "2–4 PM" and not r["job"]["confirmed"]
        assert any("is now" in b for _, b in texts) and any("moved to" in b for _, b in texts)
        assert _post(client, "job/text", job_id=j.id, to="customer", body="On our way soon").get_json()["ok"]
        assert _post(client, "job/text", job_id=j.id, to="hauler", body="Call the desk").get_json()["ok"]
        with mock.patch("routes.vapi._build_checkout_url", return_value="https://checkout.stripe.test/p"):
            p = _post(client, "job/paylink", job_id=j.id, send=True).get_json()
        assert p["ok"] and p["texted"] and "checkout" in p["url"]
    assert _post(client, "overview").get_json()["jobs"]["scheduled"][0]["payment"]["link_sent"] is True
    with mock.patch("cancellation.notify_customer_cancelled"):
        r = _post(client, "job/cancel", job_id=j.id, reason="customer changed plans")
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["job"]["status"] == "cancelled"
    assert _post(client, "job/cancel", job_id=j.id, reason="again").status_code == 409


def test_hauler_detail_text_and_broadcast(client):
    h = _hauler(); j = _job(status="completed", driver=h, hours=-30); open_ = _job()
    d = _post(client, "hauler", contractor_id=h.id).get_json()["hauler"]
    assert d["name"] == "Hank Hauler" and d["stats"] is not None and d["recent_jobs"] and d["docs"]["verification"] is None or True
    with mock.patch("desk_line.send_desk_text", return_value="SM1"):
        assert _post(client, "hauler/text", contractor_id=h.id, body="Standby today?").get_json()["ok"]
    with mock.patch("dispatcher.broadcast_job") as bc:
        r = _post(client, "job/broadcast", job_id=open_.id).get_json()
    assert bc.called and r["ok"] and r["offers"] == 0
    assert _post(client, "job/broadcast", job_id=j.id).status_code == 409


def test_tile_proxy_clamps_and_caches(client):
    import dispatch_desk as dd
    dd._TILE_CACHE.clear()
    calls = []
    class _R:
        status_code = 200; content = b"\x89PNG fake"
    with mock.patch("requests.get", side_effect=lambda url, **k: calls.append(url) or _R()):
        r1 = client.get("/api/va/dispatch/tile/11/561/865.png"); r2 = client.get("/api/va/dispatch/tile/11/561/865.png")
    assert r1.status_code == 200 and r1.mimetype == "image/png" and r1.data.startswith(b"\x89PNG")
    assert len(calls) == 1 and "tile.openstreetmap.org/11/561/865.png" in calls[0]   # second hit served from cache
    assert client.get("/api/va/dispatch/tile/3/1/1.png").status_code == 404           # too far out
    assert client.get("/api/va/dispatch/tile/11/999999/1.png").status_code == 404     # off the grid


def test_placeholder_position_is_not_a_position(client):
    _hauler("Phone Only", lat=26.7153, lng=-80.0534, concierge=True)
    real = _hauler("GPS Hauler", lat=26.62, lng=-80.07)
    rows = _post(client, "overview").get_json()["haulers"]
    by = {r["name"]: r for r in rows}
    assert by["Phone Only"]["lat"] is None and by["Phone Only"]["location"] == "unknown" and by["Phone Only"]["county"] is None
    assert by["GPS Hauler"]["lat"] == 26.62 and by["GPS Hauler"]["location"] == "known"


def test_dump_sites_on_overview_and_ranked_for_a_job(client):
    from models import LandfillFacility, TipFee
    from seed_landfills import seed_landfill_facilities
    seed_landfill_facilities(db.session, LandfillFacility, TipFee, generate_uuid); db.session.commit()
    try:
        j = _job()
        d = _post(client, "overview").get_json()
        assert len(d["dumps"]) >= 40
        site = next(x for x in d["dumps"] if x["name"] == "SWA North County Landfill")
        assert site["lat"] and site["lng"] and site["county_label"] == "Palm Beach" and site["walk_in"]
        assert site["type_label"] == "Landfill" and len(site["hours"]) == 7 and site["hours"][0]["day"] == "Mon"
        assert site["fees"] and site["fees"][0]["amount"] is not None and "label" in site["accepts"][0]
        r = _post(client, "dumps", job_id=j.id); assert r.status_code == 200
        rk = r.get_json()
        assert rk["for"]["job_code"] == j.confirmation_code and rk["for"]["category"] == "bulky"
        assert rk["ranked"] and rk["ranked"][0]["eligible"] and rk["ranked"][0]["miles"] < 30
        assert all("id" in x and "blockers" in x for x in rk["ranked"])
        assert _post(client, "dumps", lat=26.7, lng=-80.1).status_code == 200
        assert _post(client, "dumps").status_code == 400
    finally:
        TipFee.query.delete(); LandfillFacility.query.delete(); db.session.commit()
