"""Google Places text search shared by the outreach engines.

Tries Places API (New) first — the only API enabled on keys created since
mid-2024, and it returns website + phone inline so no Details round-trip.
Falls back to the legacy Text Search endpoint for older keys. Either way,
a failing endpoint's status lands in the caller's diag dict instead of
silently sourcing zero leads.
"""
import logging

import requests

logger = logging.getLogger(__name__)

_NEW_FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,"
    "places.websiteUri,places.nationalPhoneNumber"
)


def text_search(api_key, query, diag=None):
    """Return normalized place dicts for a text query.

    Each dict: {place_id, name, address, website, phone}. Legacy results
    set website/phone to None and "_needs_details": True — the caller
    decides whether to spend a Details call on them.
    """
    try:
        r = requests.post(
            "https://places.googleapis.com/v1/places:searchText",
            headers={
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": _NEW_FIELD_MASK,
                "Content-Type": "application/json",
            },
            json={"textQuery": query, "pageSize": 20},
            timeout=15,
        )
        if r.status_code == 200:
            places = (r.json() or {}).get("places", [])
            return [
                {
                    "place_id": p.get("id"),
                    "name": (p.get("displayName") or {}).get("text"),
                    "address": p.get("formattedAddress") or "",
                    "website": p.get("websiteUri"),
                    "phone": p.get("nationalPhoneNumber"),
                }
                for p in places
            ]
        try:
            err = (r.json() or {}).get("error", {})
        except ValueError:
            err = {}
        if diag is not None:
            diag["new_api_status"] = err.get("status") or "HTTP {}".format(r.status_code)
            diag["new_api_error"] = (err.get("message") or "")[:200]
        logger.warning(
            "Places (New) %s for '%s': %s", r.status_code, query, err.get("message")
        )
    except Exception:
        logger.warning("Places (New) request failed for '%s'", query)

    try:
        r = requests.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            params={"query": query, "key": api_key},
            timeout=15,
        )
        data = r.json() or {}
        status = data.get("status")
        if status not in ("OK", "ZERO_RESULTS"):
            if diag is not None:
                diag["status"] = status
                diag["error"] = data.get("error_message")
            logger.error(
                "Places legacy %s for '%s': %s", status, query, data.get("error_message")
            )
            return []
        return [
            {
                "place_id": res.get("place_id"),
                "name": res.get("name"),
                "address": res.get("formatted_address") or "",
                "website": None,
                "phone": None,
                "_needs_details": True,
            }
            for res in data.get("results", [])
        ]
    except Exception:
        logger.warning("Places legacy request failed for '%s'", query)
        return []
