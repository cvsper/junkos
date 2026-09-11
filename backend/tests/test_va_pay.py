"""Hourly pay beside the hours.

The clock tracked seconds but no rate, so working out what a VA was owed each
period was manual arithmetic. Pay is derived from hours x rate at read time —
never stored — so correcting a rate corrects every figure.
"""
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from models import db, VaShift, DeskSetting, User
import va_time


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code",
                                      "VA_DEFAULT_HOURLY_RATE": "0"}):
        yield
    VaShift.query.delete(); DeskSetting.query.delete(); db.session.commit()


def _shift(va, hours, days_ago=0):
    end = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago, hours=1)
    sh = VaShift(va_name=va, started_at=end - timedelta(hours=hours), ended_at=end)
    db.session.add(sh); db.session.commit()
    return sh


def _va(client, path, payload=None):
    base = {"code": "test-code", "va_name": "Tracy"}
    base.update(payload or {})
    return client.post(path, json=base)


def test_no_rate_set_means_no_invented_wage():
    _shift("Tracy", 7.2)
    t = va_time.totals_for("Tracy")
    assert t["hourly_rate"] == 0
    assert t["period_pay"] is None, "a missing rate must read as unknown, not $0.00 earned"
    assert t["period_hours"] > 0


def test_pay_is_hours_times_rate():
    va_time.set_hourly_rate("Tracy", 1.25)
    _shift("Tracy", 8)
    t = va_time.totals_for("Tracy")
    assert t["hourly_rate"] == 1.25
    assert t["period_hours"] == 8.0 and t["period_pay"] == 10.0


def test_rate_is_per_va_with_a_default_fallback():
    DeskSetting.put("va_rate:default", "2.0000")
    va_time.set_hourly_rate("Tracy", 1.25)
    assert va_time.hourly_rate("Tracy") == 1.25
    assert va_time.hourly_rate("Someone Else") == 2.0
    assert va_time.hourly_rate("TRACY") == 1.25, "name lookup must be case-insensitive"


def test_each_shift_carries_its_own_pay():
    va_time.set_hourly_rate("Tracy", 1.25)
    _shift("Tracy", 7.2)
    rep = va_time.hours_report("Tracy")
    row = rep["shifts"][0]
    assert row["hours"] == 7.2 and row["pay"] == 9.0


def test_reading_is_open_to_the_desk_but_only_a_manager_can_change_pay(client):
    assert _va(client, "/api/va/time/rate", {}).get_json()["hourly_rate"] == 0
    # a VA cannot give themselves a raise
    r = _va(client, "/api/va/time/rate", {"rate": 50})
    assert r.status_code == 403
    assert va_time.hourly_rate("Tracy") == 0

    from desk_auth import create_desk_user
    create_desk_user("payroll@goumuve.com", "Payroll", "manager", "pw-payroll")
    tok = client.post("/api/desk/login", json={"email": "payroll@goumuve.com",
                                               "password": "pw-payroll"}).get_json()["token"]
    r = client.post("/api/va/time/rate", json={"va": "Tracy", "rate": 1.25},
                    headers={"Authorization": "Bearer " + tok})
    assert r.status_code == 200 and r.get_json()["hourly_rate"] == 1.25
    assert va_time.hourly_rate("Tracy") == 1.25
    bad = client.post("/api/va/time/rate", json={"va": "Tracy", "rate": -5},
                      headers={"Authorization": "Bearer " + tok})
    assert bad.status_code == 400
    User.query.filter_by(email="payroll@goumuve.com").delete(); db.session.commit()


def test_hours_endpoint_carries_pay_for_the_period(client):
    va_time.set_hourly_rate("Tracy", 1.25)
    _shift("Tracy", 7.2)
    body = _va(client, "/api/va/time/hours", {}).get_json()
    assert body["period_hours"] == 7.2 and body["period_pay"] == 9.0
    assert body["hourly_rate"] == 1.25
