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
def _link_member_by_email(email):
    """Find an OrgMember whose org's sso_domain matches the email domain.

    Returns (portal_jwt, org_id, user_id) on success, or None.  We never
    auto-create memberships in the MVP — that's an admin action.
    """
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
        # Provision a shell user so the OrgMember row stays valid.  This
        # matches existing invite-acceptance behavior in routes/portal.py.
        user = User(email=email.lower(), role="customer")
        db.session.add(user)
        db.session.flush()

    member = (
        db.session.query(OrgMember)
        .filter_by(org_id=org.id, user_id=user.id)
        .first()
    )
    if not member:
        return None

    # Mark joined_at if this is the first successful SSO login.
    import datetime as _dt
    if member.joined_at is None:
        member.joined_at = _dt.datetime.utcnow()
        member.invite_token = None
        db.session.commit()

    token = mint_portal_token(user.id, org.id, member.role, member.scopes or [])
    return token, org.id, user.id


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
    result = _link_member_by_email(email)
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
    result = _link_member_by_email(email)
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
