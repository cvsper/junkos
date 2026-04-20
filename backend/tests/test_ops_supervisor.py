"""
Ops Supervisor Agent — route + behaviour tests (spec 11, 72h MVP).

Pattern mirrors tests/test_portal_routes.py. The service token MUST be set
BEFORE the app is imported so the route sees it.

Mocks:
  * ``sms_service.send_sms`` is patched to a capture function so no Twilio
    call is ever attempted.
  * ``anthropic`` is not imported because ``ANTHROPIC_API_KEY`` is never set
    in tests -- ``craft_sms`` takes the template fallback.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

# Set BEFORE importing app -- matches the portal-test pattern.
os.environ.setdefault("OPS_SUPERVISOR_SERVICE_TOKEN", "test-supervisor-token")
# Ensure Claude path is NOT taken in tests.
os.environ.pop("ANTHROPIC_API_KEY", None)

from models import db, User, Job  # noqa: E402


SERVICE_TOKEN = "test-supervisor-token"


# ---------------------------------------------------------------------------
# Blueprint registration — server.py is off-limits in this build slice, so
# we attach the supervisor blueprint to the shared test app ourselves.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def _register_ops_blueprint(app):
    from routes.ops_supervisor import ops_supervisor_bp
    if "ops_supervisor" not in app.blueprints:
        app.register_blueprint(ops_supervisor_bp)
    # Re-create tables after the new models get registered on db.metadata.
    with app.app_context():
        db.create_all()
    yield


# ---------------------------------------------------------------------------
# Fixtures / helpers
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


def _make_job(
    customer,
    status="in_progress",
    scheduled_offset_min=-20,  # 20 min ago -> late
    lat=25.7617,
    lng=-80.1918,
    payment_status=None,
):
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
    db.session.flush()

    if payment_status is not None:
        from models import Payment
        p = Payment(
            id=str(uuid.uuid4()),
            job_id=job.id,
            amount=120.0,
            payment_status=payment_status,
        )
        db.session.add(p)
        db.session.flush()

    db.session.commit()
    return job


def _svc_headers():
    return {"X-Service-Token": SERVICE_TOKEN}


# ===========================================================================
# 1. Service token required
# ===========================================================================
def test_service_token_required(client, db_session):
    resp = client.post(
        "/ops-supervisor/v1/internal/events",
        json={"type": "booking.late", "booking_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert resp.status_code == 401, resp.get_json()


# ===========================================================================
# 2. booking.late event creates OpsEvent + Situation + Decision + Action chain
# ===========================================================================
def test_late_event_creates_full_chain(client, db_session):
    cust = _make_customer()
    job = _make_job(cust, status="in_progress", scheduled_offset_min=-20)

    with patch("routes.ops_supervisor.sms_service.send_sms",
               return_value="SM_fake_sid"):
        resp = client.post(
            "/ops-supervisor/v1/internal/events",
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
    assert data["detection"]["tag"] == "truck_late"
    assert data["situation"]["tag"] == "truck_late"
    assert len(data["decisions"]) == 1

    actions = data["decisions"][0]["actions"]
    tools_fired = [a["tool"] for a in actions if a["status"] == "executed"]
    assert "issue_credit" in tools_fired
    assert "send_customer_sms" in tools_fired

    # DB round-trip sanity.
    from ops_supervisor_models import OpsEvent, Situation, AgentDecision, AgentAction
    assert db.session.query(OpsEvent).filter_by(booking_id=job.id).count() == 1
    assert db.session.query(Situation).filter_by(booking_id=job.id).count() == 1
    decs = db.session.query(AgentDecision).all()
    assert len(decs) == 1
    assert db.session.query(AgentAction).filter_by(decision_id=decs[0].id).count() >= 2


# ===========================================================================
# 3. detect_truck_late pure unit
# ===========================================================================
def test_detect_truck_late_unit(db_session):
    from ops_supervisor_detectors import detect_truck_late

    cust = _make_customer()
    on_time = _make_job(cust, scheduled_offset_min=-5)
    assert detect_truck_late(on_time) is None

    late = _make_job(cust, scheduled_offset_min=-20)
    d = detect_truck_late(late)
    assert d is not None
    assert d.tag == "truck_late"
    assert d.details["minutes_late"] > 15


# ===========================================================================
# 4. validate_credit blocks $150
# ===========================================================================
def test_validate_credit_blocks_above_cap():
    from ops_supervisor_guardrails import validate_credit
    res = validate_credit(15000)  # $150
    assert not res.ok
    assert "cap" in res.reason.lower()

    ok = validate_credit(1500)
    assert ok.ok


# ===========================================================================
# 5. validate_refund blocks $100
# ===========================================================================
def test_validate_refund_blocks_above_cap():
    from ops_supervisor_guardrails import validate_refund
    res = validate_refund(10000)  # $100
    assert not res.ok
    assert "cap" in res.reason.lower()


# ===========================================================================
# 6. validate_sms_rate blocks second customer SMS on same situation
# ===========================================================================
def test_sms_rate_limit_blocks_second_customer_sms(client, db_session):
    cust = _make_customer(phone="+13055550777")
    job = _make_job(cust, status="in_progress", scheduled_offset_min=-25)

    with patch("routes.ops_supervisor.sms_service.send_sms",
               return_value="SM_sid_1"):
        resp1 = client.post(
            "/ops-supervisor/v1/internal/events",
            headers=_svc_headers(),
            json={"type": "booking.late", "booking_id": job.id, "payload": {}},
        )
    assert resp1.status_code == 201

    situation_id = resp1.get_json()["situation"]["id"]

    # Now directly invoke the rate guard: it should block a second send.
    from ops_supervisor_guardrails import validate_sms_rate
    gate = validate_sms_rate(db.session, situation_id)
    assert not gate.ok
    assert "already sent" in gate.reason or "rate" in gate.reason.lower()


# ===========================================================================
# 7. payment-failed post-job: retry SMS, no credit, no refund
# ===========================================================================
def test_payment_failed_flow(client, db_session):
    cust = _make_customer(phone="+13055550999")
    job = _make_job(
        cust, status="completed", scheduled_offset_min=-120,
        payment_status="failed",
    )

    with patch("routes.ops_supervisor.sms_service.send_sms",
               return_value="SM_sid_pay"):
        resp = client.post(
            "/ops-supervisor/v1/internal/events",
            headers=_svc_headers(),
            json={
                "type": "payment.failed",
                "booking_id": job.id,
                "payload": {"payment_status": "failed"},
                "source": "stripe",
            },
        )
    data = resp.get_json()
    assert resp.status_code == 201, data
    assert data["detection"]["tag"] == "payment_failed_post_job"

    tools = [
        a["tool"]
        for dec in data["decisions"] for a in dec["actions"]
        if a["status"] == "executed"
    ]
    assert "send_customer_sms" in tools
    assert "issue_credit" not in tools
    assert "issue_refund" not in tools


# ===========================================================================
# 8. GPS deviation -> escalation ticket
# ===========================================================================
def test_gps_deviation_creates_escalation(client, db_session):
    cust = _make_customer(phone="+13055550222")
    # Destination in Miami, driver reports from Fort Lauderdale (~25 mi away).
    job = _make_job(
        cust, status="in_progress", scheduled_offset_min=-5,
        lat=25.7617, lng=-80.1918,
    )

    with patch("routes.ops_supervisor.sms_service.send_sms",
               return_value="SM_sid_drv"):
        resp = client.post(
            "/ops-supervisor/v1/internal/events",
            headers=_svc_headers(),
            json={
                "type": "booking.gps.deviation",
                "booking_id": job.id,
                "payload": {
                    "lat": 26.1224,
                    "lng": -80.1373,
                    # last_on_route_at 15 min ago -> definitely off-route.
                    "last_on_route_at": (datetime.now(timezone.utc)
                                         - timedelta(minutes=15)).isoformat(),
                },
                "source": "gps_tracker",
            },
        )
    data = resp.get_json()
    assert resp.status_code == 201, data
    assert data["detection"]["tag"] == "gps_deviation"
    assert len(data["escalations"]) >= 1
    assert data["escalations"][0]["priority"] == "p2"


# ===========================================================================
# 9. craft_sms falls back to template without ANTHROPIC_API_KEY
# ===========================================================================
def test_craft_sms_fallback_without_api_key():
    from ops_supervisor_sms import craft_sms, TEMPLATES
    assert "ANTHROPIC_API_KEY" not in os.environ or not os.environ["ANTHROPIC_API_KEY"]
    body = craft_sms(
        "truck_late",
        {"customer_name": "Alex Diaz"},
        {"credit_dollars": 15, "minutes_late": 22},
    )
    # Template renders with the supplied values.
    assert "Alex" in body
    assert "$15" in body or "15" in body
    assert len(body) <= 320

    # Unknown tag gets the generic fallback text.
    generic = craft_sms("some_unknown_tag", {}, {})
    assert generic  # non-empty


# ===========================================================================
# 10. Situation listing filters
# ===========================================================================
def test_situation_listing_filters(client, db_session):
    cust = _make_customer(phone="+13055550333")
    j1 = _make_job(cust, status="in_progress", scheduled_offset_min=-20)
    j2 = _make_job(cust, status="in_progress", scheduled_offset_min=-50)  # high severity

    with patch("routes.ops_supervisor.sms_service.send_sms",
               return_value="SM"):
        client.post(
            "/ops-supervisor/v1/internal/events",
            headers=_svc_headers(),
            json={"type": "booking.late", "booking_id": j1.id, "payload": {}},
        )
        client.post(
            "/ops-supervisor/v1/internal/events",
            headers=_svc_headers(),
            json={"type": "booking.late", "booking_id": j2.id, "payload": {}},
        )

    resp_all = client.get("/ops-supervisor/v1/situations?open=true")
    assert resp_all.status_code == 200
    assert len(resp_all.get_json()["situations"]) >= 2

    resp_high = client.get("/ops-supervisor/v1/situations?severity=high")
    assert resp_high.status_code == 200
    sev_set = {s["severity"] for s in resp_high.get_json()["situations"]}
    assert sev_set <= {"high"}

    # Close one and verify open=false surfaces closed situations only.
    any_sit = resp_all.get_json()["situations"][0]
    close_resp = client.post(
        "/ops-supervisor/v1/situations/{}/close".format(any_sit["id"]),
        json={"outcome": "customer_happy"},
    )
    assert close_resp.status_code == 200
    closed_list = client.get("/ops-supervisor/v1/situations?open=false").get_json()
    assert any(s["id"] == any_sit["id"] for s in closed_list["situations"])


# ===========================================================================
# 11. Audit-log completeness: every AgentAction has a preceding AgentDecision
# ===========================================================================
def test_every_action_has_preceding_decision(client, db_session):
    cust = _make_customer(phone="+13055550444")
    job = _make_job(cust, status="in_progress", scheduled_offset_min=-25)

    with patch("routes.ops_supervisor.sms_service.send_sms", return_value="SM"):
        client.post(
            "/ops-supervisor/v1/internal/events",
            headers=_svc_headers(),
            json={"type": "booking.late", "booking_id": job.id, "payload": {}},
        )

    from ops_supervisor_models import AgentAction, AgentDecision
    actions = db.session.query(AgentAction).all()
    assert len(actions) >= 2
    for a in actions:
        decision = db.session.query(AgentDecision).filter_by(id=a.decision_id).first()
        assert decision is not None, "action {} has no parent decision".format(a.id)
        # Decision must have been created at or before the action.
        assert decision.created_at <= a.created_at
