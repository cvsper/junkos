"""
Referral API routes for Umuve.
Allows customers to share referral codes and track referral rewards.
Also handles hauler-to-hauler (contractor) referrals — supply growth.
"""

import os
import logging

from flask import Blueprint, jsonify, request

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, User, Contractor, Referral, generate_referral_code, utcnow
from auth_routes import require_auth

logger = logging.getLogger(__name__)

referrals_bp = Blueprint("referrals", __name__, url_prefix="/api/referrals")

# Bonus paid to BOTH the referring hauler and the new hauler once the new
# hauler completes their first job. Env-tunable per market.
try:
    CONTRACTOR_REFERRAL_BONUS = float(os.environ.get("CONTRACTOR_REFERRAL_BONUS", "100.0"))
except (TypeError, ValueError):
    CONTRACTOR_REFERRAL_BONUS = 100.0


@referrals_bp.route("/my-code", methods=["GET"])
@require_auth
def get_my_code(user_id):
    """Get the current user's referral code.

    If the user does not yet have a referral code, generate one.
    """
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Generate referral code on the fly if the user doesn't have one
    if not user.referral_code:
        # Ensure uniqueness
        for _ in range(10):
            code = generate_referral_code()
            existing = User.query.filter_by(referral_code=code).first()
            if not existing:
                user.referral_code = code
                db.session.commit()
                break
        else:
            return jsonify({"error": "Failed to generate unique referral code"}), 500

    # Include rollup stats so clients can render the referral card in a single
    # request (avoids a second round-trip to /stats just to populate counts).
    referrals = Referral.query.filter_by(referrer_id=user_id).all()
    total_referrals = len(referrals)
    credits_earned = round(
        sum(r.reward_amount for r in referrals if r.status in ("completed", "rewarded")),
        2,
    )

    return jsonify({
        "success": True,
        "referral_code": user.referral_code,
        "share_url": "/book?ref={}".format(user.referral_code),
        "total_referrals": total_referrals,
        "credits_earned": credits_earned,
    }), 200


@referrals_bp.route("/stats", methods=["GET"])
@require_auth
def get_referral_stats(user_id):
    """Get referral statistics for the current user.

    Returns total referred, completed, and total earned.
    """
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    referrals = Referral.query.filter_by(referrer_id=user_id).all()

    total_referred = len(referrals)
    signed_up = sum(1 for r in referrals if r.status in ("signed_up", "completed", "rewarded"))
    completed = sum(1 for r in referrals if r.status in ("completed", "rewarded"))
    total_earned = sum(r.reward_amount for r in referrals if r.status in ("completed", "rewarded"))

    return jsonify({
        "success": True,
        "stats": {
            "total_referred": total_referred,
            "signed_up": signed_up,
            "completed": completed,
            "total_earned": round(total_earned, 2),
            "reward_per_referral": 10.00,
        },
        "referrals": [r.to_dict() for r in referrals],
    }), 200


@referrals_bp.route("/contractor/apply", methods=["POST"])
@require_auth
def apply_contractor_referral(user_id):
    """A new hauler claims they were referred by an existing hauler.

    Called during driver onboarding with {"referral_code": "XXXXXXXX"}. Creates
    a 'contractor'-type Referral in 'signed_up' status; it completes (and pays
    both parties the CONTRACTOR_REFERRAL_BONUS) on the new hauler's first
    completed job. Idempotent — a hauler can only be referred once.
    """
    data = request.get_json() or {}
    code = (data.get("referral_code") or "").strip().upper()
    if not code or len(code) != 8:
        return jsonify({"error": "A valid 8-character referral code is required"}), 400

    referrer = User.query.filter_by(referral_code=code).first()
    if not referrer:
        return jsonify({"error": "Referral code not found"}), 404
    if referrer.id == user_id:
        return jsonify({"error": "You can't refer yourself"}), 400

    # The referrer must themselves be an approved hauler (real supply, not a
    # rider's customer code being reused to farm bonuses).
    referrer_contractor = Contractor.query.filter_by(user_id=referrer.id).first()
    if not referrer_contractor or referrer_contractor.approval_status != "approved":
        return jsonify({"error": "That code doesn't belong to an active hauler"}), 400

    # One referral per new hauler, regardless of type.
    existing = Referral.query.filter_by(referee_id=user_id).first()
    if existing:
        return jsonify({
            "error": "You've already been credited to a referrer",
            "referral": existing.to_dict(),
        }), 409

    referral = Referral(
        referrer_id=referrer.id,
        referee_id=user_id,
        referral_code=code,
        status="signed_up",
        reward_amount=CONTRACTOR_REFERRAL_BONUS,
        referral_type="contractor",
    )
    db.session.add(referral)
    db.session.commit()

    logger.info(
        "Contractor referral created: referrer=%s referee=%s bonus=$%.2f",
        referrer.id, user_id, CONTRACTOR_REFERRAL_BONUS,
    )
    return jsonify({
        "success": True,
        "message": (
            "You're linked to {}. You both earn ${:.0f} after your first "
            "completed job."
        ).format((referrer.name or "your referrer").split()[0], CONTRACTOR_REFERRAL_BONUS),
        "referral": referral.to_dict(),
    }), 201


@referrals_bp.route("/validate/<code>", methods=["POST"])
def validate_referral_code(code):
    """Validate a referral code and return the referrer's name.

    This endpoint is public (no auth required) so new users can
    verify a referral code before signing up.
    """
    if not code or len(code) != 8:
        return jsonify({"error": "Invalid referral code"}), 400

    referrer = User.query.filter_by(referral_code=code.upper()).first()
    if not referrer:
        return jsonify({"error": "Referral code not found"}), 404

    # Mask the name for privacy (show first name + last initial)
    display_name = referrer.name or "An Umuve user"
    parts = display_name.strip().split()
    if len(parts) >= 2:
        display_name = "{} {}.".format(parts[0], parts[-1][0])
    elif len(parts) == 1:
        display_name = parts[0]

    return jsonify({
        "success": True,
        "referrer_name": display_name,
        "referral_code": referrer.referral_code,
    }), 200
