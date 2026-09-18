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

from dispatcher import accept_offer, _aware_utc
from timeutils import fmt_local

offers_bp = Blueprint("offers", __name__)


# ---------------------------------------------------------------------------
# Minimal inline page rendering (no template engine dependency)
# ---------------------------------------------------------------------------
def _page(title, inner_html, tone="go"):
    """One shell for every state of the offer flow.

    The stylesheet is a served FILE, never an inline <style>: these pages run
    under a CSP with style-src 'self', which drops inline blocks silently —
    which is exactly how this page spent its life unstyled in front of haulers.
    """
    return """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex">
<title>{title} — umuve</title>
<link rel="stylesheet" href="/static/hauler.css">
</head>
<body><div class="wrap">
  <div class="mark"><img src="/static/brand-logo.png" alt=""><span>umuve</span></div>
  {inner}
</div></body></html>""".format(title=title, inner=inner_html)


def _closed(title, headline, lede, tone="stop", action_html=""):
    """A state with nothing to accept: taken, expired, gone, invalid.

    Each one says what happened and what happens next — a hauler who tapped a
    dead link should still learn when the next job comes.
    """
    body = ('<h1 class="headline {tone}">{headline}</h1>'
            '<p class="lede">{lede}</p>').format(
                tone=tone, headline=headline, lede=lede)
    if action_html:
        body += '<div class="spacer"></div>' + action_html
    return _page(title, body, tone=tone)


# ---------------------------------------------------------------------------
# GET /o/<token>  — hauler-facing accept page
# ---------------------------------------------------------------------------
@offers_bp.route("/o/<token>", methods=["GET"])
def offer_page(token):
    from models import JobOffer, Job, utcnow

    offer = JobOffer.query.filter_by(accept_token=token).first()
    if not offer:
        return _closed("Invalid", "This link isn't valid",
                       "Check the text we sent you, or reply HELP and a person "
                       "will sort it out."), 404

    job = Job.query.get(offer.job_id)
    if not job:
        return _closed("Gone", "This job is gone",
                       "The customer cancelled it. We'll text you the next one "
                       "in your area."), 410

    console = ('<a class="go quiet" href="/w/{}">Open the job console</a>'
               '<p class="note">Bookmark that page — it is how you run this job '
               'and get paid.</p>').format(token)

    if job.driver_id and job.driver_id != offer.contractor_id:
        return _closed("Taken", "Another hauler got this one",
                       "It went to whoever tapped first. We'll text you the next "
                       "job near you.")

    if job.driver_id == offer.contractor_id:
        concierge = offer.contractor and offer.contractor.is_concierge
        return _closed("Yours", "This job is yours",
                       "Head to the address at the scheduled time." if concierge
                       else "Open the umuve app for directions and full details.",
                       tone="done", action_html=console if concierge else "")

    if offer.expires_at and utcnow() > _aware_utc(offer.expires_at):
        return _closed("Expired", "This offer expired",
                       "Offers are first come, first served. Keep an eye on your "
                       "texts — the next one usually comes within the hour.")

    # Live offer. The take-home is the whole reason they tapped the text, so it
    # leads; the address is the thing they weigh it against.
    payout = "${:,.2f}".format(offer.payout_amount) if offer.payout_amount else "Pay in app"
    when = fmt_local(job.scheduled_at, "%a %b %-d, %-I:%M %p", "As soon as you can")
    dist = ("{:.0f} miles".format(offer.distance_miles)
            if offer.distance_miles is not None else "Nearby")

    # Jobs carry one address string. Split it so the street reads as the
    # headline and the city/zip sits under it — that is the order a hauler
    # scans it in: which street, then how far into town.
    full = (job.address or "").strip()
    if full:
        street, _, rest = full.partition(",")
        addr, city = street.strip(), rest.strip()
    else:
        addr, city = "Address shared when you accept", ""

    clock = ""
    if offer.expires_at:
        mins = int((_aware_utc(offer.expires_at) - utcnow()).total_seconds() // 60)
        if mins >= 1:
            clock = ('<p class="clock">{} minutes left to claim it</p>'
                     .format(mins))

    inner = """
    <p class="payout">{payout}</p>
    <p class="payout-note">Your take-home, after our cut</p>

    <section class="facts">
      <p class="addr">{addr}</p>
      {city}
      <dl class="split">
        <div><dt>Distance</dt><dd>{dist}</dd></div>
        <div><dt>Pickup</dt><dd>{when}</dd></div>
      </dl>
    </section>

    {clock}

    <div class="spacer"></div>

    <form method="POST" action="/o/{token}/accept">
      <button class="go" type="submit">Accept this job</button>
    </form>
    <p class="note">First hauler to accept gets it. One tap is enough.</p>
    """.format(payout=payout, addr=addr,
               city='<p class="addr-sub">{}</p>'.format(city) if city else "",
               dist=dist, when=when, clock=clock, token=token)
    return _page("Job offer", inner)


# ---------------------------------------------------------------------------
# POST /o/<token>/accept  — form submit from the page
# ---------------------------------------------------------------------------
@offers_bp.route("/o/<token>/accept", methods=["POST"])
def offer_accept_page(token):
    from models import JobOffer

    result = accept_offer(token)
    if result["ok"]:
        offer = JobOffer.query.filter_by(accept_token=token).first()
        if offer and offer.contractor and offer.contractor.is_concierge:
            # Phone-only haulers have no app — the console is the only way they
            # can run the job, so it is the action, not a footnote.
            return _closed(
                "Accepted", "The job is yours",
                "Run it from the job console: mark yourself on the way, call the "
                "customer, and close it out when the truck is loaded.",
                tone="done",
                action_html='<a class="go" href="/w/{}">Open the job console</a>'
                            '<p class="note">Bookmark that page — it is how you '
                            'get paid.</p>'.format(token))
        return _closed("Accepted", "The job is yours", result["message"], tone="done")

    return _closed("Sorry", "Couldn't accept that", result["message"])


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
