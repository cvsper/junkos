"""
B2B Commercial Portal API (Spec 04) — /portal/v1/*

Multi-tenant endpoints backing portal.goumuve.com. Every request is
tenant-scoped through a portal JWT that embeds {user_id, org_id, role,
scopes[]}. The middleware stack per endpoint is:

    portal_auth  ->  rbac_check(role | scope)  ->  view  ->  audit_log

On Postgres, Row-Level Security (migrate.py) provides a second barrier by
binding `app.current_org_id` to the session. On SQLite the app-layer
tenant_guard is the sole enforcer.

Endpoints shipped in 72h-MVP scope (spec §10):
  * POST   /orgs                       (sales service-token bootstrap)
  * GET    /orgs/me
  * PATCH  /orgs/me
  * GET    /orgs/me/members
  * POST   /orgs/me/members            (magic-link invite)
  * POST   /orgs/me/members/accept     (redeem invite token)
  * DELETE /orgs/me/members/<id>
  * GET    /properties
  * POST   /properties
  * GET    /jobs                        (proxy to residential jobs filtered by org_id)
  * GET    /billing/subscription
  * GET    /billing/invoices
  * GET    /auth/token                  (exchange user JWT -> portal JWT)

Stripe wiring lives in billing_portal.py.
"""

import datetime as _dt
import hashlib
import hmac
import logging
import os
import secrets
from functools import wraps

import jwt
from flask import Blueprint, jsonify, request, g
from sqlalchemy import and_, or_, text

from models import (
    db,
    User,
    Job,
    Org,
    OrgMember,
    PortalProperty,
    PortalInvoice,
    PortalAuditLog,
)

logger = logging.getLogger(__name__)

portal_bp = Blueprint("portal", __name__, url_prefix="/portal/v1")


# ---------------------------------------------------------------------------
# JWT — portal tokens carry org/role claims so RBAC is a header check,
# not a per-request DB roundtrip. Signed with JWT_SECRET shared w/ auth.
# ---------------------------------------------------------------------------
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-fallback-do-not-use")
PORTAL_TOKEN_TTL_DAYS = 7
INVITE_TTL_DAYS = 14

# Sales-only bootstrap endpoint: called by ops CLI / internal tooling,
# never from the portal UI.
SALES_SERVICE_TOKEN = os.environ.get("PORTAL_SALES_SERVICE_TOKEN", "")


def mint_portal_token(user_id, org_id, role, scopes=None):
    """Return a short-lived JWT carrying the tenant claim set."""
    payload = {
        "user_id": user_id,
        "org_id": org_id,
        "role": role,
        "scopes": list(scopes or []),
        "exp": _dt.datetime.utcnow() + _dt.timedelta(days=PORTAL_TOKEN_TTL_DAYS),
        "iat": _dt.datetime.utcnow(),
        "typ": "portal",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _decode_portal_token(token):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    if payload.get("typ") != "portal":
        return None
    return payload


# ---------------------------------------------------------------------------
# Middleware: portal_auth + RBAC
# ---------------------------------------------------------------------------
def portal_auth(f):
    """Require a valid portal JWT. Populates flask.g.{user_id,org_id,role,
    scopes} and binds Postgres RLS via SET LOCAL."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        raw = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not raw:
            return jsonify({"error": "unauthorized"}), 401
        claims = _decode_portal_token(raw)
        if not claims:
            return jsonify({"error": "unauthorized"}), 401

        g.user_id = claims["user_id"]
        g.org_id = claims["org_id"]
        g.role = claims["role"]
        g.scopes = claims.get("scopes", [])

        # Defense-in-depth: bind org_id into PG session so RLS policy fires.
        # SQLite ignores this; no-op via text() + error swallow.
        try:
            if db.engine.dialect.name == "postgresql":
                db.session.execute(
                    text("SET LOCAL app.current_org_id = :oid"),
                    {"oid": g.org_id},
                )
        except Exception as exc:  # pragma: no cover
            logger.warning("RLS binding failed: %s", exc)

        return f(*args, **kwargs)

    return wrapper


def require_role(*allowed):
    """Gate an endpoint to a set of roles (owner|admin|operator|viewer)."""
    allowed_set = set(allowed)

    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if getattr(g, "role", None) not in allowed_set:
                return jsonify({"error": "forbidden"}), 403
            return f(*args, **kwargs)
        return wrapper

    return deco


def audit(action, object_type=None, object_id=None, before=None, after=None):
    """Append-only audit entry. Cheap; never raises into the request."""
    try:
        entry = PortalAuditLog(
            org_id=getattr(g, "org_id", None),
            user_id=getattr(g, "user_id", None),
            action=action,
            object_type=object_type,
            object_id=object_id,
            before=before,
            after=after,
            ip=request.headers.get("X-Forwarded-For", request.remote_addr),
            user_agent=(request.headers.get("User-Agent") or "")[:240],
        )
        db.session.add(entry)
        db.session.commit()
    except Exception as exc:  # pragma: no cover
        logger.warning("audit log failed for %s: %s", action, exc)
        db.session.rollback()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _slugify(name):
    base = "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")
    return base[:50] or secrets.token_hex(4)


def _unique_slug(base):
    slug = base
    n = 1
    while db.session.query(Org).filter_by(slug=slug).first() is not None:
        n += 1
        slug = "{}-{}".format(base, n)
    return slug


def _member_or_403(user_id, org_id):
    """Return OrgMember row or None. View should 403 on None."""
    return (
        db.session.query(OrgMember)
        .filter_by(user_id=user_id, org_id=org_id)
        .first()
    )


# ---------------------------------------------------------------------------
# Token exchange: user JWT (from app login) -> portal JWT for a given org
# ---------------------------------------------------------------------------
@portal_bp.route("/auth/token", methods=["POST"])
def auth_exchange_token():
    """Exchange a residential user JWT for a portal JWT scoped to an org.

    Body: {"user_token": "<user jwt>", "org_id": "..."}. Confirms the user
    has an OrgMember row in the requested org and returns a portal token
    baking {org_id, role, scopes} in.
    """
    data = request.get_json(silent=True) or {}
    user_token = data.get("user_token", "")
    org_id = data.get("org_id", "")
    if not user_token or not org_id:
        return jsonify({"error": "user_token and org_id required"}), 400

    try:
        claims = jwt.decode(user_token, JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return jsonify({"error": "invalid user_token"}), 401

    user_id = claims.get("user_id")
    if not user_id:
        return jsonify({"error": "invalid user_token"}), 401

    member = _member_or_403(user_id, org_id)
    if not member or member.joined_at is None:
        return jsonify({"error": "not a member of this org"}), 403

    token = mint_portal_token(user_id, org_id, member.role, member.scopes or [])
    return jsonify(
        {
            "token": token,
            "org_id": org_id,
            "role": member.role,
            "scopes": member.scopes or [],
            "expires_in": PORTAL_TOKEN_TTL_DAYS * 86400,
        }
    )


# ---------------------------------------------------------------------------
# Self-serve B2B auth — the human front doors. No JWT-pasting, no service
# token: a business owner signs up or logs in with email + password and the
# org is resolved automatically. Both return a portal JWT (same shape as the
# token-exchange path) so the rest of the app is unchanged.
# ---------------------------------------------------------------------------
try:  # rate-limit if the app's limiter is wired; no-op fallback otherwise
    from extensions import limiter as _limiter

    def _rl(spec):
        return _limiter.limit(spec)
except Exception:  # pragma: no cover - limiter optional in some contexts

    def _rl(_spec):
        def _wrap(f):
            return f

        return _wrap


def _norm_email(v):
    return (v or "").strip().lower()


def _valid_email(email):
    return "@" in email and "." in email.split("@")[-1]


@portal_bp.route("/auth/register", methods=["POST"])
@_rl("5 per minute")
def auth_register():
    """Self-serve business signup.

    Creates the User (or claims a sales-provisioned one that has no password
    yet), the Org, and an owner membership, then returns a portal JWT — the
    store is signed in immediately.

    Body: {business_name, email, password, contact_name?, phone?}
    """
    data = request.get_json(silent=True) or {}
    business = (data.get("business_name") or data.get("name") or "").strip()
    email = _norm_email(data.get("email"))
    password = data.get("password") or ""
    contact_name = (
        data.get("contact_name") or data.get("owner_name") or ""
    ).strip() or None
    phone = (data.get("phone") or "").strip() or None

    if not business or not email or not password:
        return jsonify(
            {"error": "Business name, email and password are required."}
        ), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400
    if not _valid_email(email):
        return jsonify({"error": "Enter a valid email address."}), 400

    user = db.session.query(User).filter_by(email=email).first()
    if user and user.password_hash:
        return jsonify(
            {
                "error": "That email already has an account. Sign in instead.",
                "code": "email_exists",
            }
        ), 409

    if user is None:
        user = User(email=email, name=contact_name, phone=phone, role="customer")
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
    else:
        # Sales-provisioned user with no password yet — let them claim it.
        user.set_password(password)
        if contact_name and not user.name:
            user.name = contact_name

    org = Org(
        name=business,
        slug=_unique_slug(_slugify(business)),
        billing_email=email,
        tier="starter",
        status="trial",
        net_terms_days=0,
    )
    db.session.add(org)
    db.session.flush()

    member = OrgMember(
        org_id=org.id,
        user_id=user.id,
        role="owner",
        scopes=["*"],
        joined_at=_dt.datetime.utcnow(),
    )
    db.session.add(member)
    db.session.commit()

    token = mint_portal_token(user.id, org.id, "owner", ["*"])
    return jsonify(
        {
            "token": token,
            "org_id": org.id,
            "role": "owner",
            "scopes": ["*"],
            "org": org.to_dict(),
            "expires_in": PORTAL_TOKEN_TTL_DAYS * 86400,
        }
    ), 201


@portal_bp.route("/auth/login", methods=["POST"])
@_rl("10 per minute")
def auth_login():
    """Email + password login that resolves the user's org automatically.

    Body: {email, password, org_id?}
      - bad creds -> 401
      - 0 orgs    -> 403 {code: "no_org"}
      - 1 org     -> portal JWT
      - >1 orgs   -> 200 {needs_org: true, orgs: [...]} unless org_id is given
    """
    data = request.get_json(silent=True) or {}
    email = _norm_email(data.get("email"))
    password = data.get("password") or ""
    org_id = (data.get("org_id") or "").strip() or None

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    user = db.session.query(User).filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid email or password."}), 401

    memberships = (
        db.session.query(OrgMember, Org)
        .join(Org, Org.id == OrgMember.org_id)
        .filter(OrgMember.user_id == user.id, OrgMember.joined_at.isnot(None))
        .all()
    )
    if not memberships:
        return jsonify(
            {
                "error": "No business account is linked to this email yet.",
                "code": "no_org",
            }
        ), 403

    chosen = None
    if org_id:
        chosen = next((row for row in memberships if row[0].org_id == org_id), None)
        if chosen is None:
            return jsonify({"error": "You don't have access to that business."}), 403
    elif len(memberships) == 1:
        chosen = memberships[0]
    else:
        return jsonify(
            {
                "needs_org": True,
                "orgs": [
                    {"org_id": m.org_id, "name": o.name, "role": m.role}
                    for m, o in memberships
                ],
            }
        )

    member, org = chosen
    token = mint_portal_token(user.id, org.id, member.role, member.scopes or [])
    return jsonify(
        {
            "token": token,
            "org_id": org.id,
            "role": member.role,
            "scopes": member.scopes or [],
            "org": org.to_dict(),
            "expires_in": PORTAL_TOKEN_TTL_DAYS * 86400,
        }
    )


# ---------------------------------------------------------------------------
# Sales-service bootstrap: POST /orgs
# ---------------------------------------------------------------------------
@portal_bp.route("/orgs", methods=["POST"])
def create_org():
    """Provision a new org + initial owner. Auth is a service token, not a
    portal JWT — this is how sales onboards a customer before they log in.
    """
    if not SALES_SERVICE_TOKEN:
        return jsonify({"error": "sales service token not configured"}), 503

    provided = request.headers.get("X-Service-Token", "")
    if not hmac.compare_digest(provided, SALES_SERVICE_TOKEN):
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    required = ("name", "billing_email", "owner_email")
    missing = [k for k in required if not data.get(k)]
    if missing:
        return jsonify({"error": "missing: {}".format(missing)}), 400

    name = data["name"].strip()
    billing_email = data["billing_email"].strip().lower()
    owner_email = data["owner_email"].strip().lower()
    tier = data.get("tier", "starter")
    if tier not in {"starter", "pro", "enterprise"}:
        return jsonify({"error": "invalid tier"}), 400

    slug = _unique_slug(_slugify(data.get("slug") or name))

    org = Org(
        name=name,
        slug=slug,
        billing_email=billing_email,
        tier=tier,
        net_terms_days=30 if tier == "enterprise" else 0,
        status="trial",
    )
    db.session.add(org)
    db.session.flush()

    # Find-or-create the owner user.
    owner = db.session.query(User).filter_by(email=owner_email).first()
    if owner is None:
        owner = User(email=owner_email, name=data.get("owner_name"), role="customer")
        db.session.add(owner)
        db.session.flush()

    invite_token = secrets.token_urlsafe(32)
    member = OrgMember(
        org_id=org.id,
        user_id=owner.id,
        role="owner",
        scopes=["*"],
        invite_token=invite_token,
    )
    db.session.add(member)
    db.session.commit()

    return jsonify(
        {
            "org": org.to_dict(),
            "owner_user_id": owner.id,
            "owner_email": owner_email,
            "invite_token": invite_token,
            "invite_url": "{}/invite?token={}".format(
                os.environ.get("PORTAL_URL", "https://portal.goumuve.com"),
                invite_token,
            ),
        }
    ), 201


# ---------------------------------------------------------------------------
# Invite redemption — turns invite_token into an active membership + token
# ---------------------------------------------------------------------------
@portal_bp.route("/orgs/invite/accept", methods=["POST"])
def accept_invite():
    """Redeem an invite_token. The user must already exist OR provide a
    password to create one. Returns a portal JWT on success."""
    data = request.get_json(silent=True) or {}
    token_str = data.get("invite_token", "")
    if not token_str:
        return jsonify({"error": "invite_token required"}), 400

    member = (
        db.session.query(OrgMember).filter_by(invite_token=token_str).first()
    )
    if not member:
        return jsonify({"error": "invalid invite"}), 404
    if member.joined_at is not None:
        return jsonify({"error": "invite already redeemed"}), 409
    if member.invited_at and (
        _dt.datetime.utcnow() - member.invited_at
    ) > _dt.timedelta(days=INVITE_TTL_DAYS):
        return jsonify({"error": "invite expired"}), 410

    password = data.get("password")
    user = db.session.get(User, member.user_id)
    if user and password:
        user.set_password(password)

    member.joined_at = _dt.datetime.utcnow()
    member.invite_token = None
    db.session.commit()

    token = mint_portal_token(
        member.user_id, member.org_id, member.role, member.scopes or []
    )
    return jsonify(
        {
            "token": token,
            "org_id": member.org_id,
            "role": member.role,
            "user_id": member.user_id,
        }
    )


# ---------------------------------------------------------------------------
# Org: GET/PATCH /orgs/me
# ---------------------------------------------------------------------------
@portal_bp.route("/orgs/me", methods=["GET"])
@portal_auth
def get_my_org():
    org = db.session.get(Org, g.org_id)
    if not org:
        return jsonify({"error": "not_found"}), 404
    return jsonify(org.to_dict())


@portal_bp.route("/orgs/me", methods=["PATCH"])
@portal_auth
@require_role("owner", "admin")
def patch_my_org():
    org = db.session.get(Org, g.org_id)
    if not org:
        return jsonify({"error": "not_found"}), 404
    data = request.get_json(silent=True) or {}
    before = org.to_dict()

    for field in ("name", "tax_id", "billing_email", "billing_address",
                  "sso_provider", "sso_domain", "auto_pay"):
        if field in data:
            setattr(org, field, data[field])

    db.session.commit()
    audit("org.update", "org", org.id, before, org.to_dict())
    return jsonify(org.to_dict())


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------
@portal_bp.route("/orgs/me/members", methods=["GET"])
@portal_auth
def list_members():
    members = (
        db.session.query(OrgMember, User)
        .join(User, User.id == OrgMember.user_id)
        .filter(OrgMember.org_id == g.org_id)
        .all()
    )
    return jsonify(
        {
            "members": [
                {
                    **m.to_dict(),
                    "email": u.email,
                    "name": u.name,
                    "pending": m.joined_at is None,
                }
                for m, u in members
            ]
        }
    )


@portal_bp.route("/orgs/me/members", methods=["POST"])
@portal_auth
@require_role("owner", "admin")
def invite_member():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    role = data.get("role", "viewer")
    if not email:
        return jsonify({"error": "email required"}), 400
    if role not in {"owner", "admin", "operator", "viewer"}:
        return jsonify({"error": "invalid role"}), 400
    # Only owners can mint more owners.
    if role == "owner" and g.role != "owner":
        return jsonify({"error": "only owner can invite owner"}), 403

    # Find or create the user.
    user = db.session.query(User).filter_by(email=email).first()
    if user is None:
        user = User(email=email, role="customer")
        db.session.add(user)
        db.session.flush()

    existing = _member_or_403(user.id, g.org_id)
    if existing:
        return jsonify({"error": "already a member"}), 409

    invite_token = secrets.token_urlsafe(32)
    member = OrgMember(
        org_id=g.org_id,
        user_id=user.id,
        role=role,
        scopes=data.get("scopes") or [],
        invited_by=g.user_id,
        invite_token=invite_token,
    )
    db.session.add(member)
    db.session.commit()
    audit("member.invite", "org_member", member.id, None, member.to_dict())

    return jsonify(
        {
            "member": member.to_dict(),
            "email": email,
            "invite_url": "{}/invite?token={}".format(
                os.environ.get("PORTAL_URL", "https://portal.goumuve.com"),
                invite_token,
            ),
        }
    ), 201


@portal_bp.route("/orgs/me/members/<member_id>", methods=["DELETE"])
@portal_auth
@require_role("owner", "admin")
def remove_member(member_id):
    m = db.session.get(OrgMember, member_id)
    if not m or m.org_id != g.org_id:
        return jsonify({"error": "not_found"}), 404
    if m.role == "owner" and g.role != "owner":
        return jsonify({"error": "only owner can remove owner"}), 403
    before = m.to_dict()
    db.session.delete(m)
    db.session.commit()
    audit("member.remove", "org_member", member_id, before, None)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Properties (minimal CRUD for MVP; full spec §6 comes in v1)
# ---------------------------------------------------------------------------
@portal_bp.route("/properties", methods=["GET"])
@portal_auth
def list_properties():
    rows = (
        db.session.query(PortalProperty)
        .filter_by(org_id=g.org_id)
        .order_by(PortalProperty.created_at.desc())
        .all()
    )
    return jsonify({"properties": [p.to_dict() for p in rows]})


@portal_bp.route("/properties", methods=["POST"])
@portal_auth
@require_role("owner", "admin", "operator")
def create_property():
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name required"}), 400
    p = PortalProperty(
        org_id=g.org_id,
        name=data["name"],
        address_line1=data.get("address_line1"),
        address_line2=data.get("address_line2"),
        city=data.get("city"),
        state=data.get("state"),
        zip=data.get("zip"),
        lat=data.get("lat"),
        lng=data.get("lng"),
        unit_count=data.get("unit_count") or 1,
        source=data.get("source") or "manual",
        external_ref=data.get("external_ref"),
    )
    db.session.add(p)
    db.session.commit()
    audit("property.create", "portal_property", p.id, None, p.to_dict())
    return jsonify(p.to_dict()), 201


# ---------------------------------------------------------------------------
# Jobs: proxy to residential Job table scoped by org_id
# ---------------------------------------------------------------------------
@portal_bp.route("/jobs", methods=["GET"])
@portal_auth
def list_jobs():
    status = request.args.get("status")
    q = db.session.query(Job).filter(Job.org_id == g.org_id)
    if status:
        q = q.filter(Job.status == status)
    q = q.order_by(Job.created_at.desc()).limit(
        min(int(request.args.get("limit", 50)), 200)
    )
    rows = q.all()
    return jsonify({"jobs": [j.to_dict() for j in rows], "total": len(rows)})


# ---------------------------------------------------------------------------
# Billing (read-only for MVP; Stripe writes live in billing_portal.py)
# ---------------------------------------------------------------------------
@portal_bp.route("/billing/subscription", methods=["GET"])
@portal_auth
def get_subscription():
    org = db.session.get(Org, g.org_id)
    return jsonify(
        {
            "tier": org.tier,
            "status": org.status,
            "auto_pay": org.auto_pay,
            "net_terms_days": org.net_terms_days,
            "stripe_customer_id": org.stripe_customer_id,
            "stripe_subscription_id": org.stripe_subscription_id,
        }
    )


# Self-serve: start a Stripe Checkout to subscribe + collect a card. The
# checkout.session.completed webhook (billing_portal.py) activates the org.
@portal_bp.route("/billing/checkout", methods=["POST"])
@portal_auth
@require_role("owner", "admin")
def billing_checkout():
    org = db.session.get(Org, g.org_id)
    if not org:
        return jsonify({"error": "not_found"}), 404
    data = request.get_json(silent=True) or {}
    tier = data.get("tier") or org.tier or "starter"
    base = os.environ.get("PORTAL_URL", "https://portal.goumuve.com")
    success_url = data.get("successUrl") or "{}/settings?billing=success".format(base)
    cancel_url = data.get("cancelUrl") or "{}/settings?billing=cancel".format(base)
    try:
        from billing_portal import create_checkout_session
        url = create_checkout_session(org, tier, success_url, cancel_url)
        audit("billing.checkout_started", "org", org.id, after={"tier": tier})
        return jsonify({"url": url}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 502


# Self-serve: Stripe Customer Portal link to manage card/subscription/invoices.
@portal_bp.route("/billing/portal-session", methods=["POST"])
@portal_auth
@require_role("owner", "admin")
def billing_portal_session():
    org = db.session.get(Org, g.org_id)
    if not org:
        return jsonify({"error": "not_found"}), 404
    base = os.environ.get("PORTAL_URL", "https://portal.goumuve.com")
    return_url = (request.get_json(silent=True) or {}).get("returnUrl") or "{}/settings".format(base)
    try:
        from billing_portal import create_billing_portal_session
        url = create_billing_portal_session(org, return_url)
        return jsonify({"url": url}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@portal_bp.route("/billing/invoices", methods=["GET"])
@portal_auth
def list_invoices():
    status = request.args.get("status")
    q = db.session.query(PortalInvoice).filter_by(org_id=g.org_id)
    if status:
        q = q.filter_by(status=status)
    q = q.order_by(PortalInvoice.period_start.desc()).limit(100)
    rows = q.all()
    return jsonify({"invoices": [i.to_dict() for i in rows]})


@portal_bp.route("/billing/invoices/<invoice_id>", methods=["GET"])
@portal_auth
def get_invoice(invoice_id):
    inv = db.session.get(PortalInvoice, invoice_id)
    if not inv or inv.org_id != g.org_id:
        return jsonify({"error": "not_found"}), 404
    return jsonify(inv.to_dict(include_lines=True))


# ---------------------------------------------------------------------------
# Dashboard summary — one call from the Next.js app on load
# ---------------------------------------------------------------------------
@portal_bp.route("/dashboard/summary", methods=["GET"])
@portal_auth
def dashboard_summary():
    now = _dt.datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    jobs_this_month = (
        db.session.query(Job)
        .filter(Job.org_id == g.org_id, Job.created_at >= month_start)
        .count()
    )
    open_invoices = (
        db.session.query(PortalInvoice)
        .filter(
            PortalInvoice.org_id == g.org_id,
            PortalInvoice.status.in_(("open", "past_due")),
        )
        .count()
    )
    prop_count = (
        db.session.query(PortalProperty)
        .filter_by(org_id=g.org_id, active=True)
        .count()
    )

    next_pickup = (
        db.session.query(Job)
        .filter(
            Job.org_id == g.org_id,
            Job.scheduled_at != None,  # noqa: E711
            Job.status.in_(("pending", "scheduled", "assigned")),
        )
        .order_by(Job.scheduled_at.asc())
        .first()
    )

    return jsonify(
        {
            "jobs_this_month": jobs_this_month,
            "open_invoices": open_invoices,
            "active_properties": prop_count,
            "next_pickup": next_pickup.to_dict() if next_pickup else None,
        }
    )


# ---------------------------------------------------------------------------
# Error handlers — keep JSON shape consistent
# ---------------------------------------------------------------------------
@portal_bp.errorhandler(404)
def _404(e):
    return jsonify({"error": "not_found"}), 404


@portal_bp.errorhandler(405)
def _405(e):
    return jsonify({"error": "method_not_allowed"}), 405
