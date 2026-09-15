"""Informational alerts go to email and Slack, never to the owner's phone.

sevs, 15 Sep: "you sent me like 3-4 text notifying me text cost just do email".
Every text costs money and these fire all day. SMS is now opt-in per kind via
OPS_ALERT_SMS; customer- and hauler-facing texts are untouched.
"""
import os
from unittest import mock

import pytest

import booking_alerts


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {"ADMIN_PHONE": "+15615551111",
                                      "OPERATOR_PHONE": "+15615552222",
                                      "ADMIN_EMAIL": "owner@t.local",
                                      "SLACK_ALERT_WEBHOOK": "",
                                      "OPS_ALERT_SMS": ""}):
        yield


def test_by_default_nothing_texts_the_owner():
    assert booking_alerts._phones() == []
    assert booking_alerts._phones("booked") == []
    assert booking_alerts._phones(None) == []


def test_sms_is_opt_in_per_kind():
    with mock.patch.dict(os.environ, {"OPS_ALERT_SMS": "booked,paid"}):
        assert booking_alerts._phones("booked") == ["+15615551111", "+15615552222"]
        assert booking_alerts._phones("paid")
        assert booking_alerts._phones("lead") == []      # not listed
        assert booking_alerts._phones(None) == []        # informational, never
    with mock.patch.dict(os.environ, {"OPS_ALERT_SMS": "all"}):
        assert booking_alerts._phones("anything")


def test_an_ops_alert_emails_and_does_not_text():
    with mock.patch("notifications._send_email_sync") as email, \
         mock.patch("sms_service.send_sms_async") as sms:
        used = booking_alerts.ops_alert("Thumbtack lead · Dana", "body here")
    assert "email" in used and "sms" not in used
    assert sms.call_count == 0
    assert email.call_args[0][0] == "owner@t.local"
    assert "Thumbtack lead" in email.call_args[0][1]


def test_extra_alert_addresses_are_honoured():
    with mock.patch.dict(os.environ, {"OPS_ALERT_EMAILS": "ops@t.local, second@t.local"}):
        assert booking_alerts._emails() == ["owner@t.local", "ops@t.local", "second@t.local"]


@pytest.mark.parametrize("module,fn", [("thumbtack", "alert_team"),
                                       ("photo_quote", "_alert"),
                                       ("job_addons", "_alert")])
def test_the_new_alert_paths_never_reach_send_sms(module, fn):
    import importlib
    import inspect
    src = inspect.getsource(getattr(importlib.import_module(module), fn))
    assert "ops_alert" in src
    assert "send_sms_async" not in src and "_phones" not in src
