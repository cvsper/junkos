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


def _prospect(company="Palm Coast PM", digits="5615550142", status="interested",
              days_ago=5, note=None):
    p = CallProspect(id=generate_uuid(), tier=1, category="property management", company=company,
                     phone="(561) 555-0142", phone_digits=digits, city="Lake Worth",
                     contact_name="Marcus Bell", status=status, last_note=note)
    db.session.add(p); db.session.commit()
    # backdate LAST: `updated_at` has onupdate=now, so any later commit on this
    # row makes it look fresh again and it drops out of the nudge window.
    p.updated_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago)
    db.session.commit()
    return p


def test_the_offer_is_a_signed_link_that_knows_who_it_came_from():
    p = _prospect()
    url = first_job.offer_url(p)
    assert url.startswith("https://app.goumuve.com/partners/start?p=" + p.id)
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


def test_the_admin_preview_never_sends(client):
    _prospect()
    assert client.get("/api/admin/first-job/nudge").status_code == 401
    assert client.post("/api/admin/first-job/nudge").status_code == 401


# ---------------------------------------------------------------------------
# who must never be texted
# ---------------------------------------------------------------------------
def test_an_auto_responder_line_is_never_texted():
    """11 Sep: Maya's bot traded ~1,100 texts with apartment-office
    auto-responders overnight. Never again from this sweep."""
    p = _prospect(company="ParkLine Palm Beaches", digits="5615550170",
                  note=("[2026-09-11 17:31] THEY TEXTED: Reply YES to consent to text messages "
                        "from ParkLine Palm Beaches by Bozzuto Management"))
    assert first_job.skip_reason(p) == "their line is an auto-responder"
    assert p not in first_job.due_for_nudge()
    with mock.patch("desk_line.send_desk_text") as send:
        ok, why = first_job.send_offer(p)
    assert ok is False and why == "their line is an auto-responder" and send.call_count == 0


def test_a_number_that_cannot_receive_texts_is_never_texted():
    p = _prospect(company="Palms West Apartments", digits="5615550171",
                  note=("[2026-09-11 18:20] THEY TEXTED: We're sorry, text messages can't be "
                        "received by this phone number."))
    assert first_job.skip_reason(p) == "that number can't receive texts"
    with mock.patch("desk_line.send_desk_text") as send:
        ok, _ = first_job.send_offer(p)
    assert ok is False and send.call_count == 0


def test_a_normal_note_is_still_textable():
    p = _prospect(company="Colony Hotel", digits="5615550172",
                  note="Alani said they'll keep Umuve as a backup vendor.")
    assert first_job.skip_reason(p) is None
    assert p in first_job.due_for_nudge()


def test_the_sweep_reports_who_it_skipped():
    _prospect(company="Auto Line", digits="5615550173",
              note="THEY TEXTED: Reply START to receive SMS updates")
    _prospect(company="Real One", digits="5615550174")
    with mock.patch("flags.flag", return_value=True), \
         mock.patch("desk_line.send_desk_text", return_value="SM1") as send:
        out = first_job.nurture_sweep()
    assert out["sent"] == 1 and send.call_count == 1
    assert [s["company"] for s in out["skipped"]] == ["Auto Line"]


# ---------------------------------------------------------------- the partner request page
def _sig(p):
    return first_job.sign(p.id)


def test_the_link_greets_them_and_records_the_open(client):
    p = _prospect()
    assert client.get("/api/partners/offer?p=%s&s=nope" % p.id).status_code == 404
    r = client.get("/api/partners/offer?p=%s&s=%s" % (p.id, _sig(p)))
    assert r.status_code == 200
    j = r.get_json()
    assert j["company"] == "Palm Coast PM" and j["first_name"] == "Marcus"
    assert ("/rate-card/%s.pdf?s=" % p.id) in j["rate_card_url"]
    db.session.refresh(p)
    assert p.offer_opened_at is not None, "opening the link is the signal"
    first = p.offer_opened_at
    client.get("/api/partners/offer?p=%s&s=%s" % (p.id, _sig(p)))
    db.session.refresh(p)
    assert p.offer_opened_at == first, "the first open is the one that counts"
    # and the desk sees it as a lead
    import leads
    l = next(x for x in leads.collect()[0] if x["kind"] == "offer_open")
    assert l["what"].startswith("opened the booking link") and l["company"] == "Palm Coast PM"


def test_a_pickup_request_becomes_an_open_callback_with_everything_on_it(client):
    from models_inbound import CallbackRequest
    p = _prospect(status="queued")
    with mock.patch("desk_line.send_desk_text") as fwd, mock.patch("growth.notify_reply"), \
         mock.patch.dict(os.environ, {"DESK_FORWARD_NUMBER": "+15615550777"}):
        r = client.post("/api/partners/request", json={
            "p": p.id, "s": _sig(p), "what": "two sofas and a mattress from unit 4B",
            "address": "1200 S Dixie Hwy, West Palm Beach", "when": "tomorrow morning",
            "name": "Marcus Bell", "phone": "(561) 555-0199", "email": "marcus@palmcoast.com"})
    assert r.status_code == 200, r.get_json()
    cb = CallbackRequest.query.filter_by(status="open").one()
    assert cb.phone_digits == "5615550199"
    assert "Pickup request from Palm Coast PM" in cb.note and "unit 4B" in cb.note and "tomorrow morning" in cb.note
    db.session.refresh(p)
    assert p.status == "interested" and p.direct_phone == "5615550199" and p.email == "marcus@palmcoast.com"
    assert p.next_followup_at is not None
    assert fwd.call_count == 1, "the VA's cell hears about it"
    # a request with nothing in it is refused, plainly
    r = client.post("/api/partners/request", json={"p": p.id, "s": _sig(p), "what": ""})
    assert r.status_code == 400 and "what needs to go" in r.get_json()["error"]


def test_month_end_text_goes_once_to_vendor_listed_lines_that_take_texts():
    a = _prospect(company="Avalon PM", digits="5615550150", status="vendor_listed")
    b = _prospect(company="Texted Lately", digits="5615550151", status="vendor_listed")
    b.last_texted_at = first_job._now() - timedelta(days=3); db.session.commit()
    c = _prospect(company="Bot Line", digits="5615550152", status="vendor_listed",
                  note="THEY TEXTED: Thanks for contacting - reply START to receive updates")
    _prospect(company="Merely Interested", digits="5615550153", status="interested")
    with mock.patch("first_job._now", return_value=datetime(2026, 9, 26, 14, 30)):
        dry = first_job.vendor_month_end_sweep(dry_run=True)
    assert dry["companies"] == ["Avalon PM"], dry
    assert any(s["company"] == "Bot Line" for s in dry["skipped"])
    with mock.patch("first_job._now", return_value=datetime(2026, 9, 10, 14, 30)):
        assert first_job.vendor_month_end_sweep(dry_run=True)["due"] == 0, "not month end"
    with mock.patch("first_job._now", return_value=datetime(2026, 9, 26, 14, 30)), \
         mock.patch("desk_line.send_desk_text", return_value="SMv1") as send:
        out = first_job.vendor_month_end_sweep(dry_run=False)
    assert out["sent"] == 1 and send.call_count == 1
    body = send.call_args.args[1]
    assert body.startswith("Hi Marcus, it's Tracy with Umuve. Move-outs this week?") and "Reply STOP" in body
    db.session.refresh(a)
    assert a.last_texted_at is not None
    with mock.patch("first_job._now", return_value=datetime(2026, 9, 27, 14, 30)):
        assert first_job.vendor_month_end_sweep(dry_run=True)["due"] == 0, "once a month"
