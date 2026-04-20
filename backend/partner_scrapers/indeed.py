"""
Indeed scraper — public job listings for "junk removal driver owner-operator".

We scrape the SERP only — the detail page usually requires JS/cookies. For v1
we capture: title, company, job URL (external_id), and snippet as notes.
Phone/email rarely appear on SERP, so `dedupe_hash` falls back to the job URL.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Dict, List, Optional
from urllib.parse import quote_plus

import requests

from . import (
    REQUEST_DELAY_SEC,
    compute_dedupe_hash,
    http_get,
    pick_user_agent,
)

logger = logging.getLogger(__name__)
_SOURCE = "indeed"

SEARCH_URL = (
    "https://www.indeed.com/jobs?q={q}&l={l}"
)
DEFAULT_QUERY = "junk removal driver owner-operator"


def _fetch(session: requests.Session, url: str) -> Optional[str]:
    return http_get(session, url, source=_SOURCE)


def _parse(html: str) -> List[Dict]:
    out: List[Dict] = []
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for card in soup.select("a.tapItem, a.jcs-JobTitle, a[data-jk]"):
            jk = card.get("data-jk") or ""
            href = card.get("href") or ""
            if not (jk or href):
                continue
            title_el = card.select_one("h2, span[title]")
            title = (title_el.get_text(" ", strip=True) if title_el else "") or card.get("title") or ""
            company_el = card.find(class_=re.compile("companyName", re.I))
            company = company_el.get_text(" ", strip=True) if company_el else None
            snippet_el = card.find(class_=re.compile("job-snippet|snippet", re.I))
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else None

            ext = jk or href
            url = "https://www.indeed.com/viewjob?jk={}".format(jk) if jk else (
                href if href.startswith("http") else "https://www.indeed.com" + href
            )
            out.append({
                "source": "indeed",
                "external_id": ext,
                "name_guess": company,
                "phone": None,
                "email": None,
                "url": url,
                "notes": (title + " — " + (snippet or ""))[:500] if (title or snippet) else None,
            })
    except Exception:
        # Regex fallback — grab jk codes from links.
        for m in re.finditer(r'jk=([a-f0-9]{12,})', html or ""):
            ext = m.group(1)
            out.append({
                "source": "indeed",
                "external_id": ext,
                "name_guess": None,
                "phone": None,
                "email": None,
                "url": "https://www.indeed.com/viewjob?jk={}".format(ext),
                "notes": None,
            })

    # NOTE: We deliberately do NOT lift phone/email from the SERP body and
    # attach it to out[0] — that was a correctness bug in the v1 scaffold.
    # A phone number appearing in the SERP chrome (e.g. Indeed's own support
    # line) is not attributable to any specific listing. Contact extraction
    # happens in the downstream outreach step when we actually load the
    # viewjob detail page per listing.

    # Dedupe on external_id.
    seen = set()
    unique: List[Dict] = []
    for row in out:
        k = row.get("external_id")
        if not k or k in seen:
            continue
        seen.add(k)
        unique.append(row)
    return unique


def scrape(city: str = "Miami", limit: int = 25) -> List[Dict]:
    q = quote_plus(DEFAULT_QUERY)
    l = quote_plus(city or "Miami, FL")
    url = SEARCH_URL.format(q=q, l=l)

    session = requests.Session()
    session.headers.update({"User-Agent": pick_user_agent()})
    html = _fetch(session, url)
    time.sleep(REQUEST_DELAY_SEC)
    if not html:
        return []

    rows = _parse(html)[:limit]
    for row in rows:
        row["dedupe_hash"] = compute_dedupe_hash(
            phone=row.get("phone") or "",
            email=row.get("email") or "",
            external_id=row.get("external_id") or "",
        )
    return rows
