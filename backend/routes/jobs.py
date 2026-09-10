"""
Customer-facing Job API routes for Umuve.
"""

from flask import Blueprint, request, jsonify

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone, timedelta
from werkzeug.utils import secure_filename

from models import db, Job, Contractor, Rating, Payment, User, Notification, generate_uuid, utcnow
from auth_routes import require_auth, optional_auth
from notifications import send_push_notification
from storage import save_file
from timeutils import parse_local, iso_utc

jobs_bp = Blueprint("jobs", __name__, url_prefix="/api/jobs")

# ---------------------------------------------------------------------------
# Upload constants (shared with routes/upload.py)
# ---------------------------------------------------------------------------
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_FILES = 10
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")


def _allowed_file(filename):
    """Check if a filename has an allowed extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _ensure_upload_dir():
    """Create the uploads directory if it does not exist."""
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ---------------------------------------------------------------------------
# GET /api/jobs/lookup/<confirmation_code>  (PUBLIC -- no auth required)
# ---------------------------------------------------------------------------
@jobs_bp.route("/lookup/<confirmation_code>", methods=["GET"])
def lookup_by_confirmation_code(confirmation_code):
    """
    Public endpoint: look up a job by its confirmation code or job ID.
    Returns job details suitable for unauthenticated customers to track
    their pickup status. Does NOT expose sensitive internal data.
    """
    code = confirmation_code.strip()
    if not code:
        return jsonify({"error": "Job ID or confirmation code required"}), 400

    # Try lookup by confirmation code first (8 chars, alphanumeric)
    if len(code) == 8:
        job = Job.query.filter_by(confirmation_code=code.upper()).first()
        if job:
            # Found by confirmation code
            pass
        else:
            # Try by job ID as fallback
            job = db.session.get(Job, code)
    else:
        # Assume it's a job ID (UUID format)
        job = db.session.get(Job, code)

    if not job:
        return jsonify({"error": "No job found with that ID or confirmation code"}), 404

    # Build a safe public response (no customer_id, payment details, internal IDs)
    result = {
        "id": job.id,
        "confirmation_code": job.confirmation_code,
        "status": job.status,
        "address": job.address,
        "items": job.items or [],
        "photos": job.photos or [],
        "before_photos": job.before_photos or [],
        "after_photos": job.after_photos or [],
        "scheduled_at": iso_utc(job.scheduled_at),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "total_price": job.total_price,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "notes": job.notes,
    }

    # Include contractor info if assigned
    if job.driver_id:
        contractor = db.session.get(Contractor, job.driver_id)
        if contractor:
            result["contractor"] = {
                "name": contractor.user.name if contractor.user else None,
                "truck_type": contractor.truck_type,
                "avg_rating": contractor.avg_rating,
                "total_jobs": contractor.total_jobs,
            }
        else:
            result["contractor"] = None
    else:
        result["contractor"] = None

    return jsonify({"success": True, "job": result}), 200


@jobs_bp.route("", methods=["GET"])
@require_auth
def list_jobs(user_id):
    """
    Return jobs belonging to the authenticated customer.
    Optional query params:
        - status: filter by job status
        - page: page number (default 1)
        - per_page: results per page (default 20)
    Results are ordered by created_at descending.
    """
    query = Job.query.filter_by(customer_id=user_id)

    status = request.args.get("status")
    if status:
        query = query.filter_by(status=status)

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    pagination = query.order_by(Job.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    result = []
    for job in pagination.items:
        job_dict = job.to_dict()
        if job.payment:
            job_dict["payment"] = {
                "id": job.payment.id,
                "amount": job.payment.amount,
                "payment_status": job.payment.payment_status,
                "tip_amount": job.payment.tip_amount,
            }
        else:
            job_dict["payment"] = None
        if job.rating:
            job_dict["rating"] = {
                "id": job.rating.id,
                "stars": job.rating.stars,
                "comment": job.rating.comment,
                "created_at": job.rating.created_at.isoformat() if job.rating.created_at else None,
            }
        else:
            job_dict["rating"] = None
        result.append(job_dict)

    return jsonify({
        "success": True,
        "jobs": result,
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    }), 200


@jobs_bp.route("/<job_id>", methods=["GET"])
@require_auth
def get_job(user_id, job_id):
    """
    Return a single job detail for the authenticated customer.
    Includes nested payment, rating, and contractor info.
    """
    job = db.session.get(Job, job_id)
    if not job or job.customer_id != user_id:
        return jsonify({"error": "Job not found"}), 404

    job_dict = job.to_dict()

    # Include payment info
    if job.payment:
        job_dict["payment"] = {
            "id": job.payment.id,
            "amount": job.payment.amount,
            "payment_status": job.payment.payment_status,
            "tip_amount": job.payment.tip_amount,
        }
    else:
        job_dict["payment"] = None

    # Include rating info
    if job.rating:
        job_dict["rating"] = {
            "id": job.rating.id,
            "stars": job.rating.stars,
            "comment": job.rating.comment,
            "created_at": job.rating.created_at.isoformat() if job.rating.created_at else None,
        }
    else:
        job_dict["rating"] = None

    # Include contractor info
    if job.driver_id:
        contractor = db.session.get(Contractor, job.driver_id)
        if contractor:
            contractor_dict = contractor.to_dict()
            job_dict["contractor"] = contractor_dict
        else:
            job_dict["contractor"] = None
    else:
        job_dict["contractor"] = None

    return jsonify({"success": True, "job": job_dict}), 200


def _manage_token_from_request():
    data = request.get_json(silent=True) or {}
    return (request.args.get("token") or request.args.get("manage_token")
            or data.get("manage_token") or data.get("token") or "")


def _load_customer_job(job_id, user_id):
    """Job + authorization for customer self-service (JWT owner or guest manage token)."""
    from cancellation import customer_may_act
    job = db.session.get(Job, job_id)
    if not job or not customer_may_act(job, user_id, _manage_token_from_request()):
        return None
    return job


@jobs_bp.route("/<job_id>/cancel-preview", methods=["GET"])
@optional_auth
def cancel_preview(user_id, job_id):
    """Disclose the cancellation outcome (fee / refund) before the customer commits."""
    from cancellation import cancellation_outcome
    job = _load_customer_job(job_id, user_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    o = cancellation_outcome(job, "customer")
    return jsonify({
        "success": True,
        "allowed": o.allowed,
        "cancellation_fee": o.fee,
        "refund_amount": o.refund_amount,
        "reason_code": o.reason_code,
        "requires_confirmation": o.requires_confirmation,
        "message": o.message,
    }), 200


@jobs_bp.route("/<job_id>/cancel", methods=["POST", "PUT"])
@optional_auth
def cancel_job(user_id, job_id):
    """
    Cancel a job (customer self-service).

    Policy lives in cancellation.cancellation_outcome (audit F18):
    - never assigned a hauler       -> always allowed, $0 fee, full refund
    - assigned, before en-route     -> allowed, time-based fee (<24h $25, <2h $50)
    - en_route / arrived            -> allowed as a REQUEST: the outcome is
      disclosed and the call must carry ``{"confirm": true}`` (else 409 with
      the outcome so the UI can ask)
    Auth: the owner's JWT or a guest manage token (``?token=``/``manage_token``).
    """
    from cancellation import execute_cancellation, notify_customer_cancelled
    job = _load_customer_job(job_id, user_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    data = request.get_json(silent=True) or {}
    confirmed = bool(data.get("confirm"))
    outcome, result = execute_cancellation(
        job, "customer", actor_user_id=job.customer_id,
        reason=(data.get("reason") or "customer_cancelled")[:120], confirmed=confirmed,
    )
    if not outcome.allowed:
        return jsonify({"error": outcome.message, "reason_code": outcome.reason_code}), 409
    if not result["applied"]:
        # On-the-way: disclose the fee and ask for explicit confirmation.
        return jsonify({
            "error": outcome.message,
            "code": "confirmation_required",
            "requires_confirmation": True,
            "cancellation_fee": outcome.fee,
            "refund_amount": outcome.refund_amount,
            "reason_code": outcome.reason_code,
        }), 409

    db.session.commit()
    notify_customer_cancelled(job)

    return jsonify({
        "success": True,
        "job": job.to_dict(),
        "cancellation_fee": outcome.fee,
        "refund_amount": outcome.refund_amount,
        "reason_code": outcome.reason_code,
        "refund_status": result["refund_status"],
    }), 200


@jobs_bp.route("/<job_id>/reschedule", methods=["PUT"])
@optional_auth
def reschedule_job(user_id, job_id):
    """
    Reschedule a job to a new date/time.

    Audit F18: rescheduling
    - re-prices the schedule surcharge and invalidates ``price_version``: if
      the total changes, the request must echo the new ``price_version`` (409
      ``price_changed`` carries it) — a paid job settles the delta through a
      change order (separate charge / partial refund);
    - re-qualifies the assigned hauler (released + re-dispatched on conflict)
      and voids outstanding offers;
    - resets the reminder / no-show / rescue timers keyed off scheduled_at.
    Auth: owner JWT or guest manage token.
    """
    from price_version import compute_price_version, normalize_schedule
    from routes.booking import calculate_estimate

    job = _load_customer_job(job_id, user_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    reschedulable = ("pending", "confirmed", "assigned", "accepted", "broadcasting")
    if job.status not in reschedulable:
        return jsonify({"error": "Job cannot be rescheduled in its current status"}), 409

    data = request.get_json(silent=True) or {}
    scheduled_date = data.get("scheduled_date") or data.get("scheduledDate")
    scheduled_time = data.get("scheduled_time") or data.get("scheduledTimeSlot")

    if not scheduled_date or not scheduled_time:
        return jsonify({"error": "scheduled_date and scheduled_time are required"}), 400

    try:
        new_scheduled_at = parse_local(scheduled_date, scheduled_time)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid date/time format. Use YYYY-MM-DD and HH:MM"}), 400

    if new_scheduled_at < datetime.now(timezone.utc):
        return jsonify({"error": "Cannot schedule a job in the past"}), 400

    # --- Re-price the schedule surcharge (only the date-driven delta moves) ---
    items = [i for i in (job.items or []) if isinstance(i, dict)]
    delta = 0.0
    surge_reasons = []
    if items:
        try:
            from timeutils import local_date_str as _lds
            old_date = _lds(job.scheduled_at) if job.scheduled_at else None
            old_est = calculate_estimate(items, scheduled_date=old_date, lat=job.lat, lng=job.lng)
            new_est = calculate_estimate(items, scheduled_date=scheduled_date, lat=job.lat, lng=job.lng)
            delta = round(new_est["total"] - old_est["total"], 2)
            surge_reasons = new_est.get("surge_reasons") or []
        except Exception:
            delta = 0.0
    new_total = round(float(job.total_price or 0.0) + delta, 2)
    date_part, slot = normalize_schedule(scheduled_date, scheduled_time)
    version = compute_price_version(
        items, job.lat, job.lng, job.address, date_part, slot, None,
        job.promo_code.code if job.promo_code else "", job.discount_amount or 0.0,
        job.service_fee or 0.0, new_total,
    )
    client_version = (data.get("price_version") or data.get("priceVersion") or "").strip()
    if abs(delta) >= 0.01 and client_version != version:
        return jsonify({
            "error": "This date changes your price — please confirm the updated total.",
            "code": "price_changed",
            "old_total": round(float(job.total_price or 0.0), 2),
            "total": new_total,
            "delta": delta,
            "surge_reasons": surge_reasons,
            "price_version": version,
        }), 409

    old_scheduled_at = job.scheduled_at
    job.scheduled_at = new_scheduled_at
    job.rescheduled_count = (job.rescheduled_count or 0) + 1
    job.price_version = version

    settlement = None
    if abs(delta) >= 0.01:
        from change_orders import propose_change_order, accept_change_order
        order = propose_change_order(job, "customer", job.customer_id, new_total,
                                     scope={"scheduled_date": date_part, "scheduled_time": slot},
                                     reason="reschedule")
        accept_change_order(job, order)  # consent = the echoed price_version
        settlement = order.to_dict()

    # --- Reset rescue / reminder timers keyed off scheduled_at ---
    job.noshow_t30_alerted = False
    job.noshow_late_alerted = False
    job.reminder_sent = False
    job.reminder_call_id = None

    # --- Void outstanding offers; re-qualify / release the assigned hauler ---
    try:
        from models import JobOffer
        JobOffer.query.filter_by(job_id=job.id, status="sent").update(
            {"status": "expired"}, synchronize_session=False)
    except Exception:
        pass

    released_driver = None
    redispatch = False
    paid = bool(job.payment and job.payment.payment_status in ("succeeded", "partially_refunded"))
    if job.driver_id:
        driver = db.session.get(Contractor, job.driver_id)
        conflict = False
        if driver:
            try:
                from dispatcher import _has_schedule_conflict
                conflict = _has_schedule_conflict(driver, new_scheduled_at, Job)
            except Exception:
                conflict = False
        if driver and not conflict:
            send_push_notification(
                driver.user_id, "Job Rescheduled",
                "Job #{} has been rescheduled to {} at {}.".format(str(job.id)[:8], scheduled_date, scheduled_time),
                {"job_id": job.id, "scheduled_date": scheduled_date, "scheduled_time": scheduled_time},
            )
            db.session.add(Notification(
                id=generate_uuid(), user_id=driver.user_id, type="job_rescheduled",
                title="Job Rescheduled",
                body="Job #{} has been rescheduled to {} at {}.".format(str(job.id)[:8], scheduled_date, scheduled_time),
                data={"job_id": job.id, "scheduled_date": scheduled_date, "scheduled_time": scheduled_time},
            ))
        else:
            released_driver = job.driver_id
            if driver:
                send_push_notification(
                    driver.user_id, "Job Released",
                    "Job #{} was rescheduled to a time you're not available — it has been released.".format(str(job.id)[:8]),
                    {"job_id": job.id, "status": "released"},
                )
            job.driver_id = None
            job.status = "confirmed" if paid else "pending"
            redispatch = paid
    elif job.status == "broadcasting":
        job.status = "confirmed" if paid else "pending"
        redispatch = paid

    db.session.add(Notification(
        id=generate_uuid(), user_id=job.customer_id, type="job_rescheduled",
        title="Job Rescheduled",
        body="Your job #{} has been rescheduled to {} at {}.".format(str(job.id)[:8], scheduled_date, scheduled_time),
        data={"job_id": job.id, "scheduled_date": scheduled_date, "scheduled_time": scheduled_time,
              "price_delta": delta},
    ))
    job.updated_at = utcnow()
    db.session.commit()

    if redispatch:
        try:
            from flask import current_app
            from dispatcher import auto_assign_job_async
            auto_assign_job_async(job.id, current_app._get_current_object())
        except Exception:
            pass

    return jsonify({
        "success": True,
        "job": job.to_dict(),
        "price_delta": delta,
        "price_version": version,
        "released_driver": released_driver,
        "settlement": settlement,
        "previous_scheduled_at": iso_utc(old_scheduled_at),
    }), 200


@jobs_bp.route("/<job_id>/proof", methods=["GET"])
@require_auth
def get_job_proof(user_id, job_id):
    """
    Return proof photos (before/after) for a job.

    Accessible to:
        - The customer who owns the job
        - The driver assigned to the job
        - An admin user
    """
    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    # Determine access: customer, driver, or admin
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    is_customer = job.customer_id == user_id
    is_admin = user.role == "admin"

    # Check if the user is the assigned driver
    is_driver = False
    if user.contractor_profile and job.driver_id == user.contractor_profile.id:
        is_driver = True

    if not (is_customer or is_driver or is_admin):
        return jsonify({"error": "You do not have access to this job's proof photos"}), 403

    return jsonify({
        "success": True,
        "job_id": job.id,
        "before_photos": job.before_photos or [],
        "after_photos": job.after_photos or [],
        "proof_submitted_at": job.proof_submitted_at.isoformat() if job.proof_submitted_at else None,
    }), 200


# ---------------------------------------------------------------------------
# GET /api/jobs/<job_id>/photos  (customer or driver can view)
# ---------------------------------------------------------------------------
@jobs_bp.route("/<job_id>/photos", methods=["GET"])
@require_auth
def get_job_photos(user_id, job_id):
    """
    Return all photos for a job (before_photos, after_photos, and original photos).

    Accessible to:
        - The customer who owns the job
        - The driver assigned to the job
        - An admin user
    """
    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    is_customer = job.customer_id == user_id
    is_admin = user.role == "admin"
    is_driver = False
    if user.contractor_profile and job.driver_id == user.contractor_profile.id:
        is_driver = True

    if not (is_customer or is_driver or is_admin):
        return jsonify({"error": "You do not have access to this job's photos"}), 403

    return jsonify({
        "success": True,
        "job_id": job.id,
        "photos": job.photos or [],
        "before_photos": job.before_photos or [],
        "after_photos": job.after_photos or [],
        "proof_submitted_at": job.proof_submitted_at.isoformat() if job.proof_submitted_at else None,
    }), 200


# ---------------------------------------------------------------------------
# POST /api/jobs/<job_id>/photos/before  (driver uploads before photos)
# ---------------------------------------------------------------------------
@jobs_bp.route("/<job_id>/photos/before", methods=["POST"])
@require_auth
def upload_before_photos(user_id, job_id):
    """
    Driver uploads before photos for a job (multipart/form-data).

    Only the assigned driver can upload.
    Form field: ``files`` (multiple).
    Appends uploaded URLs to ``job.before_photos``.
    """
    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    # Verify the authenticated user is the assigned driver
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    is_driver = False
    if user.contractor_profile and job.driver_id == user.contractor_profile.id:
        is_driver = True

    if not is_driver:
        return jsonify({"error": "Only the assigned driver can upload before photos"}), 403

    # Parse files from the request
    if "files" not in request.files:
        return jsonify({"error": "No files provided. Use the 'files' form field."}), 400

    files = request.files.getlist("files")
    if len(files) == 0:
        return jsonify({"error": "No files provided"}), 400
    if len(files) > MAX_FILES:
        return jsonify({"error": "Maximum {} files allowed per upload".format(MAX_FILES)}), 400

    urls = []
    errors = []

    for file in files:
        if not file or not file.filename:
            errors.append({"file": "unknown", "error": "Empty file"})
            continue

        if not _allowed_file(file.filename):
            errors.append({"file": file.filename, "error": "File type not allowed. Accepted: jpg, png, webp"})
            continue

        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)

        if size > MAX_FILE_SIZE:
            errors.append({"file": file.filename, "error": "File exceeds maximum size of 10 MB"})
            continue

        url = save_file(file, prefix="jobs/before", filename=file.filename)
        urls.append(url)

    if not urls:
        return jsonify({"success": False, "error": "No files were uploaded successfully", "errors": errors}), 400

    # Append to existing before_photos
    existing = list(job.before_photos or [])
    existing.extend(urls)
    job.before_photos = existing

    db.session.commit()

    response = {"success": True, "urls": urls, "before_photos": job.before_photos}
    if errors:
        response["errors"] = errors

    return jsonify(response), 201


# ---------------------------------------------------------------------------
# POST /api/jobs/<job_id>/photos/after  (driver uploads after photos)
# ---------------------------------------------------------------------------
@jobs_bp.route("/<job_id>/photos/after", methods=["POST"])
@require_auth
def upload_after_photos(user_id, job_id):
    """
    Driver uploads after photos for a job (multipart/form-data).

    Only the assigned driver can upload.
    Form field: ``files`` (multiple).
    Appends uploaded URLs to ``job.after_photos``.
    Sets ``proof_submitted_at`` on first upload.
    """
    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    # Verify the authenticated user is the assigned driver
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    is_driver = False
    if user.contractor_profile and job.driver_id == user.contractor_profile.id:
        is_driver = True

    if not is_driver:
        return jsonify({"error": "Only the assigned driver can upload after photos"}), 403

    # Parse files from the request
    if "files" not in request.files:
        return jsonify({"error": "No files provided. Use the 'files' form field."}), 400

    files = request.files.getlist("files")
    if len(files) == 0:
        return jsonify({"error": "No files provided"}), 400
    if len(files) > MAX_FILES:
        return jsonify({"error": "Maximum {} files allowed per upload".format(MAX_FILES)}), 400

    urls = []
    errors = []

    for file in files:
        if not file or not file.filename:
            errors.append({"file": "unknown", "error": "Empty file"})
            continue

        if not _allowed_file(file.filename):
            errors.append({"file": file.filename, "error": "File type not allowed. Accepted: jpg, png, webp"})
            continue

        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)

        if size > MAX_FILE_SIZE:
            errors.append({"file": file.filename, "error": "File exceeds maximum size of 10 MB"})
            continue

        url = save_file(file, prefix="jobs/after", filename=file.filename)
        urls.append(url)

    if not urls:
        return jsonify({"success": False, "error": "No files were uploaded successfully", "errors": errors}), 400

    # Append to existing after_photos
    existing = list(job.after_photos or [])
    existing.extend(urls)
    job.after_photos = existing

    # Mark proof submission timestamp on first after-photo upload
    if not job.proof_submitted_at:
        job.proof_submitted_at = utcnow()

    db.session.commit()

    response = {"success": True, "urls": urls, "after_photos": job.after_photos}
    if errors:
        response["errors"] = errors

    return jsonify(response), 201


@jobs_bp.route("/<job_id>/change-orders", methods=["GET"])
@optional_auth
def list_change_orders(user_id, job_id):
    """Customer view of every proposed/decided change order for the job."""
    from models import ChangeOrder
    job = _load_customer_job(job_id, user_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    orders = (ChangeOrder.query.filter_by(job_id=job.id)
              .order_by(ChangeOrder.version.desc()).all())
    return jsonify({"success": True, "change_orders": [o.to_dict() for o in orders]}), 200


def _open_change_order(job):
    from models import ChangeOrder
    return (ChangeOrder.query.filter_by(job_id=job.id, status="proposed")
            .order_by(ChangeOrder.version.desc()).first())


@jobs_bp.route("/<job_id>/volume/approve", methods=["POST"])
@jobs_bp.route("/<job_id>/change-orders/<order_id>/accept", methods=["POST"])
@optional_auth
def approve_volume_adjustment(user_id, job_id, order_id=None):
    """Customer accepts the open change order (audit F12).

    The captured PaymentIntent is never modified: an increase is charged as a
    separate intent, a decrease refunded. The split uses the shared
    recompute_payment_split, not a fixed 20/80.
    """
    from change_orders import accept_change_order
    from socket_events import socketio
    import logging
    logger = logging.getLogger(__name__)

    job = _load_customer_job(job_id, user_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    order = _open_change_order(job)
    if order is None or (order_id and order.id != order_id):
        return jsonify({"error": "No volume adjustment is pending"}), 409

    try:
        accept_change_order(job, order)
    except ValueError as exc:
        db.session.commit()
        return jsonify({"error": str(exc), "code": "change_order_closed"}), 409
    db.session.commit()

    try:
        socketio.emit("volume:approved", {"job_id": job_id, "change_order_id": order.id},
                      room=f"driver:{job.driver_id}")
    except Exception as e:
        logger.warning("Failed to emit volume:approved socket event: %s", e)

    logger.info("Change order %s v%s accepted for job %s", order.id, order.version, job_id)
    body = {"success": True, "change_order": order.to_dict(), "total_price": job.total_price}
    client_secret = getattr(order, "client_secret", None)
    if client_secret:
        body["client_secret"] = client_secret  # confirm the additional charge in-app
    return jsonify(body), 200


@jobs_bp.route("/<job_id>/change-orders/<order_id>/confirm", methods=["POST"])
@optional_auth
def confirm_change_order_charge(user_id, job_id, order_id):
    """Finalise a ``requires_action`` additional charge after in-app confirmation."""
    from models import ChangeOrder
    from change_orders import confirm_settlement
    job = _load_customer_job(job_id, user_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    order = db.session.get(ChangeOrder, order_id)
    if order is None or order.job_id != job.id:
        return jsonify({"error": "Change order not found"}), 404
    confirm_settlement(job, order)
    db.session.commit()
    return jsonify({"success": True, "change_order": order.to_dict()}), 200


@jobs_bp.route("/<job_id>/volume/decline", methods=["POST"])
@jobs_bp.route("/<job_id>/change-orders/<order_id>/decline", methods=["POST"])
@optional_auth
def decline_volume_adjustment(user_id, job_id, order_id=None):
    """Customer declines the change order: the original scope and price stand.

    No trip fee, no cancellation — the hauler completes the booked scope. If
    the crew cannot, the operator cancels (no customer fee; cancellation.py).
    """
    from change_orders import decline_change_order
    from socket_events import socketio
    import logging
    logger = logging.getLogger(__name__)

    job = _load_customer_job(job_id, user_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    order = _open_change_order(job)
    if order is None or (order_id and order.id != order_id):
        return jsonify({"error": "No volume adjustment is pending"}), 409

    decline_change_order(job, order)
    db.session.commit()

    try:
        socketio.emit("volume:declined", {"job_id": job_id, "change_order_id": order.id,
                                          "original_price": job.total_price},
                      room=f"driver:{job.driver_id}")
    except Exception as e:
        logger.warning("Failed to emit volume:declined socket event: %s", e)

    logger.info("Change order %s declined for job %s — original price stands", order.id, job_id)
    return jsonify({"success": True, "change_order": order.to_dict(),
                    "total_price": job.total_price, "trip_fee": 0.0}), 200
