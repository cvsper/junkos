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


def _validate_twilio_signature():
    """Validate the X-Twilio-Signature header on the inbound webhook.

    Fail-safe by design (this is live SMS — a misconfig must not brick it):
      - Only enforced when TWILIO_AUTH_TOKEN is set AND
        SMS_WEBHOOK_VALIDATE (default "on") is not "off". Setting
        SMS_WEBHOOK_VALIDATE=off is the escape hatch if the reconstructed
        URL ever mismatches what Twilio signed in prod.
      - Any unexpected error in the validator itself allows the request
        through (logged) rather than dropping customer texts.

    Returns True when the request may proceed, False to reject with 403.
    """
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    validate_flag = os.environ.get("SMS_WEBHOOK_VALIDATE", "on").strip().lower()

    if not auth_token or validate_flag == "off":
        logger.warning(
            "Twilio signature validation SKIPPED (auth_token_set=%s, "
            "SMS_WEBHOOK_VALIDATE=%s)",
            bool(auth_token), validate_flag,
        )
        return True

    try:
        from twilio.request_validator import RequestValidator

        # Render terminates TLS at its proxy, so Flask sees http:// while
        # Twilio signed the public https:// URL. Honor X-Forwarded-Proto to
        # rebuild the scheme Twilio actually used.
        url = request.url
        forwarded_proto = (
            request.headers.get("X-Forwarded-Proto", "").split(",")[0].strip().lower()
        )
        if forwarded_proto == "https" and url.startswith("http://"):
            url = "https://" + url[len("http://"):]

        signature = request.headers.get("X-Twilio-Signature", "")
        validator = RequestValidator(auth_token)
        return validator.validate(url, request.form, signature)
    except Exception:
        # Never let a validator bug take down inbound SMS — allow and log.
        logger.exception("Twilio signature validation errored; allowing request")
        return True


@sms_webhook_bp.route("/inbound", methods=["POST"])
def inbound_sms():
    """Handle inbound SMS/MMS from Twilio.

    Router: photos → our AI quote engine, text-only → forward to Vapi.
    Twilio sends form-encoded data:
        From, To, Body, NumMedia, MediaUrl0, MediaContentType0, etc.
    """
    if not _validate_twilio_signature():
        logger.warning(
            "Rejected inbound SMS with invalid Twilio signature (remote=%s)",
            request.remote_addr,
        )
        return Response("Forbidden", status=403)

    from_phone = request.form.get("From", "")
    body = request.form.get("Body", "").strip()
    num_media = int(request.form.get("NumMedia", 0))

    logger.info("Inbound SMS from %s: body=%r media=%d", from_phone, body[:100], num_media)

    # --- Hauler self-signup + opt-out (Tier 1-A): runs before everything so a
    # "JOBS" text becomes supply instead of getting auto-quoted, and a "STOP"
    # from a concierge hauler removes them from the offer wave. Consent-clean:
    # the hauler initiated the message. ---
    if num_media == 0 and body:
        try:
            from recruiter import is_signup_keyword, register_concierge
            lower = body.strip().lower()

            if lower.split()[0].strip(".!,") in ("stop", "unsubscribe", "cancel", "quit"):
                _opt_out_concierge(from_phone)
                # Twilio's own STOP handling also fires; this just flips our flag.

            elif is_signup_keyword(body):
                res = register_concierge(from_phone, source="inbound_keyword")
                if res["status"] == "created":
                    return _twiml_response(
                        "You're on Umuve's paid-jobs list! We text you a job "
                        "(pay + address), you reply to grab it, haul it, we pay "
                        "same day. No app needed to start. Reply STOP to opt out."
                    )
                if res["status"] == "exists_concierge":
                    return _twiml_response(
                        "You're already on the list — job offers come by text. "
                        "Reply STOP to opt out."
                    )
                if res["status"] == "exists_app":
                    return _twiml_response(
                        "You're already registered in the Umuve Pro app — open "
                        "it and tap Go Online to get jobs."
                    )
                # invalid/error: fall through to normal handling
        except Exception:
            logger.exception("Hauler signup fast-path failed; falling through")

    # --- Support detection (Tier 1-B): bypass Vapi for customers in trouble ---
    # Check BEFORE the photo/Vapi paths so a "where is my hauler" text doesn't
    # get auto-quoted or lost in the AI line. Photos are still photos — only
    # text-only messages route through the support detector.
    if num_media == 0 and body:
        try:
            from support_router import is_support_request, forward_to_admin
            if is_support_request(body, from_phone):
                forward_to_admin(from_phone, body)
                logger.info(
                    "Support-text fast-path: forwarded inbound from %s to admin",
                    from_phone,
                )
                return _twiml_response(
                    "Got your message — the owner has been notified directly "
                    "and will personally reach out to you shortly. We're sorry "
                    "for the trouble."
                )
        except Exception:
            # Never let support detection break the normal SMS flow
            logger.exception("Support-router check failed; falling through")

    # If there are images, run photo quoting (handled by us)
    if num_media > 0:
        media_urls = []
        for i in range(num_media):
            url = request.form.get("MediaUrl{}".format(i), "")
            content_type = request.form.get("MediaContentType{}".format(i), "")
            if url and content_type.startswith("image/"):
                media_urls.append(url)

        if media_urls:
            # A hauler texting photos right after a job is submitting
            # before/after proof, not asking for a quote — attach the photos
            # to their job and skip the quote engine entirely.
            proof_reply = _attach_operator_proof(from_phone, body, media_urls)
            if proof_reply:
                return _twiml_response(proof_reply)

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

    # No photo — forward to Vapi for conversational SMS handling
    vapi_url = os.environ.get("VAPI_SMS_WEBHOOK", "https://api.vapi.ai/twilio/sms")
    try:
        import requests as http_requests
        vapi_resp = http_requests.post(
            vapi_url,
            data=request.form.to_dict(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        if vapi_resp.status_code == 200 and vapi_resp.text.strip():
            return Response(vapi_resp.text, mimetype="text/xml")
        logger.warning("Vapi SMS forward returned %d", vapi_resp.status_code)
    except Exception:
        logger.exception("Failed to forward SMS to Vapi")

    # Vapi fallback — handle locally if Vapi is down
    lower_body = body.lower()

    if any(w in lower_body for w in ["quote", "price", "how much", "estimate"]):
        return _twiml_response(
            "For an instant quote, text us a photo of what you need removed "
            "and we'll price it out in seconds. Or call (844) 435-6005!"
        )

    if any(w in lower_body for w in ["book", "schedule", "pickup"]):
        frontend_url = os.environ.get("FRONTEND_URL", "https://app.goumuve.com")
        return _twiml_response(
            "Book your pickup here: {}/book?ref=sms "
            "Or call (844) 435-6005 and Maya will get you set up!".format(frontend_url)
        )

    if any(w in lower_body for w in ["stop", "unsubscribe", "cancel"]):
        return _twiml_response("You've been unsubscribed. Reply START to opt back in.")

    # Default response
    return _twiml_response(
        "Thanks for texting Umuve! Text us a PHOTO of your junk for an instant quote, "
        "or call (844) 435-6005. Book online: app.goumuve.com"
    )


# How long after a job's last touch a hauler's texted photos still count as
# proof for it. Beyond this, photos fall through to the quote engine.
PROOF_ATTACH_WINDOW_H = 72


def _attach_operator_proof(phone, body, media_urls):
    """Attach texted photos to the sender's active or just-finished job.

    Returns the confirmation reply to send, or None when the sender isn't a
    hauler with a recent started/completed job (→ photo-quote path).
    Never raises.
    """
    try:
        from datetime import timedelta
        from models import db, Job, User, utcnow
        from recruiter import normalize_phone
        e164 = normalize_phone(phone) or phone
        user = User.query.filter_by(phone=e164).first()
        contractor = user.contractor_profile if user else None
        if not contractor:
            return None
        cutoff = utcnow() - timedelta(hours=PROOF_ATTACH_WINDOW_H)
        job = (Job.query
               .filter(Job.driver_id == contractor.id,
                       Job.status.in_(("started", "completed")),
                       Job.updated_at >= cutoff)
               .order_by(Job.updated_at.desc())
               .first())
        if not job:
            return None

        # "before"/"after" in the text wins; otherwise fill before first.
        lower = (body or "").lower()
        if "before" in lower:
            side = "before"
        elif "after" in lower:
            side = "after"
        else:
            side = "before" if not job.before_photos else "after"

        # JSON columns need reassignment (in-place append isn't tracked).
        setattr(job, side + "_photos",
                list(getattr(job, side + "_photos") or []) + media_urls)
        job.proof_submitted_at = utcnow()
        job.updated_at = utcnow()
        db.session.commit()
        logger.info("Attached %d %s photo(s) to job %s from hauler %s",
                    len(media_urls), side, job.id, contractor.id)

        if side == "before" and not job.after_photos:
            follow = " Text the AFTER shot once the space is clear."
        elif side == "after" and not job.before_photos:
            follow = (" Got a before shot too? Text it with the word "
                      "'before'.")
        else:
            follow = " Full before/after set — that's the good stuff."
        n = len(media_urls)
        return "Attached {} {} photo{} to your job.{}".format(
            n, side, "" if n == 1 else "s", follow)
    except Exception:
        logger.exception("Operator proof attach failed for %s", phone)
        return None


def _opt_out_concierge(phone):
    """Flip a concierge hauler offline on STOP so they stop getting offers.

    Never raises. Only touches concierge accounts — a customer texting STOP
    is handled by Twilio's carrier-level opt-out and the default reply below.
    """
    try:
        from models import db, User, utcnow
        from recruiter import normalize_phone
        e164 = normalize_phone(phone) or phone
        user = User.query.filter_by(phone=e164).first()
        if user and user.contractor_profile and user.contractor_profile.is_concierge:
            c = user.contractor_profile
            c.is_online = False
            c.updated_at = utcnow()
            db.session.commit()
            logger.info("Concierge %s opted out (STOP) — offline", c.id)
    except Exception:
        logger.exception("Concierge opt-out failed for %s", phone)


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
                    "Call (844) 435-6005 for an instant quote!"
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
                        "I had trouble loading your photo. Try sending it again, "
                        "or call (844) 435-6005 for a quick quote!"
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
                    "Try a clearer shot or call (844) 435-6005!"
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
                "Or call (844) 435-6005\n"
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
                "call (844) 435-6005 for a quick quote!"
            )
        except Exception:
            logger.exception("Photo quote processing failed for %s", phone)
            try:
                from sms_service import send_sms_async
                send_sms_async(phone,
                    "Something went wrong processing your photo. "
                    "Call (844) 435-6005 — we'll get you a quote!"
                )
            except Exception:
                pass
