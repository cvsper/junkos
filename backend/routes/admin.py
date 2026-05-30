"""
Admin API routes for Umuve.
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
    PricingConfig, Review, Rating, DeviceToken, AbandonedBooking,
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

    type_filter = request.args.get("type")

    query = Contractor.query
    if status_filter:
        query = query.filter_by(approval_status=status_filter)
    if type_filter == "operator":
        query = query.filter_by(is_operator=True)
    elif type_filter == "fleet":
        query = query.filter(Contractor.operator_id.isnot(None), Contractor.is_operator == False)
    elif type_filter == "independent":
        query = query.filter(Contractor.operator_id.is_(None), Contractor.is_operator == False)

    pagination = query.order_by(Contractor.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

    contractors = []
    for c in pagination.items:
        c_data = c.to_dict()
        # Flatten user fields to the top level so the admin frontend can
        # access name / email / phone directly (instead of c.user.name etc.)
        user_obj = c_data.pop("user", None) or {}
        c_data["name"] = user_obj.get("name")
        c_data["email"] = user_obj.get("email")
        c_data["phone"] = user_obj.get("phone")
        # Frontend expects "rating" but the model stores "avg_rating"
        c_data["rating"] = c_data.get("avg_rating")
        # Add operator name for fleet contractors
        if c.operator_id and c.operator:
            c_data["operator_name"] = c.operator.user.name if c.operator.user else None
        else:
            c_data["operator_name"] = None
        # Add fleet size for operators
        if c.is_operator:
            c_data["fleet_size"] = Contractor.query.filter_by(operator_id=c.id).count()
        else:
            c_data["fleet_size"] = 0
        contractors.append(c_data)

    return jsonify({
        "success": True,
        "contractors": contractors,
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


@admin_bp.route("/contractors/<contractor_id>/promote-operator", methods=["PUT"])
@require_admin
def promote_contractor_to_operator(user_id, contractor_id):
    """Promote a contractor to operator status."""
    contractor = db.session.get(Contractor, contractor_id)
    if not contractor:
        return jsonify({"error": "Contractor not found"}), 404

    if contractor.is_operator:
        return jsonify({"error": "Contractor is already an operator"}), 409

    contractor.is_operator = True
    contractor.updated_at = utcnow()

    # Update the associated user role to operator
    user = db.session.get(User, contractor.user_id)
    if user:
        user.role = "operator"

    notification = Notification(
        id=generate_uuid(),
        user_id=contractor.user_id,
        type="system",
        title="Promoted to Operator",
        body="You have been promoted to operator status. You can now manage a fleet of contractors.",
        data={"is_operator": True},
    )
    db.session.add(notification)
    db.session.commit()

    return jsonify({"success": True, "contractor": contractor.to_dict()}), 200


@admin_bp.route("/jobs", methods=["GET"])
@require_admin
def list_jobs(user_id):
    """List all jobs with search, status filter, and date range."""
    status_filter = request.args.get("status")
    search = request.args.get("search", "").strip()
    city = request.args.get("city", "").strip()
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    single_date = request.args.get("date")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page") or request.args.get("limit") or 20
    per_page = int(per_page)

    query = Job.query
    if status_filter:
        query = query.filter_by(status=status_filter)

    if search:
        like_term = f"%{search}%"
        query = query.join(User, Job.customer_id == User.id).filter(
            db.or_(
                User.name.ilike(like_term),
                User.email.ilike(like_term),
                Job.address.ilike(like_term),
                Job.id.ilike(like_term),
                Job.confirmation_code.ilike(like_term),
            )
        )

    if city:
        query = query.filter(Job.address.ilike(f"%{city}%"))

    if single_date and not date_from and not date_to:
        try:
            from_dt = datetime.fromisoformat(single_date + "T00:00:00")
            to_dt = datetime.fromisoformat(single_date + "T23:59:59")
            query = query.filter(Job.created_at >= from_dt, Job.created_at <= to_dt)
        except (ValueError, TypeError):
            pass
    else:
        if date_from:
            try:
                from_dt = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
                query = query.filter(Job.created_at >= from_dt)
            except (ValueError, TypeError):
                pass

        if date_to:
            try:
                to_dt = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
                query = query.filter(Job.created_at <= to_dt)
            except (ValueError, TypeError):
                pass

    pagination = query.order_by(Job.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

    jobs_data = []
    for j in pagination.items:
        jd = j.to_dict()
        jd["customer_name"] = j.customer.name if j.customer else None
        jd["customer_email"] = j.customer.email if j.customer else None
        jobs_data.append(jd)

    return jsonify({
        "success": True,
        "jobs": jobs_data,
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    }), 200


@admin_bp.route("/jobs/<job_id>", methods=["GET"])
@require_admin
def get_job_detail(user_id, job_id):
    """Return full job detail including proof photos, payment, driver, and customer info."""
    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    job_data = job.to_dict()

    # Include customer info
    if job.customer:
        job_data["customer"] = job.customer.to_dict()
    else:
        job_data["customer"] = None

    # Include driver/contractor info
    if job.driver:
        driver_data = job.driver.to_dict()
        job_data["driver"] = driver_data
    else:
        job_data["driver"] = None

    # Include operator info
    if job.operator_rel:
        job_data["operator"] = job.operator_rel.to_dict()
    else:
        job_data["operator"] = None

    # Include payment info
    if job.payment:
        job_data["payment"] = job.payment.to_dict()
    else:
        job_data["payment"] = None

    # Include rating info
    if job.rating:
        job_data["rating"] = job.rating.to_dict()
    else:
        job_data["rating"] = None

    return jsonify({"success": True, "job": job_data}), 200


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


@admin_bp.route("/funnel", methods=["GET"])
@require_admin
def conversion_funnel(user_id):
    """Conversion funnel: where demand leaks on its way to revenue.

    Query param ?days=N (default 30) sets the window. Stages:
        started  -> booking_created -> paid -> assigned -> completed
    'started' = booking forms begun = abandoned (didn't finish) + jobs created.
    Also returns per-stage drop-off %, abandoned-recovery rate, and a
    lead_source breakdown so sevs can see which channels actually convert.
    """
    try:
        days = request.args.get("days", default=30, type=int) or 30
        days = max(1, min(days, 365))
    except Exception:
        days = 30
    since = utcnow() - timedelta(days=days)

    # --- Stage counts (all scoped to the window) ---
    abandoned = (
        db.session.query(func.count(AbandonedBooking.id))
        .filter(AbandonedBooking.created_at >= since)
        .scalar()
    ) or 0
    abandoned_recovered = (
        db.session.query(func.count(AbandonedBooking.id))
        .filter(AbandonedBooking.created_at >= since,
                AbandonedBooking.converted.is_(True))
        .scalar()
    ) or 0

    jobs_created = (
        db.session.query(func.count(Job.id))
        .filter(Job.created_at >= since)
        .scalar()
    ) or 0

    paid = (
        db.session.query(func.count(func.distinct(Payment.job_id)))
        .filter(Payment.created_at >= since,
                Payment.payment_status == "succeeded")
        .scalar()
    ) or 0

    assigned = (
        db.session.query(func.count(Job.id))
        .filter(Job.created_at >= since, Job.driver_id.isnot(None))
        .scalar()
    ) or 0

    completed = (
        db.session.query(func.count(Job.id))
        .filter(Job.created_at >= since, Job.status == "completed")
        .scalar()
    ) or 0

    started = abandoned + jobs_created

    def _rate(num, denom):
        return round(100.0 * num / denom, 1) if denom else 0.0

    funnel = [
        {"stage": "started", "count": started, "label": "Booking form started"},
        {"stage": "booking_created", "count": jobs_created,
         "label": "Completed booking form", "from_prev_pct": _rate(jobs_created, started)},
        {"stage": "paid", "count": paid,
         "label": "Payment succeeded", "from_prev_pct": _rate(paid, jobs_created)},
        {"stage": "assigned", "count": assigned,
         "label": "Hauler assigned", "from_prev_pct": _rate(assigned, paid)},
        {"stage": "completed", "count": completed,
         "label": "Job completed", "from_prev_pct": _rate(completed, assigned)},
    ]

    # --- Biggest leak (largest absolute drop between adjacent stages) ---
    biggest_leak = None
    worst_drop = -1
    for i in range(1, len(funnel)):
        drop = funnel[i - 1]["count"] - funnel[i]["count"]
        if drop > worst_drop:
            worst_drop = drop
            biggest_leak = {
                "between": "{} -> {}".format(funnel[i - 1]["stage"], funnel[i]["stage"]),
                "lost": drop,
                "kept_pct": funnel[i].get("from_prev_pct", 0.0),
            }

    # --- Lead-source breakdown (created vs completed vs revenue) ---
    src_created = dict(
        db.session.query(func.coalesce(Job.lead_source, "unknown"), func.count(Job.id))
        .filter(Job.created_at >= since)
        .group_by(Job.lead_source).all()
    )
    src_completed = dict(
        db.session.query(func.coalesce(Job.lead_source, "unknown"), func.count(Job.id))
        .filter(Job.created_at >= since, Job.status == "completed")
        .group_by(Job.lead_source).all()
    )
    src_revenue = dict(
        db.session.query(
            func.coalesce(Job.lead_source, "unknown"),
            func.coalesce(func.sum(Payment.amount), 0.0),
        )
        .join(Payment, Payment.job_id == Job.id)
        .filter(Job.created_at >= since, Payment.payment_status == "succeeded")
        .group_by(Job.lead_source).all()
    )
    by_lead_source = []
    for src in sorted(set(src_created) | set(src_completed) | set(src_revenue)):
        created = src_created.get(src, 0)
        comp = src_completed.get(src, 0)
        by_lead_source.append({
            "lead_source": src,
            "booked": created,
            "completed": comp,
            "completion_pct": _rate(comp, created),
            "revenue": round(float(src_revenue.get(src, 0.0)), 2),
        })
    by_lead_source.sort(key=lambda r: r["revenue"], reverse=True)

    return jsonify({
        "success": True,
        "window_days": days,
        "funnel": funnel,
        "biggest_leak": biggest_leak,
        "abandoned": {
            "count": abandoned,
            "recovered": abandoned_recovered,
            "recovery_pct": _rate(abandoned_recovered, abandoned),
        },
        "by_lead_source": by_lead_source,
        "overall_conversion_pct": _rate(completed, started),
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

    # If assigning to an operator, set as delegating (operator will assign to fleet)
    if contractor.is_operator:
        job.operator_id = contractor.id
        if job.status in ("pending", "confirmed"):
            job.status = "delegating"
        job.updated_at = utcnow()

        # Notify operator
        notification = Notification(
            id=generate_uuid(),
            user_id=contractor.user_id,
            type="job_assigned",
            title="New Job for Delegation",
            body="A job at {} needs delegation to your fleet.".format(job.address or "an address"),
            data={"job_id": job.id, "address": job.address, "total_price": job.total_price},
        )
        db.session.add(notification)
        db.session.commit()

        from socket_events import broadcast_job_status, socketio
        broadcast_job_status(job.id, job.status, {"operator_id": contractor.id})
        socketio.emit("operator:new-job", {
            "job_id": job.id,
            "address": job.address,
            "total_price": job.total_price,
        }, room="operator:{}".format(contractor.id))

        return jsonify({"success": True, "job": job.to_dict()}), 200

    # Regular contractor assignment
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

    # --- Email / SMS / Push notifications ---
    driver_name = contractor.user.name if contractor.user else None
    try:
        from notifications import (
            send_driver_assigned_email, send_driver_assigned_sms, send_push_notification,
        )
        customer = db.session.get(User, job.customer_id)
        if customer:
            if customer.email:
                send_driver_assigned_email(customer.email, customer.name, driver_name, job.address)
            if customer.phone:
                send_driver_assigned_sms(customer.phone, driver_name, job.address)
        # Push to driver: new job assigned
        send_push_notification(
            contractor.user_id, "New Job Assigned",
            "New job assigned: {}".format(job.address or "an address"),
            {"job_id": job.id},
        )
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).exception("Notification failed for job %s: %s", job.id, e)

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


@admin_bp.route("/jobs/<job_id>/cancel", methods=["PUT"])
@require_admin
def admin_cancel_job(user_id, job_id):
    """Admin cancels a job regardless of ownership."""
    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.status in ("completed", "cancelled"):
        return jsonify({"error": "Job cannot be cancelled in its current status"}), 409

    job.status = "cancelled"
    job.updated_at = utcnow()
    db.session.commit()

    from socket_events import broadcast_job_status
    broadcast_job_status(job.id, "cancelled", {})

    return jsonify({"success": True, "job": job.to_dict()}), 200


@admin_bp.route("/notifications", methods=["GET"])
@require_admin
def list_admin_notifications(user_id):
    """List notifications for this admin (most recent first)."""
    limit = request.args.get("limit", 20, type=int)
    include_read = request.args.get("include_read", "false").lower() == "true"

    query = Notification.query.filter_by(user_id=user_id)
    if not include_read:
        query = query.filter_by(is_read=False)

    notifications = (
        query.order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )

    unread_count = Notification.query.filter_by(user_id=user_id, is_read=False).count()

    return jsonify({
        "success": True,
        "notifications": [n.to_dict() for n in notifications],
        "unread_count": unread_count,
    }), 200


@admin_bp.route("/notifications/<notification_id>/read", methods=["PUT"])
@require_admin
def mark_admin_notification_read(user_id, notification_id):
    """Mark a single notification as read."""
    notification = db.session.get(Notification, notification_id)
    if not notification or notification.user_id != user_id:
        return jsonify({"error": "Notification not found"}), 404

    notification.is_read = True
    db.session.commit()

    return jsonify({"success": True}), 200


@admin_bp.route("/notifications/read-all", methods=["PUT"])
@require_admin
def mark_all_admin_notifications_read(user_id):
    """Mark all notifications for this admin as read."""
    Notification.query.filter_by(user_id=user_id, is_read=False).update({"is_read": True})
    db.session.commit()

    return jsonify({"success": True}), 200


# ---------------------------------------------------------------------------
# Pricing Rules (GET)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Payments / Payouts
# ---------------------------------------------------------------------------

@admin_bp.route("/payments", methods=["GET"])
@require_admin
def list_payments(user_id):
    """
    List payment records with the actual 3-way split amounts
    (commission, operator_payout_amount, driver_payout_amount)
    plus associated job, driver, and operator info.
    """
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    status_filter = request.args.get("status")  # e.g. 'succeeded', 'pending'

    query = Payment.query
    if status_filter:
        query = query.filter_by(payment_status=status_filter)

    pagination = query.order_by(Payment.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # Aggregate totals across ALL matching payments (not just this page)
    agg = db.session.query(
        func.coalesce(func.sum(Payment.amount), 0.0),
        func.coalesce(func.sum(Payment.commission), 0.0),
        func.coalesce(func.sum(Payment.driver_payout_amount), 0.0),
        func.coalesce(func.sum(Payment.operator_payout_amount), 0.0),
    )
    if status_filter:
        agg = agg.filter(Payment.payment_status == status_filter)
    agg_row = agg.one()

    payments = []
    for p in pagination.items:
        job = p.job
        driver_name = None
        operator_name = None

        if job:
            # Driver name
            if job.driver and job.driver.user:
                driver_name = job.driver.user.name
            # Operator name
            if job.operator_rel and job.operator_rel.user:
                operator_name = job.operator_rel.user.name

        payments.append({
            "id": p.id,
            "job_id": p.job_id,
            "amount": p.amount,
            "commission": p.commission,
            "driver_payout_amount": p.driver_payout_amount,
            "operator_payout_amount": p.operator_payout_amount or 0.0,
            "payout_status": p.payout_status,
            "payment_status": p.payment_status,
            "tip_amount": p.tip_amount,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "job_address": job.address if job else None,
            "job_status": job.status if job else None,
            "driver_name": driver_name,
            "operator_name": operator_name,
            "customer_name": job.customer.name if job and job.customer else None,
        })

    return jsonify({
        "success": True,
        "payments": payments,
        "totals": {
            "total_revenue": round(float(agg_row[0]), 2),
            "total_commission": round(float(agg_row[1]), 2),
            "total_driver_payouts": round(float(agg_row[2]), 2),
            "total_operator_payouts": round(float(agg_row[3]), 2),
        },
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    }), 200


# ---------------------------------------------------------------------------
# Pricing Config (admin-overridable pricing settings)
# ---------------------------------------------------------------------------

@admin_bp.route("/pricing/config", methods=["GET"])
@require_admin
def get_pricing_config(user_id):
    """Return all pricing config overrides."""
    configs = PricingConfig.query.all()
    return jsonify({
        "success": True,
        "config": {c.key: c.value for c in configs},
    }), 200


@admin_bp.route("/pricing/config", methods=["PUT"])
@require_admin
def update_pricing_config(user_id):
    """Bulk upsert pricing configuration values.

    Body JSON:
        config: {
            "minimum_job_price": 89.00,
            "volume_discount_tiers": [
                {"min_qty": 1, "max_qty": 3, "discount_rate": 0.0},
                {"min_qty": 4, "max_qty": 7, "discount_rate": 0.10},
                ...
            ],
            "same_day_surge": 0.25,
            "next_day_surge": 0.10,
            "weekend_surge": 0.15,
        }

    Each key is stored as a separate PricingConfig row so individual
    settings can be updated independently.
    """
    data = request.get_json() or {}
    config_data = data.get("config", {})

    if not isinstance(config_data, dict):
        return jsonify({"error": "config must be an object"}), 400

    ALLOWED_KEYS = {
        "minimum_job_price",
        "volume_discount_tiers",
        "same_day_surge",
        "next_day_surge",
        "weekend_surge",
        "service_fee_rate",
    }

    updated = {}
    for key, value in config_data.items():
        if key not in ALLOWED_KEYS:
            continue

        row = db.session.get(PricingConfig, key)
        if row:
            row.value = value
            row.updated_at = utcnow()
        else:
            row = PricingConfig(key=key, value=value)
            db.session.add(row)
        updated[key] = value

    db.session.commit()

    return jsonify({"success": True, "config": updated}), 200


# ---------------------------------------------------------------------------
# Database Migration (admin trigger)
# ---------------------------------------------------------------------------

@admin_bp.route("/migrate", methods=["POST"])
@require_admin
def run_db_migration(user_id):
    """Run pending database migrations (add new columns / create new tables).

    Safe to call multiple times (idempotent).
    """
    try:
        from migrate import run_migrations
        from flask import current_app

        url = current_app.config["SQLALCHEMY_DATABASE_URI"]
        actions = run_migrations(url)

        return jsonify({
            "success": True,
            "actions": actions,
        }), 200
    except Exception as e:
        return jsonify({"error": "Migration failed: {}".format(str(e))}), 500


# ---------------------------------------------------------------------------
# GET /api/admin/reviews — List all reviews
# ---------------------------------------------------------------------------
@admin_bp.route("/reviews", methods=["GET"])
@require_admin
def list_reviews(user_id):
    """List all customer reviews with optional rating filter."""
    rating_filter = request.args.get("rating", type=int)

    query = Review.query.order_by(Review.created_at.desc())

    if rating_filter and 1 <= rating_filter <= 5:
        query = query.filter_by(rating=rating_filter)

    reviews = query.limit(200).all()

    return jsonify({
        "success": True,
        "reviews": [r.to_dict() for r in reviews],
    }), 200


# ---------------------------------------------------------------------------
# POST /api/admin/sms/send — Send custom SMS to a customer
# ---------------------------------------------------------------------------
@admin_bp.route("/sms/send", methods=["POST"])
@require_admin
def admin_send_sms(user_id):
    """Send a custom SMS to a customer (admin only)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    target_user_id = data.get("user_id")
    message = data.get("message", "").strip()

    if not target_user_id:
        return jsonify({"error": "user_id is required"}), 400
    if not message:
        return jsonify({"error": "message is required"}), 400

    target_user = db.session.get(User, target_user_id)
    if not target_user:
        return jsonify({"error": "User not found"}), 404
    if not target_user.phone:
        return jsonify({"error": "User has no phone number on file"}), 400

    from sms_service import sms_custom
    sms_custom(target_user.phone, message)

    return jsonify({"success": True, "message": "SMS queued"}), 200


    # NOTE: seed-jobs endpoint removed (was unauthenticated, security risk)


# ---------------------------------------------------------------------------
# GET/DELETE /api/admin/cleanup — Audit and remove test/seed data
# ---------------------------------------------------------------------------
@admin_bp.route("/cleanup", methods=["GET"])
@require_admin
def cleanup_audit():
    """Audit production DB for test/seed data. Returns what WOULD be deleted."""
    from sqlalchemy import or_

    test_emails = ["test@umuve.com", "test@test.com", "demo@umuve.com",
                   "seed@umuve.com", "fake@test.com"]
    test_phones = ["+15555551234", "+15555550000"]

    # Find test users
    test_users = User.query.filter(
        or_(
            User.email.in_(test_emails),
            User.email.like("%@example.com"),
            User.email.like("%test%@%"),
            User.phone.in_(test_phones),
            User.name.like("Test %"),
            User.name.like("Seed %"),
            User.name.like("Fake %"),
            User.name.like("Demo %"),
        )
    ).all()
    test_user_ids = [u.id for u in test_users]

    # Find jobs owned by test users OR with test-like notes
    test_jobs = Job.query.filter(
        or_(
            Job.customer_id.in_(test_user_ids) if test_user_ids else False,
            Job.notes.like("Test job%"),
            Job.notes.like("Seed %"),
            Job.notes.like("%test%pickup%"),
        )
    ).all()
    test_job_ids = [j.id for j in test_jobs]

    # Find payments linked to test jobs
    test_payments = Payment.query.filter(
        Payment.job_id.in_(test_job_ids)
    ).all() if test_job_ids else []

    # Find ratings linked to test jobs or test users
    test_ratings = Rating.query.filter(
        or_(
            Rating.job_id.in_(test_job_ids) if test_job_ids else False,
            Rating.from_user_id.in_(test_user_ids) if test_user_ids else False,
            Rating.to_user_id.in_(test_user_ids) if test_user_ids else False,
        )
    ).all() if (test_job_ids or test_user_ids) else []

    # Find contractor profiles for test users
    test_contractors = Contractor.query.filter(
        Contractor.user_id.in_(test_user_ids)
    ).all() if test_user_ids else []

    # Find notifications for test users
    test_notifications = Notification.query.filter(
        Notification.user_id.in_(test_user_ids)
    ).all() if test_user_ids else []

    # ALL real users (for comparison)
    total_users = User.query.count()
    total_jobs = Job.query.count()

    return jsonify({
        "mode": "audit",
        "summary": {
            "total_users": total_users,
            "total_jobs": total_jobs,
            "test_users_to_delete": len(test_users),
            "test_jobs_to_delete": len(test_jobs),
            "test_payments_to_delete": len(test_payments),
            "test_ratings_to_delete": len(test_ratings),
            "test_contractors_to_delete": len(test_contractors),
            "test_notifications_to_delete": len(test_notifications),
        },
        "test_users": [{"id": u.id, "email": u.email, "phone": u.phone,
                         "name": u.name, "role": u.role,
                         "created_at": u.created_at.isoformat() if u.created_at else None}
                        for u in test_users],
        "test_jobs": [{"id": j.id, "status": j.status, "address": j.address,
                        "notes": j.notes, "total_price": j.total_price,
                        "created_at": j.created_at.isoformat() if j.created_at else None}
                       for j in test_jobs],
        "real_users_kept": [{"id": u.id, "email": u.email, "name": u.name, "role": u.role}
                            for u in User.query.filter(~User.id.in_(test_user_ids)).all()]
                           if test_user_ids else
                           [{"id": u.id, "email": u.email, "name": u.name, "role": u.role}
                            for u in User.query.all()],
    }), 200


@admin_bp.route("/cleanup", methods=["DELETE"])
@require_admin
def cleanup_execute():
    """Delete all test/seed data from production. Requires ?confirm=yes."""
    if request.args.get("confirm") != "yes":
        return jsonify({"error": "Add ?confirm=yes to actually delete"}), 400

    from sqlalchemy import or_

    test_emails = ["test@umuve.com", "test@test.com", "demo@umuve.com",
                   "seed@umuve.com", "fake@test.com"]
    test_phones = ["+15555551234", "+15555550000"]

    test_users = User.query.filter(
        or_(
            User.email.in_(test_emails),
            User.email.like("%@example.com"),
            User.email.like("%test%@%"),
            User.phone.in_(test_phones),
            User.name.like("Test %"),
            User.name.like("Seed %"),
            User.name.like("Fake %"),
            User.name.like("Demo %"),
        )
    ).all()
    test_user_ids = [u.id for u in test_users]

    test_jobs = Job.query.filter(
        or_(
            Job.customer_id.in_(test_user_ids) if test_user_ids else False,
            Job.notes.like("Test job%"),
            Job.notes.like("Seed %"),
            Job.notes.like("%test%pickup%"),
        )
    ).all()
    test_job_ids = [j.id for j in test_jobs]

    counts = {"users": 0, "jobs": 0, "payments": 0, "ratings": 0,
              "contractors": 0, "notifications": 0}

    # Delete in dependency order (children first)
    if test_job_ids:
        counts["payments"] = Payment.query.filter(Payment.job_id.in_(test_job_ids)).delete(synchronize_session=False)
        counts["ratings"] = Rating.query.filter(
            or_(Rating.job_id.in_(test_job_ids),
                Rating.from_user_id.in_(test_user_ids) if test_user_ids else False,
                Rating.to_user_id.in_(test_user_ids) if test_user_ids else False)
        ).delete(synchronize_session=False)

    if test_user_ids:
        counts["notifications"] = Notification.query.filter(
            Notification.user_id.in_(test_user_ids)
        ).delete(synchronize_session=False)
        # Device tokens
        DeviceToken.query.filter(DeviceToken.user_id.in_(test_user_ids)).delete(synchronize_session=False)

    # Delete test jobs
    for j in test_jobs:
        db.session.delete(j)
        counts["jobs"] += 1

    # Delete test contractor profiles (before users due to FK)
    if test_user_ids:
        for c in Contractor.query.filter(Contractor.user_id.in_(test_user_ids)).all():
            db.session.delete(c)
            counts["contractors"] += 1

    # Delete test users
    for u in test_users:
        db.session.delete(u)
        counts["users"] += 1

    db.session.commit()

    return jsonify({
        "success": True,
        "deleted": counts,
        "remaining_users": User.query.count(),
        "remaining_jobs": Job.query.count(),
    }), 200


@admin_bp.route("/notifications/health", methods=["GET"])
@require_admin
def notifications_health(user_id):
    """Check which notification services are configured."""
    return jsonify({
        "email": {
            "resend": bool(os.environ.get("RESEND_API_KEY")),
            "sendgrid": bool(os.environ.get("SENDGRID_API_KEY")),
            "from": os.environ.get("EMAIL_FROM", os.environ.get("SENDGRID_FROM_EMAIL", "bookings@goumuve.com")),
        },
        "sms": {
            "twilio_configured": bool(os.environ.get("TWILIO_ACCOUNT_SID") and os.environ.get("TWILIO_AUTH_TOKEN")),
            "from_number": bool(os.environ.get("TWILIO_PHONE_NUMBER") or os.environ.get("TWILIO_FROM_NUMBER")),
        },
        "push": {
            "apns_configured": bool(
                os.environ.get("APNS_KEY_ID")
                and os.environ.get("APNS_TEAM_ID")
                and os.environ.get("APNS_AUTH_KEY_PATH")
            ),
        },
        "operator_phone": bool(os.environ.get("OPERATOR_PHONE")),
        "stripe": bool(os.environ.get("STRIPE_SECRET_KEY")),
    }), 200
