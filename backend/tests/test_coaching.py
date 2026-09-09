"""Call scorecards: heuristic rubric, Claude path, min-lines rule, idempotency, review queue, review + audit, trend."""
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from coaching import heuristic_score, score_call, score_call_async, trend, MIN_LINES
from desk_auth import create_desk_user
from models import db, AuditEvent, CallProspect, DeskActivity, DeskTranscriptLine, User
from models_analytics import CallScore, SCORE_DIMENSIONS


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code", "JWT_SECRET": "unit",
                                      "ANTHROPIC_API_KEY": ""}):
        yield
    for m in (CallScore, DeskTranscriptLine, DeskActivity, AuditEvent, CallProspect):
        m.query.delete()
    User.query.filter(User.email.in_(["tracy@goumuve.com", "boss@goumuve.com"])).delete(synchronize_session=False)
    db.session.commit()


GOOD_CALL = [
    ("va", "Hi, this is Tracy with Umuve, quick heads up this call is recorded. Got a minute?"),
    ("them", "Sure, what's this about?"),
    ("va", "We do junk removal for property managers. Who handles move-out cleanouts for you today?"),
    ("them", "Usually maintenance, sometimes a guy we know. Honestly how much does it cost?"),
    ("va", "Most one-bedroom cleanouts land around three hundred and you get one number for every unit, quoted up front from photos."),
    ("va", "How many doors are you managing right now?"),
    ("them", "About two hundred."),
    ("va", "Can I put a rate card on file so your managers have the number? Who should I send it to?"),
    ("them", "Yeah sure, send it to marcus at palmcoast dot com."),
]
WEAK_CALL = [
    ("va", "Hello."),
    ("them", "Hi, who is this?"),
    ("va", "Junk stuff."),
    ("them", "We already have a guy for that. Not interested."),
    ("va", "Ok."),
    ("them", "Bye."),
]


def _lines(pairs):
    return [{"track": t, "text": x} for t, x in pairs]


def _prospect(company="Palm Coast PM", phone="5615550142"):
    p = CallProspect(tier=1, category="property management", company=company, phone=phone, phone_digits=phone,
                     contact_name="Marcus", last_called_at=datetime.now(timezone.utc).replace(tzinfo=None))
    db.session.add(p); db.session.commit()
    return p


def _call(p, sid, va="Tracy", pairs=GOOD_CALL, when=None):
    act = DeskActivity(prospect_id=p.id, phone_digits=p.phone_digits, kind="call", direction="out",
                       twilio_sid=sid, status="completed", duration=120, va_name=va,
                       created_at=when or datetime.now(timezone.utc).replace(tzinfo=None))
    db.session.add(act)
    for i, (t, x) in enumerate(pairs):
        db.session.add(DeskTranscriptLine(call_sid=sid, prospect_id=p.id, track=t, text=x, seq=i + 1))
    db.session.commit()
    return act


def _va(client, path, payload=None, name="Tracy"):
    base = {"code": "test-code", "va_name": name}
    base.update(payload or {})
    return client.post(path, json=base)


def _tokens(client):
    create_desk_user("tracy@goumuve.com", "Tracy Jamesyoung", "va", "pw-tracy")
    create_desk_user("boss@goumuve.com", "Shamar", "manager", "pw-boss")
    va = client.post("/api/desk/login", json={"email": "tracy@goumuve.com", "password": "pw-tracy"}).get_json()["token"]
    mgr = client.post("/api/desk/login", json={"email": "boss@goumuve.com", "password": "pw-boss"}).get_json()["token"]
    return {"Authorization": "Bearer " + va}, {"Authorization": "Bearer " + mgr}


def test_heuristic_scores_within_bounds_and_separates_good_from_weak():
    good = heuristic_score(_lines(GOOD_CALL))
    weak = heuristic_score(_lines(WEAK_CALL))
    for s in (good, weak):
        for d in SCORE_DIMENSIONS:
            assert 0 <= s[d] <= 5
    assert good["opener"] >= 4 and good["discovery"] >= 3 and good["close"] == 5 and good["compliance"] == 5
    assert good["objection"] >= 4                       # "how much" was answered in a full sentence
    assert weak["opener"] <= 2 and weak["discovery"] == 0 and weak["close"] == 1 and weak["compliance"] == 2
    assert weak["objection"] <= 2                       # "already have a guy" met with "Ok."
    assert sum(good[d] for d in SCORE_DIMENSIONS) > sum(weak[d] for d in SCORE_DIMENSIONS) + 10
    assert good["strengths"] and weak["fixes"] and "recorded" in " ".join(weak["fixes"])
    assert heuristic_score([])["opener"] == 0 and heuristic_score([])["objection"] == 3


def test_claude_path_is_used_when_configured_and_falls_back_on_garbage():
    p = _prospect()
    act = _call(p, "CAclaude")
    fake = mock.MagicMock()
    fake.messages.create.return_value = mock.MagicMock(content=[mock.MagicMock(
        text='Here you go: {"opener": 5, "discovery": 4, "objection": 3, "close": 9, "compliance": "2", '
             '"strengths": ["Warm opener"], "fixes": ["Ask one more question", "Confirm the email back"]}')])
    with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k", "COPILOT_MODEL": "claude-haiku-4-5-20251001"}), \
         mock.patch("anthropic.Anthropic", return_value=fake):
        row = score_call(act, _lines(GOOD_CALL), p)
    assert row.source == "claude" and row.opener == 5 and row.close == 5 and row.compliance == 2   # clamped
    assert row.total == 5 + 4 + 3 + 5 + 2 and row.fixes == ["Ask one more question", "Confirm the email back"]
    kw = fake.messages.create.call_args.kwargs
    assert kw["model"] == "claude-haiku-4-5-20251001" and "Palm Coast PM" in kw["messages"][0]["content"]
    assert "recorded" in kw["messages"][0]["content"]
    # a non-JSON reply → heuristic, never an error
    act2 = _call(p, "CAgarbage")
    fake.messages.create.return_value = mock.MagicMock(content=[mock.MagicMock(text="I cannot score this.")])
    with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k"}), mock.patch("anthropic.Anthropic", return_value=fake):
        row2 = score_call(act2, _lines(GOOD_CALL), p)
    assert row2.source == "heuristic" and row2.total > 15


def test_short_calls_are_not_scored_and_scoring_is_idempotent():
    p = _prospect()
    short = _call(p, "CAshort", pairs=GOOD_CALL[:MIN_LINES - 1])
    assert score_call(short, _lines(GOOD_CALL[:MIN_LINES - 1]), p) is None
    assert CallScore.query.count() == 0
    act = _call(p, "CAgood")
    first = score_call(act, _lines(GOOD_CALL), p)
    again = score_call(act, _lines(WEAK_CALL), p)           # different lines, same sid → same row
    assert first.id == again.id and CallScore.query.count() == 1 and again.total == first.total
    assert score_call(DeskActivity(kind="call", direction="out", phone_digits="5615550142"), _lines(GOOD_CALL), p) is None
    # the async wrapper swallows failures
    with mock.patch("coaching.score_call", side_effect=RuntimeError("boom")):
        assert score_call_async(act, [], p) is None


def test_summarize_hook_scores_the_call(client):
    p = _prospect()
    _call(p, "CAhook", pairs=GOOD_CALL)
    r = _va(client, "/api/va/desk/summarize", {"prospect_id": p.id})
    assert r.status_code == 200 and r.get_json()["lines"] == len(GOOD_CALL)
    row = CallScore.query.filter_by(call_sid="CAhook").one()
    assert row.va_name == "Tracy" and row.prospect_id == p.id and row.line_count == len(GOOD_CALL)
    # the desk reads it back by the text on the card (no prospect id in the DOM)
    r = _va(client, "/api/va/coaching/scorecard", {"company": "Palm Coast PM", "phone": "(561) 555-0142"}).get_json()
    assert r["score"]["call_sid"] == "CAhook" and r["score"]["total"] == row.total and r["score"]["top_fix"] is not None or r["score"]["fixes"] == []
    r = _va(client, "/api/va/coaching/scorecard", {"prospect_id": p.id}).get_json()
    assert r["score"]["scores"]["compliance"] == 5


def test_scorecard_gating_and_on_demand_scoring(client):
    va, mgr = _tokens(client)
    p = _prospect()
    _call(p, "CAmine", va="Tracy")
    other = _prospect("Sunset HOA", "5615550199")
    _call(other, "CAtheirs", va="Trixie")
    # nothing scored yet → the endpoint scores on demand from the stored transcript
    r = client.post("/api/va/coaching/scorecard", json={"prospect_id": p.id}, headers=va).get_json()
    assert r["score"]["va_name"] == "Tracy" and r["score"]["source"] == "heuristic"
    # a VA can't read another VA's card; a manager can
    assert client.post("/api/va/coaching/scorecard", json={"prospect_id": other.id}, headers=va).status_code == 403
    assert client.post("/api/va/coaching/scorecard", json={"prospect_id": other.id}, headers=mgr).get_json()["score"]["va_name"] == "Trixie"
    assert client.post("/api/va/coaching/scorecard", json={"call_sid": "CAmine"}, headers=mgr).get_json()["score"]["call_sid"] == "CAmine"
    empty = client.post("/api/va/coaching/scorecard", json={"company": "Nobody Inc"}, headers=va).get_json()
    assert empty["score"] is None
    assert client.post("/api/va/coaching/scorecard", json={}).status_code == 401


def test_review_queue_orders_lowest_first_with_excerpt(client):
    va, mgr = _tokens(client)
    p = _prospect()
    good = _call(p, "CAgood", pairs=GOOD_CALL)
    weak = _call(p, "CAweak", pairs=WEAK_CALL)
    score_call(good, _lines(GOOD_CALL), p); score_call(weak, _lines(WEAK_CALL), p)
    assert client.post("/api/va/coaching/review-queue", json={}, headers=va).status_code == 403
    r = client.post("/api/va/coaching/review-queue", json={}, headers=mgr).get_json()
    assert r["unreviewed"] == 2 and [q["call_sid"] for q in r["queue"]] == ["CAweak", "CAgood"]
    q = r["queue"][0]
    assert len(q["excerpt"]) == 6 and q["excerpt"][0] == {"track": "va", "text": "Hello."}
    assert q["company"] == "Palm Coast PM" and q["reviewed"] is False and q["top_fix"]
    assert len(r["queue"][1]["excerpt"]) == 6


def test_review_marks_and_audits(client):
    va, mgr = _tokens(client)
    p = _prospect()
    act = _call(p, "CArev", pairs=WEAK_CALL)
    score_call(act, _lines(WEAK_CALL), p)
    assert client.post("/api/va/coaching/review", json={"call_sid": "CArev", "note": "x"}, headers=va).status_code == 403
    assert client.post("/api/va/coaching/review", json={"call_sid": "nope"}, headers=mgr).status_code == 404
    r = client.post("/api/va/coaching/review", json={"call_sid": "CArev", "note": "Open with Umuve and the reason.",
                                                      "tags": ["Opener", "close", "", "opener"]}, headers=mgr)
    assert r.status_code == 200
    s = r.get_json()["score"]
    assert s["reviewed"] and s["reviewed_by"] == "Shamar" and s["review_tags"] == ["opener", "close", "opener"]
    row = CallScore.query.filter_by(call_sid="CArev").one()
    assert row.reviewed_at is not None and row.review_note.startswith("Open with")
    ev = AuditEvent.query.filter_by(action="call_reviewed").one()
    assert ev.actor_name == "Shamar" and ev.via == "jwt" and ev.target_id == "CArev" and ev.meta["va"] == "Tracy"
    # reviewed calls leave the queue
    assert client.post("/api/va/coaching/review-queue", json={}, headers=mgr).get_json()["unreviewed"] == 0
    # tags may also arrive as a comma string
    act2 = _call(p, "CArev2", pairs=WEAK_CALL); score_call(act2, _lines(WEAK_CALL), p)
    r = client.post("/api/va/coaching/review", json={"call_sid": "CArev2", "tags": "close, compliance"}, headers=mgr).get_json()
    assert r["score"]["review_tags"] == ["close", "compliance"]


def test_trend_weekly_averages_per_va(client):
    va, mgr = _tokens(client)
    p = _prospect()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for sid, pairs, who, when in (("CAt1", GOOD_CALL, "Tracy", now), ("CAt2", WEAK_CALL, "Tracy", now),
                                  ("CAt3", GOOD_CALL, "Tracy", now - timedelta(days=21)),
                                  ("CAt4", WEAK_CALL, "Trixie", now)):
        row = score_call(_call(p, sid, va=who, pairs=pairs, when=when), _lines(pairs), p)
        row.created_at = when
    db.session.commit()
    t = trend(56)
    assert set(t) == {"Tracy", "Trixie"}
    assert len(t["Tracy"]) == 2 and t["Tracy"][0]["week"] < t["Tracy"][1]["week"]
    this_week = t["Tracy"][1]
    good, weak = heuristic_score(_lines(GOOD_CALL)), heuristic_score(_lines(WEAK_CALL))
    assert this_week["n"] == 2
    assert this_week["opener"] == round((good["opener"] + weak["opener"]) / 2, 1)
    assert this_week["total"] == round((sum(good[d] for d in SCORE_DIMENSIONS) + sum(weak[d] for d in SCORE_DIMENSIONS)) / 2, 1)
    assert t["Trixie"][0]["n"] == 1
    # endpoint: VA sees only herself, manager any
    r = client.post("/api/va/coaching/trend", json={"va": "Trixie"}, headers=va).get_json()
    assert r["va"] == "Tracy" and set(r["vas"]) == {"Tracy"} and r["dimensions"] == list(SCORE_DIMENSIONS)
    r = client.post("/api/va/coaching/trend", json={}, headers=mgr).get_json()
    assert set(r["vas"]) == {"Tracy", "Trixie"}
