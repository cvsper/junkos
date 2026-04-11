"""
Partner registration API routes for Umuve.
Handles realtor partnership program signups from goumuve.com/partners/realtors.
"""

from flask import Blueprint, request, jsonify, redirect

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, Partner, generate_uuid, generate_referral_code

partners_bp = Blueprint("partners", __name__, url_prefix="/api/partners")

REDIRECT_BASE = "https://goumuve.com/partners/realtors"


@partners_bp.route("/register", methods=["POST"])
def register_partner():
    """Handle partner registration form submissions (form-encoded, not JSON)."""
    try:
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        brokerage = request.form.get("brokerage", "").strip() or None
        coverage_areas = request.form.getlist("coverage_area")

        # Validate required fields
        if not name or not email or not phone:
            return redirect(f"{REDIRECT_BASE}?error=missing-fields")

        # Check for duplicate email
        existing = Partner.query.filter_by(email=email).first()
        if existing:
            return redirect(f"{REDIRECT_BASE}?error=duplicate")

        partner = Partner(
            name=name,
            email=email,
            phone=phone,
            brokerage=brokerage,
            coverage_areas=coverage_areas if coverage_areas else None,
            partner_type="realtor",
        )

        db.session.add(partner)
        db.session.commit()

        return redirect(f"{REDIRECT_BASE}?success=1")

    except Exception as e:
        db.session.rollback()
        print(f"[partners] Registration error: {e}")
        return redirect(f"{REDIRECT_BASE}?error=server")


@partners_bp.route("/list", methods=["GET"])
def list_partners():
    """Admin endpoint to list all partners (no auth for now)."""
    try:
        partners = Partner.query.order_by(Partner.created_at.desc()).all()
        return jsonify([p.to_dict() for p in partners])
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@partners_bp.route("/<partner_id>", methods=["PATCH"])
def update_partner(partner_id):
    """Update partner status or details."""
    try:
        partner = db.session.get(Partner, partner_id)
        if not partner:
            return jsonify({"error": "Partner not found"}), 404

        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Update status
        if "status" in data:
            new_status = data["status"]
            if new_status not in ("pending", "approved", "rejected"):
                return jsonify({"error": "Invalid status"}), 400
            
            partner.status = new_status
            
            # If approved, ensure they have a referral code
            if new_status == "approved" and not partner.referral_code:
                # Ensure uniqueness
                for _ in range(10):
                    code = generate_referral_code()
                    existing = Partner.query.filter_by(referral_code=code).first()
                    if not existing:
                        partner.referral_code = code
                        break

        db.session.commit()
        return jsonify(partner.to_dict()), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
