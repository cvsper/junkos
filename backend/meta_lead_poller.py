"""
Meta Lead Ads Poller — fetches new leads every 2 minutes, triggers Maya calls.

Alternative to webhook (Option C) — works without Meta app verification.
Polls the Meta Graph API for new leads from all lead gen forms on the page.

Usage:
    python meta_lead_poller.py              # Run once
    python meta_lead_poller.py --daemon     # Poll every 2 minutes

Env vars required:
    META_ACCESS_TOKEN   — Long-lived page access token
    META_PAGE_ID        — Facebook page ID
    VAPI_API_KEY        — Vapi API key for outbound calls

Optional:
    POLL_INTERVAL       — Seconds between polls (default: 120)
    BACKEND_URL         — Backend URL (default: https://junkos-backend.onrender.com)
"""

import os
import sys
import json
import time
import logging
import requests
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
META_PAGE_ID = os.environ.get("META_PAGE_ID", "")
VAPI_API_KEY = os.environ.get("VAPI_API_KEY", "")
VAPI_ASSISTANT_ID = "91198234-25c8-450a-9075-854509e9e59d"
VAPI_PHONE_NUMBER_ID = "8efe5578-e752-4154-98d0-b1dc3eba3938"
BACKEND_URL = os.environ.get("BACKEND_URL", "https://junkos-backend.onrender.com")
OPERATOR_PHONE = os.environ.get("OPERATOR_PHONE", "+15618883427")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "120"))

# Track processed leads to avoid duplicates
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".meta_lead_state.json")


def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"processed_leads": [], "last_poll": None}


def save_state(state):
    # Keep only last 500 lead IDs to prevent unbounded growth
    state["processed_leads"] = state["processed_leads"][-500:]
    state["last_poll"] = datetime.now(timezone.utc).isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def get_lead_forms():
    """Get all lead gen form IDs for the page."""
    resp = requests.get(
        "https://graph.facebook.com/v19.0/{}/leadgen_forms".format(META_PAGE_ID),
        params={"access_token": META_ACCESS_TOKEN, "limit": 25},
        timeout=15,
    )
    if resp.status_code != 200:
        logger.error("Failed to fetch lead forms: %d %s", resp.status_code, resp.text[:200])
        return []
    return resp.json().get("data", [])


def get_leads_for_form(form_id, limit=25):
    """Get recent leads for a specific form."""
    resp = requests.get(
        "https://graph.facebook.com/v19.0/{}/leads".format(form_id),
        params={"access_token": META_ACCESS_TOKEN, "limit": limit},
        timeout=15,
    )
    if resp.status_code != 200:
        logger.error("Failed to fetch leads for form %s: %d %s",
                     form_id, resp.status_code, resp.text[:200])
        return []
    return resp.json().get("data", [])


def extract_lead_fields(lead):
    """Extract name, phone, email, items from lead field_data."""
    fields = lead.get("field_data", [])
    result = {"name": "", "phone": "", "email": "", "items": "", "address": ""}

    for field in fields:
        fname = field.get("name", "").lower()
        values = field.get("values", [])
        val = values[0] if values else ""

        if "full_name" in fname or (fname == "name"):
            result["name"] = val
        elif "first" in fname and "name" in fname:
            result["name"] = val
        elif "phone" in fname or "number" in fname:
            result["phone"] = val
        elif "email" in fname:
            result["email"] = val
        elif any(k in fname for k in ["item", "junk", "remove", "what", "describe"]):
            result["items"] = val
        elif any(k in fname for k in ["address", "city", "zip", "location"]):
            result["address"] = val

    return result


def format_phone(phone):
    """Ensure US phone has +1 prefix."""
    import re
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        return "+1{}".format(digits)
    elif len(digits) == 11 and digits.startswith("1"):
        return "+{}".format(digits)
    elif phone.startswith("+"):
        return phone
    return "+{}".format(digits)


def call_lead(name, phone, items):
    """Place outbound Vapi call to the lead."""
    first_name = name.split()[0] if name else "there"

    if items:
        first_message = (
            "Hey {}! This is Maya from Umuve — you just filled out a form "
            "about getting some junk removed. Looks like you need help with {}. "
            "I can get you a quote right now — sound good?"
        ).format(first_name, items)
    else:
        first_message = (
            "Hey {}! This is Maya from Umuve, South Florida's junk removal service. "
            "You just reached out about getting some stuff picked up — "
            "I'd love to help! What do you need removed?"
        ).format(first_name)

    voicemail_msg = (
        "Hey {}, this is Maya from Umuve junk removal. "
        "We got your request and I wanted to give you a quick call. "
        "Call us back anytime at 561-944-1636 or book online "
        "at app.goumuve.com. Talk soon!"
    ).format(first_name)

    payload = {
        "assistantId": VAPI_ASSISTANT_ID,
        "phoneNumberId": VAPI_PHONE_NUMBER_ID,
        "customer": {"number": phone, "name": name or "Customer"},
        "assistantOverrides": {
            "firstMessage": first_message,
            "voicemailDetectionEnabled": True,
            "voicemailMessage": voicemail_msg,
        },
    }

    resp = requests.post(
        "https://api.vapi.ai/call/phone",
        headers={
            "Authorization": "Bearer {}".format(VAPI_API_KEY),
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )

    if resp.status_code in (200, 201):
        call_id = resp.json().get("id", "")
        logger.info("Call initiated: call_id=%s phone=%s name=%s", call_id, phone, name)
        return True
    else:
        logger.error("Call failed for %s: %d %s", phone, resp.status_code, resp.text[:200])
        return False


def send_sms_fallback(phone, name, items):
    """Send SMS if call fails."""
    first_name = name.split()[0] if name else "there"
    msg = (
        "Hey {}! Thanks for reaching out to Umuve. "
        "Book your junk removal: https://app.goumuve.com/book?ref=meta "
        "Or call us: (561) 944-1636"
    ).format(first_name)

    # Use backend SMS endpoint or Twilio directly
    try:
        from sms_service import send_sms
        send_sms(phone, msg)
    except ImportError:
        logger.warning("sms_service not available for fallback SMS to %s", phone)


def notify_operator(name, phone, items):
    """Notify operator about new Meta lead."""
    try:
        from sms_service import send_sms
        msg = (
            "META LEAD!\n"
            "Name: {}\n"
            "Phone: {}\n"
            "Items: {}\n"
            "Maya is calling them now."
        ).format(name or "Unknown", phone, items or "Not specified")
        send_sms(OPERATOR_PHONE, msg)
    except ImportError:
        logger.info("Operator notification (no sms_service): %s %s", name, phone)


def poll_once():
    """Poll Meta for new leads and process them."""
    if not META_ACCESS_TOKEN or not META_PAGE_ID:
        logger.error("META_ACCESS_TOKEN and META_PAGE_ID are required")
        return 0

    if not VAPI_API_KEY:
        logger.error("VAPI_API_KEY is required")
        return 0

    state = load_state()
    processed = set(state.get("processed_leads", []))
    new_count = 0

    forms = get_lead_forms()
    logger.info("Found %d lead gen forms", len(forms))

    for form in forms:
        form_id = form.get("id", "")
        form_name = form.get("name", "unnamed")
        leads = get_leads_for_form(form_id)

        for lead in leads:
            lead_id = lead.get("id", "")
            if not lead_id or lead_id in processed:
                continue

            fields = extract_lead_fields(lead)
            phone = format_phone(fields["phone"])

            if not phone:
                logger.warning("Lead %s has no phone — skipping", lead_id)
                processed.add(lead_id)
                continue

            logger.info("New lead: id=%s name=%s phone=%s items=%s form=%s",
                        lead_id, fields["name"], phone, fields["items"], form_name)

            # Call the lead
            success = call_lead(fields["name"], phone, fields["items"])

            if not success:
                send_sms_fallback(phone, fields["name"], fields["items"])

            notify_operator(fields["name"], phone, fields["items"])

            processed.add(lead_id)
            new_count += 1

            # Small delay between calls to avoid overwhelming Vapi
            time.sleep(5)

    state["processed_leads"] = list(processed)
    save_state(state)

    if new_count:
        logger.info("Processed %d new leads", new_count)
    else:
        logger.debug("No new leads")

    return new_count


def run_daemon():
    """Poll continuously every POLL_INTERVAL seconds."""
    logger.info("Meta lead poller daemon started (interval=%ds)", POLL_INTERVAL)
    while True:
        try:
            poll_once()
        except Exception:
            logger.exception("Poll cycle failed")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    if "--daemon" in sys.argv:
        run_daemon()
    else:
        count = poll_once()
        print("Processed {} new leads".format(count))
