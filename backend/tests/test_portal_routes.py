"""
B2B Commercial Portal — route tests (spec 04).

Covers the critical paths:
  * Sales service-token bootstrap creates Org + owner + invite
  * Invite acceptance mints a portal JWT
  * GET /orgs/me returns the caller's org (and only that org)
  * **Tenant isolation:** org-A token CANNOT read/write org-B data
  * RBAC: viewer blocked on PATCH /orgs/me; admin allowed
  * Jobs list is scoped by org_id
  * Dashboard summary shape
"""

import os
import pytest

# Set before importing app so portal sees the token
os.environ.setdefault("PORTAL_SALES_SERVICE_TOKEN", "test-service-token-abc123")

from models import db, User, Org, OrgMember, Job


SERVICE_TOKEN = "test-service-token-abc123"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _bootstrap_org(client, name, owner_email, tier="pro"):
    """Use the service-token endpoint to create an org + owner. Returns
    (org_dict, invite_token, owner_user_id)."""
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


def _accept_invite(client, invite_token, password="Passw0rd!"):
    resp = client.post(
        "/portal/v1/orgs/invite/accept",
        json={"invite_token": invite_token, "password": password},
    )
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()


def _hdr(token):
    return {"Authorization": "Bearer {}".format(token)}


def _mint_member_token(org_id, user_id, role):
    """Back-door: create a member directly + mint a portal token."""
    from routes.portal import mint_portal_token

    existing = (
        db.session.query(OrgMember)
        .filter_by(org_id=org_id, user_id=user_id)
        .first()
    )
    if not existing:
        m = OrgMember(
            org_id=org_id, user_id=user_id, role=role, scopes=[],
        )
        import datetime as _dt
        m.joined_at = _dt.datetime.utcnow()
        db.session.add(m)
        db.session.commit()
    return mint_portal_token(user_id, org_id, role, [])


# ---------------------------------------------------------------------------
# Sales bootstrap
# ---------------------------------------------------------------------------
def test_service_token_required_to_create_org(client, db_session):
    resp = client.post(
        "/portal/v1/orgs",
        json={
            "name": "No Auth Inc",
            "billing_email": "noauth@example.com",
            "owner_email": "noauth@example.com",
        },
    )
    assert resp.status_code == 401


def test_sales_bootstrap_creates_org_and_invite(client, db_session):
    org, invite, owner_id = _bootstrap_org(
        client, "Coastal Rental", "linda@coastal.example", tier="pro"
    )
    assert org["name"] == "Coastal Rental"
    assert org["slug"].startswith("coastal-rental")
    assert org["tier"] == "pro"
    assert org["status"] == "trial"
    assert invite and len(invite) >= 32

    # DB state
    o = db.session.query(Org).filter_by(id=org["id"]).first()
    assert o is not None
    members = db.session.query(OrgMember).filter_by(org_id=o.id).all()
    assert len(members) == 1
    assert members[0].role == "owner"
    assert members[0].invite_token == invite
    assert members[0].joined_at is None  # not yet redeemed


# ---------------------------------------------------------------------------
# Invite redemption
# ---------------------------------------------------------------------------
def test_invite_accept_mints_portal_token(client, db_session):
    _, invite, owner_id = _bootstrap_org(
        client, "Acme GC", "mike@acme.example", tier="starter"
    )
    result = _accept_invite(client, invite)
    assert result["token"]
    assert result["role"] == "owner"
    assert result["user_id"] == owner_id

    # Second accept should fail — token is nulled after redemption, so 404
    resp2 = client.post(
        "/portal/v1/orgs/invite/accept",
        json={"invite_token": invite, "password": "x"},
    )
    assert resp2.status_code == 404


# ---------------------------------------------------------------------------
# Org GET + PATCH + RBAC
# ---------------------------------------------------------------------------
def test_get_my_org_returns_only_callers_org(client, db_session):
    org_a, inv_a, _ = _bootstrap_org(client, "Org A", "a@x.example")
    _accept_invite(client, inv_a)

    # Fresh token via auth exchange — alt path
    from routes.portal import mint_portal_token
    owner = db.session.query(OrgMember).filter_by(org_id=org_a["id"]).first()
    token = mint_portal_token(owner.user_id, org_a["id"], "owner", [])

    resp = client.get("/portal/v1/orgs/me", headers=_hdr(token))
    assert resp.status_code == 200
    assert resp.get_json()["id"] == org_a["id"]


def test_viewer_cannot_patch_org(client, db_session):
    org, inv, _ = _bootstrap_org(client, "RBAC Co", "rb@x.example")
    _accept_invite(client, inv)
    # Add a viewer
    viewer = User(email="viewer@x.example", role="customer")
    db.session.add(viewer)
    db.session.commit()
    viewer_token = _mint_member_token(org["id"], viewer.id, "viewer")

    resp = client.patch(
        "/portal/v1/orgs/me",
        json={"name": "Renamed"},
        headers=_hdr(viewer_token),
    )
    assert resp.status_code == 403


def test_admin_can_patch_org(client, db_session):
    org, inv, _ = _bootstrap_org(client, "Admin Co", "ad@x.example")
    _accept_invite(client, inv)
    admin = User(email="admin@x.example", role="customer")
    db.session.add(admin)
    db.session.commit()
    admin_token = _mint_member_token(org["id"], admin.id, "admin")

    resp = client.patch(
        "/portal/v1/orgs/me",
        json={"name": "Admin Renamed"},
        headers=_hdr(admin_token),
    )
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "Admin Renamed"


# ---------------------------------------------------------------------------
# Tenant isolation — THE critical test per spec §13
# ---------------------------------------------------------------------------
def test_tenant_isolation_on_properties(client, db_session):
    """Org A creates a property; org B token must not see it."""
    org_a, inv_a, _ = _bootstrap_org(client, "Tenant A", "a@tenant.example")
    _accept_invite(client, inv_a)
    org_b, inv_b, _ = _bootstrap_org(client, "Tenant B", "b@tenant.example")
    _accept_invite(client, inv_b)

    # Mint tokens for each owner
    owner_a = (
        db.session.query(OrgMember).filter_by(org_id=org_a["id"]).first()
    )
    owner_b = (
        db.session.query(OrgMember).filter_by(org_id=org_b["id"]).first()
    )
    from routes.portal import mint_portal_token
    tok_a = mint_portal_token(owner_a.user_id, org_a["id"], "owner", [])
    tok_b = mint_portal_token(owner_b.user_id, org_b["id"], "owner", [])

    # A creates a property
    resp = client.post(
        "/portal/v1/properties",
        json={"name": "412 Biscayne", "zip": "33139", "unit_count": 12},
        headers=_hdr(tok_a),
    )
    assert resp.status_code == 201

    # A sees 1 property
    resp_a = client.get("/portal/v1/properties", headers=_hdr(tok_a))
    assert len(resp_a.get_json()["properties"]) == 1

    # B sees ZERO properties
    resp_b = client.get("/portal/v1/properties", headers=_hdr(tok_b))
    assert resp_b.get_json()["properties"] == []


def test_tenant_isolation_on_jobs(client, db_session):
    """Jobs stamped with org_id must not leak across orgs."""
    org_a, inv_a, _ = _bootstrap_org(client, "JobsA", "ja@x.example")
    _accept_invite(client, inv_a)
    org_b, inv_b, _ = _bootstrap_org(client, "JobsB", "jb@x.example")
    _accept_invite(client, inv_b)

    # Seed a Job for org A only
    owner_a = (
        db.session.query(OrgMember).filter_by(org_id=org_a["id"]).first()
    )
    job = Job(
        customer_id=owner_a.user_id,
        org_id=org_a["id"],
        status="pending",
        address="123 Test St, Miami FL",
    )
    db.session.add(job)
    db.session.commit()

    from routes.portal import mint_portal_token
    tok_a = mint_portal_token(owner_a.user_id, org_a["id"], "owner", [])
    owner_b = (
        db.session.query(OrgMember).filter_by(org_id=org_b["id"]).first()
    )
    tok_b = mint_portal_token(owner_b.user_id, org_b["id"], "owner", [])

    ra = client.get("/portal/v1/jobs", headers=_hdr(tok_a)).get_json()
    rb = client.get("/portal/v1/jobs", headers=_hdr(tok_b)).get_json()
    assert ra["total"] == 1
    assert rb["total"] == 0


# ---------------------------------------------------------------------------
# Member invite flow
# ---------------------------------------------------------------------------
def test_owner_can_invite_admin(client, db_session):
    org, inv, _ = _bootstrap_org(client, "Invite Co", "inv@x.example")
    _accept_invite(client, inv)
    owner = db.session.query(OrgMember).filter_by(org_id=org["id"]).first()
    from routes.portal import mint_portal_token
    tok = mint_portal_token(owner.user_id, org["id"], "owner", [])

    resp = client.post(
        "/portal/v1/orgs/me/members",
        json={"email": "teammate@x.example", "role": "admin"},
        headers=_hdr(tok),
    )
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    assert body["member"]["role"] == "admin"
    assert body["invite_url"].startswith("http")


def test_viewer_cannot_invite(client, db_session):
    org, inv, _ = _bootstrap_org(client, "Viewer Co", "v@x.example")
    _accept_invite(client, inv)
    viewer_user = User(email="viewer2@x.example", role="customer")
    db.session.add(viewer_user)
    db.session.commit()
    tok = _mint_member_token(org["id"], viewer_user.id, "viewer")

    resp = client.post(
        "/portal/v1/orgs/me/members",
        json={"email": "nope@x.example", "role": "admin"},
        headers=_hdr(tok),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
def test_dashboard_summary_shape(client, db_session):
    org, inv, _ = _bootstrap_org(client, "Dash Co", "d@x.example")
    _accept_invite(client, inv)
    owner = db.session.query(OrgMember).filter_by(org_id=org["id"]).first()
    from routes.portal import mint_portal_token
    tok = mint_portal_token(owner.user_id, org["id"], "owner", [])

    resp = client.get("/portal/v1/dashboard/summary", headers=_hdr(tok))
    assert resp.status_code == 200
    data = resp.get_json()
    assert "jobs_this_month" in data
    assert "open_invoices" in data
    assert "active_properties" in data
    assert "next_pickup" in data


# ---------------------------------------------------------------------------
# Unauthorized access
# ---------------------------------------------------------------------------
def test_no_token_returns_401(client, db_session):
    resp = client.get("/portal/v1/orgs/me")
    assert resp.status_code == 401


def test_garbage_token_returns_401(client, db_session):
    resp = client.get(
        "/portal/v1/orgs/me",
        headers={"Authorization": "Bearer not.a.real.token"},
    )
    assert resp.status_code == 401
