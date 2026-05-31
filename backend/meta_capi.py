"""
Meta Conversions API (server-side pixel).

The browser pixel alone loses 20-40% of conversion events to iOS/Safari ITP,
ad-blockers, and lost sessions — which starves Meta's optimizer right when
you're paying it to find buyers. This sends the money events (Purchase, Lead)
straight from the backend, deduplicated against the browser pixel via a shared
event_id, so Meta sees every conversion with clean attribution.

Activation is purely env-driven and fail-safe:
  META_PIXEL_ID            – the pixel/dataset id (same one the browser uses)
  META_CAPI_ACCESS_TOKEN   – System User token from Business Manager (Events Mgr
                             -> Settings -> Conversions API -> Generate token)
If either is unset, every function is a silent no-op — nothing breaks, no spend
implication. Nothing here ever raises into a caller (webhook/booking) path.
"""

import os
import time
import json
import hashlib
import logging

import requests

logger = logging.getLogger(__name__)

GRAPH_VERSION = "v19.0"

META_PIXEL_ID = os.environ.get("META_PIXEL_ID", "") or os.environ.get(
    "NEXT_PUBLIC_META_PIXEL_ID", ""
)
META_CAPI_ACCESS_TOKEN = os.environ.get("META_CAPI_ACCESS_TOKEN", "")
# Optional: a test event code from Events Manager to verify in the "Test
# Events" tab without polluting live data. Leave unset in production.
META_TEST_EVENT_CODE = os.environ.get("META_TEST_EVENT_CODE", "")


def _enabled():
    return bool(META_PIXEL_ID and META_CAPI_ACCESS_TOKEN)


def _hash(value):
    """SHA-256 a normalized PII string per Meta's spec. None -> None."""
    if not value:
        return None
    norm = str(value).strip().lower()
    if not norm:
        return None
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def _hash_phone(phone):
    """Phone must be digits-only (with country code) before hashing."""
    if not phone:
        return None
    digits = "".join(ch for ch in str(phone) if ch.isdigit())
    if not digits:
        return None
    return hashlib.sha256(digits.encode("utf-8")).hexdigest()


def _build_user_data(email=None, phone=None, client_ip=None, user_agent=None,
                     fbp=None, fbc=None):
    ud = {}
    em = _hash(email)
    ph = _hash_phone(phone)
    if em:
        ud["em"] = [em]
    if ph:
        ud["ph"] = [ph]
    # These are NOT hashed (Meta uses them raw for match quality).
    if client_ip:
        ud["client_ip_address"] = client_ip
    if user_agent:
        ud["client_user_agent"] = user_agent
    if fbp:
        ud["fbp"] = fbp          # _fbp cookie — big match-quality boost
    if fbc:
        ud["fbc"] = fbc          # _fbc cookie (from fbclid)
    return ud


def send_event(event_name, event_id, user_data, custom_data=None,
               event_source_url=None):
    """Post one event to the Conversions API. Returns True on 200, else False.
    Never raises.
    """
    if not _enabled():
        logger.debug("Meta CAPI disabled (no pixel id / token) — skipping %s", event_name)
        return False

    payload_event = {
        "event_name": event_name,
        "event_time": int(time.time()),
        "event_id": event_id,            # <-- dedup key, must match browser pixel
        "action_source": "website",
        "user_data": user_data or {},
    }
    if custom_data:
        payload_event["custom_data"] = custom_data
    if event_source_url:
        payload_event["event_source_url"] = event_source_url

    body = {"data": [payload_event]}
    if META_TEST_EVENT_CODE:
        body["test_event_code"] = META_TEST_EVENT_CODE

    url = "https://graph.facebook.com/{}/{}/events".format(GRAPH_VERSION, META_PIXEL_ID)
    try:
        resp = requests.post(
            url,
            params={"access_token": META_CAPI_ACCESS_TOKEN},
            json=body,
            timeout=10,
        )
        if resp.status_code == 200:
            logger.info("Meta CAPI %s sent (event_id=%s)", event_name, event_id)
            return True
        logger.warning(
            "Meta CAPI %s failed: HTTP %s %s",
            event_name, resp.status_code, resp.text[:300],
        )
        return False
    except Exception:
        logger.exception("Meta CAPI %s request errored", event_name)
        return False


def track_purchase(job_id, value, currency="USD", email=None, phone=None,
                   client_ip=None, user_agent=None, fbp=None, fbc=None,
                   event_source_url=None):
    """Server-side Purchase. event_id = 'purchase_<job_id>' so it dedupes with
    the browser pixel (which fires the same id). Never raises.
    """
    try:
        return send_event(
            "Purchase",
            "purchase_{}".format(job_id),
            _build_user_data(email, phone, client_ip, user_agent, fbp, fbc),
            custom_data={
                "currency": currency,
                "value": round(float(value or 0), 2),
                "content_ids": [str(job_id)],
                "content_type": "product",
            },
            event_source_url=event_source_url,
        )
    except Exception:
        logger.exception("track_purchase failed for job %s", job_id)
        return False


def track_lead(lead_id, email=None, phone=None, value=None, currency="USD",
               client_ip=None, user_agent=None, fbp=None, fbc=None,
               event_source_url=None):
    """Server-side Lead. event_id = 'lead_<lead_id>'. Never raises."""
    try:
        custom = {}
        if value is not None:
            custom = {"currency": currency, "value": round(float(value), 2)}
        return send_event(
            "Lead",
            "lead_{}".format(lead_id),
            _build_user_data(email, phone, client_ip, user_agent, fbp, fbc),
            custom_data=custom or None,
            event_source_url=event_source_url,
        )
    except Exception:
        logger.exception("track_lead failed for lead %s", lead_id)
        return False


def status():
    """Lightweight config readout for health/morning-brief surfacing."""
    return {
        "enabled": _enabled(),
        "has_pixel_id": bool(META_PIXEL_ID),
        "has_access_token": bool(META_CAPI_ACCESS_TOKEN),
        "test_mode": bool(META_TEST_EVENT_CODE),
    }
