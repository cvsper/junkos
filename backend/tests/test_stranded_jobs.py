"""Stranded-job census: open jobs nobody is moving.

A $307.80 haul sat in "assigned" for 18 days with no start, no completion and
no photos. The sentinel knew, but anything past its 14-day cutoff collapses
into one digest line, so it was invisible in practice. This is the standing
count, and it must never leak customer PII onto the public health page.
"""
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from models import db, User, Job, generate_uuid
import ops_sentinel


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code"}):
        yield
    Job.query.filter(Job.address.like("e2e-strand%")).delete(synchronize_session=False)
    User.query.filter(User.email.like("%@strand.test")).delete(synchronize_session=False)
    db.session.commit()


def _cx():
    u = User.query.filter_by(email="cx@strand.test").first()
    if not u:
        u = User(id=generate_uuid(), email="cx@strand.test", name="Strand Cx",
                 phone="+15615550777", role="customer")
        db.session.add(u); db.session.commit()
    return u


def _job(status, days_ago, code, driver=None):
    when = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago)
    j = Job(id=generate_uuid(), customer_id=_cx().id, driver_id=driver,
            address="e2e-strand 5370 South University Dr, Davie FL",
            status=status, scheduled_at=when, total_price=307.80,
            confirmation_code=code)
    db.session.add(j); db.session.commit()
    return j


def test_census_buckets_by_age_and_flags_the_worst():
    _job("assigned", 18, "STRND018")      # the real one: 18 days, hauler assigned
    _job("assigned", 3, "STRND003")
    _job("confirmed", 1, "STRND001")
    _job("completed", 40, "STRNDDON")     # finished — not stranded
    _job("cancelled", 40, "STRNDCAN")     # cancelled — not stranded

    s = ops_sentinel.stranded_summary()
    codes = {j["code"] for j in s["jobs"]}
    assert {"STRND018", "STRND003", "STRND001"} <= codes
    assert "STRNDDON" not in codes and "STRNDCAN" not in codes
    assert s["buckets"]["7d_30d"] >= 1 and s["buckets"]["2d_7d"] >= 1
    assert s["oldest_days"] >= 18
    worst = s["jobs"][0]
    assert worst["code"] == "STRND018" and worst["status"] == "assigned"


def test_recent_jobs_are_not_stranded():
    _job("assigned", 0, "STRNDNEW")
    assert all(j["code"] != "STRNDNEW" for j in ops_sentinel.stranded_summary()["jobs"])


def test_public_health_reports_the_count_but_no_customer_pii(client):
    _job("assigned", 18, "STRNDPII")
    from desk_health import check_desk_health
    rep = check_desk_health()
    chk = rep["checks"]["stranded_jobs"]
    assert chk["state"] in ("warn", "fail") and chk["total"] >= 1
    blob = repr(chk)
    for leak in ("Strand Cx", "5615550777", "South University", "307.8", "cx@strand.test"):
        assert leak not in blob, "public health check leaked {}".format(leak)


def test_recent_slice_separates_live_work_from_seed_residue():
    """The first live census returned 260 rows, 259 of them ~200 days old seed
    data. Counting those alongside a real 18-day-old haul buries the one that
    actually needs a phone call."""
    _job("assigned", 18, "STRNDREC", driver=None)
    for i in range(3):
        _job("confirmed", 199 + i, "STRNDOLD{}".format(i))
    s = ops_sentinel.stranded_summary()
    codes = {j["code"] for j in s["recent"]}
    assert "STRNDREC" in codes
    assert not any(c.startswith("STRNDOLD") for c in codes)
    assert s["total"] > s["recent_total"]
