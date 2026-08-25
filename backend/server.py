# IMPORTANT: eventlet monkey-patching must happen BEFORE any other imports
# (especially Flask/werkzeug/pydantic). gunicorn loads server:app with the
# `eventlet` worker class, and if patching runs after those modules are
# imported it fails with "Working outside of request context" and
# "Pydantic models should inherit from BaseModel" as eventlet traverses
# already-bound proxy objects. Doing it here, first, makes the worker boot.
import eventlet
eventlet.monkey_patch()

from flask import Flask, request, jsonify, url_for
from flask_cors import CORS
from functools import wraps
from datetime import datetime, timedelta
import hmac
import os
import logging

from sanitize import sanitize_dict
from extensions import limiter

from app_config import Config
from database import Database
from auth_routes import auth_bp, require_auth
from models import db as sqlalchemy_db
from socket_events import socketio
from routes import drivers_bp, pricing_bp, ratings_bp, admin_bp, payments_bp, webhook_bp, booking_bp, upload_bp, jobs_bp, offers_bp, tracking_bp, driver_bp, operator_bp, push_bp, service_area_bp, recurring_bp, referrals_bp, support_bp, chat_bp, onboarding_bp, promos_bp, reviews_bp, operator_applications_bp, migration_bp, vapi_bp, sms_webhook_bp, campaigns_bp

# ---------------------------------------------------------------------------
# Sentry error monitoring (optional -- only active when SENTRY_DSN is set)
# ---------------------------------------------------------------------------
_sentry_dsn = os.environ.get("SENTRY_DSN")
if _sentry_dsn:
    import sentry_sdk
    import re as _re
    from sentry_sdk.integrations.flask import FlaskIntegration

    # Secret-gated admin endpoints take the secret as a URL PATH segment, and
    # Sentry logs full URLs -- so the secret leaks into stored events + alert
    # emails. Redact the secret segment before any event is sent.
    _SECRET_URL_RE = _re.compile(
        r"(/api/(?:admin/(?:provision-hauler|capi-status|backfill-approval-emails|test-alert|seed-demo-driver)|run-migrate))/[^/?#]+"
    )

    def _scrub_secret_urls(event, hint):
        try:
            req = event.get("request")
            if isinstance(req, dict) and isinstance(req.get("url"), str):
                req["url"] = _SECRET_URL_RE.sub(r"\1/[redacted]", req["url"])
            tags = event.get("tags")
            if isinstance(tags, dict) and isinstance(tags.get("url"), str):
                tags["url"] = _SECRET_URL_RE.sub(r"\1/[redacted]", tags["url"])
        except Exception:
            pass
        return event

    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[FlaskIntegration()],
        traces_sample_rate=0.1,
        before_send=_scrub_secret_urls,
    )

# ---------------------------------------------------------------------------
# Production startup checks
# ---------------------------------------------------------------------------
_startup_logger = logging.getLogger("umuve.startup")

_CRITICAL_ENV_VARS = [
    "JWT_SECRET",
    "SECRET_KEY",
    "DATABASE_URL",
]

_RECOMMENDED_ENV_VARS = [
    "ADMIN_SEED_SECRET",
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "CORS_ORIGINS",
]

# Development is an EXPLICIT opt-in (FLASK_ENV=development or dev). An unset
# FLASK_ENV means production-safe defaults: startup checks run, CORS uses the
# allow-list (never wildcard), HSTS is sent, and Flask debug stays off.
_flask_env = (os.environ.get("FLASK_ENV") or "").strip().lower()
_is_development = _flask_env in ("development", "dev")
if not _is_development:
    _missing_critical = [v for v in _CRITICAL_ENV_VARS if not os.environ.get(v)]
    _missing_recommended = [v for v in _RECOMMENDED_ENV_VARS if not os.environ.get(v)]

    if _missing_critical:
        _startup_logger.critical(
            "MISSING CRITICAL ENV VARS (app may not work correctly): %s",
            ", ".join(_missing_critical),
        )
    if _missing_recommended:
        _startup_logger.warning(
            "Missing recommended env vars: %s",
            ", ".join(_missing_recommended),
        )
    if not _sentry_dsn:
        _startup_logger.warning(
            "SENTRY_DSN is not set -- error monitoring is disabled."
        )

app = Flask(__name__)
app.config.from_object(Config)

# ---------------------------------------------------------------------------
# SQLAlchemy configuration
# ---------------------------------------------------------------------------
database_url = os.environ.get("DATABASE_URL", "")
if database_url:
    # Fix postgres:// to postgresql:// for SQLAlchemy 2.x
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url

    # Connection-pool hardening for Render Postgres.
    # Render closes idle DB connections (~5 min) and spins web services down
    # when idle; without pre-ping, SQLAlchemy hands out a dead pooled
    # connection on the next request and the query dies with
    # "SSL SYSCALL error: EOF detected". pool_pre_ping issues a cheap
    # liveness check (and transparently reconnects) before every checkout;
    # pool_recycle proactively retires connections before Render's idle
    # cutoff. This fixes intermittent 500s app-wide, not just one endpoint.
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "pool_size": 5,
        "max_overflow": 5,
        "pool_timeout": 30,
    }
else:
    # Fallback to SQLite for local development
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///umuve.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max request body

# ---------------------------------------------------------------------------
# CORS configuration
# ---------------------------------------------------------------------------
# _is_development is defined once above (explicit opt-in via FLASK_ENV);
# unset FLASK_ENV ⇒ production-safe: allow-list CORS, HSTS on, debug off.

_DEFAULT_ORIGINS = [
    "https://platform-olive-nu.vercel.app",
    "https://landing-page-premium-five.vercel.app",
    "https://umuve-backend.onrender.com",
    "https://goumuve.com",
    "https://www.goumuve.com",
    "https://app.goumuve.com",
    "https://portal.goumuve.com",
]

_cors_env = os.environ.get("CORS_ORIGINS", "")
if _cors_env:
    # Honour explicit env-var override (comma-separated list)
    _allowed_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
    # Block wildcard CORS in production -- it must be an explicit list
    if not _is_development and "*" in _allowed_origins:
        _startup_logger.critical(
            "CORS_ORIGINS is set to '*' in a non-development environment! "
            "Falling back to the default allow-list for safety."
        )
        _allowed_origins = list(_DEFAULT_ORIGINS)
    else:
        # Always include our own first-party origins so a missing entry in the
        # env var can't silently break our apps (this is exactly what blocked
        # portal.goumuve.com from talking to the API). De-duped, order kept.
        _allowed_origins = list(dict.fromkeys(_allowed_origins + _DEFAULT_ORIGINS))
elif _is_development:
    _allowed_origins = "*"
else:
    _allowed_origins = _DEFAULT_ORIGINS

# ---------------------------------------------------------------------------
# Initialize extensions
# ---------------------------------------------------------------------------
# The B2B portal frontend (portal.goumuve.com) talks to /portal/v1/*, so it
# needs CORS too — without this every portal API call is blocked in-browser
# and the app bounces to /login. Stripe webhooks under /portal are server-to-
# server (CORS irrelevant there) so including them is harmless.
CORS(
    app,
    resources={
        r"/api/*": {"origins": _allowed_origins},
        r"/portal/*": {"origins": _allowed_origins},
    },
)
sqlalchemy_db.init_app(app)
socketio.init_app(
    app,
    cors_allowed_origins=_allowed_origins,
    async_mode="threading",  # Threading mode is fully compatible with Socket.IO v4
    logger=False,
    engineio_logger=False,
    # Polling-only. Under the gunicorn eventlet worker, threading-mode WebSocket
    # upgrades raise an unhandled StopIteration (Sentry noise) and fall back to
    # polling anyway. Disabling upgrades stops the failing WS handshake with no
    # functional change. Re-enable via a tested async_mode="eventlet" migration
    # when real WebSockets are wanted for performance.
    allow_upgrades=False,
    transports=['polling'],
    # Mobile connections behind Render can stall briefly; use less aggressive
    # heartbeat settings to avoid flapping between connected/reconnecting.
    ping_interval=25,
    ping_timeout=20,
)

# ---------------------------------------------------------------------------
# Rate limiting (in-memory; upgrade to Redis via RATELIMIT_STORAGE_URI)
# ---------------------------------------------------------------------------
limiter.init_app(app)


@app.errorhandler(429)
def ratelimit_handler(e):
    # e.description is set by Flask-Limiter and contains the limit that was hit.
    # Retry-After header is automatically set by Flask-Limiter; read it back.
    retry_after = e.get_headers().get("Retry-After") if hasattr(e, "get_headers") else None
    retry_after_seconds = int(retry_after) if retry_after else 60
    return jsonify({
        "error": "Too many requests. Please try again later.",
        "retry_after": retry_after_seconds,
    }), 429

# Legacy SQLite database (kept for backward compatibility with existing endpoints)
legacy_db = Database(app.config["DATABASE_PATH"])

# ---------------------------------------------------------------------------
# Register blueprints
# ---------------------------------------------------------------------------
app.register_blueprint(auth_bp)
app.register_blueprint(drivers_bp)
app.register_blueprint(pricing_bp)
app.register_blueprint(ratings_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(payments_bp)
app.register_blueprint(webhook_bp)
app.register_blueprint(booking_bp)
app.register_blueprint(upload_bp)
app.register_blueprint(jobs_bp)
app.register_blueprint(offers_bp)
app.register_blueprint(tracking_bp)
app.register_blueprint(driver_bp)
app.register_blueprint(operator_bp)
app.register_blueprint(push_bp)
app.register_blueprint(service_area_bp)
# app.register_blueprint(migration_bp)  # TEMPORARY - DISABLED for security
app.register_blueprint(recurring_bp)
app.register_blueprint(referrals_bp)
app.register_blueprint(support_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(onboarding_bp)
app.register_blueprint(promos_bp)
app.register_blueprint(reviews_bp)
app.register_blueprint(operator_applications_bp)
app.register_blueprint(vapi_bp)
app.register_blueprint(sms_webhook_bp)
app.register_blueprint(campaigns_bp)

# Automated operator/hauler recruiting outreach (operator_outreach.py)
try:
    from operator_outreach import outreach_bp
    app.register_blueprint(outreach_bp)
except Exception as _o_exc:
    import logging as _logging
    _logging.getLogger(__name__).warning("outreach_bp not registered: %s", _o_exc)

# Automated B2B customer-acquisition outreach (b2b_outreach.py)
try:
    from b2b_outreach import b2b_outreach_bp
    app.register_blueprint(b2b_outreach_bp)
except Exception as _b_exc:
    import logging as _logging
    _logging.getLogger(__name__).warning("b2b_outreach_bp not registered: %s", _b_exc)

# Ask Umuve — hosted call-coach assistant for the sales VA (trixie_assistant.py)
try:
    from trixie_assistant import coach_bp
    app.register_blueprint(coach_bp)
except Exception as _c_exc:
    import logging as _logging
    _logging.getLogger(__name__).warning("coach_bp not registered: %s", _c_exc)

# VA Tools Hub — situation-based text sender (Tracy's suggestion 2026-07-03)
try:
    from va_hub import vahub_bp
    app.register_blueprint(vahub_bp)
except Exception as _v_exc:
    import logging as _logging
    _logging.getLogger(__name__).warning("vahub_bp not registered: %s", _v_exc)

# VA Call Desk — one-card-at-a-time calling console for the demand list
try:
    from va_calls import vacalls_bp
    app.register_blueprint(vacalls_bp)
except Exception as _vc_exc:
    import logging as _logging
    _logging.getLogger(__name__).warning("vacalls_bp not registered: %s", _vc_exc)

# Previously built-but-never-registered public endpoints (2026-07-03 audit):
# newsletter capture + partner signups. Both are plain lead-capture routes the
# marketing site links to; registering them turns 404s into leads.
try:
    from routes.subscribe import subscribe_bp
    app.register_blueprint(subscribe_bp)
except Exception as _s_exc:
    import logging as _logging
    _logging.getLogger(__name__).warning("subscribe_bp not registered: %s", _s_exc)

try:
    from routes.partners import partners_bp
    app.register_blueprint(partners_bp)
except Exception as _p_exc:
    import logging as _logging
    _logging.getLogger(__name__).warning("partners_bp not registered: %s", _p_exc)

# AI photo analysis — register only when an OpenAI key exists (route 500s without).
if os.environ.get("OPENAI_API_KEY"):
    try:
        from routes import ai_bp
        app.register_blueprint(ai_bp)
    except Exception as _ai_exc:
        import logging as _logging
        _logging.getLogger(__name__).warning("ai_bp not registered: %s", _ai_exc)

# Send Setup Link — operator-onboarding SMS tool (op_text_tool.py)
try:
    from op_text_tool import optext_bp
    app.register_blueprint(optext_bp)
except Exception as _t_exc:
    import logging as _logging
    _logging.getLogger(__name__).warning("optext_bp not registered: %s", _t_exc)

# B2B agreements — in-app e-signature: passcode-gated /agreements console +
# public tokenized /sign/<token> pages (routes/agreements.py)
try:
    from routes.agreements import agreements_bp
    app.register_blueprint(agreements_bp)
except Exception as _ag_exc:
    import logging as _logging
    _logging.getLogger(__name__).warning("agreements_bp not registered: %s", _ag_exc)

# Concierge (shadow-operator) mode — phone-only haulers via SMS offers +
# token-gated /w/ job console + manual-payout ledger (routes/concierge.py)
try:
    from routes.concierge import concierge_bp
    app.register_blueprint(concierge_bp)
except Exception as _cg_exc:
    import logging as _logging
    _logging.getLogger(__name__).warning("concierge_bp not registered: %s", _cg_exc)

# Vision-Based Binding Quote Engine (spec 01-vision-quote-engine.md)
try:
    from routes.quotes import quotes_bp
    app.register_blueprint(quotes_bp)
except Exception as _q_exc:
    import logging as _logging
    _logging.getLogger(__name__).warning("quotes_bp not registered: %s", _q_exc)

# Voice AI Inbound v1 (spec 02-voice-ai-inbound.md) — /api/v1/voice/*
try:
    from routes.voice import voice_bp
    app.register_blueprint(voice_bp)
except Exception as _v_exc:
    import logging as _logging
    _logging.getLogger(__name__).warning("voice_bp not registered: %s", _v_exc)

# B2B Commercial Portal (spec 04-commercial-b2b-portal.md) — /portal/v1/*
try:
    from routes.portal import portal_bp
    app.register_blueprint(portal_bp)
    from billing_portal import billing_portal_bp
    app.register_blueprint(billing_portal_bp)
except Exception as _p_exc:
    import logging as _logging
    _logging.getLogger(__name__).warning("portal_bp not registered: %s", _p_exc)

# Portal v1 expansion (spec 04 §9) — Units, RecurringSchedule, ESG, SSO, audit
try:
    from routes.portal_v1 import portal_v1_bp
    app.register_blueprint(portal_v1_bp)
    from routes.portal_sso import portal_sso_bp
    app.register_blueprint(portal_sso_bp)
    import portal_recurring as _portal_recurring
    import portal_invoicing as _portal_invoicing
    _portal_recurring.register_cli(app)
    _portal_invoicing.register_cli(app)
except Exception as _pv1_exc:
    import logging as _logging
    _logging.getLogger(__name__).warning("portal_v1_bp not registered: %s", _pv1_exc)

# Partner (Driver) Acquisition Agent (spec 07) — /partner/v1/*
try:
    from routes.partner import partner_bp
    app.register_blueprint(partner_bp)
    from partner_cli import partner_cli
    app.cli.add_command(partner_cli)
except Exception as _pa_exc:
    import logging as _logging
    _logging.getLogger(__name__).warning("partner_bp not registered: %s", _pa_exc)

# Partner v1 expansion (spec 07 §9) — scrapers, Claude outreach, Checkr, Stripe Connect, LangGraph
try:
    from routes.partner_v1 import partner_v1_bp
    app.register_blueprint(partner_v1_bp)
except Exception as _pav1_exc:
    import logging as _logging
    _logging.getLogger(__name__).warning("partner_v1_bp not registered: %s", _pav1_exc)

# Ops Supervisor Agent (spec 11) — /ops-supervisor/v1/*
try:
    from routes.ops_supervisor import ops_supervisor_bp
    app.register_blueprint(ops_supervisor_bp)
except Exception as _o_exc:
    import logging as _logging
    _logging.getLogger(__name__).warning("ops_supervisor_bp not registered: %s", _o_exc)

# Ops Supervisor v1 expansion (spec 11 §9) — Haiku classifier, Opus agent, LangGraph, Redis, PagerDuty
try:
    from routes.ops_supervisor_v1 import ops_supervisor_v1_bp
    app.register_blueprint(ops_supervisor_v1_bp)
    from ops_worker_cli import register_worker_cli as _register_ops_worker
    _register_ops_worker(app)
except Exception as _ov1_exc:
    import logging as _logging
    _logging.getLogger(__name__).warning("ops_supervisor_v1_bp not registered: %s", _ov1_exc)

# Dynamic Surge Pricing (spec 08-dynamic-surge-pricing.md)
try:
    from routes.surge import surge_bp
    app.register_blueprint(surge_bp)
except Exception as _s_exc:
    import logging as _logging
    _logging.getLogger(__name__).warning("surge_bp not registered: %s", _s_exc)

# Insurance Claims Pipeline (spec 10-insurance-claims-pipeline.md)
# Umuve is a documentation-and-haul vendor, NOT a public adjuster (FL \u00a7626).
try:
    from routes.claims import claims_bp
    app.register_blueprint(claims_bp)
except Exception as _c_exc:
    import logging as _logging
    _logging.getLogger(__name__).warning("claims_bp not registered: %s", _c_exc)

# Post-Haul Attach Upsell Engine (spec 09-post-haul-attach-engine.md)
try:
    from routes.attach import attach_bp
    app.register_blueprint(attach_bp)
except Exception as _a_exc:
    import logging as _logging
    _logging.getLogger(__name__).warning("attach_bp not registered: %s", _a_exc)

# Rescue Engine v1 \u2014 per-job disposition preference + outcome + impact receipt.
# (The advanced per-item resale marketplace + IRS donation receipts + landfill
# routing optimizer \u2014 routes/resale.py, routes/routing.py \u2014 are a later,
# partner-dependent phase; their schema exists but stays dormant until real
# resale/donation partners are signed. Not imported here on purpose.)
try:
    from routes.impact import impact_bp
    app.register_blueprint(impact_bp)
except Exception as _imp_exc:
    import logging as _logging
    _logging.getLogger(__name__).warning("impact_bp not registered: %s", _imp_exc)

# Life-Event Demand Trigger Engine (spec 03-life-event-triggers.md)
# Umuve is a documentation-and-haul vendor, NOT a public adjuster (FL sec.
# 626) and NOT a restoration contractor (FL sec. 489). Every outbound
# contact is TCPA-gated by backend/tcpa.py.
try:
    from routes.leads import leads_bp
    app.register_blueprint(leads_bp)
except Exception as _l_exc:
    import logging as _logging
    _logging.getLogger(__name__).warning("leads_bp not registered: %s", _l_exc)

# ---------------------------------------------------------------------------
# Test endpoints DISABLED for security (were /api/test/seed-jobs,
# /api/test/delete-jobs-without-category, /api/test/fix-jobs-add-category)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Input sanitization middleware (XSS / injection prevention)
# ---------------------------------------------------------------------------
# Paths that must NOT have their bodies sanitized (file uploads, webhooks).
_SANITIZE_SKIP_PREFIXES = ("/api/bookings/upload-photos", "/uploads/", "/api/webhooks/", "/api/upload/", "/api/drivers/onboarding/documents", "/api/vapi/")


@app.before_request
def sanitize_json_input():
    """Sanitize all string values in incoming JSON bodies.

    Skips file-upload and webhook endpoints so that binary payloads and
    third-party webhook signatures are not corrupted.
    """
    if request.path.startswith(_SANITIZE_SKIP_PREFIXES):
        return  # skip

    # Skip sanitization for job photo uploads (multipart/form-data, not JSON)
    if "/photos/before" in request.path or "/photos/after" in request.path:
        return  # skip

    if request.is_json:
        try:
            raw = request.get_json(silent=True)
            if raw is not None:
                # Replace the parsed JSON cache with sanitized data so that
                # downstream calls to request.get_json() return clean values.
                request._cached_data = request.get_data()
                sanitized = sanitize_dict(raw)
                request._json = sanitized  # type: ignore[attr-defined]
        except Exception:
            pass  # If JSON parsing fails, let the route handler deal with it.


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------
@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if (request.path.startswith("/coach") or request.path.startswith("/optext")
            or request.path == "/va" or request.path.startswith("/va/")
            or request.path == "/agreements" or request.path.startswith("/agreements/")
            or request.path.startswith("/sign/")):
        # Internal VA tools (call coach + send-setup-link + VA hub) and the
        # agreements e-sign pages: load their own same-origin CSS/JS and call
        # same-origin APIs. Everything else locked.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; "
            "script-src 'self'; connect-src 'self'; base-uri 'none'; "
            "form-action 'self'; frame-ancestors 'none'"
        )
    else:
        response.headers["Content-Security-Policy"] = "default-src 'none'"
    if not _is_development:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# ---------------------------------------------------------------------------
# Create all SQLAlchemy tables on startup
# ---------------------------------------------------------------------------
with app.app_context():
    sqlalchemy_db.create_all()
    # Auto-run column migrations on startup (idempotent)
    try:
        from migrate import run_migrations
        run_migrations(app.config["SQLALCHEMY_DATABASE_URI"])
    except Exception as exc:
        app.logger.warning("Auto-migration on startup skipped: %s", exc)

    # ----------------------------------------------------------------------
    # One-time admin bootstrap (no shell required).
    #
    # Set BOOTSTRAP_ADMIN_EMAIL on the host (Render Environment tab) to promote
    # that user to admin on boot. Optionally set BOOTSTRAP_ADMIN_PASSWORD to
    # create the user if missing / reset the password. Reads creds from the
    # host env only (never hardcoded), so it is safe in a public repo: an
    # attacker can't set the host's env. Idempotent. REMOVE the password env
    # var once you've signed in.
    # ----------------------------------------------------------------------
    try:
        _boot_email = (os.environ.get("BOOTSTRAP_ADMIN_EMAIL") or "").strip().lower()
        if _boot_email:
            from sqlalchemy import func as _sa_func
            from models import User as _User
            _bu = (
                sqlalchemy_db.session.query(_User)
                .filter(_sa_func.lower(_User.email) == _boot_email)
                .first()
            )
            _boot_pw = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD")
            if _bu is None:
                if _boot_pw:
                    _bu = _User(
                        email=_boot_email,
                        name=_boot_email.split("@")[0],
                        role="admin",
                    )
                    _bu.set_password(_boot_pw)
                    sqlalchemy_db.session.add(_bu)
                    app.logger.info("admin-bootstrap: created admin %s", _boot_email)
                else:
                    app.logger.warning(
                        "admin-bootstrap: no user %s and no BOOTSTRAP_ADMIN_PASSWORD "
                        "to create one; skipping.", _boot_email,
                    )
            else:
                if _boot_pw:
                    _bu.set_password(_boot_pw)
                if _bu.role != "admin":
                    _bu.role = "admin"
                app.logger.info("admin-bootstrap: promoted %s to admin", _boot_email)
            sqlalchemy_db.session.commit()
    except Exception as exc:
        sqlalchemy_db.session.rollback()
        app.logger.warning("admin-bootstrap skipped: %s", exc)

    # ----------------------------------------------------------------------
    # Launch-promo guard (2026-07-17). PBC25 shipped with min_order_amount=0,
    # which let the code zero-out small jobs we still pay a hauler to run.
    # Raise the floor to $75 once; admins can still lower it deliberately via
    # the promos API — this only corrects the unset (0/None) state.
    # ----------------------------------------------------------------------
    try:
        from sqlalchemy import func as _sa_func
        from models import PromoCode as _PromoCode
        _pbc = (
            sqlalchemy_db.session.query(_PromoCode)
            .filter(_sa_func.upper(_PromoCode.code) == "PBC25")
            .first()
        )
        if _pbc is not None and not (_pbc.min_order_amount or 0):
            _pbc.min_order_amount = 75.0
            sqlalchemy_db.session.commit()
            app.logger.info("promo-guard: PBC25 min_order_amount set to 75.0")
    except Exception as exc:
        sqlalchemy_db.session.rollback()
        app.logger.warning("promo-guard skipped: %s", exc)

    # Seed the Post-Haul Attach Upsell Engine offer catalog (idempotent)
    try:
        from attach_catalog import seed_catalog
        seeded = seed_catalog(sqlalchemy_db, logger=app.logger)
        if seeded:
            app.logger.info("offer_catalog: seeded/updated %d rows", seeded)
    except Exception as exc:
        app.logger.warning("offer_catalog seeding skipped: %s", exc)

    # Seed South Florida landfill facilities (spec 06, idempotent).
    try:
        from seed_landfills import seed_landfill_facilities
        from models import LandfillFacility, TipFee, generate_uuid
        seeded = seed_landfill_facilities(
            sqlalchemy_db.session, LandfillFacility, TipFee, generate_uuid,
        )
        if seeded:
            app.logger.info("landfill_facilities: seeded %d rows", seeded)
    except Exception as exc:
        app.logger.warning("landfill_facility seeding skipped: %s", exc)

# ---------------------------------------------------------------------------
# Background scheduler (recurring jobs, pickup reminders)
# ---------------------------------------------------------------------------
from scheduler import init_scheduler
_scheduler = init_scheduler(app)


# ---------------------------------------------------------------------------
# Flask CLI command:  flask db-migrate
# ---------------------------------------------------------------------------
import click

@app.cli.command("db-migrate")
def cli_db_migrate():
    """Run database migrations (add new columns / create new tables)."""
    from migrate import run_migrations
    url = app.config["SQLALCHEMY_DATABASE_URI"]
    click.echo("Running Umuve database migrations...")
    actions = run_migrations(url)
    for action in actions:
        click.echo("  -> {}".format(action))
    click.echo("Migration complete.")


# ---------------------------------------------------------------------------
# Flask CLI: portal (spec 04) — sales-team bootstrap
# ---------------------------------------------------------------------------
@app.cli.group("portal")
def cli_portal():
    """B2B Commercial Portal operations."""
    pass


@cli_portal.command("orgs-create")
@click.option("--name", required=True, help="Company name")
@click.option("--billing-email", required=True)
@click.option("--owner-email", required=True)
@click.option("--owner-name", default=None)
@click.option(
    "--tier",
    type=click.Choice(("starter", "pro", "enterprise")),
    default="starter",
)
@click.option("--slug", default=None)
def cli_portal_orgs_create(name, billing_email, owner_email, owner_name,
                           tier, slug):
    """Provision a new org + initial owner. Prints invite URL."""
    import secrets as _secrets
    from models import db, User, Org, OrgMember
    from routes.portal import _slugify, _unique_slug

    with app.app_context():
        slug_final = _unique_slug(_slugify(slug or name))
        org = Org(
            name=name,
            slug=slug_final,
            billing_email=billing_email.strip().lower(),
            tier=tier,
            net_terms_days=30 if tier == "enterprise" else 0,
            status="trial",
        )
        db.session.add(org)
        db.session.flush()

        email = owner_email.strip().lower()
        user = db.session.query(User).filter_by(email=email).first()
        if user is None:
            user = User(email=email, name=owner_name, role="customer")
            db.session.add(user)
            db.session.flush()

        invite = _secrets.token_urlsafe(32)
        member = OrgMember(
            org_id=org.id,
            user_id=user.id,
            role="owner",
            scopes=["*"],
            invite_token=invite,
        )
        db.session.add(member)
        db.session.commit()

        import os as _os
        base = _os.environ.get("PORTAL_URL", "https://portal.goumuve.com")
        invite_url = "{}/invite?token={}".format(base, invite)
        click.echo("Org created: {} (slug={}, id={})".format(
            name, slug_final, org.id
        ))
        click.echo("Owner: {} ({})".format(email, user.id))
        click.echo("Invite URL: {}".format(invite_url))

        resend_key = _os.environ.get("RESEND_API_KEY")
        if resend_key:
            try:
                import resend as _resend
                _resend.api_key = resend_key
                sender = _os.environ.get(
                    "PORTAL_INVITE_FROM", "Umuve <portal@goumuve.com>"
                )
                _resend.Emails.send({
                    "from": sender,
                    "to": [email],
                    "subject": "Your Umuve Commercial Portal invite",
                    "html": (
                        "<p>Hi,</p>"
                        "<p>Your Umuve Commercial Portal account for "
                        "<strong>{}</strong> is ready.</p>"
                        "<p><a href=\"{}\">Click here to activate</a></p>"
                        "<p>This link is single-use and expires after first "
                        "login.</p>"
                    ).format(name, invite_url),
                })
                click.echo("Invite email sent to {} via Resend".format(email))
            except Exception as _email_exc:
                click.echo(
                    "Invite email FAILED (URL still valid): {}".format(
                        _email_exc
                    ),
                    err=True,
                )
        else:
            click.echo(
                "RESEND_API_KEY not set; skipping email — share the URL manually.",
                err=True,
            )


@cli_portal.command("bootstrap-stripe")
def cli_portal_bootstrap_stripe():
    """Create Stripe products + prices for all tiers (idempotent)."""
    from billing_portal import bootstrap
    cfg = bootstrap()
    import json as _json
    click.echo(_json.dumps(cfg, indent=2))


@cli_portal.command("subscribe")
@click.argument("org_id")
@click.option("--tier", default=None,
              type=click.Choice(("starter", "pro", "enterprise")))
def cli_portal_subscribe(org_id, tier):
    """Attach a Stripe subscription to an existing org."""
    from billing_portal import subscribe_org
    with app.app_context():
        out = subscribe_org(org_id, tier)
        import json as _json
        click.echo(_json.dumps(out, indent=2))


# ---------------------------------------------------------------------------
# Authentication decorator (legacy API-key based)
# ---------------------------------------------------------------------------
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get("X-API-Key")
        if api_key != app.config["API_KEY"]:
            return jsonify({"error": "Invalid or missing API key"}), 401
        return f(*args, **kwargs)
    return decorated_function


# ---------------------------------------------------------------------------
# Helper functions (legacy)
# ---------------------------------------------------------------------------
def calculate_price(service_ids, zip_code):
    """Calculate estimated price based on services"""
    total = 0
    services = []

    for service_id in service_ids:
        service = legacy_db.get_service(service_id)
        if service:
            total += service["base_price"]
            services.append(service)

    if len(services) > 0 and total < app.config["BASE_PRICE"]:
        total += app.config["BASE_PRICE"]

    return round(total, 2), services


def get_available_time_slots(requested_date=None):
    """Generate available time slots for booking"""
    slots = []
    start_date = datetime.now() + timedelta(days=1)

    if requested_date:
        try:
            start_date = datetime.strptime(requested_date, "%Y-%m-%d")
        except Exception:
            pass

    for day_offset in range(7):
        date = start_date + timedelta(days=day_offset)
        for hour in [9, 13]:
            slot_time = date.replace(hour=hour, minute=0, second=0)
            slots.append(slot_time.strftime("%Y-%m-%d %H:%M"))

    return slots[:10]


# ---------------------------------------------------------------------------
# Legacy API Routes (kept for backward compatibility)
# ---------------------------------------------------------------------------
@app.route("/api/health", methods=["GET"])
@limiter.exempt
def health_check():
    """Health check endpoint (exempt from rate limiting)"""
    return jsonify({"status": "healthy", "service": "Umuve API", "version": "2.2.6-maya-prices"}), 200


def _check_admin_seed_secret(path_secret=None):
    """Constant-time gate for the ADMIN_SEED_SECRET-protected endpoints.

    The secret is accepted from the "X-Admin-Secret" request header
    (preferred — keeps it out of URL paths and access logs) or, for backward
    compatibility with existing callers, from the URL path segment. Returns
    True only when ADMIN_SEED_SECRET is configured AND one of the provided
    values matches (hmac.compare_digest, no timing leak).
    """
    expected = os.environ.get("ADMIN_SEED_SECRET", "")
    if not expected:
        return False
    expected_bytes = expected.encode("utf-8")
    header_secret = request.headers.get("X-Admin-Secret", "")
    if header_secret and hmac.compare_digest(
        header_secret.encode("utf-8"), expected_bytes
    ):
        return True
    if path_secret and hmac.compare_digest(
        str(path_secret).encode("utf-8"), expected_bytes
    ):
        return True
    return False


@app.route("/api/run-migrate/<secret>", methods=["POST"])
def run_migrate_endpoint(secret):
    """Database migration endpoint secured by ADMIN_SEED_SECRET env var."""
    if not _check_admin_seed_secret(secret):
        return jsonify({"error": "Forbidden"}), 403
    try:
        from migrate import run_migrations
        url = app.config["SQLALCHEMY_DATABASE_URI"]
        actions = run_migrations(url)
        return jsonify({"success": True, "actions": actions}), 200
    except Exception as exc:
        import traceback
        app.logger.error("Migration failed: %s\n%s", exc, traceback.format_exc())
        return jsonify({"error": "Migration failed"}), 500


@app.route("/api/admin/test-alert/<secret>", methods=["POST", "GET"])
def test_alert_endpoint(secret):
    """Fire a test SMS + email to the configured admin contacts.

    Verifies the operator-alert delivery chain end-to-end (Twilio + email +
    ADMIN_PHONE/ADMIN_EMAIL config) without needing a real booking or payment.
    Secured by the same ADMIN_SEED_SECRET env var as the migrate endpoint.

    Returns which channels are configured and whether each send was attempted,
    so a missing env var or provider misconfig is visible in the response.
    """
    if not _check_admin_seed_secret(secret):
        return jsonify({"error": "Forbidden"}), 403

    admin_phone = os.environ.get("ADMIN_PHONE", "")
    admin_email = os.environ.get("ADMIN_EMAIL", "")

    result = {
        "admin_phone_configured": bool(admin_phone),
        "admin_email_configured": bool(admin_email),
        "sms_attempted": False,
        "email_attempted": False,
        "errors": [],
    }

    if not admin_phone and not admin_email:
        result["errors"].append(
            "Neither ADMIN_PHONE nor ADMIN_EMAIL is set — no alert can be delivered."
        )
        return jsonify(result), 200

    if admin_phone:
        try:
            from sms_service import send_sms_async
            send_sms_async(
                admin_phone,
                "umuve alert test ✅ — if you got this, your SMS alert chain is "
                "live. (No action needed.)",
            )
            result["sms_attempted"] = True
        except Exception as exc:
            result["errors"].append("SMS send failed: {}".format(exc))
            app.logger.exception("test-alert SMS failed")

    if admin_email:
        try:
            from email_service import send_email_async
            send_email_async(
                admin_email,
                "✅ umuve alert test",
                "<h2>Alert chain is live</h2><p>If you're reading this, the "
                "email alert path (ADMIN_EMAIL + email service) is working. "
                "No action needed — this was a manual test ping.</p>",
            )
            result["email_attempted"] = True
        except Exception as exc:
            result["errors"].append("Email send failed: {}".format(exc))
            app.logger.exception("test-alert email failed")

    return jsonify(result), 200


@app.route("/api/admin/seed-demo-driver/<secret>", methods=["POST", "GET"])
def seed_demo_driver_endpoint(secret):
    """Idempotently create the App Store reviewer demo account for Umuve Pro.

    Apple rejects a contractor app without working demo credentials. This seeds:
      - driver-test@goumuve.com  (role=driver, APPROVED contractor, online)
      - a demo customer + one demo Job ASSIGNED to that driver, so the reviewer
        can walk accept -> navigate -> complete.

    Secured by ADMIN_SEED_SECRET. Re-running is safe (fetches existing rows).
    Pass ?password=... to set the login password; omitted, a random one is
    generated (this repo is public — no literal defaults). Returns the
    exact credentials to paste into App Store Connect → App Review Information.
    """
    if not _check_admin_seed_secret(secret):
        return jsonify({"error": "Forbidden"}), 403

    import secrets as _secrets
    from datetime import timedelta as _td
    from flask import request as _req
    from models import db, User, Contractor, Job, generate_uuid, utcnow

    password = _req.args.get("password") or "Rev-{}".format(_secrets.token_urlsafe(12))
    created = {"user": False, "contractor": False, "customer": False, "job": False}

    try:
        # --- Driver user ---
        driver = User.query.filter_by(email="driver-test@goumuve.com").first()
        if not driver:
            driver = User(id=generate_uuid(), email="driver-test@goumuve.com",
                          name="Demo Driver", phone="+15615550100", role="driver")
            db.session.add(driver)
            created["user"] = True
        driver.role = "driver"
        driver.set_password(password)  # always reset so creds are known

        # --- Approved, online contractor profile ---
        contractor = Contractor.query.filter_by(user_id=driver.id).first()
        if not contractor:
            contractor = Contractor(id=generate_uuid(), user_id=driver.id)
            db.session.add(contractor)
            created["contractor"] = True
        contractor.approval_status = "approved"
        contractor.onboarding_status = "approved"
        contractor.background_check_status = "passed"
        contractor.is_online = True
        contractor.truck_type = "Box Truck"
        contractor.truck_capacity = 600.0
        contractor.avg_rating = 4.9
        contractor.total_jobs = 27
        contractor.current_lat = 26.7153
        contractor.current_lng = -80.0534

        # --- Demo customer (so the job has a real name/address to show) ---
        customer = User.query.filter_by(email="demo-customer@goumuve.com").first()
        if not customer:
            customer = User(id=generate_uuid(), email="demo-customer@goumuve.com",
                            name="Jordan Reviewer", phone="+15615550111", role="customer")
            db.session.add(customer)
            created["customer"] = True
        db.session.flush()

        # --- One demo job assigned to the driver (fixed code = idempotent) ---
        job = Job.query.filter_by(confirmation_code="DEMO0001").first()
        if not job:
            job = Job(
                id=generate_uuid(),
                customer_id=customer.id,
                driver_id=contractor.id,
                status="assigned",
                address="120 S Olive Ave, West Palm Beach, FL 33401",
                lat=26.7128, lng=-80.0527,
                items=[{"category": "Sofa", "quantity": 1},
                       {"category": "Mattress", "quantity": 1},
                       {"category": "Boxes", "quantity": 8}],
                volume_estimate=180.0,
                scheduled_at=utcnow() + _td(days=1),
                base_price=129.00, total_price=129.00,
                confirmation_code="DEMO0001",
                notes="App Store reviewer demo job — safe to ignore operationally.",
            )
            db.session.add(job)
            created["job"] = True
        else:
            job.driver_id = contractor.id
            job.status = "assigned"

        db.session.commit()

        return jsonify({
            "success": True,
            "created": created,
            "credentials_for_apple_review": {
                "email": "driver-test@goumuve.com",
                "password": password,
            },
            "contractor_id": contractor.id,
            "demo_job_code": "DEMO0001",
            "note": "Paste these into App Store Connect → App Review Information. "
                    "Account is approved + online with one assigned demo job.",
        }), 200
    except Exception as exc:
        db.session.rollback()
        app.logger.exception("seed-demo-driver failed")
        return jsonify({"error": "Seed failed: {}".format(exc)}), 500


@app.route("/api/admin/provision-hauler/<secret>", methods=["POST"])
def provision_hauler_endpoint(secret):
    """Idempotently provision a REAL independent hauler (driver) and approve them.

    One-shot supply onboarding: creates the login account + an APPROVED contractor
    profile so the hauler can log in, go online, and receive jobs. Used to sign up
    haulers we've recruited directly (e.g. the Palm Beach launch hauler) without
    needing an admin JWT or the dashboard.

    Secured by ADMIN_SEED_SECRET. Re-running is safe (updates the existing row).

    POST JSON:
      email       (required)  login email
      name        (required)  hauler's full name
      phone       (required)  E.164 preferred; normalized to +1 if 10 digits
      truck_type  (required)  pickup | cargo_van | box_truck | dump_trailer | flatbed
      password    (optional)  temp password; a secure one is generated if omitted
      truck_capacity (optional, cubic ft)
      lat, lng    (optional)  initial last-known location (defaults to West Palm Beach
                              so the coverage gate opens for PBC before first GPS ping)

    Returns the login credentials (incl. the generated temp password) to hand off.
    """
    if not _check_admin_seed_secret(secret):
        return jsonify({"error": "Forbidden"}), 403

    import secrets as _secrets
    import re as _re
    from flask import request as _req
    from models import db, User, Contractor, generate_uuid

    data = _req.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    name = (data.get("name") or "").strip()
    phone_raw = (data.get("phone") or "").strip()
    truck_type = (data.get("truck_type") or "").strip().lower().replace(" ", "_")

    if not email or not name or not phone_raw or not truck_type:
        return jsonify({"error": "email, name, phone, and truck_type are all required"}), 400

    valid_trucks = {"pickup", "cargo_van", "box_truck", "dump_trailer", "flatbed"}
    if truck_type not in valid_trucks:
        return jsonify({"error": "truck_type must be one of {}".format(sorted(valid_trucks))}), 400

    # Normalize phone to E.164 (+1) when given as 10 US digits.
    digits = _re.sub(r"\D", "", phone_raw)
    if phone_raw.startswith("+"):
        phone = "+" + digits
    elif len(digits) == 10:
        phone = "+1" + digits
    elif len(digits) == 11 and digits.startswith("1"):
        phone = "+" + digits
    else:
        return jsonify({"error": "phone must be a valid US number (10 digits) or E.164 (+1...)"}), 400

    password = data.get("password") or ("Umuve-" + _secrets.token_urlsafe(6))
    generated_password = not data.get("password")

    try:
        existing_email = User.query.filter_by(email=email).first()
        user = existing_email
        created_user = False
        if not user:
            user = User(id=generate_uuid(), email=email, name=name, phone=phone, role="driver")
            db.session.add(user)
            created_user = True
        user.name = name or user.name
        user.phone = phone
        user.role = "driver"
        user.set_password(password)  # always set so the handoff creds are known
        db.session.flush()

        contractor = Contractor.query.filter_by(user_id=user.id).first()
        created_contractor = False
        if not contractor:
            contractor = Contractor(id=generate_uuid(), user_id=user.id)
            db.session.add(contractor)
            created_contractor = True
        contractor.approval_status = "approved"
        contractor.is_operator = False
        # Seed last-known location so the supply/coverage gate sees PBC covered
        # before the hauler's first live GPS ping. Real location overwrites this
        # the moment he goes online in the app.
        if contractor.current_lat is None or data.get("lat") is not None:
            contractor.current_lat = float(data.get("lat", 26.7153))  # West Palm Beach
            contractor.current_lng = float(data.get("lng", -80.0534))
        contractor.truck_type = truck_type
        if data.get("truck_capacity") is not None:
            contractor.truck_capacity = float(data["truck_capacity"])
        # Hauler controls his own availability — start offline, he toggles online.
        contractor.is_online = bool(contractor.is_online)

        db.session.commit()

        return jsonify({
            "success": True,
            "created": {"user": created_user, "contractor": created_contractor},
            "contractor_id": contractor.id,
            "approval_status": contractor.approval_status,
            "login": {
                "email": email,
                "password": password,
                "password_was_generated": generated_password,
            },
            "next_steps": [
                "Send the hauler these credentials; have him change the password on first login.",
                "He logs in (Umuve Pro app or driver web), completes Stripe Connect to get paid, then toggles ONLINE to receive jobs.",
                "DISPATCH_MODE=assign: jobs auto-assign to approved+online contractors near the job.",
            ],
        }), 200
    except Exception as exc:
        db.session.rollback()
        app.logger.exception("provision-hauler failed")
        return jsonify({"error": "Provision failed: {}".format(exc)}), 500


@app.route("/api/admin/capi-status/<secret>", methods=["GET", "POST"])
def capi_status_endpoint(secret):
    """Report Meta Conversions API config + optionally fire a test event.

    Before flipping on paid ads we need to verify, from prod, that the
    server-side Conversions API is actually wired: pixel id present, access
    token present, and (optionally) that a test event reaches Events Manager.
    Secured by ADMIN_SEED_SECRET — same gate as the other /api/admin endpoints.

    NEVER echoes the access token or pixel id value — only booleans. Pass
    ?test=1 to fire a deduplicatable test 'Lead' event; it uses
    META_TEST_EVENT_CODE (if set) so it lands in the Events Manager
    "Test Events" tab without polluting live data. The response shows whether
    the send was accepted.
    """
    if not _check_admin_seed_secret(secret):
        return jsonify({"error": "Forbidden"}), 403

    from flask import request as _req

    result = {
        "has_pixel_id": bool(
            os.environ.get("META_PIXEL_ID") or os.environ.get("NEXT_PUBLIC_META_PIXEL_ID")
        ),
        "has_access_token": bool(os.environ.get("META_CAPI_ACCESS_TOKEN")),
        "has_test_event_code": bool(os.environ.get("META_TEST_EVENT_CODE")),
        "test_event": None,
    }

    try:
        import meta_capi
        # meta_capi.status() is the authoritative readout (it reflects the
        # module-level config actually loaded at import time).
        result["capi_status"] = meta_capi.status()
    except Exception as exc:
        app.logger.exception("capi-status: failed to read meta_capi.status()")
        result["capi_status"] = {"error": str(exc)}

    # Optional: fire a no-op-safe test event to confirm the send path works.
    if _req.args.get("test") in ("1", "true", "yes"):
        try:
            import time as _time
            import meta_capi
            test_event_id = "capi_test_{}".format(int(_time.time()))
            sent = meta_capi.send_event(
                "Lead",
                test_event_id,
                meta_capi._build_user_data(email="capi-test@goumuve.com"),
                custom_data={"currency": "USD", "value": 0},
                event_source_url="https://app.goumuve.com/",
            )
            result["test_event"] = {
                "attempted": True,
                "accepted": bool(sent),
                "event_id": test_event_id,
                "note": (
                    "Sent with META_TEST_EVENT_CODE — check Events Manager > "
                    "Test Events." if result["has_test_event_code"]
                    else "No META_TEST_EVENT_CODE set — this hit LIVE data."
                ),
            }
        except Exception as exc:
            app.logger.exception("capi-status: test event failed")
            result["test_event"] = {"attempted": True, "accepted": False, "error": str(exc)}

    return jsonify(result), 200


@app.route("/api/admin/social-status/<secret>", methods=["GET"])
def social_status_endpoint(secret):
    """Report social-posting (IG/FB Graph API) readiness from prod.

    The social-poster automation needs META_ACCESS_TOKEN (page token with
    pages_manage_posts + instagram_content_publish), META_PAGE_ID, and the
    page-linked IG business account. This endpoint shows what is present and
    live-probes the token's granted scopes + IG link so setup gaps are
    obvious without anyone pasting tokens around. Secured by
    ADMIN_SEED_SECRET. NEVER echoes the token — only booleans, scope names,
    and ids (page/IG ids are not secrets).
    """
    if not _check_admin_seed_secret(secret):
        return jsonify({"error": "Forbidden"}), 403

    token = os.environ.get("META_ACCESS_TOKEN", "")
    page_id = os.environ.get("META_PAGE_ID", "")
    result = {
        "has_access_token": bool(token),
        "has_page_id": bool(page_id),
        "has_ig_user_id": bool(os.environ.get("IG_USER_ID")),
        "sample_asset_url": url_for(
            "static", filename="marketing/umuve-pbc-trustlocal-9x16.png", _external=True
        ),
        "granted_scopes": None,
        "instagram_business_account": None,
        "can_post_fb": False,
        "can_post_ig": False,
    }

    if token:
        try:
            import requests as _requests

            perms = _requests.get(
                "https://graph.facebook.com/v23.0/me/permissions",
                params={"access_token": token},
                timeout=10,
            ).json()
            scopes = [
                p["permission"]
                for p in perms.get("data", [])
                if p.get("status") == "granted"
            ]
            result["granted_scopes"] = scopes
            result["can_post_fb"] = "pages_manage_posts" in scopes
            if page_id:
                page = _requests.get(
                    "https://graph.facebook.com/v23.0/{}".format(page_id),
                    params={
                        "fields": "instagram_business_account,name",
                        "access_token": token,
                    },
                    timeout=10,
                ).json()
                ig = (page.get("instagram_business_account") or {}).get("id")
                result["instagram_business_account"] = ig
                result["page_name"] = page.get("name")
                result["can_post_ig"] = bool(
                    ig and "instagram_content_publish" in scopes
                )
        except Exception as exc:
            app.logger.exception("social-status: Graph API probe failed")
            result["probe_error"] = str(exc)

    return jsonify(result), 200


@app.route("/api/admin/backfill-approval-emails/<secret>", methods=["POST"])
def backfill_approval_emails_endpoint(secret):
    """Send the branded approval email to already-approved haulers who may have
    missed it (e.g. approved before the email existed, or the old email lacked
    the next-step instructions).

    Secured by ADMIN_SEED_SECRET. **DRY-RUN BY DEFAULT** -- returns the list of
    who WOULD be emailed without sending anything. Pass ?send=1 to actually send.
    ?role=operator (default) | driver | all.
    """
    if not _check_admin_seed_secret(secret):
        return jsonify({"error": "Forbidden"}), 403

    import time as _time
    from flask import request as _req
    from models import db, User, Contractor
    from notifications import (
        send_email_sync,
        render_driver_approval_email,
        render_operator_approval_email,
    )

    role = (_req.args.get("role") or "operator").strip().lower()
    do_send = _req.args.get("send") == "1"

    query = Contractor.query.filter_by(approval_status="approved")
    if role == "operator":
        query = query.filter(Contractor.is_operator.is_(True))
    elif role == "driver":
        query = query.filter(Contractor.is_operator.is_(False))
    # role == "all" -> no is_operator filter

    recipients = []
    sent = 0
    failed = []
    for c in query.all():
        user = db.session.get(User, c.user_id)
        if not user or not user.email:
            continue
        kind = "operator" if c.is_operator else "driver"
        recipients.append({"email": user.email, "name": user.name, "role": kind})
        if not do_send:
            continue
        try:
            if c.is_operator:
                subject, html = render_operator_approval_email(user.name)
            else:
                subject, html = render_driver_approval_email(user.name)
            # Synchronous + paced: Resend caps at 5 requests/sec. Async fan-out
            # bursts past that and silently drops recipients (see Sentry
            # ResendError). One send every 250ms (~4/sec) stays under the limit
            # and lets us report real per-recipient success/failure.
            result = send_email_sync(to_email=user.email, subject=subject, html_content=html)
            if result:
                sent += 1
            else:
                failed.append(user.email)
            _time.sleep(0.25)
        except Exception:
            app.logger.exception("backfill email failed for %s", user.email)
            failed.append(user.email)

    return jsonify({
        "dry_run": not do_send,
        "role_filter": role,
        "matched": len(recipients),
        "sent": sent,
        "failed": failed,
        "recipients": recipients,
        "note": ("DRY-RUN — no emails sent. Re-run with ?send=1 to actually send."
                 if not do_send else "Done: {} sent, {} failed.".format(sent, len(failed))),
    }), 200


@app.route("/api/admin/void-job/<secret>", methods=["POST"])
def void_job_endpoint(secret):
    """Cancel or delete a job by confirmation_code or job_id — for clearing test
    / junk bookings out of the pipeline. ADMIN_SEED_SECRET-gated.

    POST JSON: {"confirmation_code": "LEHIPLLG"}  or  {"job_id": "..."}
    Default  -> soft cancel (status='cancelled', payment cancelled) — safe, keeps the row.
    ?hard=1  -> fully delete the Job + its Payment/JobOffer rows and detach any Quote.
    """
    if not _check_admin_seed_secret(secret):
        return jsonify({"error": "Forbidden"}), 403

    from flask import request as _req
    from models import db, Job, Payment, utcnow

    data = _req.get_json(silent=True) or {}
    code = (data.get("confirmation_code") or "").strip()
    job_id = (data.get("job_id") or "").strip()
    hard = _req.args.get("hard") == "1"
    if not code and not job_id:
        return jsonify({"error": "confirmation_code or job_id required"}), 400

    try:
        job = db.session.get(Job, job_id) if job_id else None
        if job is None and code:
            job = Job.query.filter_by(confirmation_code=code).first()
        if not job:
            return jsonify({"error": "Job not found"}), 404

        jid = job.id
        summary = {
            "job_id": jid,
            "confirmation_code": job.confirmation_code,
            "prev_status": job.status,
            "total_price": job.total_price,
        }

        if hard:
            Payment.query.filter_by(job_id=jid).delete(synchronize_session=False)
            try:
                from models import Quote
                Quote.query.filter_by(booking_id=jid).update(
                    {"booking_id": None, "status": "voided"}, synchronize_session=False
                )
            except Exception:
                pass
            try:
                from models import JobOffer
                JobOffer.query.filter_by(job_id=jid).delete(synchronize_session=False)
            except Exception:
                pass
            db.session.delete(job)
            db.session.commit()
            return jsonify({"success": True, "action": "deleted", "job": summary}), 200

        job.status = "cancelled"
        job.cancelled_at = utcnow()
        Payment.query.filter_by(job_id=jid).update(
            {"payment_status": "cancelled"}, synchronize_session=False
        )
        db.session.commit()
        return jsonify({"success": True, "action": "cancelled", "job": summary}), 200
    except Exception as exc:
        db.session.rollback()
        app.logger.exception("void-job failed")
        return jsonify({"error": "Void failed: {}".format(exc)}), 500


@app.route("/api/services", methods=["GET"])
@require_api_key
def get_services():
    """Get all available services"""
    try:
        services = legacy_db.get_services()
        return jsonify({"success": True, "services": services}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/quote", methods=["POST"])
@require_api_key
def get_quote():
    """Get instant price quote"""
    try:
        data = request.get_json()

        if not data.get("services") or not isinstance(data["services"], list):
            return jsonify({"error": "Services array is required"}), 400

        zip_code = data.get("zip_code", "")
        service_ids = data["services"]

        estimated_price, services = calculate_price(service_ids, zip_code)
        available_slots = get_available_time_slots()

        return jsonify({
            "success": True,
            "estimated_price": estimated_price,
            "services": services,
            "available_time_slots": available_slots,
            "currency": "USD"
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bookings", methods=["POST"])
@require_api_key
def create_booking():
    """Create new booking"""
    try:
        data = request.get_json()

        required_fields = ["address", "services", "scheduled_datetime", "customer"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": "Missing required field: {}".format(field)}), 400

        customer_data = data["customer"]
        required_customer_fields = ["name", "email", "phone"]
        for field in required_customer_fields:
            if field not in customer_data:
                return jsonify({"error": "Missing customer field: {}".format(field)}), 400

        customer_id = legacy_db.create_customer(
            customer_data["name"],
            customer_data["email"],
            customer_data["phone"]
        )

        estimated_price, services = calculate_price(
            data["services"],
            data.get("zip_code", "")
        )

        booking_id = legacy_db.create_booking(
            customer_id=customer_id,
            address=data["address"],
            zip_code=data.get("zip_code", ""),
            services=data["services"],
            photos=data.get("photos", []),
            scheduled_datetime=data["scheduled_datetime"],
            estimated_price=estimated_price,
            notes=data.get("notes", "")
        )

        return jsonify({
            "success": True,
            "booking_id": booking_id,
            "estimated_price": estimated_price,
            "confirmation": "Booking #{} confirmed".format(booking_id),
            "scheduled_datetime": data["scheduled_datetime"],
            "services": services
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bookings/<int:booking_id>", methods=["GET"])
@require_api_key
def get_booking(booking_id):
    """Get booking details"""
    try:
        booking = legacy_db.get_booking(booking_id)

        if not booking:
            return jsonify({"error": "Booking not found"}), 404

        return jsonify({"success": True, "booking": booking}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Customer bookings endpoint (used by iOS app)
# ---------------------------------------------------------------------------
@app.route("/api/bookings/customer", methods=["POST"])
@require_auth
def get_customer_bookings(user_id):
    """Get all bookings for the authenticated customer"""
    from models import Job, User, Contractor

    # Use the authenticated user — ignore any email in the body
    user = sqlalchemy_db.session.get(User, user_id)
    if not user:
        return jsonify({"success": True, "bookings": []}), 200

    # Get jobs for this customer
    jobs = Job.query.filter_by(customer_id=user.id).order_by(Job.created_at.desc()).all()

    bookings = []
    for job in jobs:
        booking = job.to_dict()
        booking["confirmation"] = "Booking #{} confirmed".format(job.id[:8])
        # Include operator name for delegated jobs
        if job.operator_id and job.operator_rel:
            op_user = job.operator_rel.user
            booking["operator_name"] = op_user.name if op_user else None
        else:
            booking["operator_name"] = None
        bookings.append(booking)

    return jsonify({"success": True, "bookings": bookings}), 200


# ---------------------------------------------------------------------------
# Customer portal compatibility endpoints
# ---------------------------------------------------------------------------
@app.route("/api/bookings/validate-address", methods=["POST"])
def validate_address():
    """Validate an address (stub - returns success with formatted data)"""
    data = request.get_json()
    address = data.get("address", "")
    if not address:
        return jsonify({"success": False, "error": "Address is required"}), 400

    return jsonify({
        "success": True,
        "address": {
            "formatted": address,
            "placeId": None,
            "lat": 26.1224,
            "lng": -80.1373,
        }
    }), 200


@app.route("/api/bookings/upload-photos", methods=["POST"])
@require_auth
def upload_booking_photos(user_id):
    """Upload photos for a booking (proxy to upload blueprint)"""
    from storage import save_file

    if "photos" not in request.files:
        return jsonify({"success": False, "error": "No photos provided"}), 400

    files = request.files.getlist("photos")
    if len(files) > 10:
        return jsonify({"success": False, "error": "Maximum 10 photos per upload"}), 400
    urls = []

    for file in files:
        if file and file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower()
            if ext in {"jpg", "jpeg", "png", "webp"}:
                url = save_file(file, prefix="bookings", filename=file.filename)
                urls.append(url)

    return jsonify({"success": True, "urls": urls}), 201


@app.route("/api/bookings/estimate", methods=["POST"])
def portal_estimate():
    """Price estimate compatible with customer portal API shape.

    Accepts EITHER the simple portal format (itemCategory + quantity) OR the
    full v2 format (items array with optional size + scheduledDate).
    """
    data = request.get_json() or {}

    from routes.booking import calculate_estimate

    # --- Build items list from whichever format the caller uses ---
    items = data.get("items")
    if not items or not isinstance(items, list):
        # Legacy simple format: single category + quantity
        category = data.get("itemCategory") or data.get("category", "general")
        quantity = int(data.get("quantity", 1))
        size = data.get("size")
        items = [{"category": category, "quantity": quantity}]
        if size:
            items[0]["size"] = size

    scheduled_date = data.get("scheduledDate") or data.get("scheduled_date")
    address = data.get("address") or {}
    lat = address.get("lat")
    lng = address.get("lng")

    est = calculate_estimate(items, scheduled_date=scheduled_date, lat=lat, lng=lng)

    # --- Format duration label ---
    duration_min = est["estimated_duration"]
    if duration_min <= 60:
        duration_label = "{} minutes".format(duration_min)
    else:
        hours = duration_min // 60
        remaining = duration_min % 60
        duration_label = "{}-{} hours".format(hours, hours + 1) if remaining else "{} hour{}".format(hours, "s" if hours > 1 else "")

    # Return both the portal-compatible shape AND the full v2 breakdown
    return jsonify({
        "success": True,
        "estimate": {
            "subtotal": est["base_price"],
            "serviceFee": est["service_fee"],
            "tax": 0,
            "total": est["total"],
            "estimatedDuration": duration_label,
            "truckSize": est["truck_size"],
            # v2 detailed breakdown
            "items_subtotal": est["items_subtotal"],
            "items": est["items"],
            "volume_discount": est["volume_discount"],
            "volume_discount_label": est["volume_discount_label"],
            "surge_multiplier": est["surge_multiplier"],
            "surge_amount": est["surge_amount"],
            "surge_reasons": est["surge_reasons"],
            "minimum_applied": est["minimum_applied"],
        }
    }), 200


@app.route("/api/bookings/available-slots", methods=["GET"])
def get_portal_available_slots():
    """Available time slots compatible with customer portal"""
    date_str = request.args.get("date")
    slots = get_available_time_slots(date_str[:10] if date_str else None)

    formatted = []
    for slot in slots:
        formatted.append({
            "date": slot.split(" ")[0],
            "time": slot.split(" ")[1] if " " in slot else "09:00",
            "available": True,
        })

    return jsonify({"success": True, "slots": formatted}), 200


@app.route("/api/bookings/create", methods=["POST"])
@limiter.limit("10 per minute")
def portal_create_booking():
    """Create a booking from the customer portal (no auth required).

    Accepts the portal's form shape and creates a User + Job + Payment.
    """
    from werkzeug.security import generate_password_hash
    from models import Job, Payment, User, Notification, generate_uuid, utcnow
    from routes.booking import calculate_estimate, _notify_nearby_contractors

    data = request.get_json() or {}

    address = data.get("address")
    if not address:
        return jsonify({"error": "address is required"}), 400

    customer_info = data.get("customerInfo") or {}
    email = customer_info.get("email")
    name = customer_info.get("name", "")
    phone = customer_info.get("phone", "")

    if not email:
        return jsonify({"error": "customerInfo.email is required"}), 400

    # Find or create user
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email, name=name, phone=phone, role="customer",
                     password_hash=generate_password_hash(generate_uuid()))
        sqlalchemy_db.session.add(user)
        sqlalchemy_db.session.flush()

    category = data.get("itemCategory") or data.get("category") or "general"
    quantity = int(data.get("quantity", 1))
    size = data.get("size")

    # Parse location from addressDetails if available
    addr_details = data.get("addressDetails") or {}
    location = addr_details.get("location") or {}
    lat = location.get("lat")
    lng = location.get("lng")

    # --- Service area geofence check ---
    if lat is not None and lng is not None:
        from geofencing import is_in_service_area
        try:
            if not is_in_service_area(float(lat), float(lng)):
                return jsonify({
                    "error": "Address is outside our service area. "
                             "We currently serve Miami-Dade, Broward, and Palm Beach counties."
                }), 400
        except (TypeError, ValueError):
            pass  # Invalid coords -- skip check, let downstream handle it

    # Parse scheduled datetime
    scheduled_at = None
    selected_date = data.get("selectedDate")
    selected_time = data.get("selectedTime", "09:00")

    # Normalize time: convert "8:00 AM - 10:00 AM" or "2:00 PM" to "HH:MM"
    if selected_time and isinstance(selected_time, str):
        import re
        am_pm_match = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)", selected_time, re.IGNORECASE)
        if am_pm_match:
            hour = int(am_pm_match.group(1))
            minute = am_pm_match.group(2)
            period = am_pm_match.group(3).upper()
            if period == "PM" and hour != 12:
                hour += 12
            if period == "AM" and hour == 12:
                hour = 0
            selected_time = "{:02d}:{}".format(hour, minute)

    if selected_date:
        try:
            date_str = selected_date[:10] if isinstance(selected_date, str) else selected_date.strftime("%Y-%m-%d")
            from datetime import timezone as tz
            scheduled_at = datetime.strptime("{} {}".format(date_str, selected_time), "%Y-%m-%d %H:%M").replace(tzinfo=tz.utc)
        except Exception:
            pass

    items = [{"category": category, "quantity": quantity}]
    if size:
        items[0]["size"] = size
    photos = data.get("photoUrls") or data.get("photos") or []

    # Use the v2 pricing engine for accurate server-side calculation
    scheduled_date_for_pricing = selected_date[:10] if selected_date and isinstance(selected_date, str) else None
    est = calculate_estimate(
        items,
        scheduled_date=scheduled_date_for_pricing,
        lat=float(lat) if lat else None,
        lng=float(lng) if lng else None,
    )

    # SECURITY: Always use server-calculated price — never trust client totalAmount
    total_amount = est["total"]

    # --- Apply promo code if provided ---
    promo_code_str = data.get("promoCode", "").strip() or data.get("promo_code", "").strip()
    promo_code_id = None
    discount_amount = 0.0

    if promo_code_str:
        from routes.promos import validate_promo_code
        from models import PromoCode as _PC
        promo, discount, promo_error = validate_promo_code(promo_code_str, total_amount)
        if promo_error:
            return jsonify({"error": promo_error}), 400
        promo_code_id = promo.id
        discount_amount = discount
        total_amount = round(total_amount - discount, 2)
        promo.use_count = (promo.use_count or 0) + 1

    job = Job(
        id=generate_uuid(),
        customer_id=user.id,
        status="pending",
        address=address,
        lat=float(lat) if lat else None,
        lng=float(lng) if lng else None,
        items=items,
        photos=photos,
        scheduled_at=scheduled_at,
        base_price=est["base_price"],
        item_total=est["items_subtotal"],
        service_fee=est["service_fee"],
        surge_multiplier=est["surge_multiplier"],
        total_price=total_amount,
        promo_code_id=promo_code_id,
        discount_amount=discount_amount,
        notes=data.get("itemDescription") or data.get("description", ""),
    )
    sqlalchemy_db.session.add(job)

    payment = Payment(
        id=generate_uuid(),
        job_id=job.id,
        amount=total_amount,
        service_fee=est["service_fee"],
        payment_status="pending",
    )
    sqlalchemy_db.session.add(payment)

    _notify_nearby_contractors(job)
    sqlalchemy_db.session.commit()

    # Send confirmation email and SMS
    from notifications import send_booking_confirmation_email, send_booking_sms
    date_str = selected_date[:10] if selected_date and isinstance(selected_date, str) else "TBD"
    if email:
        send_booking_confirmation_email(
            to_email=email,
            customer_name=name,
            booking_id=job.id,
            address=address,
            scheduled_date=date_str,
            scheduled_time=selected_time,
            total_amount=total_amount,
        )
    if phone:
        send_booking_sms(phone, job.id, date_str, address)

    # --- Mark abandoned booking as converted ---
    try:
        from models import AbandonedBooking
        if email:
            abandoned = AbandonedBooking.query.filter_by(
                email=email.strip().lower(), converted=False
            ).first()
            if abandoned:
                abandoned.converted = True
                sqlalchemy_db.session.commit()
    except Exception:
        pass

    # --- SMS operator about new booking ---
    try:
        from sms_service import send_sms_async
        operator_phone = os.environ.get("OPERATOR_PHONE", "")
        if operator_phone:
            items_count = sum(i.get("quantity", 1) for i in items if isinstance(i, dict))
            lead_source = data.get("leadSource") or data.get("lead_source") or "direct"
            msg = (
                "NEW BOOKING!\n"
                "{} - {} item{}\n"
                "${:.0f} | {}\n"
                "Scheduled: {}"
            ).format(
                address or "No address",
                items_count, "s" if items_count != 1 else "",
                total_amount,
                lead_source,
                date_str,
            )
            send_sms_async(operator_phone, msg)
    except Exception:
        pass

    return jsonify({
        "success": True,
        "bookingId": job.id,
        "job": job.to_dict(),
    }), 201


# Serve uploaded files
@app.route("/uploads/<filename>")
def serve_uploaded_file(filename):
    """Serve uploaded files"""
    from flask import send_from_directory
    import os
    upload_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
    return send_from_directory(upload_folder, filename)


# ---------------------------------------------------------------------------
# Global JSON error handlers
# ---------------------------------------------------------------------------
@app.errorhandler(400)
def bad_request(e):
    return jsonify(error="Bad request"), 400


@app.errorhandler(404)
def not_found(e):
    return jsonify(error="Not found"), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify(error="Method not allowed"), 405


@app.errorhandler(500)
def internal_error(e):
    return jsonify(error="Internal server error"), 500


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    # Debug only with explicit FLASK_ENV=development|dev — never by default.
    debug = _is_development
    socketio.run(app, debug=debug, host="0.0.0.0", port=port)
