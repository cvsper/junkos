"""A frozen ad account must be loud.

Four times in three weeks the account went unsettled over a few dollars and
nobody knew until someone happened to look at the numbers. The campaign objects
are no help — they keep reading ACTIVE while nothing is served. These tests pin
the one signal that tells the truth, and the copy that says how to end it
rather than just how to clear it.
"""
import os
from unittest import mock

import pytest

import meta_ads_health as mah


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def _meta(payload):
    return mock.patch.object(mah, "requests", create=True,
                             **{"get.return_value": _Resp(payload)})


@pytest.fixture(autouse=True)
def token():
    with mock.patch.dict(os.environ, {"META_ADS_TOKEN": "t0ken"}):
        yield


def _check(payload):
    fake = mock.MagicMock()
    fake.get.return_value = _Resp(payload)
    with mock.patch.dict("sys.modules", {"requests": fake}):
        return mah.ad_account_check()


def test_a_healthy_account_is_quiet():
    r = _check({"account_status": 1, "balance": "0"})
    assert r["state"] == "ok" and "nothing owed" in r["reason"]


def test_accruing_balance_is_still_fine():
    """Threshold billing means a running balance is normal, not a problem."""
    r = _check({"account_status": 1, "balance": "585"})
    assert r["state"] == "ok" and "5.85" in r["reason"]


def test_unsettled_fails_and_says_how_to_end_it():
    r = _check({"account_status": 3, "balance": "640"})
    assert r["state"] == "fail"
    assert "$6.40 owed" in r["reason"]
    # clearing it is the stopgap; the backup method is the actual fix
    assert "PayPal" in r["reason"] and "recurring" in r["reason"]


def test_disabled_and_closed_fail():
    assert _check({"account_status": 2})["state"] == "fail"
    assert _check({"account_status": 101})["state"] == "fail"


@pytest.mark.parametrize("status", [7, 8, 9])
def test_in_between_states_warn(status):
    assert _check({"account_status": status})["state"] == "warn"


def test_unreachable_meta_warns_rather_than_reading_healthy():
    fake = mock.MagicMock()
    fake.get.side_effect = RuntimeError("boom")
    with mock.patch.dict("sys.modules", {"requests": fake}):
        r = mah.ad_account_check()
    assert r["state"] == "warn" and r["status"] is None


def test_a_refused_read_warns():
    r = _check({"error": {"message": "Invalid OAuth access token"}})
    assert r["state"] == "warn" and "refused" in r["reason"]


def test_no_token_says_nobody_is_watching():
    with mock.patch.dict(os.environ, {"META_ADS_TOKEN": "", "META_ACCESS_TOKEN": ""}):
        r = mah.ad_account_check()
    assert r["state"] == "warn" and "nobody is watching" in r["reason"]


def test_desk_health_carries_the_check(app):
    """It has to ride the existing 30-minute beat to be worth anything."""
    from desk_health import check_desk_health
    with mock.patch.dict(os.environ, {"META_ADS_TOKEN": "", "META_ACCESS_TOKEN": ""}):
        rep = check_desk_health(alert=False)
    assert "meta_ads" in rep["checks"]
    assert rep["checks"]["meta_ads"]["state"] in ("ok", "warn", "fail")
