"""Call Desk CRM (Phase 3): stages + aging, tags, claims, history, accounts,
win alerts, end-of-shift report, role gating."""
import json
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from models import db, CallProspect, CallAttempt, DeskActivity, DeskSetting, VaShift, AuditEvent, User
from models_crm import ProspectStage, ProspectTag, ProspectClaim, Account, AccountContact, normalize_account_name
import crm
from crm import on_outcome, current_stage, crm_card_fields, next_unclaimed, build_shift_report
from desk_auth import create_desk_user


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code", "JWT_SECRET": "unit",
                                      "CRM_ALERT_ON_INTERESTED": ""}):
        yield
    for m in (AccountContact, Account, ProspectClaim, ProspectTag, ProspectStage, DeskActivity,
              CallAttempt, VaShift, DeskSetting, AuditEvent, CallProspect):
        m.query.delete()
    User.query.filter(User.email.in_(["tracy@goumuve.com", "boss@goumuve.com"])).delete(synchronize_session=False)
    db.session.commit()


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _p(company="Palm Coast Property Group", phone="5615550100", **kw):
    kw.setdefault("tier", 1); kw.setdefault("category", "property management")
    p = CallProspect(company=company, phone=phone, phone_digits=phone, **kw)
    db.session.add(p); db.session.commit()
    return p


def _va(client, path, payload=None, name="Tracy"):
    base = {"code": "test-code", "va_name": name}
    base.update(payload or {})
    return client.post(path, json=base)


def _login(client, email, pw):
    return client.post("/api/desk/login", json={"email": email, "password": pw}).get_json()["token"]


def _h(tok):
    return {"Authorization": "Bearer " + tok}


@pytest.fixture()
def accounts():
    create_desk_user("tracy@goumuve.com", "Tracy Jamesyoung", "va", "pw-tracy")
    create_desk_user("boss@goumuve.com", "Shamar", "manager", "pw-boss")


# ---------------------------------------------------------------------------
# stages
# ---------------------------------------------------------------------------

def test_outcomes_move_stages_forward_only(client):
    p = _p()
    assert current_stage(p.id) == "new"
    on_outcome(p, "voicemail", "", "Tracy"); db.session.commit()
    assert current_stage(p.id) == "contacted"
    on_outcome(p, "interested", "wants prices", "Tracy"); db.session.commit()
    assert current_stage(p.id) == "engaged"
    # a later voicemail doesn't demote an engaged prospect
    on_outcome(p, "no_answer", "", "Tracy"); db.session.commit()
    assert current_stage(p.id) == "engaged"
    on_outcome(p, "skip", "", "Tracy"); db.session.commit()
    assert current_stage(p.id) == "engaged"
    on_outcome(p, "converted", "", "Tracy"); db.session.commit()
    assert current_stage(p.id) == "won"
    stages = [s.stage for s in ProspectStage.query.filter_by(prospect_id=p.id).order_by(ProspectStage.entered_at).all()]
    assert stages == ["contacted", "engaged", "won"]
    assert AuditEvent.query.filter_by(action="stage", target_id=p.id).count() == 3


def test_terminal_and_lateral_stages_and_callback(client):
    a, b, c, d = _p("A", "5615550001"), _p("B", "5615550002"), _p("C", "5615550003"), _p("D", "5615550004")
    on_outcome(a, "not_interested", "", "T"); on_outcome(b, "vendor_listed", "", "T")
    on_outcome(c, "callback", "", "T"); on_outcome(d, "interested", "", "T"); on_outcome(d, "callback", "", "T")
    db.session.commit()
    assert current_stage(a.id) == "lost" and current_stage(b.id) == "nurture"
    assert current_stage(c.id) == "contacted"          # callback on a new card → contacted
    assert current_stage(d.id) == "engaged"            # callback keeps an engaged card engaged
    on_outcome(a, "interested", "", "T"); db.session.commit()
    assert current_stage(a.id) == "engaged"            # a lost card can come back


def test_log_endpoint_drives_stage_and_card_fields(client):
    p = _p()
    r = _va(client, "/api/va/calls/log", {"prospect_id": p.id, "outcome": "interested", "note": "call back Thu"})
    assert r.status_code == 200
    card = _va(client, "/api/va/calls/get", {"prospect_id": p.id}).get_json()["card"]
    assert card["stage"] == "engaged" and card["stage_age_days"] == 0 and card["stage_entered_at"]
    assert card["tags"] == [] and card["account"] is None and card["claimed_by"] is None
    assert len(card["history"]) == 1
    h = card["history"][0]
    assert set(h) == {"id", "outcome", "note", "va_name", "created_at"}
    assert h["outcome"] == "interested" and h["note"] == "call back Thu" and h["va_name"] == "Tracy"


def test_history_is_newest_first_and_capped_at_ten(client):
    p = _p()
    base = _now() - timedelta(days=1)
    for i in range(12):
        db.session.add(CallAttempt(prospect_id=p.id, outcome="voicemail", note="n%d" % i, va_name="Tracy",
                                   created_at=base + timedelta(minutes=i)))
    db.session.commit()
    hist = crm_card_fields(p)["history"]
    assert len(hist) == 10
    assert [h["note"] for h in hist][:3] == ["n11", "n10", "n9"]


def test_pipeline_counts_aging_and_oldest(client):
    now = _now()
    fresh = _p("Fresh", "5615550011")
    old_eng = _p("Old Engaged", "5615550012")
    mid_eng = _p("Mid Engaged", "5615550013")
    lost = _p("Lost", "5615550014")
    db.session.add_all([
        ProspectStage(prospect_id=old_eng.id, stage="engaged", entered_at=now - timedelta(days=40)),
        ProspectStage(prospect_id=mid_eng.id, stage="contacted", entered_at=now - timedelta(days=10)),
        ProspectStage(prospect_id=mid_eng.id, stage="qualified", entered_at=now - timedelta(days=5)),
        ProspectStage(prospect_id=lost.id, stage="lost", entered_at=now - timedelta(days=3)),
    ])
    db.session.commit()
    r = _va(client, "/api/va/crm/pipeline").get_json()
    assert r["counts"]["new"] == 1 and r["counts"]["engaged"] == 1 and r["counts"]["qualified"] == 1 and r["counts"]["lost"] == 1
    assert r["aging"] == {"0-2d": 1, "3-7d": 1, "8-30d": 0, "30d+": 1}     # lost isn't aged
    assert [o["company"] for o in r["oldest"]] == ["Old Engaged", "Mid Engaged"]
    assert r["oldest"][0]["stage_age_days"] == 40
    # manual move to qualified
    r = _va(client, "/api/va/crm/stage", {"prospect_id": fresh.id, "stage": "qualified"}).get_json()
    assert r["stage"] == "qualified" and r["changed"] is True
    assert _va(client, "/api/va/crm/stage", {"prospect_id": fresh.id, "stage": "bogus"}).status_code == 400


# ---------------------------------------------------------------------------
# tags
# ---------------------------------------------------------------------------

def test_tags_add_remove_normalize_and_suggest(client):
    p, q = _p(), _p("Other", "5615550099")
    r = _va(client, "/api/va/crm/tags", {"prospect_id": p.id, "add": [" Hot Lead ", "hot lead", "30+ doors", ""]}).get_json()
    assert r["tags"] == ["hot lead", "30+ doors"] and r["added"] == ["30+ doors", "hot lead"]   # tags keep add order
    _va(client, "/api/va/crm/tags", {"prospect_id": q.id, "add": ["hot lead"]})
    r = _va(client, "/api/va/crm/tags", {"prospect_id": p.id, "remove": ["30+ DOORS"]}).get_json()
    assert r["tags"] == ["hot lead"] and r["removed"] == ["30+ doors"]
    s = _va(client, "/api/va/crm/tag-suggest", {"q": "ho"}).get_json()["tags"]
    assert s == [{"tag": "hot lead", "count": 2}]
    assert _va(client, "/api/va/crm/tag-suggest", {"q": "zzz"}).get_json()["tags"] == []
    assert _va(client, "/api/va/crm/tags", {"prospect_id": p.id, "add": "nope"}).status_code == 400
    assert _va(client, "/api/va/crm/tags", {"prospect_id": "missing"}).status_code == 404
    assert crm_card_fields(p)["tags"] == ["hot lead"]
    assert AuditEvent.query.filter_by(action="tags").count() == 3


# ---------------------------------------------------------------------------
# claims
# ---------------------------------------------------------------------------

def test_claim_renew_409_release_and_status(client):
    p = _p()
    r = _va(client, "/api/va/crm/claim", {"prospect_id": p.id}, name="Tracy")
    assert r.status_code == 200 and r.get_json()["claimed_by"] == "Tracy"
    first_until = r.get_json()["claimed_until"]
    r = _va(client, "/api/va/crm/claim", {"prospect_id": p.id}, name="Trixie")
    assert r.status_code == 409
    b = r.get_json()
    assert b["claimed_by"] == "Tracy" and 18 <= b["minutes_left"] <= 20 and "Tracy" in b["error"]
    st = _va(client, "/api/va/crm/claim-status", {"prospect_id": p.id}, name="Trixie").get_json()
    assert st["claimed_by"] == "Tracy" and st["mine"] is False
    # renew by the holder extends the window
    ProspectClaim.query.one().expires_at = _now() + timedelta(minutes=5); db.session.commit()
    r = _va(client, "/api/va/crm/claim", {"prospect_id": p.id}, name="Tracy").get_json()
    assert r["claimed_until"] >= first_until and ProspectClaim.query.count() == 1
    # another VA can't release it; the holder can
    assert _va(client, "/api/va/crm/release", {"prospect_id": p.id}, name="Trixie").get_json()["released"] is False
    assert _va(client, "/api/va/crm/release", {"prospect_id": p.id}, name="Tracy").get_json()["released"] is True
    assert _va(client, "/api/va/crm/claim-status", {"prospect_id": p.id}).get_json()["claimed_by"] is None
    card = _va(client, "/api/va/calls/get", {"prospect_id": p.id}, name="Trixie").get_json()["card"]
    assert card["claimed_by"] is None


def test_expired_claim_is_free_and_next_unclaimed_skips_held_cards(client):
    a = _p("A", "5615550001", tier=1)
    b = _p("B", "5615550002", tier=2)
    # expired claim by someone else → anyone can take it
    db.session.add(ProspectClaim(prospect_id=a.id, va_name="Trixie", claimed_at=_now() - timedelta(hours=1),
                                 expires_at=_now() - timedelta(minutes=1)))
    db.session.commit()
    assert crm_card_fields(a)["claimed_by"] is None
    assert next_unclaimed("Tracy").id == a.id
    r = _va(client, "/api/va/crm/claim", {"prospect_id": a.id}, name="Tracy")
    assert r.status_code == 200
    # now Trixie's queue skips A (held by Tracy) and deals B; Tracy still gets A
    assert next_unclaimed("Trixie").id == b.id
    assert next_unclaimed("Tracy").id == a.id
    # both held → nothing for a third VA
    _va(client, "/api/va/crm/claim", {"prospect_id": b.id}, name="Trixie")
    assert next_unclaimed("Dana") is None
    # a due follow-up held by another VA is skipped too
    a.next_followup_at = _now() - timedelta(hours=1); db.session.commit()
    assert next_unclaimed("Trixie").id == b.id


# ---------------------------------------------------------------------------
# accounts
# ---------------------------------------------------------------------------

def test_account_link_create_or_match_and_rollup(client, accounts):
    assert normalize_account_name("The Palm Coast Property Group, LLC") == "palm coast property"
    p1 = _p("Palm Coast Property Group LLC", "5615550001", contact_name="Marcus", email="m@pcpg.com")
    p2 = _p("The Palm Coast Property Group", "5615550002", contact_name="Dana")
    p3 = _p("Sunrise Estate Sales", "5615550003", category="estate sales")
    r = _va(client, "/api/va/crm/account", {"prospect_id": p1.id}).get_json()
    assert r["created"] is True and r["account"]["kind"] == "property_mgmt"
    acct_id = r["account"]["id"]
    assert r["contact"]["name"] == "Marcus" and r["contact"]["email"] == "m@pcpg.com" and r["contact"]["phone_digits"] == "5615550001"
    # second prospect with the same normalized name links to the same account
    r = _va(client, "/api/va/crm/account", {"prospect_id": p2.id}).get_json()
    assert r["created"] is False and r["account"]["id"] == acct_id
    # explicit name creates a new one; explicit id links
    r = _va(client, "/api/va/crm/account", {"prospect_id": p3.id, "name": "Sunrise Estates", "kind": "estate"}).get_json()
    assert r["created"] is True and r["account"]["name"] == "Sunrise Estates"
    r = _va(client, "/api/va/crm/account", {"prospect_id": p3.id, "account_id": acct_id}).get_json()
    assert r["account"]["id"] == acct_id and AccountContact.query.filter_by(prospect_id=p3.id).one().account_id == acct_id
    assert _va(client, "/api/va/crm/account", {"prospect_id": p3.id, "account_id": "nope"}).status_code == 404
    assert crm_card_fields(p2)["account"] == {"id": acct_id, "name": "Palm Coast Property Group LLC"}
    # rollup (manager)
    on_outcome(p1, "interested", "", "Tracy"); on_outcome(p2, "voicemail", "", "Tracy"); db.session.commit()
    boss = _login(client, "boss@goumuve.com", "pw-boss")
    rows = client.get("/api/admin/crm/accounts", headers=_h(boss)).get_json()["accounts"]
    pc = [a for a in rows if a["id"] == acct_id][0]
    assert pc["prospects"] == 3 and pc["stages"] == {"engaged": 1, "contacted": 1, "new": 1}
    assert len(pc["contacts"]) == 3
    rows = client.get("/api/admin/crm/accounts?q=sunrise", headers=_h(boss)).get_json()["accounts"]
    assert [a["name"] for a in rows] == ["Sunrise Estates"]


def test_manager_only_accounts_and_role_gating(client, accounts):
    va = _login(client, "tracy@goumuve.com", "pw-tracy")
    boss = _login(client, "boss@goumuve.com", "pw-boss")
    assert client.get("/api/admin/crm/accounts", headers=_h(va)).status_code == 403
    assert client.get("/api/admin/crm/accounts").status_code == 401
    assert client.get("/api/admin/crm/accounts", headers=_h(boss)).status_code == 200
    assert client.post("/api/va/crm/pipeline", json={}).status_code == 401
    assert client.post("/api/va/crm/pipeline", json={"code": "wrong", "va_name": "x"}).status_code == 401
    assert client.post("/api/va/crm/pipeline", json={}, headers=_h(va)).status_code == 200
    # a JWT VA claims under their account name
    p = _p()
    r = client.post("/api/va/crm/claim", json={"prospect_id": p.id}, headers=_h(va)).get_json()
    assert r["claimed_by"] == "Tracy"
    # managers can force-release someone else's claim
    assert client.post("/api/va/crm/release", json={"prospect_id": p.id}, headers=_h(boss)).get_json()["released"] is True
    ev = AuditEvent.query.filter_by(action="claim").one()
    assert ev.actor_name == "Tracy" and ev.via == "jwt"


# ---------------------------------------------------------------------------
# alerts + shift report
# ---------------------------------------------------------------------------

def test_win_alert_fires_on_converted_and_vendor_listed(client):
    p = _p(contact_name="Marcus Bell", city="West Palm Beach")
    with mock.patch("desk_health._send_alert") as send:
        _va(client, "/api/va/calls/log", {"prospect_id": p.id, "outcome": "voicemail"})
        _va(client, "/api/va/calls/log", {"prospect_id": p.id, "outcome": "interested", "note": "hot"})
        assert send.call_count == 0
        _va(client, "/api/va/calls/log", {"prospect_id": p.id, "outcome": "converted", "note": "signed"})
        assert send.call_count == 1
        subject, body = send.call_args[0]
        assert "WIN" in subject and "Palm Coast" in subject
        for needle in ("Marcus Bell", "5615550100", "signed", "Tracy", "won", "West Palm Beach"):
            assert needle in body
        q = _p("Q", "5615550200")
        _va(client, "/api/va/calls/log", {"prospect_id": q.id, "outcome": "vendor_listed"})
        assert send.call_count == 2 and "VENDOR LISTED" in send.call_args[0][0]
    # interested only alerts when the env knob is on; a failing sender never breaks the log
    with mock.patch.dict(os.environ, {"CRM_ALERT_ON_INTERESTED": "on"}), \
            mock.patch("desk_health._send_alert", side_effect=RuntimeError("smtp down")) as send:
        z = _p("Z", "5615550300")
        r = _va(client, "/api/va/calls/log", {"prospect_id": z.id, "outcome": "interested"})
        assert r.status_code == 200 and send.call_count == 1
        assert current_stage(z.id) == "engaged"


def test_shift_report_numbers_and_reread(client):
    p1, p2, p3 = _p("Won Co", "5615550001"), _p("Warm Co", "5615550002"), _p("Cold Co", "5615550003")
    start = _now() - timedelta(hours=3)
    sh = VaShift(va_name="Tracy", started_at=start)
    db.session.add(sh)
    t = lambda m: start + timedelta(minutes=m)
    db.session.add_all([
        CallAttempt(prospect_id=p3.id, outcome="voicemail", va_name="Tracy", created_at=t(5)),
        CallAttempt(prospect_id=p3.id, outcome="skip", va_name="Tracy", created_at=t(6)),
        CallAttempt(prospect_id=p2.id, outcome="interested", va_name="Tracy", created_at=t(20)),
        CallAttempt(prospect_id=p2.id, outcome="callback", va_name="Tracy", created_at=t(25)),
        CallAttempt(prospect_id=p1.id, outcome="converted", va_name="Tracy", created_at=t(40)),
        CallAttempt(prospect_id=p3.id, outcome="not_interested", va_name="Tracy", created_at=t(50)),
        CallAttempt(prospect_id=p1.id, outcome="no_answer", va_name="Trixie", created_at=t(55)),   # someone else
        CallAttempt(prospect_id=p1.id, outcome="interested", va_name="Tracy", created_at=start - timedelta(days=1)),  # before
        DeskActivity(prospect_id=p2.id, phone_digits="5615550002", kind="sms", direction="out", va_name="Tracy", created_at=t(21)),
        DeskActivity(prospect_id=p2.id, phone_digits="5615550002", kind="sms", direction="in", va_name=None, created_at=t(30)),
        DeskActivity(prospect_id=p1.id, phone_digits="5615550001", kind="call", direction="out", va_name="Tracy", created_at=t(39)),
    ])
    db.session.commit()
    with mock.patch("desk_health._send_alert") as send:
        r = _va(client, "/api/va/time/clock", {"action": "out"})
        assert r.status_code == 200 and r.get_json()["on_clock"] is False
        assert send.call_count == 1
        subject, body = send.call_args[0]
    assert subject.startswith("Shift report — Tracy ")
    assert "Dials 5 · Connects 4 · Interested 1 · Callbacks 1 · Texts 1 · Wins 1" in body
    assert "Interested: Warm Co" in body and "Won: Won Co" in body
    stored = json.loads(DeskSetting.get("shift_report:" + sh.id))
    assert stored["dials"] == 5 and stored["wins"] == 1 and 2.9 <= stored["hours"] <= 3.1
    assert stored["won_names"] == ["Won Co"] and stored["interested_names"] == ["Warm Co"]
    # re-read via the endpoint; another VA can't; a manager can
    r = _va(client, "/api/va/crm/shift-report", {"shift_id": sh.id}).get_json()
    assert r["stored"] is True and r["report"]["dials"] == 5
    assert _va(client, "/api/va/crm/shift-report", {"shift_id": sh.id}, name="Trixie").status_code == 403
    assert _va(client, "/api/va/crm/shift-report", {"shift_id": "nope"}).status_code == 404
    assert AuditEvent.query.filter_by(action="shift_report", target_id=sh.id).count() == 1


def test_shift_report_never_breaks_clock_out(client):
    db.session.add(VaShift(va_name="Tracy", started_at=_now() - timedelta(hours=1))); db.session.commit()
    with mock.patch("crm.build_shift_report", side_effect=RuntimeError("boom")):
        r = _va(client, "/api/va/time/clock", {"action": "out"})
    assert r.status_code == 200 and r.get_json()["on_clock"] is False
    assert VaShift.query.one().ended_at is not None


def test_card_payload_carries_crm_fields_on_next(client):
    p = _p()
    _va(client, "/api/va/crm/tags", {"prospect_id": p.id, "add": ["hot"]})
    # another VA holds it → the desk skips it for me (queue empty)
    _va(client, "/api/va/crm/claim", {"prospect_id": p.id}, name="Trixie")
    assert _va(client, "/api/va/calls/next").get_json().get("empty") is True
    _va(client, "/api/va/crm/release", {"prospect_id": p.id}, name="Trixie")
    _va(client, "/api/va/crm/claim", {"prospect_id": p.id})
    card = _va(client, "/api/va/calls/next").get_json()["card"]
    assert card["id"] == p.id and card["stage"] == "new" and card["tags"] == ["hot"]
    assert card["claimed_by"] == "Tracy" and card["claimed_until"]
    assert card["history"] == [] and card["account"] is None
