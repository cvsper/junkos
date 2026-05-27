"""
Synthetic mystery-shop test — Tier 3-I of the airtight stack.

Once a day, this script runs through the customer's funnel as a synthetic
"shopper" — hits the booking-create endpoint with realistic data, the
service-area endpoint, the tracking endpoint, and (optionally) sends a
fake inbound SMS. If any step doesn't return the expected shape, fires
the URGENT admin alert.

The goal: catch funnel breakage within 24h, BEFORE a real customer does.

What it tests
=============
1. **Service-area static API** — GET /api/service-area returns the polygon.
2. **Service-area dynamic API** — GET /api/service-area/dynamic returns the
   live contractor coverage. (New in Tier 3-G.)
3. **Service-area check (in-area point)** — POST /api/service-area/check
   with a known good coord returns `in_service_area: true`.
4. **Service-area check (out-of-area point)** — same endpoint with NYC
   coords returns `in_service_area: false`.
5. **Tracking by code (404 path)** — GET /api/tracking/code/AAAAAAAA returns
   404 (proves the route is reachable; not just the happy path).
6. **Booking-create rejects clearly out-of-area** — POST /api/booking with
   NYC coords returns 400 with the "outside our service area" error. This
   confirms the gate is still gating; if it stops, every NYC visitor can
   book a job we can't fulfill.

What it does NOT test (intentionally)
=====================================
- No card charges. Booking-create returns the booking record only; payment
  is a separate step. The mystery shopper never touches the payment API,
  so no Stripe noise.
- No live phone call. Vapi mystery-call is a follow-up — see TODO below.

Usage
=====
    BACKEND_URL=https://junkos-backend.onrender.com python mystery_shop.py
    # Render cron (daily, slightly off-peak):
    23 12 * * *  cd /app && python mystery_shop.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Tuple

import requests

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

BACKEND_URL = os.environ.get("BACKEND_URL", "https://junkos-backend.onrender.com").rstrip("/")
TIMEOUT_S = 15

# Coordinates: West Palm Beach city center (in-area) and NYC (out-of-area)
COORD_IN_AREA = (26.7153, -80.0534)
COORD_OUT_OF_AREA = (40.7580, -73.9855)  # Times Square, NYC


def _check(label, fn) -> Tuple[bool, str]:
    """Run one check; return (ok, detail)."""
    try:
        ok, detail = fn()
        emoji = "✅" if ok else "❌"
        logger.info("%s %s — %s", emoji, label, detail)
        return ok, detail
    except Exception as exc:
        logger.exception("Check raised: %s", label)
        return False, "exception: {}".format(exc)


def check_static_service_area():
    r = requests.get(BACKEND_URL + "/api/service-area", timeout=TIMEOUT_S)
    if r.status_code != 200:
        return False, "status {}".format(r.status_code)
    data = r.json()
    if not data.get("service_area"):
        return False, "missing service_area in response"
    return True, "polygon returned"


def check_dynamic_service_area():
    r = requests.get(BACKEND_URL + "/api/service-area/dynamic", timeout=TIMEOUT_S)
    if r.status_code != 200:
        return False, "status {}".format(r.status_code)
    data = r.json()
    coverage = data.get("coverage") or {}
    return True, "{} contractor circle(s)".format(coverage.get("contractor_count", 0))


def check_service_area_in():
    r = requests.post(
        BACKEND_URL + "/api/service-area/check",
        json={"lat": COORD_IN_AREA[0], "lng": COORD_IN_AREA[1]},
        timeout=TIMEOUT_S,
    )
    if r.status_code != 200:
        return False, "status {}".format(r.status_code)
    if not r.json().get("in_service_area"):
        return False, "in_service_area = False for known-good WPB coord"
    return True, "in_service_area = True for WPB"


def check_service_area_out():
    r = requests.post(
        BACKEND_URL + "/api/service-area/check",
        json={"lat": COORD_OUT_OF_AREA[0], "lng": COORD_OUT_OF_AREA[1]},
        timeout=TIMEOUT_S,
    )
    if r.status_code != 200:
        return False, "status {}".format(r.status_code)
    if r.json().get("in_service_area"):
        return False, "in_service_area = True for NYC (geofence broken!)"
    return True, "in_service_area = False for NYC"


def check_tracking_404():
    r = requests.get(BACKEND_URL + "/api/tracking/code/AAAAAAAA", timeout=TIMEOUT_S)
    if r.status_code != 404:
        return False, "expected 404 for fake code, got {}".format(r.status_code)
    return True, "404 for fake tracking code"


def check_booking_rejects_out_of_area():
    """Confirm the geofence still blocks bookings clearly outside the service area."""
    nonce = uuid.uuid4().hex[:8]
    body = {
        "address": "Mystery Shop test address — Times Square, NYC " + nonce,
        "lat": COORD_OUT_OF_AREA[0],
        "lng": COORD_OUT_OF_AREA[1],
        "items": [{"category": "general", "quantity": 1}],
        "estimated_price": 79.0,
        "scheduled_date": (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d"),
        "scheduled_time": "10:00",
        "email": "mystery-shop+{}@goumuve.com".format(nonce),
        "name": "Mystery Shopper",
        "phone": "+15555550100",
    }
    r = requests.post(BACKEND_URL + "/api/booking", json=body, timeout=TIMEOUT_S)
    # Expected: 400 with the "outside our service area" message
    if r.status_code != 400:
        return False, "expected 400 for NYC booking, got {}".format(r.status_code)
    err = (r.json() or {}).get("error", "")
    if "service area" not in err.lower():
        return False, "400 but unexpected error message: {!r}".format(err[:80])
    return True, "geofence still rejects NYC bookings (good)"


CHECKS = [
    ("Static service-area API", check_static_service_area),
    ("Dynamic service-area API (Tier 3-G)", check_dynamic_service_area),
    ("Service-area check: in-area (WPB)", check_service_area_in),
    ("Service-area check: out-of-area (NYC)", check_service_area_out),
    ("Tracking 404 path", check_tracking_404),
    ("Booking rejects out-of-area (geofence still gating)", check_booking_rejects_out_of_area),
]
# TODO: add a synthetic Vapi mystery-call once we have a test phone number to
# call FROM and a way to assert the call connected + Maya responded. Needs
# either a real test caller or a SIP test harness.


def alert_admin(failures: List[Tuple[str, str]]):
    admin_phone = os.environ.get("ADMIN_PHONE", "")
    admin_email = os.environ.get("ADMIN_EMAIL", "")

    if not admin_phone and not admin_email:
        logger.error(
            "Mystery shop failed %d checks but NO ADMIN_PHONE/ADMIN_EMAIL configured.",
            len(failures),
        )
        return

    if admin_phone:
        try:
            from sms_service import send_sms_async
            send_sms_async(admin_phone, (
                "🚨 umuve MYSTERY SHOP: {} of {} checks FAILED. "
                "First failure: {} — {}. Check Render logs."
            ).format(
                len(failures), len(CHECKS),
                failures[0][0], failures[0][1][:80],
            ))
        except Exception:
            logger.exception("Failed to SMS mystery-shop alert")

    if admin_email:
        try:
            from email_service import send_email_async
            rows = "".join(
                "<tr><td>{}</td><td><code>{}</code></td></tr>".format(name, detail)
                for name, detail in failures
            )
            send_email_async(
                admin_email,
                "🚨 umuve — mystery shop FAILED ({} checks)".format(len(failures)),
                (
                    "<h2>Daily mystery shop caught regressions</h2>"
                    "<p>Some part of the customer funnel returned an unexpected "
                    "result. Investigate before real customers hit it.</p>"
                    "<table cellpadding='6' style='font-family:sans-serif;font-size:14px'>"
                    "<thead><tr style='background:#fee'>"
                    "<th align='left'>Check</th><th align='left'>Detail</th>"
                    "</tr></thead><tbody>{rows}</tbody></table>"
                    "<p><b>Backend:</b> {url}</p>"
                ).format(rows=rows, url=BACKEND_URL),
            )
        except Exception:
            logger.exception("Failed to email mystery-shop alert")


def main():
    logger.info("=" * 60)
    logger.info("Mystery shop starting against %s", BACKEND_URL)
    logger.info("=" * 60)

    failures: List[Tuple[str, str]] = []
    for name, fn in CHECKS:
        ok, detail = _check(name, fn)
        if not ok:
            failures.append((name, detail))

    if failures:
        logger.warning("Mystery shop: %d/%d checks failed", len(failures), len(CHECKS))
        alert_admin(failures)
        sys.exit(2)

    logger.info("Mystery shop: all %d checks passed ✨", len(CHECKS))


if __name__ == "__main__":
    main()
