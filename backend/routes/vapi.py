"""
Vapi AI phone agent webhook handler.

Handles tool calls from the Vapi assistant (price estimates, bookings,
service area checks) and webhook events (call started, ended, etc.).
"""

import os
import json
import logging
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify

from models import db, User, Job, Payment, CallLog, ScheduledCallback, Contractor, generate_uuid, generate_referral_code
from auth_routes import require_auth

logger = logging.getLogger(__name__)

vapi_bp = Blueprint("vapi", __name__, url_prefix="/api/vapi")


# ---------------------------------------------------------------------------
# Tool call handler -- Vapi sends tool calls here
# ---------------------------------------------------------------------------
@vapi_bp.route("/tool", methods=["POST"])
def handle_tool_call():
    """Handle tool calls from Vapi assistant.

    Vapi sends:
    {
        "message": {
            "type": "tool-calls",
            "toolCallList": [
                {
                    "id": "...",
                    "type": "function",
                    "function": {
                        "name": "get_price_estimate",
                        "arguments": {...}
                    }
                }
            ]
        }
    }

    We return:
    {
        "results": [
            {
                "toolCallId": "...",
                "result": "..."
            }
        ]
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400

    message = data.get("message", {})
    tool_calls = message.get("toolCallList", [])

    results = []
    for tc in tool_calls:
        tc_id = tc.get("id", "")
        func = tc.get("function", {})
        name = func.get("name", "")
        args = func.get("arguments", {})

        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}

        if name == "get_price_estimate":
            result = _handle_price_estimate(args)
        elif name == "create_booking":
            result = _handle_create_booking(args, data)
        elif name == "check_service_area":
            result = _handle_service_area(args)
        elif name == "send_checkout_text":
            result = _handle_checkout_text(args, data)
        elif name == "send_review_link":
            result = _handle_send_review_link(args, data)
        elif name == "transfer_with_context":
            result = _handle_transfer_with_context(args)
        elif name == "schedule_callback":
            result = _handle_schedule_callback(args, data)
        elif name == "send_operator_signup_text":
            result = _handle_operator_signup_text(args, data)
        else:
            result = "Unknown tool: {}".format(name)

        results.append({"toolCallId": tc_id, "result": str(result)})

    return jsonify({"results": results})


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _handle_price_estimate(args):
    """Calculate price estimate from items list."""
    from routes.booking import calculate_estimate

    items = args.get("items", [])
    scheduled_date = args.get("scheduled_date")

    if not items:
        return "I need to know what items you'd like removed to give you a quote."

    est = calculate_estimate(items, scheduled_date=scheduled_date)

    item_lines = []
    for item in est.get("items", []):
        item_lines.append("- {} x{}: ${:.0f}".format(
            item.get("category", "Item"),
            item.get("quantity", 1),
            item.get("line_total", 0),
        ))

    breakdown = "\n".join(item_lines)

    result = "Price estimate:\n{}\nSubtotal: ${:.0f}\n".format(
        breakdown, est.get("items_subtotal", 0)
    )

    if est.get("volume_discount", 0) > 0:
        result += "Volume discount: -${:.0f}\n".format(est["volume_discount"])

    if est.get("surge_multiplier", 1.0) > 1.0:
        reasons = ", ".join(est.get("surge_reasons", []))
        result += "Surge pricing: {}\n".format(reasons)

    if est.get("recycling_fees", 0) > 0:
        result += "Recycling/disposal fees: ${:.0f}\n".format(est["recycling_fees"])

    result += "Service fee (8%): ${:.0f}\nTotal: ${:.0f}".format(
        est.get("service_fee", 0), est.get("total", 0)
    )

    if est.get("minimum_applied"):
        result += " (minimum job price applied)"

    return result


def _handle_create_booking(args, vapi_data):
    """Create a booking from the phone call."""
    from routes.booking import calculate_estimate

    name = args.get("customer_name", "")
    address = args.get("address", "")
    email = (args.get("email") or "").strip().lower()
    phone = args.get("phone", "")
    items = args.get("items", [])
    scheduled_date = args.get("scheduled_date")
    scheduled_time = args.get("scheduled_time", "09:00")

    if not address or not items:
        return "I need the pickup address and items to create a booking."

    if not email:
        return "I need an email address to send the booking confirmation."

    # Get caller's phone from Vapi call data if not provided
    if not phone:
        call = vapi_data.get("message", {}).get("call", {})
        phone = call.get("customer", {}).get("number", "")

    # Calculate pricing
    est = calculate_estimate(items, scheduled_date=scheduled_date)
    total = est["total"]

    # Parse scheduled datetime
    scheduled_at = None
    if scheduled_date:
        time_str = scheduled_time
        if "-" in time_str and ":" not in time_str:
            try:
                start_hour = int(time_str.split("-")[0])
                time_str = "{:02d}:00".format(start_hour)
            except Exception:
                time_str = "09:00"
        try:
            scheduled_at = datetime.strptime(
                "{} {}".format(scheduled_date, time_str), "%Y-%m-%d %H:%M"
            ).replace(tzinfo=timezone.utc)
        except Exception:
            pass

    # Find or create user
    existing = User.query.filter_by(email=email).first()
    if existing:
        user_id = existing.id
        if name and not existing.name:
            existing.name = name
        if phone and not existing.phone:
            existing.phone = phone
    else:
        user = User(
            id=generate_uuid(),
            email=email,
            name=name or None,
            phone=phone or None,
            role="customer",
        )
        db.session.add(user)
        db.session.flush()
        user_id = user.id

    # Create job
    job = Job(
        id=generate_uuid(),
        customer_id=user_id,
        status="pending",
        address=address,
        items=items,
        scheduled_at=scheduled_at,
        base_price=est["base_price"],
        item_total=round(est["items_subtotal"], 2),
        service_fee=est["service_fee"],
        surge_multiplier=est["surge_multiplier"],
        total_price=total,
        notes="Booked via phone call (AI receptionist)",
        confirmation_code=generate_referral_code(),
    )
    db.session.add(job)

    # Create payment record
    payment = Payment(
        id=generate_uuid(),
        job_id=job.id,
        amount=total,
        service_fee=est["service_fee"],
        payment_status="pending",
    )
    db.session.add(payment)
    db.session.commit()

    # Send confirmation email
    try:
        from notifications import send_booking_confirmation_email, send_booking_sms
        date_str = str(scheduled_at.date()) if scheduled_at else "TBD"
        time_display = scheduled_time or ""
        if email:
            send_booking_confirmation_email(
                to_email=email,
                customer_name=name,
                booking_id=job.id,
                address=address,
                scheduled_date=date_str,
                scheduled_time=time_display,
                total_amount=total,
            )
        if phone:
            send_booking_sms(phone, job.id, date_str, address)
    except Exception:
        logger.exception("Failed to send booking confirmation")

    # Notify operator via SMS
    try:
        from sms_service import send_sms_async
        operator_phone = os.environ.get("OPERATOR_PHONE", "")
        if operator_phone:
            items_count = sum(
                i.get("quantity", 1) for i in items if isinstance(i, dict)
            )
            msg = (
                "NEW PHONE BOOKING!\n"
                "{} - {}\n"
                "{} item{} | ${:.0f}\n"
                "Scheduled: {} {}"
            ).format(
                name, address,
                items_count, "s" if items_count != 1 else "",
                total,
                str(scheduled_at.date()) if scheduled_at else "TBD",
                scheduled_time,
            )
            send_sms_async(operator_phone, msg)
    except Exception:
        logger.exception("Failed to send operator SMS")

    short_id = str(job.id)[:8]
    return (
        "Booking confirmed! Here are the details:\n"
        "Booking #{}\n"
        "Address: {}\n"
        "Date: {} at {}\n"
        "Total: ${:.0f}\n"
        "A confirmation email has been sent to {}."
    ).format(
        short_id,
        address,
        str(scheduled_at.date()) if scheduled_at else "TBD",
        scheduled_time,
        total,
        email,
    )


def _handle_service_area(args):
    """Check if address is in service area."""
    address = args.get("address", "").lower()

    in_area_keywords = [
        "miami", "fort lauderdale", "boca raton", "west palm", "palm beach",
        "hollywood", "pembroke", "coral springs", "pompano", "deerfield",
        "boynton", "delray", "plantation", "davie", "sunrise", "weston",
        "hialeah", "homestead", "kendall", "doral", "aventura", "hallandale",
        "miramar", "coconut creek", "margate", "tamarac", "lauderhill",
        "north miami", "miami beach", "miami gardens", "broward",
        "palm beach county", "miami-dade", "jupiter", "wellington",
        "royal palm", "lake worth", "riviera beach", "greenacres",
        "lauderdale", "cooper city", "parkland", "coral gables",
        "key biscayne", "surfside", "bal harbour",
    ]

    for keyword in in_area_keywords:
        if keyword in address:
            return (
                "Yes, {} is in our service area! We serve all of "
                "Miami-Dade, Broward, and Palm Beach counties."
            ).format(args["address"])

    # Check if it mentions Florida at all
    if "florida" in address or "fl" in address.split():
        return (
            "I'm not 100% sure if {} is in our service area. We serve "
            "Miami-Dade, Broward, and Palm Beach counties. Could you "
            "confirm which county you're in?"
        ).format(args["address"])

    return (
        "Unfortunately, {} appears to be outside our service area. "
        "We currently serve Miami-Dade, Broward, and Palm Beach counties "
        "in South Florida."
    ).format(args["address"])


def _handle_checkout_text(args, vapi_data):
    """Send the customer a text with the checkout/confirmation link."""
    from sms_service import send_sms_async

    phone = args.get("phone", "")
    booking_id = args.get("booking_id", "")
    customer_name = args.get("customer_name", "")
    total = args.get("total", 0)

    # Get caller phone from Vapi if not provided
    if not phone:
        call = vapi_data.get("message", {}).get("call", {})
        phone = call.get("customer", {}).get("number", "")

    if not phone:
        return "I need a phone number to send the text."

    frontend_url = os.environ.get("FRONTEND_URL", "https://app.goumuve.com")
    short_id = str(booking_id)[:8] if booking_id else ""
    checkout_url = "{}/book?ref=phone".format(frontend_url)
    if booking_id:
        checkout_url = "{}/jobs/{}".format(frontend_url, booking_id)

    greeting = "Hi {}! ".format(customer_name) if customer_name else ""
    msg = (
        "{}Thanks for calling You-Move! "
        "Here's your booking link to confirm & pay:\n\n"
        "{}\n\n"
        "Total: ${:.0f}\n"
        "Questions? Just call us back at (561) 944-1636"
    ).format(greeting, checkout_url, float(total) if total else 0)

    send_sms_async(phone, msg)
    return "Text sent to {} with the checkout link.".format(phone)


def _handle_send_review_link(args, vapi_data):
    """Send the customer a Google review link via SMS."""
    from sms_service import send_sms_async

    phone = args.get("phone", "")

    # Get caller phone from Vapi if not provided
    if not phone:
        call = vapi_data.get("message", {}).get("call", {})
        phone = call.get("customer", {}).get("number", "")

    if not phone:
        return "I need a phone number to send the review link."

    google_review_url = os.environ.get(
        "GOOGLE_REVIEW_URL", "https://g.page/r/umuve/review"
    )

    msg = (
        "Thanks for choosing You-Move! \U0001f64f "
        "We'd love a quick Google review: {}\n"
        "It really helps us out!"
    ).format(google_review_url)

    send_sms_async(phone, msg)
    return "Review link sent to {} via text.".format(phone)


def _handle_transfer_with_context(args):
    """Send operator an SMS context summary before a warm transfer."""
    from sms_service import send_sms_async

    customer_name = args.get("customer_name", "Unknown")
    reason = args.get("reason", "Not specified")
    items = args.get("items", "None discussed")
    estimated_total = args.get("estimated_total", "")
    address = args.get("address", "Not provided")
    notes = args.get("notes", "")

    quote_line = "${:.0f}".format(float(estimated_total)) if estimated_total else "No quote given"

    msg = (
        "INCOMING TRANSFER from Maya:\n"
        "Customer: {}\n"
        "Reason: {}\n"
        "Items discussed: {}\n"
        "Quote given: {}\n"
        "Address: {}"
    ).format(customer_name, reason, items, quote_line, address)

    if notes:
        msg += "\nNotes: {}".format(notes)

    operator_phone = os.environ.get("OPERATOR_PHONE", "+15618883427")
    send_sms_async(operator_phone, msg)

    logger.info("Transfer context SMS sent to operator for customer: %s", customer_name)

    return "Context sent to operator. Please transfer the call now."


def _handle_schedule_callback(args, vapi_data):
    """Schedule a callback for the customer."""
    customer_name = args.get("customer_name", "")
    phone = args.get("phone", "")
    callback_time = args.get("callback_time", "")

    # Get caller phone from Vapi if not provided
    if not phone:
        call = vapi_data.get("message", {}).get("call", {})
        phone = call.get("customer", {}).get("number", "")

    if not phone:
        return "I need a phone number to schedule a callback."

    if not callback_time:
        return "I need to know when you'd like us to call back."

    # Get call_id from Vapi data
    call_id = vapi_data.get("message", {}).get("call", {}).get("id", "")

    # Try to parse the callback time into a datetime
    scheduled_at = None
    try:
        from dateutil import parser as dateutil_parser
        scheduled_at = dateutil_parser.parse(callback_time, fuzzy=True)
        if scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
    except Exception:
        # Store the raw text; operator will interpret it
        pass

    callback = ScheduledCallback(
        id=generate_uuid(),
        phone=phone,
        customer_name=customer_name or None,
        requested_time=callback_time,
        scheduled_at=scheduled_at,
        status="pending",
        call_id=call_id or None,
    )
    db.session.add(callback)
    db.session.commit()

    # Notify operator
    try:
        from sms_service import send_sms_async
        operator_phone = os.environ.get("OPERATOR_PHONE", "")
        if operator_phone:
            msg = (
                "CALLBACK REQUESTED\n"
                "Name: {}\n"
                "Phone: {}\n"
                "When: {}"
            ).format(customer_name or "Unknown", phone, callback_time)
            send_sms_async(operator_phone, msg)
    except Exception:
        logger.exception("Failed to send callback notification SMS")

    return "Got it! We'll give you a call back {}. Talk soon!".format(callback_time)


def _handle_operator_signup_text(args, vapi_data):
    """Send a job seeker a text with the operator/driver signup link."""
    from sms_service import send_sms_async

    phone = args.get("phone", "")
    name = args.get("name", "")
    language = args.get("language", "en")

    if not phone:
        call = vapi_data.get("message", {}).get("call", {})
        phone = call.get("customer", {}).get("number", "")

    if not phone:
        return "I need a phone number to send the signup link."

    signup_url = "https://goumuve.com/operators"

    if language == "es":
        msg = (
            "Hola{}! Gracias por tu interes en trabajar con Umuve. "
            "Registrate aqui para ser operador/conductor: {}"
        ).format(" " + name if name else "", signup_url)
    else:
        msg = (
            "Hey{}! Thanks for your interest in working with Umuve. "
            "Sign up here to become an operator/driver: {}"
        ).format(" " + name if name else "", signup_url)

    send_sms_async(phone, msg)

    # Notify operator about the job inquiry
    operator_phone = os.environ.get("OPERATOR_PHONE", "+15618883427")
    notify_msg = (
        "JOB INQUIRY via Maya:\n"
        "Name: {}\n"
        "Phone: {}\n"
        "Language: {}\n"
        "Signup link texted."
    ).format(name or "Unknown", phone, language)
    send_sms_async(operator_phone, notify_msg)

    logger.info("Operator signup text sent to %s (%s)", phone, name)

    return "Signup link sent! Let them know to check their texts."


# ---------------------------------------------------------------------------
# Webhook handler -- Vapi sends call events here
# ---------------------------------------------------------------------------
@vapi_bp.route("/webhook", methods=["POST"])
def handle_webhook():
    """Handle Vapi webhook events (call started, ended, transcript, etc.)."""
    data = request.get_json()
    if not data:
        return jsonify({"ok": True})

    message = data.get("message", {})
    msg_type = message.get("type", "")

    if msg_type == "end-of-call-report":
        _handle_end_of_call_report(message)
    elif msg_type == "status-update":
        status = message.get("status", "")
        logger.info("Vapi call status: %s", status)
    elif msg_type == "transcript":
        _handle_transcript(message)

    return jsonify({"ok": True})


def _handle_end_of_call_report(message):
    """Process end-of-call report: store CallLog, match customer, notify operator."""
    call = message.get("call", {})
    call_id = call.get("id", "")
    phone_number = call.get("customer", {}).get("number", "")
    duration = call.get("duration", None)
    ended_reason = message.get("endedReason", "")
    transcript_text = message.get("transcript", "")
    summary = message.get("summary", "")
    analysis = message.get("analysis", {})
    sentiment = analysis.get("sentiment", None)

    # Extract tools used from the messages array
    tools_used = []
    for msg in message.get("messages", []):
        if msg.get("role") == "tool_calls":
            for tc in msg.get("toolCalls", []):
                func_name = tc.get("function", {}).get("name", "")
                if func_name and func_name not in tools_used:
                    tools_used.append(func_name)

    # Check if a booking was created during this call
    booking_created = "create_booking" in tools_used

    # Try to match customer by phone number
    customer_id = None
    customer = None
    if phone_number:
        customer = User.query.filter_by(phone=phone_number).first()
        if customer:
            customer_id = customer.id

    # Check if CallLog already exists (from partial transcript)
    call_log = CallLog.query.filter_by(call_id=call_id).first() if call_id else None

    if call_log:
        # Update existing record
        call_log.phone_number = phone_number or call_log.phone_number
        call_log.duration_seconds = int(duration) if duration else None
        call_log.status = ended_reason or "completed"
        call_log.transcript = transcript_text or call_log.transcript
        call_log.summary = summary
        call_log.sentiment = sentiment
        call_log.tools_used = tools_used if tools_used else call_log.tools_used
        call_log.booking_created = booking_created
        call_log.customer_id = customer_id or call_log.customer_id
        call_log.ended_at = datetime.now(timezone.utc)
    else:
        # Create new record
        call_log = CallLog(
            id=generate_uuid(),
            call_id=call_id or generate_uuid(),
            phone_number=phone_number,
            direction=call.get("direction", "inbound"),
            duration_seconds=int(duration) if duration else None,
            status=ended_reason or "completed",
            transcript=transcript_text,
            summary=summary,
            sentiment=sentiment,
            tools_used=tools_used if tools_used else None,
            booking_created=booking_created,
            customer_id=customer_id,
            ended_at=datetime.now(timezone.utc),
        )
        db.session.add(call_log)

    # -----------------------------------------------------------------------
    # Feature 1: Lead Qualification Scoring
    # -----------------------------------------------------------------------
    if booking_created:
        lead_score = "hot"
    elif "get_price_estimate" in tools_used or "schedule_callback" in tools_used:
        lead_score = "warm"
    else:
        lead_score = "cold"

    call_log.lead_score = lead_score

    db.session.commit()

    logger.info(
        "CallLog saved: call_id=%s phone=%s duration=%s booking=%s lead=%s",
        call_id, phone_number, duration, booking_created, lead_score,
    )

    frontend_url = os.environ.get("FRONTEND_URL", "https://app.goumuve.com")

    # Send follow-up email if booking was created and customer has email
    if booking_created and customer and customer.email:
        try:
            from notifications import send_booking_confirmation_email
            # Find the most recent job for this customer booked via phone
            recent_job = Job.query.filter_by(
                customer_id=customer.id,
            ).order_by(Job.created_at.desc()).first()

            if recent_job:
                send_booking_confirmation_email(
                    to_email=customer.email,
                    customer_name=customer.name or "",
                    booking_id=recent_job.id,
                    address=recent_job.address or "",
                    scheduled_date=str(recent_job.scheduled_at.date()) if recent_job.scheduled_at else "TBD",
                    scheduled_time=str(recent_job.scheduled_at.strftime("%H:%M")) if recent_job.scheduled_at else "",
                    total_amount=recent_job.total_price or 0,
                )
        except Exception:
            logger.exception("Failed to send post-call follow-up email")

    # -----------------------------------------------------------------------
    # Feature 1 (warm leads): Auto-text customer with quote + booking link
    # -----------------------------------------------------------------------
    if lead_score == "warm" and phone_number:
        try:
            from sms_service import send_sms_async

            # Try to find the price estimate from the call's tool results
            estimate_total = None
            customer_name_from_call = ""
            for msg_item in message.get("messages", []):
                if msg_item.get("role") == "tool_calls":
                    for tc in msg_item.get("toolCalls", []):
                        if tc.get("function", {}).get("name") == "get_price_estimate":
                            # Look for the result in subsequent tool_call_result messages
                            pass
                # Try to extract name from assistant messages
                if msg_item.get("role") == "tool_call_result":
                    result_text = msg_item.get("result", "")
                    if "Total:" in result_text:
                        try:
                            total_str = result_text.split("Total: $")[1].split("\n")[0].split(" ")[0]
                            estimate_total = float(total_str)
                        except Exception:
                            pass

            # Also check if customer record has a name
            cust_name = ""
            if customer:
                cust_name = customer.name or ""

            greeting = "Hey {}! ".format(cust_name) if cust_name else "Hey! "

            if estimate_total:
                warm_msg = (
                    "{}Here's your You-Move quote: ${:.0f}. "
                    "Book anytime: {}/book?ref=phone "
                    "-- price is good for 48 hours!"
                ).format(greeting, estimate_total, frontend_url)
            else:
                warm_msg = (
                    "{}Thanks for calling You-Move! "
                    "Ready to book? {}/book?ref=phone "
                    "-- or call us back at (561) 944-1636!"
                ).format(greeting, frontend_url)

            send_sms_async(phone_number, warm_msg)
            call_log.followup_sent = True
            db.session.commit()
            logger.info("Warm lead follow-up SMS sent to %s", phone_number)
        except Exception:
            logger.exception("Failed to send warm lead follow-up SMS")

    # -----------------------------------------------------------------------
    # Feature 2: SMS Follow-Up After Non-Booking Calls
    # -----------------------------------------------------------------------
    duration_val = int(duration) if duration else 0
    if (not booking_created and phone_number and duration_val > 30
            and not call_log.followup_sent):
        try:
            from sms_service import send_sms_async
            followup_msg = (
                "Hey! Thanks for calling You-Move. Need a pickup? "
                "Book online anytime at {}/book?ref=phone "
                "or call us back at (561) 944-1636. "
                "We're here 7 days a week!"
            ).format(frontend_url)
            send_sms_async(phone_number, followup_msg)
            call_log.followup_sent = True
            db.session.commit()
            logger.info("Non-booking follow-up SMS sent to %s", phone_number)
        except Exception:
            logger.exception("Failed to send non-booking follow-up SMS")

    # Send operator summary SMS
    try:
        from sms_service import send_sms_async
        operator_phone = os.environ.get("OPERATOR_PHONE", "")
        if operator_phone:
            duration_str = "{}s".format(duration) if duration else "N/A"
            summary_short = (summary[:150] + "...") if summary and len(summary) > 150 else (summary or "No summary")
            tools_str = ", ".join(tools_used) if tools_used else "none"
            msg = (
                "CALL ENDED\n"
                "Phone: {}\n"
                "Duration: {}\n"
                "Status: {}\n"
                "Booking: {}\n"
                "Lead: {}\n"
                "Tools: {}\n"
                "Summary: {}"
            ).format(
                phone_number or "unknown",
                duration_str,
                ended_reason or "completed",
                "Yes" if booking_created else "No",
                lead_score,
                tools_str,
                summary_short,
            )
            send_sms_async(operator_phone, msg)
    except Exception:
        logger.exception("Failed to send operator call summary SMS")


def _handle_transcript(message):
    """Store partial transcript updates. Append to existing CallLog or create placeholder."""
    call = message.get("call", {})
    call_id = call.get("id", "")
    phone_number = call.get("customer", {}).get("number", "")
    transcript_text = message.get("transcript", "")

    if not call_id:
        return

    call_log = CallLog.query.filter_by(call_id=call_id).first()

    if call_log:
        # Append new transcript content
        if transcript_text:
            if call_log.transcript:
                call_log.transcript = call_log.transcript + "\n" + transcript_text
            else:
                call_log.transcript = transcript_text
    else:
        # Create placeholder record
        customer_id = None
        if phone_number:
            customer = User.query.filter_by(phone=phone_number).first()
            if customer:
                customer_id = customer.id

        call_log = CallLog(
            id=generate_uuid(),
            call_id=call_id,
            phone_number=phone_number,
            direction=call.get("direction", "inbound"),
            status="in-progress",
            transcript=transcript_text,
            customer_id=customer_id,
        )
        db.session.add(call_log)

    db.session.commit()


# ---------------------------------------------------------------------------
# Call log API endpoints (operator dashboard)
# ---------------------------------------------------------------------------
@vapi_bp.route("/calls", methods=["GET"])
def list_call_logs():
    """Return recent call logs, paginated. Defaults to last 50.

    Query params:
        page (int): page number, default 1
        per_page (int): results per page, default 50, max 100
        status (str): filter by status
        booking_only (bool): if "true", only calls that created bookings
        assigned_to (str): filter by assigned operator or driver user_id
        assignment_status (str): filter by assignment_status (unassigned, assigned_operator, assigned_driver, completed)
    """
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 100)
    status_filter = request.args.get("status", None)
    booking_only = request.args.get("booking_only", "").lower() == "true"
    assigned_to = request.args.get("assigned_to", None)
    assignment_status = request.args.get("assignment_status", None)

    query = CallLog.query

    if status_filter:
        query = query.filter(CallLog.status == status_filter)
    if booking_only:
        query = query.filter(CallLog.booking_created == True)
    if assigned_to:
        from sqlalchemy import or_
        query = query.filter(
            or_(
                CallLog.assigned_operator_id == assigned_to,
                CallLog.assigned_driver_id == assigned_to,
            )
        )
    if assignment_status:
        query = query.filter(CallLog.assignment_status == assignment_status)

    query = query.order_by(CallLog.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "calls": [c.to_dict() for c in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    })


@vapi_bp.route("/calls/<call_id>", methods=["GET"])
def get_call_log(call_id):
    """Return a single call log by Vapi call_id or internal id."""
    call_log = CallLog.query.filter_by(call_id=call_id).first()
    if not call_log:
        call_log = CallLog.query.filter_by(id=call_id).first()

    if not call_log:
        return jsonify({"error": "Call log not found"}), 404

    return jsonify(call_log.to_dict())


@vapi_bp.route("/callbacks", methods=["GET"])
def list_callbacks():
    """Return pending scheduled callbacks for the operator dashboard.

    Query params:
        status (str): filter by status (default: pending)
        page (int): page number, default 1
        per_page (int): results per page, default 50, max 100
        assigned_to (str): filter by assigned operator or driver user_id
        assignment_status (str): filter by assignment_status
    """
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 100)
    status_filter = request.args.get("status", "pending")
    assigned_to = request.args.get("assigned_to", None)
    assignment_status = request.args.get("assignment_status", None)

    query = ScheduledCallback.query

    if status_filter:
        query = query.filter(ScheduledCallback.status == status_filter)
    if assigned_to:
        from sqlalchemy import or_
        query = query.filter(
            or_(
                ScheduledCallback.assigned_operator_id == assigned_to,
                ScheduledCallback.assigned_driver_id == assigned_to,
            )
        )
    if assignment_status:
        query = query.filter(ScheduledCallback.assignment_status == assignment_status)

    query = query.order_by(ScheduledCallback.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "callbacks": [cb.to_dict() for cb in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    })


# ---------------------------------------------------------------------------
# Lead assignment endpoints
# ---------------------------------------------------------------------------
@vapi_bp.route("/calls/<call_id>/assign", methods=["POST"])
@require_auth
def assign_call(user_id, call_id):
    """Assign a call/lead to an operator and/or driver.

    Body: {"operator_id": "...", "driver_id": "..."}  (either or both)
    """
    # Verify requesting user is admin or operator
    requesting_user = db.session.get(User, user_id)
    if not requesting_user or requesting_user.role not in ("admin", "operator"):
        return jsonify({"error": "Forbidden"}), 403

    call_log = CallLog.query.filter_by(id=call_id).first()
    if not call_log:
        call_log = CallLog.query.filter_by(call_id=call_id).first()
    if not call_log:
        return jsonify({"error": "Call log not found"}), 404

    data = request.get_json() or {}
    operator_id = data.get("operator_id")
    driver_id = data.get("driver_id")

    if not operator_id and not driver_id:
        return jsonify({"error": "Must provide operator_id or driver_id"}), 400

    now = datetime.now(timezone.utc)

    if operator_id:
        op_user = db.session.get(User, operator_id)
        if not op_user or op_user.role not in ("operator", "admin"):
            return jsonify({"error": "Invalid operator_id"}), 400
        call_log.assigned_operator_id = operator_id
        call_log.assignment_status = "assigned_operator"
        call_log.assigned_at = now

    if driver_id:
        drv_user = db.session.get(User, driver_id)
        if not drv_user or drv_user.role not in ("driver", "operator", "admin"):
            return jsonify({"error": "Invalid driver_id"}), 400
        call_log.assigned_driver_id = driver_id
        call_log.assignment_status = "assigned_driver"
        call_log.assigned_at = now

    db.session.commit()
    return jsonify(call_log.to_dict())


@vapi_bp.route("/callbacks/<callback_id>/assign", methods=["POST"])
@require_auth
def assign_callback(user_id, callback_id):
    """Assign a callback to an operator and/or driver.

    Body: {"operator_id": "...", "driver_id": "..."}  (either or both)
    """
    requesting_user = db.session.get(User, user_id)
    if not requesting_user or requesting_user.role not in ("admin", "operator"):
        return jsonify({"error": "Forbidden"}), 403

    callback = ScheduledCallback.query.filter_by(id=callback_id).first()
    if not callback:
        return jsonify({"error": "Callback not found"}), 404

    data = request.get_json() or {}
    operator_id = data.get("operator_id")
    driver_id = data.get("driver_id")

    if not operator_id and not driver_id:
        return jsonify({"error": "Must provide operator_id or driver_id"}), 400

    now = datetime.now(timezone.utc)

    if operator_id:
        op_user = db.session.get(User, operator_id)
        if not op_user or op_user.role not in ("operator", "admin"):
            return jsonify({"error": "Invalid operator_id"}), 400
        callback.assigned_operator_id = operator_id
        callback.assignment_status = "assigned_operator"
        callback.assigned_at = now

    if driver_id:
        drv_user = db.session.get(User, driver_id)
        if not drv_user or drv_user.role not in ("driver", "operator", "admin"):
            return jsonify({"error": "Invalid driver_id"}), 400
        callback.assigned_driver_id = driver_id
        callback.assignment_status = "assigned_driver"
        callback.assigned_at = now

    db.session.commit()
    return jsonify(callback.to_dict())


@vapi_bp.route("/assignees", methods=["GET"])
@require_auth
def list_assignees(user_id):
    """Return lists of operators and drivers for assignment dropdowns.

    Query params:
        role (str): "operator", "driver", or omit for both
    """
    requesting_user = db.session.get(User, user_id)
    if not requesting_user or requesting_user.role not in ("admin", "operator"):
        return jsonify({"error": "Forbidden"}), 403

    role_filter = request.args.get("role", None)

    operators = []
    drivers = []

    if not role_filter or role_filter == "operator":
        op_users = User.query.filter(
            User.role == "operator",
            User.status == "active",
        ).order_by(User.name).all()
        operators = [{"id": u.id, "name": u.name, "email": u.email} for u in op_users]

    if not role_filter or role_filter == "driver":
        drv_users = User.query.filter(
            User.role == "driver",
            User.status == "active",
        ).order_by(User.name).all()
        drivers = [{"id": u.id, "name": u.name, "email": u.email} for u in drv_users]

    return jsonify({
        "operators": operators,
        "drivers": drivers,
    })
