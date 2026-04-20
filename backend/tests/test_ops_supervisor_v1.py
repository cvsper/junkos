"""
Ops Supervisor v1 — unit + integration tests (spec 11 §9).

Coverage surface:
  1. classify_event fallback path when ANTHROPIC_API_KEY is missing.
  2. classify_event happy path with injected fake Anthropic client.
  3. decide() respects guardrails: Claude returns an over-cap credit ->
     decision persists with status='blocked_by_guardrail'.
  4. LangGraph workflow runs end-to-end on a fake truck_late event and
     produces a persisted Situation + AgentDecision + AgentAction chain.
  5. Redis bus degrades to inline workflow run when REDIS_URL is missing.
  6. PagerDuty trigger_incident with mocked HTTP + without routing key.

No real network calls. unittest.mock + simple fake clients.
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

# Ensure env is clean before anything imports the app.
os.environ.setdefault("OPS_SUPERVISOR_SERVICE_TOKEN", "test-supervisor-token")
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("REDIS_URL", None)
os.environ.pop("PAGERDUTY_ROUTING_KEY", None)

from models import db, User, Job  # noqa: E402


SERVICE_TOKEN = "test-supervisor-token"


# ---------------------------------------------------------------------------
# Blueprint + schema bootstrap — mirrors the MVP test file.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def _register_v1_blueprint(app):
    # Register both blueprints so the in-memory DB has all ops tables.
    # Flask raises if the app has already served a request -- guard so that
    # running this file alongside other ops supervisor test files still works.
    from routes.ops_supervisor import ops_supervisor_bp
    from routes.ops_supervisor_v1 import ops_supervisor_v1_bp
    try:
        if "ops_supervisor" not in app.blueprints:
            app.register_blueprint(ops_supervisor_bp)
    except AssertionError:
        pass
    try:
        if "ops_supervisor_v1" not in app.blueprints:
            app.register_blueprint(ops_supervisor_v1_bp)
    except AssertionError:
        pass
    with app.app_context():
        db.create_all()
    yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_customer(phone="+13055550123", name="Alex Diaz"):
    u = User(
        id=str(uuid.uuid4()),
        email="cust-{}@example.com".format(uuid.uuid4().hex[:8]),
        name=name,
        phone=phone,
        role="customer",
    )
    db.session.add(u)
    db.session.flush()
    return u


def _make_job(customer, status="in_progress", scheduled_offset_min=-20,
              lat=25.7617, lng=-80.1918):
    job = Job(
        id=str(uuid.uuid4()),
        customer_id=customer.id,
        status=status,
        address="123 Beach Dr, Miami, FL",
        lat=lat,
        lng=lng,
        scheduled_at=datetime.now(timezone.utc) + timedelta(minutes=scheduled_offset_min),
        total_price=120.0,
    )
    db.session.add(job)
    db.session.commit()
    return job


def _make_event(event_type="booking.late", booking_id=None, payload=None):
    from ops_supervisor_models import OpsEvent
    e = OpsEvent(
        type=event_type,
        booking_id=booking_id,
        payload_json=payload or {},
        source="test",
    )
    db.session.add(e)
    db.session.commit()
    return e


def _svc_headers():
    return {"X-Service-Token": SERVICE_TOKEN}


# ---------------------------------------------------------------------------
# Fake Anthropic client factory — returns the JSON we control
# ---------------------------------------------------------------------------
def _fake_anthropic(reply_text: str):
    """Build a stand-in for ``anthropic.Anthropic`` that always returns
    ``reply_text`` from ``messages.create(...)``.
    """
    content_block = SimpleNamespace(text=reply_text)
    resp = SimpleNamespace(content=[content_block])
    client = MagicMock()
    client.messages.create.return_value = resp
    return client


# ===========================================================================
# 1. classify_event fallback — no ANTHROPIC_API_KEY
# ===========================================================================
def test_classifier_fallback_without_api_key(client, db_session):
    from ops_classifier import classify_event

    cust = _make_customer()
    job = _make_job(cust, status="in_progress", scheduled_offset_min=-25)
    evt = _make_event("booking.late", booking_id=job.id)

    result = classify_event(evt, booking=job)
    assert result.tag == "truck_late", result
    assert result.source in ("fallback_no_key", "fallback_rules"), result.source
    assert 0.0 <= result.confidence <= 1.0
    assert evt.classifier_tag == "truck_late"
    assert evt.classifier_confidence == result.confidence


# ===========================================================================
# 2. classify_event happy path with fake Claude client
# ===========================================================================
def test_classifier_with_fake_claude_client(db_session):
    from ops_classifier import classify_event

    cust = _make_customer()
    job = _make_job(cust)
    evt = _make_event("customer.chat.complaint", booking_id=job.id,
                      payload={"text": "Your driver was rude!"})

    fake = _fake_anthropic(json.dumps({
        "tag": "complaint",
        "confidence": 0.82,
        "suggested_severity": "medium",
    }))

    # Temporarily set api_key so the module doesn't short-circuit.
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
        result = classify_event(evt, booking=job, client=fake)

    assert result.tag == "complaint"
    assert result.confidence == pytest.approx(0.82)
    assert result.suggested_severity == "medium"
    assert result.source == "claude"
    fake.messages.create.assert_called_once()


# ===========================================================================
# 3. Decision agent respects guardrail — over-cap credit is blocked
# ===========================================================================
def test_decision_agent_blocks_over_cap_credit(db_session):
    from ops_decision_agent import decide
    from ops_supervisor_models import Situation

    cust = _make_customer()
    job = _make_job(cust, status="in_progress", scheduled_offset_min=-30)

    sit = Situation(
        booking_id=job.id,
        tag="truck_late",
        severity="high",
        context_snapshot_json={"booking": {"id": job.id}},
    )
    db.session.add(sit)
    db.session.commit()

    # Fake Claude: propose $250 credit (way over the $100 cap).
    fake = _fake_anthropic(json.dumps({
        "tool": "issue_credit",
        "args": {"amount_cents": 25000},
        "rationale": "Let's aggressively apologize",
        "confidence": 0.92,
    }))

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
        guarded = decide(sit, booking=job, client=fake)

    assert guarded.output.tool == "issue_credit"
    assert guarded.output.args.get("amount_cents") == 25000
    assert guarded.guardrail.ok is False
    assert "cap" in (guarded.guardrail.reason or "").lower()
    assert guarded.decision.status == "blocked_by_guardrail"

    # Guardrail reason persisted inside decision_json for audit.
    dj = guarded.decision.decision_json or {}
    assert dj.get("guardrail", {}).get("code") == "credit_cap_exceeded"


def test_decision_agent_fallback_without_api_key(db_session):
    """With no API key and no client, decide() uses the template fallback."""
    from ops_decision_agent import decide
    from ops_supervisor_models import Situation

    cust = _make_customer()
    job = _make_job(cust, status="in_progress", scheduled_offset_min=-30)

    sit = Situation(
        booking_id=job.id,
        tag="truck_late",
        severity="medium",
        context_snapshot_json={"booking": {"id": job.id}},
    )
    db.session.add(sit)
    db.session.commit()

    guarded = decide(sit, booking=job)
    assert guarded.output.model == "fallback-templates"
    assert guarded.output.tool == "issue_credit"
    assert guarded.guardrail.ok is True
    assert guarded.decision.status in ("pending", "executed")


# ===========================================================================
# 4. LangGraph workflow end-to-end on a fake truck_late event
# ===========================================================================
def test_langgraph_workflow_truck_late_end_to_end(db_session):
    from ops_langgraph import run_situation_workflow
    from ops_supervisor_models import (
        Situation, AgentDecision, AgentAction,
    )

    cust = _make_customer(phone="+13055551234")
    job = _make_job(cust, status="in_progress", scheduled_offset_min=-22)
    evt = _make_event("booking.late", booking_id=job.id)

    # Patch sms_service so no Twilio call goes out.
    with patch("routes.ops_supervisor.sms_service.send_sms",
               return_value="SM_lg_test"):
        state = run_situation_workflow(evt.id)

    assert state.get("event_id") == evt.id
    # Classifier + situation produced.
    sits = db.session.query(Situation).filter_by(booking_id=job.id).all()
    assert len(sits) >= 1
    decisions = db.session.query(AgentDecision).filter_by(
        situation_id=sits[0].id).all()
    assert len(decisions) >= 1
    actions = db.session.query(AgentAction).filter_by(
        decision_id=decisions[0].id).all()
    assert len(actions) >= 1

    # Tag persisted on event.
    db.session.refresh(evt)
    assert evt.classifier_tag == "truck_late"


# ===========================================================================
# 5. Redis bus degrades to inline when REDIS_URL is missing
# ===========================================================================
def test_bus_publish_inline_without_redis(db_session):
    import ops_event_bus

    cust = _make_customer()
    job = _make_job(cust, status="in_progress", scheduled_offset_min=-22)
    evt = _make_event("booking.late", booking_id=job.id)

    # Ensure no cached Redis client.
    ops_event_bus._redis_client = None

    called_with = {}

    def fake_handler(eid):
        called_with["eid"] = eid

    # No REDIS_URL env var -> publish runs handler inline.
    assert "REDIS_URL" not in os.environ or not os.environ["REDIS_URL"]
    ref = ops_event_bus.publish(evt, inline_handler=fake_handler)
    assert ref.startswith("inline:")
    assert called_with.get("eid") == evt.id


def test_bus_consume_without_redis_raises(db_session):
    import ops_event_bus

    ops_event_bus._redis_client = None
    os.environ.pop("REDIS_URL", None)
    with pytest.raises(RuntimeError):
        ops_event_bus.consume(lambda eid: None, max_iterations=1)


def test_bus_publish_with_fake_redis_client(db_session):
    import ops_event_bus

    cust = _make_customer()
    job = _make_job(cust)
    evt = _make_event("booking.late", booking_id=job.id)

    fake_redis = MagicMock()
    fake_redis.xadd.return_value = "1700000000-0"

    ref = ops_event_bus.publish(evt, client=fake_redis)
    assert ref == "1700000000-0"
    fake_redis.xadd.assert_called_once()
    # Envelope contains the event_id.
    args, kwargs = fake_redis.xadd.call_args
    stream_name = args[0]
    payload_fields = args[1]
    assert stream_name == ops_event_bus.STREAM_NAME
    envelope = json.loads(payload_fields["payload"])
    assert envelope["event_id"] == evt.id


# ===========================================================================
# 6. PagerDuty — trigger with mock HTTP + fallback without routing key
# ===========================================================================
def test_pagerduty_trigger_without_routing_key_returns_sentinel(db_session):
    from ops_supervisor_models import Situation, EscalationTicket
    from ops_pagerduty import trigger_incident

    cust = _make_customer()
    job = _make_job(cust)
    sit = Situation(booking_id=job.id, tag="truck_late", severity="high")
    db.session.add(sit)
    db.session.flush()
    ticket = EscalationTicket(
        situation_id=sit.id,
        priority="p1",
        summary_md="test",
        assignee="ops-on-call",
    )
    db.session.add(ticket)
    db.session.commit()

    os.environ.pop("PAGERDUTY_ROUTING_KEY", None)
    incident_id = trigger_incident(ticket)
    assert incident_id.startswith("pd_missing_key_")
    assert ticket.pagerduty_incident == incident_id


def test_pagerduty_trigger_with_mocked_http(db_session):
    from ops_supervisor_models import Situation, EscalationTicket
    from ops_pagerduty import trigger_incident, PAGERDUTY_ENQUEUE_URL

    cust = _make_customer()
    job = _make_job(cust)
    sit = Situation(booking_id=job.id, tag="truck_late", severity="high")
    db.session.add(sit)
    db.session.flush()
    ticket = EscalationTicket(
        situation_id=sit.id,
        priority="p0",
        summary_md="test summary",
        assignee="ops-on-call",
    )
    db.session.add(ticket)
    db.session.commit()

    fake_response = MagicMock()
    fake_response.status_code = 202
    fake_response.json.return_value = {"status": "success", "dedup_key": "pd-123"}

    fake_http = MagicMock()
    fake_http.post.return_value = fake_response

    with patch.dict(os.environ, {"PAGERDUTY_ROUTING_KEY": "rk-test"}):
        incident_id = trigger_incident(ticket, http_client=fake_http)

    assert incident_id == "pd-123"
    fake_http.post.assert_called_once()
    args, kwargs = fake_http.post.call_args
    assert args[0] == PAGERDUTY_ENQUEUE_URL
    body = kwargs["json"]
    assert body["routing_key"] == "rk-test"
    assert body["event_action"] == "trigger"
    assert body["dedup_key"] == ticket.id
    assert body["payload"]["severity"] == "critical"  # p0 -> critical
    assert ticket.pagerduty_incident == "pd-123"


def test_pagerduty_resolve_with_mocked_http(db_session):
    from ops_supervisor_models import Situation, EscalationTicket
    from ops_pagerduty import resolve_incident

    cust = _make_customer()
    job = _make_job(cust)
    sit = Situation(booking_id=job.id, tag="truck_late", severity="high")
    db.session.add(sit)
    db.session.flush()
    ticket = EscalationTicket(
        situation_id=sit.id,
        priority="p2",
        summary_md="test",
        pagerduty_incident="pd-dedup-abc",
    )
    db.session.add(ticket)
    db.session.commit()

    fake_response = MagicMock()
    fake_response.status_code = 202
    fake_response.json.return_value = {"status": "success"}

    fake_http = MagicMock()
    fake_http.post.return_value = fake_response

    with patch.dict(os.environ, {"PAGERDUTY_ROUTING_KEY": "rk-test"}):
        ok = resolve_incident(ticket, http_client=fake_http)

    assert ok is True
    args, kwargs = fake_http.post.call_args
    assert kwargs["json"]["event_action"] == "resolve"
    assert kwargs["json"]["dedup_key"] == "pd-dedup-abc"


# ===========================================================================
# 7. v1 ingestion route — end-to-end through the v1alpha blueprint
# ===========================================================================
def test_v1_ingest_event_runs_workflow_inline(client, db_session):
    cust = _make_customer()
    job = _make_job(cust, status="in_progress", scheduled_offset_min=-25)

    with patch("routes.ops_supervisor.sms_service.send_sms",
               return_value="SM_v1"):
        resp = client.post(
            "/ops-supervisor/v1alpha/internal/events",
            headers=_svc_headers(),
            json={
                "type": "booking.late",
                "booking_id": job.id,
                "payload": {},
                "source": "gps_tracker",
            },
        )

    data = resp.get_json()
    assert resp.status_code == 201, data
    assert data["event"]["booking_id"] == job.id
    assert data["classifier"]["tag"] == "truck_late"
    # Inline workflow produced a situation bundle.
    assert data["situation_bundle"] is not None
    assert data["situation_bundle"]["situation"]["tag"] == "truck_late"
    assert len(data["situation_bundle"]["decisions"]) >= 1


# ===========================================================================
# 8. Migration shape sanity — keeps indexes out of table arrays
# ===========================================================================
def test_v1_migration_arrays_are_separated():
    from ops_supervisor_v1_migrations import (
        NEW_TABLES_SQLITE, NEW_TABLES_PG,
        NEW_INDEXES_SQLITE, NEW_INDEXES_PG,
        NEW_TABLE_NAMES,
    )
    # Spec: "DO NOT interleave CREATE INDEX into NEW_TABLES arrays"
    for stmt in NEW_TABLES_SQLITE + NEW_TABLES_PG:
        assert "CREATE INDEX" not in stmt.upper(), (
            "CREATE INDEX leaked into NEW_TABLES array: {}".format(stmt[:80]))
    for stmt in NEW_INDEXES_SQLITE + NEW_INDEXES_PG:
        assert "CREATE INDEX" in stmt.upper()
    assert NEW_TABLE_NAMES, "NEW_TABLE_NAMES must list new tables"
