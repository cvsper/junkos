"""
Email campaign management routes for Umuve.
Admin-only endpoints for creating and sending bulk email campaigns
(e.g., operator recruitment sequences, customer winbacks).
"""

import csv
import io
import logging
import threading
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, request, jsonify

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, EmailCampaign, CampaignRecipient, generate_uuid, utcnow,
)
from auth_routes import require_auth
from notifications import send_email_sync, EMAIL_FROM, EMAIL_FROM_NAME
from email_templates import (
    operator_recruitment_1_html,
    operator_recruitment_2_html,
    operator_recruitment_3_html,
    operator_recruitment_4_html,
    operator_recruitment_5_html,
    operator_stripe_payout_html,
    winback_html,
)

logger = logging.getLogger(__name__)

campaigns_bp = Blueprint("campaigns", __name__, url_prefix="/api/campaigns")

# Template registry — maps template names to (subject, html_fn)
TEMPLATES = {
    "recruitment_1": {
        "subject": "You have a truck. We have customers. Let's make money.",
        "fn": operator_recruitment_1_html,
        "args": ["first_name", "area"],
    },
    "recruitment_2": {
        "subject": "This hauler made $4,200 last week on Umuve",
        "fn": operator_recruitment_2_html,
        "args": ["first_name", "area"],
    },
    "recruitment_3": {
        "subject": "'What's the catch?' — here's the honest answer",
        "fn": operator_recruitment_3_html,
        "args": ["first_name"],
    },
    "recruitment_4": {
        "subject": "3 operator spots left in {area}",
        "fn": operator_recruitment_4_html,
        "args": ["first_name", "area"],
    },
    "recruitment_5": {
        "subject": "Last email — $3K/week opportunity closing",
        "fn": operator_recruitment_5_html,
        "args": ["first_name"],
    },
    "stripe_payout": {
        "subject": "Set up payouts — get paid the same day you haul",
        "fn": operator_stripe_payout_html,
        "args": ["first_name"],
    },
    "winback": {
        "subject": "Still have stuff to get rid of?",
        "fn": winback_html,
        "args": ["first_name"],
    },
}


def require_admin(f):
    """Require admin role."""
    @wraps(f)
    @require_auth
    def wrapper(user_id, *args, **kwargs):
        user = db.session.get(User, user_id)
        if not user or user.role != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(user_id=user_id, *args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# List campaigns
# ---------------------------------------------------------------------------
@campaigns_bp.route("", methods=["GET"])
@require_admin
def list_campaigns(user_id):
    """List all email campaigns."""
    campaigns = EmailCampaign.query.order_by(EmailCampaign.created_at.desc()).all()
    return jsonify({"campaigns": [c.to_dict() for c in campaigns]})


# ---------------------------------------------------------------------------
# Get campaign details
# ---------------------------------------------------------------------------
@campaigns_bp.route("/<campaign_id>", methods=["GET"])
@require_admin
def get_campaign(user_id, campaign_id):
    """Get campaign details including recipient stats."""
    campaign = db.session.get(EmailCampaign, campaign_id)
    if not campaign:
        return jsonify({"error": "Campaign not found"}), 404

    recipients = campaign.recipients.all()
    data = campaign.to_dict()
    data["recipients"] = [r.to_dict() for r in recipients]
    return jsonify(data)


# ---------------------------------------------------------------------------
# Create campaign
# ---------------------------------------------------------------------------
@campaigns_bp.route("", methods=["POST"])
@require_admin
def create_campaign(user_id):
    """Create a new email campaign.

    Body JSON:
        name: str (required)
        template: str (required, one of TEMPLATES keys)
        subject: str (optional, overrides default template subject)
        recipients: list of {email, first_name?, company?, area?, phone?}
    """
    data = request.get_json(force=True)

    name = data.get("name")
    template = data.get("template")
    subject = data.get("subject")
    recipients_data = data.get("recipients", [])

    if not name:
        return jsonify({"error": "name is required"}), 400
    if not template or template not in TEMPLATES:
        return jsonify({
            "error": "template is required and must be one of: {}".format(
                ", ".join(sorted(TEMPLATES.keys()))
            )
        }), 400

    if not subject:
        subject = TEMPLATES[template]["subject"]

    campaign = EmailCampaign(
        id=generate_uuid(),
        name=name,
        subject=subject,
        template=template,
        status="draft",
        created_by=user_id,
        total_recipients=len(recipients_data),
    )
    db.session.add(campaign)

    for r in recipients_data:
        if not r.get("email"):
            continue
        recipient = CampaignRecipient(
            id=generate_uuid(),
            campaign_id=campaign.id,
            email=r["email"].strip().lower(),
            first_name=r.get("first_name", "").strip() or None,
            company=r.get("company", "").strip() or None,
            area=r.get("area", "").strip() or None,
            phone=r.get("phone", "").strip() or None,
        )
        db.session.add(recipient)

    campaign.total_recipients = len([r for r in recipients_data if r.get("email")])
    db.session.commit()

    return jsonify(campaign.to_dict()), 201


# ---------------------------------------------------------------------------
# Import recipients from CSV
# ---------------------------------------------------------------------------
@campaigns_bp.route("/<campaign_id>/import-csv", methods=["POST"])
@require_admin
def import_csv(user_id, campaign_id):
    """Import recipients from CSV text body or file upload.

    CSV must have headers: email (required), first_name, company, area, phone
    """
    campaign = db.session.get(EmailCampaign, campaign_id)
    if not campaign:
        return jsonify({"error": "Campaign not found"}), 404
    if campaign.status != "draft":
        return jsonify({"error": "Can only import to draft campaigns"}), 400

    # Accept CSV as raw text body or file upload
    if request.content_type and "multipart/form-data" in request.content_type:
        file = request.files.get("file")
        if not file:
            return jsonify({"error": "No file uploaded"}), 400
        csv_text = file.read().decode("utf-8")
    else:
        csv_text = request.get_data(as_text=True)

    if not csv_text.strip():
        return jsonify({"error": "Empty CSV"}), 400

    reader = csv.DictReader(io.StringIO(csv_text))
    added = 0
    skipped = 0

    for row in reader:
        email = (row.get("email") or "").strip().lower()
        if not email or "@" not in email:
            skipped += 1
            continue

        # Skip duplicates within this campaign
        existing = CampaignRecipient.query.filter_by(
            campaign_id=campaign.id, email=email
        ).first()
        if existing:
            skipped += 1
            continue

        recipient = CampaignRecipient(
            id=generate_uuid(),
            campaign_id=campaign.id,
            email=email,
            first_name=(row.get("first_name") or "").strip() or None,
            company=(row.get("company") or "").strip() or None,
            area=(row.get("area") or "").strip() or None,
            phone=(row.get("phone") or "").strip() or None,
        )
        db.session.add(recipient)
        added += 1

    campaign.total_recipients = campaign.recipients.count() + added
    db.session.commit()
    campaign.total_recipients = campaign.recipients.count()
    db.session.commit()

    return jsonify({
        "added": added,
        "skipped": skipped,
        "total_recipients": campaign.total_recipients,
    })


# ---------------------------------------------------------------------------
# Send campaign
# ---------------------------------------------------------------------------
def _send_campaign_background(app, campaign_id):
    """Send all pending emails for a campaign in a background thread."""
    with app.app_context():
        campaign = db.session.get(EmailCampaign, campaign_id)
        if not campaign:
            return

        template_info = TEMPLATES.get(campaign.template)
        if not template_info:
            logger.error("Unknown template %s for campaign %s", campaign.template, campaign_id)
            return

        recipients = campaign.recipients.filter_by(status="pending").all()

        for recipient in recipients:
            try:
                # Build template kwargs from recipient data
                kwargs = {}
                if "first_name" in template_info["args"]:
                    kwargs["first_name"] = recipient.first_name
                if "area" in template_info["args"]:
                    kwargs["area"] = recipient.area
                if "customer_name" in template_info["args"]:
                    kwargs["customer_name"] = recipient.first_name
                if "promo_code" in template_info["args"]:
                    kwargs["promo_code"] = "COMEBACK10"

                html = template_info["fn"](**kwargs)

                # Personalize subject line
                subject = campaign.subject
                if recipient.area and "{area}" in subject:
                    subject = subject.replace("{area}", recipient.area)

                result = send_email_sync(recipient.email, subject, html)

                if result is not None:
                    recipient.status = "sent"
                    recipient.sent_at = utcnow()
                    campaign.total_sent += 1
                else:
                    # None means dev mode (no provider configured)
                    recipient.status = "sent"
                    recipient.sent_at = utcnow()
                    campaign.total_sent += 1
                    logger.info("Dev mode: email to %s logged (not actually sent)", recipient.email)

            except Exception as e:
                logger.exception("Failed to send campaign email to %s", recipient.email)
                recipient.status = "failed"
                recipient.error_message = str(e)[:500]
                campaign.total_failed += 1

            db.session.commit()

        campaign.status = "sent"
        campaign.completed_at = utcnow()
        db.session.commit()
        logger.info(
            "Campaign %s complete: %d sent, %d failed",
            campaign_id, campaign.total_sent, campaign.total_failed,
        )


@campaigns_bp.route("/<campaign_id>/send", methods=["POST"])
@require_admin
def send_campaign(user_id, campaign_id):
    """Send all pending emails in a campaign. Runs in background thread."""
    campaign = db.session.get(EmailCampaign, campaign_id)
    if not campaign:
        return jsonify({"error": "Campaign not found"}), 404
    if campaign.status not in ("draft", "paused"):
        return jsonify({"error": "Campaign already {} — cannot send".format(campaign.status)}), 400

    pending_count = campaign.recipients.filter_by(status="pending").count()
    if pending_count == 0:
        return jsonify({"error": "No pending recipients to send to"}), 400

    campaign.status = "sending"
    campaign.sent_at = utcnow()
    db.session.commit()

    # Import current_app to pass to background thread
    from flask import current_app
    app = current_app._get_current_object()

    thread = threading.Thread(
        target=_send_campaign_background,
        args=(app, campaign_id),
        daemon=True,
    )
    thread.start()

    return jsonify({
        "message": "Campaign sending started",
        "pending_recipients": pending_count,
        "campaign": campaign.to_dict(),
    })


# ---------------------------------------------------------------------------
# Pause campaign
# ---------------------------------------------------------------------------
@campaigns_bp.route("/<campaign_id>/pause", methods=["POST"])
@require_admin
def pause_campaign(user_id, campaign_id):
    """Pause a sending campaign."""
    campaign = db.session.get(EmailCampaign, campaign_id)
    if not campaign:
        return jsonify({"error": "Campaign not found"}), 404

    campaign.status = "paused"
    db.session.commit()
    return jsonify(campaign.to_dict())


# ---------------------------------------------------------------------------
# Delete campaign
# ---------------------------------------------------------------------------
@campaigns_bp.route("/<campaign_id>", methods=["DELETE"])
@require_admin
def delete_campaign(user_id, campaign_id):
    """Delete a draft campaign and all its recipients."""
    campaign = db.session.get(EmailCampaign, campaign_id)
    if not campaign:
        return jsonify({"error": "Campaign not found"}), 404
    if campaign.status == "sending":
        return jsonify({"error": "Cannot delete while sending"}), 400

    db.session.delete(campaign)
    db.session.commit()
    return jsonify({"message": "Campaign deleted"})


# ---------------------------------------------------------------------------
# List available templates
# ---------------------------------------------------------------------------
@campaigns_bp.route("/templates", methods=["GET"])
@require_admin
def list_templates(user_id):
    """List available email templates."""
    templates = []
    for key, info in TEMPLATES.items():
        templates.append({
            "id": key,
            "subject": info["subject"],
            "args": info["args"],
        })
    return jsonify({"templates": templates})
