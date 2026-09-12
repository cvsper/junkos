"""Call Desk analytics: funnel math, reach rate, economics, lists, timeseries, gating, cache."""
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

import analytics
from analytics import cache_clear, funnel, lists, timeseries, window
from desk_auth import create_desk_user
from models import db, AuditEvent, CallAttempt, CallProspect, DeskActivity, User, VaShift
from timeutils import local_naive_to_utc, to_local


@pytest.fixture(autouse=True)
def env(app):
    cache_clear()
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code", "JWT_SECRET": "unit",
                                      "VA_PAY_PERIOD_ANCHOR": "2026-08-06", "VA_HOURLY_RATE": "6.00"}):
        yield
    cache_clear()
    for m in (CallAttempt, DeskActivity, VaShift, AuditEvent, CallProspect):
        m.query.delete()
    User.query.filter(User.email.in_(["tracy@goumuve.com", "boss@goumuve.com"])).delete(synchronize_session=False)
    db.session.commit()



def _frozen_utc():
    """20:00 America/New_York today, as an aware UTC datetime."""
    from timeutils import to_local, local_naive_to_utc
    d = to_local(datetime.now(timezone.utc)).date()
    return local_naive_to_utc(datetime.combine(d, datetime.min.time()).replace(hour=20))


@pytest.fixture(autouse=True)
def _freeze_clock():
    fixed = _frozen_utc()
    with mock.patch("analytics._now", return_value=fixed.replace(tzinfo=None)):
        yield


def _now():
    return _frozen_utc().replace(tzinfo=None)


def _at_local(hour, days_ago=0):
    """Naive-UTC instant for `hour`:00 business time, `days_ago` days back."""
    d = (to_local(_now().replace(tzinfo=timezone.utc)) - timedelta(days=days_ago)).date()
    return local_naive_to_utc(datetime.combine(d, datetime.min.time()).replace(hour=hour)).replace(tzinfo=None)


def _prospect(company, phone, category="property management", tier=1, created=None, **kw):
    p = CallProspect(tier=tier, category=category, company=company, phone=phone, phone_digits=phone,
                     created_at=created or _now(), **kw)
    db.session.add(p)
    db.session.commit()
    return p


def _attempt(p, outcome, va="Tracy", at=None):
    a = CallAttempt(prospect_id=p.id, outcome=outcome, va_name=va, created_at=at or (_now() - timedelta(minutes=1)))
    db.session.add(a)
    db.session.commit()
    return a


def _va(client, path, payload=None, name="Tracy"):
    base = {"code": "test-code", "va_name": name}
    base.update(payload or {})
    return client.post(path, json=base)


def _seed_funnel():
    """Tracy: 6 dials (3 connects, 1 interested, 1 win). Trixie: 2 dials, 1 connect.
    Two categories, two tiers, spread over hours so the by-hour math is checkable."""
    pm = _prospect("Palm Coast PM", "5615550101")
    hoa = _prospect("Sunset HOA", "5615550102", category="HOA", tier=2)
    haul = _prospect("Robs Hauling", "9545550103", category="junk removal", tier=2, why="owns two trucks")
    ten = _at_local(10)
    _attempt(pm, "voicemail", at=ten)
    _attempt(pm, "interested", at=ten + timedelta(minutes=5))
    _attempt(hoa, "no_answer", at=_at_local(14))
    _attempt(hoa, "vendor_listed", at=_at_local(14) + timedelta(minutes=10))
    _attempt(haul, "not_interested", at=_at_local(16))
    _attempt(pm, "skip", at=ten + timedelta(minutes=6))          # never a dial
    _attempt(haul, "bad_number", at=_at_local(16) + timedelta(minutes=1))
    _attempt(pm, "voicemail", va="Trixie", at=_at_local(11))
    _attempt(hoa, "sent_link", va="Trixie", at=_at_local(11) + timedelta(minutes=2))
    return pm, hoa, haul


def test_funnel_totals_reach_rate_and_groupings():
    _seed_funnel()
    start, end, label, days = window({"days": 7})
    f = funnel(start, end)
    assert f["dials"] == 8 and f["connects"] == 4 and f["interested"] == 2 and f["wins"] == 1
    assert f["reach_rate"] == 50.0 and f["conversion"] == 12.5
    assert f["by_outcome"]["voicemail"] == 2 and "skip" not in f["by_outcome"]
    tiers = {t["tier"]: t for t in f["by_tier"]}
    assert tiers[1]["dials"] == 3 and tiers[2]["dials"] == 5 and tiers[2]["wins"] == 1
    cats = {c["category"]: c for c in f["by_category"]}
    assert cats["property management"]["dials"] == 3 and cats["hoa"]["interested"] == 1 and cats["junk removal"]["connects"] == 1
    assert f["by_side"]["supply"]["dials"] == 2 and f["by_side"]["demand"]["dials"] == 6
    vas = {v["va"]: v for v in f["by_va"]}
    assert vas["Tracy"]["dials"] == 6 and vas["Tracy"]["connects"] == 3 and vas["Trixie"]["dials"] == 2
    assert f["by_va"][0]["va"] == "Tracy"                        # sorted by dials
    hours = {h["hour"]: h for h in f["by_hour"]}
    assert hours[10]["dials"] == 2 and hours[10]["interested"] == 1 and hours[14]["wins"] == 1 and hours[16]["connects"] == 1
    wd = to_local(_at_local(10)).weekday()
    assert f["heatmap"]["dials"][wd][10] == 2 and f["heatmap"]["connects"][wd][10] == 1
    assert sum(w["dials"] for w in f["by_weekday"]) == 8


def test_funnel_for_one_va_and_texts():
    pm, hoa, haul = _seed_funnel()
    at = _now() - timedelta(minutes=5)   # inside the frozen window, whatever the wall clock says
    db.session.add_all([
        DeskActivity(prospect_id=pm.id, phone_digits=pm.phone_digits, kind="sms", direction="out", va_name="Tracy", body="hi", created_at=at),
        DeskActivity(prospect_id=pm.id, phone_digits=pm.phone_digits, kind="sms", direction="in", body="who is this", created_at=at),
        DeskActivity(prospect_id=hoa.id, phone_digits=hoa.phone_digits, kind="sms", direction="out", va_name="Trixie", body="hi", created_at=at),
        DeskActivity(prospect_id=haul.id, phone_digits=haul.phone_digits, kind="sms", direction="in", body="stop", created_at=at),
        DeskActivity(prospect_id=pm.id, phone_digits=pm.phone_digits, kind="call", direction="out", va_name="Tracy", status="completed", created_at=at),
    ])
    db.session.commit()
    start, end, _, _ = window({"days": 7})
    t = funnel(start, end, "Tracy")
    assert t["dials"] == 6 and t["connects"] == 3 and t["reach_rate"] == 50.0 and t["wins"] == 1
    assert [v["va"] for v in t["by_va"]] == ["Tracy"]
    assert t["texts"] == {"sent": 1, "received": 1}             # only replies to numbers she texted
    everyone = funnel(start, end)
    assert everyone["texts"] == {"sent": 2, "received": 2}


def test_callbacks_set_vs_kept():
    p1 = _prospect("Kept Co", "5615550201")
    p2 = _prospect("Missed Co", "5615550202")
    p3 = _prospect("Pending Co", "5615550203")
    two_days_ago = _now() - timedelta(days=2)
    # kept: callback set for yesterday 10:00, called back yesterday 10:30
    cb1 = _attempt(p1, "callback", at=two_days_ago)
    db.session.add(AuditEvent(action="callback", target_type="prospect", target_id=p1.id,
                              meta={"at": (two_days_ago + timedelta(days=1)).isoformat()}, created_at=two_days_ago))
    _attempt(p1, "interested", at=two_days_ago + timedelta(days=1, minutes=30))
    # missed: callback due yesterday, no later touch
    _attempt(p2, "callback", at=two_days_ago)
    db.session.add(AuditEvent(action="callback", target_type="prospect", target_id=p2.id,
                              meta={"at": (two_days_ago + timedelta(days=1)).isoformat()}, created_at=two_days_ago))
    # pending: callback set for next week
    _attempt(p3, "callback", at=_now() - timedelta(hours=1))
    db.session.add(AuditEvent(action="callback", target_type="prospect", target_id=p3.id,
                              meta={"at": (_now() + timedelta(days=5)).isoformat()}, created_at=_now() - timedelta(hours=1)))
    db.session.commit()
    start, end, _, _ = window({"days": 7})
    cb = funnel(start, end)["callbacks"]
    assert cb == {"set": 3, "kept": 1, "pending": 1, "kept_rate": 50.0}
    assert cb1.outcome == "callback"


def test_economics_costs_from_shifts_and_rate(client):
    p = _prospect("Palm Coast PM", "5615550301")
    start = _now() - timedelta(hours=3)
    db.session.add(VaShift(va_name="Tracy", started_at=start, ended_at=start + timedelta(hours=2)))
    db.session.commit()
    for o in ("voicemail", "voicemail", "interested", "vendor_listed"):
        _attempt(p, o, at=start + timedelta(minutes=10))
    r = _va(client, "/api/va/analytics/economics", {"days": 30}).get_json()
    assert r["rate"] == 6.0
    w = r["window"]
    tracy = {v["va"]: v for v in w["vas"]}["Tracy"]
    assert tracy["hours"] == 2.0 and tracy["cost"] == 12.0
    assert tracy["dials"] == 4 and tracy["cost_per_dial"] == 3.0
    assert tracy["connects"] == 2 and tracy["cost_per_connect"] == 6.0
    assert tracy["cost_per_interested"] == 12.0 and tracy["cost_per_win"] == 12.0 and tracy["dials_per_hour"] == 2.0
    assert w["totals"]["cost"] == 12.0 and w["totals"]["cost_per_win"] == 12.0
    assert r["period"]["label"] and r["period"]["totals"]["hours"] == 2.0
    with mock.patch.dict(os.environ, {"VA_HOURLY_RATE": "9.50"}):
        cache_clear()
        r2 = _va(client, "/api/va/analytics/economics", {"days": 30}).get_json()
    assert r2["rate"] == 9.5 and r2["window"]["totals"]["cost"] == 19.0


def test_lists_group_by_import_day():
    today = _now()
    old = today - timedelta(days=3)
    a = _prospect("A", "5615550401", created=old)
    b = _prospect("B", "5615550402", created=old + timedelta(minutes=5), category="HOA")
    c = _prospect("C", "5615550403", created=today)
    _attempt(a, "voicemail"); _attempt(a, "interested"); _attempt(b, "vendor_listed")
    a.attempts = 2; b.attempts = 1; db.session.commit()
    rows = lists(30)["lists"]
    assert len(rows) == 2 and rows[0]["size"] == 1 and rows[0]["dials"] == 0         # newest first
    batch = rows[1]
    assert batch["size"] == 2 and batch["worked"] == 2 and batch["worked_pct"] == 100.0
    assert batch["dials"] == 3 and batch["reach"] == 2 and batch["interested"] == 1 and batch["wins"] == 1
    assert batch["day"] == to_local(old).date().isoformat()
    assert {x["category"] for x in batch["categories"]} == {"property management", "hoa"}
    assert c.id


def test_timeseries_fills_every_day():
    p = _prospect("Palm Coast PM", "5615550501")
    _attempt(p, "voicemail", at=_at_local(9, days_ago=2))
    _attempt(p, "interested", at=_at_local(15, days_ago=2))
    _attempt(p, "converted", at=_at_local(9))
    start, end, _, _ = window({"days": 5})
    s = timeseries(start, end)
    assert len(s) == 5 and s[-1]["day"] == to_local(_now()).date().isoformat()
    assert s[-3] == {"day": to_local(_at_local(9, days_ago=2)).date().isoformat(), "dials": 2, "connects": 1, "interested": 1, "wins": 0}
    assert s[-1]["wins"] == 1 and s[-2]["dials"] == 0


def test_window_periods():
    s, e, label, days = window({"period": "today"})
    assert label == "Today" and days == 1 and to_local(s).hour == 0
    s, e, label, days = window({"period": "week"})
    assert to_local(s).weekday() == 0 and 1 <= days <= 7
    s, e, label, days = window({"period": "pay_period"})
    assert "–" in label and 1 <= days <= 14
    assert window({"days": "999"})[3] == 365 and window({"days": "x"})[3] == 30


def test_role_gating(client):
    tracy, _ = create_desk_user("tracy@goumuve.com", "Tracy Jamesyoung", "va", "pw-tracy")
    boss, _ = create_desk_user("boss@goumuve.com", "Shamar", "manager", "pw-boss")
    p = _prospect("Palm Coast PM", "5615550601")
    _attempt(p, "interested", va="Tracy")
    _attempt(p, "voicemail", va="Trixie")
    va = client.post("/api/desk/login", json={"email": "tracy@goumuve.com", "password": "pw-tracy"}).get_json()["token"]
    mgr = client.post("/api/desk/login", json={"email": "boss@goumuve.com", "password": "pw-boss"}).get_json()["token"]
    h = lambda t: {"Authorization": "Bearer " + t}
    # a VA on a real login only ever sees herself, whatever she asks for
    r = client.post("/api/va/analytics/funnel", json={"days": 7, "va": "Trixie"}, headers=h(va)).get_json()
    assert r["scope"] == "va" and r["va"] == "Tracy" and r["dials"] == 1
    assert client.post("/api/va/analytics/economics", json={}, headers=h(va)).status_code == 403
    assert client.post("/api/va/analytics/lists", json={}, headers=h(va)).status_code == 403
    # manager: everyone, or any one VA
    r = client.post("/api/va/analytics/funnel", json={"days": 7}, headers=h(mgr)).get_json()
    assert r["scope"] == "all" and r["dials"] == 2
    r = client.post("/api/va/analytics/funnel", json={"days": 7, "va": "Trixie"}, headers=h(mgr)).get_json()
    assert r["va"] == "Trixie" and r["dials"] == 1
    assert client.post("/api/va/analytics/economics", json={}, headers=h(mgr)).status_code == 200
    assert client.post("/api/va/analytics/lists", json={}, headers=h(mgr)).status_code == 200
    ts = client.post("/api/va/analytics/timeseries", json={"days": 3}, headers=h(va)).get_json()
    assert ts["va"] == "Tracy" and len(ts["series"]) == 3
    # no identity at all
    assert client.post("/api/va/analytics/funnel", json={}).status_code == 401
    assert client.post("/api/va/analytics/economics", json={"code": "wrong"}).status_code == 401


def test_cache_is_keyed_by_args(client):
    p = _prospect("Palm Coast PM", "5615550701")
    _attempt(p, "interested")
    assert _va(client, "/api/va/analytics/funnel", {"days": 7}).get_json()["dials"] == 1
    _attempt(p, "voicemail")
    # same args inside the TTL → cached
    assert _va(client, "/api/va/analytics/funnel", {"days": 7}).get_json()["dials"] == 1
    # different args → fresh
    assert _va(client, "/api/va/analytics/funnel", {"days": 14}).get_json()["dials"] == 2
    assert _va(client, "/api/va/analytics/funnel", {"days": 7, "va": "Tracy"}).get_json()["dials"] == 2
    assert _va(client, "/api/va/analytics/funnel", {"period": "today"}).get_json()["dials"] == 2
    cache_clear()
    assert _va(client, "/api/va/analytics/funnel", {"days": 7}).get_json()["dials"] == 2
    with mock.patch.dict(os.environ, {"ANALYTICS_CACHE_SECONDS": "0"}):
        _attempt(p, "no_answer")
        assert _va(client, "/api/va/analytics/funnel", {"days": 7}).get_json()["dials"] == 3
    assert analytics._ttl() == 60


def test_manager_page_serves_and_desk_loads_addon(client):
    r = client.get("/va/manager")
    assert r.status_code == 200
    body = r.data.decode()
    assert "/static/manager.js" in body and "/static/manager.css" in body and "/va/app.css" in body
    assert "<script>" not in body                                   # CSP: no inline scripts
    assert "script-src 'self'" in r.headers.get("Content-Security-Policy", "")
    assert client.get("/static/manager.js").status_code == 200
    assert client.get("/static/desk-analytics.js").status_code == 200
    desk = client.get("/va/calls").data.decode()
    assert desk.index("/static/desk-analytics.js") < desk.index("/va/calls.js")
