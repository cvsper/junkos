"""A business that said yes and never booked is still owed a first pickup.

On 1 Oct 2026 the desk had 18 "converted" prospects and 0 jobs ever. Converted
meant "they'll use us", and the queue then forgot them. Now a converted row
with no job comes back when a follow-up is due — and only then — and the owner
can list who said yes and never booked.
"""
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from models import db, CallProspect
from desk_auth import create_desk_user
from va_calls import next_card


@pytest.fixture(autouse=True)
def passcode_env():
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code"}):
        yield


@pytest.fixture()
def rows(app):
    past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    rows = [
        CallProspect(tier=1, category="property management", company="Said Yes LLC",
                     phone="5615550101", phone_digits="5615550101", status="converted",
                     next_followup_at=past),
        CallProspect(tier=1, category="property management", company="Real Customer Inc",
                     phone="5615550102", phone_digits="5615550102", status="converted",
                     job_id="job-1", job_value=180.0, next_followup_at=past),
        CallProspect(tier=1, category="property management", company="Forgotten Yes Co",
                     phone="5615550103", phone_digits="5615550103", status="converted"),
        CallProspect(tier=2, category="restaurant", company="Fresh Card Diner",
                     phone="5615550104", phone_digits="5615550104", status="queued"),
    ]
    db.session.add_all(rows)
    db.session.commit()
    yield rows
    for r in rows:
        db.session.delete(r)
    db.session.commit()


def test_converted_without_a_job_is_dealt_when_due(app, rows):
    assert next_card().company == "Said Yes LLC"


def test_converted_with_a_job_is_a_customer_not_a_card(app, rows):
    rows[0].next_followup_at = None
    db.session.commit()
    # Real Customer Inc is due too, but has a job — never dealt again.
    assert next_card().company == "Fresh Card Diner"


def test_converted_never_comes_back_as_a_fresh_card(app, rows):
    rows[0].next_followup_at = None
    db.session.commit()
    # Forgotten Yes Co has no follow-up set: it waits for someone to schedule one.
    assert next_card().company == "Fresh Card Diner"


def test_owner_can_list_who_said_yes_and_never_booked(app, client, rows):
    create_desk_user("boss2@goumuve.com", "Shamar", "manager", "pw-boss")
    tok = client.post("/api/desk/login", json={"email": "boss2@goumuve.com", "password": "pw-boss"}).get_json()["token"]
    r = client.get("/api/admin/call-prospects?status=converted&no_job=1", headers={"Authorization": "Bearer " + tok})
    assert r.status_code == 200
    names = sorted(x["company"] for x in r.get_json()["rows"])
    assert names == ["Forgotten Yes Co", "Said Yes LLC"]
    row = [x for x in r.get_json()["rows"] if x["company"] == "Said Yes LLC"][0]
    assert row["job_id"] is None and row["next_followup_at"] and "offer_sent_at" in row
    assert client.get("/api/admin/call-prospects").status_code == 401
