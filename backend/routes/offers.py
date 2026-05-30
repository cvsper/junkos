"""
Marketplace job-offer routes (broadcast / first-to-accept).

When a job is dispatched in broadcast mode (DISPATCH_MODE=broadcast), every
eligible hauler gets an SMS with a link to ``/o/<token>``. This blueprint
serves a mobile-friendly accept page so a hauler can claim the job straight
from their phone browser — no app install required (critical for landing the
first trucks). The first to accept wins atomically; the rest see "taken".

Also exposes JSON endpoints under ``/api/offers`` for the in-app flow.
"""

from flask import Blueprint, request, jsonify

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dispatcher import accept_offer

offers_bp = Blueprint("offers", __name__)


# ---------------------------------------------------------------------------
# Minimal inline page rendering (no template engine dependency)
# ---------------------------------------------------------------------------
def _page(title, headline, body_html, accent="#0f9d58"):
    return """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — umuve</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
         background:#0b0f14; color:#e8eef5; display:flex; min-height:100vh;
         align-items:center; justify-content:center; padding:24px; }}
  .card {{ width:100%; max-width:420px; background:#141b24; border:1px solid #1f2a36;
          border-radius:18px; padding:28px; box-shadow:0 12px 40px rgba(0,0,0,.45); }}
  .brand {{ font-weight:800; letter-spacing:.5px; color:{accent}; font-size:15px;
           text-transform:lowercase; margin-bottom:18px; }}
  h1 {{ font-size:22px; margin:0 0 10px; line-height:1.25; }}
  .detail {{ background:#0e141c; border:1px solid #1f2a36; border-radius:12px;
            padding:16px; margin:18px 0; font-size:15px; }}
  .detail .row {{ display:flex; justify-content:space-between; padding:6px 0;
                 border-bottom:1px solid #19222d; }}
  .detail .row:last-child {{ border-bottom:0; }}
  .detail .k {{ color:#8aa0b6; }}
  .detail .v {{ font-weight:700; text-align:right; }}
  .payout {{ color:{accent}; font-size:20px; }}
  button {{ width:100%; padding:16px; font-size:17px; font-weight:800; border:0;
           border-radius:12px; background:{accent}; color:#06210f; cursor:pointer; }}
  button:active {{ transform:translateY(1px); }}
  p.note {{ color:#8aa0b6; font-size:13px; text-align:center; margin-top:16px; }}
</style></head>
<body><div class="card">
  <div class="brand">umuve</div>
  <h1>{headline}</h1>
  {body}
</div></body></html>""".format(
        title=title, headline=headline, body=body_html, accent=accent
    )


# ---------------------------------------------------------------------------
# GET /o/<token>  — hauler-facing accept page
# ---------------------------------------------------------------------------
@offers_bp.route("/o/<token>", methods=["GET"])
def offer_page(token):
    from models import JobOffer, Job, utcnow

    offer = JobOffer.query.filter_by(accept_token=token).first()
    if not offer:
        return _page("Invalid", "This link isn't valid",
                     "<p class='note'>The job offer link is incorrect or has been removed.</p>",
                     accent="#d9534f"), 404

    job = Job.query.get(offer.job_id)
    if not job:
        return _page("Gone", "This job no longer exists",
                     "<p class='note'>It may have been cancelled.</p>", accent="#d9534f"), 410

    # Already taken?
    if job.driver_id and job.driver_id != offer.contractor_id:
        return _page("Taken", "Already claimed",
                     "<p class='note'>Another hauler grabbed this job first. "
                     "We'll text you the next one.</p>", accent="#d9534f")

    if job.driver_id == offer.contractor_id:
        return _page("Yours", "This job is yours ✅",
                     "<p class='note'>Open the umuve app for full details and navigation.</p>")

    if offer.expires_at and utcnow() > offer.expires_at:
        return _page("Expired", "This offer expired",
                     "<p class='note'>Offers are first-come, first-served. "
                     "Watch for the next text.</p>", accent="#d9534f")

    # Live offer — render details + accept button
    payout = "${:.2f}".format(offer.payout_amount) if offer.payout_amount else "See app"
    dist = ("{:.0f} mi away".format(offer.distance_miles)
            if offer.distance_miles is not None else "Nearby")
    when = job.scheduled_at.strftime("%b %d, %I:%M %p") if job.scheduled_at else "ASAP"
    addr = job.address or "Address shared on accept"

    body = """
    <div class="detail">
      <div class="row"><span class="k">Your take-home</span><span class="v payout">{payout}</span></div>
      <div class="row"><span class="k">Location</span><span class="v">{addr}</span></div>
      <div class="row"><span class="k">Distance</span><span class="v">{dist}</span></div>
      <div class="row"><span class="k">When</span><span class="v">{when}</span></div>
    </div>
    <form method="POST" action="/o/{token}/accept">
      <button type="submit">Accept this job</button>
    </form>
    <p class="note">First to accept gets it. Tap once.</p>
    """.format(payout=payout, addr=addr, dist=dist, when=when, token=token)
    return _page("Job offer", "New job available", body)


# ---------------------------------------------------------------------------
# POST /o/<token>/accept  — form submit from the page
# ---------------------------------------------------------------------------
@offers_bp.route("/o/<token>/accept", methods=["POST"])
def offer_accept_page(token):
    result = accept_offer(token)
    if result["ok"]:
        return _page("Accepted", "Job accepted! 🎉",
                     "<p class='note'>{}</p>".format(result["message"]))
    accent = "#d9534f"
    return _page("Sorry", "Couldn't accept",
                 "<p class='note'>{}</p>".format(result["message"]), accent=accent)


# ---------------------------------------------------------------------------
# JSON API (in-app flow)
# ---------------------------------------------------------------------------
@offers_bp.route("/api/offers/<token>", methods=["GET"])
def offer_detail(token):
    from models import JobOffer, Job
    offer = JobOffer.query.filter_by(accept_token=token).first()
    if not offer:
        return jsonify({"success": False, "error": "Offer not found"}), 404
    job = Job.query.get(offer.job_id)
    return jsonify({
        "success": True,
        "offer": offer.to_dict(),
        "job": job.to_dict() if job else None,
        "claimable": bool(job and not job.driver_id),
    }), 200


@offers_bp.route("/api/offers/<token>/accept", methods=["POST"])
def offer_accept_json(token):
    result = accept_offer(token)
    code = 200 if result["ok"] else 409
    if result["status"] in ("invalid",):
        code = 404
    elif result["status"] == "error":
        code = 500
    return jsonify({
        "success": result["ok"],
        "status": result["status"],
        "message": result["message"],
        "job": result["job"],
    }), code
