"""
Umuve API Route Blueprints

Imports are wrapped in try/except so that in-flight specs (quotes, voice,
attach, surge, claims, resale, routing, leads) whose route modules haven't
landed on disk yet don't take down the whole `routes` package. `server.py`
already imports those optional blueprints behind their own try/except blocks.
"""
from .drivers import drivers_bp
from .pricing import pricing_bp
from .ratings import ratings_bp
from .admin import admin_bp
from .payments import payments_bp, webhook_bp
from .booking import booking_bp
from .upload import upload_bp
from .jobs import jobs_bp
from .tracking import tracking_bp
from .driver import driver_bp
from .operator import operator_bp
from .push import push_bp
from .service_area import service_area_bp
from .recurring import recurring_bp
from .referrals import referrals_bp
from .support import support_bp
from .chat import chat_bp
from .onboarding import onboarding_bp
from .promos import promos_bp
from .reviews import reviews_bp
from .vapi import vapi_bp
from .operator_applications import operator_applications_bp
from .ai_analysis import ai_bp
from .migration import migration_bp
from .sms_webhook import sms_webhook_bp
from .campaigns import campaigns_bp
from .portal import portal_bp

# In-flight spec blueprints — optional. `server.py` registers these behind
# its own try/except so missing modules don't crash boot.
_optional_names = ["quotes_bp", "attach_bp", "surge_bp", "voice_bp"]
try:
    from .quotes import quotes_bp  # noqa: F401
except Exception:
    quotes_bp = None  # type: ignore
try:
    from .attach import attach_bp  # noqa: F401
except Exception:
    attach_bp = None  # type: ignore
try:
    from .surge import surge_bp  # noqa: F401
except Exception:
    surge_bp = None  # type: ignore
try:
    from .voice import voice_bp  # noqa: F401
except Exception:
    voice_bp = None  # type: ignore

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
    "tracking_bp",
    "driver_bp",
    "operator_bp",
    "push_bp",
    "service_area_bp",
    "recurring_bp",
    "referrals_bp",
    "support_bp",
    "chat_bp",
    "onboarding_bp",
    "promos_bp",
    "reviews_bp",
    "operator_applications_bp",
    "ai_bp",
    "migration_bp",
    "vapi_bp",
    "sms_webhook_bp",
    "campaigns_bp",
    "quotes_bp",
    "attach_bp",
    "surge_bp",
    "voice_bp",
    "portal_bp",
]
