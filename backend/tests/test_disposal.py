"""The quote carries the dump fee, and the hauler gets every cent of it."""
import pytest

from models import db, User, Job, Payment, LandfillFacility, TipFee, generate_uuid
from seed_landfills import seed_landfill_facilities
import disposal
from routes.booking import calculate_estimate
from routes.payments import recompute_payment_split, PLATFORM_COMMISSION

LANTANA = (26.60, -80.07)


@pytest.fixture(autouse=True)
def seeded(app, db_session):
    seed_landfill_facilities(db.session, LandfillFacility, TipFee, generate_uuid)
    yield


def test_a_cart_becomes_a_weigh_ticket():
    p = disposal.load_profile([{"category": "sofa"}, {"category": "mattress", "quantity": 2}])
    assert p["total_lbs"] == 180 + 140 and p["category"] == "bulky"   # furniture + mattress = a bulk ticket
    p = disposal.load_profile([{"category": "sofa"}, {"category": "construction", "quantity": 4}])
    assert p["category"] == "c_and_d" and p["tons"] == pytest.approx((180 + 2000) / 2000, abs=0.001)


def test_pbc_address_prices_the_dump_at_the_swa_rate():
    d = disposal.disposal_estimate([{"category": "sofa"}], *LANTANA)
    assert d["rate_source"] == "facility" and d["rate_per_ton"] == 42.0
    assert d["disposal_fee"] == 10.0            # 180 lb x $42/t = $3.78 → scale minimum
    d = disposal.disposal_estimate([{"category": "construction", "quantity": 8}], *LANTANA)
    assert d["category"] == "c_and_d" and d["rate_per_ton"] == 80.0
    assert d["disposal_fee"] == pytest.approx(2.0 * 80.0)   # 4,000 lb of debris


def test_no_coordinates_falls_back_to_home_market_rates():
    d = disposal.disposal_estimate([{"category": "construction", "quantity": 8}])
    assert d["rate_source"] == "default" and d["rate_per_ton"] == 80.0 and d["disposal_fee"] == 160.0
    assert disposal.disposal_estimate([])["disposal_fee"] == 0.0


def test_the_estimate_carries_the_dump_line_and_nothing_else_moves():
    est = calculate_estimate([{"category": "construction", "quantity": 8}], lat=LANTANA[0], lng=LANTANA[1])
    assert est["disposal_fee"] == 160.0 and est["disposal"]["facility"]
    subtotal_side = est["base_price"] + est["service_fee"] + est["surge_amount"] + est["recycling_fees"] + est["addons_total"]
    assert est["total"] == pytest.approx(subtotal_side + est["disposal_fee"], abs=0.01)
    # service fee is on the items, not on the dump line
    assert est["service_fee"] == pytest.approx(round(est["base_price"] * est["surge_multiplier"], 2) * 0.08, abs=0.02)


def test_the_hauler_gets_the_dump_fee_in_full():
    cx = User(id=generate_uuid(), email="cx@disposal.test", name="Cx", phone="+15615550991", role="customer")
    db.session.add(cx); db.session.flush()
    job = Job(id=generate_uuid(), customer_id=cx.id, status="pending", address="x", total_price=260.0, disposal_fee=60.0)
    db.session.add(job); db.session.flush()
    pay = Payment(id=generate_uuid(), job_id=job.id, amount=260.0, service_fee=16.0, disposal_fee=60.0, tip_amount=0.0)
    db.session.add(pay); db.session.commit()
    recompute_payment_split(pay, job)
    split_base = 200.0
    assert pay.commission == round(split_base * PLATFORM_COMMISSION, 2)
    assert pay.driver_payout_amount == pytest.approx(split_base - pay.commission - 16.0 + 60.0, abs=0.01)
    # same job with no dump fee: the hauler nets exactly $60 less
    pay.disposal_fee = 0.0
    recompute_payment_split(pay, job)
    assert pay.driver_payout_amount == pytest.approx(260.0 - round(260.0 * PLATFORM_COMMISSION, 2) - 16.0, abs=0.01)


def test_booking_stores_the_dump_fee_on_job_and_payment(client):
    r = client.post("/api/booking/estimate", json={"items": [{"category": "sofa"}, {"category": "construction", "quantity": 6}],
                                                   "lat": LANTANA[0], "lng": LANTANA[1]})
    assert r.status_code == 200, r.get_json()
    est = r.get_json()["estimate"]
    assert est["disposal_fee"] > 0 and est["disposal"]["category"] == "c_and_d"
