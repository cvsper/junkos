"""Card prep: generated angles (template + Claude), backfill, and live Google enrichment."""
import json
import os
from unittest import mock

import pytest

from models import db, CallProspect, DeskSetting
import enrich


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code", "ANTHROPIC_API_KEY": "",
                                      "GOOGLE_PLACES_API_KEY": ""}):
        yield
    DeskSetting.query.delete(); CallProspect.query.delete(); db.session.commit()


def _p(**kw):
    base = dict(tier=1, category="property management", company="Palm Coast PM", phone="(561) 555-0142",
                phone_digits="5615550142", city="West Palm Beach", why="340 doors across 6 buildings")
    base.update(kw)
    p = CallProspect(**base); db.session.add(p); db.session.commit()
    return p


def _va(client, path, payload):
    base = {"code": "test-code", "va_name": "Tracy"}
    base.update(payload or {})
    return client.post(path, json=base)


def test_template_angles_by_side_and_segment():
    assert "Standing account" in enrich.template_angle(_p())
    assert "keys back" in enrich.template_angle(_p(category="estate sales", phone_digits="1", phone="1"))
    assert "keep the majority" in enrich.template_angle(_p(category="junk removal & hauling", phone_digits="2", phone="2"))
    assert "return leg" in enrich.template_angle(_p(category="used appliance dealer, delivers", phone_digits="3", phone="3"))
    assert "roll-offs" in enrich.template_angle(_p(category="dumpster rental", phone_digits="4", phone="4"))


def test_card_shows_template_angle_when_blank(client):
    p = _p(angle=None)
    card = _va(client, "/api/va/calls/next", {}).get_json()["card"]
    assert card["angle"].startswith("Standing account") and card["angle_generated"] is True
    p.angle = "Hand-written angle"; db.session.commit()
    card = _va(client, "/api/va/calls/get", {"prospect_id": p.id}).get_json()["card"]
    assert card["angle"] == "Hand-written angle" and "angle_generated" not in card


def test_backfill_fills_only_blanks_and_uses_claude_when_keyed(app):
    blank = _p(angle=None)
    kept = _p(angle="keep me", phone_digits="5615550143", phone="(561) 555-0143", company="Other Co")
    assert enrich.fill_missing_angles(use_llm=False) == 1
    db.session.refresh(blank); db.session.refresh(kept)
    assert blank.angle.startswith("Standing account") and kept.angle == "keep me"
    assert json.loads(DeskSetting.get("angles:last"))["filled"] == 1
    # Claude path
    blank2 = _p(angle="", phone_digits="5615550144", phone="(561) 555-0144", company="Third Co", category="estate sales")
    fake = mock.MagicMock()
    fake.messages.create.return_value = mock.MagicMock(content=[mock.MagicMock(
        text='"Offer to clear every estate the Monday after the sale so the family gets the keys back fast."')])
    with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k"}), mock.patch("anthropic.Anthropic", return_value=fake):
        assert enrich.fill_missing_angles() == 1
    db.session.refresh(blank2)
    assert blank2.angle.startswith("Offer to clear every estate")
    assert "Third Co" in fake.messages.create.call_args.kwargs["messages"][0]["content"]
    # junk LLM output falls back to the template
    fake.messages.create.return_value = mock.MagicMock(content=[mock.MagicMock(text="ok")])
    blank3 = _p(angle=None, phone_digits="5615550145", phone="(561) 555-0145", company="Fourth Co")
    with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k"}), mock.patch("anthropic.Anthropic", return_value=fake):
        enrich.fill_missing_angles()
    db.session.refresh(blank3)
    assert blank3.angle.startswith("Standing account")


def test_backfill_endpoint_is_manager_only(client):
    _p(angle=None)
    assert _va(client, "/api/admin/angles/backfill", {}).status_code == 403      # passcode identity is a VA
    assert client.post("/api/admin/angles/backfill", json={"code": "wrong"}).status_code == 401
    from desk_auth import create_desk_user
    create_desk_user("boss2@goumuve.com", "Boss", "manager", "pw-boss2")
    tok = client.post("/api/desk/login", json={"email": "boss2@goumuve.com", "password": "pw-boss2"}).get_json()["token"]
    r = client.post("/api/admin/angles/backfill", json={"llm": False}, headers={"Authorization": "Bearer " + tok}).get_json()
    assert r["filled"] == 1 and r["remaining"] == 0
    from models import User
    User.query.filter_by(email="boss2@goumuve.com").delete(); db.session.commit()


def test_enrich_lookup_cache_and_dom_fallback(client):
    p = _p()
    place = {"displayName": {"text": "Palm Coast Property Management"}, "rating": 4.7, "userRatingCount": 212,
             "websiteUri": "https://palmcoastpm.com/", "currentOpeningHours": {"openNow": True},
             "regularOpeningHours": {"weekdayDescriptions": ["Monday: 9 AM – 5 PM"] * 7},
             "formattedAddress": "1 Main St, West Palm Beach, FL", "googleMapsUri": "https://maps.google.com/?cid=1",
             "businessStatus": "OPERATIONAL", "nationalPhoneNumber": "(561) 555-0142",
             "primaryTypeDisplayName": {"text": "Property management company"}}
    with mock.patch.dict(os.environ, {"GOOGLE_PLACES_API_KEY": "k"}), \
         mock.patch("enrich._places_lookup", return_value=place) as look:
        r = _va(client, "/api/va/calls/enrich", {"prospect_id": p.id}).get_json()
        assert r["found"] and r["rating"] == 4.7 and r["reviews"] == 212 and r["open_now"] is True
        assert r["website"].startswith("https://palmcoastpm.com") and r["hours_today"].endswith("5 PM")
        assert look.call_args[0][1] == "Palm Coast PM West Palm Beach FL"
        # cached: second call doesn't hit Places; DOM-style lookup by phone text works
        r2 = _va(client, "/api/va/calls/enrich", {"company": "Palm Coast PM", "phone": "(561) 555-0142"}).get_json()
        assert r2["found"] and look.call_count == 1
        assert "_at" not in r2
        # force refresh hits again
        _va(client, "/api/va/calls/enrich", {"prospect_id": p.id, "force": True})
        assert look.call_count == 2
    # no key → honest miss
    r3 = _va(client, "/api/va/calls/enrich", {"prospect_id": p.id, "force": True}).get_json()
    assert r3["found"] is False and r3["reason"] == "no places key"
    assert _va(client, "/api/va/calls/enrich", {"company": "Nobody Inc", "phone": "000"}).status_code == 404
