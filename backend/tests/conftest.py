"""
Pytest fixtures for Umuve backend E2E tests.

Sets up an in-memory SQLite database and provides a test client
that can be used to exercise API endpoints without side effects.
"""

import os
import sys

# ---------------------------------------------------------------------------
# Environment setup -- MUST happen before any application code is imported
# so that server.py picks up these values instead of production defaults.
# ---------------------------------------------------------------------------
os.environ["FLASK_ENV"] = "development"
os.environ["DATABASE_URL"] = ""  # Force SQLite fallback
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-jwt-secret-do-not-use-in-production"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["API_KEY"] = "test-api-key"
os.environ["DATABASE_PATH"] = ":memory:"
os.environ["ENABLE_SCHEDULER"] = ""  # Disable background scheduler

# Ensure the backend directory is on sys.path so that all modules resolve.
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

import pytest
from models import db as _db


@pytest.fixture(scope="session")
def app():
    """Create the Flask application for the entire test session.

    Uses an in-memory SQLite database so tests are fast and isolated from
    any real database.
    """
    from server import app as flask_app

    flask_app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SERVER_NAME": None,
        # Disable rate limiting in tests
        "RATELIMIT_ENABLED": False,
    })

    # Disable rate limiter for tests
    from extensions import limiter
    limiter.enabled = False

    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.drop_all()


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
