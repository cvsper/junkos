"""Audit 2026-09-10 — F09 / F10 / F11 / F12 / F18 / F30 regression tests.

Each test reproduces the audit scenario against the fixed code path:
  F09 schedule surcharge shows in the estimate; stale price_version -> 409;
      a $25 promo on a $200 job charges $175 (not $150)
  F10 coordinates required + validated; surge zones apply by geometry in NY time
  F11 negative quantity -> 400 (no negative disposal fees); quote scope -> 409
  F12 volume adjustment no longer KeyErrors; increase = separate intent,
      decrease = partial refund; decline keeps the price, no trip fee
  F18 unassigned cancellation -> $0 fee + full refund; on-the-way needs confirm;
      admin cancel refunds; guest manage token; reschedule re-prices + resets timers
  F30 legacy integer-ID route -> 410 when the flag is off; compat route delegates
"""
import json
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import mock

import pytest

from models import (
    db, User, Contractor, Job, Payment, PromoCode, Quote, SurgeZone, Refund,
    ChangeOrder, generate_uuid,
)
from timeutils import local_now

BOCA = {"street": "123 Test Ave, Boca Raton, FL 33432", "lat": 26.3683, "lng": -80.1289,
        "zip": "33432", "city": "Boca Raton", "state": "FL"}
_seq = iter(range(1, 100000))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _quiet(app):
    with mock.patch("dispatcher.has_active_coverage", return_value=True), \
         mock.patch("dispatcher.auto_assign_job_async"), \
         mock.patch("socket_events.notify_nearby_drivers"), \
         mock.patch("socket_events.broadcast_job_status"), \
         mock.patch("notifications.send_push_notification"):
        yield


def _future_date(days=10):
    d = local_now().date() + timedelta(days=days)
    # avoid weekends so the base estimate carries no surcharge
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d.isoformat()


def _customer(email=None):
    email = email or "cx{}@audit.test".format(next(_seq))
    u = User(id=generate_uuid(), email=email, name="Audit Cx", phone="+15615550{:03d}".format(next(_seq) % 1000),
             role="customer")
    db.session.add(u)
    db.session.commit()
    return u


def _hauler():
    u = User(id=generate_uuid(), email="h{}@audit.test".format(next(_seq)), name="Hauler", role="driver")
    db.session.add(u)
    db.session.flush()
    c = Contractor(id=generate_uuid(), user_id=u.id, is_online=True, approval_status="approved",
                   current_lat=26.37, current_lng=-80.12, avg_rating=4.8, truck_capacity=12.0)
    db.session.add(c)
    db.session.commit()
    return c


def _token(user_id):
    from auth_routes import generate_token
    return {"Authorization": "Bearer " + generate_token(user_id)}


def _job(customer=None, total=200.0, status="confirmed", paid=True, driver=None,
         hours_ahead=48, intent="pi_dev", discount=0.0, promo_id=None):
    customer = customer or _customer()
    if intent and intent.startswith("pi_dev"):
        intent = "pi_dev_{}".format(next(_seq))
    j = Job(id=generate_uuid(), customer_id=customer.id, status=status, address=BOCA["street"],
            lat=BOCA["lat"], lng=BOCA["lng"], items=[{"category": "sofa", "quantity": 1}],
            scheduled_at=datetime.now(timezone.utc) + timedelta(hours=hours_ahead),
            base_price=total, item_total=total, service_fee=round(total * 0.08, 2),
            total_price=total, discount_amount=discount, promo_code_id=promo_id,
            driver_id=driver.id if driver else None, confirmation_code="A{:07d}".format(next(_seq)))
    db.session.add(j)
    db.session.flush()
    db.session.add(Payment(id=generate_uuid(), job_id=j.id, amount=total, service_fee=j.service_fee,
                           payment_status="succeeded" if paid else "pending",
                           stripe_payment_intent_id=intent))
    db.session.commit()
    return j


def _estimate(client, items, date=None, slot="10-12", promo=None, address=BOCA, **extra):
    body = {"items": items, "address": address, "scheduledDate": date or _future_date(),
            "scheduledTimeSlot": slot}
    if promo:
        body["promo_code"] = promo
    body.update(extra)
    return client.post("/api/booking/estimate", json=body)


def _booking_payload(items, version, date=None, slot="10-12", **extra):
    body = {
        "address": BOCA, "items": items, "scheduledDate": date or _future_date(),
        "scheduledTimeSlot": slot, "price_version": version,
        "customerName": "Audit Cx", "customerEmail": "guest{}@audit.test".format(next(_seq)),
        "customerPhone": "5615551234",
    }
    body.update(extra)
    return body


# ---------------------------------------------------------------------------
# F09 — displayed price == charged price
# ---------------------------------------------------------------------------
class TestF09PriceVersion:
    def test_estimate_includes_schedule_surcharge(self, client):
        base = _estimate(client, [{"category": "sofa", "quantity": 1}]).get_json()["estimate"]
        today = local_now().date().isoformat()
        same_day = _estimate(client, [{"category": "sofa", "quantity": 1}], date=today).get_json()["estimate"]
        assert same_day["surge_amount"] > 0
        assert any("Same-day" in r for r in same_day["surge_reasons"])
        assert same_day["total"] > base["total"]
        assert same_day["price_version"] != base["price_version"]
        assert same_day["market_timezone"] == "America/New_York"

    def test_stale_price_version_is_rejected_then_reconfirmed(self, client):
        items = [{"category": "sofa", "quantity": 1}]
        shown = _estimate(client, items).get_json()  # customer saw the no-surcharge price
        today = local_now().date().isoformat()
        # ...but books same-day: the surcharge would have first appeared on the card
        resp = client.post("/api/booking", json=_booking_payload(items, shown["price_version"], date=today))
        assert resp.status_code == 409, resp.get_json()
        body = resp.get_json()
        assert body["code"] == "price_changed"
        assert body["total"] > shown["estimate"]["total"]
        assert body["estimate"]["surge_amount"] > 0
        # re-confirm with the server-issued version -> booked at exactly that total
        ok = client.post("/api/booking", json=_booking_payload(items, body["price_version"], date=today))
        assert ok.status_code == 201, ok.get_json()
        job = ok.get_json()["job"]
        assert job["total_price"] == body["total"]
        assert job["price_version"] == body["price_version"]
        assert ok.get_json()["manage_token"]

    def test_price_version_required_without_estimated_price(self, client):
        payload = _booking_payload([{"category": "sofa", "quantity": 1}], "")
        payload.pop("price_version")
        resp = client.post("/api/booking", json=payload)
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "price_version_required"

    def test_legacy_client_echoing_the_server_total_is_accepted(self, client):
        items = [{"category": "sofa", "quantity": 1}]
        est = _estimate(client, items).get_json()["estimate"]
        payload = _booking_payload(items, "")
        payload.pop("price_version")
        payload["estimated_price"] = est["total"]
        assert client.post("/api/booking", json=payload).status_code == 201
        payload["customerEmail"] = "other@audit.test"
        payload["estimated_price"] = est["total"] - 30
        assert client.post("/api/booking", json=payload).status_code == 409

    def test_promo_applied_once_25_off_200_charges_175(self, client):
        promo = PromoCode(id=generate_uuid(), code="AUDIT25", discount_type="fixed", discount_value=25.0,
                          is_active=True, use_count=0)
        db.session.add(promo)
        db.session.commit()
        # Booking is the single owner of the discount: stores the FINAL $175.
        job = _job(total=175.0, discount=25.0, promo_id=promo.id, paid=False, intent=None)
        assert job.total_price == 175.0 and job.discount_amount == 25.0

        fake_stripe = mock.MagicMock()
        fake_stripe.PaymentIntent.create.return_value = SimpleNamespace(id="pi_test_175", client_secret="sec")
        with mock.patch("routes.payments._get_stripe", return_value=fake_stripe), \
             mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_x"}):
            from routes.payments import checkout_token
            resp = client.post("/api/payments/create-intent-simple",
                               json={"bookingId": job.id, "amount": 175.0, "customerEmail": "x@audit.test",
                                     "checkout_token": checkout_token(job.id),
                                     "submission_key": generate_uuid()})
        assert resp.status_code == 201, resp.get_json()
        assert resp.get_json()["amount"] == 175.0
        assert fake_stripe.PaymentIntent.create.call_args.kwargs["amount"] == 17500  # not 15000
        assert promo.use_count == 0  # consumed on payment success, never at creation

    def test_booking_stores_discounted_total_and_versions_it(self, client):
        promo = PromoCode(id=generate_uuid(), code="TAKE25", discount_type="fixed", discount_value=25.0,
                          is_active=True, use_count=0)
        db.session.add(promo)
        db.session.commit()
        items = [{"category": "sofa", "quantity": 2}]
        plain = _estimate(client, items).get_json()["estimate"]
        with_promo = _estimate(client, items, promo="TAKE25").get_json()["estimate"]
        assert with_promo["discount_amount"] == 25.0
        assert with_promo["total"] == round(plain["total"] - 25.0, 2)
        # the un-discounted version is stale once a promo is applied
        stale = client.post("/api/booking", json=_booking_payload(items, plain["price_version"], promo_code="TAKE25"))
        assert stale.status_code == 409
        ok = client.post("/api/booking", json=_booking_payload(items, with_promo["price_version"], promo_code="TAKE25"))
        assert ok.status_code == 201, ok.get_json()
        job = ok.get_json()["job"]
        assert job["total_price"] == with_promo["total"]
        assert job["discount_amount"] == 25.0
        assert ok.get_json()["payment"]["amount"] == with_promo["total"]
        assert PromoCode.query.get(promo.id).use_count == 0

    def test_promo_redemption_is_unique_per_order(self, client):
        from routes.promos import redeem_promo_for_job
        promo = PromoCode(id=generate_uuid(), code="ONCE", discount_type="fixed", discount_value=10.0,
                          is_active=True, use_count=0)
        db.session.add(promo)
        db.session.commit()
        job = _job(total=100.0, discount=10.0, promo_id=promo.id)
        assert redeem_promo_for_job(job) is True
        assert redeem_promo_for_job(job) is False  # webhook replay / confirm race
        db.session.commit()
        assert PromoCode.query.get(promo.id).use_count == 1


# ---------------------------------------------------------------------------
# F10 — geography
# ---------------------------------------------------------------------------
class TestF10Geography:
    def test_booking_requires_coordinates(self, client):
        items = [{"category": "sofa", "quantity": 1}]
        version = _estimate(client, items).get_json()["price_version"]
        payload = _booking_payload(items, version)
        payload["address"] = {"street": BOCA["street"]}  # typed, never selected
        resp = client.post("/api/booking", json=payload)
        assert resp.status_code == 422
        assert resp.get_json()["code"] == "invalid_coordinates"
        payload["address"] = {"street": BOCA["street"], "lat": "NaN", "lng": 400}
        assert client.post("/api/booking", json=payload).status_code == 422

    def test_outside_market_is_422_not_charged(self, client):
        items = [{"category": "sofa", "quantity": 1}]
        resp = _estimate(client, items, address={"street": "1 Main St, Orlando FL", "lat": 28.54, "lng": -81.38})
        assert resp.status_code == 422
        assert resp.get_json()["code"] == "outside_market"

    def test_market_bounds_endpoint(self, client):
        m = client.get("/api/booking/market-bounds").get_json()["market"]
        assert m["timezone"] == "America/New_York"
        west, south, east, north = [float(x) for x in m["mapbox_bbox"].split(",")]
        assert south < BOCA["lat"] < north and west < BOCA["lng"] < east
        assert "Palm Beach" in m["counties"]

    def test_surge_zone_applies_only_where_geometry_contains_point(self, client):
        from routes.booking import _active_surge
        now = local_now()
        window = (now - timedelta(hours=1)).strftime("%H:%M"), (now + timedelta(hours=1)).strftime("%H:%M")
        far = SurgeZone(id=generate_uuid(), name="Homestead", surge_multiplier=1.5, is_active=True,
                        boundary={"lat": 25.47, "lng": -80.48, "radius_km": 5},
                        start_time=window[0], end_time=window[1], days_of_week=[now.weekday()])
        near = SurgeZone(id=generate_uuid(), name="Boca", surge_multiplier=1.25, is_active=True,
                         boundary=[{"lat": 26.30, "lng": -80.20}, {"lat": 26.30, "lng": -80.05},
                                   {"lat": 26.45, "lng": -80.05}, {"lat": 26.45, "lng": -80.20}],
                         start_time=window[0], end_time=window[1], days_of_week=[now.weekday()])
        legacy_no_geometry = SurgeZone(id=generate_uuid(), name="Everywhere", surge_multiplier=3.0,
                                       is_active=True, boundary=None)
        db.session.add_all([far, near, legacy_no_geometry])
        db.session.commit()
        assert _active_surge(BOCA["lat"], BOCA["lng"]) == (1.25, "Boca")
        assert _active_surge(25.47, -80.48) == (1.5, "Homestead")
        assert _active_surge(26.70, -80.06) == (1.0, None)
        est = _estimate(client, [{"category": "sofa", "quantity": 1}]).get_json()["estimate"]
        assert est["surge_zone"] == "Boca"
        assert any("Boca" in r for r in est["surge_reasons"])

    def test_surge_zone_window_is_evaluated_in_market_time(self, client):
        from routes.booking import _active_surge
        from zoneinfo import ZoneInfo
        # 21:30 Florida on a Tuesday == 01:30 UTC Wednesday
        local = datetime(2026, 9, 15, 21, 30, tzinfo=ZoneInfo("America/New_York"))
        zone = SurgeZone(id=generate_uuid(), name="Evening", surge_multiplier=1.4, is_active=True,
                         boundary={"north": 26.5, "south": 26.2, "east": -80.0, "west": -80.3},
                         start_time="20:00", end_time="23:00", days_of_week=[1])  # Tuesday
        db.session.add(zone)
        db.session.commit()
        assert _active_surge(BOCA["lat"], BOCA["lng"], when=local)[0] == 1.4
        assert _active_surge(BOCA["lat"], BOCA["lng"], when=local.astimezone(timezone.utc).replace(tzinfo=None).replace(tzinfo=ZoneInfo("America/New_York")))[0] == 1.0


# ---------------------------------------------------------------------------
# F11 — quantities + quotes
# ---------------------------------------------------------------------------
class TestF11ItemsAndQuotes:
    def test_negative_quantity_is_rejected(self, client):
        resp = _estimate(client, [{"category": "sofa", "quantity": 10}, {"category": "mattress", "quantity": -10}])
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "invalid_items"
        for bad in (0, 100, 1.5, "abc", True, float("inf")):
            r = _estimate(client, [{"category": "sofa", "quantity": bad}])
            assert r.status_code == 400, bad
        assert _estimate(client, [{"category": "spaceship", "quantity": 1}]).status_code == 400

    def test_engine_never_prices_negative_fees(self, app, db_session):
        """The audit's attack: 10 sofas $1,092.42 -> add -10 mattresses -> $892.42
        with -$200 of disposal fees. The malformed line is now dropped from BOTH
        the item loop and the recycling-fee loop, so it cannot underprice."""
        from routes.booking import calculate_estimate
        clean = calculate_estimate([{"category": "sofa", "quantity": 10}])
        attacked = calculate_estimate([
            {"category": "sofa", "quantity": 10},
            {"category": "mattress", "quantity": -10},
        ])
        assert attacked["total"] == clean["total"]
        assert attacked["recycling_fees"] >= 0
        assert attacked["total_quantity"] == clean["total_quantity"]
        # ...and every payable entry point rejects it outright rather than pricing it.
        assert all(line["quantity"] > 0 for line in attacked["items"])

    def _quote(self, items, zip_code="33432", email=None, user_id=None, price=150.0, binding=True,
               scheduled_date=None):
        from price_version import quote_scope_hash
        q = Quote(id=generate_uuid(), user_id=user_id, guest_email=email, zip_code=zip_code, zone="palm-beach",
                  status="binding" if binding else "pending_review", origin="vision",
                  price_cents=int(price * 100), estimated_volume_cubic_yards=2.0, confidence_score=0.9,
                  binding=binding, model_version="test", calibration_version="cal",
                  expires_at=datetime.now(timezone.utc) + timedelta(hours=24), photo_urls=["inline://x"],
                  scope_hash=quote_scope_hash(items, zip_code, scheduled_date))
        db.session.add(q)
        db.session.commit()
        return q

    def test_quote_scope_mismatch_is_409_no_silent_fallback(self, client):
        items = [{"category": "sofa", "quantity": 1}]
        q = self._quote(items, email="q@audit.test")
        bigger = [{"category": "sofa", "quantity": 4}]
        est = _estimate(client, bigger, quote_id=q.id, customerEmail="q@audit.test")
        assert est.status_code == 409 and est.get_json()["code"] == "quote_scope_mismatch"
        resp = client.post("/api/booking", json=_booking_payload(
            bigger, "x", quote_id=q.id, customerEmail="q@audit.test"))
        assert resp.status_code == 409
        assert resp.get_json()["code"] == "quote_scope_mismatch"
        assert Job.query.count() == 0

    def test_binding_quote_converts_once_at_locked_price(self, client):
        items = [{"category": "sofa", "quantity": 1}]
        q = self._quote(items, email="q2@audit.test", price=150.0)
        est = _estimate(client, items, quote_id=q.id, customerEmail="q2@audit.test").get_json()
        assert est["estimate"]["total"] == 150.0 and est["estimate"]["quote_locked"] is True
        payload = _booking_payload(items, est["price_version"], quote_id=q.id, customerEmail="q2@audit.test")
        ok = client.post("/api/booking", json=payload)
        assert ok.status_code == 201, ok.get_json()
        assert ok.get_json()["job"]["total_price"] == 150.0
        assert db.session.get(Quote, q.id).status == "booked"
        again = client.post("/api/booking", json=payload)
        assert again.status_code == 409 and again.get_json()["code"] == "quote_already_used"

    def test_quote_schedule_surcharge_requires_requote(self, client):
        items = [{"category": "sofa", "quantity": 1}]
        q = self._quote(items, email="q3@audit.test")
        today = local_now().date().isoformat()
        resp = client.post("/api/booking", json=_booking_payload(
            items, "x", date=today, quote_id=q.id, customerEmail="q3@audit.test"))
        assert resp.status_code == 409 and resp.get_json()["code"] == "quote_scope_mismatch"

    def test_quote_ownership_never_from_body(self, client):
        owner = _customer()
        items = [{"category": "sofa", "quantity": 1}]
        q = self._quote(items, user_id=owner.id)
        resp = client.post("/api/booking", json=_booking_payload(items, "x", quote_id=q.id, user_id=owner.id))
        assert resp.status_code == 409 and resp.get_json()["code"] == "quote_not_owned"
        est = _estimate(client, items, quote_id=q.id, user_id=owner.id)
        assert est.status_code == 409
        # the real owner (bearer token) can use it
        est = client.post("/api/booking/estimate", headers=_token(owner.id), json={
            "items": items, "address": BOCA, "scheduledDate": _future_date(), "quote_id": q.id})
        assert est.status_code == 200 and est.get_json()["estimate"]["quote_locked"] is True

    def test_anonymous_quote_needs_claim_token(self, client):
        from price_version import quote_claim_token
        items = [{"category": "sofa", "quantity": 1}]
        q = self._quote(items)
        assert _estimate(client, items, quote_id=q.id).status_code == 409
        ok = _estimate(client, items, quote_id=q.id, quote_token=quote_claim_token(q.id))
        assert ok.status_code == 200 and ok.get_json()["estimate"]["quote_locked"] is True


# ---------------------------------------------------------------------------
# F12 — change orders
# ---------------------------------------------------------------------------
def _live_stripe(intent_status="succeeded"):
    fake = mock.MagicMock()
    fake.PaymentIntent.retrieve.return_value = SimpleNamespace(
        id="pi_test_orig", customer="cus_1", payment_method="pm_1", status="succeeded")
    fake.PaymentIntent.create.return_value = SimpleNamespace(
        id="pi_test_delta", status=intent_status, client_secret="pi_test_delta_secret")
    fake.Refund.create.return_value = SimpleNamespace(id="re_test_1")
    return fake


class TestF12ChangeOrders:
    def _arrived(self, total=119.0):
        hauler = _hauler()
        job = _job(total=total, status="arrived", driver=hauler, intent="pi_test_orig")
        return job, hauler

    def test_volume_adjustment_no_longer_keyerrors_and_proposes(self, client):
        job, hauler = self._arrived()
        resp = client.post("/api/drivers/jobs/{}/volume".format(job.id), headers=_token(hauler.user_id),
                           json={"actual_volume": 20})
        assert resp.status_code == 200, resp.get_json()
        body = resp.get_json()
        assert body["auto_approved"] is False and body["new_price"] > body["original_price"]
        assert body["change_order_id"] and body["expires_at"]
        job = db.session.get(Job, job.id)
        assert job.volume_adjustment_proposed is True and job.adjusted_price == body["new_price"]
        assert job.total_price == 119.0  # nothing moves until the customer decides
        order = db.session.get(ChangeOrder, body["change_order_id"])
        assert order.status == "proposed" and order.version == 1

    def test_accept_increase_creates_separate_intent_never_modifies_original(self, client):
        job, hauler = self._arrived()
        fake = _live_stripe()
        with mock.patch("routes.payments._get_stripe", return_value=fake), \
             mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_x"}):
            prop = client.post("/api/drivers/jobs/{}/volume".format(job.id), headers=_token(hauler.user_id),
                               json={"actual_volume": 20}).get_json()
            resp = client.post("/api/jobs/{}/volume/approve".format(job.id), headers=_token(job.customer_id))
        assert resp.status_code == 200, resp.get_json()
        delta = round(prop["new_price"] - 119.0, 2)
        assert fake.PaymentIntent.create.call_args.kwargs["amount"] == int(round(delta * 100))
        assert fake.PaymentIntent.create.call_args.kwargs["off_session"] is True
        fake.PaymentIntent.modify.assert_not_called()
        job = db.session.get(Job, job.id)
        assert job.total_price == prop["new_price"] and job.volume_adjustment_proposed is False
        assert job.payment.amount == prop["new_price"]
        # shared split, not a fixed 20/80
        from routes.payments import PLATFORM_COMMISSION
        assert job.payment.commission == round(prop["new_price"] * PLATFORM_COMMISSION, 2)
        order = db.session.get(ChangeOrder, prop["change_order_id"])
        assert order.status == "settled" and order.settlement_intent_id == "pi_test_delta"

    def test_decrease_auto_settles_with_partial_refund(self, client):
        job, hauler = self._arrived(total=300.0)
        fake = _live_stripe()
        with mock.patch("routes.payments._get_stripe", return_value=fake), \
             mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_x"}):
            resp = client.post("/api/drivers/jobs/{}/volume".format(job.id), headers=_token(hauler.user_id),
                               json={"actual_volume": 1})
        body = resp.get_json()
        assert resp.status_code == 200 and body["auto_approved"] is True
        assert body["new_price"] < 300.0
        fake.Refund.create.assert_called_once()
        assert fake.Refund.create.call_args.kwargs["amount"] == int(round((300.0 - body["new_price"]) * 100))
        fake.PaymentIntent.modify.assert_not_called()
        job = db.session.get(Job, job.id)
        assert job.total_price == body["new_price"] and job.payment.payment_status == "partially_refunded"
        assert Refund.query.filter_by(payment_id=job.payment.id).first().status == "succeeded"

    def test_decline_keeps_original_price_no_trip_fee(self, client):
        job, hauler = self._arrived()
        client.post("/api/drivers/jobs/{}/volume".format(job.id), headers=_token(hauler.user_id),
                    json={"actual_volume": 20})
        resp = client.post("/api/jobs/{}/volume/decline".format(job.id), headers=_token(job.customer_id))
        assert resp.status_code == 200 and resp.get_json()["trip_fee"] == 0.0
        job = db.session.get(Job, job.id)
        assert job.status == "arrived" and job.total_price == 119.0 and job.cancellation_fee in (None, 0.0)
        assert job.volume_adjustment_proposed is False
        assert ChangeOrder.query.filter_by(job_id=job.id).first().status == "declined"
        # nothing pending any more
        assert client.post("/api/jobs/{}/volume/approve".format(job.id), headers=_token(job.customer_id)).status_code == 409

    def test_expired_proposal_cannot_be_accepted(self, client):
        job, hauler = self._arrived()
        prop = client.post("/api/drivers/jobs/{}/volume".format(job.id), headers=_token(hauler.user_id),
                           json={"actual_volume": 20}).get_json()
        order = db.session.get(ChangeOrder, prop["change_order_id"])
        order.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.session.commit()
        resp = client.post("/api/jobs/{}/volume/approve".format(job.id), headers=_token(job.customer_id))
        assert resp.status_code == 409 and resp.get_json()["code"] == "change_order_closed"
        assert db.session.get(Job, job.id).total_price == 119.0


# ---------------------------------------------------------------------------
# F18 — cancellation policy
# ---------------------------------------------------------------------------
class TestF18Cancellation:
    def test_unassigned_cancellation_is_free_with_full_refund(self, client):
        job = _job(total=200.0, status="confirmed", hours_ahead=1)  # inside the "$50" window
        resp = client.post("/api/jobs/{}/cancel".format(job.id), headers=_token(job.customer_id))
        assert resp.status_code == 200, resp.get_json()
        body = resp.get_json()
        assert body["cancellation_fee"] == 0.0 and body["refund_amount"] == 200.0
        assert body["reason_code"] == "unfulfilled_no_hauler"
        job = db.session.get(Job, job.id)
        assert job.status == "cancelled" and job.payment.payment_status == "refunded"
        assert Refund.query.filter_by(payment_id=job.payment.id).first().amount == 200.0

    def test_broadcasting_job_is_cancellable_free(self, client):
        job = _job(total=150.0, status="broadcasting", hours_ahead=1)
        resp = client.post("/api/jobs/{}/cancel".format(job.id), headers=_token(job.customer_id))
        assert resp.status_code == 200 and resp.get_json()["cancellation_fee"] == 0.0

    def test_assigned_before_en_route_applies_time_fee(self, client):
        job = _job(total=200.0, status="assigned", driver=_hauler(), hours_ahead=1)
        resp = client.post("/api/jobs/{}/cancel".format(job.id), headers=_token(job.customer_id))
        assert resp.status_code == 200
        assert resp.get_json()["cancellation_fee"] == 50.0 and resp.get_json()["refund_amount"] == 150.0
        assert db.session.get(Job, job.id).payment.payment_status == "partially_refunded"

    def test_en_route_is_a_request_with_disclosed_outcome(self, client):
        job = _job(total=200.0, status="en_route", driver=_hauler(), hours_ahead=1)
        preview = client.get("/api/jobs/{}/cancel-preview".format(job.id), headers=_token(job.customer_id)).get_json()
        assert preview["allowed"] is True and preview["requires_confirmation"] is True
        assert preview["cancellation_fee"] == 50.0
        resp = client.post("/api/jobs/{}/cancel".format(job.id), headers=_token(job.customer_id))
        assert resp.status_code == 409 and resp.get_json()["code"] == "confirmation_required"
        assert db.session.get(Job, job.id).status == "en_route"
        resp = client.post("/api/jobs/{}/cancel".format(job.id), headers=_token(job.customer_id), json={"confirm": True})
        assert resp.status_code == 200 and resp.get_json()["cancellation_fee"] == 50.0
        assert db.session.get(Job, job.id).status == "cancelled"

    def test_admin_cancellation_never_charges_customer(self, client):
        admin = User(id=generate_uuid(), email="admin{}@audit.test".format(next(_seq)), role="admin")
        db.session.add(admin)
        db.session.commit()
        job = _job(total=200.0, status="en_route", driver=_hauler(), hours_ahead=1)
        resp = client.put("/api/admin/jobs/{}/cancel".format(job.id), headers=_token(admin.id), json={"reason": "crew no-show"})
        assert resp.status_code == 200, resp.get_json()
        c = resp.get_json()["cancellation"]
        assert c["cancellation_fee"] == 0.0 and c["refund_amount"] == 200.0 and c["reason_code"] == "admin_cancelled"
        assert db.session.get(Job, job.id).payment.payment_status == "refunded"

    def test_policy_function_matrix(self, app, db_session):
        from cancellation import cancellation_outcome
        job = _job(total=100.0, status="completed")
        assert cancellation_outcome(job, "customer").allowed is False
        job = _job(total=100.0, status="arrived", driver=_hauler(), hours_ahead=1)
        o = cancellation_outcome(job, "operator")
        assert (o.allowed, o.fee, o.refund_amount, o.reason_code) == (True, 0.0, 100.0, "operator_cancelled")
        o = cancellation_outcome(job, "safety")
        assert o.fee == 0.0 and o.reason_code == "safety_cancelled"
        unpaid = _job(total=100.0, status="assigned", driver=_hauler(), hours_ahead=1, paid=False)
        o = cancellation_outcome(unpaid, "customer")
        assert o.fee == 50.0 and o.refund_amount == 0.0

    def test_guest_manage_token_allows_cancel_without_jwt(self, client):
        from cancellation import make_manage_token
        job = _job(total=120.0, status="confirmed")
        customer = db.session.get(User, job.customer_id)
        bad = client.post("/api/jobs/{}/cancel?token=nope".format(job.id))
        assert bad.status_code == 404
        wrong_job = make_manage_token(generate_uuid(), customer.email)
        assert client.post("/api/jobs/{}/cancel?token={}".format(job.id, wrong_job)).status_code == 404
        token = make_manage_token(job.id, customer.email)
        resp = client.post("/api/jobs/{}/cancel?token={}".format(job.id, token))
        assert resp.status_code == 200 and resp.get_json()["refund_amount"] == 120.0

    def test_reschedule_reprices_resets_timers_and_requalifies(self, client):
        hauler = _hauler()
        job = _job(total=200.0, status="assigned", driver=hauler, hours_ahead=72)
        job.noshow_t30_alerted = True
        job.reminder_sent = True
        db.session.commit()
        soon = local_now() + timedelta(hours=3)          # may roll past midnight late in the day
        today = soon.date().isoformat()
        slot = soon.strftime("%H:%M")
        resp = client.put("/api/jobs/{}/reschedule".format(job.id), headers=_token(job.customer_id),
                          json={"scheduled_date": today, "scheduled_time": slot})
        assert resp.status_code == 409, resp.get_json()
        body = resp.get_json()
        assert body["code"] == "price_changed" and body["delta"] > 0 and body["price_version"]
        # consent with the issued version -> applied, delta settled via change order
        with mock.patch("dispatcher._has_schedule_conflict", return_value=True):
            resp = client.put("/api/jobs/{}/reschedule".format(job.id), headers=_token(job.customer_id),
                              json={"scheduled_date": today, "scheduled_time": slot,
                                    "price_version": body["price_version"]})
        assert resp.status_code == 200, resp.get_json()
        out = resp.get_json()
        assert out["price_delta"] == body["delta"] and out["released_driver"] == hauler.id
        job = db.session.get(Job, job.id)
        assert job.total_price == body["total"] and job.price_version == body["price_version"]
        assert job.driver_id is None and job.status == "confirmed"
        assert job.noshow_t30_alerted is False and job.reminder_sent is False
        assert out["settlement"]["reason"] == "reschedule" and out["settlement"]["status"] in ("accepted", "settled")


# ---------------------------------------------------------------------------
# F30 — legacy booking paths
# ---------------------------------------------------------------------------
class TestF30LegacyPaths:
    def test_legacy_integer_id_route_is_410_when_flag_off(self, client, app):
        headers = {"X-API-Key": app.config["API_KEY"]}
        with mock.patch.dict(os.environ, {"LEGACY_BOOKINGS_ENABLED": ""}):
            resp = client.post("/api/bookings", headers=headers, json={
                "address": "x", "services": ["general"], "scheduled_datetime": "2026-10-01 09:00",
                "customer": {"name": "a", "email": "a@b.c", "phone": "1"}})
            assert resp.status_code == 410
            assert resp.get_json()["code"] == "legacy_bookings_disabled"
            assert resp.get_json()["upgrade"]["book"] == "/api/booking"
            assert client.get("/api/bookings/1", headers=headers).status_code == 410

    def test_compat_route_delegates_and_does_not_notify_or_consume_promo(self, client):
        promo = PromoCode(id=generate_uuid(), code="COMPAT10", discount_type="fixed", discount_value=10.0,
                          is_active=True, use_count=0)
        db.session.add(promo)
        db.session.commit()
        items = [{"category": "furniture", "quantity": 2}]
        est = _estimate(client, items, promo="COMPAT10").get_json()["estimate"]
        with mock.patch("routes.booking._notify_nearby_contractors") as notify, \
             mock.patch("notifications.send_booking_confirmation_email") as email:
            resp = client.post("/api/bookings/create", json={
                "address": BOCA["street"], "itemCategory": "furniture", "quantity": 2,
                "addressDetails": {"location": {"lat": BOCA["lat"], "lng": BOCA["lng"]}, "zip": "33432"},
                "selectedDate": _future_date(), "selectedTime": "10:00 AM",
                "promoCode": "COMPAT10", "totalAmount": est["total"],
                "customerInfo": {"name": "Portal Cx", "email": "portal{}@audit.test".format(next(_seq)), "phone": "5615550000"},
            })
        assert resp.status_code == 201, resp.get_json()
        body = resp.get_json()
        assert body["bookingId"] == body["job"]["id"]
        assert body["job"]["total_price"] == est["total"] and body["job"]["discount_amount"] == 10.0
        assert body["job"]["status"] == "pending"
        notify.assert_not_called()
        email.assert_not_called()
        assert PromoCode.query.get(promo.id).use_count == 0

    def test_compat_route_uses_canonical_validation(self, client):
        resp = client.post("/api/bookings/create", json={
            "address": BOCA["street"], "itemCategory": "furniture", "quantity": -3,
            "addressDetails": {"location": {"lat": BOCA["lat"], "lng": BOCA["lng"]}},
            "totalAmount": 50, "customerInfo": {"email": "v@audit.test"}})
        assert resp.status_code == 400 and resp.get_json()["code"] == "invalid_items"
        resp = client.post("/api/bookings/create", json={
            "address": BOCA["street"], "itemCategory": "furniture", "quantity": 1,
            "totalAmount": 50, "customerInfo": {"email": "v@audit.test"}})
        assert resp.status_code == 422 and resp.get_json()["code"] == "invalid_coordinates"
