"""
Partner Acquisition Agent — Craigslist scraper (spec 07 §9 MVP).

Single-threaded, backend-IP only. No proxy for MVP; Craigslist tolerates this
volume from a single residential IP, and we stay well under their rate limits
via time.sleep(8) between requests.

For each search URL:
  1. Fetch the search results page.
  2. For each listing: extract post-id, title, price, posting-date.
  3. Fetch the detail page (1 extra round-trip) to mine phone + body text.
  4. POST to /partner/v1/internal/leads/ingest with X-Service-Token header.

The ingest endpoint handles deduping via sha256(phone + name) so re-runs are
idempotent. We never write to the DB from this module directly.
"""

import logging
import os
import re
import time
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

DEFAULT_QUERIES = ["junk+hauling", "hauler", "moving"]
DEFAULT_SUBDOMAIN = "miami"  # maps to spec metros: miami, ftl, wpb, tpa
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
REQUEST_DELAY_SEC = 8  # spec §8 Craigslist rate rail
FETCH_TIMEOUT_SEC = 12

PHONE_RE = re.compile(r"(\+?1[\s\-\.]?)?\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}")


def _parse_listings(html):
    """Extract listings from search-results HTML. Falls back to regex if
    BeautifulSoup is unavailable."""
    try:
        from bs4 import BeautifulSoup  # noqa: WPS433 (optional dep)
    except Exception:  # pragma: no cover
        BeautifulSoup = None  # type: ignore

    if BeautifulSoup is None:
        # Minimal regex fallback — each result has data-pid="<id>".
        out = []
        for m in re.finditer(r'data-pid="(\d+)".*?href="(https?://[^"]+)".*?>([^<]+)</a>',
                             html, flags=re.DOTALL):
            out.append({
                "external_ref": m.group(1),
                "detail_url": m.group(2),
                "title": m.group(3).strip(),
            })
        return out

    soup = BeautifulSoup(html, "html.parser")
    results = []
    # Craigslist ships either <li class="cl-static-search-result"> or
    # <li class="result-row"> depending on list/gallery view.
    for li in soup.select("li.cl-static-search-result, li.result-row"):
        pid = li.get("data-pid") or ""
        link = li.find("a", href=True)
        if not link:
            continue
        title_el = li.find(class_="title") or link
        title = title_el.get_text(" ", strip=True)
        price_el = li.find(class_="result-price") or li.find(class_="price")
        price = price_el.get_text(strip=True) if price_el else None
        time_el = li.find("time")
        posted = time_el.get("datetime") if time_el else None
        results.append({
            "external_ref": pid or link["href"],
            "detail_url": link["href"],
            "title": title,
            "price": price,
            "posted": posted,
        })
    return results


def _fetch(url, session):
    try:
        resp = session.get(url, timeout=FETCH_TIMEOUT_SEC)
        if resp.status_code != 200:
            logger.warning("Craigslist fetch %s -> %s", url, resp.status_code)
            return None
        return resp.text
    except Exception:
        logger.exception("Craigslist fetch failed for %s", url)
        return None


def _extract_detail(html):
    """Return (body_text, phone_or_None)."""
    if not html:
        return "", None
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        body_el = soup.find(id="postingbody")
        body = body_el.get_text(" ", strip=True) if body_el else ""
    except Exception:
        # Strip HTML tags with a regex — good enough to mine phone numbers.
        body = re.sub(r"<[^>]+>", " ", html)
    match = PHONE_RE.search(body)
    return body, match.group(0) if match else None


def _guess_name(title, body):
    """Very rough name-guess: first capitalized two words before common stop words."""
    # e.g. "Bob's Hauling — pickup truck $100/load"
    m = re.search(r"\b([A-Z][a-z]+)\s+([A-Z][a-z]+)", (title or "") + " " + (body or ""))
    if m:
        return "{} {}".format(m.group(1), m.group(2))
    return None


def _post_ingest(ingest_url, token, payload):
    try:
        resp = requests.post(
            ingest_url,
            json=payload,
            headers={"X-Service-Token": token, "Content-Type": "application/json"},
            timeout=FETCH_TIMEOUT_SEC,
        )
        return resp.status_code, (resp.json() if resp.content else {})
    except Exception as exc:
        logger.warning("ingest POST failed: %s", exc)
        return None, None


def scrape_craigslist(
    metro="miami",
    subdomain=DEFAULT_SUBDOMAIN,
    queries=None,
    ingest_url=None,
    service_token=None,
    max_listings_per_query=20,
    sleep_between=REQUEST_DELAY_SEC,
):
    """Scrape Craigslist /search/lbs for hauling/moving listings.

    Returns a summary dict: {listings_found, ingested, deduped, errors}.
    Does NOT raise — logs and returns a partial summary on failure.
    """
    queries = queries or DEFAULT_QUERIES
    ingest_url = ingest_url or os.environ.get(
        "PARTNER_INGEST_URL",
        "http://localhost:5000/partner/v1/internal/leads/ingest",
    )
    service_token = service_token or os.environ.get("PARTNER_SERVICE_TOKEN", "")

    summary = {"listings_found": 0, "ingested": 0, "deduped": 0, "errors": 0}
    if not service_token:
        logger.error("scrape_craigslist: PARTNER_SERVICE_TOKEN not set")
        summary["errors"] += 1
        return summary

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    for q in queries:
        search_url = "https://{}.craigslist.org/search/lbs?query={}".format(subdomain, q)
        logger.info("Craigslist search: %s", search_url)
        html = _fetch(search_url, session)
        time.sleep(sleep_between)
        if not html:
            summary["errors"] += 1
            continue

        listings = _parse_listings(html)[:max_listings_per_query]
        summary["listings_found"] += len(listings)

        for li in listings:
            detail_html = _fetch(li["detail_url"], session)
            time.sleep(sleep_between)
            body, phone = _extract_detail(detail_html)
            if not phone:
                # Skip — no phone means we can't SMS and we can't dedupe well.
                continue

            payload = {
                "source": "craigslist",
                "search_url": search_url,
                "external_ref": li.get("external_ref"),
                "name_guess": _guess_name(li.get("title"), body),
                "phone": phone,
                "metro": metro,
                "raw": {
                    "title": li.get("title"),
                    "price": li.get("price"),
                    "posted": li.get("posted"),
                    "detail_url": li.get("detail_url"),
                    "body_snippet": (body or "")[:500],
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                },
            }
            status, body_json = _post_ingest(ingest_url, service_token, payload)
            if status in (200, 201):
                if body_json and body_json.get("deduped"):
                    summary["deduped"] += 1
                else:
                    summary["ingested"] += 1
            else:
                summary["errors"] += 1

    logger.info("Craigslist scrape summary: %s", summary)
    return summary


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    print(scrape_craigslist())
