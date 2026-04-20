"""
Placeholder for Vision-Based Binding Quote Engine routes (spec 01).

Keeps `routes/__init__.py` importable until the real module ships.
Contains an empty Blueprint so the package import doesn't fail.
"""

from flask import Blueprint

quotes_bp = Blueprint("quotes", __name__, url_prefix="/api/v1/quotes")
