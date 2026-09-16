"""Desk runway: balance → texts or minutes, and never a dollar figure.

The point of this module is what it withholds. A VA on a shared screen sees how
much line is left; the account balance stays the owner's business. These tests
hold that line, plus the arithmetic and the fallbacks behind it.
"""
import json
import os
from unittest import mock

import pytest

import twilio_capacity
from models import db, DeskSetting


class _Rec:
    def __init__(self, usage, price):
        self.usage, self.price = usage, price


class _Window:
    def __init__(self, by_category):
        self._by = by_category

    def list(self, category=None, limit=None):
        rec = self._by.get(category)
        return [rec] if rec else []


class _Records:
    def __init__(self, last_month=None, this_month=None):
        self.last_month = _Window(last_month or {})
        self.this_month = _Window(this_month or {})


class _Usage:
    def __init__(self, records):
        self.records = records


class _Balance:
    def __init__(self, amount):
        self.balance = amount

    def fetch(self):
        return self


class _Client:
    def __init__(self, balance="100.00", last_month=None, this_month=None):
        self.balance = _Balance(balance)
        self.usage = _Usage(_Records(last_month, this_month))


@pytest.fixture(autouse=True)
def clean(app):
    with mock.patch.dict(os.environ, {"TWILIO_ACCOUNT_SID": "AC_test", "TWILIO_AUTH_TOKEN": "tok",
                                      "TRIXIE_ASSISTANT_PASSCODE": "test-code"}):
        DeskSetting.query.filter_by(key=twilio_capacity.CACHE_KEY).delete()
        db.session.commit()
        yield
    DeskSetting.query.filter_by(key=twilio_capacity.CACHE_KEY).delete()
    db.session.commit()


def _patch(client):
    return mock.patch.object(twilio_capacity, "_client", return_value=client)


def test_blends_the_rate_from_real_spend():
    # $100 left; last month 1,000 texts cost $11 and 500 minutes cost $7.50.
    client = _Client("100.00", last_month={"sms-outbound": _Rec("1000", "11.00"),
                                           "calls-outbound": _Rec("500", "7.50")})
    with _patch(client):
        cap = twilio_capacity.desk_capacity(refresh=True)
    assert cap["rate_source"] == "usage"
    assert cap["texts"] == 9090      # 100 / 0.011
    assert cap["minutes"] == 6666    # 100 / 0.015
    assert cap["level"] == "ok"


def test_reports_units_and_never_money():
    client = _Client("42.50", last_month={"sms-outbound": _Rec("1000", "11.00"),
                                          "calls-outbound": _Rec("500", "7.50")})
    with _patch(client):
        cap = twilio_capacity.desk_capacity(refresh=True)
    blob = json.dumps(cap)
    assert "42.5" not in blob and "$" not in blob
    for banned in ("balance", "price", "amount", "currency", "usd"):
        assert banned not in blob.lower()


def test_thin_usage_falls_back_to_list_price():
    # Three texts last month is not a rate; don't pretend it is.
    client = _Client("10.90", last_month={"sms-outbound": _Rec("3", "0.05")})
    with _patch(client):
        cap = twilio_capacity.desk_capacity(refresh=True)
    assert cap["rate_source"] == "list"
    assert cap["texts"] == int(10.90 // twilio_capacity.LIST_RATE_SMS)


def test_this_month_covers_a_brand_new_account():
    client = _Client("50.00", last_month={},
                     this_month={"sms-outbound": _Rec("500", "5.00"),
                                 "calls-outbound": _Rec("200", "2.80")})
    with _patch(client):
        cap = twilio_capacity.desk_capacity(refresh=True)
    assert cap["rate_source"] == "usage" and cap["texts"] == 5000


def test_env_overrides_beat_list_price():
    client = _Client("20.00")
    with _patch(client), mock.patch.dict(os.environ, {"TWILIO_RATE_SMS": "0.02",
                                                      "TWILIO_RATE_CALL_MIN": "0.04"}):
        cap = twilio_capacity.desk_capacity(refresh=True)
    assert cap["rate_source"] == "env" and cap["texts"] == 1000 and cap["minutes"] == 500


def test_low_and_empty_levels():
    client = _Client("1.00", last_month={"sms-outbound": _Rec("1000", "10.00"),
                                         "calls-outbound": _Rec("500", "7.00")})
    with _patch(client):
        assert twilio_capacity.desk_capacity(refresh=True)["level"] == "low"
    with _patch(_Client("0.00")):
        assert twilio_capacity.desk_capacity(refresh=True)["level"] == "empty"


def test_unreachable_twilio_shows_nothing_rather_than_a_wrong_number():
    client = _Client("100.00")
    client.balance.fetch = mock.Mock(side_effect=RuntimeError("boom"))
    with _patch(client):
        cap = twilio_capacity.desk_capacity(refresh=True)
    assert cap["ok"] is False and cap["texts"] is None and cap["level"] == "unknown"
    assert twilio_capacity.summary_line(cap) == ""


def test_missing_credentials_are_not_an_error():
    with mock.patch.dict(os.environ, {"TWILIO_ACCOUNT_SID": "", "TWILIO_AUTH_TOKEN": ""}):
        cap = twilio_capacity.desk_capacity(refresh=True)
    assert cap["configured"] is False and cap["ok"] is False


def test_a_page_load_costs_no_twilio_round_trip():
    client = _Client("100.00", last_month={"sms-outbound": _Rec("1000", "11.00"),
                                           "calls-outbound": _Rec("500", "7.50")})
    with _patch(client) as first:
        twilio_capacity.desk_capacity(refresh=True)
        assert first.call_count == 1
        twilio_capacity.desk_capacity()
        twilio_capacity.desk_capacity()
        assert first.call_count == 1  # served from the cache


def test_summary_line_reads_as_either_or():
    client = _Client("100.00", last_month={"sms-outbound": _Rec("1000", "10.00"),
                                           "calls-outbound": _Rec("500", "5.00")})
    with _patch(client):
        line = twilio_capacity.summary_line(twilio_capacity.desk_capacity(refresh=True))
    assert line == "≈ 10,000 texts or 10,000 min left"
    assert "$" not in line


def test_desk_endpoint_needs_a_sign_in(client):
    assert client.post("/api/va/desk/capacity", json={}).status_code == 401


def test_desk_endpoint_returns_units_only(client):
    tw = _Client("100.00", last_month={"sms-outbound": _Rec("1000", "11.00"),
                                       "calls-outbound": _Rec("500", "7.50")})
    with _patch(tw):
        r = client.post("/api/va/desk/capacity", json={"code": "test-code", "va_name": "Tracy"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True and body["texts"] == 9090 and body["minutes"] == 6666
    assert body["label"] == "≈ 9,090 texts or 6,666 min left"
    assert "$" not in json.dumps(body) and "balance" not in json.dumps(body).lower()


def test_manager_page_carries_the_chip(client):
    page = client.get("/va/manager").get_data(as_text=True)
    assert 'id="cap-chip"' in page and 'id="cap-label"' in page
    css = client.get("/static/manager.css").get_data(as_text=True)
    assert ".mg-cap{" in css and ".mg-cap.low" in css and ".mg-cap.empty" in css
    js = client.get("/static/manager.js").get_data(as_text=True)
    assert "/api/va/desk/capacity" in js
    # the owner's page shows runway, not the account balance
    assert "$" not in page.split('id="cap-chip"')[1][:400]


def test_call_desk_page_carries_the_chip(client):
    page = client.get("/va/calls").get_data(as_text=True)
    assert 'id="cap-chip"' in page
    assert ".cap{" in client.get("/va/calls.css").get_data(as_text=True)
    assert "/api/va/desk/capacity" in client.get("/va/calls.js").get_data(as_text=True)
