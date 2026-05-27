"""
Review monitor — Tier 2-E of the airtight stack (SCAFFOLD).

Daily scan of public review surfaces (Google Business Profile, Yelp, App
Store, Trustpilot, Better Business Bureau) for new reviews about umuve.
Alerts the admin within an hour of any 1-3 star review so sevs can respond
publicly before the rating festers.

DESIGN — three fetcher strategies, mix as needed:
  1. Official API (where free/cheap):
     - Google Business Profile API — requires OAuth + verified business.
     - App Store Connect API — requires App Store key (JWT). umuve already
       has an App ID (6759219031); App Store Connect access is on sevs's
       Apple developer account.
     - Yelp Fusion API — paid, limited; deprecated free tier as of 2025.
  2. Public RSS / scrape (where APIs are gated):
     - Yelp public business page → parse HTML / RSS where available.
     - Google Maps reviews (limited via Places API).
  3. Third-party aggregator (paid):
     - ReviewTrackers, Birdeye, Podium. ~$50-100/mo, one integration.
     - Trustpilot has its own webhook → cheap.

This file ships the SHAPE — fetcher stubs that return a normalized list and
the alert pipeline. Wire in real fetchers once an approach is picked.

CONFIG NEEDED before going live:
  - GOOGLE_PLACE_ID                # for Google reviews via Places API
  - GOOGLE_PLACES_API_KEY          # API key with Places API enabled
  - APP_STORE_APP_ID=6759219031    # umuve iOS app
  - APP_STORE_CONNECT_KEY_PATH     # JWT key file (downloaded from App Store Connect)
  - APP_STORE_CONNECT_ISSUER_ID
  - APP_STORE_CONNECT_KEY_ID
  - YELP_BUSINESS_ID               # if Yelp Fusion paid tier is acquired
  - YELP_API_KEY

Usage:
    python review_monitor.py               # standalone
    # Render cron (daily morning):
    15 11 * * *  cd /app && python review_monitor.py
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

ALERT_RATING_THRESHOLD = int(os.environ.get("REVIEW_ALERT_THRESHOLD", "4"))
LOOKBACK_HOURS = int(os.environ.get("REVIEW_LOOKBACK_HOURS", "24"))


# ---------------------------------------------------------------------------
# Normalized review shape — every fetcher returns these
# ---------------------------------------------------------------------------
@dataclass
class Review:
    platform: str           # "google", "yelp", "appstore", ...
    external_id: str        # platform's unique ID for the review
    rating: int             # 1-5
    title: Optional[str]
    body: str
    author: str
    posted_at: datetime     # tz-aware UTC
    url: Optional[str]


# ---------------------------------------------------------------------------
# Fetcher stubs — replace each `return []` with the real implementation.
# Each fetcher MUST: return only reviews newer than `since`, never raise out
# (errors logged + empty list), normalize to the Review dataclass above.
# ---------------------------------------------------------------------------

def fetch_google_reviews(since):
    """Google Business Profile / Places API.

    Recommended path: enable Places API on the GOOGLE_PLACES_API_KEY project,
    use Place Details endpoint with GOOGLE_PLACE_ID, parse `reviews[]`. Note:
    Places API only returns the 5 most recent reviews — fine for daily polling.
    """
    place_id = os.environ.get("GOOGLE_PLACE_ID", "")
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
    if not place_id or not api_key:
        logger.info("Google reviews: GOOGLE_PLACE_ID / API_KEY not set — skipping")
        return []
    # TODO(implement): GET https://maps.googleapis.com/maps/api/place/details/json
    #   ?place_id={place_id}&fields=reviews&key={api_key}
    # Parse `result.reviews[]`, normalize, filter by posted_at >= since.
    logger.warning("fetch_google_reviews: TODO — implement Places API call")
    return []


def fetch_yelp_reviews(since):
    """Yelp Fusion API (paid as of 2025) OR scrape public page.

    Cheap MVP: hit the public Yelp business page and parse the HTML.
    Production: Yelp Fusion `/businesses/{id}/reviews` with YELP_API_KEY.
    """
    business_id = os.environ.get("YELP_BUSINESS_ID", "")
    api_key = os.environ.get("YELP_API_KEY", "")
    if not business_id or not api_key:
        logger.info("Yelp reviews: YELP_BUSINESS_ID / API_KEY not set — skipping")
        return []
    # TODO(implement): GET https://api.yelp.com/v3/businesses/{id}/reviews
    logger.warning("fetch_yelp_reviews: TODO — implement Yelp Fusion call")
    return []


def fetch_appstore_reviews(since):
    """App Store Connect API for umuve iOS app (6759219031).

    Auth is JWT signed with the App Store Connect private key. Endpoint:
    GET https://api.appstoreconnect.apple.com/v1/apps/{app_id}/customerReviews
    """
    app_id = os.environ.get("APP_STORE_APP_ID", "6759219031")
    key_path = os.environ.get("APP_STORE_CONNECT_KEY_PATH", "")
    if not app_id or not key_path:
        logger.info("App Store reviews: KEY_PATH not set — skipping")
        return []
    # TODO(implement): generate JWT, hit /v1/apps/{app_id}/customerReviews,
    # parse `data[].attributes` → Review, filter by `createdDate >= since`.
    logger.warning("fetch_appstore_reviews: TODO — implement App Store Connect call")
    return []


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def fetch_all(since):
    """Run every fetcher and return a flat list of new reviews."""
    reviews: List[Review] = []
    for fetcher in (fetch_google_reviews, fetch_yelp_reviews, fetch_appstore_reviews):
        try:
            reviews.extend(fetcher(since))
        except Exception:
            logger.exception("Fetcher %s failed", fetcher.__name__)
    return reviews


def alert_admin(review: Review):
    """Fire the admin alert for a low-rated review (dual-channel)."""
    admin_phone = os.environ.get("ADMIN_PHONE", "")
    admin_email = os.environ.get("ADMIN_EMAIL", "")

    if not admin_phone and not admin_email:
        logger.error(
            "Bad review on %s but NO ADMIN_PHONE/ADMIN_EMAIL configured — "
            "alert cannot be delivered.",
            review.platform,
        )
        return

    body_snippet = (review.body or "")[:280]

    if admin_phone:
        try:
            from sms_service import send_sms_async
            send_sms_async(admin_phone, (
                "⭐ {stars}-STAR REVIEW on {plat} by {author}:\n\n"
                "{body}\n\n"
                "Respond publicly fast — silence reads as confirmation."
            ).format(
                stars=review.rating,
                plat=review.platform,
                author=review.author or "?",
                body=body_snippet,
            ))
        except Exception:
            logger.exception("Failed to SMS bad-review alert")

    if admin_email:
        try:
            from email_service import send_email_async
            send_email_async(admin_email, (
                "⭐ {stars}-star review on {plat} — respond ASAP"
            ).format(stars=review.rating, plat=review.platform), (
                "<h2>{stars}-star review just posted</h2>"
                "<p><b>Platform:</b> {plat} • <b>Author:</b> {author} • "
                "<b>Posted:</b> {when}</p>"
                "<blockquote style='border-left:4px solid #ccc;padding-left:12px;"
                "color:#333'>{body}</blockquote>"
                "<p>{url}</p>"
                "<p><b>Playbook:</b> respond publicly within 24h. Acknowledge "
                "the specific complaint, take responsibility, offer to make it "
                "right offline. Never argue.</p>"
            ).format(
                stars=review.rating,
                plat=review.platform,
                author=review.author or "?",
                when=review.posted_at.isoformat() if review.posted_at else "?",
                body=(review.body or "").replace("<", "&lt;"),
                url=(
                    "<a href='{}'>{}</a>".format(review.url, review.url)
                    if review.url else ""
                ),
            ))
        except Exception:
            logger.exception("Failed to email bad-review alert")


def main():
    logger.info("=" * 60)
    logger.info("Review monitor starting")
    logger.info("=" * 60)

    since = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    reviews = fetch_all(since)

    logger.info("Fetched %d reviews since %s", len(reviews), since.isoformat())

    fired = 0
    for r in reviews:
        if r.rating < ALERT_RATING_THRESHOLD:
            alert_admin(r)
            fired += 1

    logger.info("Review monitor done — %d alerts fired", fired)


if __name__ == "__main__":
    main()
