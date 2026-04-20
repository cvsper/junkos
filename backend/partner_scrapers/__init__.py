"""
Partner Acquisition Agent — scraper dispatcher (spec 07 §9 v1).

Public surface:
    run_all_scrapers(city, limit_per_source) -> list[dict]
    http_get(session, url, *, max_attempts=3) -> Optional[str]
    get_scraper_stats() -> dict
    reset_scraper_stats() -> None

Each scraper module exposes `scrape(city: str, limit: int) -> list[dict]` and
returns a flat list of listing dicts with this shape:

    {
        "source": "craigslist" | "fb_marketplace" | "thumbtack" | "nextdoor" | "indeed",
        "external_id": "<platform-local id or URL>",
        "name_guess": "Bob's Hauling" | None,
        "phone": "3055551212" | None,
        "email": "bob@example.com" | None,
        "url": "https://...",
        "notes": "first 500 chars of body" | None,
        "raw_html": "<!doctype html>..." | None,
        "dedupe_hash": "<sha256 hex>",
    }

All scrapers:
  * 8-second rate-limit between HTTP calls (spec §8 rail)
  * Polite rotating User-Agent
  * Exponential backoff with Retry-After honor on 429/503
  * Never raise — return [] + log on error
  * Emit per-source counters to `get_scraper_stats()` for observability
"""

from __future__ import annotations

import hashlib
import logging
import random
import re
import time
from threading import Lock
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

REQUEST_DELAY_SEC = 8  # spec §8 Craigslist / FB Marketplace rate rail
FETCH_TIMEOUT_SEC = 12
MAX_FETCH_ATTEMPTS = 3

# Rotating User-Agent pool — reduces naive fingerprinting by the target sites.
# All desktop Chrome variants so HTML is served (not mobile).
_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 UmuvePartnerBot/1.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0 Safari/537.36 UmuvePartnerBot/1.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36 UmuvePartnerBot/1.0",
]

# Back-compat alias — older modules import USER_AGENT as a string.
USER_AGENT = _USER_AGENTS[0]


def pick_user_agent() -> str:
    return random.choice(_USER_AGENTS)


PHONE_RE = re.compile(r"(\+?1[\s\-\.]?)?\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}")
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


# ---------------------------------------------------------------------------
# Per-source health counters (last-run observability)
# ---------------------------------------------------------------------------
_STATS_LOCK = Lock()
_STATS: Dict[str, Dict[str, int]] = {}


def _bump(source: str, field: str, by: int = 1) -> None:
    with _STATS_LOCK:
        bucket = _STATS.setdefault(
            source,
            {"attempts": 0, "fetched": 0, "errors": 0, "rate_limited": 0, "listings": 0},
        )
        bucket[field] = bucket.get(field, 0) + by


def get_scraper_stats() -> Dict[str, Dict[str, int]]:
    """Return a defensive copy of the per-source counters."""
    with _STATS_LOCK:
        return {src: dict(fields) for src, fields in _STATS.items()}


def reset_scraper_stats() -> None:
    """Clear counters (used by tests + scheduled runs that want a fresh snapshot)."""
    with _STATS_LOCK:
        _STATS.clear()


# ---------------------------------------------------------------------------
# Shared HTTP fetcher with retry + backoff
# ---------------------------------------------------------------------------
def http_get(
    session,
    url: str,
    *,
    source: str = "unknown",
    max_attempts: int = MAX_FETCH_ATTEMPTS,
    timeout: int = FETCH_TIMEOUT_SEC,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Optional[str]:
    """GET with exponential backoff + Retry-After honor.

    Returns response body on 200, None on exhausted retries. Honors 429/503
    Retry-After headers (seconds). Caps backoff at 30s to avoid wedging a
    worker. Classifies outcomes into the per-source stats bucket.

    `sleep_fn` override exists so tests can skip real sleeps.
    """
    _bump(source, "attempts")

    backoff = 1.0
    import requests  # local import so module loads without requests

    for attempt in range(1, max_attempts + 1):
        try:
            resp = session.get(url, timeout=timeout, allow_redirects=True)
        except requests.RequestException as exc:
            logger.warning(
                "%s fetch network error on %s attempt=%d: %s",
                source, url, attempt, exc,
            )
            _bump(source, "errors")
            if attempt == max_attempts:
                return None
            sleep_fn(min(backoff, 30))
            backoff *= 2
            continue

        status = resp.status_code
        if status == 200:
            _bump(source, "fetched")
            return resp.text

        if status in (429, 503):
            _bump(source, "rate_limited")
            retry_after = resp.headers.get("Retry-After")
            delay = backoff
            if retry_after:
                try:
                    delay = float(retry_after)
                except ValueError:
                    pass
            logger.warning(
                "%s rate-limited %s (status=%s) — backing off %ss",
                source, url, status, delay,
            )
            if attempt == max_attempts:
                return None
            sleep_fn(min(delay, 30))
            backoff *= 2
            continue

        # 4xx other than 429: no point retrying.
        if 400 <= status < 500:
            logger.warning("%s fetch %s -> %s (no retry)", source, url, status)
            _bump(source, "errors")
            return None

        # 5xx: retry.
        logger.warning(
            "%s fetch %s -> %s attempt=%d", source, url, status, attempt,
        )
        _bump(source, "errors")
        if attempt == max_attempts:
            return None
        sleep_fn(min(backoff, 30))
        backoff *= 2

    return None


# ---------------------------------------------------------------------------
# Listing helpers
# ---------------------------------------------------------------------------
def compute_dedupe_hash(phone: str = "", email: str = "", external_id: str = "") -> str:
    """sha256 over whichever identifier is most stable.

    Priority: phone > email > external_id. Matches spec 07 §9 ("phone or email
    or external_id"). Digits-only for phone; lowercased for email.
    """
    phone_digits = re.sub(r"\D", "", phone or "")
    email_norm = (email or "").strip().lower()
    ext = (external_id or "").strip()
    basis = phone_digits or email_norm or ext or "unknown"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def enrich(listing: Dict) -> Dict:
    """Fill dedupe_hash if missing. Normalizes optional keys to None."""
    listing.setdefault("phone", None)
    listing.setdefault("email", None)
    listing.setdefault("external_id", None)
    listing.setdefault("name_guess", None)
    listing.setdefault("notes", None)
    listing.setdefault("url", None)
    listing.setdefault("raw_html", None)
    if not listing.get("dedupe_hash"):
        listing["dedupe_hash"] = compute_dedupe_hash(
            phone=listing.get("phone") or "",
            email=listing.get("email") or "",
            external_id=listing.get("external_id") or "",
        )
    return listing


def run_all_scrapers(city: str = "Miami", limit_per_source: int = 25) -> List[Dict]:
    """Call every scraper module and return aggregated listings.

    Scrapers run serially — each one sleeps 8s between its own calls, but we
    don't gate across sources. A misbehaving source never blocks the others
    because each scraper swallows its own exceptions.
    """
    from . import craigslist, facebook_marketplace, thumbtack, nextdoor, indeed

    # Walk modules (not bare functions) so the `listings` counter is keyed by
    # the scraper's real name even when tests monkeypatch `module.scrape` with
    # a lambda whose __module__ points at the test file.
    modules = [craigslist, facebook_marketplace, thumbtack, nextdoor, indeed]

    results: List[Dict] = []
    for mod in modules:
        source_name = mod.__name__.rsplit(".", 1)[-1]
        try:
            rows = mod.scrape(city=city, limit=limit_per_source) or []
        except Exception:
            logger.exception("scraper %s raised", source_name)
            rows = []
        _bump(source_name, "listings", by=len(rows))
        for row in rows:
            results.append(enrich(row))
    logger.info(
        "run_all_scrapers(city=%s, limit=%s) -> %s listings",
        city, limit_per_source, len(results),
    )
    return results
