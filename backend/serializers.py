"""Audience-specific serializers (audit F21).

``Contractor.to_dict`` / ``Job.to_dict`` are the *admin* views — they carry the
onboarding dossier (document URLs, expiries, Stripe ids, rejection notes,
availability) and internal ops flags. Nothing customer- or public-facing may
emit those. Use:

- ``contractor_public_arrival(contractor)`` — what a customer needs to
  recognise the hauler at the door.
- ``job_for_customer(job)`` — the customer's own booking, with the arrival
  profile nested under ``contractor``.
- ``rating_public(rating)`` — a rating without the rater's contact details.
- ``contractor_private_docs(contractor)`` — document links that go through
  the authenticated signed-URL endpoint, never the raw storage URL.
"""

from timeutils import iso_utc

__all__ = [
    "contractor_public_arrival", "job_for_customer", "rating_public",
    "contractor_private_docs", "CUSTOMER_JOB_FIELDS",
]

# Fields of Job.to_dict() a customer may see about their own booking.
# Deliberately absent: reminder/review call ids, no-show alert flags,
# lead_source, promo_code_id, delegated_at, operator_id, driver_id (the
# contractor block below replaces it), and every internal marker.
CUSTOMER_JOB_FIELDS = (
    "id", "customer_id", "status", "address", "lat", "lng", "items",
    "volume_estimate", "photos", "before_photos", "after_photos",
    "proof_submitted_at", "scheduled_at", "started_at", "completed_at",
    "base_price", "item_total", "volume_price", "service_fee",
    "surge_multiplier", "total_price", "discount_amount", "notes",
    "confirmation_code", "cancelled_at", "cancellation_fee",
    "rescheduled_count", "volume_adjustment_proposed", "adjusted_volume",
    "adjusted_price", "disposition_preference", "disposition_outcome",
    "impact_summary", "created_at", "updated_at",
)


def _first_name(user):
    name = (getattr(user, "name", None) or "").strip()
    return name.split()[0] if name else None


def contractor_public_arrival(contractor):
    """Safe arrival profile: first name, photo, rating, vehicle, plate tail.

    Never document URLs, expiries, Stripe ids, home address, availability,
    rejection metadata, email or phone.
    """
    if contractor is None:
        return None
    user = getattr(contractor, "user", None)
    photos = contractor.truck_photos or []
    plate = getattr(contractor, "license_plate", None) or getattr(contractor, "plate", None)
    return {
        "id": contractor.id,
        "first_name": _first_name(user) or "your hauler",
        "photo_url": getattr(user, "avatar_url", None),
        "avg_rating": round(contractor.avg_rating, 1) if contractor.avg_rating else None,
        "total_jobs": contractor.total_jobs or 0,
        "vehicle": contractor.truck_type,
        "vehicle_photo_url": photos[0] if photos else None,
        "plate_last3": str(plate)[-3:] if plate else None,
    }


def job_for_customer(job):
    """The customer's own booking with the hauler reduced to the arrival profile."""
    raw = job.to_dict()
    data = {k: raw.get(k) for k in CUSTOMER_JOB_FIELDS}
    data["scheduled_at"] = iso_utc(job.scheduled_at)
    contractor = getattr(job, "driver", None)
    if contractor is None and job.driver_id:
        from models import db, Contractor
        contractor = db.session.get(Contractor, job.driver_id)
    data["contractor"] = contractor_public_arrival(contractor) if contractor else None
    data["tracking_url"] = job.tracking_url()
    return data


def rating_public(rating):
    if rating is None:
        return None
    return {
        "id": rating.id,
        "job_id": rating.job_id,
        "stars": rating.stars,
        "comment": rating.comment,
        "created_at": rating.created_at.isoformat() if rating.created_at else None,
    }


_DOC_ATTRS = {
    "insurance": "insurance_document_url",
    "drivers_license": "drivers_license_url",
    "vehicle_registration": "vehicle_registration_url",
}


def contractor_private_docs(contractor):
    """Per-document access paths that require an authenticated caller.

    Returns ``{doc_type: "/api/documents/contractor/<id>/<doc_type>" | None}``
    — the endpoint (routes/upload.py) checks admin-or-owner and then
    redirects to a short-lived S3 presigned URL or streams the local file.
    """
    out = {}
    for doc_type, attr in _DOC_ATTRS.items():
        stored = getattr(contractor, attr, None)
        out[doc_type] = (
            "/api/documents/contractor/{}/{}".format(contractor.id, doc_type)
            if stored else None
        )
    return out
