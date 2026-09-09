"""Maya pre-qualification (prequal.py + growth.py routes): who is eligible,
the calling window and daily cap on a mocked clock, the Vapi call payload,
the result webhook (secret + dispositions), and the manager/VA endpoints."""
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from models import db, User, AuditEvent, DeskSetting, CallProspect, CallAttempt
from models_growth import PrequalCall
from desk_auth import create_desk_user
import prequal

# Tue 2026-09-08 15:00 UTC = 11:00 ET (EDT) — inside the window.
IN_WINDOW = datetime(2026, 9, 8, 15, 0, tzinfo=timezone.utc)
EVENING = datetime(2026, 9, 8, 21, 0, tzinfo=timezone.utc)      # 17:00 ET
SUNDAY = datetime(2026, 9, 6, 15, 0, tzinfo=timezone.utc)

VAPI_ENV = {"PREQUAL_ENABLED": "true", "VAPI_API_KEY": "k", "VAPI_PHONE_NUMBER_ID": "pn_1",
            "PREQUAL_ASSISTANT_ID": "asst_prequal", "VAPI_SERVER_SECRET": "vapi-secret",
            "PREQUAL_DAILY_CAP": "2"}


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, dict(VAPI_ENV, TRIXIE_ASSISTANT_PASSCODE="test-code", JWT_SECRET="unit")):
        from flags import set_flag
        set_flag("maya_prequal", True)
        yield
    for m in (PrequalCall, CallAttempt, AuditEvent, DeskSetting):
        m.query.delete()
    CallProspect.query.delete()
    User.query.filter(User.email.in_(["boss@goumuve.com"])).delete(synchronize_session=False)
    db.session.commit()


def _prospect(company, digits, category="junk removal", **kw):
    p = CallProspect(tier=kw.pop("tier", 2), category=category, company=company,
                     phone="({}) {}-{}".format(digits[:3], digits[3:6], digits[6:]), phone_digits=digits, **kw)
    db.session.add(p); db.session.commit(); return p


def _va(client, path, payload=None):
    base = {"code": "test-code", "va_name": "Tracy"}
    base.update(payload or {})
    return client.post(path, json=base)


def _manager(client):
    create_desk_user("boss@goumuve.com", "Shamar", "manager", "pw-boss")
    tok = client.post("/api/desk/login", json={"email": "boss@goumuve.com", "password": "pw-boss"}).get_json()["token"]
    return {"Authorization": "Bearer " + tok}


def _ok_post(*a, **kw):
    return mock.Mock(status_code=201, json=lambda: {"id": "call_" + kw["json"]["customer"]["number"][-4:]}, text="")


# ------------------------------------------------------------------ eligibility + window
def test_eligible_rules(app):
    hauler = _prospect("Robs Hauling", "9545550100")
    assert prequal.eligible(hauler) is True
    assert prequal.eligible(_prospect("Palm Coast PM", "5615550142", category="property management")) is False
    assert prequal.eligible(_prospect("Tried Already", "5615550143", attempts=1)) is False
    assert prequal.eligible(_prospect("Warm Already", "5615550144", status="interested")) is False
    assert prequal.eligible(hauler, extra_filter=lambda p: p.city == "Miami") is False
    db.session.add(PrequalCall(prospect_id=hauler.id, disposition="pending")); db.session.commit()
    assert prequal.eligible(hauler) is False           # Maya never dials the same card twice


def test_calling_window_is_et_business_hours_mon_sat():
    assert prequal.in_window(IN_WINDOW) is True
    assert prequal.in_window(datetime(2026, 9, 12, 14, 0, tzinfo=timezone.utc)) is True     # Sat 10:00 ET
    assert prequal.in_window(datetime(2026, 9, 8, 13, 59, tzinfo=timezone.utc)) is False    # 09:59 ET
    assert prequal.in_window(datetime(2026, 9, 8, 20, 0, tzinfo=timezone.utc)) is False     # 16:00 ET
    assert prequal.in_window(EVENING) is False
    assert prequal.in_window(SUNDAY) is False
    assert prequal.in_window(datetime(2026, 1, 13, 15, 30, tzinfo=timezone.utc)) is True    # 10:30 EST in winter


# ------------------------------------------------------------------ run
def test_run_stays_dark_unless_every_gate_passes(app):
    _prospect("Robs Hauling", "9545550100")
    with mock.patch("requests.post") as post:
        with mock.patch.dict(os.environ, {"PREQUAL_ENABLED": ""}):
            assert prequal.run_prequal(now=IN_WINDOW)["reason"] == "PREQUAL_ENABLED != true"
        from flags import set_flag
        set_flag("maya_prequal", False)
        assert prequal.run_prequal(now=IN_WINDOW)["reason"] == "flag maya_prequal off"
        set_flag("maya_prequal", True)
        assert prequal.run_prequal(now=EVENING)["reason"] == "outside_window"
        assert prequal.run_prequal(now=SUNDAY)["reason"] == "outside_window"
    assert post.call_count == 0 and PrequalCall.query.count() == 0


def test_dry_run_lists_supply_cards_without_dialing(app):
    _prospect("Robs Hauling", "9545550100")
    _prospect("Palm Coast PM", "5615550142", category="property management")
    with mock.patch("requests.post") as post:
        res = prequal.run_prequal(dry_run=True, now=IN_WINDOW)
    assert [c["company"] for c in res["would_call"]] == ["Robs Hauling"] and res["room"] == 2
    assert post.call_count == 0 and PrequalCall.query.count() == 0


def test_run_places_capped_calls_with_prospect_metadata(app):
    a = _prospect("A Hauling", "9545550100", tier=1)
    b = _prospect("B Hauling", "9545550101", contact_name="Beth Jones")
    _prospect("C Hauling", "9545550102")
    with mock.patch("requests.post", side_effect=_ok_post) as post:
        res = prequal.run_prequal(now=IN_WINDOW)
    assert [c["company"] for c in res["called"]] == ["A Hauling", "B Hauling"]     # cap 2, tier first
    assert post.call_count == 2
    payload = post.call_args_list[1].kwargs["json"]
    assert payload["assistantId"] == "asst_prequal" and payload["phoneNumberId"] == "pn_1"
    assert payload["customer"] == {"number": "+19545550101", "name": "Beth"}
    assert payload["assistantOverrides"]["metadata"] == {"prequal_prospect_id": b.id, "purpose": "prequal"}
    assert post.call_args_list[1].kwargs["headers"]["Authorization"] == "Bearer k"
    rows = {r.prospect_id: r for r in PrequalCall.query.all()}
    assert rows[a.id].vapi_call_id == "call_0100" and rows[a.id].disposition == "pending"
    # the cap counts today's calls: the next tick is a no-op
    with mock.patch("requests.post", side_effect=_ok_post) as post:
        assert prequal.run_prequal(now=IN_WINDOW + timedelta(hours=1))["reason"] == "daily_cap"
    assert post.call_count == 0
    # tomorrow the cap resets and C is still eligible while A and B are not
    with mock.patch("requests.post", side_effect=_ok_post) as post:
        res = prequal.run_prequal(dry_run=True, now=IN_WINDOW + timedelta(days=1))
    assert [c["company"] for c in res["would_call"]] == ["C Hauling"]


def test_failed_vapi_call_is_recorded_not_retried_forever(app):
    p = _prospect("Robs Hauling", "9545550100")
    with mock.patch("requests.post", return_value=mock.Mock(status_code=500, text="boom")):
        res = prequal.run_prequal(now=IN_WINDOW)
    assert res["called"] == [] and res["attempted"] == 1
    assert PrequalCall.query.filter_by(prospect_id=p.id).one().disposition == "failed"
    assert prequal.eligible(p) is False


# ------------------------------------------------------------------ webhook
def _result(client, payload, secret="vapi-secret"):
    headers = {"X-Vapi-Secret": secret} if secret is not None else {}
    return client.post("/api/growth/prequal/result", json=payload, headers=headers)


def test_webhook_requires_the_vapi_secret(client):
    p = _prospect("Robs Hauling", "9545550100")
    assert _result(client, {"prospect_id": p.id, "disposition": "warm"}, secret=None).status_code == 401
    assert _result(client, {"prospect_id": p.id, "disposition": "warm"}, secret="wrong").status_code == 401
    assert PrequalCall.query.count() == 0 and db.session.get(CallProspect, p.id).status == "queued"


def test_webhook_warm_pins_an_immediate_callback(client):
    p = _prospect("Robs Hauling", "9545550100")
    db.session.add(PrequalCall(prospect_id=p.id, vapi_call_id="call_1", disposition="pending")); db.session.commit()
    r = _result(client, {"prospect_id": p.id, "disposition": "warm", "vapi_call_id": "call_1",
                         "summary": "Has a 16ft box truck, wants 3-4 jobs a week.", "transcript": "AI: Hi...\nUser: Yes"})
    assert r.status_code == 200 and r.get_json()["status"] == "interested"
    p = db.session.get(CallProspect, p.id)
    assert p.status == "interested" and p.last_outcome == "callback"
    assert p.next_followup_at <= datetime.now(timezone.utc).replace(tzinfo=None)     # due now
    assert p.last_note == "MAYA: Has a 16ft box truck, wants 3-4 jobs a week."
    att = CallAttempt.query.filter_by(prospect_id=p.id).one()
    assert (att.outcome, att.va_name) == ("callback", "Maya")
    row = PrequalCall.query.one()
    assert row.disposition == "warm" and row.transcript.startswith("AI: Hi") and row.resolved_at is not None
    ev = AuditEvent.query.filter_by(action="growth.prequal_result").one()
    assert ev.via == "vapi" and ev.meta["disposition"] == "warm"
    # the desk card now carries Maya's result
    q = _va(client, "/api/va/growth/prequal", {"prospect_id": p.id}).get_json()["prequal"]
    assert q["disposition"] == "warm" and q["summary"].startswith("Has a 16ft")


def test_webhook_cold_and_voicemail_follow_desk_cadence(client):
    cold = _prospect("Cold Co", "9545550100")
    vm = _prospect("VM Co", "9545550101")
    assert _result(client, {"prospect_id": cold.id, "disposition": "cold", "summary": "Retired last year"}).status_code == 200
    assert _result(client, {"prospect_id": vm.id, "disposition": "voicemail"}).status_code == 200
    cold = db.session.get(CallProspect, cold.id); vm = db.session.get(CallProspect, vm.id)
    assert cold.status == "dead" and cold.last_outcome == "not_interested" and cold.last_note == "MAYA: Retired last year"
    assert vm.status == "queued" and vm.attempts == 1 and vm.last_outcome == "voicemail"
    assert vm.next_followup_at is not None and vm.next_followup_at > datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=2)
    assert {r.disposition for r in PrequalCall.query.all()} == {"cold", "voicemail"}
    assert _result(client, {"prospect_id": vm.id, "disposition": "maybe"}).status_code == 400
    assert _result(client, {"prospect_id": "nope", "disposition": "warm"}).status_code == 400
    # a pending result is not shown on the card
    pend = _prospect("Pending Co", "9545550102")
    db.session.add(PrequalCall(prospect_id=pend.id, disposition="pending")); db.session.commit()
    assert _va(client, "/api/va/growth/prequal", {"prospect_id": pend.id}).get_json()["prequal"] is None


def test_webhook_accepts_a_raw_vapi_end_of_call_report(client):
    p = _prospect("Robs Hauling", "9545550100")
    report = {"message": {"type": "end-of-call-report", "summary": "Interested, has a trailer.",
                          "transcript": "AI: ...", "endedReason": "customer-ended-call",
                          "analysis": {"structuredData": {"outcome": "interested"}},
                          "call": {"id": "call_raw", "assistantOverrides": {"metadata": {"prequal_prospect_id": p.id, "purpose": "prequal"}}}}}
    assert _result(client, report).status_code == 200
    assert db.session.get(CallProspect, p.id).status == "interested"
    assert PrequalCall.query.one().vapi_call_id == "call_raw"
    # someone else's report (no prequal marker) is acknowledged, not applied
    other = {"message": {"type": "end-of-call-report", "call": {"assistantOverrides": {"metadata": {"purpose": "recruit"}}}}}
    r = _result(client, other)
    assert r.status_code == 200 and r.get_json()["ok"] is False


# ------------------------------------------------------------------ manager endpoints
def test_manager_prequal_run_and_stats(client):
    _prospect("Robs Hauling", "9545550100")
    assert _va(client, "/api/admin/growth/prequal-run", {"dry_run": True}).status_code == 403
    h = _manager(client)
    with mock.patch("prequal._now", return_value=IN_WINDOW), mock.patch("requests.post", side_effect=_ok_post) as post:
        r = client.post("/api/admin/growth/prequal-run", json={"dry_run": True}, headers=h)
        assert r.status_code == 200 and r.get_json()["dry_run"] is True
        assert [c["company"] for c in r.get_json()["would_call"]] == ["Robs Hauling"]
        assert post.call_count == 0
        r = client.post("/api/admin/growth/prequal-run", json={"dry_run": False}, headers=h)
        assert len(r.get_json()["called"]) == 1 and post.call_count == 1
        s = client.get("/api/admin/growth/prequal-stats", headers=h).get_json()
    assert s["enabled"] is True and s["daily_cap"] == 2 and s["called_today"] == 1 and s["in_window"] is True
    assert s["by_disposition"] == {"pending": 1} and s["total"] == 1
    assert AuditEvent.query.filter_by(action="growth.prequal_run").count() == 1
