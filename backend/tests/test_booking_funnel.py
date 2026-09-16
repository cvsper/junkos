"""The website booking funnel is measured, and its drop-offs are callable.

The six-step booking page recorded nothing until step 6, and only then if a
valid email had been typed. Someone who gave an address, picked items, chose a
day, saw a locked price and closed the tab left no trace. The one dashboard
that claimed to measure quotes was counting the photo-AI `quotes` table, which
is a different feature, which is why it read zero in every price band.
"""
from datetime import datetime, timedelta, timezone

import pytest

from models import db, User, Job
from models_funnel import BookingFunnel
import booking_funnel


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture(autouse=True)
def clean(app):
    yield
    BookingFunnel.query.delete()
    Job.query.delete()
    User.query.delete()
    db.session.commit()


def _beacon(session_id="s1", **over):
    data = {"session_id": session_id, "step": 1}
    data.update(over)
    return booking_funnel.record(data)


def _age(row, minutes):
    """Push a row's last activity back so it counts as abandoned."""
    row.updated_at = _now() - timedelta(minutes=minutes)
    db.session.commit()
    return row


# --------------------------------------------------------------------------
# Recording
# --------------------------------------------------------------------------
def test_one_row_per_attempt_however_many_beacons():
    _beacon(step=1)
    _beacon(step=2)
    _beacon(step=3)
    assert BookingFunnel.query.count() == 1
    assert BookingFunnel.query.one().max_step == 3


def test_stepping_back_does_not_lower_the_furthest_step():
    _beacon(step=5)
    _beacon(step=2)
    row = BookingFunnel.query.one()
    assert row.step == 2 and row.max_step == 5


def test_a_beacon_without_a_session_id_is_ignored():
    assert booking_funnel.record({"step": 3}) is None
    assert BookingFunnel.query.count() == 0


def test_contact_details_are_kept_as_they_arrive():
    _beacon(step=5, estimatedPrice=389)
    _beacon(step=6, name="Cassie S.", phone="(561) 555-0142", email="Cassie@Example.com")
    row = BookingFunnel.query.one()
    assert row.quoted_price == 389.0
    assert row.phone_digits == "5615550142"
    assert row.email == "cassie@example.com"
    assert row.reachable is True


def test_a_session_with_no_contact_is_not_reachable():
    _beacon(step=5, estimatedPrice=200)
    assert BookingFunnel.query.one().reachable is False


def test_a_nonsense_step_cannot_break_the_row():
    _beacon(step="banana")
    _beacon(session_id="s2", step=99)
    assert BookingFunnel.query.filter_by(session_id="s1").one().step == 1
    assert BookingFunnel.query.filter_by(session_id="s2").one().step == 6


def test_a_silly_price_is_dropped_rather_than_stored():
    _beacon(step=5, estimatedPrice=-5)
    assert BookingFunnel.query.one().quoted_price is None


# --------------------------------------------------------------------------
# Abandonment
# --------------------------------------------------------------------------
def test_somebody_still_booking_is_not_treated_as_abandoned():
    _beacon(step=5, estimatedPrice=250, phone="5615550142")
    # They beaconed a moment ago — still typing.
    assert booking_funnel.open_leads() == []


def test_a_priced_session_that_stopped_becomes_a_lead():
    row = _beacon(step=5, estimatedPrice=250, phone="5615550142", name="Rod")
    _age(row, 45)
    leads = booking_funnel.open_leads()
    assert len(leads) == 1 and leads[0].quoted_price == 250.0


def test_an_abandoned_session_with_no_price_is_not_a_lead():
    row = _beacon(step=3, phone="5615550142")
    _age(row, 45)
    assert booking_funnel.open_leads() == []


def test_a_booked_session_is_never_chased():
    row = _beacon(step=6, estimatedPrice=250, phone="5615550142")
    _age(row, 45)
    booking_funnel.mark_converted(session_id="s1")
    assert booking_funnel.open_leads() == []


def test_conversion_is_matched_on_phone_when_the_id_is_missing():
    row = _beacon(step=6, estimatedPrice=250, phone="+1 (561) 555-0142")
    _age(row, 45)
    booking_funnel.mark_converted(phone="5615550142")
    db.session.refresh(row)
    assert row.converted is True


def test_conversion_is_matched_on_email_too():
    row = _beacon(step=6, estimatedPrice=250, email="rod@example.com")
    _age(row, 45)
    booking_funnel.mark_converted(email="ROD@example.com")
    db.session.refresh(row)
    assert row.converted is True


def test_marking_an_unknown_session_is_harmless():
    assert booking_funnel.mark_converted(session_id="nope") is None


# --------------------------------------------------------------------------
# The report
# --------------------------------------------------------------------------
def test_the_report_shows_where_people_leave():
    for i, step in enumerate([1, 1, 2, 3, 5, 5, 6]):
        _beacon(session_id="s%d" % i, step=step,
                estimatedPrice=200 if step >= 5 else None)
    out = booking_funnel.report(30)
    assert out["started"] == 7
    by_step = {s["step"]: s for s in out["steps"]}
    assert by_step[1]["reached"] == 7
    assert by_step[2]["reached"] == 5
    assert by_step[2]["lost_here"] == 2      # two never left the address step
    assert by_step[5]["reached"] == 3
    assert by_step[6]["reached"] == 1
    assert out["saw_a_price"] == 3


def test_somebody_mid_checkout_is_not_reported_as_walked_away():
    """The page and the call list must agree: a live session is not a lost one.

    Someone who saw a price two minutes ago is probably typing their card in.
    Counting them as walked away would put them on Tracy's call list and get
    them phoned mid-checkout.
    """
    _beacon(session_id="live", step=5, estimatedPrice=312, phone="5615550199")
    out = booking_funnel.report(30)
    assert out["saw_a_price"] == 1
    assert out["still_booking"] == 1
    assert out["saw_a_price_and_left"] == 0
    assert out["money_left_on_the_table"] == 0
    assert out["recoverable"] == []


def test_the_report_and_the_call_list_use_the_same_rule():
    row = _beacon(session_id="gone", step=5, estimatedPrice=312, phone="5615550199")
    _age(row, booking_funnel.ABANDON_AFTER_MINUTES + 5)
    out = booking_funnel.report(30)
    assert out["saw_a_price_and_left"] == 1 and out["still_booking"] == 0
    assert len(out["recoverable"]) == len(booking_funnel.open_leads()) == 1


def test_the_report_counts_the_money_that_walked():
    a = _beacon(session_id="a", step=5, estimatedPrice=389, phone="5615550142")
    b = _beacon(session_id="b", step=5, estimatedPrice=164)
    _age(a, 45); _age(b, 45)
    out = booking_funnel.report(30)
    assert out["saw_a_price_and_left"] == 2
    assert out["money_left_on_the_table"] == 553.0
    # Only one of them left a way to reach them.
    assert out["left_and_reachable"] == 1
    assert out["recoverable"][0]["phone"] == "5615550142"


def test_the_report_splits_by_where_they_came_from():
    _beacon(session_id="a", step=5, leadSource="meta", estimatedPrice=100)
    _beacon(session_id="b", step=2, leadSource="google")
    _beacon(session_id="c", step=2)
    out = booking_funnel.report(30)
    sources = {s["source"]: s for s in out["by_source"]}
    assert sources["meta"]["priced"] == 1
    assert sources["google"]["started"] == 1
    assert sources["direct"]["started"] == 1


def test_an_empty_funnel_reports_zeroes_not_an_error():
    out = booking_funnel.report(30)
    assert out["started"] == 0 and out["conversion"] == 0.0
    assert len(out["steps"]) == 6


# --------------------------------------------------------------------------
# The public beacon endpoint
# --------------------------------------------------------------------------
def test_the_endpoint_records_without_auth(client):
    r = client.post("/api/booking/funnel", json={"session_id": "web-1", "step": 4,
                                                 "estimatedPrice": 149})
    assert r.status_code == 200 and r.get_json()["success"] is True
    assert BookingFunnel.query.filter_by(session_id="web-1").one().max_step == 4


def test_the_endpoint_refuses_a_payload_with_no_session(client):
    r = client.post("/api/booking/funnel", json={"step": 2})
    assert r.status_code == 400
    assert BookingFunnel.query.count() == 0


def test_a_broken_beacon_never_returns_an_error_to_the_page(client, monkeypatch):
    """Analytics must not be able to break a booking."""
    import booking_funnel as bf
    monkeypatch.setattr(bf, "record", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    r = client.post("/api/booking/funnel", json={"session_id": "web-2", "step": 1})
    assert r.status_code == 200
    assert r.get_json()["success"] is False


# --------------------------------------------------------------------------
# It reaches the desk
# --------------------------------------------------------------------------
def test_an_abandoned_price_shows_up_in_the_lead_list():
    import leads
    row = _beacon(step=5, estimatedPrice=389, phone="5615550142", name="Cassie S.",
                  items=[{"name": "Couch"}, {"name": "Dresser"}])
    _age(row, 45)
    found = leads._funnel(_now() - timedelta(days=7))
    assert len(found) == 1
    lead = found[0]
    assert lead["phone_digits"] == "5615550142"
    assert lead["source"] == "web"
    assert "$389 quote" in lead["what"]
    assert "Couch" in lead["what"]


def test_a_paid_source_keeps_its_label_in_the_lead_list():
    import leads
    row = _beacon(step=5, estimatedPrice=200, phone="5615550142", leadSource="facebook")
    _age(row, 45)
    assert leads._funnel(_now() - timedelta(days=7))[0]["source"] == "meta"


def test_a_bad_row_can_be_removed():
    _beacon(session_id="smoke-1", step=5, estimatedPrice=275)
    assert booking_funnel.forget("smoke-1") is True
    assert BookingFunnel.query.count() == 0
    # Removing something that isn't there is not an error.
    assert booking_funnel.forget("smoke-1") is False


# --------------------------------------------------------------------------
# It shows up on the analytics page
# --------------------------------------------------------------------------
def test_the_analytics_payload_carries_the_website_funnel():
    import desk_analytics
    row = _beacon(step=5, estimatedPrice=389, phone="5615550142", name="Cassie S.")
    _age(row, 45)
    start = _now() - timedelta(days=7)
    end = _now()
    out = desk_analytics.desk_report(start, end, "7 days", 7, va=None, everyone=True)
    assert out["web"]["started"] == 1
    assert out["web"]["saw_a_price_and_left"] == 1
    assert out["web"]["recoverable"][0]["name"] == "Cassie S."


def test_a_va_does_not_see_the_website_funnel():
    """The recoverable list carries customer names and numbers."""
    import desk_analytics
    _beacon(step=5, estimatedPrice=389, phone="5615550142")
    start = _now() - timedelta(days=7)
    out = desk_analytics.desk_report(start, _now(), "7 days", 7, va="Tracy", everyone=False)
    assert "web" not in out


def test_the_analytics_page_has_the_website_sections():
    import desk_analytics
    html = desk_analytics.PAGE_HTML
    for node in ("t-web-steps", "t-web-src", "t-web-lost", 'id="web"'):
        assert node in html, node
