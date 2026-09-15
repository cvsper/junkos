"""Thumbtack webhook → desk lead list, first text, alerts, admin visibility."""
import base64
import os
from unittest import mock

import pytest

from models import db
from models_thumbtack import ThumbtackLead


LEAD = {
    "leadID": "299999",
    "createTimestamp": "1757800000",
    "leadType": "phone",
    "leadPrice": "18.50",
    "customer": {"customerID": "c1", "name": "Dana Reyes", "phone": "(561) 555-0142"},
    "business": {"businessID": "b1", "name": "Umuve"},
    "request": {
        "category": "Junk Removal", "categoryID": "cat1", "title": "Junk Removal",
        "description": "Old sectional and a treadmill in the garage.",
        "schedule": "This week",
        "location": {"address1": "12 Palm Way", "city": "Lake Worth", "state": "FL", "zipCode": "33460"},
        "details": [{"question": "What needs removal?", "answer": "Furniture"}],
        "attachments": [{"fileName": "pile.jpg", "mimeType": "image/jpeg", "url": "https://x/pile.jpg"}],
    },
}


def _basic(u="umuve", p="s3cret"):
    return {"Authorization": "Basic " + base64.b64encode("{}:{}".format(u, p).encode()).decode()}


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {"THUMBTACK_WEBHOOK_USER": "umuve", "THUMBTACK_WEBHOOK_PASSWORD": "s3cret",
                                      "DESK_VA_NAME": "Tracy"}):
        yield
    from leads import LeadTouch
    LeadTouch.query.filter_by(kind="thumbtack").delete()
    ThumbtackLead.query.delete()
    db.session.commit()


def test_auth_fail_closed_and_basic(client):
    with mock.patch.dict(os.environ, {"THUMBTACK_WEBHOOK_USER": "", "THUMBTACK_WEBHOOK_PASSWORD": ""}):
        assert client.post("/api/webhooks/thumbtack/lead", json=LEAD).status_code == 503
    assert client.post("/api/webhooks/thumbtack/lead", json=LEAD).status_code == 401
    assert client.post("/api/webhooks/thumbtack/lead", json=LEAD, headers=_basic(p="wrong")).status_code == 401


def test_lead_is_filed_texted_alerted_and_listed(client):
    with mock.patch("desk_line.send_desk_text", return_value="SM1") as send, \
         mock.patch("thumbtack.alert_team") as alert, \
         mock.patch("inbound.humans_online", return_value=False):
        r = client.post("/api/webhooks/thumbtack/lead", json=LEAD, headers=_basic())
    assert r.status_code == 200 and r.get_json()["created"] is True
    lead = ThumbtackLead.query.filter_by(lead_id="299999").one()
    assert lead.customer_name == "Dana Reyes" and lead.phone_digits == "5615550142" and lead.city == "Lake Worth"
    assert lead.category == "Junk Removal" and lead.attachments[0]["url"] == "https://x/pile.jpg" and lead.lead_price == 18.5
    assert lead.raw["leadID"] == "299999" and lead.text_sent_at and lead.status == "replied"
    to, body = send.call_args[0][0], send.call_args[0][1]
    assert to == "+15615550142" and "Thumbtack" in body and "Dana" in body and "photo" in body and "STOP" in body
    assert alert.call_count == 1
    # it shows in the desk's lead list first, marked auto-texted so the sweep leaves it alone
    from leads import collect
    leads, broken = collect()
    assert "thumbtack" not in broken
    mine = [l for l in leads if l["kind"] == "thumbtack"]
    assert mine and mine[0]["source_label"] == "Thumbtack" and mine[0]["phone_digits"] == "5615550142"
    assert mine[0]["auto_text_at"] and mine[0]["photos"] == 1 and leads[0]["kind"] == "thumbtack"
    # same lead again: no second row, no second text
    with mock.patch("desk_line.send_desk_text", return_value="SM2") as send2, mock.patch("thumbtack.alert_team"):
        r2 = client.post("/api/webhooks/thumbtack/lead", json=LEAD, headers=_basic())
    assert r2.get_json()["created"] is False and send2.call_count == 0 and ThumbtackLead.query.count() == 1


def test_kill_switch_stops_the_text_but_keeps_the_lead(client):
    with mock.patch("flags.flag", return_value=False), mock.patch("desk_line.send_desk_text") as send, \
         mock.patch("thumbtack.alert_team"):
        client.post("/api/webhooks/thumbtack/lead", json=LEAD, headers=_basic())
    lead = ThumbtackLead.query.one()
    assert send.call_count == 0 and lead.text_sent_at is None and lead.status == "new"


def test_message_appends_reopens_clock_and_alerts(client):
    with mock.patch("desk_line.send_desk_text", return_value="SM1"), mock.patch("thumbtack.alert_team"):
        client.post("/api/webhooks/thumbtack/lead", json=LEAD, headers=_basic())
    msg = {"leadID": "299999", "messageID": "m1", "message": {"text": "Can you come Saturday?", "sender": "customer"}}
    with mock.patch("thumbtack.alert_team") as alert:
        r = client.post("/api/webhooks/thumbtack/message", json=msg, headers=_basic())
        r_dup = client.post("/api/webhooks/thumbtack/message", json=msg, headers=_basic())
    assert r.status_code == 200 and r.get_json()["created"] and r_dup.get_json()["created"] is False
    lead = ThumbtackLead.query.one()
    assert lead.messages[-1]["text"] == "Can you come Saturday?" and alert.call_count == 1
    from leads import collect
    mine = [l for l in collect()[0] if l["kind"] == "thumbtack"][0]
    assert "they said: Can you come Saturday?" in mine["what"] and not mine["touched_at"]


def test_unknown_shape_is_kept_raw_and_answered_200(client):
    with mock.patch("thumbtack.alert_team"):
        r = client.post("/api/webhooks/thumbtack", json={"something": "else", "phone": "561-555-0199"}, headers=_basic())
    assert r.status_code == 200
    lead = ThumbtackLead.query.one()
    assert lead.phone_digits == "5615550199" and lead.raw["something"] == "else"
    from thumbtack import RECENT_EVENTS
    assert RECENT_EVENTS[0]["payload"]["something"] == "else"


def test_admin_events_route(client):
    assert client.get("/api/admin/thumbtack/events").status_code == 401


# The exact body Thumbtack POSTed to us on 15 Sep 2026 — every field name here
# is real, not from their docs (the docs' flat shape was wrong on every count).
REAL = {
    "event": {"eventType": "NegotiationCreatedV4", "triggeredAt": "2026-09-15T04:02:29Z",
              "webhookID": "590298304139583503", "description": ""},
    "data": {
        "negotiationID": "590299344770662410",
        "status": "Open", "chargeState": "Created", "createdAt": "2026-09-15T04:02:24Z",
        "leadPrice": "$25.00",
        "leadPriceBreakdown": {"salesTax": "$1.85", "subtotal": "$23.15"},
        "business": {"businessID": "590297085345701895", "name": "Griffis Property Group"},
        "customer": {"customerID": "590299344770162703", "firstName": "Dana",
                     "lastName": "Reyes", "phone": "5615550142"},
        "estimate": {"total": "$150.00", "pricePerUnit": "150.00", "type": "Fixed",
                     "unitName": "service", "unitQuantity": 1},
        "request": {
            "requestID": "590299344772112393",
            "category": {"categoryID": "240123621172183344", "name": "Junk Removal"},
            "description": "Need a sectional and two mattresses gone",
            "location": {"address1": "123 Main St", "address2": "Apt 4B",
                         "city": "Lake Worth", "state": "FL", "zipCode": "33460"},
            "details": [{"question": "Frequency of services", "answer": "One time only"}],
            "proposedTimes": [{"start": "2026-09-16T10:00:00Z", "end": "2026-09-16T11:00:00Z"}],
            "attachments": [{"fileName": "pile.jpg", "mimeType": "image/jpeg",
                             "fileSize": 20, "url": "https://x/pile.jpg"}],
            "travelPreferences": ["ProviderTravelToCustomer"],
        },
    },
}


def test_the_real_wrapped_payload_parses():
    """Their body is under `data`, the id is negotiationID, the name is split,
    category is an object and money is a string like "$25.00"."""
    from thumbtack import parse_lead, _infer_kind
    assert _infer_kind(REAL) == "lead"
    d = parse_lead(REAL)
    assert d["lead_id"] == "590299344770662410"
    assert d["business_id"] == "590297085345701895"
    assert d["customer_name"] == "Dana Reyes"
    assert d["phone_digits"] == "5615550142" and d["phone"] == "(561) 555-0142"
    assert d["lead_price"] == 25.0                      # from "$25.00"
    assert d["category"] == "Junk Removal"
    assert d["city"] == "Lake Worth" and d["state"] == "FL" and d["zip"] == "33460"
    assert d["address"] == "123 Main St, Apt 4B"
    assert "sectional" in d["description"]
    assert d["schedule"] == "2026-09-16T10:00:00Z to 2026-09-16T11:00:00Z"
    assert d["attachments"][0]["url"] == "https://x/pile.jpg"
    assert d["details"][0]["question"] == "Frequency of services"


def test_the_real_payload_reaches_the_desk_and_the_customer(client):
    with mock.patch("desk_line.send_desk_text", return_value="SM1") as send, \
         mock.patch("thumbtack.alert_team"), mock.patch("inbound.humans_online", return_value=False):
        r = client.post("/api/webhooks/thumbtack", json=REAL, headers=_basic())
    assert r.status_code == 200 and r.get_json()["kind"] == "lead"
    lead = ThumbtackLead.query.one()
    assert lead.customer_name == "Dana Reyes" and lead.lead_price == 25.0
    assert send.call_args[0][0] == "+15615550142"
    assert "junk removal" in send.call_args[0][1].lower()
    from leads import collect
    assert collect()[0][0]["kind"] == "thumbtack"


def test_thumbtacks_own_webhook_test_is_never_texted(client):
    """Their test payload carries a fake customer and a fake number."""
    import copy
    t = copy.deepcopy(REAL)
    t["data"]["business"]["name"] = "Test Business for Webhooks"
    t["data"]["customer"].update({"firstName": "Test", "lastName": "Customer",
                                  "phone": "1234567890"})
    with mock.patch("desk_line.send_desk_text") as send, mock.patch("thumbtack.alert_team") as alert:
        r = client.post("/api/webhooks/thumbtack", json=t, headers=_basic())
    assert r.status_code == 200
    assert send.call_count == 0                      # nobody gets a text
    assert alert.call_count == 1                     # but we still hear about it
    assert ThumbtackLead.query.one().status == "test"


def test_a_refused_call_leaves_a_trace(client):
    """Otherwise "they never called" and "we turned them away" look the same."""
    from thumbtack import REJECTED
    REJECTED.clear()
    with mock.patch.dict(os.environ, {"THUMBTACK_WEBHOOK_USER": "", "THUMBTACK_WEBHOOK_PASSWORD": ""}):
        assert client.post("/api/webhooks/thumbtack/lead", json=LEAD).status_code == 503
    assert REJECTED and "not configured" in REJECTED[0]["why"]
    assert REJECTED[0]["path"].endswith("/lead") and REJECTED[0]["had_auth"] is False
    client.post("/api/webhooks/thumbtack/lead", json=LEAD, headers=_basic(p="wrong"))
    assert "credentials" in REJECTED[0]["why"] and REJECTED[0]["had_auth"] is True


# ---------------------------------------------------------------------------
# using the feed: only pay attention to work we can do, and measure the rest
# ---------------------------------------------------------------------------
import copy


def _lead_payload(category="Junk Removal", city="Lake Worth", state="FL", zipc="33460", price="$25.00"):
    p = copy.deepcopy(REAL)
    p["data"]["request"]["category"]["name"] = category
    p["data"]["request"]["location"].update({"city": city, "state": state, "zipCode": zipc})
    p["data"]["leadPrice"] = price
    p["data"]["negotiationID"] = "neg-" + category[:6] + city[:4] + zipc
    return p


def test_a_lawn_care_lead_is_not_texted_and_is_counted_as_waste(client):
    """Thumbtack charges either way — the point is to stop bothering the
    customer and to total up what their targeting is costing us."""
    with mock.patch("desk_line.send_desk_text") as send, mock.patch("thumbtack.alert_team") as alert:
        r = client.post("/api/webhooks/thumbtack", json=_lead_payload(category="Full Service Lawn Care"),
                        headers=_basic())
    assert r.status_code == 200
    lead = ThumbtackLead.query.one()
    assert lead.serviceable is False and lead.status == "not_serviceable"
    assert "not junk removal" in (lead.service_note or "")
    assert send.call_count == 0                     # nobody gets a text
    assert "NOT SERVICEABLE" in alert.call_args.kwargs.get("extra", "")
    from leads import collect
    assert not [l for l in collect()[0] if l["kind"] == "thumbtack"]   # off Tracy's list


def test_a_lead_outside_the_service_area_is_not_texted(client):
    with mock.patch("desk_line.send_desk_text") as send, mock.patch("thumbtack.alert_team"), \
         mock.patch("sameday.geocode", return_value=(41.88, -87.63)):     # Chicago
        client.post("/api/webhooks/thumbtack", json=_lead_payload(city="Chicago", state="IL", zipc="60601"),
                    headers=_basic())
    lead = ThumbtackLead.query.one()
    assert lead.serviceable is False and "outside the service area" in (lead.service_note or "")
    assert send.call_count == 0


def test_a_real_junk_lead_in_area_is_texted(client):
    with mock.patch("desk_line.send_desk_text", return_value="SM1") as send, \
         mock.patch("thumbtack.alert_team"), mock.patch("inbound.humans_online", return_value=False), \
         mock.patch("sameday.geocode", return_value=(26.62, -80.05)):
        client.post("/api/webhooks/thumbtack", json=_lead_payload(), headers=_basic())
    lead = ThumbtackLead.query.one()
    assert lead.serviceable is True and lead.county == "Palm Beach" and lead.text_sent_at
    assert send.call_count == 1


def test_a_review_is_stored_not_just_announced(client):
    from models_thumbtack import ThumbtackReview
    payload = {"event": {"eventType": "ReviewCreatedV1"},
               "data": {"negotiationID": "590299344770662410",
                        "customer": {"firstName": "Dana", "lastName": "Reyes"},
                        "review": {"reviewID": "rev-1", "rating": 5, "text": "Fast and clean."}}}
    with mock.patch("thumbtack.alert_team") as alert:
        r = client.post("/api/webhooks/thumbtack", json=payload, headers=_basic())
        dup = client.post("/api/webhooks/thumbtack", json=payload, headers=_basic())
    assert r.status_code == 200 and r.get_json()["kind"] == "review"
    assert dup.get_json()["created"] is False          # Thumbtack retries
    row = ThumbtackReview.query.one()
    assert row.rating == 5.0 and "Fast and clean" in row.text and row.reviewer == "Dana Reyes"
    assert "5★" in alert.call_args.kwargs.get("extra", "")
    ThumbtackReview.query.delete(); db.session.commit()


def test_the_report_shows_spend_waste_and_where_the_demand_is(client):
    from thumbtack import report, link_booking
    from models import Job, User, generate_uuid
    with mock.patch("desk_line.send_desk_text", return_value="SM1"), mock.patch("thumbtack.alert_team"), \
         mock.patch("inbound.humans_online", return_value=False), \
         mock.patch("sameday.geocode", return_value=(26.62, -80.05)):
        client.post("/api/webhooks/thumbtack", json=_lead_payload(zipc="33460"), headers=_basic())
    with mock.patch("desk_line.send_desk_text"), mock.patch("thumbtack.alert_team"):
        client.post("/api/webhooks/thumbtack",
                    json=_lead_payload(category="Lawn Mowing", zipc="33461", price="$18.00"),
                    headers=_basic())
    cust = User(id=generate_uuid(), name="Dana Reyes", phone="+15615550142",
                email="{}@t.local".format(generate_uuid()[:8]), role="customer")
    db.session.add(cust); db.session.flush()
    job = Job(id=generate_uuid(), customer_id=cust.id, status="pending", address="12 Palm Way",
              items=[{"category": "sofa", "quantity": 1}], total_price=392.36, confirmation_code="TT1")
    db.session.add(job); db.session.commit()
    assert link_booking(job, digits="5615550142") is not None

    rep = report(30)
    assert rep["leads"] == 2 and rep["spend"] == 43.0
    assert rep["booked"] == 1 and rep["revenue"] == 392.36
    assert rep["cost_per_booking"] == 43.0 and rep["return_on_spend"] > 9
    assert rep["not_serviceable"] == 1 and rep["wasted_spend"] == 18.0
    assert "Junk Removal" in rep["by_category"] and rep["by_county"]["Palm Beach"]["booked"] == 1
    assert rep["median_reply_seconds"] is not None


def test_the_report_route_is_admin_only(client):
    assert client.get("/api/admin/thumbtack/report").status_code == 401
