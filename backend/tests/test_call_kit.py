"""Call Kit + callback scheduler on the Call Desk."""
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from models import db, CallProspect, CallAttempt
from call_kit import detect_side, build_kit, demand_segment


@pytest.fixture(autouse=True)
def passcode_env():
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code"}):
        yield


@pytest.fixture()
def demand(app):
    p = CallProspect(tier=1, category="property management", company="Palm Coast PM",
                     phone="(561) 555-0100", phone_digits="5615550100", city="West Palm Beach")
    db.session.add(p); db.session.commit()
    yield p
    CallAttempt.query.delete(); db.session.delete(p); db.session.commit()


@pytest.fixture()
def hauler(app):
    p = CallProspect(tier=2, category="junk removal & hauling", company="Rob's Hauling",
                     phone="(954) 555-0100", phone_digits="9545550100", city="Lauderhill")
    db.session.add(p); db.session.commit()
    yield p
    CallAttempt.query.delete(); db.session.delete(p); db.session.commit()


def _va(client, path, payload):
    base = {"code": "test-code", "va_name": "Tracy"}
    base.update(payload)
    return client.post(path, json=base)


# ------------------------------------------------------------------ side + segment
def test_side_detection():
    mk = lambda cat, why="", angle="": CallProspect(category=cat, company="x", phone="1", phone_digits="1", why=why, angle=angle)
    assert detect_side(mk("junk removal")) == "supply"
    assert detect_side(mk("dumpster rental")) == "supply"
    assert detect_side(mk("used appliance dealer, delivers")) == "supply"
    assert detect_side(mk("property management")) == "demand"
    assert detect_side(mk("estate sales")) == "demand"
    # a mover is a referral partner unless the list says we're recruiting their truck
    assert detect_side(mk("moving company")) == "demand"
    assert detect_side(mk("moving company", angle="Has a truck — send them paid jobs")) == "supply"


def test_demand_segments():
    assert demand_segment("HOA management") == "property"
    assert demand_segment("estate sales") == "estate"
    assert demand_segment("real estate brokerage") == "realtor"
    assert demand_segment("restoration contractor") == "contractor"
    assert demand_segment("something odd") == "property"


# ------------------------------------------------------------------ kit content
def test_kit_demand_shape(client, demand):
    body = _va(client, "/api/va/calls/kit", {"prospect_id": demand.id}).get_json()
    assert body["side"] == "demand" and body["track"]["segment"] == "property"
    assert body["track"]["opener"].startswith("Hi, this is Tracy")
    assert len(body["track"]["discover"]) >= 2 and body["track"]["close"]
    assert any("already have a guy" in o["say"] for o in body["objections"])
    assert all("{va}" not in o["reply"] for o in body["objections"])
    assert any(a["q"] == "Insured?" for a in body["answers"])
    labels = [p["label"] for p in body["prices"]]
    assert "Sofa" in labels and "Hot tub" in labels
    assert all(isinstance(p["from"], int) and p["from"] > 0 for p in body["prices"])
    assert any(l["label"] == "Maps + reviews" and "Palm+Coast" in l["url"] for l in body["lookup"])


def test_kit_supply_shape_and_override(client, hauler, demand):
    body = _va(client, "/api/va/calls/kit", {"prospect_id": hauler.id}).get_json()
    assert body["side"] == "supply" and body["track"]["segment"] == "hauler"
    assert "keep the majority" in body["track"]["pitch"]
    assert any("JOBS" in a["a"] for a in body["answers"])
    assert not any("85%" in a["a"] for a in body["answers"])   # never promise a number the site doesn't
    # VA can flip the side for a mis-tagged card
    body = _va(client, "/api/va/calls/kit", {"prospect_id": demand.id, "side": "supply"}).get_json()
    assert body["side"] == "supply" and body["detected_side"] == "demand"


def test_kit_prices_survive_engine_failure(demand):
    with mock.patch("call_kit._estimate_total", return_value=None):
        kit = build_kit(demand)
    assert kit["prices"] and kit["prices"][0]["from"] > 0     # falls back to base price


def test_kit_auth(client, demand):
    assert client.post("/api/va/calls/kit", json={"code": "nope", "prospect_id": demand.id}).status_code == 401
    assert _va(client, "/api/va/calls/kit", {"prospect_id": "missing"}).status_code == 404


# ------------------------------------------------------------------ callback scheduler
def test_callback_preset_pins_followup_and_logs(client, demand):
    resp = _va(client, "/api/va/calls/callback",
               {"prospect_id": demand.id, "preset": "tomorrow_pm", "note": "asked for Pat"})
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["logged"] and "2:00 PM" in body["callback_local"]
    db.session.refresh(demand)
    assert demand.last_outcome == "callback" and demand.attempts == 1
    assert demand.last_note == "asked for Pat"
    assert demand.status == "queued"                      # still workable, cadence untouched
    delta = demand.next_followup_at - datetime.now(timezone.utc).replace(tzinfo=None)
    assert timedelta(hours=12) < delta < timedelta(hours=48)
    att = CallAttempt.query.filter_by(prospect_id=demand.id).one()
    assert att.outcome == "callback" and att.va_name == "Tracy"
    assert body["stats"]["calls_today"] == 1


def test_callback_custom_time_is_florida_local(client, demand):
    at = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%dT10:30")
    body = _va(client, "/api/va/calls/callback", {"prospect_id": demand.id, "at": at}).get_json()
    assert "10:30 AM" in body["callback_local"]
    db.session.refresh(demand)
    # stored as UTC: Florida 10:30 is 14:30 UTC (EDT) or 15:30 (EST)
    assert demand.next_followup_at.hour in (14, 15) and demand.next_followup_at.minute == 30


def test_callback_revives_dead_card(client, demand):
    demand.status = "dead"; db.session.commit()
    _va(client, "/api/va/calls/callback", {"prospect_id": demand.id, "preset": "next_week"})
    db.session.refresh(demand)
    assert demand.status == "interested"


def test_callback_rejects_past_and_garbage(client, demand):
    assert _va(client, "/api/va/calls/callback", {"prospect_id": demand.id}).status_code == 400
    assert _va(client, "/api/va/calls/callback", {"prospect_id": demand.id, "at": "2020-01-01T09:00"}).status_code == 400
    assert _va(client, "/api/va/calls/callback", {"prospect_id": demand.id, "at": "not a date"}).status_code == 400
    assert CallAttempt.query.count() == 0


def test_how_much_objection_uses_live_prices(client, demand):
    body = _va(client, "/api/va/calls/kit", {"prospect_id": demand.id}).get_json()
    sofa = next(p["from"] for p in body["prices"] if p["label"] == "Sofa")
    how_much = next(o["reply"] for o in body["objections"] if o["say"] == "How much?")
    assert "${}".format(sofa) in how_much and "{sofa}" not in how_much
