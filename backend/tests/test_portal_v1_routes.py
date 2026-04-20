"""
B2B Commercial Portal — v1 expansion route + generator tests (Spec 04 §9).

Covers the critical paths for the v1 scope:

  * Unit CRUD (list / create / update / delete) w/ tenant guard
  * Recurring schedule generator produces Job rows + advances next_run_at
  * Monthly invoice generation sums completed-job totals correctly
  * Audit-mutation decorator captures before/after snapshots
  * ESG report math (tonnage -> CO2e)
  * SSO endpoints return 503 when env vars are missing
"""

import datetime as _dt
import os
import sys

import pytest

# Env setup MUST happen before importing app.
os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("DATABASE_URL", "")
os.environ.setdefault("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-do-not-use-in-production")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("ENABLE_SCHEDULER", "")
os.environ.setdefault("PORTAL_SALES_SERVICE_TOKEN", "test-service-token-abc123")
# Ensure SSO env is UNSET for the 503 test (the tests are in-process).
for _k in (
    "GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET",
    "ENTRA_CLIENT_ID", "ENTRA_CLIENT_SECRET", "ENTRA_TENANT_ID",
):
    os.environ.pop(_k, None)

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from models import db, User, Org, OrgMember, Job, PortalProperty
from portal_v1_models import (
    PortalUnit, PortalRecurringSchedule, PortalV1AuditLog,
)

SERVICE_TOKEN = "test-service-token-abc123"


# ---------------------------------------------------------------------------
# Standalone test app — we build a minimal Flask app that registers only
# the portal-related blueprints.  This lets the v1 tests run even when
# the full server.py import chain is broken (pre-existing issue with
# routes/__init__.py eager-importing routes.quotes which doesn't exist).
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def app():
    from flask import Flask

    # Import portal routes DIRECTLY (not via routes package __init__)
    # to avoid the broken wildcard import.
    from routes.portal import portal_bp
    from routes.portal_v1 import portal_v1_bp
    from routes.portal_sso import portal_sso_bp

    flask_app = Flask(__name__)
    flask_app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SERVER_NAME": None,
        "RATELIMIT_ENABLED": False,
        "SECRET_KEY": os.environ["SECRET_KEY"],
    })
    db.init_app(flask_app)
    flask_app.register_blueprint(portal_bp)
    flask_app.register_blueprint(portal_v1_bp)
    flask_app.register_blueprint(portal_sso_bp)

    with flask_app.app_context():
        db.create_all()
        # Add the ALTER TABLE columns (jobs.unit_id, orgs.esg_*).
        from portal_v1_migrations import apply_sqlalchemy
        apply_sqlalchemy(db.engine)
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture(scope="function")
def db_session(app):
    with app.app_context():
        yield db.session
        db.session.rollback()
        # Clean all tables between tests.
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()


@pytest.fixture(scope="function")
def client(app, db_session):
    with app.test_client() as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# Helpers (mirrors of the MVP test helpers)
# ---------------------------------------------------------------------------
def _bootstrap_org(client, name, owner_email, tier="pro"):
    resp = client.post(
        "/portal/v1/orgs",
        json={
            "name": name,
            "billing_email": owner_email,
            "owner_email": owner_email,
            "tier": tier,
        },
        headers={"X-Service-Token": SERVICE_TOKEN},
    )
    assert resp.status_code == 201, resp.get_json()
    data = resp.get_json()
    return data["org"], data["invite_token"], data["owner_user_id"]


def _accept_invite(client, invite_token):
    resp = client.post(
        "/portal/v1/orgs/invite/accept",
        json={"invite_token": invite_token, "password": "Passw0rd!"},
    )
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()


def _hdr(token):
    return {"Authorization": "Bearer {}".format(token)}


def _token_for_org(org_id):
    """Owner token for `org_id` (assumes owner already exists via bootstrap)."""
    from routes.portal import mint_portal_token

    owner = (
        db.session.query(OrgMember).filter_by(org_id=org_id, role="owner").first()
    )
    return mint_portal_token(owner.user_id, org_id, "owner", [])


def _seed_org_and_property(client, name="V1 Co", email="v1@x.example"):
    """Bootstrap an org, accept invite, create a property.  Returns
    (org, token, property)."""
    org, invite, _ = _bootstrap_org(client, name, email)
    _accept_invite(client, invite)
    token = _token_for_org(org["id"])
    resp = client.post(
        "/portal/v1/properties",
        json={"name": "Main Tower", "zip": "33139", "unit_count": 10},
        headers=_hdr(token),
    )
    assert resp.status_code == 201
    return org, token, resp.get_json()


# ===========================================================================
# Units
# ===========================================================================
def test_create_and_list_units(client, db_session):
    org, token, prop = _seed_org_and_property(client)

    # Empty initially
    r = client.get(
        "/portal/v1/properties/{}/units".format(prop["id"]),
        headers=_hdr(token),
    )
    assert r.status_code == 200
    assert r.get_json()["units"] == []

    # Create
    r = client.post(
        "/portal/v1/properties/{}/units".format(prop["id"]),
        json={"unit_number": "101", "sqft": 850, "access_notes": "Key under mat"},
        headers=_hdr(token),
    )
    assert r.status_code == 201, r.get_json()
    unit = r.get_json()
    assert unit["unit_number"] == "101"
    assert unit["sqft"] == 850

    # Duplicate unit_number on same property -> 409
    r2 = client.post(
        "/portal/v1/properties/{}/units".format(prop["id"]),
        json={"unit_number": "101"},
        headers=_hdr(token),
    )
    assert r2.status_code == 409

    # List
    r3 = client.get(
        "/portal/v1/properties/{}/units".format(prop["id"]),
        headers=_hdr(token),
    )
    assert len(r3.get_json()["units"]) == 1


def test_unit_update_and_delete(client, db_session):
    org, token, prop = _seed_org_and_property(client, "UDel Co", "udel@x.example")
    unit = client.post(
        "/portal/v1/properties/{}/units".format(prop["id"]),
        json={"unit_number": "A1"},
        headers=_hdr(token),
    ).get_json()

    # PATCH
    r = client.patch(
        "/portal/v1/units/{}".format(unit["id"]),
        json={"status": "inactive", "access_notes": "Gate code 4242"},
        headers=_hdr(token),
    )
    assert r.status_code == 200
    assert r.get_json()["status"] == "inactive"

    # DELETE
    r = client.delete(
        "/portal/v1/units/{}".format(unit["id"]),
        headers=_hdr(token),
    )
    assert r.status_code == 200

    # 404 after delete
    r = client.patch(
        "/portal/v1/units/{}".format(unit["id"]),
        json={"status": "active"},
        headers=_hdr(token),
    )
    assert r.status_code == 404


def test_unit_tenant_isolation(client, db_session):
    """Org B cannot see or mutate Org A's unit."""
    _, tok_a, prop_a = _seed_org_and_property(client, "UnitsA", "ua@x.example")
    _, tok_b, _prop_b = _seed_org_and_property(client, "UnitsB", "ub@x.example")

    unit = client.post(
        "/portal/v1/properties/{}/units".format(prop_a["id"]),
        json={"unit_number": "A1"},
        headers=_hdr(tok_a),
    ).get_json()

    # B cannot list A's units
    r = client.get(
        "/portal/v1/properties/{}/units".format(prop_a["id"]),
        headers=_hdr(tok_b),
    )
    assert r.status_code == 404

    # B cannot PATCH A's unit
    r = client.patch(
        "/portal/v1/units/{}".format(unit["id"]),
        json={"status": "inactive"},
        headers=_hdr(tok_b),
    )
    assert r.status_code == 404


# ===========================================================================
# Recurring schedule generator
# ===========================================================================
def test_recurring_generator_creates_jobs(client, db_session):
    from portal_recurring import generate_jobs_for_due_schedules

    org, token, prop = _seed_org_and_property(client, "Recur Co", "rc@x.example")

    unit = client.post(
        "/portal/v1/properties/{}/units".format(prop["id"]),
        json={"unit_number": "U1"},
        headers=_hdr(token),
    ).get_json()

    # Due right now
    past = (_dt.datetime.utcnow() - _dt.timedelta(minutes=1)).isoformat()
    r = client.post(
        "/portal/v1/recurring",
        json={
            "property_id": prop["id"],
            "unit_id": unit["id"],
            "cadence": "weekly",
            "next_run_at": past,
        },
        headers=_hdr(token),
    )
    assert r.status_code == 201, r.get_json()

    # Run
    ids = generate_jobs_for_due_schedules(_dt.datetime.utcnow())
    assert len(ids) == 1
    job = db.session.get(Job, ids[0])
    assert job is not None
    assert job.org_id == org["id"]
    assert job.status == "pending"

    # next_run_at advanced
    sched = db.session.query(PortalRecurringSchedule).first()
    assert sched.next_run_at > _dt.datetime.utcnow()


def test_recurring_generator_skips_future(client, db_session):
    from portal_recurring import generate_jobs_for_due_schedules

    org, token, prop = _seed_org_and_property(
        client, "Future Co", "future@x.example",
    )

    future = (_dt.datetime.utcnow() + _dt.timedelta(days=1)).isoformat()
    client.post(
        "/portal/v1/recurring",
        json={
            "property_id": prop["id"],
            "cadence": "weekly",
            "next_run_at": future,
        },
        headers=_hdr(token),
    )

    ids = generate_jobs_for_due_schedules(_dt.datetime.utcnow())
    assert ids == []


# ===========================================================================
# Monthly invoicing
# ===========================================================================
def test_monthly_invoice_sums_completed_jobs(client, db_session):
    from portal_invoicing import generate_monthly_invoices
    from models import PortalInvoice

    org, token, _prop = _seed_org_and_property(client, "Inv Co", "inv@x.example")
    owner = db.session.query(OrgMember).filter_by(org_id=org["id"]).first()

    # Seed 3 completed jobs in March 2026 (target month).
    target_month, target_year = 3, 2026
    for price in (120.00, 80.50, 200.25):
        j = Job(
            customer_id=owner.user_id,
            org_id=org["id"],
            status="completed",
            address="123 Main",
            total_price=price,
            completed_at=_dt.datetime(target_year, target_month, 15, 12, 0),
        )
        db.session.add(j)

    # One completed job in a DIFFERENT month — must not be included.
    db.session.add(Job(
        customer_id=owner.user_id,
        org_id=org["id"],
        status="completed",
        address="999 Far Away",
        total_price=999.99,
        completed_at=_dt.datetime(target_year, 2, 10, 12, 0),
    ))
    # One pending job in the target month — must not be included.
    db.session.add(Job(
        customer_id=owner.user_id,
        org_id=org["id"],
        status="pending",
        address="555 Open",
        total_price=500.0,
        completed_at=_dt.datetime(target_year, target_month, 20, 12, 0),
    ))
    db.session.commit()

    ids = generate_monthly_invoices(target_month, target_year)
    assert len(ids) == 1

    inv = db.session.get(PortalInvoice, ids[0])
    # (120.00 + 80.50 + 200.25) * 100 = 40075 cents
    assert inv.subtotal_cents == 40075
    assert inv.total_cents == 40075
    assert inv.status == "open"
    assert inv.due_at is not None
    # 3 line items (one per completed job).
    assert len(inv.line_items) == 3

    # Re-run is idempotent.
    ids2 = generate_monthly_invoices(target_month, target_year)
    assert ids2 == []


# ===========================================================================
# Audit log capture
# ===========================================================================
def test_audit_captures_unit_create_and_update(client, db_session):
    org, token, prop = _seed_org_and_property(client, "Aud Co", "aud@x.example")

    # Create
    r = client.post(
        "/portal/v1/properties/{}/units".format(prop["id"]),
        json={"unit_number": "Aud-1", "sqft": 500},
        headers=_hdr(token),
    )
    assert r.status_code == 201
    unit_id = r.get_json()["id"]

    # Update
    r = client.patch(
        "/portal/v1/units/{}".format(unit_id),
        json={"sqft": 650},
        headers=_hdr(token),
    )
    assert r.status_code == 200

    # Inspect audit log
    entries = (
        db.session.query(PortalV1AuditLog)
        .filter_by(org_id=org["id"], entity_type="portal_unit")
        .order_by(PortalV1AuditLog.created_at.asc())
        .all()
    )
    assert len(entries) >= 2
    create_entry = entries[0]
    update_entry = entries[-1]

    assert create_entry.action == "create"
    assert create_entry.before_json is None
    assert create_entry.after_json is not None
    # Create audit logs the response body; the response includes sqft=500.
    assert create_entry.after_json.get("sqft") == 500

    assert update_entry.action == "update"
    # before snapshot should hold the pre-update sqft
    assert (update_entry.before_json or {}).get("sqft") == 500
    assert (update_entry.after_json or {}).get("sqft") == 650


# ===========================================================================
# ESG report math
# ===========================================================================
def test_esg_report_math(client, db_session):
    from portal_esg import CO2E_PER_TONNE

    org, token, _prop = _seed_org_and_property(
        client, "ESG Co", "esg@x.example",
    )
    owner = db.session.query(OrgMember).filter_by(org_id=org["id"]).first()

    # 3 completed jobs in April 2026, tonnages 1.0, 2.5, 0.5 = 4.0 total
    target_month, target_year = 4, 2026
    for tonnes in (1.0, 2.5, 0.5):
        db.session.add(Job(
            customer_id=owner.user_id,
            org_id=org["id"],
            status="completed",
            address="ESG Lane",
            volume_estimate=tonnes,
            completed_at=_dt.datetime(target_year, target_month, 10, 12, 0),
        ))
    # Out-of-range job should NOT be counted.
    db.session.add(Job(
        customer_id=owner.user_id,
        org_id=org["id"],
        status="completed",
        address="Wrong Month",
        volume_estimate=10.0,
        completed_at=_dt.datetime(target_year, 5, 10, 12, 0),
    ))
    db.session.commit()

    r = client.get(
        "/portal/v1/esg/report?month={}&year={}".format(target_month, target_year),
        headers=_hdr(token),
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["total_jobs"] == 3
    assert data["total_tonnage"] == 4.0
    assert data["co2e_tonnes"] == round(4.0 * CO2E_PER_TONNE, 3)
    assert data["diverted_percent"] == 100.0


def test_esg_settings_patch_and_read(client, db_session):
    org, token, _prop = _seed_org_and_property(
        client, "ESGS Co", "esgs@x.example",
    )

    # Default
    r = client.get("/portal/v1/esg/settings", headers=_hdr(token))
    assert r.status_code == 200
    assert r.get_json()["esg_report_enabled"] is False

    # Patch
    r = client.patch(
        "/portal/v1/esg/settings",
        json={"esg_report_enabled": True, "esg_contact_email": "esg@co.example"},
        headers=_hdr(token),
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["esg_report_enabled"] is True
    assert body["esg_contact_email"] == "esg@co.example"


def test_esg_report_requires_params(client, db_session):
    _, token, _ = _seed_org_and_property(
        client, "ESG Bad Co", "esgbad@x.example",
    )
    r = client.get("/portal/v1/esg/report", headers=_hdr(token))
    assert r.status_code == 400


# ===========================================================================
# SSO skeleton — all four endpoints 503 when env is unset
# ===========================================================================
@pytest.mark.parametrize(
    "path",
    [
        "/portal/v1/auth/sso/google/start",
        "/portal/v1/auth/sso/google/callback",
        "/portal/v1/auth/sso/entra/start",
        "/portal/v1/auth/sso/entra/callback",
    ],
)
def test_sso_returns_503_when_unset(client, db_session, path):
    # Make doubly sure env is unset (session-scoped env could have been
    # mutated by another suite — strip before asserting).
    for k in (
        "GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET",
        "ENTRA_CLIENT_ID", "ENTRA_CLIENT_SECRET", "ENTRA_TENANT_ID",
    ):
        os.environ.pop(k, None)

    r = client.get(path)
    assert r.status_code == 503
    body = r.get_json()
    assert body.get("error") == "sso_not_configured"
    assert body.get("missing_env")
