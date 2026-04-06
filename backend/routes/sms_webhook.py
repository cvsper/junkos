"""
Twilio Inbound SMS/MMS Webhook — Photo Quoting Engine.

When a customer texts a photo of their junk to the Umuve phone number,
this endpoint receives the MMS, sends the image to Claude Haiku for item
identification, calculates a quote using the pricing engine, and texts
the estimate + booking link back.

Configure in Twilio console:
    Messaging > Phone Number > Webhook URL:
    POST https://junkos-backend.onrender.com/api/sms/inbound
"""

import os
import json
import base64
import logging
import threading
from datetime import datetime, timezone

from flask import Blueprint, request, Response

logger = logging.getLogger(__name__)

sms_webhook_bp = Blueprint("sms_webhook", __name__, url_prefix="/api/sms")


@sms_webhook_bp.route("/inbound", methods=["POST"])
def inbound_sms():
    """Handle inbound SMS/MMS from Twilio.

    Twilio sends form-encoded data:
        From, To, Body, NumMedia, MediaUrl0, MediaContentType0, etc.
    """
    from_phone = request.form.get("From", "")
    body = request.form.get("Body", "").strip()
    num_media = int(request.form.get("NumMedia", 0))

    logger.info("Inbound SMS from %s: body=%r media=%d", from_phone, body[:100], num_media)

    # If there are images, run photo quoting
    if num_media > 0:
        media_urls = []
        for i in range(num_media):
            url = request.form.get("MediaUrl{}".format(i), "")
            content_type = request.form.get("MediaContentType{}".format(i), "")
            if url and content_type.startswith("image/"):
                media_urls.append(url)

        if media_urls:
            # Process in background so Twilio gets a fast response
            from flask import current_app
            app = current_app._get_current_object()
            t = threading.Thread(
                target=_process_photo_quote,
                args=(app, from_phone, body, media_urls),
                daemon=True,
            )
            t.start()

            # Immediate acknowledgment via TwiML
            return _twiml_response(
                "Got your photo! Analyzing it now — "
                "you'll get a quote in about 30 seconds."
            )

    # Text-only message — check if it's a keyword
    lower_body = body.lower()

    if any(w in lower_body for w in ["quote", "price", "how much", "estimate"]):
        return _twiml_response(
            "Hey! For an instant quote, text us a photo of what you need removed "
            "and we'll price it out in seconds. Or call us at (561) 944-1636!"
        )

    if any(w in lower_body for w in ["book", "schedule", "pickup"]):
        frontend_url = os.environ.get("FRONTEND_URL", "https://app.goumuve.com")
        return _twiml_response(
            "Book your pickup here: {}/book?ref=sms "
            "Or call us at (561) 944-1636 and Maya will get you set up!".format(frontend_url)
        )

    if any(w in lower_body for w in ["stop", "unsubscribe", "cancel"]):
        return _twiml_response("You've been unsubscribed. Reply START to opt back in.")

    # Default response
    return _twiml_response(
        "Thanks for texting Umuve! Text us a PHOTO of your junk for an instant quote, "
        "or call (561) 944-1636. Book online: app.goumuve.com"
    )


def _twiml_response(message):
    """Return a TwiML XML response."""
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response><Message>{}</Message></Response>"
    ).format(message)
    return Response(twiml, mimetype="text/xml")


def _process_photo_quote(app, phone, body_text, media_urls):
    """Background: send photos to Claude Haiku vision, identify items, calculate quote, text back."""
    with app.app_context():
        try:
            import requests as http_requests
            from sms_service import send_sms_async
            from routes.booking import calculate_estimate

            anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
            openai_key = os.environ.get("OPENAI_API_KEY", "")

            if not anthropic_key and not openai_key:
                logger.warning("No ANTHROPIC_API_KEY or OPENAI_API_KEY — cannot process photo quote")
                send_sms_async(phone,
                    "Sorry, our photo quoting is temporarily unavailable. "
                    "Call us at (844) 435-6005 for an instant quote!"
                )
                return

            prompt_text = (
                "You are a junk removal pricing assistant for Umuve. "
                "Look at the photo(s) and identify every item that needs removal. "
                "For each item, pick the closest category from this list:\n"
                "sofa, sectional, recliner, mattress, box_spring, bed_frame, "
                "refrigerator, washer, dryer, dining_table, coffee_table, desk, "
                "tv, treadmill, elliptical, hot_tub, pool_table, piano, "
                "yard_waste, general\n\n"
                "Return ONLY a JSON array of objects: "
                '[{"category": "sofa", "quantity": 1, "description": "brown leather sofa"}]\n'
                "If you can't identify items clearly, make your best guess. "
                "Include a quantity for each. No markdown fencing."
            )

            if body_text:
                prompt_text += "\n\nThe customer also wrote: \"{}\"".format(body_text[:200])

            use_anthropic = bool(anthropic_key)

            if use_anthropic:
                # Fetch images as base64 (Twilio media URLs require auth)
                twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
                twilio_token = os.environ.get("TWILIO_AUTH_TOKEN", "")

                image_content = []
                for url in media_urls[:3]:
                    try:
                        img_resp = http_requests.get(url, auth=(twilio_sid, twilio_token), timeout=15)
                        if img_resp.status_code == 200:
                            img_b64 = base64.standard_b64encode(img_resp.content).decode("utf-8")
                            media_type = img_resp.headers.get("Content-Type", "image/jpeg")
                            image_content.append({
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": img_b64,
                                },
                            })
                        else:
                            logger.warning("Failed to fetch Twilio media %s: %d", url, img_resp.status_code)
                    except Exception:
                        logger.exception("Error fetching Twilio media URL: %s", url)

                if not image_content:
                    logger.error("Could not fetch any images from Twilio")
                    send_sms_async(phone,
                        "I had trouble loading your photo. Try sending it again or "
                        "call (844) 435-6005 for a quick quote!"
                    )
                    return

                messages_payload = [{
                    "role": "user",
                    "content": [
                        *image_content,
                        {"type": "text", "text": prompt_text},
                    ],
                }]

                resp = http_requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": anthropic_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "claude-haiku-4-5-20251001",
                        "messages": messages_payload,
                        "temperature": 0.2,
                        "max_tokens": 500,
                    },
                    timeout=45,
                )

                if resp.status_code != 200:
                    logger.error("Anthropic vision error: %d %s", resp.status_code, resp.text[:200])
                    # Fall back to OpenAI if available
                    if openai_key:
                        logger.info("Falling back to OpenAI after Anthropic error")
                        use_anthropic = False
                    else:
                        send_sms_async(phone,
                            "Hmm, I had trouble analyzing your photo. "
                            "Call us at (844) 435-6005 and Maya can help!"
                        )
                        return

                if use_anthropic:
                    content = resp.json()["content"][0]["text"].strip()

            if not use_anthropic:
                # OpenAI fallback path
                image_content_oai = []
                for url in media_urls[:3]:
                    image_content_oai.append({
                        "type": "image_url",
                        "image_url": {"url": url, "detail": "low"},
                    })

                messages_payload = [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        *image_content_oai,
                    ],
                }]

                resp = http_requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": "Bearer {}".format(openai_key),
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-4o",
                        "messages": messages_payload,
                        "temperature": 0.2,
                        "max_tokens": 500,
                    },
                    timeout=45,
                )

                if resp.status_code != 200:
                    logger.error("OpenAI vision error: %d %s", resp.status_code, resp.text[:200])
                    send_sms_async(phone,
                        "Hmm, I had trouble analyzing your photo. "
                        "Call us at (844) 435-6005 and Maya can help!"
                    )
                    return

                content = resp.json()["choices"][0]["message"]["content"].strip()

            # Strip markdown fencing
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

            items = json.loads(content)

            if not items or not isinstance(items, list):
                send_sms_async(phone,
                    "I couldn't identify any items in the photo. "
                    "Try a clearer shot or call (561) 944-1636!"
                )
                return

            # Calculate quote using existing pricing engine
            estimate_items = [
                {"category": item.get("category", "general"), "quantity": item.get("quantity", 1)}
                for item in items
            ]
            est = calculate_estimate(estimate_items)
            total = est.get("total", 0)

            # Build response
            item_lines = []
            for item in items:
                desc = item.get("description", item.get("category", "item"))
                qty = item.get("quantity", 1)
                item_lines.append("  {} x{}".format(desc, qty))

            items_text = "\n".join(item_lines[:8])  # Cap at 8 lines

            frontend_url = os.environ.get("FRONTEND_URL", "https://app.goumuve.com")

            quote_msg = (
                "PHOTO QUOTE from Umuve:\n\n"
                "I see:\n{}\n\n"
                "Estimated total: ${:.0f}\n"
                "(includes 8% service fee{})\n\n"
                "Book now: {}/book?ref=photo\n"
                "Or call (561) 944-1636\n"
                "Quote valid for 48 hours!"
            ).format(
                items_text,
                total,
                ", volume discount applied" if est.get("volume_discount", 0) > 0 else "",
                frontend_url,
            )

            send_sms_async(phone, quote_msg)
            logger.info("Photo quote sent to %s: %d items, $%.0f", phone, len(items), total)

            # Update caller profile with items
            try:
                from models import db, CallerProfile, generate_uuid
                profile = CallerProfile.query.filter_by(phone=phone).first()
                if not profile:
                    profile = CallerProfile(
                        id=generate_uuid(),
                        phone=phone,
                        first_call_at=datetime.now(timezone.utc),
                    )
                    db.session.add(profile)

                existing_items = profile.past_items or []
                for item in items:
                    cat = item.get("category", "")
                    if cat and cat not in existing_items:
                        existing_items.append(cat)
                profile.past_items = existing_items[-20:]

                tags = profile.tags or []
                if "photo_quote" not in tags:
                    tags.append("photo_quote")
                profile.tags = tags
                profile.last_call_at = datetime.now(timezone.utc)

                db.session.commit()
            except Exception:
                logger.exception("Failed to update caller profile for photo quote")

            # Notify operator
            try:
                operator_phone = os.environ.get("OPERATOR_PHONE", "")
                if operator_phone:
                    notify = (
                        "PHOTO QUOTE sent!\n"
                        "From: {}\n"
                        "Items: {}\n"
                        "Total: ${:.0f}"
                    ).format(phone, ", ".join(i.get("category", "?") for i in items[:5]), total)
                    send_sms_async(operator_phone, notify)
            except Exception:
                logger.exception("Failed to notify operator about photo quote")

        except json.JSONDecodeError:
            logger.exception("Failed to parse vision response as JSON")
            from sms_service import send_sms_async
            send_sms_async(phone,
                "I had trouble with that photo. Try another angle or "
                "call (561) 944-1636 for a quick quote!"
            )
        except Exception:
            logger.exception("Photo quote processing failed for %s", phone)
            try:
                from sms_service import send_sms_async
                send_sms_async(phone,
                    "Something went wrong processing your photo. "
                    "Call us at (561) 944-1636 — we'll get you a quote!"
                )
            except Exception:
                pass
