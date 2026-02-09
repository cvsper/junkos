from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps
from datetime import datetime, timedelta
import os

from app_config import Config
from database import Database
from auth_routes import auth_bp
from models import db as sqlalchemy_db
from socket_events import socketio
from routes import drivers_bp, pricing_bp, ratings_bp, admin_bp, payments_bp, webhook_bp, booking_bp, upload_bp, jobs_bp, tracking_bp, driver_bp, operator_bp

app = Flask(__name__)
app.config.from_object(Config)

# ---------------------------------------------------------------------------
# SQLAlchemy configuration
# ---------------------------------------------------------------------------
database_url = os.environ.get("DATABASE_URL", "")
if database_url:
    # Fix postgres:// to postgresql:// for SQLAlchemy 2.x
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    # Fallback to SQLite for local development
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///junkos.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# ---------------------------------------------------------------------------
# Initialize extensions
# ---------------------------------------------------------------------------
CORS(app, resources={r"/api/*": {"origins": app.config.get("CORS_ORIGINS", "*")}})
sqlalchemy_db.init_app(app)
socketio.init_app(app, cors_allowed_origins="*", async_mode="eventlet")

# Legacy SQLite database (kept for backward compatibility with existing endpoints)
legacy_db = Database(app.config["DATABASE_PATH"])

# ---------------------------------------------------------------------------
# Register blueprints
# ---------------------------------------------------------------------------
app.register_blueprint(auth_bp)
app.register_blueprint(drivers_bp)
app.register_blueprint(pricing_bp)
app.register_blueprint(ratings_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(payments_bp)
app.register_blueprint(webhook_bp)
app.register_blueprint(booking_bp)
app.register_blueprint(upload_bp)
app.register_blueprint(jobs_bp)
app.register_blueprint(tracking_bp)
app.register_blueprint(driver_bp)
app.register_blueprint(operator_bp)

# ---------------------------------------------------------------------------
# Create all SQLAlchemy tables on startup
# ---------------------------------------------------------------------------
with app.app_context():
    sqlalchemy_db.create_all()


# ---------------------------------------------------------------------------
# Authentication decorator (legacy API-key based)
# ---------------------------------------------------------------------------
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get("X-API-Key")
        if api_key != app.config["API_KEY"]:
            return jsonify({"error": "Invalid or missing API key"}), 401
        return f(*args, **kwargs)
    return decorated_function


# ---------------------------------------------------------------------------
# Helper functions (legacy)
# ---------------------------------------------------------------------------
def calculate_price(service_ids, zip_code):
    """Calculate estimated price based on services"""
    total = 0
    services = []

    for service_id in service_ids:
        service = legacy_db.get_service(service_id)
        if service:
            total += service["base_price"]
            services.append(service)

    if len(services) > 0 and total < app.config["BASE_PRICE"]:
        total += app.config["BASE_PRICE"]

    return round(total, 2), services


def get_available_time_slots(requested_date=None):
    """Generate available time slots for booking"""
    slots = []
    start_date = datetime.now() + timedelta(days=1)

    if requested_date:
        try:
            start_date = datetime.strptime(requested_date, "%Y-%m-%d")
        except Exception:
            pass

    for day_offset in range(7):
        date = start_date + timedelta(days=day_offset)
        for hour in [9, 13]:
            slot_time = date.replace(hour=hour, minute=0, second=0)
            slots.append(slot_time.strftime("%Y-%m-%d %H:%M"))

    return slots[:10]


# ---------------------------------------------------------------------------
# Legacy API Routes (kept for backward compatibility)
# ---------------------------------------------------------------------------
@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "JunkOS API"}), 200


@app.route("/api/services", methods=["GET"])
@require_api_key
def get_services():
    """Get all available services"""
    try:
        services = legacy_db.get_services()
        return jsonify({"success": True, "services": services}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/quote", methods=["POST"])
@require_api_key
def get_quote():
    """Get instant price quote"""
    try:
        data = request.get_json()

        if not data.get("services") or not isinstance(data["services"], list):
            return jsonify({"error": "Services array is required"}), 400

        zip_code = data.get("zip_code", "")
        service_ids = data["services"]

        estimated_price, services = calculate_price(service_ids, zip_code)
        available_slots = get_available_time_slots()

        return jsonify({
            "success": True,
            "estimated_price": estimated_price,
            "services": services,
            "available_time_slots": available_slots,
            "currency": "USD"
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bookings", methods=["POST"])
@require_api_key
def create_booking():
    """Create new booking"""
    try:
        data = request.get_json()

        required_fields = ["address", "services", "scheduled_datetime", "customer"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": "Missing required field: {}".format(field)}), 400

        customer_data = data["customer"]
        required_customer_fields = ["name", "email", "phone"]
        for field in required_customer_fields:
            if field not in customer_data:
                return jsonify({"error": "Missing customer field: {}".format(field)}), 400

        customer_id = legacy_db.create_customer(
            customer_data["name"],
            customer_data["email"],
            customer_data["phone"]
        )

        estimated_price, services = calculate_price(
            data["services"],
            data.get("zip_code", "")
        )

        booking_id = legacy_db.create_booking(
            customer_id=customer_id,
            address=data["address"],
            zip_code=data.get("zip_code", ""),
            services=data["services"],
            photos=data.get("photos", []),
            scheduled_datetime=data["scheduled_datetime"],
            estimated_price=estimated_price,
            notes=data.get("notes", "")
        )

        return jsonify({
            "success": True,
            "booking_id": booking_id,
            "estimated_price": estimated_price,
            "confirmation": "Booking #{} confirmed".format(booking_id),
            "scheduled_datetime": data["scheduled_datetime"],
            "services": services
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bookings/<int:booking_id>", methods=["GET"])
@require_api_key
def get_booking(booking_id):
    """Get booking details"""
    try:
        booking = legacy_db.get_booking(booking_id)

        if not booking:
            return jsonify({"error": "Booking not found"}), 404

        return jsonify({"success": True, "booking": booking}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Customer bookings endpoint (used by iOS app)
# ---------------------------------------------------------------------------
@app.route("/api/bookings/customer", methods=["POST"])
def get_customer_bookings():
    """Get all bookings for a customer by email"""
    from models import Job, User
    data = request.get_json()
    email = data.get("email") if data else None

    if not email:
        return jsonify({"success": True, "bookings": []}), 200

    # Find user by email
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"success": True, "bookings": []}), 200

    # Get jobs for this customer
    jobs = Job.query.filter_by(customer_id=user.id).order_by(Job.created_at.desc()).all()

    bookings = []
    for job in jobs:
        booking = job.to_dict()
        booking["confirmation"] = "Booking #{} confirmed".format(job.id[:8])
        bookings.append(booking)

    return jsonify({"success": True, "bookings": bookings}), 200


# ---------------------------------------------------------------------------
# Customer portal compatibility endpoints
# ---------------------------------------------------------------------------
@app.route("/api/bookings/validate-address", methods=["POST"])
def validate_address():
    """Validate an address (stub - returns success with formatted data)"""
    data = request.get_json()
    address = data.get("address", "")
    if not address:
        return jsonify({"success": False, "error": "Address is required"}), 400

    return jsonify({
        "success": True,
        "address": {
            "formatted": address,
            "placeId": None,
            "lat": 26.1224,
            "lng": -80.1373,
        }
    }), 200


@app.route("/api/bookings/upload-photos", methods=["POST"])
def upload_booking_photos():
    """Upload photos for a booking (proxy to upload blueprint)"""
    from models import generate_uuid
    from werkzeug.utils import secure_filename
    import os

    upload_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
    os.makedirs(upload_folder, exist_ok=True)

    if "photos" not in request.files:
        return jsonify({"success": False, "error": "No photos provided"}), 400

    files = request.files.getlist("photos")
    urls = []

    for file in files:
        if file and file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower()
            if ext in {"jpg", "jpeg", "png", "webp"}:
                unique_name = "{}.{}".format(generate_uuid(), ext)
                filepath = os.path.join(upload_folder, secure_filename(unique_name))
                file.save(filepath)
                urls.append("/uploads/{}".format(secure_filename(unique_name)))

    return jsonify({"success": True, "urls": urls}), 201


@app.route("/api/bookings/estimate", methods=["POST"])
def portal_estimate():
    """Price estimate compatible with customer portal API shape"""
    data = request.get_json() or {}

    category = data.get("itemCategory") or data.get("category", "general")
    quantity = int(data.get("quantity", 1))

    from routes.booking import _get_item_price, _estimate_duration, BASE_PRICE, SERVICE_FEE_RATE

    unit_price = _get_item_price(category)
    item_total = unit_price * quantity
    subtotal = BASE_PRICE + item_total
    service_fee = round(subtotal * SERVICE_FEE_RATE, 2)
    total = round(subtotal + service_fee, 2)
    duration_min = _estimate_duration(quantity)

    if duration_min <= 60:
        duration_label = "{} minutes".format(duration_min)
    else:
        hours = duration_min // 60
        remaining = duration_min % 60
        duration_label = "{}-{} hours".format(hours, hours + 1) if remaining else "{} hour{}".format(hours, "s" if hours > 1 else "")

    truck_size = "Large Truck" if quantity > 5 else "Standard Truck"

    return jsonify({
        "success": True,
        "estimate": {
            "subtotal": round(subtotal, 2),
            "serviceFee": service_fee,
            "tax": 0,
            "total": total,
            "estimatedDuration": duration_label,
            "truckSize": truck_size,
        }
    }), 200


@app.route("/api/bookings/available-slots", methods=["GET"])
def get_portal_available_slots():
    """Available time slots compatible with customer portal"""
    date_str = request.args.get("date")
    slots = get_available_time_slots(date_str[:10] if date_str else None)

    formatted = []
    for slot in slots:
        formatted.append({
            "date": slot.split(" ")[0],
            "time": slot.split(" ")[1] if " " in slot else "09:00",
            "available": True,
        })

    return jsonify({"success": True, "slots": formatted}), 200


@app.route("/api/bookings/create", methods=["POST"])
def portal_create_booking():
    """Create a booking from the customer portal (no auth required).

    Accepts the portal's form shape and creates a User + Job + Payment.
    """
    from werkzeug.security import generate_password_hash
    from models import Job, Payment, User, Notification, generate_uuid, utcnow
    from routes.booking import _get_item_price, _notify_nearby_contractors, BASE_PRICE, SERVICE_FEE_RATE

    data = request.get_json() or {}

    address = data.get("address")
    if not address:
        return jsonify({"error": "address is required"}), 400

    customer_info = data.get("customerInfo") or {}
    email = customer_info.get("email")
    name = customer_info.get("name", "")
    phone = customer_info.get("phone", "")

    if not email:
        return jsonify({"error": "customerInfo.email is required"}), 400

    # Find or create user
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email, name=name, phone=phone, role="customer",
                     password_hash=generate_password_hash(generate_uuid()))
        sqlalchemy_db.session.add(user)
        sqlalchemy_db.session.flush()

    category = data.get("itemCategory") or data.get("category") or "general"
    quantity = int(data.get("quantity", 1))
    total_amount = float(data.get("totalAmount", 0))
    # Also accept total from estimate object
    if total_amount <= 0:
        estimate = data.get("estimate") or {}
        total_amount = float(estimate.get("total", 0))

    # Recalculate price if not provided
    if total_amount <= 0:
        unit_price = _get_item_price(category)
        item_total = unit_price * quantity
        subtotal = BASE_PRICE + item_total
        service_fee = round(subtotal * SERVICE_FEE_RATE, 2)
        total_amount = round(subtotal + service_fee, 2)

    # Parse location from addressDetails if available
    addr_details = data.get("addressDetails") or {}
    location = addr_details.get("location") or {}
    lat = location.get("lat")
    lng = location.get("lng")

    # Parse scheduled datetime
    scheduled_at = None
    selected_date = data.get("selectedDate")
    selected_time = data.get("selectedTime", "09:00")

    # Normalize time: convert "8:00 AM - 10:00 AM" or "2:00 PM" to "HH:MM"
    if selected_time and isinstance(selected_time, str):
        import re
        am_pm_match = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)", selected_time, re.IGNORECASE)
        if am_pm_match:
            hour = int(am_pm_match.group(1))
            minute = am_pm_match.group(2)
            period = am_pm_match.group(3).upper()
            if period == "PM" and hour != 12:
                hour += 12
            if period == "AM" and hour == 12:
                hour = 0
            selected_time = "{:02d}:{}".format(hour, minute)

    if selected_date:
        try:
            date_str = selected_date[:10] if isinstance(selected_date, str) else selected_date.strftime("%Y-%m-%d")
            from datetime import timezone as tz
            scheduled_at = datetime.strptime("{} {}".format(date_str, selected_time), "%Y-%m-%d %H:%M").replace(tzinfo=tz.utc)
        except Exception:
            pass

    items = [{"category": category, "quantity": quantity}]
    photos = data.get("photoUrls") or data.get("photos") or []

    job = Job(
        id=generate_uuid(),
        customer_id=user.id,
        status="pending",
        address=address,
        lat=float(lat) if lat else None,
        lng=float(lng) if lng else None,
        items=items,
        photos=photos,
        scheduled_at=scheduled_at,
        base_price=BASE_PRICE,
        item_total=round(total_amount - BASE_PRICE, 2),
        service_fee=round(total_amount * SERVICE_FEE_RATE, 2),
        total_price=total_amount,
        notes=data.get("itemDescription") or data.get("description", ""),
    )
    sqlalchemy_db.session.add(job)

    payment = Payment(
        id=generate_uuid(),
        job_id=job.id,
        amount=total_amount,
        service_fee=round(total_amount * SERVICE_FEE_RATE, 2),
        payment_status="pending",
    )
    sqlalchemy_db.session.add(payment)

    _notify_nearby_contractors(job)
    sqlalchemy_db.session.commit()

    # Send confirmation email and SMS
    from notifications import send_booking_confirmation_email, send_booking_sms
    date_str = selected_date[:10] if selected_date and isinstance(selected_date, str) else "TBD"
    if email:
        send_booking_confirmation_email(
            to_email=email,
            customer_name=name,
            booking_id=job.id,
            address=address,
            scheduled_date=date_str,
            scheduled_time=selected_time,
            total_amount=total_amount,
        )
    if phone:
        send_booking_sms(phone, job.id, date_str, address)

    return jsonify({
        "success": True,
        "bookingId": job.id,
        "job": job.to_dict(),
    }), 201


@app.route("/api/payments/confirm-simple", methods=["POST"])
def confirm_payment_simple():
    """Confirm a payment without auth (for customer portal).

    In dev mode (no Stripe webhook), this acts as the payment-succeeded handler:
    marks the payment as succeeded, updates job status, and auto-assigns a driver.
    """
    from models import Payment, Job, Notification, generate_uuid, utcnow

    data = request.get_json() or {}
    intent_id = data.get("paymentIntentId") or data.get("payment_intent_id")

    if not intent_id:
        return jsonify({"error": "paymentIntentId is required"}), 400

    payment = Payment.query.filter_by(stripe_payment_intent_id=intent_id).first()
    if not payment:
        return jsonify({"error": "Payment not found"}), 404

    payment.payment_status = "succeeded"
    payment.updated_at = utcnow()

    # Update job status and trigger auto-assignment
    job = sqlalchemy_db.session.get(Job, payment.job_id)
    if job and job.status == "pending":
        job.status = "confirmed"
        job.updated_at = utcnow()

        # Auto-assign nearest driver
        from routes.payments import _auto_assign_driver
        _auto_assign_driver(job)

        # Broadcast status update
        from socket_events import broadcast_job_status
        broadcast_job_status(job.id, job.status)

    sqlalchemy_db.session.commit()

    return jsonify({
        "success": True,
        "payment": payment.to_dict(),
        "job": job.to_dict() if job else None,
    }), 200


# Serve uploaded files
@app.route("/uploads/<filename>")
def serve_uploaded_file(filename):
    """Serve uploaded files"""
    from flask import send_from_directory
    import os
    upload_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
    return send_from_directory(upload_folder, filename)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    debug = os.environ.get("FLASK_ENV", "development") == "development"
    socketio.run(app, debug=debug, host="0.0.0.0", port=port)
