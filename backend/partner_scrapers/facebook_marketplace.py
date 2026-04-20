"""
Facebook Marketplace scraper — public-listing-only (spec 07 §8 "never
login-gated content"). In practice FB gates most listing pages behind a login
redirect; when that happens this module returns [] and logs a warning.

Strategy:
  1. GET https://www.facebook.com/marketplace/<city>/search/?query=junk+hauling
  2. If the response HTML still contains a `<script type="application/ld+json">`
     block describing listings, parse it. Otherwise warn and return [].
  3. Rate-limit 8s between requests per spec §8.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Dict, List, Optional

import requests

from . import (
    EMAIL_RE,
    FETCH_TIMEOUT_SEC,
    PHONE_RE,
    REQUEST_DELAY_SEC,
    USER_AGENT,
    compute_dedupe_hash,
)

logger = logging.getLogger(__name__)

CITY_SLUG = {
    "miami": "miami",
    "fort lauderdale": "fortlauderdale",
    "ftl": "fortlauderdale",
    "west palm beach": "westpalmbeach",
    "wpb": "westpalmbeach",
    "tampa": "tampa",
    "tpa": "tampa",
}

SEARCH_URL_TMPL = (
    "https://www.facebook.com/marketplace/{slug}/search/"
    "?query=junk%20hauling%20driver"
)


def _fetch(session: requests.Session, url: str) -> Optional[str]:
    try:
        resp = session.get(url, timeout=FETCH_TIMEOUT_SEC, allow_redirects=True)
        if resp.status_code != 200:
            logger.warning("fb_marketplace fetch %s -> %s", url, resp.status_code)
            return None
        # Login-gate heuristic: FB redirects to /login/ when the page is gated.
        final = str(resp.url or "")
        if "/login" in final or "login.php" in final:
            logger.warning("fb_marketplace gated by login; skipping (%s)", final)
            return None
        return resp.text
    except Exception:
        logger.exception("fb_marketplace fetch failed for %s", url)
        return None


def _extract_from_html(html: str) -> List[Dict]:
    """Pull any listing-looking blobs from the HTML. Best-effort."""
    out: List[Dict] = []
    # FB ships server-rendered data in <script type="application/json"> blobs.
    # Mining them is fragile — we only look for phone/email patterns in the
    # visible body text and treat each hit as a distinct listing.
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
    except Exception:
        text = re.sub(r"<[^>]+>", " ", html or "")

    seen = set()
    for m in PHONE_RE.finditer(text):
        phone = m.group(0)
        if phone in seen:
            continue
        seen.add(phone)
        out.append({
            "source": "fb_marketplace",
            "external_id": None,
            "phone": phone,
            "email": None,
            "name_guess": None,
            "url": None,
            "notes": None,
        })
    for m in EMAIL_RE.finditer(text):
        email = m.group(0)
        if email in seen:
            continue
        seen.add(email)
        out.append({
            "source": "fb_marketplace",
            "external_id": None,
            "phone": None,
            "email": email,
            "name_guess": None,
            "url": None,
            "notes": None,
        })
    return out


def scrape(city: str = "Miami", limit: int = 25) -> List[Dict]:
    """Return FB Marketplace-derived listings or [] on login gating.

    This scraper is best-effort. FB will usually gate us and we return [] with
    a warning. Downstream pipeline treats zero-result runs as healthy.
    """
    slug = CITY_SLUG.get((city or "").strip().lower(), "miami")
    url = SEARCH_URL_TMPL.format(slug=slug)

    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
    })

    html = _fetch(session, url)
    time.sleep(REQUEST_DELAY_SEC)
    if not html:
        return []

    raw_rows = _extract_from_html(html)
    out: List[Dict] = []
    for row in raw_rows[:limit]:
        row["url"] = url
        row["raw_html"] = html[:4000]  # cap to keep payloads sane
        row["dedupe_hash"] = compute_dedupe_hash(
            phone=row.get("phone") or "",
            email=row.get("email") or "",
            external_id=row.get("external_id") or "",
        )
        out.append(row)
    return out
