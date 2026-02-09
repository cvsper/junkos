"""
Operator API routes for JunkOS.
Fleet managers who receive jobs from admin and delegate them to their contractors.
"""

import secrets
from flask import Blueprint, request, jsonify
from functools import wraps
from datetime import datetime, timezone, timedelta

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Contractor, Job, Payment, Notification, OperatorInvite,
    generate_uuid, utcnow,
)
from auth_routes import require_auth

operator_bp = Blueprint("operator", __name__, url_prefix="/api/operator")


def require_operator(f):
    """Wrap require_auth and check that the user is an operator."""
    @wraps(f)
    @require_auth
    def wrapper(user_id, *args, **kwargs):
        user = db.session.get(User, user_id)
        if not user or user.role != "operator":
            return jsonify({"error": "Operator access required"}), 403
        contractor = Contractor.query.filter_by(user_id=user_id).first()
        if not contractor or not contractor.is_operator:
            return jsonify({"error": "Operator access required"}), 403
        return f(user_id=user_id, operator=contractor, *args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@operator_bp.route("/dashboard", methods=["GET"])
@require_operator
def dashboard(user_id, operator):
    """Operator dashboard stats."""
    now = utcnow()
    thirty_days_ago = now - timedelta(days=30)

    fleet = Contractor.query.filter_by(operator_id=operator.id).all()
    fleet_ids = [c.id for c in fleet]
    fleet_size = len(fleet)
    online_count = sum(1 for c in fleet if c.is_online)

    pending_delegation = Job.query.filter_by(
        operator_id=operator.id, status="delegating"
    ).count()

    # 30d earnings from commission on fleet jobs
    earnings_30d = 0.0
    if fleet_ids:
        payments = (
            Payment.query
            .join(Job, Payment.job_id == Job.id)
            .filter(
                Job.operator_id == operator.id,
                Job.driver_id.in_(fleet_ids),
                Payment.payment_status == "succeeded",
                Payment.created_at >= thirty_days_ago,
            )
            .all()
        )
        earnings_30d = sum(p.operator_payout_amount or 0.0 for p in payments)

    return jsonify({
        "success": True,
        "dashboard": {
            "fleet_size": fleet_size,
            "online_count": online_count,
            "pending_delegation": pending_delegation,
            "earnings_30d": round(earnings_30d, 2),
        },
    }), 200


# ---------------------------------------------------------------------------
# Fleet Management
# ---------------------------------------------------------------------------

@operator_bp.route("/fleet", methods=["GET"])
@require_operator
def list_fleet(user_id, operator):
    """List fleet contractors."""
    fleet = Contractor.query.filter_by(operator_id=operator.id).all()

    contractors = []
    for c in fleet:
        contractors.append({
            "id": c.id,
            "name": c.user.name if c.user else None,
            "email": c.user.email if c.user else None,
            "truck_type": c.truck_type,
            "is_online": c.is_online,
            "avg_rating": c.avg_rating,
            "total_jobs": c.total_jobs,
            "approval_status": c.approval_status,
        })

    return jsonify({"success": True, "contractors": contractors}), 200


# ---------------------------------------------------------------------------
# Invite Codes
# ---------------------------------------------------------------------------

@operator_bp.route("/invites", methods=["POST"])
@require_operator
def create_invite(user_id, operator):
    """Create an invite code for a new fleet contractor."""
    data = request.get_json() or {}

    code = secrets.token_urlsafe(6)[:8].upper()
    invite = OperatorInvite(
        id=generate_uuid(),
        operator_id=operator.id,
        invite_code=code,
        email=data.get("email"),
        max_uses=int(data.get("max_uses", 1)),
        is_active=True,
    )

    expires_days = data.get("expires_days")
    if expires_days:
        invite.expires_at = utcnow() + timedelta(days=int(expires_days))

    db.session.add(invite)
    db.session.commit()

    return jsonify({"success": True, "invite": invite.to_dict()}), 201


@operator_bp.route("/invites", methods=["GET"])
@require_operator
def list_invites(user_id, operator):
    """List active invite codes."""
    invites = OperatorInvite.query.filter_by(
        operator_id=operator.id, is_active=True
    ).order_by(OperatorInvite.created_at.desc()).all()

    return jsonify({
        "success": True,
        "invites": [i.to_dict() for i in invites],
    }), 200


@operator_bp.route("/invites/<invite_id>", methods=["DELETE"])
@require_operator
def revoke_invite(user_id, operator, invite_id):
    """Revoke an invite code."""
    invite = db.session.get(OperatorInvite, invite_id)
    if not invite or invite.operator_id != operator.id:
        return jsonify({"error": "Invite not found"}), 404

    invite.is_active = False
    db.session.commit()

    return jsonify({"success": True}), 200


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

@operator_bp.route("/jobs", methods=["GET"])
@require_operator
def list_jobs(user_id, operator):
    """List jobs for this operator, filterable by status group."""
    status_filter = request.args.get("filter", "all")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    query = Job.query.filter_by(operator_id=operator.id)

    if status_filter == "delegating":
        query = query.filter_by(status="delegating")
    elif status_filter == "active":
        query = query.filter(Job.status.in_(["assigned", "accepted", "en_route", "arrived", "started"]))
    elif status_filter == "completed":
        query = query.filter_by(status="completed")

    pagination = query.order_by(Job.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    jobs = []
    for j in pagination.items:
        job_data = j.to_dict()
        # Include driver name if assigned
        if j.driver_id and j.driver:
            job_data["driver_name"] = j.driver.user.name if j.driver.user else None
        else:
            job_data["driver_name"] = None
        # Include customer name
        if j.customer:
            job_data["customer_name"] = j.customer.name
            job_data["customer_email"] = j.customer.email
        jobs.append(job_data)

    return jsonify({
        "success": True,
        "jobs": jobs,
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    }), 200


@operator_bp.route("/jobs/<job_id>/delegate", methods=["PUT"])
@require_operator
def delegate_job(user_id, operator, job_id):
    """Delegate a job to a fleet contractor."""
    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.operator_id != operator.id:
        return jsonify({"error": "Job does not belong to your fleet"}), 403

    if job.status != "delegating":
        return jsonify({"error": "Job is not in delegating status"}), 409

    data = request.get_json() or {}
    contractor_id = data.get("contractor_id")
    if not contractor_id:
        return jsonify({"error": "contractor_id is required"}), 400

    contractor = db.session.get(Contractor, contractor_id)
    if not contractor:
        return jsonify({"error": "Contractor not found"}), 404

    if contractor.operator_id != operator.id:
        return jsonify({"error": "Contractor is not in your fleet"}), 403

    if contractor.approval_status != "approved":
        return jsonify({"error": "Contractor is not approved"}), 403

    job.driver_id = contractor.id
    job.status = "assigned"
    job.delegated_at = utcnow()
    job.updated_at = utcnow()

    # Notify the fleet contractor
    notification = Notification(
        id=generate_uuid(),
        user_id=contractor.user_id,
        type="job_assigned",
        title="New Job Assigned",
        body="Your operator has assigned you a job at {}.".format(job.address or "an address"),
        data={"job_id": job.id, "address": job.address, "total_price": job.total_price},
    )
    db.session.add(notification)

    # Notify customer
    notification_cust = Notification(
        id=generate_uuid(),
        user_id=job.customer_id,
        type="job_update",
        title="Driver Assigned",
        body="A driver has been assigned to your job.",
        data={"job_id": job.id, "status": "assigned"},
    )
    db.session.add(notification_cust)
    db.session.commit()

    # Broadcast via SocketIO
    from socket_events import broadcast_job_status, socketio
    broadcast_job_status(job.id, "assigned", {"driver_id": contractor.id})

    socketio.emit("job:assigned", {
        "job_id": job.id,
        "contractor_id": contractor.id,
        "contractor_name": contractor.user.name if contractor.user else None,
    }, room="driver:{}".format(contractor.id))

    return jsonify({"success": True, "job": job.to_dict()}), 200


# ---------------------------------------------------------------------------
# Earnings
# ---------------------------------------------------------------------------

@operator_bp.route("/earnings", methods=["GET"])
@require_operator
def earnings(user_id, operator):
    """Operator commission earnings."""
    now = utcnow()
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)

    fleet = Contractor.query.filter_by(operator_id=operator.id).all()
    fleet_ids = [c.id for c in fleet]

    if not fleet_ids:
        return jsonify({
            "success": True,
            "earnings": {
                "total": 0.0,
                "earnings_30d": 0.0,
                "earnings_7d": 0.0,
                "per_contractor": [],
            },
        }), 200

    all_payments = (
        Payment.query
        .join(Job, Payment.job_id == Job.id)
        .filter(
            Job.operator_id == operator.id,
            Job.driver_id.in_(fleet_ids),
            Payment.payment_status == "succeeded",
        )
        .all()
    )

    total = sum(p.operator_payout_amount or 0.0 for p in all_payments)
    e_30d = sum(
        p.operator_payout_amount or 0.0 for p in all_payments
        if p.created_at and p.created_at >= thirty_days_ago
    )
    e_7d = sum(
        p.operator_payout_amount or 0.0 for p in all_payments
        if p.created_at and p.created_at >= seven_days_ago
    )

    # Per-contractor breakdown
    contractor_map = {c.id: c for c in fleet}
    per_contractor = {}
    for p in all_payments:
        job = db.session.get(Job, p.job_id)
        if job and job.driver_id:
            if job.driver_id not in per_contractor:
                c = contractor_map.get(job.driver_id)
                per_contractor[job.driver_id] = {
                    "contractor_id": job.driver_id,
                    "name": c.user.name if c and c.user else None,
                    "commission": 0.0,
                    "jobs": 0,
                }
            per_contractor[job.driver_id]["commission"] += p.operator_payout_amount or 0.0
            per_contractor[job.driver_id]["jobs"] += 1

    return jsonify({
        "success": True,
        "earnings": {
            "total": round(total, 2),
            "earnings_30d": round(e_30d, 2),
            "earnings_7d": round(e_7d, 2),
            "per_contractor": list(per_contractor.values()),
        },
    }), 200
