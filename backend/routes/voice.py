"""
Placeholder for Voice AI Inbound routes (spec 02).

Keeps the `routes` package importable until the real module ships.
Contains an empty Blueprint so the package import doesn't fail.
"""

from flask import Blueprint

voice_bp = Blueprint("voice", __name__, url_prefix="/api/v1/voice")
