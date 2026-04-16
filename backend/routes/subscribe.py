"""
Public subscribe endpoint for Umuve newsletter / email lists.
No auth required — this is a public-facing endpoint.
"""

import logging
import re

from flask import Blueprint, request, jsonify

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, Subscriber, generate_uuid

logger = logging.getLogger(__name__)

subscribe_bp = Blueprint("subscribe", __name__, url_prefix="/api")

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


@subscribe_bp.route("/subscribe", methods=["POST"])
def subscribe():
    """Add a subscriber to a mailing list.

    Body JSON:
        email: str (required)
        name: str (optional)
        source: str (optional, default "website")
        list: str (optional, default "newsletter")
    """
    data = request.get_json(force=True) if request.is_json else {}

    email = (data.get("email") or "").strip().lower()
    name = (data.get("name") or "").strip()
    source = (data.get("source") or "website").strip()[:50]
    list_name = (data.get("list") or "newsletter").strip()[:50]

    if not email or not EMAIL_RE.match(email):
        return jsonify({"error": "Valid email is required"}), 400

    # Check for existing subscriber
    existing = Subscriber.query.filter_by(email=email).first()
    if existing:
        # If they unsubscribed before, reactivate
        if existing.status == "unsubscribed":
            existing.status = "active"
            existing.list_name = list_name
            if name:
                existing.name = name
            db.session.commit()
            return jsonify({"message": "Welcome back!", "subscriber": existing.to_dict()}), 200
        return jsonify({"message": "You're already subscribed!", "subscriber": existing.to_dict()}), 200

    subscriber = Subscriber(
        id=generate_uuid(),
        email=email,
        name=name or None,
        source=source,
        list_name=list_name,
    )
    db.session.add(subscriber)
    db.session.commit()

    logger.info("New subscriber: %s (source: %s, list: %s)", email, source, list_name)

    return jsonify({"message": "Subscribed!", "subscriber": subscriber.to_dict()}), 201


@subscribe_bp.route("/unsubscribe", methods=["POST"])
def unsubscribe():
    """Unsubscribe an email address.

    Body JSON:
        email: str (required)
    """
    data = request.get_json(force=True) if request.is_json else {}
    email = (data.get("email") or "").strip().lower()

    if not email:
        return jsonify({"error": "Email is required"}), 400

    subscriber = Subscriber.query.filter_by(email=email).first()
    if subscriber:
        subscriber.status = "unsubscribed"
        db.session.commit()

    # Always return success (don't leak whether email exists)
    return jsonify({"message": "Unsubscribed successfully"}), 200
