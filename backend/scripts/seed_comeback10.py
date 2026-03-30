"""
Seed the COMEBACK10 promo code (10% off, $50 cap, unlimited uses, no expiration).

Usage:
    python scripts/seed_comeback10.py
"""

import sys
import os

# Ensure the backend package is importable when running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server import app
from models import db, PromoCode, generate_uuid


def seed():
    with app.app_context():
        existing = PromoCode.query.filter_by(code="COMEBACK10").first()
        if existing:
            print("COMEBACK10 already exists (id=%s). Skipping." % existing.id)
            return

        promo = PromoCode(
            id=generate_uuid(),
            code="COMEBACK10",
            discount_type="percentage",
            discount_value=10.0,
            max_discount=50.0,
            max_uses=None,
            is_active=True,
        )
        db.session.add(promo)
        db.session.commit()
        print("Created COMEBACK10 promo code (id=%s)." % promo.id)


if __name__ == "__main__":
    seed()
