"""
Nextdoor scraper — DEFERRED.

Nextdoor gates all business-listing + neighborhood content behind an
authenticated session and enforces device+neighborhood verification. Scraping
it from a headless backend IP violates their ToS and yields empty HTML.

Per spec §9 2-week v1, this module is stubbed and returns [] immediately with
a DEFERRED log line. Revisit when we have an API partnership or a human-in-
the-loop browser-extension ingest.
"""

from __future__ import annotations

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


def scrape(city: str = "Miami", limit: int = 25) -> List[Dict]:
    logger.info(
        "nextdoor scraper DEFERRED — returning [] (login-gated platform). "
        "city=%s limit=%s", city, limit,
    )
    return []
