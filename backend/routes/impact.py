"""
Rescue Engine v1 — customer-facing impact API.

Endpoints:
  GET /api/impact/config            -> preference choices + copy (public; the
                                       funnel renders options from this)
  GET /api/impact/code/<code>       -> single completed job's impact receipt by
                                       confirmation code (public; guest receipt)
  GET /api/impact/history           -> the authed customer's diversion summary
                                       + past jobs with disposition (auth)

Reads the per-job disposition fields written by the booking flow (preference)
and the driver completion flow (outcome). All copy is estimate-only and never
names a charity — see impact.py.
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, jsonify
from models import db, Job
from auth_routes import require_auth
from impact import PREFERENCE_CHOICES, OUTCOME_CHOICES, diversion_stats, build_impact_summary

impact_bp = Blueprint("impact", __name__, url_prefix="/api/impact")


@impact_bp.route("/config", methods=["GET"])
def impact_config():
    """Preference options + copy so every client renders the same choices."""
    return jsonify({
        "preferences": [
            {"value": v, "label": label, "help": help_}
            for v, (label, help_) in PREFERENCE_CHOICES.items()
        ],
        "outcomes": [
            {"value": v, "label": label, "diverted": diverted}
            for v, (label, diverted) in OUTCOME_CHOICES.items()
        ],
        "disclaimer": "Estimated impact — final handling is at the hauler's discretion. "
                      "Reusable items may be routed toward donation or reuse partners where available.",
    }), 200


@impact_bp.route("/code/<code>", methods=["GET"])
def impact_by_code(code):
    """Public impact receipt for one job by confirmation code (guest-safe:
    no IDs, price, or PII — just the impact story)."""
    if not code:
        return jsonify({"error": "code required"}), 400
    job = Job.query.filter_by(confirmation_code=code.strip().upper()).first()
    if not job:
        return jsonify({"error": "Not found"}), 404

    summary = job.impact_summary
    if not summary and job.status == "completed":
        summary = build_impact_summary(job)

    return jsonify({
        "status": job.status,
        "preference": job.disposition_preference or "best",
        "outcome": job.disposition_outcome,
        "impact_summary": summary,
        "is_estimated": True,
    }), 200


@impact_bp.route("/history", methods=["GET"])
@require_auth
def impact_history(user_id):
    """The customer's lifetime diversion summary + recent completed jobs."""
    jobs = (
        Job.query
        .filter_by(customer_id=user_id, status="completed")
        .order_by(Job.completed_at.desc())
        .all()
    )
    stats = diversion_stats(jobs)
    recent = [{
        "confirmation_code": j.confirmation_code,
        "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        "preference": j.disposition_preference or "best",
        "outcome": j.disposition_outcome,
        "impact_summary": j.impact_summary,
    } for j in jobs[:50]]

    return jsonify({
        "success": True,
        "summary": stats,
        "is_estimated": True,
        "jobs": recent,
    }), 200
