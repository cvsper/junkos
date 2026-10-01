"""Desk runway: days of calling left, and the reminder that reaches the owner.

The account ran dry on 30 Sep 2026 with nobody told. These tests hold the two
things that fix that: the capacity read now carries days (from real daily
spend) and a fill for the rail, and the runway check alerts once on the way
down, nags daily while short, and says so once on the way back up.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

import desk_runway
import twilio_capacity
from models import db, DeskSetting


# --- a fake Twilio client with daily usage records ----------------------------
class _Rec:
    def __init__(self, usage, price):
        self.usage, self.price = usage, price


class _Window:
    def __init__(self, by_category):
        self._by = by_category

    def list(self, category=None, limit=None, **kw):
        rec = self._by.get(category)
        return [rec] if rec else []


class _Daily:
    def __init__(self, prices):
        self._prices = prices

    def list(self, category=None, start_date=None, end_date=None, limit=None):
        return [_Rec("1", p) for p in self._prices]


class _Records:
    def __init__(self, last_month=None, daily=None):
        self.last_month = _Window(last_month or {})
        self.this_month = _Window({})
        self.daily = _Daily(daily or [])


class _Usage:
    def __init__(self, records):
        self.records = records


class _Balance:
    def __init__(self, amount):
        self.balance = amount

    def fetch(self):
        return self


class _Client:
    def __init__(self, balance="100.00", last_month=None, daily=None):
        self.balance = _Balance(balance)
        self.usage = _Usage(_Records(last_month, daily))


@pytest.fixture(autouse=True)
def clean(app):
    with mock.patch.dict(os.environ, {"TWILIO_ACCOUNT_SID": "AC_test", "TWILIO_AUTH_TOKEN": "tok"}):
        for key in (twilio_capacity.CACHE_KEY, desk_runway.STATE_KEY, desk_runway.NAG_KEY):
            DeskSetting.query.filter_by(key=key).delete()
        db.session.commit()
        yield
    for key in (twilio_capacity.CACHE_KEY, desk_runway.STATE_KEY, desk_runway.NAG_KEY):
        DeskSetting.query.filter_by(key=key).delete()
    db.session.commit()


def _cap(client):
    with mock.patch.object(twilio_capacity, "_client", return_value=client):
        return twilio_capacity.desk_capacity(refresh=True)


# --- capacity: days and fill ---------------------------------------------------
def test_days_come_from_real_daily_spend():
    # $21 left, $3/day for the last week → 7 days of calling.
    cap = _cap(_Client("21.00", daily=["3.00"] * 7))
    assert cap["ok"] and cap["days"] == 7.0
    assert cap["fill"] == pytest.approx(0.7)      # 7 of the 10-day "full" mark
    assert cap["level"] == "ok"
    assert "balance" not in cap and "$" not in json.dumps(cap)


def test_two_days_left_is_low_even_with_plenty_of_minutes():
    # At list price $6 is ≈430 minutes — above the old minute mark — but the
    # desk really spends $3 a day, so it's two days from dark.
    cap = _cap(_Client("6.00", daily=["3.00"] * 7))
    assert cap["minutes"] > 400
    assert cap["days"] == 2.0
    assert cap["level"] == "low"


def test_no_spend_history_falls_back_to_minutes():
    cap = _cap(_Client("30.00", daily=[]))
    assert cap["days"] is None
    assert cap["level"] == "ok"
    assert 0 < cap["fill"] <= 1


def test_empty_account_reads_empty_and_zero_fill():
    cap = _cap(_Client("0.00", daily=["3.00"] * 7))
    assert cap["level"] == "empty" and cap["fill"] == 0.0


# --- runway alerts -------------------------------------------------------------
def _low_cap(days=2.0):
    return {"configured": True, "ok": True, "texts": 500, "minutes": 400, "days": days,
            "fill": 0.2, "level": "low"}


def _ok_cap():
    return {"configured": True, "ok": True, "texts": 5000, "minutes": 3000, "days": 9.0,
            "fill": 0.9, "level": "ok"}


def test_alerts_once_when_it_turns_low_then_stays_quiet():
    with mock.patch.object(desk_runway, "_send", return_value=["sms"]) as send:
        r = desk_runway.check_and_alert(_low_cap(), balance=6.0)
        assert r["state"] == "warn" and "2 days" in r["reason"]
        assert send.call_count == 1
        subject, body = send.call_args[0]
        assert "low" in subject.lower()
        assert "2 days of calling left" in body and "$6.00" in body and "console.twilio.com" in body
        # Same reading half an hour later: no second text.
        desk_runway.check_and_alert(_low_cap(), balance=6.0)
        assert send.call_count == 1


def test_nags_again_after_a_day_while_still_low():
    with mock.patch.object(desk_runway, "_send", return_value=["sms"]) as send:
        desk_runway.check_and_alert(_low_cap(), balance=6.0)
        stale = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        DeskSetting.put(desk_runway.NAG_KEY, stale)
        desk_runway.check_and_alert(_low_cap(1.5), balance=4.5)
        assert send.call_count == 2


def test_says_topped_up_once_on_recovery():
    with mock.patch.object(desk_runway, "_send", return_value=["sms"]) as send:
        desk_runway.check_and_alert(_low_cap(), balance=6.0)
        desk_runway.check_and_alert(_ok_cap(), balance=40.0)
        assert send.call_count == 2
        assert "topped up" in send.call_args[0][0].lower()
        desk_runway.check_and_alert(_ok_cap(), balance=40.0)
        assert send.call_count == 2          # ok → ok is silent


def test_empty_is_a_fail_and_reads_off():
    cap = dict(_low_cap(0.0), level="empty", texts=0, minutes=0, fill=0.0)
    with mock.patch.object(desk_runway, "_send", return_value=["sms"]) as send:
        r = desk_runway.check_and_alert(cap, balance=0.0)
        assert r["state"] == "fail" and "OFF" in r["reason"]
        assert "OFF" in send.call_args[0][0]


def test_unknown_runway_never_texts():
    with mock.patch.object(desk_runway, "_send") as send:
        r = desk_runway.check_and_alert({"configured": True, "ok": False, "level": "unknown"})
        assert r["state"] == "warn"
        send.assert_not_called()


def test_alert_false_records_state_without_sending():
    with mock.patch.object(desk_runway, "_send") as send:
        desk_runway.check_and_alert(_low_cap(), alert=False)
        send.assert_not_called()
        assert DeskSetting.get(desk_runway.STATE_KEY) == "low"


def test_text_goes_to_the_private_alert_number_first():
    with mock.patch("ops_contacts.alert_phone", return_value="+15550001111"), \
         mock.patch("sms_service.send_sms", return_value=True) as sms, \
         mock.patch("desk_health._send_alert") as fan:
        sent = desk_runway._send("subj", "body")
        sms.assert_called_once_with("+15550001111", "body")
        fan.assert_called_once_with("subj", "body")
        assert sent == ["sms", "desk_health"]


# --- the endpoint carries days, fill and whether the line is on ----------------
def test_capacity_endpoint_reports_line_state(client, app):
    from models import User
    import desk_line
    with app.app_context():
        with mock.patch.object(desk_line, "desk_identity", return_value={"name": "T", "user_id": "x"}), \
             mock.patch("twilio_capacity.desk_capacity", return_value=_low_cap()), \
             mock.patch.object(desk_line, "delivery_report", return_value=None):
            r = client.post("/api/va/desk/capacity", json={})
            assert r.status_code == 200
            b = r.get_json()
            assert b["line"] == "on" and b["days"] == 2.0 and b["fill"] == 0.2 and b["level"] == "low"
        with mock.patch.object(desk_line, "desk_identity", return_value={"name": "T", "user_id": "x"}), \
             mock.patch("twilio_capacity.desk_capacity",
                        return_value={"configured": True, "ok": False, "level": "unknown"}), \
             mock.patch.object(desk_line, "delivery_report", return_value=None):
            b = client.post("/api/va/desk/capacity", json={}).get_json()
            assert b["line"] == "off"
