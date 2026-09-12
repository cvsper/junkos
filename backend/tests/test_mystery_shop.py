"""The daily mystery shopper: accepts the booking route's real rejection code
and reports failing checks by name instead of exiting the scheduler thread."""
from unittest import mock

import mystery_shop
import scheduler as sched


class _Resp:
    def __init__(self, status, body):
        self.status_code = status; self._body = body
    def json(self):
        return self._body


def test_out_of_area_check_accepts_the_routes_422():
    body = {"error": "Address is outside our service area. We currently serve Miami-Dade…", "code": "outside_market"}
    with mock.patch.object(mystery_shop.requests, "post", return_value=_Resp(422, body)):
        ok, detail = mystery_shop.check_booking_rejects_out_of_area()
    assert ok and "422" in detail
    with mock.patch.object(mystery_shop.requests, "post", return_value=_Resp(400, body)):
        assert mystery_shop.check_booking_rejects_out_of_area()[0]
    with mock.patch.object(mystery_shop.requests, "post", return_value=_Resp(201, {"id": "oops"})):
        ok, detail = mystery_shop.check_booking_rejects_out_of_area()
    assert not ok and "201" in detail


def test_run_returns_failures_without_exiting(monkeypatch):
    monkeypatch.setattr(mystery_shop, "CHECKS", [("good", lambda: (True, "fine")), ("bad", lambda: (False, "broke"))])
    alerts = []
    monkeypatch.setattr(mystery_shop, "alert_admin", lambda f: alerts.append(f))
    assert mystery_shop.run() == [("bad", "broke")]
    assert alerts == [[("bad", "broke")]]


def test_scheduler_job_names_the_failing_checks(app, monkeypatch):
    monkeypatch.setattr(mystery_shop, "run", lambda: [("Booking rejects out-of-area", "expected 400, got 422")])
    monkeypatch.setenv("MYSTERY_SHOP_ENABLED", "true")
    try:
        sched._run_mystery_shop(app)
    except RuntimeError as exc:
        assert "Booking rejects out-of-area" in str(exc)
    else:
        raise AssertionError("failing checks should surface as the job's error")
    monkeypatch.setattr(mystery_shop, "run", lambda: [])
    sched._run_mystery_shop(app)  # all green → returns quietly
