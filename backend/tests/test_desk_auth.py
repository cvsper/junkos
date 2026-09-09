"""Desk accounts + roles, passcode fallback + flag, audit trail, flags, health."""
import os
from unittest import mock

import pytest

from models import db, User, AuditEvent, DeskSetting, CallProspect, VaShift
from desk_auth import create_desk_user


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code", "JWT_SECRET": "unit"}):
        yield
    AuditEvent.query.delete(); DeskSetting.query.delete(); VaShift.query.delete(); CallProspect.query.delete()
    User.query.filter(User.email.in_(["tracy@goumuve.com", "boss@goumuve.com", "cust@x.com"])).delete(synchronize_session=False)
    db.session.commit()


@pytest.fixture()
def accounts():
    tracy, tp = create_desk_user("tracy@goumuve.com", "Tracy Jamesyoung", "va", "pw-tracy")
    boss, bp = create_desk_user("boss@goumuve.com", "Shamar", "manager", "pw-boss")
    cust = User(email="cust@x.com", name="Cust", role="customer"); cust.set_password("pw"); db.session.add(cust); db.session.commit()
    return {"tracy": tracy, "boss": boss}


def _login(client, email, pw):
    return client.post("/api/desk/login", json={"email": email, "password": pw})


def _h(token):
    return {"Authorization": "Bearer " + token}


def test_login_roles_and_me(client, accounts):
    r = _login(client, "tracy@goumuve.com", "pw-tracy")
    assert r.status_code == 200
    b = r.get_json()
    assert b["name"] == "Tracy" and b["role"] == "va" and b["is_manager"] is False and b["token"]
    me = client.post("/api/desk/me", headers=_h(b["token"])).get_json()
    assert me["signed_in"] and me["via"] == "jwt" and me["name"] == "Tracy"
    assert _login(client, "tracy@goumuve.com", "wrong").status_code == 401
    assert _login(client, "cust@x.com", "pw").status_code == 403
    boss = _login(client, "boss@goumuve.com", "pw-boss").get_json()
    assert boss["is_manager"] is True
    # failed + successful logins are audited
    actions = [e.action for e in AuditEvent.query.all()]
    assert "login" in actions and "login_failed" in actions


def test_jwt_replaces_passcode_and_names_the_va(client, accounts):
    tok = _login(client, "tracy@goumuve.com", "pw-tracy").get_json()["token"]
    p = CallProspect(tier=1, category="storage", company="X Storage", phone="5615550100", phone_digits="5615550100")
    db.session.add(p); db.session.commit()
    # no code in the body, no va_name typed — identity comes from the token
    r = client.post("/api/va/calls/log", json={"prospect_id": p.id, "outcome": "interested"}, headers=_h(tok))
    assert r.status_code == 200
    from models import CallAttempt
    assert CallAttempt.query.filter_by(prospect_id=p.id).one().va_name == "Tracy"
    ev = AuditEvent.query.filter_by(action="outcome").one()
    assert ev.actor_name == "Tracy" and ev.actor_user_id == accounts["tracy"].id and ev.via == "jwt"
    assert ev.target_id == p.id and ev.meta["outcome"] == "interested"
    # clock uses the account name too
    r = client.post("/api/va/time/clock", json={"action": "in"}, headers=_h(tok)).get_json()
    assert r["on_clock"] and r["va_name"] == "Tracy"


def test_passcode_still_works_until_flag_off(client):
    r = client.post("/api/va/calls/next", json={"code": "test-code", "va_name": "Trixie"})
    assert r.status_code == 200
    DeskSetting.put("flag:passcode_login", "off")
    r = client.post("/api/va/calls/next", json={"code": "test-code", "va_name": "Trixie"})
    assert r.status_code == 401
    assert client.post("/api/va/calls/next", json={}).status_code == 401


def test_manager_only_endpoints(client, accounts):
    va = _login(client, "tracy@goumuve.com", "pw-tracy").get_json()["token"]
    boss = _login(client, "boss@goumuve.com", "pw-boss").get_json()["token"]
    assert client.get("/api/admin/audit", headers=_h(va)).status_code == 403
    assert client.post("/api/va/time/team", json={}, headers=_h(va)).status_code == 403
    assert client.get("/api/admin/audit", headers=_h(boss)).status_code == 200
    assert client.post("/api/va/time/team", json={}, headers=_h(boss)).status_code == 200
    # flags: VA reads, manager writes
    assert client.post("/api/va/flags", json={}, headers=_h(va)).get_json()["flags"]["copilot"] is True
    assert client.post("/api/admin/flags", json={"name": "copilot", "value": False}, headers=_h(va)).status_code == 403
    r = client.post("/api/admin/flags", json={"name": "copilot", "value": False}, headers=_h(boss)).get_json()
    assert r["flags"]["copilot"]["on"] is False and r["flags"]["copilot"]["source"] == "db"
    assert client.post("/api/va/flags", json={}, headers=_h(va)).get_json()["flags"]["copilot"] is False
    client.post("/api/admin/flags", json={"name": "copilot", "value": None}, headers=_h(boss))
    assert client.post("/api/va/flags", json={}, headers=_h(va)).get_json()["flags"]["copilot"] is True
    assert client.post("/api/admin/flags", json={"name": "nope", "value": True}, headers=_h(boss)).status_code == 400


def test_manager_creates_va_account_with_one_time_password(client, accounts):
    boss = _login(client, "boss@goumuve.com", "pw-boss").get_json()["token"]
    r = client.post("/api/admin/desk-users", json={"email": "New@GoUmuve.com", "name": "Trixie V", "role": "va"}, headers=_h(boss))
    assert r.status_code == 200
    b = r.get_json()
    assert b["user"]["email"] == "new@goumuve.com" and b["user"]["role"] == "va" and len(b["temp_password"]) >= 8
    assert _login(client, "new@goumuve.com", b["temp_password"]).status_code == 200
    # second upsert without a password returns none and keeps the account
    b2 = client.post("/api/admin/desk-users", json={"email": "new@goumuve.com", "name": "Trixie Vergara"}, headers=_h(boss)).get_json()
    assert b2["temp_password"] is None and b2["user"]["name"] == "Trixie Vergara"
    # disable, then login fails
    client.post("/api/admin/desk-users", json={"email": "new@goumuve.com", "status": "disabled"}, headers=_h(boss))
    assert _login(client, "new@goumuve.com", b["temp_password"]).status_code == 403
    users = client.get("/api/admin/desk-users", headers=_h(boss)).get_json()["users"]
    assert {u["email"] for u in users} >= {"tracy@goumuve.com", "boss@goumuve.com", "new@goumuve.com"}
    assert client.post("/api/admin/desk-users", json={"email": "x@y.com", "role": "admin"}, headers=_h(boss)).status_code == 403
    User.query.filter_by(email="new@goumuve.com").delete(); db.session.commit()


def test_env_flag_and_default(client, accounts):
    va = _login(client, "tracy@goumuve.com", "pw-tracy").get_json()["token"]
    with mock.patch.dict(os.environ, {"FEATURE_POWER_DIAL": "off"}):
        assert client.post("/api/va/flags", json={}, headers=_h(va)).get_json()["flags"]["power_dial"] is False
    assert client.post("/api/va/flags", json={}, headers=_h(va)).get_json()["flags"]["power_dial"] is True


def test_health_endpoint_reports_without_secrets(client):
    with mock.patch.dict(os.environ, {"TWILIO_ACCOUNT_SID": "", "TWILIO_AUTH_TOKEN": "unit-auth-token-value", "SENTRY_DSN": ""}):
        r = client.get("/api/health/desk")
    assert r.status_code == 503
    b = r.get_json()
    assert b["state"] == "down" and "twilio_account" in b["fails"] and "sentry" in b["warns"]
    assert "unit-auth-token-value" not in str(b)                # var names may appear, values never


def test_health_alerts_only_on_state_change(app):
    from desk_health import _alert_on_change
    with mock.patch("desk_health._send_alert") as send:
        _alert_on_change({"state": "ok", "fails": [], "warns": [], "checks": {}, "checked_at": "t"})
        assert send.call_count == 0                      # first observation, healthy: quiet
        _alert_on_change({"state": "down", "fails": ["twilio_balance"], "warns": [],
                          "checks": {"twilio_balance": {"state": "fail", "reason": "$1.00"}}, "checked_at": "t"})
        assert send.call_count == 1 and "twilio_balance" in send.call_args[0][1]
        _alert_on_change({"state": "down", "fails": ["twilio_balance"], "warns": [],
                          "checks": {"twilio_balance": {"state": "fail", "reason": "$1.00"}}, "checked_at": "t"})
        assert send.call_count == 1                      # same state: no repeat
        _alert_on_change({"state": "ok", "fails": [], "warns": [], "checks": {}, "checked_at": "t"})
        assert send.call_count == 2                      # recovery pings once


def test_passcode_can_bootstrap_only_the_first_accounts(client):
    User.query.filter(User.role.in_(["va", "manager"])).delete(synchronize_session=False); db.session.commit()
    r = client.post("/api/admin/desk-users", json={"code": "test-code", "va_name": "Dommo",
                                                   "email": "boss@goumuve.com", "name": "Shamar", "role": "manager"})
    assert r.status_code == 200 and r.get_json()["temp_password"]
    # once a manager exists, the passcode can't mint accounts anymore
    r = client.post("/api/admin/desk-users", json={"code": "test-code", "va_name": "Dommo",
                                                   "email": "tracy@goumuve.com", "name": "Tracy", "role": "va"})
    assert r.status_code == 403


def test_change_password(client, accounts):
    tok = _login(client, "tracy@goumuve.com", "pw-tracy").get_json()["token"]
    r = client.post("/api/desk/change-password", json={"current": "wrong", "new": "brand-new-1"}, headers=_h(tok))
    assert r.status_code == 401
    r = client.post("/api/desk/change-password", json={"current": "pw-tracy", "new": "short"}, headers=_h(tok))
    assert r.status_code == 400
    r = client.post("/api/desk/change-password", json={"current": "pw-tracy", "new": "brand-new-1"}, headers=_h(tok))
    assert r.status_code == 200
    assert _login(client, "tracy@goumuve.com", "pw-tracy").status_code == 401
    assert _login(client, "tracy@goumuve.com", "brand-new-1").status_code == 200
    # the passcode can't change anyone's password
    assert client.post("/api/desk/change-password", json={"code": "test-code", "va_name": "x", "current": "a", "new": "bbbbbbbbb"}).status_code == 401
    assert AuditEvent.query.filter_by(action="password_changed").count() == 1
