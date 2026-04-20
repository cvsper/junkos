"""
Partner Acquisition Agent — scraper dispatcher (spec 07 §9 v1).

Public surface:
    run_all_scrapers(city, limit_per_source) -> list[dict]

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
  * Polite User-Agent string (shared constant)
  * Never raise — return [] + log on error
  * Are safe to call with no network (monkeypatch `_fetch` in tests)
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Callable, Dict, List

logger = logging.getLogger(__name__)

REQUEST_DELAY_SEC = 8  # spec §8 Craigslist / FB Marketplace rate rail
FETCH_TIMEOUT_SEC = 12
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 UmuvePartnerBot/1.0"
)

PHONE_RE = re.compile(r"(\+?1[\s\-\.]?)?\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}")
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


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

    sources: List[Callable] = [
        craigslist.scrape,
        facebook_marketplace.scrape,
        thumbtack.scrape,
        nextdoor.scrape,
        indeed.scrape,
    ]

    results: List[Dict] = []
    for fn in sources:
        try:
            rows = fn(city=city, limit=limit_per_source) or []
        except Exception:
            logger.exception("scraper %s raised", fn.__module__)
            rows = []
        for row in rows:
            results.append(enrich(row))
    logger.info(
        "run_all_scrapers(city=%s, limit=%s) -> %s listings",
        city, limit_per_source, len(results),
    )
    return results
