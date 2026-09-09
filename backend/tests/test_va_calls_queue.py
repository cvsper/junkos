"""Call Desk self-loading: CSV import (Desktop list shapes), add-a-business,
and the queue view."""
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from models import db, CallProspect, CallAttempt
from va_calls import parse_tier, rows_from_csv


@pytest.fixture(autouse=True)
def passcode_env():
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code"}):
        yield


@pytest.fixture(autouse=True)
def clean(app):
    yield
    CallAttempt.query.delete(); CallProspect.query.delete(); db.session.commit()


def _va(client, path, payload):
    base = {"code": "test-code", "va_name": "Tracy"}
    base.update(payload)
    return client.post(path, json=base)


WEEKLY_CSV = """Tier,#,Company,Phone,City,What they do,Contact,Notes,Call status,Outcome
Tier 1 — Palm Beach County (LAUNCH MARKET — call first),1,Luxury Movers,951-316-6908,Boca Raton,"Residential/commercial moving, packing",Hunter,"CL post 8/16; local crew",,
Tier 2 — Broward,2,Dahill Junk Removal,(954) 235-1601,Pompano Beach,appliance removal + junk hauling,,RE-TOUCH — owner-operator,called,no answer
Tier 4 — Treasure Coast,3,Bad Row,555,Stuart,junk,,,,
"""
RETOUCH_CSV = """Tier,Company,Phone,City,What they do,Contact,Notes,Outcome
Tier 3 — 3,"Reliable Junk Removal Services, Inc",(786) 424-2950,Hollywood / Miramar,junk removal,,"RE-TOUCH (jul7) — south-Broward focus",
"""


def test_parse_tier_shapes():
    assert parse_tier("Tier 1 — Palm Beach County (LAUNCH MARKET — call first)") == 1
    assert parse_tier("Tier 2 — 2") == 2
    assert parse_tier("3") == 3
    assert parse_tier("Tier 4 — TC+inland") == 3      # clamps like the admin import
    assert parse_tier("") == 2 and parse_tier(None) == 2


def test_rows_from_desktop_csv():
    rows = rows_from_csv(WEEKLY_CSV)
    assert len(rows) == 3
    assert rows[0]["company"] == "Luxury Movers" and rows[0]["contact_name"] == "Hunter"
    assert rows[0]["category"].startswith("Residential") and rows[0]["why"].startswith("CL post")
    assert "Call status" not in rows[1] and "Outcome" not in rows[1] and "#" not in rows[1]


def test_va_import_csv_merges_and_reports(client):
    resp = _va(client, "/api/va/calls/import", {"csv": WEEKLY_CSV})
    assert resp.status_code == 200, resp.get_json()
    b = resp.get_json()
    assert (b["added"], b["skipped_dupes"], b["invalid"], b["total"]) == (2, 0, 1, 2)
    p = CallProspect.query.filter_by(phone_digits="9542351601").one()
    assert p.tier == 2 and p.status == "queued" and p.why.startswith("RE-TOUCH")
    # re-running the same file is a no-op; a re-touch list (different header shape) adds its row
    b = _va(client, "/api/va/calls/import", {"csv": WEEKLY_CSV}).get_json()
    assert b["added"] == 0 and b["skipped_dupes"] == 2 and b["total"] == 2
    b = _va(client, "/api/va/calls/import", {"csv": RETOUCH_CSV}).get_json()
    assert b["added"] == 1 and b["total"] == 3
    assert CallProspect.query.filter_by(phone_digits="7864242950").one().tier == 3
    # existing rows keep their history through a re-import
    p.status = "interested"; p.last_note = "keep me"; db.session.commit()
    _va(client, "/api/va/calls/import", {"csv": WEEKLY_CSV})
    db.session.refresh(p)
    assert p.status == "interested" and p.last_note == "keep me"


def test_va_import_json_rows_and_guards(client):
    rows = [{"tier": "2", "category": "junk removal", "company": "A", "phone": "(561) 555-0001"}]
    assert _va(client, "/api/va/calls/import", {"rows": rows}).get_json()["added"] == 1
    assert _va(client, "/api/va/calls/import", {}).status_code == 400
    assert _va(client, "/api/va/calls/import", {"csv": "Company,Phone\n"}).status_code == 400
    assert client.post("/api/va/calls/import", json={"code": "wrong", "csv": WEEKLY_CSV}).status_code == 401
    assert _va(client, "/api/va/calls/import", {"rows": [{"company": "x", "phone": "5615550002"}] * 2001}).status_code == 400


def test_add_business_opens_card_and_dedupes(client):
    resp = _va(client, "/api/va/calls/add", {"company": "Walk-in Movers", "phone": "561-555-0199",
                                              "city": "Lake Worth", "category": "moving company",
                                              "why": "called the desk line asking about jobs"})
    assert resp.status_code == 200
    b = resp.get_json()
    assert b["exists"] is False and b["card"]["company"] == "Walk-in Movers" and b["card"]["tier"] == 1
    again = _va(client, "/api/va/calls/add", {"company": "Walk-in Movers", "phone": "(561) 555-0199"}).get_json()
    assert again["exists"] is True and again["card"]["id"] == b["card"]["id"]
    assert _va(client, "/api/va/calls/add", {"company": "", "phone": "5615550100"}).status_code == 400
    assert _va(client, "/api/va/calls/add", {"company": "x", "phone": "123"}).status_code == 400


def test_queue_view_orders_due_then_fresh(client):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.add_all([
        CallProspect(tier=2, category="estate sales", company="Fresh T2", phone="5615550010", phone_digits="5615550010"),
        CallProspect(tier=1, category="property management", company="Fresh T1", phone="5615550011", phone_digits="5615550011"),
        CallProspect(tier=1, category="storage", company="Due Now", phone="5615550012", phone_digits="5615550012",
                     status="interested", next_followup_at=now - timedelta(hours=1), last_outcome="callback"),
        CallProspect(tier=1, category="storage", company="Later", phone="5615550013", phone_digits="5615550013",
                     next_followup_at=now + timedelta(days=2)),
        CallProspect(tier=1, category="storage", company="Dead", phone="5615550014", phone_digits="5615550014", status="dead"),
    ])
    db.session.commit()
    q = _va(client, "/api/va/calls/queue", {}).get_json()
    assert [r["company"] for r in q["due"]] == ["Due Now"]
    assert [r["company"] for r in q["fresh"]] == ["Fresh T1", "Fresh T2"]
    assert [r["company"] for r in q["later"]] == ["Later"]
    assert q["counts"]["due"] == 1 and q["counts"]["fresh"] == 2 and q["counts"]["total"] == 5
    assert q["counts"]["by_tier"] == {"1": 1, "2": 1}
    assert q["counts"]["by_status"]["dead"] == 1
    assert q["due"][0]["last_outcome"] == "callback"


def test_next_distinguishes_empty_queue_from_quiet_queue(client):
    b = _va(client, "/api/va/calls/next", {}).get_json()
    assert b["empty"] and b["total"] == 0 and b["scheduled"] == 0
    db.session.add(CallProspect(tier=1, category="storage", company="Later", phone="5615550013",
                                phone_digits="5615550013",
                                next_followup_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1)))
    db.session.commit()
    b = _va(client, "/api/va/calls/next", {}).get_json()
    assert b["empty"] and b["total"] == 1 and b["scheduled"] == 1 and b["next_due"]
