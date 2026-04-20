"""
Scraper hardening tests (item 7.2 follow-up to spec 07 §9).

Focus: retry/backoff, Retry-After honor, rotating UA, per-source stats,
Indeed SERP-smear regression, Thumbtack profile follow-through.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from partner_scrapers import (
    get_scraper_stats,
    http_get,
    pick_user_agent,
    reset_scraper_stats,
)


# ---------------------------------------------------------------------------
# http_get behavior
# ---------------------------------------------------------------------------
class _FakeResponse:
    def __init__(self, status, text="ok", headers=None):
        self.status_code = status
        self.text = text
        self.headers = headers or {}
        self.url = "https://example.com"


class _FakeSession:
    def __init__(self, responses):
        # responses: list of _FakeResponse OR Exception instances
        self._responses = list(responses)
        self.calls = 0

    def get(self, url, timeout=None, allow_redirects=True):
        self.calls += 1
        r = self._responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture(autouse=True)
def _clear_stats():
    reset_scraper_stats()
    yield
    reset_scraper_stats()


def test_http_get_returns_body_on_200():
    sess = _FakeSession([_FakeResponse(200, text="hello")])
    body = http_get(sess, "https://x", source="test", sleep_fn=lambda _s: None)
    assert body == "hello"
    stats = get_scraper_stats()["test"]
    assert stats["attempts"] == 1
    assert stats["fetched"] == 1
    assert stats["errors"] == 0


def test_http_get_retries_on_500_then_succeeds():
    sess = _FakeSession(
        [_FakeResponse(500), _FakeResponse(200, text="ok")]
    )
    body = http_get(
        sess, "https://x", source="test", sleep_fn=lambda _s: None,
    )
    assert body == "ok"
    assert sess.calls == 2
    stats = get_scraper_stats()["test"]
    assert stats["errors"] == 1
    assert stats["fetched"] == 1


def test_http_get_honors_retry_after_header():
    sleeps = []
    sess = _FakeSession([
        _FakeResponse(429, headers={"Retry-After": "7"}),
        _FakeResponse(200, text="ok"),
    ])
    body = http_get(
        sess, "https://x", source="test",
        sleep_fn=lambda s: sleeps.append(s),
    )
    assert body == "ok"
    assert sleeps == [7.0]
    assert get_scraper_stats()["test"]["rate_limited"] == 1


def test_http_get_caps_backoff_at_30s():
    sleeps = []
    sess = _FakeSession([
        _FakeResponse(503, headers={"Retry-After": "9999"}),
        _FakeResponse(200, text="ok"),
    ])
    http_get(
        sess, "https://x", source="test",
        sleep_fn=lambda s: sleeps.append(s),
    )
    assert sleeps == [30]


def test_http_get_gives_up_after_max_attempts_on_500():
    sess = _FakeSession([_FakeResponse(500)] * 5)
    body = http_get(
        sess, "https://x", source="test",
        max_attempts=3, sleep_fn=lambda _s: None,
    )
    assert body is None
    assert sess.calls == 3
    stats = get_scraper_stats()["test"]
    assert stats["attempts"] == 1
    assert stats["errors"] == 3


def test_http_get_no_retry_on_404():
    sess = _FakeSession([_FakeResponse(404)])
    body = http_get(
        sess, "https://x", source="test", sleep_fn=lambda _s: None,
    )
    assert body is None
    assert sess.calls == 1  # no retry on 4xx-other-than-429


def test_http_get_survives_network_exception():
    import requests as _rq
    sess = _FakeSession([
        _rq.ConnectionError("boom"),
        _FakeResponse(200, text="ok"),
    ])
    body = http_get(
        sess, "https://x", source="test", sleep_fn=lambda _s: None,
    )
    assert body == "ok"
    assert get_scraper_stats()["test"]["errors"] == 1


# ---------------------------------------------------------------------------
# pick_user_agent rotation
# ---------------------------------------------------------------------------
def test_pick_user_agent_returns_allowed_string():
    from partner_scrapers import _USER_AGENTS
    ua = pick_user_agent()
    assert ua in _USER_AGENTS
    assert "UmuvePartnerBot" in ua


# ---------------------------------------------------------------------------
# Indeed: SERP-smear regression
# ---------------------------------------------------------------------------
def test_indeed_parser_does_not_smear_serp_phone_onto_first_listing():
    """Regression: earlier v1 code attached any phone found in the SERP body
    to out[0].phone — that was wrong (the number may be Indeed's support line,
    not the advertiser's). This test asserts listings parse with phone=None.
    """
    from partner_scrapers import indeed

    # SERP HTML with a stray support phone NOT attributable to any listing.
    html = """
    <html><body>
      <div>Customer support: 1-800-555-0100</div>
      <a class="tapItem" data-jk="abc123def456" href="/viewjob?jk=abc123def456">
        <h2>Junk Removal Driver</h2>
        <span class="companyName">Bob's Hauling</span>
        <div class="job-snippet">Drive truck, remove debris.</div>
      </a>
    </body></html>
    """
    listings = indeed._parse(html)
    assert len(listings) >= 1
    for row in listings:
        assert row["phone"] is None, "SERP phone must not smear onto listings"
        assert row["email"] is None


# ---------------------------------------------------------------------------
# Thumbtack: profile follow-through
# ---------------------------------------------------------------------------
def test_thumbtack_profile_follow_through_pulls_phone(monkeypatch):
    """The SERP never has phones. Profile follow-through should recover them
    for the top N cards.
    """
    from partner_scrapers import thumbtack

    serp_html = """
    <html><body>
      <a href="/pros/bobs-hauling-123"><div>Bob's Hauling</div></a>
      <a href="/pros/fast-removal-456"><div>Fast Removal</div></a>
    </body></html>
    """
    profile_html_bob = "<html><body>Call us: 305-555-1234</body></html>"
    profile_html_fast = "<html><body>Email: hi@fastremoval.com</body></html>"

    calls = {"urls": []}

    def _fake_fetch(session, url):
        calls["urls"].append(url)
        if "near-me/?zip_code=33101" in url:
            return serp_html
        if "bobs-hauling-123" in url:
            return profile_html_bob
        if "fast-removal-456" in url:
            return profile_html_fast
        return None

    monkeypatch.setattr(thumbtack, "_fetch", _fake_fetch)
    monkeypatch.setattr(thumbtack.time, "sleep", lambda _s: None)

    rows = thumbtack.scrape(city="Miami", limit=10)
    assert len(rows) == 2

    by_name = {r["name_guess"]: r for r in rows}
    assert by_name["Bob's Hauling"]["phone"] == "305-555-1234"
    assert by_name["Fast Removal"]["email"] == "hi@fastremoval.com"

    # Dedupe hash should use phone/email now (not just external_id).
    assert by_name["Bob's Hauling"]["dedupe_hash"] != by_name["Fast Removal"]["dedupe_hash"]


def test_thumbtack_profile_follow_through_capped(monkeypatch):
    """PROFILE_FOLLOW_THROUGH caps the number of profile fetches regardless of
    how many SERP rows came back — prevents runaway 8s * N delays.
    """
    from partner_scrapers import thumbtack

    # SERP with 10 distinct pros.
    cards = "\n".join(
        '<a href="/pros/pro-{i}"><div>Pro {i}</div></a>'.format(i=i)
        for i in range(10)
    )
    serp_html = "<html><body>{}</body></html>".format(cards)

    fetch_counts = {"serp": 0, "profile": 0}

    def _fake_fetch(session, url):
        if "near-me/?zip_code=33101" in url:
            fetch_counts["serp"] += 1
            return serp_html
        fetch_counts["profile"] += 1
        return "<html><body>no contact info</body></html>"

    monkeypatch.setattr(thumbtack, "_fetch", _fake_fetch)
    monkeypatch.setattr(thumbtack.time, "sleep", lambda _s: None)

    thumbtack.scrape(city="Miami", limit=25)
    assert fetch_counts["serp"] == 1
    assert fetch_counts["profile"] == thumbtack.PROFILE_FOLLOW_THROUGH


# ---------------------------------------------------------------------------
# Stats aggregation after run_all_scrapers
# ---------------------------------------------------------------------------
def test_run_all_scrapers_emits_listings_count_per_source(monkeypatch):
    """run_all_scrapers should bump the `listings` counter per source."""
    from partner_scrapers import (
        craigslist, facebook_marketplace, indeed, nextdoor, run_all_scrapers,
        thumbtack,
    )

    def _empty(city, limit):
        return []

    def _two(city, limit):
        return [
            {"source": "craigslist", "external_id": "1", "phone": "3051111111"},
            {"source": "craigslist", "external_id": "2", "phone": "3052222222"},
        ]

    monkeypatch.setattr(craigslist, "scrape", _two)
    monkeypatch.setattr(facebook_marketplace, "scrape", _empty)
    monkeypatch.setattr(thumbtack, "scrape", _empty)
    monkeypatch.setattr(nextdoor, "scrape", _empty)
    monkeypatch.setattr(indeed, "scrape", _empty)

    results = run_all_scrapers(city="Miami", limit_per_source=10)
    assert len(results) == 2
    stats = get_scraper_stats()
    assert stats["craigslist"]["listings"] == 2
    assert stats["facebook_marketplace"]["listings"] == 0
    assert stats["thumbtack"]["listings"] == 0
    assert stats["nextdoor"]["listings"] == 0
    assert stats["indeed"]["listings"] == 0


# ---------------------------------------------------------------------------
# FB Marketplace: login-gate detection on body
# ---------------------------------------------------------------------------
def test_fb_marketplace_detects_login_gate_in_body(monkeypatch):
    """If the returned body contains FB's login form marker, treat as gated."""
    from partner_scrapers import facebook_marketplace

    def _fake_http_get(session, url, **_):
        return '<html><body><form id="loginform">sign in</form></body></html>'

    monkeypatch.setattr(facebook_marketplace, "http_get", _fake_http_get)
    monkeypatch.setattr(facebook_marketplace.time, "sleep", lambda _s: None)

    rows = facebook_marketplace.scrape(city="Miami", limit=10)
    assert rows == []


# ---------------------------------------------------------------------------
# Nextdoor: stays DEFERRED (stub unchanged)
# ---------------------------------------------------------------------------
def test_nextdoor_remains_deferred():
    from partner_scrapers import nextdoor
    assert nextdoor.scrape(city="Miami", limit=100) == []
