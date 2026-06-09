"""
Promo Code / Coupon API routes for Umuve.
Public: validate a promo code.
Admin: CRUD promo codes.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timezone

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, User, PromoCode, PromoRedemption, generate_uuid, utcnow
from auth_routes import require_auth, require_admin

promos_bp = Blueprint("promos", __name__)


# ---------------------------------------------------------------------------
# Helper: compute discount for a given promo code + order amount
# ---------------------------------------------------------------------------
def compute_discount(promo, order_amount):
    """Return the discount amount for a promo code applied to an order.

    Parameters
    ----------
    promo : PromoCode
    order_amount : float

    Returns
    -------
    float
    """
    if promo.discount_type == "fixed":
        discount = promo.discount_value
    else:
        # percentage
        discount = round(order_amount * (promo.discount_value / 100.0), 2)
        if promo.max_discount is not None:
            discount = min(discount, promo.max_discount)

    # Discount should never exceed the order amount
    discount = min(discount, order_amount)
    return round(discount, 2)


# ---------------------------------------------------------------------------
# Helper: validate a promo code and return error or (promo, discount)
# ---------------------------------------------------------------------------
def validate_promo_code(code, order_amount, user_id=None, email=None):
    """Validate a promo code string against business rules.

    Parameters
    ----------
    code : str
    order_amount : float
    user_id, email : optional caller identity. When supplied, enforce the
        per-customer redemption cap (``promo.per_user_limit``). When both are
        ``None`` (e.g. the anonymous ``/api/promos/validate`` preview call) the
        per-customer check is skipped — the global cap still applies.

    Returns
    -------
    (promo, discount, None) on success, or (None, 0, error_message) on failure.
    """
    promo = PromoCode.query.filter(
        db.func.upper(PromoCode.code) == code.strip().upper()
    ).first()

    if not promo:
        return None, 0, "Promo code not found."

    if not promo.is_active:
        return None, 0, "This promo code is no longer active."

    if promo.expires_at:
        now = datetime.now(timezone.utc)
        expires = promo.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if now > expires:
            return None, 0, "This promo code has expired."

    if promo.max_uses is not None and promo.use_count >= promo.max_uses:
        return None, 0, "This promo code has reached its usage limit."

    # --- Per-customer cap (only when we know who is redeeming) ---
    per_user_limit = getattr(promo, "per_user_limit", None)
    if per_user_limit is not None and (user_id or email):
        email_norm = (email or "").strip().lower() or None
        ident = []
        if user_id:
            ident.append(PromoRedemption.user_id == user_id)
        if email_norm:
            ident.append(PromoRedemption.email == email_norm)
        used = PromoRedemption.query.filter(
            PromoRedemption.promo_code_id == promo.id,
            PromoRedemption.status == "confirmed",
            db.or_(*ident),
        ).count()
        if used >= per_user_limit:
            return None, 0, "You've already used this promo code."

    if promo.min_order_amount and order_amount < promo.min_order_amount:
        return None, 0, "Minimum order of ${:.2f} required for this promo code.".format(
            promo.min_order_amount
        )

    discount = compute_discount(promo, order_amount)
    return promo, discount, None


def confirm_promo_redemption(job):
    """Mark a job's reserved promo redemption as confirmed and bump use_count.

    Called once a payment succeeds (job -> "confirmed"). Idempotent: a second
    call for the same job is a no-op. Counting usage here — rather than at
    booking creation — means abandoned/unpaid bookings never burn a code, and
    the global ``use_count`` reflects only paid redemptions.
    """
    if job is None:
        return
    redemption = PromoRedemption.query.filter_by(
        job_id=job.id, status="reserved"
    ).first()
    if not redemption:
        return
    redemption.status = "confirmed"
    redemption.redeemed_at = utcnow()
    promo = db.session.get(PromoCode, redemption.promo_code_id)
    if promo is not None:
        promo.use_count = (promo.use_count or 0) + 1


# ============================================================================
# PUBLIC: Validate promo code
# ============================================================================

@promos_bp.route("/api/promos/validate", methods=["POST"])
def validate():
    """Validate a promo code and return the discount details.

    Body JSON:
        code: str
        order_amount: float
    """
    data = request.get_json() or {}
    code = data.get("code", "").strip()
    order_amount = data.get("order_amount", 0)

    if not code:
        return jsonify({"error": "Promo code is required."}), 400

    try:
        order_amount = float(order_amount)
    except (TypeError, ValueError):
        return jsonify({"error": "order_amount must be a number."}), 400

    promo, discount, error = validate_promo_code(code, order_amount)

    if error:
        return jsonify({"valid": False, "error": error}), 400

    return jsonify({
        "valid": True,
        "promo": {
            "id": promo.id,
            "code": promo.code,
            "discount_type": promo.discount_type,
            "discount_value": promo.discount_value,
            "max_discount": promo.max_discount,
            "min_order_amount": promo.min_order_amount or 0.0,
        },
        "discount_amount": discount,
        "new_total": round(order_amount - discount, 2),
    }), 200


# ============================================================================
# ADMIN: List promo codes
# ============================================================================

@promos_bp.route("/api/admin/promos", methods=["GET"])
@require_admin
def list_promos(user_id):
    """List all promo codes (active and inactive)."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)

    query = PromoCode.query.order_by(PromoCode.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "success": True,
        "promos": [p.to_dict() for p in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    }), 200


# ============================================================================
# ADMIN: Create promo code
# ============================================================================

@promos_bp.route("/api/admin/promos", methods=["POST"])
@require_admin
def create_promo(user_id):
    """Create a new promo code.

    Body JSON:
        code: str
        discount_type: "percentage" | "fixed"
        discount_value: float
        min_order_amount: float (optional, default 0)
        max_discount: float (optional, null = no cap)
        max_uses: int (optional, null = unlimited global cap)
        per_user_limit: int (optional, default 1; null = unlimited per customer)
        expires_at: str (optional ISO datetime)
        is_active: bool (optional, default true)
    """
    data = request.get_json() or {}

    code = data.get("code", "").strip().upper()
    if not code:
        return jsonify({"error": "code is required."}), 400

    discount_type = data.get("discount_type", "").strip().lower()
    if discount_type not in ("percentage", "fixed"):
        return jsonify({"error": "discount_type must be 'percentage' or 'fixed'."}), 400

    discount_value = data.get("discount_value")
    if discount_value is None:
        return jsonify({"error": "discount_value is required."}), 400
    try:
        discount_value = float(discount_value)
        if discount_value <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({"error": "discount_value must be a positive number."}), 400

    # Check uniqueness
    existing = PromoCode.query.filter(
        db.func.upper(PromoCode.code) == code
    ).first()
    if existing:
        return jsonify({"error": "A promo code with this code already exists."}), 409

    # Parse optional expires_at
    expires_at = None
    expires_str = data.get("expires_at")
    if expires_str:
        try:
            expires_at = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return jsonify({"error": "Invalid expires_at format. Use ISO 8601."}), 400

    promo = PromoCode(
        id=generate_uuid(),
        code=code,
        discount_type=discount_type,
        discount_value=discount_value,
        min_order_amount=float(data.get("min_order_amount", 0)),
        max_discount=float(data["max_discount"]) if data.get("max_discount") is not None else None,
        max_uses=int(data["max_uses"]) if data.get("max_uses") is not None else None,
        per_user_limit=(
            int(data["per_user_limit"]) if data.get("per_user_limit") is not None else 1
        ),
        expires_at=expires_at,
        is_active=data.get("is_active", True),
        created_by=user_id,
    )
    db.session.add(promo)
    db.session.commit()

    return jsonify({"success": True, "promo": promo.to_dict()}), 201


# ============================================================================
# ADMIN: Update promo code
# ============================================================================

@promos_bp.route("/api/admin/promos/<promo_id>", methods=["PUT"])
@require_admin
def update_promo(user_id, promo_id):
    """Update an existing promo code.

    Body JSON: same fields as create, all optional.
    """
    promo = db.session.get(PromoCode, promo_id)
    if not promo:
        return jsonify({"error": "Promo code not found."}), 404

    data = request.get_json() or {}

    if "code" in data:
        new_code = data["code"].strip().upper()
        if new_code != promo.code:
            existing = PromoCode.query.filter(
                db.func.upper(PromoCode.code) == new_code,
                PromoCode.id != promo.id,
            ).first()
            if existing:
                return jsonify({"error": "A promo code with this code already exists."}), 409
            promo.code = new_code

    if "discount_type" in data:
        dt = data["discount_type"].strip().lower()
        if dt not in ("percentage", "fixed"):
            return jsonify({"error": "discount_type must be 'percentage' or 'fixed'."}), 400
        promo.discount_type = dt

    if "discount_value" in data:
        try:
            dv = float(data["discount_value"])
            if dv <= 0:
                raise ValueError()
            promo.discount_value = dv
        except (TypeError, ValueError):
            return jsonify({"error": "discount_value must be a positive number."}), 400

    if "min_order_amount" in data:
        promo.min_order_amount = float(data["min_order_amount"])

    if "max_discount" in data:
        promo.max_discount = float(data["max_discount"]) if data["max_discount"] is not None else None

    if "max_uses" in data:
        promo.max_uses = int(data["max_uses"]) if data["max_uses"] is not None else None

    if "expires_at" in data:
        if data["expires_at"]:
            try:
                promo.expires_at = datetime.fromisoformat(
                    data["expires_at"].replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                return jsonify({"error": "Invalid expires_at format."}), 400
        else:
            promo.expires_at = None

    if "is_active" in data:
        promo.is_active = bool(data["is_active"])

    db.session.commit()

    return jsonify({"success": True, "promo": promo.to_dict()}), 200


# ============================================================================
# ADMIN: Deactivate (soft-delete) promo code
# ============================================================================

@promos_bp.route("/api/admin/promos/<promo_id>", methods=["DELETE"])
@require_admin
def deactivate_promo(user_id, promo_id):
    """Deactivate a promo code (soft delete)."""
    promo = db.session.get(PromoCode, promo_id)
    if not promo:
        return jsonify({"error": "Promo code not found."}), 404

    promo.is_active = False
    db.session.commit()

    return jsonify({"success": True, "promo": promo.to_dict()}), 200
