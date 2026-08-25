"""
Admin API routes for Umuve.
Protected by role-based access (admin only).
"""

from flask import Blueprint, request, jsonify, current_app
from functools import wraps
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from sqlalchemy import func

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Contractor, Job, Payment, PricingRule, SurgeZone, Notification,
    PricingConfig, Review, Rating, DeviceToken, AbandonedBooking, Quote, Referral,
    ReferralPayout, generate_uuid, utcnow,
)
from auth_routes import require_auth
from notifications import send_email, render_driver_approval_email

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


@admin_bp.route("/contractors/payout-reminder-sms", methods=["POST"])
@require_admin
def payout_reminder_sms(user_id):
    """Text the payout-setup reminder to approved contractors with no usable
    email on file (phone-only signups the email campaign can't reach).

    Body: {"send": false} (default) returns the candidate list without
    texting; {"send": true} fires the SMS. Optional "contractor_ids" narrows
    the run to specific contractors instead of auto-selecting.
    """
    data = request.get_json(silent=True) or {}
    do_send = bool(data.get("send"))
    only_ids = set(data.get("contractor_ids") or [])

    candidates = []
    for c in Contractor.query.filter_by(approval_status="approved").all():
        u = db.session.get(User, c.user_id) if c.user_id else None
        if not u or not (u.phone or "").strip():
            continue
        has_email = "@" in (u.email or "")
        if only_ids:
            if c.id not in only_ids:
                continue
        elif has_email:
            continue
        candidates.append({"contractor_id": c.id, "name": u.name,
                           "phone": u.phone, "email": u.email or None})

    if not do_send:
        return jsonify({"success": True, "mode": "dry_run",
                        "candidates": candidates}), 200

    import sms_service

    def already_reminded(formatted_phone):
        """True if this number already got the payout reminder recently —
        makes re-runs (e.g. after a mid-batch crash) safe from double-texts."""
        try:
            client = sms_service._get_twilio()
            if not client or not formatted_phone:
                return False
            since = datetime.now(timezone.utc) - timedelta(days=3)
            for m in client.messages.list(to=formatted_phone, date_sent_after=since, limit=20):
                if "connect your payout account" in (m.body or ""):
                    return True
        except Exception:
            current_app.logger.exception("payout reminder dedupe check failed")
        return False

    results = []
    for cand in candidates:
        # One bad row must never abort the whole run — build + send inside
        # the guard, and report per-contractor.
        try:
            formatted = sms_service.format_phone(cand["phone"])
            if already_reminded(formatted):
                results.append({**cand, "sent": False, "skipped": "already reminded"})
                continue
            name_parts = (cand["name"] or "").split()
            first = name_parts[0] if name_parts else "there"
            body = (
                "Hi {}, it's Umuve — one step left before you can get paid: "
                "connect your payout account in your driver profile → "
                "https://app.goumuve.com/driver/profile Takes about 5 min. "
                "Add a debit card to unlock instant cash-outs, 24/7. Do it now "
                "so you're payout-ready before your first job."
            ).format(first)
            sid = sms_service.send_sms(cand["phone"], body)
            results.append({**cand, "sent": bool(sid)})
        except Exception:
            current_app.logger.exception(
                "payout reminder SMS failed for %s", cand.get("contractor_id"))
            results.append({**cand, "sent": False})

    sent_n = sum(1 for r in results if r["sent"])
    current_app.logger.info("payout reminder SMS: %d/%d sent", sent_n, len(results))
    return jsonify({"success": True, "mode": "sent",
                    "sent": sent_n, "total": len(results),
                    "results": results}), 200


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

    # Email the driver so approval isn't silent (mirrors the operator flow).
    # Branded template lives in notifications.render_driver_approval_email and
    # spells out the steps to actually start earning -- crucially Stripe payment
    # setup, without which payouts silently defer. Non-fatal: a mail failure
    # must never block the approval itself.
    try:
        driver = db.session.get(User, contractor.user_id)
        if driver and driver.email:
            subject, html = render_driver_approval_email(driver.name)
            send_email(to_email=driver.email, subject=subject, html_content=html)
    except Exception:
        current_app.logger.exception(
            "Failed to send approval email to contractor %s", contractor_id
        )

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

_PRICING_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Umuve — Pricing & Conversion</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Outfit:wght@600;700;800;900&display=swap" rel="stylesheet">
<style>
  :root{--ink:#1a1a1a;--red:#C52222;--mut:#6b6b66;--line:#e8e5df;--bg:#FAF8F5}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:'DM Sans',system-ui,sans-serif}
  .wrap{max-width:1000px;margin:0 auto;padding:2.5rem 1.25rem 4rem}
  h1{font-family:'Outfit',sans-serif;font-weight:800;font-size:1.9rem;letter-spacing:-.02em;margin:0}
  .sub{color:var(--mut);margin:.25rem 0 1.5rem;font-size:.95rem}
  .bar{display:flex;flex-wrap:wrap;gap:.6rem;align-items:center;margin-bottom:1.5rem}
  input,select{font:inherit;border:1px solid #d6d2ca;border-radius:.55rem;padding:.55rem .7rem;background:#fff}
  input{min-width:18rem}
  button{font:inherit;font-weight:700;background:var(--red);color:#fff;border:0;border-radius:.55rem;padding:.6rem 1.1rem;cursor:pointer}
  button:hover{background:#9E1B1B}
  .kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:.9rem;margin-bottom:1.5rem}
  @media(max-width:640px){.kpis{grid-template-columns:repeat(2,1fr)}}
  .card{background:#fff;border:1px solid var(--line);border-radius:.9rem;padding:1.1rem 1.2rem}
  .card .l{font-size:.7rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#9a948b}
  .card .v{font-family:'Outfit',sans-serif;font-weight:800;font-size:1.7rem;margin-top:.25rem;letter-spacing:-.02em}
  h2{font-family:'Outfit',sans-serif;font-weight:800;font-size:1.05rem;margin:1.75rem 0 .75rem}
  table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:.9rem;overflow:hidden}
  th,td{padding:.7rem .9rem;text-align:left;font-size:.9rem;border-top:1px solid var(--line)}
  th{background:#f3f0ea;font-size:.7rem;letter-spacing:.06em;text-transform:uppercase;color:#9a948b;border-top:0}
  td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
  .conv{display:flex;align-items:center;gap:.5rem;justify-content:flex-end}
  .track{width:80px;height:7px;border-radius:4px;background:#eee;overflow:hidden}
  .fill{height:100%;background:var(--red)}
  .muted{color:var(--mut);font-size:.85rem}
  .err{color:var(--red);font-size:.9rem;margin:.5rem 0}
  .adminnav{display:flex;gap:.4rem;margin-bottom:1.4rem;flex-wrap:wrap}
  .adminnav a{font-size:.85rem;font-weight:700;color:#6b6b66;text-decoration:none;padding:.42rem .85rem;border-radius:999px;border:1px solid transparent}
  .adminnav a:hover{background:#f3f0ea}
  .adminnav a.active{background:#fff;border-color:#e8e5df;color:#1a1a1a;box-shadow:0 1px 2px rgba(0,0,0,.04)}
</style></head><body>
<div id="adminLogin" style="display:none;position:fixed;inset:0;background:#FAF8F5;z-index:100;align-items:center;justify-content:center">
  <div style="background:#fff;border:1px solid #e8e5df;border-radius:1rem;padding:2rem;max-width:340px;width:90%;box-shadow:0 18px 40px rgba(0,0,0,.08)">
    <h2 style="font-family:'Outfit',sans-serif;font-weight:800;margin:0 0 .25rem">Admin sign in</h2>
    <p style="color:#6b6b66;font-size:.9rem;margin:0 0 1.2rem">Sign in with your Umuve admin email &amp; password.</p>
    <input id="al-email" type="email" placeholder="Email" autocomplete="email" style="width:100%;border:1px solid #d6d2ca;border-radius:.55rem;padding:.6rem .7rem;margin-bottom:.6rem;font:inherit;box-sizing:border-box">
    <input id="al-pass" type="password" placeholder="Password" autocomplete="current-password" onkeydown="if(event.key==='Enter')adminLogin()" style="width:100%;border:1px solid #d6d2ca;border-radius:.55rem;padding:.6rem .7rem;margin-bottom:.6rem;font:inherit;box-sizing:border-box">
    <button onclick="adminLogin()" style="width:100%;background:#C52222;color:#fff;border:0;border-radius:.55rem;padding:.65rem;font:inherit;font-weight:700;cursor:pointer">Sign in</button>
    <div id="al-err" style="color:#C52222;font-size:.85rem;margin-top:.6rem"></div>
  </div>
</div>
<div class="wrap">
  <nav class="adminnav">
    <a href="/api/admin/command-center-dashboard">Command Center</a>
    <a href="/api/admin/verification-dashboard">Verification</a>
    <a href="/api/admin/referral-dashboard">Referrals</a>
    <a href="/api/admin/pricing-dashboard" class="active">Pricing</a>
  </nav>
  <h1>Pricing &amp; Conversion</h1>
  <div class="sub">Quote &rarr; book conversion and platform take, by price band. Tune the binding quote toward the band that maximizes conversion &times; revenue.</div>
  <div class="bar">
    <select id="days">
      <option value="30">Last 30 days</option>
      <option value="90" selected>Last 90 days</option>
      <option value="180">Last 180 days</option>
      <option value="365">Last 365 days</option>
    </select>
    <button onclick="load()">Load</button>
  </div>
  <div id="err" class="err"></div>
  <div id="out" style="display:none">
    <div class="kpis">
      <div class="card"><div class="l">Quotes</div><div class="v" id="k_q">—</div></div>
      <div class="card"><div class="l">Booked</div><div class="v" id="k_b">—</div></div>
      <div class="card"><div class="l">Conversion</div><div class="v" id="k_c">—</div></div>
      <div class="card"><div class="l">Avg quote</div><div class="v" id="k_aq">—</div></div>
      <div class="card"><div class="l">Platform revenue</div><div class="v" id="k_rev">—</div></div>
      <div class="card"><div class="l">Avg take / job</div><div class="v" id="k_take">—</div></div>
    </div>
    <h2>By price band</h2>
    <table><thead><tr>
      <th>Band</th><th class="n">Quoted</th><th class="n">Booked</th>
      <th class="n">Conversion</th><th class="n">Avg price</th><th class="n">Platform rev</th>
    </tr></thead><tbody id="bands"></tbody></table>
    <h2>Binding vs estimate</h2>
    <table><thead><tr><th>Quote type</th><th class="n">Quoted</th><th class="n">Booked</th><th class="n">Conversion</th></tr></thead>
      <tbody id="conf"></tbody></table>
    <p class="muted" id="meta" style="margin-top:1rem"></p>
  </div>
<script>
  const $=id=>document.getElementById(id);
  const money=n=>'$'+(n||0).toLocaleString(undefined,{maximumFractionDigits:0});
  const TOKEN_KEY='umuve_admin_token';
  function _tok(){ return localStorage.getItem(TOKEN_KEY)||''; }
  function _showLogin(msg){ document.getElementById('adminLogin').style.display='flex'; var o=document.getElementById('out'); if(o) o.style.display='none'; if(msg) document.getElementById('al-err').textContent=msg; }
  function _hideLogin(){ document.getElementById('adminLogin').style.display='none'; }
  async function adminLogin(){
    var email=(document.getElementById('al-email').value||'').trim().toLowerCase();
    var pass=document.getElementById('al-pass').value;
    document.getElementById('al-err').textContent='';
    if(!email||!pass){ document.getElementById('al-err').textContent='Enter email and password.'; return; }
    try{
      var r=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email,password:pass})});
      var b=await r.json().catch(function(){return{};});
      if(r.ok&&b.token){ localStorage.setItem(TOKEN_KEY,b.token); _hideLogin(); load(); }
      else { document.getElementById('al-err').textContent=(b&&b.error)||'Sign in failed.'; }
    }catch(e){ document.getElementById('al-err').textContent='Network error.'; }
  }
  async function load(){
    $('err').textContent=''; const days=$('days').value;
    try{
      const r=await fetch('/api/admin/pricing-analytics?days='+days,{headers:{Authorization:'Bearer '+_tok()}});
      if(r.status===401){ _showLogin('Please sign in.'); return; }
      if(r.status===403){ _showLogin('That account is not an admin.'); return; }
      if(!r.ok){ $('err').textContent='Error '+r.status; return; }
      _hideLogin(); render(await r.json());
    }catch(e){ $('err').textContent='Request failed: '+e; }
  }
  function convCell(p){ return '<div class="conv"><span>'+p.toFixed(1)+'%</span><span class="track"><span class="fill" style="width:'+Math.min(100,p)+'%"></span></span></div>'; }
  function render(d){
    $('out').style.display='block';
    const o=d.overall;
    $('k_q').textContent=o.quoted.toLocaleString();
    $('k_b').textContent=o.booked.toLocaleString();
    $('k_c').textContent=o.conversion.toFixed(1)+'%';
    $('k_aq').textContent=money(o.avg_quote);
    $('k_rev').textContent=money(o.platform_revenue);
    $('k_take').textContent=money(o.avg_take_per_job);
    $('bands').innerHTML=d.by_price_band.map(b=>'<tr><td>'+b.band+'</td><td class="n">'+b.quoted+'</td><td class="n">'+b.booked+'</td><td class="n">'+convCell(b.conversion)+'</td><td class="n">'+money(b.avg_price)+'</td><td class="n">'+money(b.revenue)+'</td></tr>').join('');
    const c=d.by_confidence;
    $('conf').innerHTML=[['Binding (high confidence)',c.binding],['Estimate (buffered)',c.non_binding]].map(([lbl,x])=>'<tr><td>'+lbl+'</td><td class="n">'+x.quoted+'</td><td class="n">'+x.booked+'</td><td class="n">'+convCell(x.conversion)+'</td></tr>').join('');
    $('meta').textContent='Window: '+d.window_days+' days · platform take '+(d.take_rate*100).toFixed(0)+'% · revenue = booked price × take.';
  }
  if(_tok()) load(); else _showLogin();
</script>
</div></body></html>"""


_REFERRAL_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Umuve — Referral Payouts</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Outfit:wght@600;700;800;900&display=swap" rel="stylesheet">
<style>
  :root{--ink:#1a1a1a;--red:#C52222;--mut:#6b6b66;--line:#e8e5df;--bg:#FAF8F5}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:'DM Sans',system-ui,sans-serif}
  .wrap{max-width:1000px;margin:0 auto;padding:2.5rem 1.25rem 4rem}
  h1{font-family:'Outfit',sans-serif;font-weight:800;font-size:1.9rem;letter-spacing:-.02em;margin:0}
  .sub{color:var(--mut);margin:.25rem 0 1.5rem;font-size:.95rem}
  .bar{display:flex;flex-wrap:wrap;gap:.6rem;align-items:center;margin-bottom:1.5rem}
  input,select{font:inherit;border:1px solid #d6d2ca;border-radius:.55rem;padding:.55rem .7rem;background:#fff}
  input{min-width:18rem}
  button{font:inherit;font-weight:700;background:var(--red);color:#fff;border:0;border-radius:.55rem;padding:.6rem 1.1rem;cursor:pointer}
  button:hover{background:#9E1B1B}
  .kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:.9rem;margin-bottom:1.5rem}
  @media(max-width:640px){.kpis{grid-template-columns:repeat(2,1fr)}}
  .card{background:#fff;border:1px solid var(--line);border-radius:.9rem;padding:1.1rem 1.2rem}
  .card .l{font-size:.7rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#9a948b}
  .card .v{font-family:'Outfit',sans-serif;font-weight:800;font-size:1.7rem;margin-top:.25rem;letter-spacing:-.02em}
  table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:.9rem;overflow:hidden}
  th,td{padding:.7rem .9rem;text-align:left;font-size:.9rem;border-top:1px solid var(--line)}
  th{background:#f3f0ea;font-size:.7rem;letter-spacing:.06em;text-transform:uppercase;color:#9a948b;border-top:0}
  td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
  .tag{display:inline-block;border-radius:999px;padding:.15rem .55rem;font-size:.72rem;font-weight:700}
  .t-rewarded{background:#E9F7EE;color:#1B7F44}
  .t-completed{background:#FEF6E7;color:#9a6700}
  .t-signed_up{background:#EEF2FF;color:#3a4ea8}
  .t-other{background:#eee;color:#666}
  .muted{color:var(--mut);font-size:.85rem}
  .err{color:var(--red);font-size:.9rem;margin:.5rem 0}
  .who{font-weight:600}.whoe{color:#9a948b;font-size:.78rem}
  .adminnav{display:flex;gap:.4rem;margin-bottom:1.4rem;flex-wrap:wrap}
  .adminnav a{font-size:.85rem;font-weight:700;color:#6b6b66;text-decoration:none;padding:.42rem .85rem;border-radius:999px;border:1px solid transparent}
  .adminnav a:hover{background:#f3f0ea}
  .adminnav a.active{background:#fff;border-color:#e8e5df;color:#1a1a1a;box-shadow:0 1px 2px rgba(0,0,0,.04)}
</style></head><body>
<div id="adminLogin" style="display:none;position:fixed;inset:0;background:#FAF8F5;z-index:100;align-items:center;justify-content:center">
  <div style="background:#fff;border:1px solid #e8e5df;border-radius:1rem;padding:2rem;max-width:340px;width:90%;box-shadow:0 18px 40px rgba(0,0,0,.08)">
    <h2 style="font-family:'Outfit',sans-serif;font-weight:800;margin:0 0 .25rem">Admin sign in</h2>
    <p style="color:#6b6b66;font-size:.9rem;margin:0 0 1.2rem">Sign in with your Umuve admin email &amp; password.</p>
    <input id="al-email" type="email" placeholder="Email" autocomplete="email" style="width:100%;border:1px solid #d6d2ca;border-radius:.55rem;padding:.6rem .7rem;margin-bottom:.6rem;font:inherit;box-sizing:border-box">
    <input id="al-pass" type="password" placeholder="Password" autocomplete="current-password" onkeydown="if(event.key==='Enter')adminLogin()" style="width:100%;border:1px solid #d6d2ca;border-radius:.55rem;padding:.6rem .7rem;margin-bottom:.6rem;font:inherit;box-sizing:border-box">
    <button onclick="adminLogin()" style="width:100%;background:#C52222;color:#fff;border:0;border-radius:.55rem;padding:.65rem;font:inherit;font-weight:700;cursor:pointer">Sign in</button>
    <div id="al-err" style="color:#C52222;font-size:.85rem;margin-top:.6rem"></div>
  </div>
</div>
<div class="wrap">
  <nav class="adminnav">
    <a href="/api/admin/command-center-dashboard">Command Center</a>
    <a href="/api/admin/verification-dashboard">Verification</a>
    <a href="/api/admin/referral-dashboard" class="active">Referrals</a>
    <a href="/api/admin/pricing-dashboard">Pricing</a>
  </nav>
  <h1>Referral Payouts</h1>
  <div class="sub">Hauler-to-hauler referrals. Each completed referral pays BOTH haulers. Totals are actual Stripe transfers from the payout ledger.</div>
  <div class="bar">
    <select id="days">
      <option value="90">Last 90 days</option>
      <option value="365" selected>Last 365 days</option>
      <option value="730">Last 2 years</option>
    </select>
    <button onclick="load()">Load</button>
  </div>
  <div id="err" class="err"></div>
  <div id="out" style="display:none">
    <div class="kpis">
      <div class="card"><div class="l">Paid out</div><div class="v" id="k_paid">—</div></div>
      <div class="card"><div class="l">Pending payout</div><div class="v" id="k_pending">—</div></div>
      <div class="card"><div class="l">Rewarded refs</div><div class="v" id="k_rew">—</div></div>
      <div class="card"><div class="l">Awaiting 1st job</div><div class="v" id="k_signed">—</div></div>
    </div>
    <table><thead><tr>
      <th>Referrer</th><th>Referred hauler</th><th>Status</th>
      <th class="n">Bonus each</th><th class="n">Paid / total</th><th>Completed</th>
    </tr></thead><tbody id="rows"></tbody></table>
    <p class="muted" id="meta" style="margin-top:1rem"></p>
  </div>
<script>
  const $=id=>document.getElementById(id);
  const money=n=>'$'+(n||0).toLocaleString(undefined,{maximumFractionDigits:0});
  const TOKEN_KEY='umuve_admin_token';
  function _tok(){ return localStorage.getItem(TOKEN_KEY)||''; }
  function _showLogin(msg){ document.getElementById('adminLogin').style.display='flex'; var o=document.getElementById('out'); if(o) o.style.display='none'; if(msg) document.getElementById('al-err').textContent=msg; }
  function _hideLogin(){ document.getElementById('adminLogin').style.display='none'; }
  async function adminLogin(){
    var email=(document.getElementById('al-email').value||'').trim().toLowerCase();
    var pass=document.getElementById('al-pass').value;
    document.getElementById('al-err').textContent='';
    if(!email||!pass){ document.getElementById('al-err').textContent='Enter email and password.'; return; }
    try{
      var r=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email,password:pass})});
      var b=await r.json().catch(function(){return{};});
      if(r.ok&&b.token){ localStorage.setItem(TOKEN_KEY,b.token); _hideLogin(); load(); }
      else { document.getElementById('al-err').textContent=(b&&b.error)||'Sign in failed.'; }
    }catch(e){ document.getElementById('al-err').textContent='Network error.'; }
  }
  async function load(){
    $('err').textContent=''; const days=$('days').value;
    try{
      const r=await fetch('/api/admin/referral-payouts?days='+days,{headers:{Authorization:'Bearer '+_tok()}});
      if(r.status===401){ _showLogin('Please sign in.'); return; }
      if(r.status===403){ _showLogin('That account is not an admin.'); return; }
      if(!r.ok){ $('err').textContent='Error '+r.status; return; }
      _hideLogin(); render(await r.json());
    }catch(e){ $('err').textContent='Request failed: '+e; }
  }
  function who(w){ if(!w||(!w.name&&!w.email)) return '<span class="whoe">unknown</span>'; return '<div class="who">'+(w.name||w.email)+'</div>'+(w.name&&w.email?'<div class="whoe">'+w.email+'</div>':''); }
  function tag(s){ const cls=['rewarded','completed','signed_up'].includes(s)?s:'other'; const lbl={rewarded:'Paid',completed:'Earned (pending)',signed_up:'Linked'}[s]||s; return '<span class="tag t-'+cls+'">'+lbl+'</span>'; }
  function fdate(d){ return d? new Date(d).toLocaleDateString():'—'; }
  function render(d){
    $('out').style.display='block'; const s=d.summary;
    $('k_paid').textContent=money(s.paid_out);
    $('k_pending').textContent=money(s.pending_payout);
    $('k_rew').textContent=s.rewarded;
    $('k_signed').textContent=s.signed_up;
    $('rows').innerHTML = d.referrals.length ? d.referrals.map(r=>'<tr><td>'+who(r.referrer)+'</td><td>'+who(r.referee)+'</td><td>'+tag(r.status)+'</td><td class="n">'+money(r.bonus_each)+'</td><td class="n">'+money(r.paid)+' / '+money(r.total_if_both)+'</td><td>'+fdate(r.completed_at)+'</td></tr>').join('') : '<tr><td colspan="6" style="text-align:center;color:#9a948b;padding:2rem">No referrals in this window yet.</td></tr>';
    $('meta').textContent='Window: '+d.window_days+' days · $'+d.bonus_per_hauler+' per hauler · '+s.total+' referrals · '+(s.transfers||0)+' transfers. Paid out = actual Stripe transfers (ledger); pending = earned but not yet sent.';
  }
  if(_tok()) load(); else _showLogin();
</script>
</div></body></html>"""


# ===========================================================================
# Command Center — one snapshot of the whole machine (supply, demand, outreach,
# B2B, launch verdict, and what needs a human). Same design system as the rest.
# ===========================================================================
_COMMAND_CENTER_HTML = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Umuve — Command Center</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Outfit:wght@600;700;800;900&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:#F5F2EC; --card:#fff; --ink:#191714; --mut:#6E6A62; --faint:#A8A296;
    --line:#E9E3D8; --red:#C52222; --red-d:#9E1B1B;
    --ready:#1B7F44; --ready-bg:#E7F4EC; --hold:#B7791F; --hold-bg:#FBF1DF;
    --stop:#C0362C; --stop-bg:#FBEAE7;
    --r:16px; --shadow:0 1px 2px rgba(25,23,20,.04), 0 10px 30px -16px rgba(25,23,20,.14);
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:'DM Sans',system-ui,sans-serif;-webkit-font-smoothing:antialiased}
  .wrap{max-width:1020px;margin:0 auto;padding:2rem 1.25rem 4rem}
  .num{font-variant-numeric:tabular-nums;font-feature-settings:"tnum"}
  a{color:inherit}
  button{font:inherit;cursor:pointer}
  :focus-visible{outline:2px solid var(--red);outline-offset:2px;border-radius:6px}

  /* nav */
  .adminnav{display:flex;gap:.4rem;margin-bottom:1.5rem;flex-wrap:wrap}
  .adminnav a{font-size:.85rem;font-weight:700;color:var(--mut);text-decoration:none;padding:.42rem .85rem;border-radius:999px;border:1px solid transparent}
  .adminnav a:hover{background:#EDE8DF}
  .adminnav a.active{background:#fff;border-color:var(--line);color:var(--ink);box-shadow:0 1px 2px rgba(0,0,0,.04)}

  /* status line */
  .status{display:flex;align-items:center;gap:.55rem;margin-bottom:1.1rem;font-size:.9rem;color:var(--mut)}
  .live{width:.55rem;height:.55rem;border-radius:50%;background:var(--faint);flex:0 0 auto}
  .live.ready{background:var(--ready)} .live.hold{background:var(--hold)} .live.stop{background:var(--stop)}
  .status .sp{margin-left:auto;display:flex;align-items:center;gap:.8rem}
  .refresh{background:transparent;border:1px solid var(--line);border-radius:999px;padding:.35rem .8rem;color:var(--ink);font-weight:600;font-size:.82rem}
  .refresh:hover{background:#fff}

  /* hero / dispatch */
  .hero{background:var(--card);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow);padding:1.6rem 1.7rem;position:relative;overflow:hidden}
  .hero::before{content:"";position:absolute;left:0;top:0;bottom:0;width:5px}
  .hero.ready::before{background:var(--ready)} .hero.hold::before{background:var(--hold)} .hero.stop::before{background:var(--stop)}
  .eyebrow{font-size:.72rem;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:var(--faint)}
  .word{font-family:'Outfit',sans-serif;font-weight:900;font-size:2.6rem;line-height:1.02;letter-spacing:-.03em;margin:.15rem 0 .25rem}
  .ready .word{color:var(--ready)} .hold .word{color:var(--hold)} .stop .word{color:var(--stop)}
  .say{font-size:1.02rem;color:var(--ink);max-width:46ch}

  /* the dispatch link — the signature */
  .link{display:flex;align-items:center;gap:.7rem;margin:1.5rem 0 .2rem;max-width:560px}
  .node{flex:0 0 auto;min-width:118px;text-align:center;background:#FBFAF7;border:1px solid var(--line);border-radius:12px;padding:.7rem .6rem}
  .node .n{font-family:'Outfit',sans-serif;font-weight:800;font-size:1.5rem;letter-spacing:-.02em}
  .node .nl{font-size:.7rem;color:var(--mut);text-transform:uppercase;letter-spacing:.06em;margin-top:.15rem}
  .wire{flex:1;height:2px;border-radius:2px;min-width:18px}
  .clasp{flex:0 0 auto;width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:.85rem;position:relative}
  /* matched */
  .link.matched .wire{background:var(--ready)}
  .link.matched .clasp{background:var(--ready);color:#fff}
  .link.matched .node{border-color:#CDE7D6}
  /* severed */
  .link.severed .wire{background:repeating-linear-gradient(90deg,var(--stop) 0 5px,transparent 5px 10px);opacity:.55}
  .link.severed .clasp{background:var(--stop-bg);color:var(--stop);border:1.5px solid var(--stop)}
  .link.severed .node.supply{border-color:#E7C6C1}

  .move{display:inline-flex;align-items:center;gap:.5rem;margin-top:1.2rem;font-weight:700;font-size:.98rem;text-decoration:none}
  .move .tag{font-size:.66rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:#fff;background:var(--red);padding:.2rem .5rem;border-radius:999px}
  .move.go .tag{background:var(--ready)}
  .move .arr{color:var(--red);transition:transform .15s ease}
  a.move:hover .arr{transform:translateX(3px)}

  /* section heads */
  .head{font-family:'Outfit',sans-serif;font-weight:800;font-size:.8rem;letter-spacing:.12em;text-transform:uppercase;color:var(--faint);margin:2rem 0 .7rem}

  /* action feed */
  .feed{background:var(--card);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow);overflow:hidden}
  .frow{display:flex;align-items:center;gap:.8rem;padding:.85rem 1.1rem;border-top:1px solid var(--line);font-size:.94rem}
  .frow:first-child{border-top:0}
  .frow .sev{width:.6rem;height:.6rem;border-radius:50%;flex:0 0 auto}
  .sev.high{background:var(--stop)} .sev.med{background:var(--hold)} .sev.low{background:var(--faint)}
  .frow .do{margin-left:auto;font-size:.82rem;font-weight:700;color:var(--red);white-space:nowrap;text-decoration:none;display:inline-flex;align-items:center;gap:.3rem}
  a.do:hover{text-decoration:underline}
  .frow.clear{color:var(--mut);font-style:normal}
  .frow.clear .sev{background:var(--ready)}

  /* marketplace sides */
  .sides{display:grid;grid-template-columns:1fr 1px 1fr;gap:1.2rem;align-items:start}
  .rule{background:var(--line);align-self:stretch}
  .sidehead{font-family:'Outfit',sans-serif;font-weight:800;font-size:.95rem;margin-bottom:.7rem;display:flex;align-items:center;gap:.5rem}
  .sidehead .d{width:.5rem;height:.5rem;border-radius:50%}
  .sidehead.sup .d{background:var(--ink)} .sidehead.dem .d{background:var(--red)}
  .cards{display:grid;grid-template-columns:1fr 1fr;gap:.7rem}
  .card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:.85rem .95rem;transition:transform .12s ease,box-shadow .12s ease}
  .card:hover{transform:translateY(-1px);box-shadow:var(--shadow)}
  .card .cl{font-size:.7rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--faint)}
  .card .cv{font-family:'Outfit',sans-serif;font-weight:800;font-size:1.55rem;letter-spacing:-.02em;margin-top:.2rem}
  .card .cs{font-size:.74rem;color:var(--mut);margin-top:.1rem}
  .card.gate{background:linear-gradient(180deg,#fff,#FBFAF7)}
  .card.gate.zero{border-color:#E7C6C1;background:linear-gradient(180deg,#fff,var(--stop-bg))}
  .card.gate.zero .cv{color:var(--stop)}
  .card.gate.ok .cv{color:var(--ready)}
  .card.hot .cv{color:var(--red)}

  /* pipeline funnels */
  .pipe{background:var(--card);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow);padding:1.1rem 1.2rem}
  .flow{display:flex;align-items:center;flex-wrap:wrap;gap:.1rem;padding:.55rem 0;border-top:1px solid var(--line)}
  .flow:first-of-type{border-top:0}
  .flow .fname{font-weight:700;font-size:.84rem;width:88px;flex:0 0 auto;color:var(--ink)}
  .stage{display:inline-flex;align-items:baseline;gap:.3rem;padding:.1rem .15rem}
  .stage .sc{font-family:'Outfit',sans-serif;font-weight:800;font-size:.98rem}
  .stage .sl{font-size:.74rem;color:var(--mut)}
  .stage.warm .sc{color:var(--red)}
  .sep{color:var(--faint);font-size:.85rem;padding:0 .35rem}
  .accts{font-size:.86rem;color:var(--mut);margin-top:.1rem}
  .accts b{color:var(--ink);font-variant-numeric:tabular-nums}

  .err{color:var(--red);font-size:.92rem;margin:.5rem 0}
  .muted{color:var(--mut);font-size:.82rem}

  @media (max-width:680px){
    .word{font-size:2.1rem}
    .sides{grid-template-columns:1fr;gap:.4rem}
    .rule{display:none}
    .sidehead{margin-top:1rem}
    .link{flex-wrap:nowrap}
    .node{min-width:96px}
    .flow .fname{width:100%}
  }
  /* one orchestrated load + the living clasp; fully off for reduced-motion */
  @media (prefers-reduced-motion: no-preference){
    .reveal{opacity:0;transform:translateY(8px);animation:rise .55s cubic-bezier(.2,.7,.2,1) forwards}
    .reveal.d1{animation-delay:.04s}.reveal.d2{animation-delay:.12s}.reveal.d3{animation-delay:.2s}.reveal.d4{animation-delay:.28s}
    @keyframes rise{to{opacity:1;transform:none}}
    .link.matched .clasp::after{content:"";position:absolute;inset:-5px;border-radius:50%;border:2px solid var(--ready);opacity:.6;animation:beat 2.4s ease-out infinite}
    @keyframes beat{0%{transform:scale(.8);opacity:.55}70%{transform:scale(1.5);opacity:0}100%{opacity:0}}
  }
</style></head><body>
<div id="adminLogin" style="display:none;position:fixed;inset:0;background:#F5F2EC;z-index:100;align-items:center;justify-content:center">
  <div style="background:#fff;border:1px solid #E9E3D8;border-radius:1rem;padding:2rem;max-width:340px;width:90%;box-shadow:0 18px 40px rgba(0,0,0,.08)">
    <h2 style="font-family:'Outfit',sans-serif;font-weight:800;margin:0 0 .25rem">Sign in</h2>
    <p style="color:#6E6A62;font-size:.9rem;margin:0 0 1.2rem">Use your Umuve admin email and password.</p>
    <input id="al-email" type="email" placeholder="Email" autocomplete="email" style="width:100%;border:1px solid #d6d2ca;border-radius:.55rem;padding:.6rem .7rem;margin-bottom:.6rem;font:inherit;box-sizing:border-box">
    <input id="al-pass" type="password" placeholder="Password" autocomplete="current-password" onkeydown="if(event.key==='Enter')adminLogin()" style="width:100%;border:1px solid #d6d2ca;border-radius:.55rem;padding:.6rem .7rem;margin-bottom:.6rem;font:inherit;box-sizing:border-box">
    <button onclick="adminLogin()" style="width:100%;background:#C52222;color:#fff;border:0;border-radius:.55rem;padding:.65rem;font:inherit;font-weight:700">Sign in</button>
    <div id="al-err" style="color:#C52222;font-size:.85rem;margin-top:.6rem"></div>
  </div>
</div>
<div class="wrap">
  <nav class="adminnav">
    <a href="/api/admin/command-center-dashboard" class="active">Command Center</a>
    <a href="/api/admin/verification-dashboard">Verification</a>
    <a href="/api/admin/referral-dashboard">Referrals</a>
    <a href="/api/admin/pricing-dashboard">Pricing</a>
  </nav>
  <div class="status">
    <span id="live" class="live"></span><span>Umuve dispatch</span>
    <span class="sp"><span id="asof" class="muted"></span><button class="refresh" onclick="load()">Refresh</button></span>
  </div>
  <div id="err" class="err"></div>
  <div id="out" style="display:none"></div>
<script>
  const $=id=>document.getElementById(id);
  const TOKEN_KEY='umuve_admin_token';
  function _tok(){ return localStorage.getItem(TOKEN_KEY)||''; }
  function esc(s){ return (s==null?'':String(s)).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
  function _showLogin(m){ document.getElementById('adminLogin').style.display='flex'; var o=$('out'); if(o)o.style.display='none'; if(m)$('al-err').textContent=m; }
  function _hideLogin(){ document.getElementById('adminLogin').style.display='none'; }
  async function adminLogin(){
    var email=($('al-email').value||'').trim().toLowerCase(), pass=$('al-pass').value;
    $('al-err').textContent='';
    if(!email||!pass){ $('al-err').textContent='Enter your email and password.'; return; }
    try{ var r=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email,password:pass})});
      var b=await r.json().catch(()=>({})); if(r.ok&&b.token){ localStorage.setItem(TOKEN_KEY,b.token); _hideLogin(); load(); }
      else $('al-err').textContent=(b&&b.error)||'That sign-in did not work.';
    }catch(e){ $('al-err').textContent='Network error. Try again.'; }
  }
  const money=n=>'$'+(n||0).toLocaleString(undefined,{maximumFractionDigits:0});
  let _first=true; function rv(n){ return _first?(' reveal d'+n):''; }
  const VMAP={
    'GO':{cls:'ready',word:'Ready',say:'A West Palm booking will reach an online truck right now.'},
    'ALMOST':{cls:'hold',word:'Almost',say:'Everything is set. One truck needs to go online to start dispatching.'},
    'NO-GO':{cls:'stop',word:'Blocked',say:'Dispatch is off. Check the mode, or get a truck online.'}
  };
  function vchip(v){ return VMAP[v]||VMAP['NO-GO']; }
  function card(label,val,sub,cls){ return '<div class="card '+(cls||'')+'"><div class="cl">'+label+'</div><div class="cv num">'+val+'</div>'+(sub?'<div class="cs">'+sub+'</div>':'')+'</div>'; }
  function flow(name,obj,order,labels){
    const keys=order.filter(k=>obj[k]!=null);
    const rest=Object.keys(obj).filter(k=>!order.includes(k)&&k!=='none');
    const all=keys.concat(rest);
    const seg=all.map((k,i)=>{
      const warm=(k==='replied'||k==='converted')&&obj[k]>0;
      return (i?'<span class="sep">›</span>':'')+'<span class="stage'+(warm?' warm':'')+'"><span class="sc num">'+obj[k]+'</span><span class="sl">'+esc(labels[k]||k)+'</span></span>';
    }).join('');
    return '<div class="flow"><span class="fname">'+name+'</span>'+(all.length?seg:'<span class="muted">no leads yet</span>')+'</div>';
  }
  function actionHref(what){ return /document|onboarding|verif/i.test(what)?'/api/admin/verification-dashboard':null; }

  async function load(){
    $('err').textContent='';
    try{
      const r=await fetch('/api/admin/command-center',{headers:{Authorization:'Bearer '+_tok()}});
      if(r.status===401){ _showLogin('Please sign in.'); return; }
      if(r.status===403){ _showLogin('That account is not an admin.'); return; }
      if(!r.ok){ $('err').textContent='Could not load ('+r.status+'). Try Refresh.'; return; }
      _hideLogin(); render(await r.json());
    }catch(e){ $('err').textContent='Request failed. Check your connection and Refresh.'; }
  }

  function render(d){
    $('out').style.display='block';
    const v=vchip(d.verdict), s=d.supply||{}, dm=d.demand||{};
    $('live').className='live '+v.cls;
    $('asof').textContent = d.as_of ? ('Updated '+new Date(d.as_of).toLocaleString([], {month:'short',day:'numeric',hour:'numeric',minute:'2-digit'})) : '';

    const trucks = s.online_in_range_wpb||0;
    const matched = trucks>=1;
    const demandLabel = dm.waitlist_open>0 ? (dm.waitlist_open+' waiting')
                       : dm.jobs_active>0 ? (dm.jobs_active+' active')
                       : 'open';
    const demandNum = dm.waitlist_open>0 ? dm.waitlist_open : (dm.jobs_active||0);

    // the one move: first high item, else next step
    const att=(d.attention||[]);
    const top=att.find(a=>a.level==='high')||att[0];
    let moveHtml='';
    if(d.verdict==='GO'){
      moveHtml='<span class="move go"><span class="tag">Next</span> Turn on the West Palm ads ($25/day)</span>';
    } else if(top){
      const href=actionHref(top.what);
      const inner='<span class="tag">Do this</span> '+esc(top.action)+(href?'<span class="arr">→</span>':'');
      moveHtml = href? ('<a class="move" href="'+href+'">'+inner+'</a>') : ('<span class="move">'+inner+'</span>');
    }

    const link=
      '<div class="link '+(matched?'matched':'severed')+'">'+
        '<div class="node supply"><div class="n num">'+trucks+'</div><div class="nl">trucks · WPB</div></div>'+
        '<span class="wire"></span><span class="clasp">'+(matched?'✓':'✕')+'</span><span class="wire"></span>'+
        '<div class="node demand"><div class="n num">'+demandNum+'</div><div class="nl">'+esc(demandLabel)+'</div></div>'+
      '</div>';

    const hero=
      '<div class="hero '+v.cls+rv(1)+'">'+
        '<div class="eyebrow">West Palm Beach · dispatch</div>'+
        '<div class="word">'+v.word+'</div>'+
        '<div class="say">'+v.say+'</div>'+
        link+ moveHtml +
      '</div>';

    const feedRows = att.length ? att.map(a=>{
      const href=actionHref(a.what);
      const doEl = href? ('<a class="do" href="'+href+'">'+esc(a.action)+' →</a>') : ('<span class="do">'+esc(a.action)+'</span>');
      return '<div class="frow"><span class="sev '+esc(a.level)+'"></span><span>'+esc(a.what)+'</span>'+doEl+'</div>';
    }).join('') : '<div class="frow clear"><span class="sev"></span>You’re clear. Nothing needs you right now.</div>';
    const feed='<div class="head">Do this now</div><div class="feed'+rv(2)+'">'+feedRows+'</div>';

    const docflag=(s.docs&&s.docs.flagged)||0;
    const supplyCards='<div class="cards">'+
      card('Online in WPB', trucks, 'the launch gate', 'gate '+(trucks>0?'ok':'zero'))+
      card('Online anywhere', s.online||0)+
      card('Approved', s.approved||0, (s.approved_offline||0)+' offline now')+
      card('Operators', s.operators_total||0, docflag?(docflag+' docs flagged'):null, docflag?'hot':'')+
    '</div>';
    const demandCards='<div class="cards">'+
      card('Revenue · 7 days', money(dm.revenue_this_week), 'completed jobs')+
      card('Jobs today', dm.jobs_today||0)+
      card('Working now', dm.jobs_active||0, 'in progress')+
      card('Waitlist', dm.waitlist_open||0, 'uncovered demand', (dm.waitlist_open||0)>0?'hot':'')+
    '</div>';
    const sides=
      '<div class="head">The marketplace</div>'+
      '<div class="sides'+rv(3)+'">'+
        '<div><div class="sidehead sup"><span class="d"></span>Supply · trucks</div>'+supplyCards+'</div>'+
        '<div class="rule"></div>'+
        '<div><div class="sidehead dem"><span class="d"></span>Demand · hauls</div>'+demandCards+'</div>'+
      '</div>';

    const L={new:'new',qualified:'qualified',contacted:'sent',replied:'replied',converted:'won',skipped:'skipped',unsubscribed:'opted out',bounced:'bounced',interested:'interested',dead:'dead'};
    const orgs=d.b2b_orgs||{};
    const orgLine=['trial','active','past_due','paused','churned'].filter(k=>orgs[k]!=null)
      .map(k=>esc(k.replace('_',' '))+' <b>'+orgs[k]+'</b>').join(' · ') || 'no accounts yet';
    const pipe=
      '<div class="head">Pipeline</div><div class="pipe'+rv(4)+'">'+
        flow('Haulers', d.outreach_haulers||{}, ['new','qualified','contacted','replied','converted'], L)+
        flow('Business', d.outreach_b2b||{}, ['new','qualified','contacted','replied','converted'], L)+
        '<div class="flow"><span class="fname">Accounts</span><span class="accts">'+orgLine+'</span></div>'+
      '</div>';

    $('out').innerHTML = hero + feed + sides + pipe;
    _first=false;
  }
  if(_tok()) load(); else _showLogin();
</script>
</div></body></html>"""


# ===========================================================================
# Operator Verification dashboard — review automated document checks and
# approve/reject haulers with one click. Mirrors the referral/pricing dashboard
# design system (porcelain + Outfit/DM Sans + red, shared login overlay).
# ===========================================================================
_VERIFICATION_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Umuve — Operator Verification</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Outfit:wght@600;700;800;900&display=swap" rel="stylesheet">
<style>
  :root{--ink:#1a1a1a;--red:#C52222;--mut:#6b6b66;--line:#e8e5df;--bg:#FAF8F5}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:'DM Sans',system-ui,sans-serif}
  .wrap{max-width:1080px;margin:0 auto;padding:2.5rem 1.25rem 4rem}
  h1{font-family:'Outfit',sans-serif;font-weight:800;font-size:1.9rem;letter-spacing:-.02em;margin:0}
  .sub{color:var(--mut);margin:.25rem 0 1.5rem;font-size:.95rem}
  .bar{display:flex;flex-wrap:wrap;gap:.6rem;align-items:center;margin-bottom:1.5rem}
  select{font:inherit;border:1px solid #d6d2ca;border-radius:.55rem;padding:.55rem .7rem;background:#fff}
  button{font:inherit;font-weight:700;background:var(--red);color:#fff;border:0;border-radius:.55rem;padding:.6rem 1.1rem;cursor:pointer}
  button:hover{background:#9E1B1B}
  button.ghost{background:#fff;color:var(--ink);border:1px solid #d6d2ca}
  button.ghost:hover{background:#f3f0ea}
  button.ok{background:#1B7F44}button.ok:hover{background:#156635}
  button.sm{padding:.4rem .8rem;font-size:.85rem}
  .kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:.9rem;margin-bottom:1.5rem}
  @media(max-width:640px){.kpis{grid-template-columns:repeat(2,1fr)}}
  .card{background:#fff;border:1px solid var(--line);border-radius:.9rem;padding:1.1rem 1.2rem}
  .card .l{font-size:.7rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#9a948b}
  .card .v{font-family:'Outfit',sans-serif;font-weight:800;font-size:1.7rem;margin-top:.25rem;letter-spacing:-.02em}
  table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:.9rem;overflow:hidden}
  th,td{padding:.7rem .9rem;text-align:left;font-size:.9rem;border-top:1px solid var(--line)}
  th{background:#f3f0ea;font-size:.7rem;letter-spacing:.06em;text-transform:uppercase;color:#9a948b;border-top:0}
  .tag{display:inline-block;border-radius:999px;padding:.15rem .55rem;font-size:.72rem;font-weight:700;white-space:nowrap}
  .t-green{background:#E9F7EE;color:#1B7F44}
  .t-amber{background:#FEF6E7;color:#9a6700}
  .t-red{background:#FDECEC;color:#B42318}
  .t-blue{background:#EEF2FF;color:#3a4ea8}
  .t-gray{background:#eee;color:#666}
  .muted{color:var(--mut);font-size:.85rem}
  .err{color:var(--red);font-size:.9rem;margin:.5rem 0}
  .who{font-weight:600}.whoe{color:#9a948b;font-size:.78rem}
  /* Detail drawer */
  #detail{display:none;margin-top:1.5rem;background:#fff;border:1px solid var(--line);border-radius:1rem;padding:1.5rem}
  #detail h2{font-family:'Outfit',sans-serif;font-weight:800;margin:0;font-size:1.3rem}
  .docgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:1rem;margin:1.2rem 0}
  .doc{border:1px solid var(--line);border-radius:.8rem;padding:1rem;background:#FCFBF9}
  .doc h3{font-family:'Outfit',sans-serif;font-weight:700;font-size:.95rem;margin:0 0 .5rem;display:flex;justify-content:space-between;align-items:center;gap:.5rem}
  .kv{font-size:.83rem;margin:.2rem 0;color:#3a3a36}
  .kv b{color:#9a948b;font-weight:600;display:inline-block;min-width:5.5rem}
  .reasons{margin:.6rem 0 0;padding-left:1.1rem}
  .reasons li{font-size:.82rem;margin:.15rem 0}
  .reasons li.bad{color:#B42318}
  .actions{display:flex;flex-wrap:wrap;gap:.6rem;margin-top:1.2rem;padding-top:1.2rem;border-top:1px solid var(--line)}
  a.file{font-size:.8rem;color:var(--red);font-weight:600;text-decoration:none}
  a.file:hover{text-decoration:underline}
  .vrow{cursor:pointer}.vrow:hover{background:#FCFBF9}
  .adminnav{display:flex;gap:.4rem;margin-bottom:1.4rem;flex-wrap:wrap}
  .adminnav a{font-size:.85rem;font-weight:700;color:#6b6b66;text-decoration:none;padding:.42rem .85rem;border-radius:999px;border:1px solid transparent}
  .adminnav a:hover{background:#f3f0ea}
  .adminnav a.active{background:#fff;border-color:#e8e5df;color:#1a1a1a;box-shadow:0 1px 2px rgba(0,0,0,.04)}
</style></head><body>
<div id="adminLogin" style="display:none;position:fixed;inset:0;background:#FAF8F5;z-index:100;align-items:center;justify-content:center">
  <div style="background:#fff;border:1px solid #e8e5df;border-radius:1rem;padding:2rem;max-width:340px;width:90%;box-shadow:0 18px 40px rgba(0,0,0,.08)">
    <h2 style="font-family:'Outfit',sans-serif;font-weight:800;margin:0 0 .25rem">Admin sign in</h2>
    <p style="color:#6b6b66;font-size:.9rem;margin:0 0 1.2rem">Sign in with your Umuve admin email &amp; password.</p>
    <input id="al-email" type="email" placeholder="Email" autocomplete="email" style="width:100%;border:1px solid #d6d2ca;border-radius:.55rem;padding:.6rem .7rem;margin-bottom:.6rem;font:inherit;box-sizing:border-box">
    <input id="al-pass" type="password" placeholder="Password" autocomplete="current-password" onkeydown="if(event.key==='Enter')adminLogin()" style="width:100%;border:1px solid #d6d2ca;border-radius:.55rem;padding:.6rem .7rem;margin-bottom:.6rem;font:inherit;box-sizing:border-box">
    <button onclick="adminLogin()" style="width:100%;background:#C52222;color:#fff;border:0;border-radius:.55rem;padding:.65rem;font:inherit;font-weight:700;cursor:pointer">Sign in</button>
    <div id="al-err" style="color:#C52222;font-size:.85rem;margin-top:.6rem"></div>
  </div>
</div>
<div class="wrap">
  <nav class="adminnav">
    <a href="/api/admin/command-center-dashboard">Command Center</a>
    <a href="/api/admin/verification-dashboard" class="active">Verification</a>
    <a href="/api/admin/referral-dashboard">Referrals</a>
    <a href="/api/admin/pricing-dashboard">Pricing</a>
  </nav>
  <h1>Operator Verification</h1>
  <div class="sub">Automated insurance / license / registration checks. Click a hauler to see the extracted fields and approve or reject.</div>
  <div class="bar">
    <select id="status">
      <option value="needs_attention" selected>Needs attention</option>
      <option value="documents_submitted">Submitted</option>
      <option value="under_review">Under review</option>
      <option value="approved">Approved</option>
      <option value="rejected">Rejected</option>
      <option value="all">All</option>
    </select>
    <button onclick="load()">Load</button>
  </div>
  <div id="err" class="err"></div>
  <div id="out" style="display:none">
    <div class="kpis">
      <div class="card"><div class="l">Ready to approve</div><div class="v" id="k_ready">—</div></div>
      <div class="card"><div class="l">Needs review</div><div class="v" id="k_flag">—</div></div>
      <div class="card"><div class="l">Failed / expired</div><div class="v" id="k_fail">—</div></div>
      <div class="card"><div class="l">Approved</div><div class="v" id="k_appr">—</div></div>
    </div>
    <table><thead><tr>
      <th>Hauler</th><th>Onboarding</th><th>Verification</th><th>Documents</th><th></th>
    </tr></thead><tbody id="rows"></tbody></table>
    <p class="muted" id="meta" style="margin-top:1rem"></p>
  </div>
  <div id="detail"></div>
<script>
  const $=id=>document.getElementById(id);
  const TOKEN_KEY='umuve_admin_token';
  function _tok(){ return localStorage.getItem(TOKEN_KEY)||''; }
  function H(){ return {Authorization:'Bearer '+_tok()}; }
  function esc(s){ return (s==null?'':String(s)).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
  function _showLogin(msg){ document.getElementById('adminLogin').style.display='flex'; var o=$('out'); if(o) o.style.display='none'; if(msg) $('al-err').textContent=msg; }
  function _hideLogin(){ document.getElementById('adminLogin').style.display='none'; }
  async function adminLogin(){
    var email=($('al-email').value||'').trim().toLowerCase(); var pass=$('al-pass').value;
    $('al-err').textContent='';
    if(!email||!pass){ $('al-err').textContent='Enter email and password.'; return; }
    try{
      var r=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email,password:pass})});
      var b=await r.json().catch(function(){return{};});
      if(r.ok&&b.token){ localStorage.setItem(TOKEN_KEY,b.token); _hideLogin(); load(); }
      else { $('al-err').textContent=(b&&b.error)||'Sign in failed.'; }
    }catch(e){ $('al-err').textContent='Network error.'; }
  }
  // ---- Tag helpers ----
  const V_TAG={passed:['green','Verified'],flagged:['amber','Needs review'],failed:['red','Failed'],verifying:['blue','Verifying…'],not_checked:['gray','Not checked']};
  const O_TAG={approved:['green','Approved'],under_review:['amber','Under review'],documents_submitted:['amber','Submitted'],rejected:['red','Rejected'],pending:['gray','Pending']};
  function tag(map,k){ const m=map[k]||['gray',k||'—']; return '<span class="tag t-'+m[0]+'">'+esc(m[1])+'</span>'; }
  const DOCT={insurance:'Insurance',drivers_license:"Driver's license",vehicle_registration:'Registration'};
  function who(a){ return '<div class="who">'+esc(a.name||a.email||'Unknown')+'</div>'+(a.email?'<div class="whoe">'+esc(a.email)+(a.phone?' · '+esc(a.phone):'')+'</div>':''); }
  function docDots(a){
    const map=[['insurance',a.insurance_document_url],['drivers_license',a.drivers_license_url],['vehicle_registration',a.vehicle_registration_url]];
    return map.map(([k,u])=>'<span title="'+DOCT[k]+'" style="opacity:'+(u?1:.25)+'">'+(u?'●':'○')+'</span>').join(' ');
  }
  let CURRENT=[];
  async function load(){
    $('err').textContent=''; $('detail').style.display='none';
    const sel=$('status').value;
    const qs = (sel==='all'||sel==='needs_attention') ? 'per_page=200' : 'status='+encodeURIComponent(sel)+'&per_page=200';
    try{
      const r=await fetch('/api/admin/onboarding/applications?'+qs,{headers:H()});
      if(r.status===401){ _showLogin('Please sign in.'); return; }
      if(r.status===403){ _showLogin('That account is not an admin.'); return; }
      if(!r.ok){ $('err').textContent='Error '+r.status; return; }
      _hideLogin(); const d=await r.json();
      let apps=d.applications||[];
      if(sel==='needs_attention') apps=apps.filter(a=>['documents_submitted','under_review'].includes(a.onboarding_status)||a.documents_verification_status==='flagged');
      render(apps, d.total);
    }catch(e){ $('err').textContent='Request failed: '+e; }
  }
  function render(apps,total){
    CURRENT=apps; $('out').style.display='block';
    const cnt=s=>apps.filter(s).length;
    $('k_ready').textContent=cnt(a=>a.documents_verification_status==='passed'&&a.onboarding_status!=='approved');
    $('k_flag').textContent=cnt(a=>a.documents_verification_status==='flagged');
    $('k_fail').textContent=cnt(a=>a.documents_verification_status==='failed');
    $('k_appr').textContent=cnt(a=>a.onboarding_status==='approved');
    $('rows').innerHTML = apps.length ? apps.map((a,i)=>
      '<tr class="vrow" onclick="openDetail('+i+')"><td>'+who(a)+'</td>'+
      '<td>'+tag(O_TAG,a.onboarding_status)+'</td>'+
      '<td>'+tag(V_TAG,a.documents_verification_status)+'</td>'+
      '<td style="font-size:1.05rem;letter-spacing:.1rem;color:#1B7F44">'+docDots(a)+'</td>'+
      '<td><button class="ghost sm" onclick="event.stopPropagation();openDetail('+i+')">View</button></td></tr>'
    ).join('') : '<tr><td colspan="5" style="text-align:center;color:#9a948b;padding:2rem">Nothing here. Try a different filter.</td></tr>';
    $('meta').textContent=apps.length+' shown'+(total!=null?' · '+total+' total in this status':'')+'. ● = uploaded, ○ = missing.';
  }
  function fdate(d){ return d? new Date(d).toLocaleDateString():'—'; }
  function closeDetail(){ document.getElementById('detail').style.display='none'; }
  async function openDetail(i){
    const a=CURRENT[i]; const box=$('detail');
    box.style.display='block'; box.scrollIntoView({behavior:'smooth',block:'nearest'});
    box.innerHTML='<p class="muted">Loading verification…</p>';
    let v={documents:{}};
    try{ const r=await fetch('/api/admin/onboarding/'+a.id+'/verification',{headers:H()}); if(r.ok) v=await r.json(); }catch(e){}
    const docs=v.documents||{};
    const order=['insurance','drivers_license','vehicle_registration'];
    const docCards=order.map(k=>{
      const d=docs[k]; const url=[a.insurance_document_url,a.drivers_license_url,a.vehicle_registration_url][order.indexOf(k)];
      const ex=(d&&d.extracted)||{};
      const st=d? (d.status==='verified'?['green','Verified']:d.status==='rejected'?['red','Rejected']:d.status==='needs_review'?['amber','Review']:['gray',d.status]) : ['gray','Not run'];
      const reasons=(d&&d.reasons||[]).map(x=>{const bad=/expired|wrong|tamper|hard to read|doesn|could not|unavailable/i.test(x);return '<li class="'+(bad?'bad':'')+'">'+esc(x)+'</li>';}).join('');
      return '<div class="doc"><h3>'+DOCT[k]+' <span class="tag t-'+st[0]+'">'+st[1]+'</span></h3>'+
        '<div class="kv"><b>On file</b>'+esc(ex.full_name||'—')+'</div>'+
        '<div class="kv"><b>Expires</b>'+fdate(d&&d.expiry_date)+'</div>'+
        '<div class="kv"><b>ID #</b>'+esc(ex.id_number||'—')+'</div>'+
        '<div class="kv"><b>Issuer</b>'+esc(ex.issuer||'—')+'</div>'+
        (d&&d.confidence!=null?'<div class="kv"><b>Confidence</b>'+Math.round(d.confidence*100)+'%</div>':'')+
        (reasons?'<ul class="reasons">'+reasons+'</ul>':'')+
        (url?'<div style="margin-top:.6rem"><a class="file" href="'+esc(url)+'" target="_blank" rel="noopener">View uploaded file ↗</a></div>':'<div class="muted" style="margin-top:.6rem">No file uploaded</div>')+
        '</div>';
    }).join('');
    box.innerHTML='<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;flex-wrap:wrap">'+
      '<div><h2>'+esc(a.name||a.email||'Hauler')+'</h2><div class="muted">'+esc(a.email||'')+(a.phone?' · '+esc(a.phone):'')+'</div>'+
      '<div style="margin-top:.5rem">'+tag(O_TAG,a.onboarding_status)+' '+tag(V_TAG,a.documents_verification_status)+(v.verified_at?'<span class="muted"> · checked '+fdate(v.verified_at)+'</span>':'')+'</div></div>'+
      '<button class="ghost sm" onclick="closeDetail()">Close</button></div>'+
      '<div class="docgrid">'+docCards+'</div>'+
      '<div class="actions">'+
        '<button class="ok" onclick="review(\\''+a.id+'\\',\\'approve\\')">Approve hauler</button>'+
        '<button onclick="review(\\''+a.id+'\\',\\'reject\\')">Reject…</button>'+
        '<button class="ghost" onclick="reverify(\\''+a.id+'\\')">Re-run verification</button>'+
      '</div><div id="aerr" class="err"></div>';
  }
  async function review(id,action){
    const body={action:action};
    if(action==='reject'){ const why=prompt('Reason for rejection (the hauler will see this):'); if(!why) return; body.rejection_reason=why; }
    try{
      const r=await fetch('/api/admin/onboarding/'+id+'/review',{method:'PUT',headers:Object.assign({'Content-Type':'application/json'},H()),body:JSON.stringify(body)});
      if(!r.ok){ const b=await r.json().catch(()=>({})); $('aerr').textContent=(b&&b.error)||('Error '+r.status); return; }
      $('detail').style.display='none'; load();
    }catch(e){ $('aerr').textContent='Request failed: '+e; }
  }
  async function reverify(id){
    const e=$('aerr'); if(e) e.textContent='';
    try{
      const r=await fetch('/api/admin/onboarding/'+id+'/verify',{method:'POST',headers:H()});
      if(!r.ok){ if(e) e.textContent='Error '+r.status; return; }
      if(e){ e.style.color='#1B7F44'; e.textContent='Re-running… reload in ~20s to see results.'; }
    }catch(err){ if(e) e.textContent='Request failed: '+err; }
  }
  if(_tok()) load(); else _showLogin();
</script>
</div></body></html>"""


# ---------------------------------------------------------------------------
# Pricing analytics — quote -> book conversion + platform revenue, banded by
# price. This is the lever for tuning the binding quote toward the price that
# maximizes (conversion x take), instead of guessing.
# ---------------------------------------------------------------------------
_PRICE_BANDS = [(0, 100), (100, 150), (150, 250), (250, 400),
                (400, 700), (700, 1500), (1500, None)]


def _band_label(lo, hi):
    return "${}+".format(lo) if hi is None else "${}–${}".format(lo, hi)


@admin_bp.route("/pricing-analytics", methods=["GET"])
@require_admin
def pricing_analytics(user_id):
    """Quote->book conversion + platform revenue, banded by quoted price.

    A quote counts as converted when it reached 'booked' (or has a booking_id /
    booked_at). Platform revenue per booked job = price * take_rate. Query param
    ?days=N (default 90, clamped 1..365).
    """
    from pricing_config import platform_take_rate

    try:
        days = max(1, min(365, int(request.args.get("days", 90))))
    except (TypeError, ValueError):
        days = 90
    since = utcnow() - timedelta(days=days)
    take = platform_take_rate()

    quotes = Quote.query.filter(Quote.created_at >= since).all()

    def band_for(dollars):
        for lo, hi in _PRICE_BANDS:
            if dollars >= lo and (hi is None or dollars < hi):
                return _band_label(lo, hi)
        return _band_label(*_PRICE_BANDS[-1])

    def is_booked(q):
        return q.status == "booked" or q.booking_id is not None or q.booked_at is not None

    rows = {
        _band_label(lo, hi): {"band": _band_label(lo, hi), "quoted": 0,
                              "booked": 0, "price_sum": 0.0, "revenue": 0.0}
        for lo, hi in _PRICE_BANDS
    }
    tot = {"quoted": 0, "booked": 0, "revenue": 0.0, "price_sum": 0.0}
    conf = {"binding": {"quoted": 0, "booked": 0},
            "non_binding": {"quoted": 0, "booked": 0}}

    for q in quotes:
        dollars = (q.price_cents or 0) / 100.0
        r = rows[band_for(dollars)]
        r["quoted"] += 1
        r["price_sum"] += dollars
        tot["quoted"] += 1
        tot["price_sum"] += dollars
        ck = "binding" if q.binding else "non_binding"
        conf[ck]["quoted"] += 1
        if is_booked(q):
            rev = dollars * take
            r["booked"] += 1
            r["revenue"] += rev
            tot["booked"] += 1
            tot["revenue"] += rev
            conf[ck]["booked"] += 1

    def pct(b, q):
        return round(100.0 * b / q, 1) if q else 0.0

    bands = []
    for lo, hi in _PRICE_BANDS:
        r = rows[_band_label(lo, hi)]
        bands.append({
            "band": r["band"],
            "quoted": r["quoted"],
            "booked": r["booked"],
            "conversion": pct(r["booked"], r["quoted"]),
            "avg_price": round(r["price_sum"] / r["quoted"], 2) if r["quoted"] else 0.0,
            "revenue": round(r["revenue"], 2),
        })

    return jsonify({
        "window_days": days,
        "take_rate": round(take, 4),
        "overall": {
            "quoted": tot["quoted"],
            "booked": tot["booked"],
            "conversion": pct(tot["booked"], tot["quoted"]),
            "avg_quote": round(tot["price_sum"] / tot["quoted"], 2) if tot["quoted"] else 0.0,
            "platform_revenue": round(tot["revenue"], 2),
            "avg_take_per_job": round(tot["revenue"] / tot["booked"], 2) if tot["booked"] else 0.0,
        },
        "by_price_band": bands,
        "by_confidence": {
            "binding": {**conf["binding"], "conversion": pct(conf["binding"]["booked"], conf["binding"]["quoted"])},
            "non_binding": {**conf["non_binding"], "conversion": pct(conf["non_binding"]["booked"], conf["non_binding"]["quoted"])},
        },
    })


@admin_bp.route("/pricing-dashboard", methods=["GET"])
def pricing_dashboard():
    """Self-contained pricing/conversion dashboard page. The page is public;
    the data call it makes is admin-gated, so paste an admin token once (stored
    in your browser only)."""
    from flask import Response
    return Response(_PRICING_DASHBOARD_HTML, mimetype="text/html")


# ---------------------------------------------------------------------------
# Referral payouts — watch the supply-side referral spend (who got paid, totals)
# ---------------------------------------------------------------------------
@admin_bp.route("/outreach-run", methods=["POST"])
@require_admin
def outreach_run(user_id):
    """Fire the operator-outreach cycle on demand (instead of waiting for the
    14:00 UTC cron). Runs in a background thread so it can't time out; the
    report is emailed to OUTREACH_REPORT_TO/ADMIN_EMAIL when it finishes.

    ?preview=1  -> source + draft + report only, sends NOTHING (safe test).
    default     -> a real run (sends if the engine is configured LIVE).
    """
    import threading
    from flask import current_app
    from operator_outreach import run_outreach_cycle, _cfg, _can_send

    preview = (request.args.get("preview") or "").lower() in ("1", "true", "yes")
    app_obj = current_app._get_current_object()
    cfg = _cfg()
    will_send = bool(_can_send(cfg) and cfg["places_key"]) and not preview

    threading.Thread(
        target=run_outreach_cycle, args=(app_obj,),
        kwargs={"force_dry": preview}, daemon=True,
    ).start()

    return jsonify({
        "started": True,
        "preview": preview,
        "will_send": will_send,
        "message": ("Preview run started — sources + drafts only, no emails sent."
                    if not will_send else
                    "Live run started — sending up to the daily cap now."),
        "report_emailed_to": cfg["report_to"] or None,
        "note": "The full report (sourced/qualified/sent) is emailed in ~1-2 min.",
    }), 202


@admin_bp.route("/outreach-status", methods=["GET"])
@require_admin
def outreach_status(user_id):
    """Whether the daily operator-outreach engine is configured to actually send.

    No secrets returned (booleans for keys), and it never sends — just reports
    the effective mode so you can confirm your Render env took effect.
    """
    from operator_outreach import _cfg, _can_send
    cfg = _cfg()
    live = bool(_can_send(cfg) and cfg["places_key"])
    missing = [name for name, ok in (
        ("GOOGLE_PLACES_API_KEY", cfg["places_key"]),
        ("OUTREACH_FROM", cfg["from"]),
        ("OUTREACH_POSTAL_ADDRESS", cfg["postal"]),
        ("OUTREACH_SEND_ENABLED=true", cfg["send_enabled"]),
    ) if not ok]
    return jsonify({
        "mode": "LIVE — sends daily at 14:00 UTC" if live else "DRY RUN — sends nothing",
        "live": live,
        "config": {
            "google_places_key_set": bool(cfg["places_key"]),
            "outreach_from": cfg["from"] or None,
            "postal_address_set": bool(cfg["postal"]),
            "send_enabled": cfg["send_enabled"],
            "daily_cap": cfg["daily_cap"],
            "report_to": cfg["report_to"] or None,
            "target_zips": cfg["zips"],
        },
        "missing_to_go_live": missing,
    })


def _check_seed_secret():
    """Simple shared-secret gate for admin one-offs (browser/curl friendly).
    Accepts ?secret=<ADMIN_SEED_SECRET> or an X-Admin-Secret header."""
    expected = os.environ.get("ADMIN_SEED_SECRET", "")
    got = request.args.get("secret") or request.headers.get("X-Admin-Secret", "")
    return bool(expected) and got == expected


@admin_bp.route("/outreach/run", methods=["GET", "POST"])
def outreach_run_now():
    """Run the recruiting outreach on demand instead of waiting for the 14:00 UTC cron.

    Secured by ADMIN_SEED_SECRET (?secret= or X-Admin-Secret header).
    SAFE BY DEFAULT: a source-only preview (force_dry) — sources + qualifies leads
    but sends NO email. Pass ?send=1 to actually send (and it only really sends if
    the Render env is configured live). ?engine=operator (default) | b2b | both.
    """
    if not _check_seed_secret():
        return jsonify({"error": "Forbidden"}), 403
    send = request.args.get("send") == "1"
    engine = (request.args.get("engine") or "operator").strip().lower()
    app = current_app._get_current_object()
    report = {}
    if engine in ("operator", "both"):
        from operator_outreach import run_outreach_cycle
        report["operator"] = run_outreach_cycle(app, force_dry=not send)
    if engine in ("b2b", "both"):
        from b2b_outreach import run_b2b_outreach_cycle
        report["b2b"] = run_b2b_outreach_cycle(app, force_dry=not send)
    return jsonify({
        "ok": True,
        "mode": "LIVE SEND" if send else "DRY RUN (sourced leads only, no email sent)",
        "report": report,
        "next": "Download the sourced leads: GET /api/admin/outreach/leads.csv?secret=…",
    })


@admin_bp.route("/outreach/leads.csv", methods=["GET"])
def outreach_leads_csv():
    """Export sourced hauler leads in the caller-kit tracker CSV format.

    Secured by ADMIN_SEED_SECRET (?secret= or X-Admin-Secret header) — open in a
    browser to download. Only leads WITH a phone, newest first, suppressed
    statuses excluded. Optional: ?limit=N (default 500), ?city=, ?status=.
    """
    if not _check_seed_secret():
        return jsonify({"error": "Forbidden"}), 403
    import csv
    import io
    from flask import Response
    from models import OperatorLead
    try:
        limit = max(1, min(2000, int(request.args.get("limit", 500))))
    except (TypeError, ValueError):
        limit = 500
    q = OperatorLead.query.filter(
        OperatorLead.phone.isnot(None),
        OperatorLead.phone != "",
        OperatorLead.status.notin_(["unsubscribed", "bounced", "converted", "skipped"]),
    )
    city = request.args.get("city")
    if city:
        q = q.filter(OperatorLead.city.ilike("%{}%".format(city)))
    status = request.args.get("status")
    if status:
        q = q.filter(OperatorLead.status == status)
    leads = q.order_by(OperatorLead.created_at.desc()).limit(limit).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["priority", "company", "contact", "phone", "city", "email",
                     "status", "outcome", "next_step", "called_on", "notes"])
    for i, lead in enumerate(leads, 1):
        note = "[{}]".format(lead.status)
        if lead.website:
            note += " " + lead.website
        if lead.notes:
            note += " " + lead.notes
        writer.writerow([i, lead.business_name or "", "", lead.phone or "",
                         lead.city or "", lead.email or "", "Not called",
                         "", "", "", note.strip()])
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=hauler_leads.csv"},
    )


@admin_bp.route("/referral-payouts", methods=["GET"])
@require_admin
def referral_payouts(user_id):
    """Contractor (hauler) referral payouts: status, who, and totals.

    A 'contractor' referral pays BOTH haulers reward_amount on the referred
    hauler's first completed job (see payments.pay_referral_bonus). Money totals
    are status-based approximations (we don't store per-transfer rows):
      rewarded  -> both paid     -> counts as 2 x reward 'paid out'
      completed -> earned, not fully paid -> 2 x reward 'pending'
      signed_up -> linked, awaiting first job
    Query param ?days=N (default 365, clamped 1..730).
    """
    try:
        days = max(1, min(730, int(request.args.get("days", 365))))
    except (TypeError, ValueError):
        days = 365
    since = utcnow() - timedelta(days=days)

    try:
        from routes.referrals import CONTRACTOR_REFERRAL_BONUS as _bonus
    except Exception:
        _bonus = 100.0

    refs = (
        db.session.query(Referral)
        .filter(Referral.referral_type == "contractor", Referral.created_at >= since)
        .order_by(Referral.created_at.desc())
        .all()
    )

    uids = set()
    for r in refs:
        uids.add(r.referrer_id)
        uids.add(r.referee_id)
    uids.discard(None)
    users = {}
    if uids:
        users = {u.id: u for u in db.session.query(User).filter(User.id.in_(uids)).all()}

    def who(uid):
        u = users.get(uid)
        if not u:
            return {"name": None, "email": None}
        return {"name": u.name, "email": u.email}

    # Precise spend from the payout ledger (one row per referral+role).
    ref_ids = [r.id for r in refs]
    paid_by_ref = defaultdict(float)
    paid_out = 0.0
    transfers_count = 0
    if ref_ids:
        for p in (db.session.query(ReferralPayout)
                  .filter(ReferralPayout.referral_id.in_(ref_ids)).all()):
            if p.status == "paid":
                amt = float(p.amount or 0.0)
                paid_out += amt
                paid_by_ref[p.referral_id] += amt
                transfers_count += 1

    pending = 0.0
    counts = {"rewarded": 0, "completed": 0, "signed_up": 0, "other": 0}
    rows = []
    for r in refs:
        bonus = float(r.reward_amount or 0.0)
        both = round(bonus * 2, 2)
        counts[r.status if r.status in counts else "other"] += 1
        paid_ref = round(paid_by_ref.get(r.id, 0.0), 2)
        # Owed = what both haulers earn (once the referral lands) minus what we've
        # actually transferred. Only earned states (completed/rewarded) owe.
        owed = round(max(0.0, both - paid_ref), 2) if r.status in ("completed", "rewarded") else 0.0
        pending += owed
        rows.append({
            "id": r.id,
            "referrer": who(r.referrer_id),
            "referee": who(r.referee_id),
            "status": r.status,
            "bonus_each": bonus,
            "total_if_both": both,
            "paid": paid_ref,
            "owed": owed,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        })

    return jsonify({
        "window_days": days,
        "bonus_per_hauler": _bonus,
        "summary": {
            "total": len(refs),
            "rewarded": counts["rewarded"],
            "completed_unpaid": counts["completed"],
            "signed_up": counts["signed_up"],
            "paid_out": round(paid_out, 2),
            "transfers": transfers_count,
            "pending_payout": round(pending, 2),
        },
        "referrals": rows,
    })


@admin_bp.route("/outreach/leads", methods=["GET"])
@require_admin
def outreach_leads(user_id):
    """List recruiting leads for follow-up, newest-touched first. Filter by
    ?status= (e.g. replied) or ?q= (name/email substring). Includes a status
    breakdown so you can see how the funnel is moving."""
    from models import OperatorLead

    status = (request.args.get("status") or "").strip()
    q = (request.args.get("q") or "").strip().lower()
    limit = min(int(request.args.get("limit", 100)), 500)

    query = OperatorLead.query
    if status:
        query = query.filter(OperatorLead.status == status)
    if q:
        like = "%{}%".format(q)
        query = query.filter(db.or_(
            db.func.lower(OperatorLead.business_name).like(like),
            db.func.lower(OperatorLead.email).like(like),
        ))
    rows = query.order_by(OperatorLead.updated_at.desc()).limit(limit).all()

    # Status breakdown across ALL leads (not just the filtered page).
    counts = {}
    for st, n in db.session.query(OperatorLead.status, db.func.count(OperatorLead.id)).group_by(OperatorLead.status).all():
        counts[st] = n

    return jsonify({
        "success": True,
        "counts": counts,
        "total": sum(counts.values()),
        "leads": [l.to_dict() for l in rows],
    }), 200


@admin_bp.route("/outreach/leads/<lead_id>", methods=["POST"])
@require_admin
def update_outreach_lead(user_id, lead_id):
    """Update a lead's status and/or append a note. Body: {status?, note?}."""
    from models import OperatorLead, utcnow

    lead = db.session.get(OperatorLead, lead_id)
    if not lead:
        return jsonify({"error": "Lead not found"}), 404

    data = request.get_json() or {}
    new_status = (data.get("status") or "").strip()
    note = (data.get("note") or "").strip()
    allowed = {"new", "qualified", "contacted", "replied", "interested",
               "converted", "skipped", "bounced", "unsubscribed", "dead"}
    if new_status:
        if new_status not in allowed:
            return jsonify({"error": "Invalid status. Allowed: {}".format(sorted(allowed))}), 400
        lead.status = new_status
    if note:
        import time as _t
        stamp = _t.strftime("%Y-%m-%d %H:%M", _t.gmtime())
        entry = "[{}] {}".format(stamp, note)
        lead.notes = (lead.notes + "\n" + entry) if lead.notes else entry
    lead.updated_at = utcnow()
    db.session.commit()
    return jsonify({"success": True, "lead": lead.to_dict()}), 200


@admin_bp.route("/b2b/leads", methods=["GET"])
@require_admin
def b2b_leads(user_id):
    """B2B customer-acquisition leads for follow-up. ?status= / ?q= filters +
    status breakdown across the whole funnel."""
    from models import B2BLead

    status = (request.args.get("status") or "").strip()
    q = (request.args.get("q") or "").strip().lower()
    limit = min(int(request.args.get("limit", 100)), 500)

    query = B2BLead.query
    if status:
        query = query.filter(B2BLead.status == status)
    if q:
        like = "%{}%".format(q)
        query = query.filter(db.or_(
            db.func.lower(B2BLead.business_name).like(like),
            db.func.lower(B2BLead.email).like(like),
        ))
    rows = query.order_by(B2BLead.updated_at.desc()).limit(limit).all()

    counts = {}
    for st, n in db.session.query(B2BLead.status, db.func.count(B2BLead.id)).group_by(B2BLead.status).all():
        counts[st] = n

    return jsonify({
        "success": True,
        "counts": counts,
        "total": sum(counts.values()),
        "leads": [l.to_dict() for l in rows],
    }), 200


@admin_bp.route("/b2b/leads/<lead_id>", methods=["POST"])
@require_admin
def update_b2b_lead(user_id, lead_id):
    """Update a B2B lead's status and/or append a note. Body: {status?, note?}."""
    from models import B2BLead, utcnow

    lead = db.session.get(B2BLead, lead_id)
    if not lead:
        return jsonify({"error": "Lead not found"}), 404

    data = request.get_json() or {}
    new_status = (data.get("status") or "").strip()
    note = (data.get("note") or "").strip()
    allowed = {"new", "qualified", "contacted", "replied", "interested",
               "converted", "skipped", "bounced", "unsubscribed", "dead"}
    if new_status:
        if new_status not in allowed:
            return jsonify({"error": "Invalid status. Allowed: {}".format(sorted(allowed))}), 400
        lead.status = new_status
    if note:
        import time as _t
        stamp = _t.strftime("%Y-%m-%d %H:%M", _t.gmtime())
        entry = "[{}] {}".format(stamp, note)
        lead.notes = (lead.notes + "\n" + entry) if lead.notes else entry
    lead.updated_at = utcnow()
    db.session.commit()
    return jsonify({"success": True, "lead": lead.to_dict()}), 200


@admin_bp.route("/demand/signals", methods=["GET"])
@require_admin
def demand_signals(user_id):
    """Public-records demand signals (code violations / probate / evictions)
    for review. ?record_type= / ?status= / ?city= filters, ?days=N recency,
    plus a breakdown so the funnel is visible at a glance."""
    from models import DemandRecord

    record_type = (request.args.get("record_type") or "").strip()
    status = (request.args.get("status") or "").strip()
    city = (request.args.get("city") or "").strip()
    limit = min(int(request.args.get("limit", 100)), 500)

    query = DemandRecord.query
    if record_type:
        query = query.filter(DemandRecord.record_type == record_type)
    if status:
        query = query.filter(DemandRecord.status == status)
    if city:
        query = query.filter(DemandRecord.city.ilike("%{}%".format(city)))
    days = request.args.get("days")
    if days:
        import datetime as _dt
        try:
            cutoff = _dt.datetime.utcnow() - _dt.timedelta(days=max(1, int(days)))
            query = query.filter(DemandRecord.created_at >= cutoff)
        except (TypeError, ValueError):
            pass
    rows = query.order_by(DemandRecord.created_at.desc()).limit(limit).all()

    counts = {}
    for rt, st, n in db.session.query(
        DemandRecord.record_type, DemandRecord.status, db.func.count(DemandRecord.id)
    ).group_by(DemandRecord.record_type, DemandRecord.status).all():
        counts.setdefault(rt, {})[st] = n

    return jsonify({
        "success": True,
        "counts": counts,
        "total": sum(n for by_status in counts.values() for n in by_status.values()),
        "signals": [s.to_dict() for s in rows],
    }), 200


@admin_bp.route("/demand/signals/<signal_id>", methods=["POST"])
@require_admin
def update_demand_signal(user_id, signal_id):
    """Update a demand signal's status and/or append a note. Body: {status?, note?}."""
    from models import DemandRecord, utcnow

    sig = db.session.get(DemandRecord, signal_id)
    if not sig:
        return jsonify({"error": "Signal not found"}), 404

    data = request.get_json() or {}
    new_status = (data.get("status") or "").strip()
    note = (data.get("note") or "").strip()
    allowed = {"new", "reviewed", "contacted", "converted", "skipped"}
    if new_status:
        if new_status not in allowed:
            return jsonify({"error": "Invalid status. Allowed: {}".format(sorted(allowed))}), 400
        sig.status = new_status
    if note:
        import time as _t
        stamp = _t.strftime("%Y-%m-%d %H:%M", _t.gmtime())
        entry = "[{}] {}".format(stamp, note)
        sig.notes = (sig.notes + "\n" + entry) if sig.notes else entry
    sig.updated_at = utcnow()
    db.session.commit()
    return jsonify({"success": True, "signal": sig.to_dict()}), 200


@admin_bp.route("/demand/signals.csv", methods=["GET"])
def demand_signals_csv():
    """CSV export of demand signals — browser-downloadable for the call desk /
    letter runs. Secured by ADMIN_SEED_SECRET (?secret= or X-Admin-Secret),
    same as the other CSV exports. Optional: ?status=, ?days=N."""
    if not _check_seed_secret():
        return jsonify({"error": "Forbidden"}), 403
    from flask import Response
    from models import DemandRecord
    from demand_records import signals_csv

    days = None
    try:
        days = max(1, int(request.args.get("days"))) if request.args.get("days") else None
    except (TypeError, ValueError):
        pass
    csv_text = signals_csv(db, DemandRecord, status=request.args.get("status") or None, days=days)
    return Response(
        csv_text, mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=umuve-demand-signals.csv"},
    )


@admin_bp.route("/demand/ingest-report", methods=["POST"])
@require_admin
def demand_ingest_report(user_id):
    """Ingest a purchased PBC Clerk Cart report (Decedent 07 probate weekly /
    Evictions 06 weekly) into demand signals. Multipart form: file=<csv|xlsx>,
    record_type=probate|eviction. Fuzzy header matching — returns which
    columns mapped so a bad layout is obvious immediately."""
    from models import DemandRecord
    from demand_records import ingest_clerk_report

    record_type = (request.form.get("record_type") or "").strip()
    if record_type not in ("probate", "eviction"):
        return jsonify({"error": "record_type must be 'probate' or 'eviction'"}), 400
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "Attach the report as multipart field 'file' (.csv or .xlsx)"}), 400
    try:
        report = ingest_clerk_report(db, DemandRecord, f, record_type)
    except Exception as exc:
        return jsonify({"error": "Could not parse report: {}".format(str(exc)[:200])}), 422
    if not report["columns_mapped"]:
        return jsonify({"error": "No recognizable header row found", "report": report}), 422
    return jsonify({"success": True, "report": report}), 200


@admin_bp.route("/demand/records-run", methods=["GET", "POST"])
def demand_records_run():
    """Fire the public-records demand sweep on demand (vs the daily cron).
    ADMIN_SEED_SECRET-gated (?secret= / X-Admin-Secret) like /outreach/run so
    it's browser/curl-triggerable. Background thread; digest emailed when
    done. Observe-only: nothing is sent to the people in the records."""
    if not _check_seed_secret():
        return jsonify({"error": "Forbidden"}), 403
    import threading
    from flask import current_app
    from demand_records import run_demand_records_cycle

    app_obj = current_app._get_current_object()
    threading.Thread(
        target=run_demand_records_cycle, args=(app_obj,), daemon=True
    ).start()
    return jsonify({
        "success": True,
        "message": "Demand-records sweep started in background.",
        "next": "Review: GET /api/admin/demand/signals · CSV: /api/admin/demand/signals.csv?secret=…",
    }), 202


@admin_bp.route("/b2b-outreach-run", methods=["POST"])
@require_admin
def b2b_outreach_run(user_id):
    """Fire the B2B customer-outreach cycle on demand (vs the 15:00 UTC cron).
    Background thread; report emailed when done.
    ?preview=1 -> source + draft + report only, sends NOTHING."""
    import threading
    from flask import current_app
    from b2b_outreach import run_b2b_outreach_cycle, _cfg, _can_send

    preview = (request.args.get("preview") or "").lower() in ("1", "true", "yes")
    app_obj = current_app._get_current_object()
    cfg = _cfg()
    will_send = bool(_can_send(cfg) and cfg["places_key"]) and not preview

    threading.Thread(
        target=run_b2b_outreach_cycle, args=(app_obj,),
        kwargs={"force_dry": preview}, daemon=True,
    ).start()

    return jsonify({
        "started": True,
        "preview": preview,
        "will_send": will_send,
        "message": ("Preview run started — sources + drafts only, no emails sent."
                    if not will_send else
                    "Live run started — emailing businesses up to the daily cap now."),
        "report_emailed_to": cfg["report_to"] or None,
        "note": "The full report (sourced/qualified/sent) is emailed in ~1-2 min.",
    }), 202


@admin_bp.route("/orgs", methods=["GET"])
@require_admin
def list_orgs(user_id):
    """List B2B portal orgs with owner contact + engagement signals, for
    personalized outreach. ?status=trial to filter (default all)."""
    from models import Org, OrgMember, User, PortalProperty
    from datetime import timezone as _tz

    status = (request.args.get("status") or "").strip()
    query = Org.query
    if status:
        query = query.filter(Org.status == status)
    orgs = query.order_by(Org.created_at.desc()).limit(500).all()

    now = utcnow()
    out = []
    for o in orgs:
        # Owner contact (fall back to any member, then billing_email).
        owner = (
            db.session.query(User)
            .join(OrgMember, OrgMember.user_id == User.id)
            .filter(OrgMember.org_id == o.id, OrgMember.role == "owner")
            .first()
        )
        if owner is None:
            owner = (
                db.session.query(User)
                .join(OrgMember, OrgMember.user_id == User.id)
                .filter(OrgMember.org_id == o.id)
                .first()
            )
        member_count = db.session.query(OrgMember).filter_by(org_id=o.id).count()
        property_count = db.session.query(PortalProperty).filter_by(org_id=o.id).count()
        age_days = None
        if o.created_at:
            created = o.created_at if o.created_at.tzinfo else o.created_at.replace(tzinfo=_tz.utc)
            age_days = (now - created).days

        out.append({
            "id": o.id,
            "name": o.name,
            "status": o.status,
            "tier": o.tier,
            "billing_email": o.billing_email,
            "owner_name": (owner.name if owner else None),
            "owner_email": (owner.email if owner else None),
            "owner_phone": (owner.phone if owner else None),
            "members": member_count,
            "properties": property_count,
            "has_stripe_customer": bool(o.stripe_customer_id),
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "age_days": age_days,
        })

    return jsonify({"success": True, "count": len(out), "orgs": out}), 200


@admin_bp.route("/orgs/<org_id>", methods=["DELETE"])
@require_admin
def delete_org(user_id, org_id):
    """Delete a B2B org by explicit ID (cascades to its members/properties/
    invoices). SAFETY: refuses any org that has a Stripe customer or
    subscription attached — those must be cancelled in Stripe first, so a real
    billed account can never be deleted by accident. Returns what was removed."""
    from models import Org

    org = db.session.get(Org, org_id)
    if not org:
        return jsonify({"error": "Org not found"}), 404

    if org.stripe_customer_id or org.stripe_subscription_id:
        return jsonify({
            "error": "Refusing to delete — this org has Stripe billing attached. "
                     "Cancel/delete it in Stripe first.",
            "org": {"id": org.id, "name": org.name, "status": org.status,
                    "stripe_customer_id": org.stripe_customer_id},
        }), 409

    removed = {"id": org.id, "name": org.name, "billing_email": org.billing_email,
               "status": org.status}
    db.session.delete(org)
    db.session.commit()
    return jsonify({"success": True, "deleted": removed}), 200


@admin_bp.route("/waitlist", methods=["GET"])
@require_admin
def waitlist_leads(user_id):
    """No-coverage waitlist customers (demand in areas without a hauler yet).
    ?notified=0|1 to filter on whether they've been told we're live."""
    from models import AbandonedBooking

    notified = request.args.get("notified")
    limit = min(int(request.args.get("limit", 200)), 500)
    query = AbandonedBooking.query.filter(
        AbandonedBooking.lead_source == "no_coverage_waitlist"
    )
    if notified == "0":
        query = query.filter(AbandonedBooking.waitlist_notified_at.is_(None))
    elif notified == "1":
        query = query.filter(AbandonedBooking.waitlist_notified_at.isnot(None))
    rows = query.order_by(AbandonedBooking.created_at.desc()).limit(limit).all()

    waiting = AbandonedBooking.query.filter(
        AbandonedBooking.lead_source == "no_coverage_waitlist",
        AbandonedBooking.waitlist_notified_at.is_(None),
        AbandonedBooking.converted.is_(False),
    ).count()

    return jsonify({
        "success": True,
        "waiting_count": waiting,
        "leads": [l.to_dict() for l in rows],
    }), 200


@admin_bp.route("/waitlist/notify", methods=["POST"])
@require_admin
def waitlist_notify(user_id):
    """Manually fire waitlist reactivation for an area (e.g. when you onboard a
    truck in a new zip). Body: {lat, lng, radius?}. Emails matching customers
    'we're live in your area' once each."""
    from flask import current_app
    data = request.get_json() or {}
    lat, lng = data.get("lat"), data.get("lng")
    radius = float(data.get("radius", 30))
    if lat is None or lng is None:
        return jsonify({"error": "lat and lng are required"}), 400
    from waitlist import notify_waitlist_for_coverage
    result = notify_waitlist_for_coverage(current_app._get_current_object(), lat, lng, radius)
    return jsonify({"success": True, **result}), 200


@admin_bp.route("/command-center", methods=["GET"])
@require_admin
def command_center(user_id):
    """One aggregated snapshot of the whole machine — supply, demand, both
    outreach funnels, B2B, the WPB launch verdict, and an 'attention' list of
    what needs a human. Read-only."""
    import os as _os
    from datetime import timedelta as _td
    from models import (Contractor, Job, AbandonedBooking, OperatorLead,
                        B2BLead, Org)
    import dispatcher

    now = utcnow()
    today0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - _td(days=7)
    WPB = (26.7153, -80.0534)
    ACTIVE_JOB = ("pending", "assigned", "accepted", "en_route", "arrived", "started")

    def _counts(model):
        out = {}
        for st, n in db.session.query(model.status, db.func.count(model.id)).group_by(model.status).all():
            out[st or "none"] = n
        return out

    # --- Supply ---
    contractors = Contractor.query.all()
    approved = [c for c in contractors if c.approval_status == "approved"]
    online = [c for c in approved if c.is_online]
    online_in_range = 0
    approved_offline = 0
    for c in approved:
        if not c.is_online:
            approved_offline += 1
        if c.current_lat is not None and c.current_lng is not None and c.is_online:
            if dispatcher.haversine(WPB[0], WPB[1], float(c.current_lat), float(c.current_lng)) <= 30:
                online_in_range += 1
    docs = {}
    for st, n in db.session.query(Contractor.documents_verification_status, db.func.count(Contractor.id)).group_by(Contractor.documents_verification_status).all():
        docs[st or "not_checked"] = n
    onboarding_review = Contractor.query.filter(
        Contractor.onboarding_status.in_(["documents_submitted", "under_review"])
    ).count()

    # --- Demand (consumer) ---
    jobs_today = Job.query.filter(Job.created_at >= today0).count()
    jobs_week = Job.query.filter(Job.created_at >= week_ago).count()
    jobs_active = Job.query.filter(Job.status.in_(ACTIVE_JOB)).count()
    completed_week = Job.query.filter(Job.status == "completed", Job.completed_at >= week_ago).count()
    revenue_week = db.session.query(db.func.coalesce(db.func.sum(Job.total_price), 0.0)).filter(
        Job.status == "completed", Job.completed_at >= week_ago
    ).scalar() or 0.0
    waitlist_open = AbandonedBooking.query.filter(
        AbandonedBooking.lead_source == "no_coverage_waitlist",
        AbandonedBooking.converted.is_(False),
        AbandonedBooking.waitlist_notified_at.is_(None),
    ).count()

    # --- Outreach funnels + B2B ---
    hauler_funnel = _counts(OperatorLead)
    b2b_funnel = _counts(B2BLead)
    org_status = {}
    for st, n in db.session.query(Org.status, db.func.count(Org.id)).group_by(Org.status).all():
        org_status[st or "none"] = n

    # --- Launch verdict (WPB) ---
    dm = (_os.environ.get("DISPATCH_MODE") or dispatcher.DISPATCH_MODE or "").strip().lower()
    if dm in ("assign", "broadcast") and online_in_range >= 1:
        verdict = "GO"
    elif dm in ("assign", "broadcast"):
        verdict = "ALMOST"
    else:
        verdict = "NO-GO"

    # --- Attention list (what needs a human) ---
    replied_leads = (OperatorLead.query.filter_by(status="replied").count()
                     + B2BLead.query.filter_by(status="replied").count())
    attention = []
    if online_in_range == 0:
        attention.append({"level": "high", "what": "No truck online in WPB — launch is blocked",
                          "action": "Text an operator to Go Online"})
    if approved_offline:
        attention.append({"level": "high", "what": "{} approved operator(s) offline".format(approved_offline),
                          "action": "Nudge them to Go Online"})
    if docs.get("flagged"):
        attention.append({"level": "med", "what": "{} document(s) flagged for review".format(docs["flagged"]),
                          "action": "Review in Verification dashboard"})
    if onboarding_review:
        attention.append({"level": "med", "what": "{} onboarding submission(s) awaiting review".format(onboarding_review),
                          "action": "Approve/reject in Verification"})
    if replied_leads:
        attention.append({"level": "med", "what": "{} outreach lead(s) replied".format(replied_leads),
                          "action": "Follow up — they're warm"})
    if waitlist_open:
        attention.append({"level": "low", "what": "{} customer(s) on the no-coverage waitlist".format(waitlist_open),
                          "action": "Auto-converts when a truck covers them"})

    return jsonify({
        "verdict": verdict,
        "supply": {
            "operators_total": len(contractors), "approved": len(approved),
            "online": len(online), "online_in_range_wpb": online_in_range,
            "approved_offline": approved_offline, "docs": docs,
            "onboarding_awaiting_review": onboarding_review,
        },
        "demand": {
            "jobs_today": jobs_today, "jobs_this_week": jobs_week,
            "jobs_active": jobs_active, "completed_this_week": completed_week,
            "revenue_this_week": round(float(revenue_week), 2),
            "waitlist_open": waitlist_open,
        },
        "outreach_haulers": hauler_funnel,
        "outreach_b2b": b2b_funnel,
        "b2b_orgs": org_status,
        "attention": attention,
        "as_of": now.isoformat(),
    }), 200


@admin_bp.route("/launch-readiness", methods=["GET"])
@require_admin
def launch_readiness(user_id):
    """Read-only GO/NO-GO check for a market launch. Runs the REAL dispatch
    read-path (coverage + in-range online operators) against live prod data and
    checks every config precondition the first booking depends on. Writes
    nothing — safe to hit anytime.

    Query: ?lat=&lng=&radius= (defaults to West Palm Beach, 30mi).
    """
    import os as _os
    import dispatcher
    from models import Contractor

    lat = float(request.args.get("lat", 26.7153))
    lng = float(request.args.get("lng", -80.0534))
    radius = float(request.args.get("radius", dispatcher.MAX_RADIUS_MILES))

    checks = []

    def add(name, status, detail):
        # status: pass | warn | fail
        checks.append({"check": name, "status": status, "detail": detail})

    # --- Dispatch mode (the silent breaker) ---
    dm = (_os.environ.get("DISPATCH_MODE") or dispatcher.DISPATCH_MODE or "").strip().lower()
    add("dispatch_mode", "pass" if dm in ("assign", "broadcast") else "fail",
        "DISPATCH_MODE={} ('assign' auto-assigns; 'broadcast' offers to all haulers, first accept wins)".format(dm or "unset"))

    # --- Scheduler (drips, reminders, payouts, no-show) ---
    sched = (_os.environ.get("ENABLE_SCHEDULER") or "").lower() == "true"
    add("scheduler", "pass" if sched else "warn",
        "ENABLE_SCHEDULER={}".format("true" if sched else "off — drips/payouts/reminders won't run"))

    # --- Stripe (operator payouts) ---
    stripe_ok = bool(_os.environ.get("STRIPE_SECRET_KEY"))
    add("stripe_payouts", "pass" if stripe_ok else "warn",
        "STRIPE_SECRET_KEY {}".format("set — operators can be paid" if stripe_ok else "missing — payouts defer to credit"))

    # --- No-operator fallback contacts ---
    has_fallback = bool(_os.environ.get("ADMIN_PHONE") or _os.environ.get("ADMIN_EMAIL"))
    add("admin_fallback", "pass" if has_fallback else "warn",
        "ADMIN_PHONE/ADMIN_EMAIL {}".format("set" if has_fallback else "neither set — an unassigned paid job alerts nobody"))

    # --- Live operator coverage (read-only, real dispatcher logic) ---
    approved = Contractor.query.filter_by(approval_status="approved").all()
    in_range, online_in_range = [], []
    for c in approved:
        if c.current_lat is None or c.current_lng is None:
            continue
        d = dispatcher.haversine(lat, lng, float(c.current_lat), float(c.current_lng))
        if d <= radius:
            entry = {
                "name": (c.user.name if c.user else c.id),
                "miles": round(d, 1),
                "online": bool(c.is_online),
                "has_stripe": bool(c.stripe_connect_id),
            }
            in_range.append(entry)
            if c.is_online:
                online_in_range.append(entry)

    add("operator_coverage",
        "pass" if online_in_range else ("warn" if in_range else "fail"),
        "{} approved in range, {} ONLINE now (need >=1 online to dispatch)".format(len(in_range), len(online_in_range)))

    # pre-payment coverage gate (does the funnel let a WPB booking through?)
    try:
        covered = dispatcher.has_active_coverage(lat, lng, radius)
    except Exception:
        covered = None
    add("booking_gate", "pass" if covered else "warn",
        "has_active_coverage={} (if false, WPB bookings get waitlisted not charged)".format(covered))

    # --- Verdict ---
    any_fail = any(c["status"] == "fail" for c in checks)
    blocking = (dm != "assign") or (not online_in_range)
    if not blocking and not any_fail:
        verdict, summary = "GO", "Ready — a WPB booking will dispatch to an online operator."
    elif dm == "assign" and in_range and not online_in_range:
        verdict, summary = "ALMOST", "Config is good; nobody is ONLINE yet. Get an operator to Go Online, then it's GO."
    else:
        verdict, summary = "NO-GO", "Blocked — see failing checks below."

    return jsonify({
        "verdict": verdict,
        "summary": summary,
        "market": {"lat": lat, "lng": lng, "radius_miles": radius},
        "checks": checks,
        "operators_in_range": in_range,
        "operators_online_in_range": online_in_range,
    }), 200


@admin_bp.route("/referral-dashboard", methods=["GET"])
def referral_dashboard():
    """Self-contained referral-payouts dashboard. Public page; the data call is
    admin-gated, so paste an admin token once (stored in your browser only)."""
    from flask import Response
    return Response(_REFERRAL_DASHBOARD_HTML, mimetype="text/html")


@admin_bp.route("/verification-dashboard", methods=["GET"])
def verification_dashboard():
    """Self-contained operator document-verification dashboard. Public page;
    data + actions are admin-gated (sign in once; token stored in-browser)."""
    from flask import Response
    return Response(_VERIFICATION_DASHBOARD_HTML, mimetype="text/html")


@admin_bp.route("/command-center-dashboard", methods=["GET"])
def command_center_dashboard():
    """Self-contained ops command-center page (whole-machine snapshot). Public
    page; the data call is admin-gated (sign in once; token stored in-browser)."""
    from flask import Response
    return Response(_COMMAND_CENTER_HTML, mimetype="text/html")


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

    # Concierge (no-app) hauler: mint an accepted offer token and SMS them the
    # job console link — the console is their only way to run the job.
    if contractor.is_concierge:
        try:
            from routes.concierge import ensure_concierge_console_link
            ensure_concierge_console_link(job, contractor)
        except Exception as e:
            import logging as _log
            _log.getLogger(__name__).exception(
                "Concierge console link failed for job %s: %s", job.id, e)

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


@admin_bp.route("/jobs/<job_id>/reschedule", methods=["PUT"])
@require_admin
def admin_reschedule_job(user_id, job_id):
    """Admin override to fix a job's scheduled_at (e.g. a bad date saved by
    the phone-booking flow). Accepts scheduled_date (YYYY-MM-DD) and
    scheduled_time (HH:MM), combined into a UTC scheduled_at."""
    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.status not in ("pending", "confirmed", "assigned", "delegating"):
        return jsonify({"error": "Job cannot be rescheduled in its current status"}), 409

    data = request.get_json(silent=True) or {}
    scheduled_date = data.get("scheduled_date")
    scheduled_time = data.get("scheduled_time")
    if not scheduled_date or not scheduled_time:
        return jsonify({"error": "scheduled_date and scheduled_time are required"}), 400

    try:
        new_scheduled_at = datetime.strptime(
            "{} {}".format(scheduled_date, scheduled_time), "%Y-%m-%d %H:%M"
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        return jsonify({"error": "Invalid date/time format. Use YYYY-MM-DD and HH:MM"}), 400

    if new_scheduled_at < datetime.now(timezone.utc):
        return jsonify({"error": "Cannot schedule a job in the past"}), 400

    job.scheduled_at = new_scheduled_at
    job.updated_at = utcnow()

    if job.driver_id:
        driver = db.session.get(Contractor, job.driver_id)
        if driver:
            from notifications import send_push_notification
            send_push_notification(
                driver.user_id,
                "Job Rescheduled",
                "Job #{} has been rescheduled to {} at {}.".format(
                    str(job.id)[:8], scheduled_date, scheduled_time
                ),
            )

    db.session.commit()

    from socket_events import broadcast_job_status
    broadcast_job_status(job.id, job.status, {"scheduled_at": new_scheduled_at.isoformat()})

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


@admin_bp.route("/vapi/sync-assistant", methods=["POST"])
@require_admin
def sync_vapi_assistant(user_id):
    """Push the local Maya assistant config (vapi_setup.assistant_config) to Vapi.

    Reads VAPI_API_KEY from the host environment only, so no key ever lives in
    the repo. Mirrors the env-gated admin bootstrap pattern.

    Body (optional): {"assistant_id": "..."} — defaults to VAPI_ASSISTANT_ID env
    or the known Maya assistant.
    """
    import os as _os

    if not _os.environ.get("VAPI_API_KEY"):
        return jsonify({"error": "VAPI_API_KEY not set on this host"}), 503

    body = request.get_json(silent=True) or {}
    assistant_id = (
        body.get("assistant_id")
        or _os.environ.get("VAPI_ASSISTANT_ID")
        or "91198234-25c8-450a-9075-854509e9e59d"
    )

    # serverUrlSecret comes from the request body (preferred while staging
    # enforcement) or host env; it is forwarded to Vapi and never persisted.
    server_url_secret = body.get("serverUrlSecret") or _os.environ.get(
        "VAPI_SERVER_SECRET"
    )

    try:
        import vapi_setup
        result = vapi_setup.update_assistant(
            assistant_id, server_url_secret=server_url_secret
        )
    except vapi_setup.VapiUpdateError as exc:
        current_app.logger.warning("Vapi rejected assistant update: %s", exc)
        return jsonify({"error": "Vapi rejected the update", "detail": str(exc)}), 502
    except Exception as exc:
        current_app.logger.exception("Vapi assistant sync failed")
        return jsonify({"error": "sync failed", "detail": str(exc)[:300]}), 500

    if not result:
        return jsonify({"error": "Vapi returned no assistant payload"}), 502

    tools = [
        t.get("function", {}).get("name")
        for t in (result.get("model", {}) or {}).get("tools", [])
    ]
    return jsonify({
        "success": True,
        "assistant_id": assistant_id,
        "name": result.get("name"),
        "tools": tools,
        "updated_at": result.get("updatedAt"),
    }), 200
