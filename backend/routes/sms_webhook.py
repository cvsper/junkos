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
import re
import json
import base64
import logging
import threading
from datetime import datetime, timezone

from flask import Blueprint, request, Response

# Module-level so the provider_events table is registered before
# db.create_all() runs (webhook_guard imports models_webhooks).
import webhook_guard  # noqa: F401

logger = logging.getLogger(__name__)

sms_webhook_bp = Blueprint("sms_webhook", __name__, url_prefix="/api/sms")


def _validate_twilio_signature():
    """Validate the X-Twilio-Signature header on the inbound webhook.

    Policy (audit F23, shared with desk_line.py which reuses this helper):
      - Production (``app_config.is_production()``): a missing
        TWILIO_AUTH_TOKEN REJECTS every request (403, logged once), and an
        exception inside the validator also rejects. ``SMS_WEBHOOK_VALIDATE=off``
        is NOT honoured in production — a URL-reconstruction mismatch is an
        incident to fix, not a reason to accept unsigned texts.
      - Development / tests: the historical fail-safe stays — no token or
        ``SMS_WEBHOOK_VALIDATE=off`` skips validation, and a validator error
        allows the request through (logged).

    Returns True when the request may proceed, False to reject with 403.
    """
    from webhook_guard import (
        allow_when_secret_missing, allow_on_validator_error, is_production,
    )

    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    validate_flag = os.environ.get("SMS_WEBHOOK_VALIDATE", "on").strip().lower()

    if not auth_token:
        return allow_when_secret_missing(
            "twilio", "Inbound SMS/MMS and the desk line cannot be verified.",
        )
    if validate_flag == "off":
        if is_production():
            logger.warning(
                "SMS_WEBHOOK_VALIDATE=off is ignored in production — "
                "Twilio signatures are still enforced"
            )
        else:
            logger.warning("Twilio signature validation SKIPPED (SMS_WEBHOOK_VALIDATE=off)")
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
        return bool(validator.validate(url, request.form, signature))
    except Exception as exc:
        return allow_on_validator_error("twilio", exc)


_MD_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__", re.S)
_MD_ITALIC = re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])|(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", re.S)
_MD_HEADER = re.compile(r"^\s{0,3}#{1,6}\s+", re.M)
_MD_BULLET = re.compile(r"^\s*[-*•]\s+", re.M)


def _plain_sms(twiml):
    """Maya's LLM answers texts in markdown (**$119**, - bullets, ## headers);
    phones show the asterisks literally. Flatten every <Message> body to
    plain text and leave the surrounding TwiML alone."""
    def flatten(m):
        body = m.group(2)
        body = _MD_BOLD.sub(lambda x: x.group(1) or x.group(2), body)
        body = _MD_ITALIC.sub(lambda x: x.group(1) or x.group(2), body)
        body = _MD_HEADER.sub("", body)
        body = _MD_BULLET.sub("- ", body)
        return m.group(1) + body + m.group(3)
    return re.sub(r"(<Message[^>]*>)(.*?)(</Message>)", flatten, twiml, flags=re.S)


def _empty_twiml():
    return Response(
        '<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        mimetype="text/xml",
    )


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

    # Twilio retries on timeout/5xx; MessageSid is stable across retries.
    # Persisting it makes a redelivered text a no-op instead of a second
    # quote / second signup / duplicate desk thread. 200 so Twilio stops.
    _sid = request.form.get("MessageSid", "")
    if _sid:
        from webhook_guard import record_provider_event
        if not record_provider_event("twilio", _sid, event_type="inbound_sms"):
            logger.info("Duplicate Twilio MessageSid %s ignored", _sid)
            return _empty_twiml()

    from_phone = request.form.get("From", "")
    body = request.form.get("Body", "").strip()
    num_media = int(request.form.get("NumMedia", 0))

    logger.info("Inbound SMS from %s: body=%r media=%d", from_phone, body[:100], num_media)

    # Call Desk thread: if this sender is a known prospect (Tracy's B2B list),
    # mirror the text into the desk inbox. Observe-only — routing below is
    # unchanged, and customer texts never match a prospect.
    _p = None
    try:
        from desk_line import match_prospect, record_inbound_text, _digits as _dl_digits
        _p = match_prospect(_dl_digits(from_phone))
        if _p is not None:
            _urls = [request.form.get("MediaUrl{}".format(i), "") for i in range(num_media)]
            record_inbound_text(from_phone, body, [u for u in _urls if u],
                                sid=request.form.get("MessageSid"), prospect=_p)
    except Exception:
        logger.exception("desk-thread mirror failed; continuing")

    # --- Loop guard (9/11 incident: Maya's bot traded ~1,100 texts with
    # apartment-office auto-responders). Auto-responder text gets silence, and
    # a known desk prospect is Tracy's conversation — the text is already in
    # the desk thread above; the bot never answers it. STOP from a prospect is
    # registered by record_inbound_text and Twilio's own opt-out handling. ---
    from sms_guard import looks_automated, reply_allowed, note_reply
    if num_media == 0 and looks_automated(body):
        logger.info("Inbound SMS from ...%s looks automated — no reply: %r", from_phone[-4:], body[:80])
        return _empty_twiml()
    if _p is not None and num_media == 0:
        logger.info("Inbound SMS from prospect ...%s left to the desk — no bot reply", from_phone[-4:])
        return _empty_twiml()

    # --- Hauler self-signup + opt-out (Tier 1-A): runs before everything so a
    # "JOBS" text becomes supply instead of getting auto-quoted, and a "STOP"
    # from a concierge hauler removes them from the offer wave. Consent-clean:
    # the hauler initiated the message. ---
    # --- Same-day standby answers (Y / N from a known hauler) ---
    if num_media == 0 and body:
        try:
            from sameday import record_standby_reply
            _standby_reply = record_standby_reply(from_phone, body, via="sms")
            if _standby_reply:
                return _twiml_response(_standby_reply)
        except Exception:
            logger.exception("standby reply check failed; falling through")

    if num_media == 0 and body:
        try:
            from recruiter import is_signup_keyword, register_concierge
            lower = body.strip().lower()

            if lower.split()[0].strip(".!,") in ("stop", "unsubscribe", "cancel", "quit"):
                _opt_out_concierge(from_phone)
                try:
                    from leads import stop_followups
                    stop_followups(from_phone, "stop")
                except Exception:
                    logger.exception("quote follow-up stop failed")
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

    # --- An answer to an open photo quote (stairs / anything not pictured) is
    # ours: it re-prices and re-sends the firm number. Before the support
    # detector and Vapi, or Maya answers a question we asked. ---
    if num_media == 0 and body:
        try:
            from photo_quote import handle_reply
            if handle_reply(from_phone, body) is not None:
                logger.info("photo-quote reply handled for %s", from_phone[-4:])
                return _empty_twiml()
        except Exception:
            logger.exception("photo-quote reply handling failed")

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

    # No photo — forward to Vapi for conversational SMS handling.
    # Rate-capped per sender and overall so an unrecognised loop dies fast.
    _sender_digits = "".join(ch for ch in from_phone if ch.isdigit())[-10:]
    if not reply_allowed(_sender_digits):
        return _empty_twiml()
    note_reply(_sender_digits)
    vapi_url = os.environ.get("VAPI_SMS_WEBHOOK", "https://api.vapi.ai/twilio/sms")
    try:
        import requests as http_requests
        vapi_resp = http_requests.post(
            vapi_url,
            data=request.form.to_dict(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        # Vapi answers 201 Created with the TwiML (probed 9/12) — accept any 2xx.
        if 200 <= vapi_resp.status_code < 300 and vapi_resp.text.strip():
            return Response(_plain_sms(vapi_resp.text), mimetype="text/xml")
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
    """Background: photo → firm price (photo_quote.handle_photos).

    The pricing, the confidence gate and the wording live in photo_quote; this
    is only the thread seam. It used to inline its own vision prompt, which
    drifted from the price table and quoted a sectional at a $25 unit price —
    see photo_quote for why a "firm" number has to be built from the real
    categories.
    """
    with app.app_context():
        try:
            from photo_quote import handle_photos
            handle_photos(phone, body_text, media_urls)
        except Exception:
            logger.exception("photo quote failed for %s", str(phone)[-4:])
