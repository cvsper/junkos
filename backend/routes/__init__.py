"""
JunkOS API Route Blueprints
"""
from .drivers import drivers_bp
from .pricing import pricing_bp
from .ratings import ratings_bp
from .admin import admin_bp
from .payments import payments_bp, webhook_bp
from .booking import booking_bp
from .upload import upload_bp
from .jobs import jobs_bp

__all__ = [
    "drivers_bp",
    "pricing_bp",
    "ratings_bp",
    "admin_bp",
    "payments_bp",
    "webhook_bp",
    "booking_bp",
    "upload_bp",
    "jobs_bp",
]
