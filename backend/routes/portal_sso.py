"""
B2B Commercial Portal — SSO skeleton (Spec 04 §9.6).

Skeleton endpoints:

  * GET /portal/v1/auth/sso/google/start
  * GET /portal/v1/auth/sso/google/callback
  * GET /portal/v1/auth/sso/entra/start
  * GET /portal/v1/auth/sso/entra/callback

If the provider's env vars are missing, all four return **503** with a
clear message so the orchestrator / infra owner knows exactly which
secret is unset.

Required env:
  GOOGLE_OAUTH_CLIENT_ID
  GOOGLE_OAUTH_CLIENT_SECRET
  ENTRA_CLIENT_ID
  ENTRA_CLIENT_SECRET
  ENTRA_TENANT_ID
  PORTAL_SSO_REDIRECT_BASE   (e.g. https://portal.goumuve.com/api)

On successful callback the user is matched to an existing OrgMember by
email-domain match against `orgs.sso_domain`.  If no match, we return
the claim set but do not auto-create a membership — the portal UI can
present an "ask your admin" flow.

Authlib is the only new dep.  It's optional at import-time so the rest
of the portal still boots if authlib isn't installed yet.
"""

import logging
import os

from flask import Blueprint, g, jsonify, redirect, request, url_for

from models import db, Org, OrgMember, User
from routes.portal import mint_portal_token

logger = logging.getLogger(__name__)

# Authlib is optional; fail gracefully if missing.
try:
    from authlib.integrations.flask_client import OAuth  # type: ignore
    _AUTHLIB_OK = True
except Exception:  # pragma: no cover
    OAuth = None
    _AUTHLIB_OK = False

portal_sso_bp = Blueprint("portal_sso", __name__, url_prefix="/portal/v1")


# ---------------------------------------------------------------------------
# Provider config lookup — re-read each request so env changes land without
# a process restart (useful in dev).
# ---------------------------------------------------------------------------
def _provider_config(provider):
    if provider == "google":
        cid = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
        secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
        return {
            "client_id": cid,
            "client_secret": secret,
            "server_metadata_url": (
                "https://accounts.google.com/.well-known/openid-configuration"
            ),
            "scopes": "openid email profile",
        }
    if provider == "entra":
        cid = os.environ.get("ENTRA_CLIENT_ID", "")
        secret = os.environ.get("ENTRA_CLIENT_SECRET", "")
        tenant = os.environ.get("ENTRA_TENANT_ID", "")
        return {
            "client_id": cid,
            "client_secret": secret,
            "tenant_id": tenant,
            "server_metadata_url": (
                "https://login.microsoftonline.com/{}/v2.0/.well-known/"
                "openid-configuration".format(tenant or "common")
            ),
            "scopes": "openid email profile",
        }
    return None


def _provider_ready(cfg):
    if not cfg:
        return False
    if not (cfg.get("client_id") and cfg.get("client_secret")):
        return False
    if cfg.get("tenant_id") is not None and not cfg["tenant_id"]:
        return False
    return True


def _service_unavailable(provider, missing):
    return (
        jsonify(
            {
                "error": "sso_not_configured",
                "provider": provider,
                "missing_env": missing,
                "message": (
                    "Set {} in the environment and redeploy to enable {} SSO."
                ).format(", ".join(missing), provider),
            }
        ),
        503,
    )


def _missing_env(provider):
    if provider == "google":
        need = ["GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET"]
    elif provider == "entra":
        need = ["ENTRA_CLIENT_ID", "ENTRA_CLIENT_SECRET", "ENTRA_TENANT_ID"]
    else:
        return ["unknown_provider"]
    return [k for k in need if not os.environ.get(k)]


# ---------------------------------------------------------------------------
# OAuth registry — lazy so we don't crash on import when authlib isn't
# installed or env vars are missing.
# ---------------------------------------------------------------------------
_oauth = None


def _get_oauth():
    """Attach Authlib's OAuth helper to the current Flask app once."""
    global _oauth
    from flask import current_app

    if _oauth is not None:
        return _oauth
    if not _AUTHLIB_OK:
        return None
    _oauth = OAuth(current_app)
    return _oauth


def _register_provider(provider):
    oauth = _get_oauth()
    if oauth is None:
        return None
    cfg = _provider_config(provider)
    if not _provider_ready(cfg):
        return None
    # Authlib's register is idempotent-ish but guarded for re-registration.
    existing = oauth._clients.get(provider) if hasattr(oauth, "_clients") else None
    if existing is not None:
        return existing
    return oauth.register(
        name=provider,
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        server_metadata_url=cfg["server_metadata_url"],
        client_kwargs={"scope": cfg["scopes"]},
    )


# ---------------------------------------------------------------------------
# Shared post-login linker
# ---------------------------------------------------------------------------
def _upsert_identity(provider, subject, user_id, email):
    """Insert or refresh the (provider, subject) → user_id row.

    Written with raw SQL so we don't need a SqlAlchemy model for
    `sso_identities` — the table is tiny and only touched here + in the
    callback.  Idempotent: on conflict, bumps `last_seen_at` + `email`.
    """
    import datetime as _dt
    import uuid
    from sqlalchemy import text

    if not provider or not subject or not user_id:
        return
    now = _dt.datetime.utcnow()

    existing = db.session.execute(
        text(
            "SELECT id FROM sso_identities "
            "WHERE provider = :p AND subject = :s"
        ),
        {"p": provider, "s": subject},
    ).fetchone()

    if existing:
        db.session.execute(
            text(
                "UPDATE sso_identities "
                "SET user_id = :u, email = :e, last_seen_at = :n "
                "WHERE id = :id"
            ),
            {"u": user_id, "e": (email or "").lower() or None,
             "n": now, "id": existing[0]},
        )
    else:
        db.session.execute(
            text(
                "INSERT INTO sso_identities "
                "(id, provider, subject, user_id, email, "
                " created_at, last_seen_at) "
                "VALUES (:id, :p, :s, :u, :e, :c, :n)"
            ),
            {
                "id": str(uuid.uuid4()),
                "p": provider,
                "s": subject,
                "u": user_id,
                "e": (email or "").lower() or None,
                "c": now,
                "n": now,
            },
        )


def _lookup_identity(provider, subject):
    """Return (user_id, email) for (provider, subject) or None."""
    if not provider or not subject:
        return None
    from sqlalchemy import text
    row = db.session.execute(
        text(
            "SELECT user_id, email FROM sso_identities "
            "WHERE provider = :p AND subject = :s"
        ),
        {"p": provider, "s": subject},
    ).fetchone()
    if not row:
        return None
    return row[0], row[1]


def _finalize_member_login(user, org, provider, subject, email):
    """Mint JWT + record identity + update joined_at.  Returns the tuple
    returned by both callbacks."""
    import datetime as _dt

    member = (
        db.session.query(OrgMember)
        .filter_by(org_id=org.id, user_id=user.id)
        .first()
    )
    if not member:
        return None

    if member.joined_at is None:
        member.joined_at = _dt.datetime.utcnow()
        member.invite_token = None

    _upsert_identity(provider, subject, user.id, email)
    db.session.commit()

    token = mint_portal_token(
        user.id, org.id, member.role, member.scopes or [],
    )
    return token, org.id, user.id


def _link_member(provider, subject, email):
    """Link an SSO login to an OrgMember.

    Priority order:
      1. Identity-first: `(provider, subject)` hit in `sso_identities` →
         pick the unique OrgMember (first org_member row for that user).
         This survives email renames and shared-mailbox rebinding.
      2. Email-domain fallback: match `orgs.sso_domain` against the email
         domain and locate the user by email.  On success, upsert the
         identity so the next login short-circuits to path 1.

    Returns (portal_jwt, org_id, user_id) or None.  Never auto-creates
    memberships — that's still an admin action.
    """
    # Path 1 — identity-first
    ident = _lookup_identity(provider, subject)
    if ident is not None:
        user_id, _ident_email = ident
        user = db.session.get(User, user_id)
        if user is not None:
            # Pick any active org_member row. v1 supports a user in multiple
            # orgs — first row wins; UI can add an org-picker in v2 if that
            # becomes a real case.
            member = (
                db.session.query(OrgMember)
                .filter_by(user_id=user.id)
                .first()
            )
            if member is not None:
                org = db.session.get(Org, member.org_id)
                if org is not None:
                    result = _finalize_member_login(
                        user, org, provider, subject, email,
                    )
                    if result is not None:
                        return result
        # Fall through to email-domain if the identity is stale (user gone).

    # Path 2 — email-domain fallback
    if not email or "@" not in email:
        return None
    domain = email.split("@", 1)[1].lower()

    org = (
        db.session.query(Org)
        .filter(Org.sso_domain == domain)
        .first()
    )
    if not org:
        return None

    user = db.session.query(User).filter_by(email=email.lower()).first()
    if not user:
        user = User(email=email.lower(), role="customer")
        db.session.add(user)
        db.session.flush()

    return _finalize_member_login(user, org, provider, subject, email)


# Back-compat shim: older tests call _link_member_by_email with just the
# email. We keep the old name working so the v1 test suite doesn't break,
# but new code should call `_link_member(provider, subject, email)`.
def _link_member_by_email(email):
    return _link_member(provider=None, subject=None, email=email)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@portal_sso_bp.route("/auth/sso/google/start", methods=["GET"])
def google_start():
    missing = _missing_env("google")
    if missing:
        return _service_unavailable("google", missing)
    if not _AUTHLIB_OK:
        return _service_unavailable("google", ["authlib-not-installed"])

    client = _register_provider("google")
    if client is None:
        return _service_unavailable("google", ["authlib-registration-failed"])
    redirect_uri = _callback_uri("google")
    return client.authorize_redirect(redirect_uri)


@portal_sso_bp.route("/auth/sso/google/callback", methods=["GET"])
def google_callback():
    missing = _missing_env("google")
    if missing:
        return _service_unavailable("google", missing)
    if not _AUTHLIB_OK:
        return _service_unavailable("google", ["authlib-not-installed"])

    client = _register_provider("google")
    if client is None:
        return _service_unavailable("google", ["authlib-registration-failed"])

    try:
        token = client.authorize_access_token()
        userinfo = token.get("userinfo") or client.userinfo(token=token)
    except Exception as exc:  # pragma: no cover
        logger.warning("google sso callback failed: %s", exc)
        return jsonify({"error": "sso_callback_failed"}), 400

    email = (userinfo or {}).get("email")
    subject = (userinfo or {}).get("sub")
    result = _link_member("google", subject, email)
    if result is None:
        return jsonify(
            {
                "error": "no_membership",
                "email": email,
                "message": "No org membership found for this SSO identity.",
            }
        ), 403

    jwt_token, org_id, user_id = result
    return jsonify(
        {"token": jwt_token, "org_id": org_id, "user_id": user_id}
    )


@portal_sso_bp.route("/auth/sso/entra/start", methods=["GET"])
def entra_start():
    missing = _missing_env("entra")
    if missing:
        return _service_unavailable("entra", missing)
    if not _AUTHLIB_OK:
        return _service_unavailable("entra", ["authlib-not-installed"])

    client = _register_provider("entra")
    if client is None:
        return _service_unavailable("entra", ["authlib-registration-failed"])
    redirect_uri = _callback_uri("entra")
    return client.authorize_redirect(redirect_uri)


@portal_sso_bp.route("/auth/sso/entra/callback", methods=["GET"])
def entra_callback():
    missing = _missing_env("entra")
    if missing:
        return _service_unavailable("entra", missing)
    if not _AUTHLIB_OK:
        return _service_unavailable("entra", ["authlib-not-installed"])

    client = _register_provider("entra")
    if client is None:
        return _service_unavailable("entra", ["authlib-registration-failed"])

    try:
        token = client.authorize_access_token()
        userinfo = token.get("userinfo") or {}
    except Exception as exc:  # pragma: no cover
        logger.warning("entra sso callback failed: %s", exc)
        return jsonify({"error": "sso_callback_failed"}), 400

    email = (userinfo or {}).get("email") or (userinfo or {}).get("preferred_username")
    # Entra OIDC uses `oid` (stable per-tenant user id) as the canonical
    # subject; `sub` is only stable per (app, user) pair. Prefer `oid`.
    subject = (
        (userinfo or {}).get("oid")
        or (userinfo or {}).get("sub")
    )
    result = _link_member("entra", subject, email)
    if result is None:
        return jsonify(
            {
                "error": "no_membership",
                "email": email,
                "message": "No org membership found for this SSO identity.",
            }
        ), 403

    jwt_token, org_id, user_id = result
    return jsonify(
        {"token": jwt_token, "org_id": org_id, "user_id": user_id}
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _callback_uri(provider):
    base = os.environ.get("PORTAL_SSO_REDIRECT_BASE")
    if base:
        return "{}/portal/v1/auth/sso/{}/callback".format(
            base.rstrip("/"), provider
        )
    # Fall back to url_for in the request context.
    return url_for(
        "portal_sso.{}_callback".format(provider), _external=True
    )
