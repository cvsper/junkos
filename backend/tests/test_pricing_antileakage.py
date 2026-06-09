"""Tests for the pricing upgrade + anti-leakage changes.

These are intentionally self-contained: they build a minimal Flask app bound to
an in-memory SQLite DB and exercise the pricing/promo/quote logic directly,
without importing the full ``server`` (socketio/stripe) stack. That keeps them
fast and runnable even in trimmed environments.

Covers:
  A. Demand-based auto-surge        (routes.booking._demand_surge)
  B. Vision-quote cost guard         (routes.quotes dedupe + daily budget)
  C. Economics endpoint gating       (routes.pricing.get_pricing_config)
  D. Promo per-customer cap          (routes.promos validate/confirm)
"""

import os
import sys

import pytest

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

os.environ.pop("REDIS_URL", None)  # exercise the in-process dedupe path

from flask import Flask  # noqa: E402
from models import (  # noqa: E402
    db, User, Job, Contractor, PricingConfig, PromoCode, PromoRedemption,
    VisionInferenceLog, generate_uuid,
)
import routes.booking as booking  # noqa: E402
import routes.promos as promos  # noqa: E402
import routes.quotes as quotes  # noqa: E402
import routes.pricing as pricing  # noqa: E402


@pytest.fixture()
def app():
    flask_app = Flask(__name__)
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    flask_app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(flask_app)
    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()


def _seed_user(role="customer", email=None):
    u = User(id=generate_uuid(), email=email or (generate_uuid() + "@x.com"), role=role)
    db.session.add(u)
    db.session.flush()
    return u


# ---------------------------------------------------------------------------
# A. Demand-based auto-surge
# ---------------------------------------------------------------------------
def test_demand_surge_disabled_by_default(app):
    mult, reason = booking._demand_surge(26.12, -80.13)
    assert mult == 1.0 and reason is None


def test_demand_surge_rises_with_demand(app):
    db.session.add(PricingConfig(key="demand_surge_enabled", value=True))
    cust = _seed_user("customer")
    drv = _seed_user("driver")
    for _ in range(4):  # 4 open jobs near the point
        db.session.add(Job(id=generate_uuid(), customer_id=cust.id, status="pending",
                           address="x", lat=26.121, lng=-80.131, items=[]))
    db.session.add(Contractor(id=generate_uuid(), user_id=drv.id, is_online=True,
                              approval_status="approved",
                              current_lat=26.122, current_lng=-80.132))  # 1 driver
    db.session.commit()

    mult, reason = booking._demand_surge(26.12, -80.13)
    assert mult > 1.0
    assert reason and "demand" in reason.lower()

    est = booking.calculate_estimate([{"category": "sofa", "quantity": 1}],
                                     lat=26.12, lng=-80.13)
    assert est["surge_multiplier"] > 1.0


def test_demand_surge_missing_coords_noop(app):
    db.session.add(PricingConfig(key="demand_surge_enabled", value=True))
    db.session.commit()
    assert booking._demand_surge(None, None) == (1.0, None)


# ---------------------------------------------------------------------------
# B. Vision-quote cost guard
# ---------------------------------------------------------------------------
def test_image_hash_stable_and_distinct(app):
    a = [{"kind": "url", "value": "http://x/a.jpg"}]
    b = [{"kind": "url", "value": "http://x/b.jpg"}]
    assert quotes._images_hash(a) == quotes._images_hash(a)
    assert quotes._images_hash(a) != quotes._images_hash(b)


def test_dedupe_roundtrip(app):
    h = quotes._images_hash([{"kind": "url", "value": "http://x/c.jpg"}])
    quotes._dedupe_put(h, "quote-xyz")
    assert quotes._dedupe_get(h) == "quote-xyz"
    assert quotes._dedupe_get("missing-hash") is None


def test_daily_spend_accumulates(app):
    assert quotes._vision_spend_today_cents() == 0.0
    db.session.add(VisionInferenceLog(
        id=generate_uuid(), quote_id=None, model="m", prompt_hash="x",
        input_tokens=0, output_tokens=0, cost_cents=123.0, latency_ms=1,
        raw_response={},
    ))
    db.session.commit()
    assert quotes._vision_spend_today_cents() == 123.0


# ---------------------------------------------------------------------------
# C. Economics endpoint gating
# ---------------------------------------------------------------------------
def test_public_config_hides_commission(app):
    with app.test_request_context():
        resp, code = pricing.get_pricing_config()
    body = resp.get_json()
    assert code == 200
    assert "commission_rate" not in body["config"]
    assert "minimum_job_price" in body["config"]


# ---------------------------------------------------------------------------
# D. Promo per-customer cap + paid-only counting
# ---------------------------------------------------------------------------
def _make_promo(per_user_limit=1):
    p = PromoCode(id=generate_uuid(), code="SAVE10", discount_type="percentage",
                  discount_value=10, per_user_limit=per_user_limit, use_count=0,
                  is_active=True)
    db.session.add(p)
    db.session.commit()
    return p


def test_promo_paid_only_counting_and_per_customer_cap(app):
    promo = _make_promo()
    cust = _seed_user("customer")

    # First validation succeeds.
    _, disc, err = promos.validate_promo_code("SAVE10", 100.0, email="a@b.com")
    assert err is None and disc == 10.0

    # Reserve against a job; use_count must NOT move until payment.
    job = Job(id=generate_uuid(), customer_id=cust.id, status="pending",
              address="x", items=[])
    db.session.add(job)
    db.session.flush()
    db.session.add(PromoRedemption(id=generate_uuid(), promo_code_id=promo.id,
                                   email="a@b.com", job_id=job.id, status="reserved"))
    db.session.commit()
    assert promo.use_count == 0

    # Payment success confirms the redemption (and is idempotent).
    promos.confirm_promo_redemption(job)
    promos.confirm_promo_redemption(job)
    db.session.commit()
    db.session.refresh(promo)
    assert promo.use_count == 1
    assert PromoRedemption.query.filter_by(job_id=job.id).first().status == "confirmed"

    # Same customer is now blocked; a different customer is still allowed.
    _, _, err_same = promos.validate_promo_code("SAVE10", 100.0, email="a@b.com")
    assert err_same and "already used" in err_same
    _, _, err_other = promos.validate_promo_code("SAVE10", 100.0, email="z@z.com")
    assert err_other is None


def test_promo_anonymous_preview_skips_per_user_check(app):
    _make_promo()
    _, _, err = promos.validate_promo_code("SAVE10", 100.0)  # no identity
    assert err is None
