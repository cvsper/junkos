"""Shared job-assignment machinery.

One implementation of "put this contractor on this job" used by two doors:
the admin dashboard (routes/admin.py) and the VA Dispatch Desk
(va_dispatch.py). Handles operator delegation, direct driver assignment,
the concierge SMS console link, and every downstream notification, so the
two callers can't drift apart.

Callers are responsible for authorization and for validating that the job
and contractor exist; this module validates state (approval, job status)
and performs the assignment.
"""
from __future__ import annotations

import logging

from models import db, Notification, User, generate_uuid, utcnow

logger = logging.getLogger(__name__)

# Job statuses a new assignment is allowed to start from.
ASSIGNABLE_STATUSES = ("pending", "confirmed")


class AssignmentError(Exception):
    """Assignment refused — .status_code and str(exc) explain why."""

    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


def assign_contractor_to_job(job, contractor, assigned_by=None):
    """Assign `contractor` to `job` and fire all downstream effects.

    Returns the refreshed job dict. Raises AssignmentError when the
    contractor isn't approved. `assigned_by` is a free-text attribution
    ("admin", "Tracy (VA desk)") used only in logs.
    """
    if contractor.approval_status != "approved":
        raise AssignmentError("Contractor is not approved", 403)

    if contractor.is_operator:
        return _assign_operator(job, contractor)
    return _assign_driver(job, contractor, assigned_by)


def _assign_operator(job, contractor):
    """Operator gets the job for delegation to their fleet."""
    job.operator_id = contractor.id
    if job.status in ASSIGNABLE_STATUSES:
        job.status = "delegating"
    job.updated_at = utcnow()

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

    return job.to_dict()


def _assign_driver(job, contractor, assigned_by=None):
    """Direct driver assignment — app hauler or concierge hauler."""
    job.driver_id = contractor.id
    if job.status in ASSIGNABLE_STATUSES:
        job.status = "assigned"
    job.updated_at = utcnow()

    notification = Notification(
        id=generate_uuid(),
        user_id=contractor.user_id,
        type="job_assigned",
        title="New Job Assigned",
        body="{} assigned you a job at {}.".format(
            assigned_by or "An admin", job.address or "an address"),
        data={"job_id": job.id, "address": job.address, "total_price": job.total_price},
    )
    db.session.add(notification)

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
            logger.exception("Concierge console link failed for job %s: %s", job.id, e)

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
        send_push_notification(
            contractor.user_id, "New Job Assigned",
            "New job assigned: {}".format(job.address or "an address"),
            {"job_id": job.id},
        )
    except Exception as e:
        logger.exception("Notification failed for job %s: %s", job.id, e)

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

    return job.to_dict()
