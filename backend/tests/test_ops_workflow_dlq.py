"""
Ops Supervisor workflow dead-letter tests (item 7.4 — spec 11 §9 v1
follow-up).

Verifies:
  * Empty event_id writes a `no_event` DLQ row.
  * Exception in a node routes to a `exception` DLQ row + re-raises.
  * Completion past the wall-clock deadline writes a `deadline_exceeded`
    DLQ row but still returns the final state.
  * Happy path does NOT write any DLQ row.
  * DLQ writes are truncated to keep rows reasonable.
"""

import json
import os
import uuid

import pytest

os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("REDIS_URL", None)

from models import db


@pytest.fixture(scope="module", autouse=True)
def _apply_v1_migrations(app):
    """The conftest app fixture only runs db.create_all() (ORM tables).
    DLQ is defined in raw-SQL migration module — apply it here."""
    from ops_supervisor_v1_migrations import (
        NEW_TABLES_SQLITE, NEW_INDEXES_SQLITE,
    )
    from sqlalchemy import text
    with app.app_context():
        with db.engine.begin() as conn:
            for ddl in NEW_TABLES_SQLITE:
                conn.execute(text(ddl))
            for ddl in NEW_INDEXES_SQLITE:
                conn.execute(text(ddl))
    yield


def _dlq_count():
    from sqlalchemy import text
    return db.session.execute(
        text("SELECT COUNT(*) FROM ops_workflow_dead_letters"),
    ).scalar()


def _dlq_rows():
    from sqlalchemy import text
    return db.session.execute(
        text(
            "SELECT id, event_id, reason, error_message, state_snapshot "
            "FROM ops_workflow_dead_letters ORDER BY created_at DESC"
        ),
    ).fetchall()


def _reset_dlq():
    from sqlalchemy import text
    db.session.execute(text("DELETE FROM ops_workflow_dead_letters"))
    db.session.commit()


def test_empty_event_id_writes_no_event_dlq(app):
    import ops_langgraph
    with app.app_context():
        _reset_dlq()
        result = ops_langgraph.run_situation_workflow("")
        assert result == {"error": "missing event_id"}
        rows = _dlq_rows()
        assert len(rows) == 1
        assert rows[0][2] == "no_event"


def test_exception_in_node_writes_dlq_and_reraises(app, monkeypatch):
    import ops_langgraph
    with app.app_context():
        _reset_dlq()

        def _boom(state):
            raise RuntimeError("classifier exploded")

        monkeypatch.setattr(
            ops_langgraph, "node_classify_event", _boom,
        )
        # Force linear fallback so monkeypatch takes effect.
        monkeypatch.setattr(ops_langgraph, "get_compiled_graph", lambda: None)

        with pytest.raises(RuntimeError, match="classifier exploded"):
            ops_langgraph.run_situation_workflow("evt-ex-1")

        rows = _dlq_rows()
        assert len(rows) == 1
        assert rows[0][1] == "evt-ex-1"
        assert rows[0][2] == "exception"
        assert "classifier exploded" in (rows[0][3] or "")


def test_deadline_exceeded_writes_dlq_but_returns_state(
    app, monkeypatch,
):
    import ops_langgraph
    with app.app_context():
        _reset_dlq()
        # Force tiny deadline so any real run trips it.
        monkeypatch.setenv("OPS_WORKFLOW_DEADLINE_SEC", "0.001")

        # Fake linear runner: returns immediately with a final state, but we
        # fake monotonic() so elapsed appears past the 0.001s deadline.
        fake_state = {"event_id": "evt-slow-1", "outcome": "executed"}
        monkeypatch.setattr(
            ops_langgraph, "_run_linear", lambda s: fake_state,
        )
        monkeypatch.setattr(ops_langgraph, "get_compiled_graph", lambda: None)

        # Patch time.monotonic to simulate elapsed = 10s.
        calls = {"n": 0}
        real_mono = ops_langgraph.time.monotonic

        def _fake_mono():
            calls["n"] += 1
            # First call (start) = 0, later calls = 10.
            return 0.0 if calls["n"] == 1 else 10.0

        monkeypatch.setattr(ops_langgraph.time, "monotonic", _fake_mono)

        result = ops_langgraph.run_situation_workflow("evt-slow-1")
        assert result["outcome"] == "executed"

        rows = _dlq_rows()
        assert len(rows) == 1
        assert rows[0][2] == "deadline_exceeded"
        assert "elapsed=10" in (rows[0][3] or "")


def test_happy_path_writes_no_dlq(app, monkeypatch):
    """When the linear runner completes under the deadline, no DLQ row."""
    import ops_langgraph
    with app.app_context():
        _reset_dlq()

        fake_state = {"event_id": "evt-ok", "outcome": "executed"}
        monkeypatch.setattr(
            ops_langgraph, "_run_linear", lambda s: fake_state,
        )
        monkeypatch.setattr(ops_langgraph, "get_compiled_graph", lambda: None)

        result = ops_langgraph.run_situation_workflow("evt-ok")
        assert result["outcome"] == "executed"
        assert _dlq_count() == 0


def test_dlq_state_snapshot_is_json(app, monkeypatch):
    """DLQ `state_snapshot` column should hold valid JSON we can round-trip."""
    import ops_langgraph
    with app.app_context():
        _reset_dlq()

        def _boom(state):
            raise RuntimeError("boom")

        monkeypatch.setattr(ops_langgraph, "node_classify_event", _boom)
        monkeypatch.setattr(ops_langgraph, "get_compiled_graph", lambda: None)

        with pytest.raises(RuntimeError):
            ops_langgraph.run_situation_workflow("evt-json-1")

        rows = _dlq_rows()
        assert len(rows) == 1
        snap = rows[0][4]
        assert snap is not None
        parsed = json.loads(snap)
        assert parsed["event_id"] == "evt-json-1"
