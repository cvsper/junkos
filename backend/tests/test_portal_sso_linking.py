"""
Portal SSO identity linking tests (item 7.3 — spec 04 §9.6 v1 follow-up).

Verifies:
  * Identity-first lookup: (provider, subject) hit short-circuits before
    email-domain fallback.
  * Email-domain fallback: on first login, find by domain and upsert the
    identity.
  * Identity survives email rename: second login with a new email claim
    but same `sub` still lands the same user_id/org_id.
  * No-match returns None.
  * Stale identity pointing at a deleted user falls through to email-domain.
  * last_seen_at bumps on repeat login.
"""

import datetime as _dt
import os
import sys
import uuid

import pytest

os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-do-not-use-in-production")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("DATABASE_PATH", ":memory:")

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from models import db, User, Org, OrgMember


@pytest.fixture(scope="function")
def app():
    from flask import Flask

    from routes.portal import portal_bp
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
    flask_app.register_blueprint(portal_sso_bp)

    with flask_app.app_context():
        db.create_all()
        from portal_sso_migrations import apply_sqlalchemy
        apply_sqlalchemy(db.engine)
        yield flask_app
        db.session.remove()
        db.drop_all()


def _make_user(email):
    u = User(
        id=str(uuid.uuid4()),
        email=email.lower(),
        role="customer",
    )
    db.session.add(u)
    db.session.flush()
    return u


def _make_org(name, sso_domain):
    o = Org(
        id=str(uuid.uuid4()),
        name=name,
        slug=name.lower().replace(" ", "-"),
        billing_email="billing@{}".format(sso_domain),
        tier="pro",
        sso_domain=sso_domain,
    )
    db.session.add(o)
    db.session.flush()
    return o


def _join(user, org, role="owner"):
    m = OrgMember(
        id=str(uuid.uuid4()),
        user_id=user.id,
        org_id=org.id,
        role=role,
        scopes=[],
        joined_at=None,
    )
    db.session.add(m)
    db.session.flush()
    return m


def _count_identities():
    from sqlalchemy import text
    return db.session.execute(
        text("SELECT COUNT(*) FROM sso_identities"),
    ).scalar()


def _fetch_identity(provider, subject):
    from sqlalchemy import text
    row = db.session.execute(
        text(
            "SELECT user_id, email, last_seen_at FROM sso_identities "
            "WHERE provider = :p AND subject = :s"
        ),
        {"p": provider, "s": subject},
    ).fetchone()
    return row


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_email_domain_fallback_creates_identity(app):
    """First login with no prior identity: match by domain, then upsert."""
    from routes.portal_sso import _link_member

    with app.app_context():
        user = _make_user("bob@acme.com")
        org = _make_org("Acme", "acme.com")
        _join(user, org, role="owner")

        assert _count_identities() == 0

        result = _link_member(
            provider="google",
            subject="google-sub-xyz-111",
            email="bob@acme.com",
        )
        assert result is not None
        token, org_id, user_id = result
        assert token  # JWT string
        assert org_id == org.id
        assert user_id == user.id

        # Identity was recorded for next login.
        assert _count_identities() == 1
        ident = _fetch_identity("google", "google-sub-xyz-111")
        assert ident is not None
        assert ident[0] == user.id
        assert ident[1] == "bob@acme.com"


def test_identity_first_short_circuits_email_fallback(app):
    """Second login: (provider, subject) exists, no email-domain lookup needed."""
    from routes.portal_sso import _link_member

    with app.app_context():
        user = _make_user("bob@acme.com")
        org = _make_org("Acme", "acme.com")
        _join(user, org, role="owner")

        # Seed first login.
        _link_member("google", "sub-aaa", "bob@acme.com")
        assert _count_identities() == 1

        # Now wipe org.sso_domain so the email-domain fallback would fail,
        # then log in again — should still succeed via identity lookup.
        org.sso_domain = None
        db.session.commit()

        result = _link_member("google", "sub-aaa", "bob@acme.com")
        assert result is not None
        _, org_id, user_id = result
        assert user_id == user.id
        assert org_id == org.id


def test_identity_survives_email_rename(app):
    """Sub stays stable, email claim changes — still lands same user."""
    from routes.portal_sso import _link_member

    with app.app_context():
        user = _make_user("alice@acme.com")
        org = _make_org("Acme", "acme.com")
        _join(user, org, role="owner")

        # First login — alice@acme.com (creates identity).
        _link_member("google", "sub-rename-1", "alice@acme.com")

        # Entra re-issues with a new email (alice.smith@acme.com) but same sub.
        result = _link_member(
            "google", "sub-rename-1", "alice.smith@acme.com",
        )
        assert result is not None
        _, _, user_id = result
        assert user_id == user.id

        # Identity's email is refreshed.
        ident = _fetch_identity("google", "sub-rename-1")
        assert ident[1] == "alice.smith@acme.com"


def test_no_match_returns_none(app):
    from routes.portal_sso import _link_member

    with app.app_context():
        # No org, no user, no identity.
        result = _link_member("google", "unknown-sub", "stranger@nowhere.com")
        assert result is None


def test_email_without_domain_match_returns_none(app):
    """Domain not in any orgs.sso_domain → no membership."""
    from routes.portal_sso import _link_member

    with app.app_context():
        user = _make_user("bob@acme.com")
        org = _make_org("Acme", "acme.com")
        _join(user, org, role="owner")

        result = _link_member(
            "google", "sub-new", "bob@other-company.com",
        )
        assert result is None
        # No identity recorded on miss.
        assert _count_identities() == 0


def test_stale_identity_pointing_at_deleted_user_falls_through(app):
    """If the identity row points at a user_id that no longer exists, fall
    through to email-domain fallback and re-bind the identity."""
    from routes.portal_sso import _link_member, _upsert_identity

    with app.app_context():
        org = _make_org("Acme", "acme.com")
        real_user = _make_user("bob@acme.com")
        _join(real_user, org, role="owner")

        # Insert a stale identity pointing at a deleted user id.
        _upsert_identity(
            "google", "stale-sub", str(uuid.uuid4()), "ghost@acme.com",
        )
        db.session.commit()

        result = _link_member("google", "stale-sub", "bob@acme.com")
        assert result is not None
        _, _, user_id = result
        assert user_id == real_user.id


def test_last_seen_at_bumps_on_repeat_login(app):
    from routes.portal_sso import _link_member

    with app.app_context():
        user = _make_user("bob@acme.com")
        org = _make_org("Acme", "acme.com")
        _join(user, org, role="owner")

        _link_member("google", "sub-repeat", "bob@acme.com")
        first = _fetch_identity("google", "sub-repeat")
        first_seen = first[2]

        # Sleep-like: directly manipulate the row so the comparison is
        # deterministic without real clock dependency.
        from sqlalchemy import text
        past = _dt.datetime.utcnow() - _dt.timedelta(hours=1)
        db.session.execute(
            text(
                "UPDATE sso_identities SET last_seen_at = :p "
                "WHERE provider='google' AND subject='sub-repeat'"
            ),
            {"p": past},
        )
        db.session.commit()

        _link_member("google", "sub-repeat", "bob@acme.com")
        second = _fetch_identity("google", "sub-repeat")
        second_seen = second[2]

        # Parse both if sqlite returns strings.
        def _as_dt(v):
            if isinstance(v, _dt.datetime):
                return v
            return _dt.datetime.fromisoformat(str(v))

        assert _as_dt(second_seen) > _as_dt(past)


def test_back_compat_link_member_by_email(app):
    """Old internal helper signature still works for any unconverted callers."""
    from routes.portal_sso import _link_member_by_email

    with app.app_context():
        user = _make_user("bob@acme.com")
        org = _make_org("Acme", "acme.com")
        _join(user, org, role="owner")

        result = _link_member_by_email("bob@acme.com")
        assert result is not None
        _, org_id, user_id = result
        assert user_id == user.id
        assert org_id == org.id
