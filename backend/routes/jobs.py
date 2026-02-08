"""
Customer-facing Job API routes for JunkOS.
"""

from flask import Blueprint, request, jsonify

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, Job, Contractor, Rating, Payment
from auth_routes import require_auth

jobs_bp = Blueprint("jobs", __name__, url_prefix="/api/jobs")


@jobs_bp.route("", methods=["GET"])
@require_auth
def list_jobs(user_id):
    """
    Return all jobs belonging to the authenticated customer.
    Optional query param: status (filter by job status).
    Results are ordered by created_at descending.
    """
    query = Job.query.filter_by(customer_id=user_id)

    status = request.args.get("status")
    if status:
        query = query.filter_by(status=status)

    query = query.order_by(Job.created_at.desc())
    jobs = query.all()

    result = []
    for job in jobs:
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

    return jsonify({"success": True, "jobs": result}), 200


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


@jobs_bp.route("/<job_id>/cancel", methods=["POST"])
@require_auth
def cancel_job(user_id, job_id):
    """
    Cancel a job. Only allowed if the job status is 'pending' or 'confirmed'.
    The job must belong to the authenticated customer.
    """
    job = db.session.get(Job, job_id)
    if not job or job.customer_id != user_id:
        return jsonify({"error": "Job not found"}), 404

    if job.status not in ("pending", "confirmed"):
        return jsonify({"error": "Job cannot be cancelled in its current status"}), 409

    job.status = "cancelled"
    db.session.commit()

    return jsonify({"success": True, "job": job.to_dict()}), 200
