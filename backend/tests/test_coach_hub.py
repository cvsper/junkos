"""The Coach tab: one call returns the VA's week, class, focus, scored calls,
trend and playbook; a VA sees only herself; the chat coach gets a live briefing."""
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from models import db, CallProspect, CallAttempt, DeskActivity, VaShift
from models_analytics import CallScore, CoachingClass
import coach_hub


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture(autouse=True)
def env(app, db_session):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code", "JWT_SECRET": "unit"}):
        yield


def _va(client, path, payload, name="Tracy"):
    base = {"code": "test-code", "va_name": name}
    base.update(payload or {})
    return client.post(path, json=base)


def _seed(va="Tracy"):
    p = CallProspect(tier=1, category="property management", company="Palm Coast PM", phone="5615550142",
                     phone_digits="5615550142", city="Lantana", created_at=_now())
    db.session.add(p); db.session.flush()
    for i, (total, fixes) in enumerate([(21, ["Ask for the decision maker by name"]), (12, ["Skipped the recording notice", "Opened with a pitch, not a question"])]):
        sid = "CAcoach%d" % i
        db.session.add(DeskActivity(prospect_id=p.id, phone_digits="5615550142", kind="call", direction="out",
                                    twilio_sid=sid, status="completed", duration=180, recording_url="https://api.twilio.com/rec/%d" % i,
                                    va_name=va))
        db.session.add(CallScore(call_sid=sid, prospect_id=p.id, va_name=va, opener=4, discovery=4, objection=total - 13, close=3, compliance=2,
                                 total=total, strengths=["Warm opener"], fixes=fixes, source="heuristic", line_count=12,
                                 created_at=_now() - timedelta(hours=2 + i)))
        db.session.add(CallAttempt(prospect_id=p.id, outcome="interested" if i == 0 else "no_answer", va_name=va, created_at=_now() - timedelta(hours=2 + i)))
    monday = (_now().date() - timedelta(days=_now().date().weekday())).isoformat()
    db.session.add(CoachingClass(va_name=va, week_start=monday, status="assigned", calls=2, avg_total=165,
                                 dims={"opener": 4, "discovery": 4, "objection": 2.5, "close": 3, "compliance": 2}, weakest="compliance",
                                 lesson={"title": "Say the notice, then breathe", "summary": "Two calls, one skipped the notice.",
                                         "went_well": [{"point": "Warm opener", "quote": None}],
                                         "fix": [{"point": "Play the recording notice every time", "quote": None, "say_instead": "Quick heads-up, this call is recorded for quality."}],
                                         "drill": {"line": "Quick heads-up, this call is recorded for quality.", "why": "Florida is all-party consent."},
                                         "quiz": [{"q": "When do you say the notice?", "options": ["Never", "Before they speak", "After the pitch", "Only on voicemail"], "answer": 1, "why": "Consent first."}]},
                                 source="heuristic", due_at=_now() + timedelta(days=2)))
    db.session.add(VaShift(va_name=va, started_at=_now() - timedelta(hours=3), ended_at=_now() - timedelta(hours=1)))
    db.session.commit()
    return p


def test_home_returns_every_section_for_the_va(client):
    _seed()
    r = _va(client, "/api/va/coach/home", {}, name="Tracy")
    assert r.status_code == 200
    d = r.get_json()
    assert d["va"] == "Tracy" and d["first"] == "Tracy"
    assert d["week"]["dials"] == 2 and d["week"]["interested"] == 1 and d["week"]["hours"] == 2.0 and d["week"]["streak"] >= 1
    assert d["klass"]["current"]["status"] == "assigned" and d["klass"]["history"][0]["week_start"] == d["klass"]["current"]["week_start"]
    assert "answer" not in d["klass"]["current"]["lesson"]["quiz"][0]          # quiz stays un-spoiled
    assert d["focus"]["weakest"] == "compliance" and d["focus"]["drill"]["line"].startswith("Quick heads-up")
    calls = d["calls"]
    assert calls["total"] == 2 and calls["avg_total"] == 16.5 and calls["calls"][0]["total"] == 21
    assert calls["calls"][0]["recording_url"].startswith("https://api.twilio.com/rec/") and calls["calls"][0]["link"].startswith("/va/calls?prospect=")
    assert calls["calls"][1]["top_fix"] == "Skipped the recording notice"
    assert d["trend"]["weeks"] and d["trend"]["weeks"][-1]["n"] == 2
    pb = d["playbook"]
    assert pb["openers"] and "Tracy" in pb["openers"][0]["text"]
    assert pb["demand"]["objections"][0]["say"] and pb["demand"]["objections"][0]["reply"]
    assert pb["supply"]["objections"] and pb["supply"]["answers"] and pb["demand"]["answers"]
    assert isinstance(pb["prices"], list)


def test_a_va_only_sees_herself_and_the_passcode_can_pick(client):
    _seed("Tracy")
    other = _va(client, "/api/va/coach/home", {"va": "Tracy"}, name="Sam").get_json()
    assert other["va"] == "Tracy"            # passcode users are trusted to look at anyone
    from desk_auth import create_desk_user
    create_desk_user("sam@goumuve.com", "Sam", "va", "pw-sam-11")
    tok = client.post("/api/desk/login", json={"email": "sam@goumuve.com", "password": "pw-sam-11"}).get_json()["token"]
    mine = client.post("/api/va/coach/home", json={"va": "Tracy"}, headers={"Authorization": "Bearer " + tok}).get_json()
    assert mine["va"] == "Sam" and mine["calls"]["total"] == 0 and mine["manager"] is False
    assert client.post("/api/va/coach/home", json={}).status_code == 401


def test_my_calls_and_playbook_routes(client):
    _seed()
    r = _va(client, "/api/va/coaching/my-calls", {"days": 30, "limit": 1}).get_json()
    assert r["total"] == 2 and len(r["calls"]) == 1 and r["va"] == "Tracy"
    pb = _va(client, "/api/va/coaching/playbook", {}).get_json()
    assert pb["demand"]["tracks"]["property"]["pitch"] and pb["supply"]["track"]["opener"].startswith("Hi, this is Tracy")


def test_chat_coach_gets_a_live_briefing_and_desk_auth(client):
    _seed()
    ctx = coach_hub.coach_context("Tracy")
    assert "2 dials" in ctx and "the recording notice" in ctx and "Palm Coast PM" in ctx and "Demand objection" in ctx
    captured = {}
    class _Resp:
        content = [type("B", (), {"text": "Say the notice first, then ask who handles haul-away."})()]
    fake = mock.Mock(); fake.messages.create.side_effect = lambda **kw: captured.update(kw) or _Resp()
    with mock.patch("trixie_assistant._anthropic_client", return_value=fake):
        r = _va(client, "/api/coach/chat", {"messages": [{"role": "user", "content": "How do I open?"}]})
    assert r.status_code == 200 and "notice" in r.get_json()["reply"]
    assert "ABOUT TRACY" in captured["system"] and "CUSTOMER (DEMAND) SIDE" in captured["system"] and "(844) 435-6005" in captured["system"]
    assert client.get("/coach").status_code == 200 and b"co-playbook" in client.get("/coach").data
    assert client.get("/static/coach.js").status_code == 200
