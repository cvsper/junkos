"""The weekly class is built from her own calls, holds her to it, and grades honestly."""
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from desk_auth import create_desk_user
from models import db, AuditEvent, CallProspect, DeskActivity, DeskTranscriptLine, User
from models_analytics import CallScore, CoachingClass
import coaching_class as cc


@pytest.fixture(autouse=True)
def env(app, db_session):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code", "JWT_SECRET": "unit",
                                      "ANTHROPIC_API_KEY": "", "SLACK_ALERT_WEBHOOK": ""}):
        yield


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _score(va, sid, total_by_dim, strengths=(), fixes=(), when=None, company="Palm Coast PM"):
    phone = "56155" + str(abs(hash(sid)) % 100000).zfill(5)      # one prospect per call; phone_digits is unique
    p = CallProspect(tier=1, category="property management", company=company, phone=phone, phone_digits=phone)
    db.session.add(p); db.session.flush()
    for i, (t, x) in enumerate([("va", "Hi, this is Tracy with Umuve, quick heads up this call is recorded. Got a minute?"),
                                ("them", "Sure"), ("va", "Who handles move-out cleanouts for you today?"), ("them", "Maintenance."),
                                ("va", "Can I put a rate card on file? Who should I send it to?"), ("them", "marcus@pc.com")]):
        db.session.add(DeskTranscriptLine(call_sid=sid, prospect_id=p.id, track=t, text=x, seq=i + 1))
    s = CallScore(call_sid=sid, prospect_id=p.id, va_name=va, strengths=list(strengths), fixes=list(fixes), source="heuristic",
                  line_count=6, created_at=when or _now())
    for d, v in total_by_dim.items():
        setattr(s, d, v)
    s.total = sum(total_by_dim.values())
    db.session.add(s); db.session.commit()
    return s


def _this_monday():
    return cc.week_bounds(cc._local(_now()).date())[2]


def test_class_is_built_from_the_weeks_scores_and_targets_the_weakest_dimension():
    _score("Tracy", "CA1", {"opener": 5, "discovery": 4, "objection": 3, "close": 1, "compliance": 5},
           strengths=["Clear opener with the recording notice."], fixes=["Never asked for the rate card."])
    _score("Tracy", "CA2", {"opener": 4, "discovery": 3, "objection": 3, "close": 2, "compliance": 5},
           strengths=["Good discovery question."], fixes=["Ended without a next step."])
    row = cc.build_class("Tracy", _this_monday())
    assert row is not None and row.calls == 2 and row.weakest == "close" and row.avg_total == 175   # (18 + 17) / 2
    assert row.source == "heuristic" and row.status == "assigned"
    lesson = row.lesson
    assert "close" in lesson["title"] and len(lesson["quiz"]) == 3 and lesson["drill"]["line"] == cc.DRILL["close"]
    assert lesson["fix"][0]["point"] in ("Never asked for the rate card.", "Ended without a next step.")
    assert lesson["fix"][0]["say_instead"] == cc.DRILL["close"]
    assert lesson["went_well"][0]["quote"]            # her own words, quoted back
    # idempotent
    assert cc.build_class("Tracy", _this_monday()).id == row.id
    assert cc.build_class("Nobody", _this_monday()) is None


def test_claude_lesson_is_used_when_it_returns_good_json_and_ignored_when_garbage():
    _score("Tracy", "CA3", {"opener": 1, "discovery": 4, "objection": 3, "close": 4, "compliance": 5})
    good = ('{"title":"Own the first ten seconds","summary":"You get to the point fast. Start with your name.",'
            '"went_well":[{"point":"Strong close","quote":"Can I put a rate card on file?"}],'
            '"fix":[{"point":"No name in the opener","quote":"Hello.","say_instead":"Hi, this is Tracy with Umuve."}],'
            '"drill":{"line":"Hi, this is Tracy with Umuve.","why":"Say it five times."},'
            '"quiz":[{"q":"First words?","options":["Hello","Name and company","Price","Silence"],"answer":1,"why":"Identify yourself."},'
            '{"q":"Ask for time how?","options":["Ten minutes?","Got a minute?","Never","Email"],"answer":1,"why":"Small ask."}]}')
    fake = mock.MagicMock()
    fake.messages.create.return_value = mock.MagicMock(content=[mock.MagicMock(text=good)])
    with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k"}), mock.patch("anthropic.Anthropic", return_value=fake, create=True):
        row = cc.build_class("Tracy", _this_monday(), force=True)
    assert row.source == "claude" and row.lesson["title"] == "Own the first ten seconds" and len(row.lesson["quiz"]) == 2
    fake.messages.create.return_value = mock.MagicMock(content=[mock.MagicMock(text="not json at all")])
    with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k"}), mock.patch("anthropic.Anthropic", return_value=fake, create=True):
        row = cc.build_class("Tracy", _this_monday(), force=True)
    assert row.source == "heuristic" and row.weakest == "opener"


def test_class_week_flips_on_friday_at_five():
    thu = cc._to_utc(datetime(2026, 9, 10, 12, 0))    # Thursday noon local
    fri_late = cc._to_utc(datetime(2026, 9, 11, 17, 30))
    sun = cc._to_utc(datetime(2026, 9, 13, 9, 0))
    wk = lambda d: cc.week_bounds(cc.class_week_for(d))[2]   # noqa: E731
    assert wk(thu) == "2026-08-31"       # last week's class is the open one
    assert wk(fri_late) == "2026-09-07"  # this week, once Friday 5pm has passed
    assert wk(sun) == "2026-09-07"


def test_desk_holds_the_va_until_she_finishes_and_grades_her(client):
    _score("Tracy", "CA4", {"opener": 5, "discovery": 2, "objection": 3, "close": 4, "compliance": 5},
           fixes=["Pitched before asking a single question."])
    create_desk_user("tracy@goumuve.com", "Tracy Jamesyoung", "va", "pw-tracy")
    create_desk_user("boss@goumuve.com", "Shamar", "manager", "pw-boss")
    va = {"Authorization": "Bearer " + client.post("/api/desk/login", json={"email": "tracy@goumuve.com", "password": "pw-tracy"}).get_json()["token"]}
    mgr = {"Authorization": "Bearer " + client.post("/api/desk/login", json={"email": "boss@goumuve.com", "password": "pw-boss"}).get_json()["token"]}

    # her class builds on demand and blocks her; answers are never leaked
    r = client.post("/api/va/coaching/class/current", json={}, headers=va).get_json()
    assert r["blocking"] is True and r["class"]["weakest"] == "discovery" and r["class"]["quiz_total"] == 3
    assert all("answer" not in q for q in r["class"]["lesson"]["quiz"])
    cid = r["class"]["id"]
    # a manager looking at the same class is never blocked, and sees the answers
    m = client.post("/api/va/coaching/class/current", json={"va": "Tracy"}, headers=mgr).get_json()
    assert m["blocking"] is False and m["class"]["id"] == cid

    # reflection is required
    r = client.post("/api/va/coaching/class/complete", json={"class_id": cid, "answers": [1, 1, 1], "reflection": "ok"}, headers=va)
    assert r.status_code == 400
    # the bank's answers are all index 1; miss one on purpose
    r = client.post("/api/va/coaching/class/complete", json={"class_id": cid, "answers": [1, 0, 1],
                                                            "reflection": "Ask who handles cleanouts before I say a word about price."}, headers=va)
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["score"] == 2 and body["of"] == 3 and body["results"][1]["correct"] is False and body["results"][1]["why"]
    row = db.session.get(CoachingClass, cid)
    assert row.status == "completed" and row.quiz_score == 2 and row.completed_at is not None
    assert AuditEvent.query.filter_by(action="coaching_class_completed").count() == 1
    # no longer blocking
    assert client.post("/api/va/coaching/class/current", json={}, headers=va).get_json()["blocking"] is False
    # history: she sees hers; manager sees everyone incl. answers; someone else's class is off limits
    assert client.post("/api/va/coaching/class/history", json={}, headers=va).get_json()["classes"][0]["id"] == cid
    assert client.post("/api/va/coaching/class/history", json={}, headers=mgr).get_json()["classes"][0]["quiz_score"] == 2
    create_desk_user("sam@goumuve.com", "Sam", "va", "pw-sam-11")
    sam = {"Authorization": "Bearer " + client.post("/api/desk/login", json={"email": "sam@goumuve.com", "password": "pw-sam-11"}).get_json()["token"]}
    assert client.post("/api/va/coaching/class/complete", json={"class_id": cid, "answers": [1], "reflection": "x" * 20}, headers=sam).status_code == 403


def test_manager_can_rebuild_and_waive_and_the_scheduler_assigns_everyone(client):
    _score("Tracy", "CA5", {"opener": 3, "discovery": 3, "objection": 3, "close": 3, "compliance": 1})
    _score("Sam", "CA6", {"opener": 5, "discovery": 5, "objection": 5, "close": 5, "compliance": 5})
    with mock.patch("coaching_class.class_week_for", return_value=cc._local(_now()).date()):
        built = cc.assign_week()
    assert sorted(r.va_name for r in built) == ["Sam", "Tracy"]
    assert next(r for r in built if r.va_name == "Tracy").weakest == "compliance"
    base = {"code": "test-code", "va_name": "Shamar"}
    r = client.post("/api/va/coaching/class/build", json=dict(base, va="Tracy", force=True)).get_json()
    assert r["class"]["status"] == "assigned" and r["class"]["lesson"]["quiz"][0]["answer"] == 1
    r = client.post("/api/va/coaching/class/waive", json=dict(base, class_id=r["class"]["id"], note="on vacation")).get_json()
    assert r["class"]["status"] == "waived" and r["class"]["manager_note"] == "on vacation"
    assert client.post("/api/va/coaching/class/build", json=dict(base, va="Nobody")).status_code == 404
    assert client.get("/static/desk-class.js").status_code == 200 and client.get("/static/desk-class.css").status_code == 200
