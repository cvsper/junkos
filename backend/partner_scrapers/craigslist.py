"""
Craigslist scraper — ported from `partner_scraper.py` into the v1 dispatcher
shape. Public entry is `scrape(city, limit)`. The legacy wrapper
`partner_scraper.scrape_craigslist()` still works and is not touched here.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Dict, List, Optional

import requests

from . import (
    EMAIL_RE,
    PHONE_RE,
    REQUEST_DELAY_SEC,
    compute_dedupe_hash,
    http_get,
    pick_user_agent,
)

logger = logging.getLogger(__name__)
_SOURCE = "craigslist"

DEFAULT_QUERIES = ["junk+hauling", "hauler", "moving"]
CITY_TO_SUBDOMAIN = {
    "miami": "miami",
    "fort lauderdale": "southflorida",
    "ftl": "southflorida",
    "west palm beach": "southflorida",
    "wpb": "southflorida",
    "tampa": "tampa",
    "tpa": "tampa",
}


def _fetch(session: requests.Session, url: str) -> Optional[str]:
    return http_get(session, url, source=_SOURCE)


def _parse_listings(html: str) -> List[Dict]:
    try:
        from bs4 import BeautifulSoup
    except Exception:  # pragma: no cover
        return _regex_fallback(html)

    soup = BeautifulSoup(html, "html.parser")
    results: List[Dict] = []
    for li in soup.select("li.cl-static-search-result, li.result-row"):
        pid = li.get("data-pid") or ""
        link = li.find("a", href=True)
        if not link:
            continue
        title_el = li.find(class_="title") or link
        title = title_el.get_text(" ", strip=True)
        results.append({
            "external_id": pid or link["href"],
            "url": link["href"],
            "title": title,
        })
    return results


def _regex_fallback(html: str) -> List[Dict]:
    out = []
    for m in re.finditer(
        r'data-pid="(\d+)".*?href="(https?://[^"]+)".*?>([^<]+)</a>',
        html, flags=re.DOTALL,
    ):
        out.append({
            "external_id": m.group(1),
            "url": m.group(2),
            "title": m.group(3).strip(),
        })
    return out


def _extract_detail(html: Optional[str]):
    if not html:
        return "", None, None
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        body_el = soup.find(id="postingbody")
        body = body_el.get_text(" ", strip=True) if body_el else ""
    except Exception:
        body = re.sub(r"<[^>]+>", " ", html)
    phone_m = PHONE_RE.search(body)
    email_m = EMAIL_RE.search(body)
    return body, (phone_m.group(0) if phone_m else None), (email_m.group(0) if email_m else None)


def _guess_name(title: str, body: str) -> Optional[str]:
    m = re.search(r"\b([A-Z][a-z]+)\s+([A-Z][a-z]+)", (title or "") + " " + (body or ""))
    if m:
        return "{} {}".format(m.group(1), m.group(2))
    return None


def scrape(city: str = "Miami", limit: int = 25) -> List[Dict]:
    """Scrape Craigslist `lbs` (labor/gigs) for junk/hauling listings.

    Returns a list of listing dicts (never raises; returns [] on failure).
    """
    sub = CITY_TO_SUBDOMAIN.get((city or "").strip().lower(), "miami")
    session = requests.Session()
    session.headers.update({"User-Agent": pick_user_agent()})

    all_rows: List[Dict] = []
    for query in DEFAULT_QUERIES:
        if len(all_rows) >= limit:
            break
        search_url = "https://{}.craigslist.org/search/lbs?query={}".format(sub, query)
        logger.info("craigslist search: %s", search_url)
        html = _fetch(session, search_url)
        time.sleep(REQUEST_DELAY_SEC)
        if not html:
            continue

        listings = _parse_listings(html)
        for li in listings:
            if len(all_rows) >= limit:
                break
            detail_html = _fetch(session, li.get("url", ""))
            time.sleep(REQUEST_DELAY_SEC)
            body, phone, email = _extract_detail(detail_html)
            if not (phone or email):
                continue
            row = {
                "source": "craigslist",
                "external_id": li.get("external_id"),
                "name_guess": _guess_name(li.get("title", ""), body),
                "phone": phone,
                "email": email,
                "url": li.get("url"),
                "notes": (body or "")[:500] or None,
                "raw_html": detail_html,
            }
            row["dedupe_hash"] = compute_dedupe_hash(
                phone=phone or "", email=email or "", external_id=row["external_id"] or "",
            )
            all_rows.append(row)

    return all_rows
