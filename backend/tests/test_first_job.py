"""Turning "interested" into work.

sevs, 15 Sep: "how can we turn that 70 interested into revenue". In the 30
days before this, the desk logged 736 dials, 70 interested and 31 wins on $0
of revenue, because nothing ever asked them to book.
"""
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from models import db, CallProspect, Job, User, generate_uuid
import first_job


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code",
                                      "RATE_CARD_SECRET": "unit", "DESK_VA_NAME": "Tracy",
                                      "FRONTEND_URL": "https://app.goumuve.com"}):
        yield
    from models_crm import ProspectStage
    ProspectStage.query.delete()
    CallProspect.query.delete(); Job.query.delete(); User.query.delete()
    db.session.commit()


def _prospect(company="Palm Coast PM", digits="5615550142", status="interested", days_ago=5):
    p = CallProspect(id=generate_uuid(), tier=1, category="property management", company=company,
                     phone="(561) 555-0142", phone_digits=digits, city="Lake Worth",
                     contact_name="Marcus Bell", status=status)
    db.session.add(p); db.session.commit()
    p.updated_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago)
    db.session.commit()
    return p


def test_the_offer_is_a_signed_link_that_knows_who_it_came_from():
    p = _prospect()
    url = first_job.offer_url(p)
    assert url.startswith("https://app.goumuve.com/book?p=" + p.id)
    assert first_job.check_sig(p.id, url.split("s=")[1])
    assert not first_job.check_sig(p.id, "nope")


def test_the_offer_text_asks_for_the_booking():
    p = _prospect()
    body = first_job.offer_text(p)
    assert "Marcus" in body and "Tracy" in body
    assert "first pickup" in body and p.id in body and "STOP" in body


def test_sending_the_offer_is_recorded_and_not_repeated():
    p = _prospect()
    with mock.patch("desk_line.send_desk_text", return_value="SM1") as send:
        ok, why = first_job.send_offer(p)
    assert ok and why is None and p.offer_sent_at
    assert send.call_args[0][0] == "+15615550142"
    with mock.patch("desk_line.send_desk_text") as again:
        ok2, why2 = first_job.send_offer(p)
    assert ok2 is False and why2 == "already sent" and again.call_count == 0


def test_a_prospect_who_already_booked_is_not_asked_again():
    p = _prospect()
    p.job_id = "job-1"; db.session.commit()
    ok, why = first_job.send_offer(p)
    assert ok is False and "already have a job" in why


def test_a_booking_turns_the_prospect_into_real_revenue():
    p = _prospect()
    u = User(id=generate_uuid(), name="Marcus", phone="+15615550142",
             email="m@t.local", role="customer")
    db.session.add(u); db.session.flush()
    job = Job(id=generate_uuid(), customer_id=u.id, status="pending", address="12 Palm Way",
              items=[{"category": "sofa", "quantity": 1}], total_price=257.0,
              confirmation_code="FJ1")
    db.session.add(job); db.session.commit()
    with mock.patch("booking_alerts.ops_alert") as alert:
        out = first_job.link_booking(job, prospect_id=p.id)
    assert out.id == p.id
    db.session.refresh(p)
    assert p.job_id == job.id and p.job_value == 257.0 and p.status == "converted"
    from crm import current_stage
    assert current_stage(p.id) == "won"
    assert alert.call_count == 1                      # the one alert worth having
    # and it never double-credits
    assert first_job.link_booking(job, prospect_id=p.id) is None


def test_the_nudge_is_off_until_switched_on():
    _prospect()
    with mock.patch("desk_line.send_desk_text") as send:
        out = first_job.nurture_sweep()
    assert out["dry_run"] is True and out["due"] == 1 and out["sent"] == 0
    assert send.call_count == 0                       # ships silent, per the rule


def test_the_nudge_asks_once_when_it_is_on():
    p = _prospect()
    with mock.patch("flags.flag", return_value=True), \
         mock.patch("desk_line.send_desk_text", return_value="SM1") as send:
        out = first_job.nurture_sweep()
        again = first_job.nurture_sweep()
    assert out["sent"] == 1 and send.call_count == 1
    assert again["due"] == 0 and again["sent"] == 0    # never a second unprompted text
    db.session.refresh(p); assert p.offer_sent_at


def test_too_fresh_and_too_old_are_both_left_alone():
    _prospect(company="Yesterday", digits="5615550101", days_ago=1)      # too soon
    _prospect(company="Ancient", digits="5615550102", days_ago=60)       # gone cold
    _prospect(company="Just Right", digits="5615550103", days_ago=5)
    due = [p.company for p in first_job.due_for_nudge()]
    assert due == ["Just Right"]


def test_the_scoreboard_separates_claims_from_work():
    _prospect(company="Said Yes", digits="5615550111")
    booked = _prospect(company="Actually Booked", digits="5615550112")
    booked.job_id = "job-9"; booked.job_value = 300.0; db.session.commit()
    s = first_job.scoreboard(30)
    assert s["interested_now"] == 1                    # the booked one left that state
    assert s["booked_ever"] == 1 and s["revenue_in_window"] == 300.0
    assert s["waiting_on_an_offer"] == 1


def test_the_desk_route_is_gated(client):
    assert client.post("/api/va/calls/first-job", json={}).status_code == 401


def test_the_desk_can_send_the_offer(client):
    p = _prospect()
    with mock.patch("desk_line.send_desk_text", return_value="SM1"):
        r = client.post("/api/va/calls/first-job",
                        json={"code": "test-code", "va_name": "Tracy", "prospect_id": p.id})
    assert r.status_code == 200 and "Booking link sent" in r.get_json()["message"]
    db.session.refresh(p); assert p.offer_sent_at


# ---------------------------------------------------------------------------
# somebody who reached out beats a stranger
# ---------------------------------------------------------------------------
def test_the_cold_queue_yields_to_an_untouched_lead(client):
    """736 cold dials went out while inbound leads waited a median of 32 hours."""
    _prospect(company="Cold Call Me", digits="5615559999", status="queued")
    waiting = [{"kind": "thumbtack", "ref_id": "x1", "phone_digits": "5615550142",
                "phone": "(561) 555-0142", "name": "Dana Reyes", "what": "sectional",
                "source": "thumbtack", "source_label": "Thumbtack", "age_seconds": 400,
                "age_label": "6 min", "created_at": None, "contacts": 1}]
    with mock.patch("leads.untouched", return_value=waiting):
        r = client.post("/api/va/calls/next", json={"code": "test-code", "va_name": "Tracy"})
    body = r.get_json()
    assert r.status_code == 200 and body["leads_first"] is True
    assert body["waiting"] == 1 and body["paid"] == 1
    assert "card" not in body                       # no cold card while they wait
    assert body["leads"][0]["name"] == "Dana Reyes"


def test_a_lead_with_no_phone_number_does_not_block_the_queue(client):
    """It can't be called, so it must not stop the desk working."""
    _prospect(company="Cold Call Me", digits="5615559999", status="queued")
    with mock.patch("leads.untouched", return_value=[{"kind": "thumbtack", "ref_id": "x",
                                                      "phone_digits": None, "source": "thumbtack",
                                                      "age_seconds": 90}]):
        r = client.post("/api/va/calls/next", json={"code": "test-code", "va_name": "Tracy"})
    body = r.get_json()
    assert not body.get("leads_first") and body.get("card", {}).get("company") == "Cold Call Me"


def test_the_desk_can_still_get_a_card_when_it_has_to(client):
    _prospect(company="Cold Call Me", digits="5615559999", status="queued")
    waiting = [{"kind": "thumbtack", "ref_id": "x1", "phone_digits": "5615550142",
                "source": "thumbtack", "age_seconds": 400}]
    with mock.patch("leads.untouched", return_value=waiting):
        r = client.post("/api/va/calls/next", json={"code": "test-code", "va_name": "Tracy",
                                                    "skip_leads": True})
    assert r.get_json().get("card", {}).get("company") == "Cold Call Me"
