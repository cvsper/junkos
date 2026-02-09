"""
Admin API routes for JunkOS.
Protected by role-based access (admin only).
"""

from flask import Blueprint, request, jsonify
from functools import wraps
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from sqlalchemy import func

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Contractor, Job, Payment, PricingRule, SurgeZone, Notification,
    generate_uuid, utcnow,
)
from auth_routes import require_auth

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def require_admin(f):
    """Wrap require_auth and additionally check that the user has admin role."""
    @wraps(f)
    @require_auth
    def wrapper(user_id, *args, **kwargs):
        user = db.session.get(User, user_id)
        if not user or user.role != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(user_id=user_id, *args, **kwargs)
    return wrapper


@admin_bp.route("/dashboard", methods=["GET"])
@require_admin
def dashboard(user_id):
    """Aggregate dashboard statistics."""
    now = utcnow()
    thirty_days_ago = now - timedelta(days=30)

    total_jobs = Job.query.count()
    completed_jobs = Job.query.filter_by(status="completed").count()
    pending_jobs = Job.query.filter_by(status="pending").count()
    active_jobs = Job.query.filter(Job.status.in_(["accepted", "en_route", "arrived", "started"])).count()

    total_users = User.query.count()
    total_contractors = Contractor.query.count()
    approved_contractors = Contractor.query.filter_by(approval_status="approved").count()
    online_contractors = Contractor.query.filter_by(is_online=True, approval_status="approved").count()

    recent_payments = (
        Payment.query
        .filter(Payment.payment_status == "succeeded", Payment.created_at >= thirty_days_ago)
        .all()
    )
    revenue_30d = sum(p.amount for p in recent_payments)
    commission_30d = sum(p.commission for p in recent_payments)

    return jsonify({
        "success": True,
        "dashboard": {
            "total_jobs": total_jobs,
            "completed_jobs": completed_jobs,
            "pending_jobs": pending_jobs,
            "active_jobs": active_jobs,
            "total_users": total_users,
            "total_contractors": total_contractors,
            "approved_contractors": approved_contractors,
            "online_contractors": online_contractors,
            "revenue_30d": round(revenue_30d, 2),
            "commission_30d": round(commission_30d, 2),
        },
    }), 200


@admin_bp.route("/contractors", methods=["GET"])
@require_admin
def list_contractors(user_id):
    """List contractors with optional approval_status filter."""
    status_filter = request.args.get("status")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    query = Contractor.query
    if status_filter:
        query = query.filter_by(approval_status=status_filter)

    pagination = query.order_by(Contractor.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "success": True,
        "contractors": [c.to_dict() for c in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    }), 200


@admin_bp.route("/contractors/<contractor_id>/approve", methods=["PUT"])
@require_admin
def approve_contractor(user_id, contractor_id):
    """Approve a contractor application."""
    contractor = db.session.get(Contractor, contractor_id)
    if not contractor:
        return jsonify({"error": "Contractor not found"}), 404

    contractor.approval_status = "approved"
    contractor.updated_at = utcnow()

    notification = Notification(
        id=generate_uuid(),
        user_id=contractor.user_id,
        type="system",
        title="Application Approved",
        body="Your contractor application has been approved. You can now go online and accept jobs.",
        data={"approval_status": "approved"},
    )
    db.session.add(notification)
    db.session.commit()

    return jsonify({"success": True, "contractor": contractor.to_dict()}), 200


@admin_bp.route("/contractors/<contractor_id>/suspend", methods=["PUT"])
@require_admin
def suspend_contractor(user_id, contractor_id):
    """Suspend a contractor."""
    contractor = db.session.get(Contractor, contractor_id)
    if not contractor:
        return jsonify({"error": "Contractor not found"}), 404

    contractor.approval_status = "suspended"
    contractor.is_online = False
    contractor.updated_at = utcnow()

    notification = Notification(
        id=generate_uuid(),
        user_id=contractor.user_id,
        type="system",
        title="Account Suspended",
        body="Your contractor account has been suspended. Please contact support.",
        data={"approval_status": "suspended"},
    )
    db.session.add(notification)
    db.session.commit()

    return jsonify({"success": True, "contractor": contractor.to_dict()}), 200


@admin_bp.route("/jobs", methods=["GET"])
@require_admin
def list_jobs(user_id):
    """List all jobs with optional status filter."""
    status_filter = request.args.get("status")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    query = Job.query
    if status_filter:
        query = query.filter_by(status=status_filter)

    pagination = query.order_by(Job.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "success": True,
        "jobs": [j.to_dict() for j in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    }), 200


@admin_bp.route("/pricing/rules", methods=["PUT"])
@require_admin
def update_pricing_rules(user_id):
    """
    Bulk upsert pricing rules.
    Body JSON: rules (list of dicts with item_type, base_price, description, is_active)
    """
    data = request.get_json() or {}
    rules_data = data.get("rules", [])

    if not isinstance(rules_data, list):
        return jsonify({"error": "rules must be a list"}), 400

    updated = []
    for r in rules_data:
        item_type = r.get("item_type")
        if not item_type:
            continue

        rule = PricingRule.query.filter_by(item_type=item_type).first()
        if rule:
            if "base_price" in r:
                rule.base_price = float(r["base_price"])
            if "description" in r:
                rule.description = r["description"]
            if "is_active" in r:
                rule.is_active = bool(r["is_active"])
            rule.updated_at = utcnow()
        else:
            base_price = r.get("base_price")
            if base_price is None:
                continue
            rule = PricingRule(
                id=generate_uuid(),
                item_type=item_type,
                base_price=float(base_price),
                description=r.get("description"),
                is_active=r.get("is_active", True),
            )
            db.session.add(rule)
        updated.append(rule)

    db.session.commit()
    return jsonify({"success": True, "rules": [r.to_dict() for r in updated]}), 200


@admin_bp.route("/pricing/surge", methods=["POST"])
@require_admin
def upsert_surge_zone(user_id):
    """
    Create or update a surge zone.
    Body JSON: id (opt), name, boundary, surge_multiplier, is_active, start_time, end_time, days_of_week
    """
    data = request.get_json() or {}

    zone_id = data.get("id")
    if zone_id:
        zone = db.session.get(SurgeZone, zone_id)
        if not zone:
            return jsonify({"error": "Surge zone not found"}), 404
    else:
        zone = SurgeZone(id=generate_uuid())
        db.session.add(zone)

    if "name" in data:
        zone.name = data["name"]
    if "boundary" in data:
        zone.boundary = data["boundary"]
    if "surge_multiplier" in data:
        zone.surge_multiplier = float(data["surge_multiplier"])
    if "is_active" in data:
        zone.is_active = bool(data["is_active"])
    if "start_time" in data:
        zone.start_time = data["start_time"]
    if "end_time" in data:
        zone.end_time = data["end_time"]
    if "days_of_week" in data:
        zone.days_of_week = data["days_of_week"]

    zone.updated_at = utcnow()
    db.session.commit()

    return jsonify({"success": True, "surge_zone": zone.to_dict()}), 200


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------

@admin_bp.route("/customers", methods=["GET"])
@require_admin
def list_customers(user_id):
    """List all users with role='customer', with computed job and spending stats."""
    search = request.args.get("search", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    query = User.query.filter_by(role="customer")

    if search:
        like_term = f"%{search}%"
        query = query.filter(
            db.or_(
                User.name.ilike(like_term),
                User.email.ilike(like_term),
            )
        )

    pagination = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    customers = []
    for user in pagination.items:
        user_data = user.to_dict()

        # Count total jobs for this customer
        total_jobs = Job.query.filter_by(customer_id=user.id).count()

        # Sum of payments for completed jobs
        total_spent_result = (
            db.session.query(func.coalesce(func.sum(Payment.amount), 0.0))
            .join(Job, Job.id == Payment.job_id)
            .filter(
                Job.customer_id == user.id,
                Job.status == "completed",
                Payment.payment_status == "succeeded",
            )
            .scalar()
        )

        user_data["total_jobs"] = total_jobs
        user_data["total_spent"] = round(float(total_spent_result), 2)
        customers.append(user_data)

    return jsonify({
        "success": True,
        "customers": customers,
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    }), 200


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@admin_bp.route("/analytics", methods=["GET"])
@require_admin
def analytics(user_id):
    """Return analytics data for admin dashboard charts."""
    now = utcnow()

    # -- jobs_by_day: last 30 days -------------------------------------------
    thirty_days_ago = now - timedelta(days=30)
    recent_jobs = (
        Job.query
        .filter(Job.created_at >= thirty_days_ago)
        .all()
    )
    jobs_day_map = defaultdict(int)
    for j in recent_jobs:
        if j.created_at:
            day_key = j.created_at.strftime("%Y-%m-%d")
            jobs_day_map[day_key] += 1

    jobs_by_day = []
    for offset in range(30):
        day = (now - timedelta(days=29 - offset)).strftime("%Y-%m-%d")
        jobs_by_day.append({"date": day, "count": jobs_day_map.get(day, 0)})

    # -- revenue_by_week: last 12 weeks --------------------------------------
    twelve_weeks_ago = now - timedelta(weeks=12)
    recent_payments = (
        Payment.query
        .filter(
            Payment.payment_status == "succeeded",
            Payment.created_at >= twelve_weeks_ago,
        )
        .all()
    )
    week_map = defaultdict(float)
    for p in recent_payments:
        if p.created_at:
            # ISO week start (Monday)
            week_start = p.created_at - timedelta(days=p.created_at.weekday())
            week_key = week_start.strftime("%Y-%m-%d")
            week_map[week_key] += p.amount

    revenue_by_week = []
    for w in range(12):
        ref = now - timedelta(weeks=11 - w)
        week_start = ref - timedelta(days=ref.weekday())
        week_key = week_start.strftime("%Y-%m-%d")
        revenue_by_week.append({
            "week_start": week_key,
            "revenue": round(week_map.get(week_key, 0.0), 2),
        })

    # -- jobs_by_status ------------------------------------------------------
    status_rows = (
        db.session.query(Job.status, func.count(Job.id))
        .group_by(Job.status)
        .all()
    )
    jobs_by_status = {status: count for status, count in status_rows}

    # -- top_contractors: top 5 by total_jobs completed ----------------------
    top_contractors_query = (
        Contractor.query
        .order_by(Contractor.total_jobs.desc())
        .limit(5)
        .all()
    )
    top_contractors = []
    for c in top_contractors_query:
        top_contractors.append({
            "id": c.id,
            "name": c.user.name if c.user else None,
            "total_jobs": c.total_jobs,
            "avg_rating": c.avg_rating,
        })

    # -- busiest_hours: count of jobs by scheduled hour ----------------------
    busiest_hours = {h: 0 for h in range(24)}
    scheduled_jobs = Job.query.filter(Job.scheduled_at.isnot(None)).all()
    for j in scheduled_jobs:
        hour = j.scheduled_at.hour
        busiest_hours[hour] += 1

    busiest_hours_list = [
        {"hour": h, "count": busiest_hours[h]} for h in range(24)
    ]

    # -- avg_job_value: average total_price of completed jobs ----------------
    avg_val = (
        db.session.query(func.coalesce(func.avg(Job.total_price), 0.0))
        .filter(Job.status == "completed")
        .scalar()
    )
    avg_job_value = round(float(avg_val), 2)

    return jsonify({
        "success": True,
        "analytics": {
            "jobs_by_day": jobs_by_day,
            "revenue_by_week": revenue_by_week,
            "jobs_by_status": jobs_by_status,
            "top_contractors": top_contractors,
            "busiest_hours": busiest_hours_list,
            "avg_job_value": avg_job_value,
        },
    }), 200


# ---------------------------------------------------------------------------
# Pricing Rules (GET)
# ---------------------------------------------------------------------------

@admin_bp.route("/map-data", methods=["GET"])
@require_admin
def map_data(user_id):
    """Return online contractors and active jobs for the live map."""
    # Online approved contractors with a known location
    contractors = (
        Contractor.query
        .filter_by(is_online=True, approval_status="approved")
        .filter(Contractor.current_lat.isnot(None), Contractor.current_lng.isnot(None))
        .all()
    )
    contractor_points = []
    for c in contractors:
        contractor_points.append({
            "id": c.id,
            "name": c.user.name if c.user else None,
            "truck_type": c.truck_type,
            "avg_rating": c.avg_rating,
            "total_jobs": c.total_jobs,
            "lat": c.current_lat,
            "lng": c.current_lng,
        })

    # Active jobs (pending through started) with a known location
    active_statuses = ["pending", "accepted", "en_route", "arrived", "started"]
    jobs = (
        Job.query
        .filter(Job.status.in_(active_statuses))
        .filter(Job.lat.isnot(None), Job.lng.isnot(None))
        .all()
    )
    job_points = []
    for j in jobs:
        customer_name = None
        if j.customer:
            customer_name = j.customer.name
        job_points.append({
            "id": j.id,
            "address": j.address,
            "status": j.status,
            "lat": j.lat,
            "lng": j.lng,
            "customer_name": customer_name,
            "driver_id": j.driver_id,
            "total_price": j.total_price,
        })

    return jsonify({
        "success": True,
        "contractors": contractor_points,
        "jobs": job_points,
    }), 200


# ---------------------------------------------------------------------------
# Pricing Rules (GET)
# ---------------------------------------------------------------------------

@admin_bp.route("/jobs/<job_id>/assign", methods=["PUT"])
@require_admin
def assign_job(user_id, job_id):
    """Manually assign a contractor to a job."""
    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    data = request.get_json() or {}
    contractor_id = data.get("contractor_id")
    if not contractor_id:
        return jsonify({"error": "contractor_id is required"}), 400

    contractor = db.session.get(Contractor, contractor_id)
    if not contractor:
        return jsonify({"error": "Contractor not found"}), 404

    if contractor.approval_status != "approved":
        return jsonify({"error": "Contractor is not approved"}), 403

    job.driver_id = contractor.id
    if job.status in ("pending", "confirmed"):
        job.status = "assigned"
    job.updated_at = utcnow()

    # Notify driver
    notification = Notification(
        id=generate_uuid(),
        user_id=contractor.user_id,
        type="job_assigned",
        title="New Job Assigned",
        body="An admin has assigned you a job at {}.".format(job.address or "an address"),
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
    broadcast_job_status(job.id, job.status, {"driver_id": contractor.id})

    socketio.emit("job:assigned", {
        "job_id": job.id,
        "contractor_id": contractor.id,
        "contractor_name": contractor.user.name if contractor.user else None,
    }, room="driver:{}".format(contractor.id))

    socketio.emit("job:driver-assigned", {
        "job_id": job.id,
        "driver": {
            "id": contractor.id,
            "name": contractor.user.name if contractor.user else None,
            "truck_type": contractor.truck_type,
            "avg_rating": contractor.avg_rating,
            "total_jobs": contractor.total_jobs,
        },
    }, room=job.id)

    return jsonify({"success": True, "job": job.to_dict()}), 200


@admin_bp.route("/pricing/rules", methods=["GET"])
@require_admin
def list_pricing_rules(user_id):
    """List all pricing rules."""
    rules = PricingRule.query.order_by(PricingRule.item_type).all()
    return jsonify({
        "success": True,
        "rules": [r.to_dict() for r in rules],
    }), 200


# ---------------------------------------------------------------------------
# Surge Zones (GET)
# ---------------------------------------------------------------------------

@admin_bp.route("/pricing/surge", methods=["GET"])
@require_admin
def list_surge_zones(user_id):
    """List all surge zones."""
    zones = SurgeZone.query.order_by(SurgeZone.name).all()
    return jsonify({
        "success": True,
        "surge_zones": [z.to_dict() for z in zones],
    }), 200
