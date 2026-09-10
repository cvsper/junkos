"""
Pytest fixtures for the Umuve backend test suite.

Every test in this suite runs against a per-session scratch SQLite FILE that
lives in pytest's tmp directory and is thrown away afterwards.

Why this file is so careful (audit finding F25)
-----------------------------------------------
The fixtures used to set ``SQLALCHEMY_DATABASE_URI`` as an environment
variable, which server.py ignored, and then rewrote ``app.config`` *after*
Flask-SQLAlchemy had already bound its engine. Rewriting the config dictionary
does not rebind the engine, so the suite silently connected to
``backend/instance/umuve.db`` — the local development database — and the
session-scoped ``drop_all`` at teardown deleted every table in it.

Two changes make that impossible now:

1. The database URL and ``UMUVE_SKIP_STARTUP`` are exported into the
   environment BEFORE ``server`` is imported, and server.py honours both at
   import time (it reads SQLALCHEMY_DATABASE_URI before ``init_app``).
2. ``_assert_disposable()`` reads the URL off the *bound engine* and refuses to
   run a single destructive statement unless it is the scratch file this
   session created. A misconfiguration now fails the run instead of deleting
   somebody's data.
"""

import os
import sys
import tempfile
import uuid

import pytest

# ---------------------------------------------------------------------------
# Scratch database -- MUST be chosen before any application code is imported
# ---------------------------------------------------------------------------
# pytest's tmp_path_factory is only available inside a fixture, and server.py
# is imported at fixture time, so the path is built here with the same
# semantics: a unique directory under the system temp root, per session.
_SCRATCH_DIR = tempfile.mkdtemp(prefix="umuve-tests-")
_SCRATCH_DB = os.path.join(_SCRATCH_DIR, "test-{}.db".format(uuid.uuid4().hex[:8]))
_SCRATCH_URI = "sqlite:///{}".format(_SCRATCH_DB)

# ---------------------------------------------------------------------------
# Environment setup -- MUST happen before any application code is imported
# so that server.py picks up these values instead of production defaults.
# ---------------------------------------------------------------------------
os.environ["FLASK_ENV"] = "development"
os.environ["DATABASE_URL"] = ""              # never inherit a real database
os.environ["SQLALCHEMY_DATABASE_URI"] = _SCRATCH_URI
os.environ["JWT_SECRET"] = "test-jwt-secret-do-not-use-in-production"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["API_KEY"] = "test-api-key"
os.environ["DATABASE_PATH"] = os.path.join(_SCRATCH_DIR, "legacy.db")
os.environ["ENABLE_SCHEDULER"] = ""          # Disable background scheduler
# No create_all / migrations / admin bootstrap / seeding / scheduler on import.
os.environ["UMUVE_SKIP_STARTUP"] = "1"

# Ensure the backend directory is on sys.path so that all modules resolve.
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from models import db as _db  # noqa: E402  (import after env setup, by design)


# ---------------------------------------------------------------------------
# Destructive-operation guard
# ---------------------------------------------------------------------------
def _bound_url():
    """The URL of the engine SQLAlchemy actually bound (not app.config)."""
    return str(_db.engine.url)


def _assert_disposable():
    """Refuse to run destructive statements against anything but the scratch DB.

    Called before every drop_all / delete sweep. Compares against the engine's
    own URL, because that is the thing that decides where the DELETE lands —
    app.config can disagree with it and historically did.
    """
    url = _bound_url()
    if url != _SCRATCH_URI:
        pytest.exit(
            "\n"
            "=========================================================\n"
            " REFUSING TO RUN: tests are bound to the wrong database.\n"
            "=========================================================\n"
            "  bound engine : {}\n"
            "  expected     : {}\n"
            "\n"
            "The suite drops and truncates tables, so it only ever runs\n"
            "against the per-session scratch file above. Something set\n"
            "SQLALCHEMY_DATABASE_URI/DATABASE_URL after conftest, or the\n"
            "app bound its engine before this configuration was applied.\n"
            "No tables were touched.\n".format(url, _SCRATCH_URI),
            returncode=3,
        )


@pytest.fixture(scope="session")
def scratch_db_uri():
    """The scratch SQLite URL this session is pinned to (for assertions)."""
    return _SCRATCH_URI


@pytest.fixture(scope="session")
def app(tmp_path_factory):
    """Create the Flask application for the entire test session.

    Bound to a scratch SQLite file created for this session only; the file and
    its directory are removed when the session ends.
    """
    from server import app as flask_app

    flask_app.config.update({
        "TESTING": True,
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SERVER_NAME": None,
        # Disable rate limiting in tests
        "RATELIMIT_ENABLED": False,
    })

    # Disable rate limiter for tests
    from extensions import limiter
    limiter.enabled = False

    with flask_app.app_context():
        # The engine is bound now -- verify it before creating anything.
        _assert_disposable()
        _db.create_all()
        # server.py no longer runs migrations on import, so apply the
        # raw-SQL migrations (tables/columns that create_all does not know
        # about) to the scratch database here.
        try:
            from migrate import run_migrations
            run_migrations(_SCRATCH_URI)
        except Exception as exc:  # pragma: no cover - diagnostics only
            print("conftest: scratch-db migrations skipped: {}".format(exc))

        yield flask_app

        _assert_disposable()
        _db.session.remove()
        _db.drop_all()

    import shutil
    shutil.rmtree(_SCRATCH_DIR, ignore_errors=True)


@pytest.fixture(scope="function")
def db_session(app):
    """Provide a clean database session for each test.

    Rolls back after every test so each test starts with a clean slate.
    """
    with app.app_context():
        _db.create_all()
        yield _db.session
        _db.session.rollback()
        # Clean all tables between tests
        _assert_disposable()
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()


@pytest.fixture(scope="function")
def client(app, db_session):
    """Flask test client with a clean database for each test."""
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture(scope="function")
def auth_headers(client):
    """Create a test user and return Authorization headers with a valid JWT.

    The user is created via the signup endpoint so the full auth flow is
    exercised.  Returns a dict suitable for passing to client.get(..., headers=...).
    """
    signup_payload = {
        "email": "testuser@example.com",
        "password": "TestPassword123!",
        "name": "Test User",
    }
    resp = client.post("/api/auth/signup", json=signup_payload)
    data = resp.get_json()
    token = data.get("token", "")
    user = data.get("user", {})
    return {
        "Authorization": f"Bearer {token}",
        "_user": user,
        "_token": token,
    }
