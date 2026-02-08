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
from routes import drivers_bp, pricing_bp, ratings_bp, admin_bp, payments_bp, booking_bp, upload_bp, jobs_bp

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
app.register_blueprint(booking_bp)
app.register_blueprint(upload_bp)
app.register_blueprint(jobs_bp)

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
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    debug = os.environ.get("FLASK_ENV", "development") == "development"
    socketio.run(app, debug=debug, host="0.0.0.0", port=port)
