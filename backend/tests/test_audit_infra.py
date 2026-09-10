"""Regression tests for the platform/infra audit findings.

F04  the committed database credential is gone and cannot come back quietly
F25  the suite can only ever run against a disposable scratch database
F26  /api/ready reports transaction readiness and 503s when it cannot transact
F27  each device token is pushed with its own app's APNs topic
"""

import os
import re

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# F04 -- committed credential
# ---------------------------------------------------------------------------
class TestNoCommittedCredential:
    def test_delete_via_sql_has_no_embedded_connection_string(self):
        """The script must read DATABASE_URL, never carry a fallback literal."""
        path = os.path.join(BACKEND_DIR, "delete_via_sql.py")
        source = open(path).read()

        # A real connection string has credentials in it: scheme://user:pass@host
        candidates = re.findall(
            r"postgres(?:ql)?://([^\s\"':/]+):([^\s\"'@]+)@([^\s\"'/]+)", source
        )
        # ALL-CAPS / <bracketed> segments are documentation placeholders
        # (the docstring shows the expected shape), not credentials.

        def _is_placeholder(part):
            return part.isupper() or (part.startswith("<") and part.endswith(">"))

        real = [
            m for m in candidates
            if not (_is_placeholder(m[0]) and _is_placeholder(m[1]))
        ]
        assert real == [], (
            "delete_via_sql.py contains an embedded connection string with "
            "credentials. It must read DATABASE_URL from the environment."
        )

        # And it must refuse to run unconfigured rather than defaulting.
        assert "os.environ.get(\"DATABASE_URL\"" in source
        assert "sys.exit(" in source

    def test_no_render_host_literal_remains(self):
        path = os.path.join(BACKEND_DIR, "delete_via_sql.py")
        source = open(path).read()
        assert "oregon-postgres.render.com" not in source
        assert "dpg-" not in source


# ---------------------------------------------------------------------------
# F25 -- the test suite cannot touch a real database
# ---------------------------------------------------------------------------
class TestScratchDatabaseGuard:
    def test_bound_engine_is_the_session_scratch_file(self, app, scratch_db_uri):
        """The engine SQLAlchemy actually bound must be the scratch file.

        app.config agreeing is not enough -- that is exactly the bug (the old
        fixtures rewrote config after the engine was already bound to
        backend/instance/umuve.db and then dropped its tables).
        """
        from models import db

        with app.app_context():
            bound = str(db.engine.url)

        assert bound == scratch_db_uri
        assert bound.startswith("sqlite:///")
        # A scratch file, not a repo-relative dev database.
        assert "umuve-tests-" in bound
        assert not bound.endswith("instance/umuve.db")
        assert not bound.endswith("/umuve.db")

    def test_guard_refuses_a_non_scratch_database(self, monkeypatch):
        """_assert_disposable must abort the run rather than delete data."""
        import sys

        # pytest imports the suite conftest under a package-qualified name.
        suite_conftest = sys.modules.get("tests.conftest") or sys.modules.get("conftest")
        assert suite_conftest is not None, "suite conftest module not importable"

        # Deliberately not credential-shaped: this file is scanned by the
        # blocking secret-scan workflow, and the guard only cares that the URL
        # is not the scratch file.
        not_the_scratch_db = "postgresql://prod-db.example.com/umuve"
        monkeypatch.setattr(suite_conftest, "_bound_url", lambda: not_the_scratch_db)

        with pytest.raises(BaseException) as excinfo:
            suite_conftest._assert_disposable()

        # pytest.exit raises pytest.exit.Exception (a BaseException).
        message = str(excinfo.value)
        assert "REFUSING TO RUN" in message
        assert "prod-db.example.com" in message

    def test_startup_side_effects_are_skipped_under_test(self):
        """server.py must not create schema / start the scheduler on import."""
        import server

        assert server._skip_startup is True
        assert server._scheduler is None
        assert server.app.config.get("TESTING") is True


# ---------------------------------------------------------------------------
# F26 -- readiness
# ---------------------------------------------------------------------------
class TestReadinessEndpoint:
    def test_ready_returns_200_when_dependencies_are_healthy(self, client):
        resp = client.get("/api/ready")
        assert resp.status_code == 200

        body = resp.get_json()
        assert body["ready"] is True
        assert body["blocking"] == []
        assert body["checks"]["database"]["ok"] is True
        assert body["checks"]["database"]["schema"] is True
        # every dependency is reported, even the soft ones
        for key in ("database", "payments", "webhooks", "storage", "scheduler"):
            assert key in body["checks"]

    def test_ready_returns_503_when_the_database_check_fails(self, client, monkeypatch):
        import server

        monkeypatch.setattr(
            server, "_check_database",
            lambda: {"ok": False, "connected": False, "schema": False,
                     "engine": "postgresql", "error": "connection refused"},
        )

        resp = client.get("/api/ready")
        assert resp.status_code == 503

        body = resp.get_json()
        assert body["ready"] is False
        assert "database" in body["blocking"]

    def test_ready_503s_when_stripe_is_missing_in_production(self, client, monkeypatch):
        """Money must be able to move before an instance takes traffic."""
        import server

        monkeypatch.setattr(server, "is_production", lambda: True)
        monkeypatch.setattr(
            server, "_check_payments",
            lambda: {"ok": False, "status": "missing_stripe_key"},
        )

        resp = client.get("/api/ready")
        assert resp.status_code == 503
        assert "payments" in resp.get_json()["blocking"]

    def test_missing_webhook_guard_is_unknown_not_fatal(self, client):
        """webhook_guard is still being built -- absence must not 503."""
        body = client.get("/api/ready").get_json()
        webhooks = body["checks"]["webhooks"]
        assert webhooks["status"] in ("unknown", "configured", "missing")
        assert "webhooks" not in body["blocking"]

    def test_health_stays_shallow_but_reports_readiness(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200

        body = resp.get_json()
        assert body["status"] == "healthy"
        assert isinstance(body["ready"], bool)
        assert body["version"]

    def test_health_is_200_even_when_not_ready(self, client, monkeypatch):
        """Liveness must not fail just because a dependency is down."""
        import server

        monkeypatch.setattr(
            server, "_check_database",
            lambda: {"ok": False, "connected": False, "schema": False,
                     "engine": None, "error": "down"},
        )

        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.get_json()["ready"] is False


# ---------------------------------------------------------------------------
# F27 -- per-app push topics
# ---------------------------------------------------------------------------
class TestPushTopicSelection:
    def test_topic_is_selected_per_app(self, monkeypatch):
        import push_notifications as pn

        monkeypatch.delenv("APNS_BUNDLE_ID_CUSTOMER", raising=False)
        monkeypatch.delenv("APNS_BUNDLE_ID_DRIVER", raising=False)

        assert pn.topic_for_app("customer") == "com.goumuve.app"
        assert pn.topic_for_app("driver") == "com.goumuve.pro"
        # The two apps must never collapse onto one topic.
        assert pn.topic_for_app("customer") != pn.topic_for_app("driver")

    def test_topic_env_overrides_are_honoured(self, monkeypatch):
        import push_notifications as pn

        monkeypatch.setenv("APNS_BUNDLE_ID_CUSTOMER", "com.example.customer")
        monkeypatch.setenv("APNS_BUNDLE_ID_DRIVER", "com.example.driver")

        assert pn.topic_for_app("customer") == "com.example.customer"
        assert pn.topic_for_app("driver") == "com.example.driver"

    def test_unknown_app_falls_back_to_driver(self, monkeypatch):
        import push_notifications as pn

        monkeypatch.delenv("APNS_BUNDLE_ID_DRIVER", raising=False)
        assert pn.topic_for_app(None) == "com.goumuve.pro"
        assert pn.topic_for_app("nonsense") == "com.goumuve.pro"

    def test_gateway_is_selected_per_token_environment(self, monkeypatch):
        import push_notifications as pn

        monkeypatch.setenv("FLASK_ENV", "production")
        # The token's own environment wins over the server's.
        assert pn._base_url_for("sandbox") == pn.APNS_SANDBOX_URL
        assert pn._base_url_for("production") == pn.APNS_PRODUCTION_URL

    def test_send_uses_the_topic_for_the_devices_app(self, app, db_session, monkeypatch):
        """The APNs request must carry the bundle id of the sending app."""
        import push_notifications as pn

        monkeypatch.setattr(pn, "APNS_KEY_ID", "KEY1234567")
        monkeypatch.setattr(pn, "APNS_TEAM_ID", "TEAM123456")
        monkeypatch.setattr(pn, "APNS_AUTH_KEY_PATH", "/tmp/fake.p8")
        monkeypatch.setattr(pn, "_get_bearer_token", lambda: "fake-bearer")
        monkeypatch.delenv("APNS_BUNDLE_ID_CUSTOMER", raising=False)
        monkeypatch.delenv("APNS_BUNDLE_ID_DRIVER", raising=False)

        captured = []

        class _Resp:
            status_code = 200

            def json(self):
                return {}

        class _Client:
            def post(self, url, json=None, headers=None):
                captured.append({"url": url, "headers": headers})
                return _Resp()

        monkeypatch.setattr(pn, "_get_client", lambda: _Client())

        assert pn.send_push_to_token(
            "tok-customer", "t", "b", app_name="customer",
            environment="production", record=False,
        )
        assert pn.send_push_to_token(
            "tok-driver", "t", "b", app_name="driver",
            environment="sandbox", record=False,
        )

        assert captured[0]["headers"]["apns-topic"] == "com.goumuve.app"
        assert captured[0]["url"].startswith(pn.APNS_PRODUCTION_URL)
        assert captured[1]["headers"]["apns-topic"] == "com.goumuve.pro"
        assert captured[1]["url"].startswith(pn.APNS_SANDBOX_URL)

    def test_gone_response_deactivates_the_token(self, app, db_session, monkeypatch):
        """410 / BadDeviceToken must retire the token, not delete the history."""
        import push_notifications as pn
        from models import DeviceToken, User

        user = User(email="push-f27@example.com", name="Push F27", role="customer")
        db_session.add(user)
        db_session.commit()

        dt = DeviceToken(
            user_id=user.id, token="dead-token-1", platform="ios",
            app="driver", environment="production", active=True,
        )
        db_session.add(dt)
        db_session.commit()

        monkeypatch.setattr(pn, "APNS_KEY_ID", "KEY1234567")
        monkeypatch.setattr(pn, "APNS_TEAM_ID", "TEAM123456")
        monkeypatch.setattr(pn, "APNS_AUTH_KEY_PATH", "/tmp/fake.p8")
        monkeypatch.setattr(pn, "_get_bearer_token", lambda: "fake-bearer")

        class _Resp:
            status_code = 410

            def json(self):
                return {"reason": "BadDeviceToken"}

        class _Client:
            def post(self, url, json=None, headers=None):
                return _Resp()

        monkeypatch.setattr(pn, "_get_client", lambda: _Client())

        assert pn.send_push_to_token(
            "dead-token-1", "t", "b", app_name="driver",
            environment="production", record=False,
        ) is False

        refreshed = DeviceToken.query.filter_by(token="dead-token-1").first()
        assert refreshed is not None, "token row must survive for the ledger"
        assert refreshed.active is False
        assert refreshed.deactivated_at is not None


class TestPushRegistration:
    def _signup(self, client, email):
        resp = client.post("/api/auth/signup", json={
            "email": email, "password": "TestPassword123!", "name": "Push User",
        })
        return {"Authorization": "Bearer {}".format(resp.get_json().get("token", ""))}

    def test_registration_records_app_and_environment(self, client, db_session):
        headers = self._signup(client, "push-reg@example.com")

        resp = client.post("/api/push/register-token", json={
            "token": "abc123token", "platform": "ios",
            "app_type": "customer", "environment": "sandbox",
        }, headers=headers)

        assert resp.status_code == 200
        device = resp.get_json()["device_token"]
        assert device["app"] == "customer"
        assert device["environment"] == "sandbox"

    def test_driver_client_camelcase_key_is_accepted(self, client, db_session):
        """Umuve Pro sends {"appType": "driver"}."""
        headers = self._signup(client, "push-reg2@example.com")

        resp = client.post("/api/push/register-token", json={
            "token": "driver-token-1", "platform": "ios", "appType": "driver",
        }, headers=headers)

        assert resp.status_code == 200
        assert resp.get_json()["device_token"]["app"] == "driver"

    def test_missing_app_defaults_to_driver(self, client, db_session):
        """Existing clients that send nothing keep working as the driver app."""
        headers = self._signup(client, "push-reg3@example.com")

        resp = client.post("/api/push/register-token", json={
            "token": "legacy-token-1", "platform": "ios",
        }, headers=headers)

        assert resp.status_code == 200
        body = resp.get_json()["device_token"]
        assert body["app"] == "driver"
        assert body["environment"] == "production"

    def test_invalid_app_is_rejected(self, client, db_session):
        headers = self._signup(client, "push-reg4@example.com")

        resp = client.post("/api/push/register-token", json={
            "token": "bad-app-token", "platform": "ios", "app": "banana",
        }, headers=headers)

        assert resp.status_code == 400


def test_readiness_webhooks_reads_the_flat_secret_map():
    """webhook_guard returns {name: bool}; the readiness shim keyed off a
    "ready" key that shape never has, so webhooks read "missing" in production
    even with every secret configured."""
    from unittest import mock
    import server

    with mock.patch("webhook_guard.webhook_secrets_ready",
                    return_value={"twilio": True, "vapi": True, "stripe": True}):
        out = server._check_webhooks()
    assert out["ok"] is True and out["status"] == "configured" and "missing" not in out

    with mock.patch("webhook_guard.webhook_secrets_ready",
                    return_value={"twilio": True, "vapi": False, "meta_leads": False}):
        out = server._check_webhooks()
    assert out["ok"] is False and out["missing"] == ["meta_leads", "vapi"]

    # the richer {"ready": ...} shape still works
    with mock.patch("webhook_guard.webhook_secrets_ready", return_value={"ready": True}):
        assert server._check_webhooks()["ok"] is True
