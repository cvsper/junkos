"""
Thumbtack scraper — public "find pros" SERP for "junk hauling" in the given
city. Thumbtack doesn't expose phone numbers on public SERPs, so we capture
the pro profile URL as the dedupe key and leave phone/email to a later outreach
step (clicking through to the profile page).

For v1 we extract: business name, profile URL, review count as notes.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Dict, List, Optional
from urllib.parse import quote_plus

import requests

from . import (
    FETCH_TIMEOUT_SEC,
    REQUEST_DELAY_SEC,
    USER_AGENT,
    compute_dedupe_hash,
)

logger = logging.getLogger(__name__)

SEARCH_URL = (
    "https://www.thumbtack.com/k/junk-removal/near-me/?zip_code={zip}"
)
# Rough per-city zip mapping for MVP (expand per metro in v2).
CITY_ZIP = {
    "miami": "33101",
    "fort lauderdale": "33301",
    "ftl": "33301",
    "west palm beach": "33401",
    "wpb": "33401",
    "tampa": "33601",
    "tpa": "33601",
}

PRO_CARD_RE = re.compile(
    r'href="(/pros/[^"]+)"[^>]*>\s*<[^>]*>([^<]+)</',
    flags=re.DOTALL,
)


def _fetch(session: requests.Session, url: str) -> Optional[str]:
    try:
        resp = session.get(url, timeout=FETCH_TIMEOUT_SEC)
        if resp.status_code != 200:
            logger.warning("thumbtack fetch %s -> %s", url, resp.status_code)
            return None
        return resp.text
    except Exception:
        logger.exception("thumbtack fetch failed for %s", url)
        return None


def _parse(html: str) -> List[Dict]:
    out: List[Dict] = []
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select('a[href^="/pros/"]'):
            href = a.get("href") or ""
            name = a.get_text(" ", strip=True)
            if not href or not name:
                continue
            # Only keep the first card anchor per pro (avatar+name dupe).
            out.append({
                "source": "thumbtack",
                "external_id": href,
                "name_guess": name[:120],
                "phone": None,
                "email": None,
                "url": "https://www.thumbtack.com" + href,
                "notes": None,
            })
    except Exception:
        for m in PRO_CARD_RE.finditer(html or ""):
            out.append({
                "source": "thumbtack",
                "external_id": m.group(1),
                "name_guess": m.group(2).strip()[:120],
                "phone": None,
                "email": None,
                "url": "https://www.thumbtack.com" + m.group(1),
                "notes": None,
            })
    # Dedupe by external_id within a single run.
    seen = set()
    unique: List[Dict] = []
    for row in out:
        key = row.get("external_id")
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def scrape(city: str = "Miami", limit: int = 25) -> List[Dict]:
    zip_code = CITY_ZIP.get((city or "").strip().lower(), "33101")
    url = SEARCH_URL.format(zip=quote_plus(zip_code))

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    html = _fetch(session, url)
    time.sleep(REQUEST_DELAY_SEC)
    if not html:
        return []

    rows = _parse(html)[:limit]
    for row in rows:
        row["dedupe_hash"] = compute_dedupe_hash(
            phone="", email="", external_id=row.get("external_id") or "",
        )
    return rows
