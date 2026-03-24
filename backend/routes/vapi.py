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

from models import db, User, Job, Payment, generate_uuid, generate_referral_code

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
        call = message.get("call", {})
        summary = message.get("summary", "")
        duration = message.get("endedReason", "")
        logger.info(
            "Vapi call ended: duration=%s reason=%s summary=%s",
            call.get("duration"), duration, summary[:200] if summary else "",
        )
    elif msg_type == "status-update":
        status = message.get("status", "")
        logger.info("Vapi call status: %s", status)
    elif msg_type == "transcript":
        # Could store transcripts for training/review
        pass

    return jsonify({"ok": True})
