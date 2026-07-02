"""
Concierge (shadow-operator) mode — run real jobs through haulers who have
never installed the app.

Why: supply is the launch bottleneck. Every hauler in Palm Beach County has
a phone; almost none will install Umuve Pro before they've been paid once.
Concierge mode lets admin register a hauler with just a name + phone. They
receive the same first-to-accept SMS offers as app haulers (the dispatcher's
broadcast wave) and run the job from a token-gated mobile console at
``/w/<token>`` — no app, no login, no Stripe. Their payouts park as
``pending_connect`` (payments.attempt_payout already defers when there is no
Stripe Connect account) and are settled by hand (Zelle/cash) through the
admin ledger here, which flips them to ``paid_manual``.

The recruiting pitch inverts: instead of "install my app" it becomes
"I have a paying job tomorrow — want it?". After a hauler has been paid for
a few concierge jobs, /optext sends them the real onboarding link.

Flow:
  admin POST /api/admin/concierge/operators   -> approved, online contractor
  dispatch finds no app operator              -> broadcast offer wave (SMS)
  hauler taps /o/<token>, accepts             -> job assigned (existing path)
  hauler works /w/<token>                     -> accepted..completed via the
                                                 shared transition engine
                                                 (drivers.apply_job_status_transition)
  completion -> auto-payout defers            -> payout_status=pending_connect
  admin GET /api/admin/concierge/ledger       -> owed per hauler
  admin marks paid (Zelle/cash)               -> payout_status=paid_manual
"""

import html
import logging
import os
import re
from functools import wraps
from urllib.parse import quote

from flask import Blueprint, jsonify, redirect, request

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, Contractor, Job, JobOffer, Notification, Payment, User,
    generate_uuid, utcnow,
)
from auth_routes import require_auth

concierge_bp = Blueprint("concierge", __name__)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Admin guard (same pattern as promos.py / admin.py)
# ---------------------------------------------------------------------------
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


def _normalize_phone(raw):
    """Best-effort E.164 for US numbers; returns None if unusable."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return ("+" + digits) if len(digits) > 10 else None


def _owed_for_contractor(contractor_id):
    """Sum of completed-job payouts still waiting on a manual settlement."""
    rows = (
        db.session.query(Payment)
        .join(Job, Payment.job_id == Job.id)
        .filter(Job.driver_id == contractor_id,
                Payment.payout_status == "pending_connect")
        .all()
    )
    return round(sum(p.driver_payout_amount or 0.0 for p in rows), 2)


# ---------------------------------------------------------------------------
# Admin: create / list / update concierge operators
# ---------------------------------------------------------------------------
@concierge_bp.route("/api/admin/concierge/operators", methods=["POST"])
@require_admin
def create_concierge_operator(user_id):
    """Register a phone-only hauler. Name + phone is all it takes."""
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    phone = _normalize_phone(data.get("phone"))
    if not name or not phone:
        return jsonify({"error": "name and phone are required"}), 400

    user = User.query.filter_by(phone=phone).first()
    if user and user.contractor_profile:
        c = user.contractor_profile
        if c.is_concierge:
            return jsonify({"error": "Already a concierge operator",
                            "contractor": c.to_dict()}), 409
        return jsonify({"error": "This phone belongs to an app-registered "
                                 "contractor — no concierge profile needed"}), 409

    if not user:
        user = User(
            id=generate_uuid(),
            name=name,
            phone=phone,
            email=(data.get("email") or "").strip() or None,
            role="driver",
            # No password is ever set: the account cannot log in anywhere.
            # The hauler acts only through unguessable offer tokens.
        )
        db.session.add(user)

    contractor = Contractor(
        id=generate_uuid(),
        user_id=user.id,
        truck_type=(data.get("truck_type") or "pickup"),
        truck_capacity=float(data.get("truck_capacity") or 15.0),
        current_lat=data.get("lat"),
        current_lng=data.get("lng"),
        is_online=True,                 # receiving offer texts; admin can toggle
        approval_status="approved",
        onboarding_status="approved",
        is_concierge=True,
    )
    db.session.add(contractor)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Concierge operator create failed (%s)", phone)
        return jsonify({"error": "Could not create operator (duplicate "
                                 "email/phone?)"}), 409

    try:
        from sms_service import send_sms_async
        send_sms_async(
            phone,
            "{}, you're on umuve's paid-jobs list for your area. We text, "
            "you accept, you haul, we pay same day. First job coming your "
            "way soon. Reply STOP to opt out.".format(name.split()[0]),
        )
    except Exception:
        logger.exception("Concierge welcome SMS failed for %s", phone)

    logger.info("CONCIERGE: operator %s (%s) created by admin %s",
                contractor.id, phone, user_id)
    return jsonify({"success": True, "contractor": contractor.to_dict()}), 201


@concierge_bp.route("/api/admin/concierge/operators", methods=["GET"])
@require_admin
def list_concierge_operators(user_id):
    ops = Contractor.query.filter(Contractor.is_concierge.is_(True)).all()
    out = []
    for c in ops:
        d = c.to_dict()
        d["owed"] = _owed_for_contractor(c.id)
        out.append(d)
    return jsonify({"success": True, "operators": out,
                    "count": len(out)}), 200


@concierge_bp.route("/api/admin/concierge/operators/<contractor_id>", methods=["PUT"])
@require_admin
def update_concierge_operator(user_id, contractor_id):
    c = db.session.get(Contractor, contractor_id)
    if not c or not c.is_concierge:
        return jsonify({"error": "Concierge operator not found"}), 404

    data = request.get_json() or {}
    if "is_online" in data:
        c.is_online = bool(data["is_online"])
    if data.get("name") and c.user:
        c.user.name = data["name"].strip()
    if data.get("phone") and c.user:
        phone = _normalize_phone(data["phone"])
        if not phone:
            return jsonify({"error": "Invalid phone"}), 400
        c.user.phone = phone
    for field in ("lat", "lng"):
        if field in data:
            setattr(c, "current_" + field, data[field])
    if "truck_capacity" in data:
        c.truck_capacity = float(data["truck_capacity"])
    c.updated_at = utcnow()
    db.session.commit()
    return jsonify({"success": True, "contractor": c.to_dict()}), 200


# ---------------------------------------------------------------------------
# Admin: cash ledger
# ---------------------------------------------------------------------------
@concierge_bp.route("/api/admin/concierge/ledger", methods=["GET"])
@require_admin
def concierge_ledger(user_id):
    """What we owe each concierge hauler, job by job.

    ``pending_connect`` = completed job, unpaid (settle via Zelle/cash, then
    mark-paid). ``paid_manual`` entries are included for history.
    """
    rows = (
        db.session.query(Payment, Job, Contractor)
        .join(Job, Payment.job_id == Job.id)
        .join(Contractor, Job.driver_id == Contractor.id)
        .filter(Contractor.is_concierge.is_(True),
                Payment.payout_status.in_(("pending_connect", "paid_manual")))
        .order_by(Payment.updated_at.desc())
        .all()
    )
    by_op = {}
    owed_total = 0.0
    for payment, job, contractor in rows:
        entry = by_op.setdefault(contractor.id, {
            "contractor_id": contractor.id,
            "name": contractor.user.name if contractor.user else None,
            "phone": contractor.user.phone if contractor.user else None,
            "owed": 0.0,
            "entries": [],
        })
        amount = payment.driver_payout_amount or 0.0
        if payment.payout_status == "pending_connect":
            entry["owed"] = round(entry["owed"] + amount, 2)
            owed_total += amount
        entry["entries"].append({
            "payment_id": payment.id,
            "job_id": job.id,
            "address": job.address,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "amount": amount,
            "payout_status": payment.payout_status,
        })
    return jsonify({
        "success": True,
        "owed_total": round(owed_total, 2),
        "operators": list(by_op.values()),
    }), 200


@concierge_bp.route("/api/admin/concierge/payments/<payment_id>/mark-paid", methods=["POST"])
@require_admin
def mark_paid_manual(user_id, payment_id):
    """Record a hand settlement (Zelle/cash/check) for a concierge payout."""
    payment = db.session.get(Payment, payment_id)
    if not payment:
        return jsonify({"error": "Payment not found"}), 404
    if payment.payout_status != "pending_connect":
        return jsonify({"error": "Payout is '{}' — only pending_connect can be "
                                 "marked paid manually".format(payment.payout_status)}), 409

    job = db.session.get(Job, payment.job_id)
    contractor = db.session.get(Contractor, job.driver_id) if job and job.driver_id else None
    if not contractor or not contractor.is_concierge:
        return jsonify({"error": "Not a concierge payout — use the Stripe "
                                 "payout route instead"}), 409

    data = request.get_json() or {}
    method = (data.get("method") or "manual").strip()
    note = (data.get("note") or "").strip()

    payment.payout_status = "paid_manual"
    payment.updated_at = utcnow()
    amount = payment.driver_payout_amount or 0.0
    db.session.add(Notification(
        id=generate_uuid(),
        user_id=contractor.user_id,
        type="payment",
        title="Payout Sent",
        body="${:.2f} paid via {}.".format(amount, method),
        data={"job_id": payment.job_id, "amount": amount,
              "method": method, "note": note},
    ))
    db.session.commit()
    logger.info("CONCIERGE LEDGER: payment %s ($%.2f) marked paid_manual "
                "(%s) by admin %s%s", payment_id, amount, method, user_id,
                " — " + note if note else "")

    try:
        from sms_service import send_sms_async
        if contractor.user and contractor.user.phone:
            send_sms_async(
                contractor.user.phone,
                "umuve: ${:.2f} sent to you via {}. Thanks for the haul — "
                "more jobs coming.".format(amount, method),
            )
    except Exception:
        logger.exception("Paid-manual SMS failed for payment %s", payment_id)

    return jsonify({"success": True, "payment": payment.to_dict()}), 200


# ---------------------------------------------------------------------------
# Admin manual-assign support (called from routes/admin.py assign_job)
# ---------------------------------------------------------------------------
def ensure_concierge_console_link(job, contractor):
    """Mint (or reuse) an accepted JobOffer for a manually-assigned concierge
    hauler and SMS them the console link. Never raises."""
    try:
        offer = JobOffer.query.filter_by(
            job_id=job.id, contractor_id=contractor.id).first()
        if not offer:
            offer = JobOffer(
                id=generate_uuid(),
                job_id=job.id,
                contractor_id=contractor.id,
                status="accepted",
                accept_token=generate_uuid(),
                payout_amount=(job.payment.driver_payout_amount
                               if job.payment else None),
                responded_at=utcnow(),
            )
            db.session.add(offer)
        elif offer.status == "sent":
            offer.status = "accepted"
            offer.responded_at = utcnow()
        db.session.commit()

        from sms_service import send_sms_async
        phone = contractor.user.phone if contractor.user else None
        if phone:
            link = "{}/w/{}".format(PUBLIC_API_URL, offer.accept_token)
            when = (job.scheduled_at.strftime("%b %d at %I:%M %p")
                    if job.scheduled_at else "ASAP")
            send_sms_async(
                phone,
                "umuve JOB assigned to you: {} — {}. Run it from here "
                "(status + your payout): {}".format(
                    (job.address or "address in link")[:60], when, link),
            )
    except Exception:
        logger.exception("ensure_concierge_console_link failed for job %s",
                         getattr(job, "id", "?"))


PUBLIC_API_URL = os.environ.get(
    "PUBLIC_API_URL", "https://junkos-backend.onrender.com"
).rstrip("/")


# ---------------------------------------------------------------------------
# The job console (/w/<token>) — token-gated, mobile-first, zero JS
# ---------------------------------------------------------------------------
# The physical sequence a hauler actually lives. Each entry:
# current job.status -> (next status, button label, waiting hint)
NEXT_ACTION = {
    "assigned":  ("accepted",  "Confirm job",     "Confirm so the customer knows you're on."),
    "accepted":  ("en_route",  "I'm on my way",   "Tap when you leave — the customer gets a text."),
    "en_route":  ("arrived",   "I've arrived",    "Tap at the curb."),
    "arrived":   ("started",   "Start the job",   "Tap before you load."),
    "started":   ("completed", "Job's done",      "Tap once everything is on the truck."),
}

# Rail steps in worked order (status reached -> label shown).
RAIL = [
    ("accepted",  "Confirmed"),
    ("en_route",  "On the way"),
    ("arrived",   "Arrived"),
    ("started",   "Working"),
    ("completed", "Done"),
]
_STATUS_ORDER = ["assigned", "accepted", "en_route", "arrived", "started", "completed"]


def _shell(title, inner, accent="#0f9d58"):
    """Same visual world as the /o/<token> accept page — screen two of one flow."""
    return """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{title} — umuve</title>
<style>
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
         background:#0b0f14; color:#e8eef5; display:flex; min-height:100vh;
         align-items:center; justify-content:center; padding:16px; }}
  .card {{ width:100%; max-width:420px; background:#141b24; border:1px solid #1f2a36;
          border-radius:18px; padding:24px; box-shadow:0 12px 40px rgba(0,0,0,.45); }}
  .brand {{ font-weight:800; letter-spacing:.5px; color:{accent}; font-size:15px;
           text-transform:lowercase; }}
  .jobtag {{ float:right; color:#8aa0b6; font-size:12px; letter-spacing:.6px; }}
  h1 {{ font-size:21px; margin:14px 0 4px; line-height:1.25; }}
  .payline {{ color:{accent}; font-size:30px; font-weight:800; margin:2px 0 14px; }}
  .payline small {{ color:#8aa0b6; font-size:13px; font-weight:600; }}
  .rail {{ list-style:none; margin:0 0 16px; padding:0; display:flex; gap:4px; }}
  .rail li {{ flex:1; text-align:center; font-size:10.5px; letter-spacing:.3px;
             color:#8aa0b6; padding-top:14px; position:relative; }}
  .rail li::before {{ content:""; position:absolute; top:0; left:0; right:0; height:5px;
                     border-radius:3px; background:#1f2a36; }}
  .rail li.done {{ color:#cfe9db; }}
  .rail li.done::before {{ background:{accent}; }}
  .rail li.now {{ color:#f4d9a6; }}
  .rail li.now::before {{ background:#e8a13d; animation:pulse 1.6s ease-in-out infinite; }}
  @keyframes pulse {{ 50% {{ opacity:.45; }} }}
  @media (prefers-reduced-motion: reduce) {{ .rail li.now::before {{ animation:none; }} }}
  .detail {{ background:#0e141c; border:1px solid #1f2a36; border-radius:12px;
            padding:14px 16px; margin:0 0 14px; font-size:15px; }}
  .detail .row {{ display:flex; justify-content:space-between; gap:12px; padding:7px 0;
                 border-bottom:1px solid #19222d; }}
  .detail .row:last-child {{ border-bottom:0; }}
  .detail .k {{ color:#8aa0b6; white-space:nowrap; }}
  .detail .v {{ font-weight:700; text-align:right; }}
  .detail .v a {{ color:#e8eef5; }}
  button, .btn {{ display:block; width:100%; padding:17px; min-height:56px; font-size:17px;
           font-weight:800; border:0; border-radius:12px; background:{accent};
           color:#06210f; cursor:pointer; text-align:center; text-decoration:none; }}
  button:active, .btn:active {{ transform:translateY(1px); }}
  button:focus-visible, a:focus-visible {{ outline:3px solid #e8eef5; outline-offset:2px; }}
  .btn.quiet {{ background:#0e141c; color:#e8eef5; border:1px solid #1f2a36;
               font-weight:600; font-size:15px; min-height:48px; padding:13px; margin-top:10px; }}
  .btn.danger {{ background:#d9534f; color:#fff; }}
  p.note {{ color:#8aa0b6; font-size:13px; text-align:center; margin:14px 0 0; }}
  p.hint {{ color:#8aa0b6; font-size:13px; margin:0 0 10px; }}
</style></head>
<body><div class="card">
  {inner}
</div></body></html>""".format(title=html.escape(title), inner=inner, accent=accent)


def _rail_html(status):
    reached = _STATUS_ORDER.index(status) if status in _STATUS_ORDER else 0
    items = []
    for i, (st, label) in enumerate(RAIL):
        pos = _STATUS_ORDER.index(st)
        cls = "done" if reached >= pos else ("now" if reached == pos - 1 else "")
        items.append('<li class="{}">{}</li>'.format(cls, html.escape(label)))
    return '<ul class="rail">' + "".join(items) + "</ul>"


def _console_ctx(token):
    """Resolve token -> (offer, job, contractor) or an error page tuple."""
    offer = JobOffer.query.filter_by(accept_token=token).first()
    if not offer:
        return None, (_shell("Invalid", '<div class="brand">umuve</div>'
                             "<h1>This link isn't valid</h1>"
                             "<p class='note'>Check the text we sent you, or "
                             "call your umuve contact.</p>", "#d9534f"), 404)
    job = db.session.get(Job, offer.job_id)
    if not job:
        return None, (_shell("Gone", '<div class="brand">umuve</div>'
                             "<h1>This job no longer exists</h1>"
                             "<p class='note'>It may have been cancelled.</p>",
                             "#d9534f"), 410)
    if job.driver_id != offer.contractor_id:
        return None, (_shell("Not yours", '<div class="brand">umuve</div>'
                             "<h1>This job isn't assigned to you</h1>"
                             "<p class='note'>Another hauler claimed it. "
                             "We'll text you the next one.</p>", "#d9534f"), 403)
    if job.status == "cancelled":
        return None, (_shell("Cancelled", '<div class="brand">umuve</div>'
                             "<h1>This job was cancelled</h1>"
                             "<p class='note'>You don't need to do anything. "
                             "We'll text you the next one.</p>", "#d9534f"), 200)
    contractor = db.session.get(Contractor, offer.contractor_id)
    return (offer, job, contractor), None


def _items_summary(job):
    names = []
    for item in (job.items or []):
        if isinstance(item, dict):
            label = (item.get("category") or "item").replace("_", " ").title()
            qty = item.get("quantity") or 1
            names.append("{}× {}".format(qty, label) if qty and qty != 1 else label)
    return ", ".join(names) or "See booking"


@concierge_bp.route("/w/<token>", methods=["GET"])
def concierge_console(token):
    ctx, err = _console_ctx(token)
    if err:
        return err
    offer, job, contractor = ctx

    payout = None
    if job.payment and job.payment.driver_payout_amount:
        payout = job.payment.driver_payout_amount
    elif offer.payout_amount:
        payout = offer.payout_amount
    pay_html = ('<div class="payline">${:.2f} <small>your take-home</small></div>'
                .format(payout) if payout else "")

    customer = db.session.get(User, job.customer_id) if job.customer_id else None
    cust_name = html.escape((customer.name or "Customer").split()[0]) if customer else "Customer"
    cust_tel = ""
    if customer and customer.phone:
        cust_tel = '<a href="tel:{0}">{0}</a>'.format(html.escape(customer.phone))

    addr = html.escape(job.address or "Address unavailable")
    maps = ('https://www.google.com/maps/dir/?api=1&destination=' +
            quote(job.address)) if job.address else None
    when = (job.scheduled_at.strftime("%a %b %d, %I:%M %p")
            if job.scheduled_at else "ASAP")

    rows = [
        '<div class="row"><span class="k">Where</span><span class="v">{}</span></div>'.format(addr),
        '<div class="row"><span class="k">When</span><span class="v">{}</span></div>'.format(when),
        '<div class="row"><span class="k">Load</span><span class="v">{}</span></div>'.format(
            html.escape(_items_summary(job))),
        '<div class="row"><span class="k">Customer</span><span class="v">{}{}</span></div>'.format(
            cust_name, " — " + cust_tel if cust_tel else ""),
    ]
    detail = '<div class="detail">' + "".join(rows) + "</div>"

    header = ('<div class="brand">umuve<span class="jobtag">JOB {}</span></div>'
              .format(html.escape(str(job.id)[:8].upper())))

    if job.status == "completed":
        paid = job.payment and job.payment.payout_status in ("paid", "paid_manual")
        settle = ("Paid — thanks for the haul." if paid else
                  "umuve pays you same day by Zelle or cash. Questions? "
                  "Reply to any of our texts.")
        inner = (header + "<h1>Job complete 🎉</h1>" + pay_html +
                 _rail_html(job.status) + detail +
                 "<p class='note'>{}</p>".format(settle))
        return _shell("Complete", inner)

    action = NEXT_ACTION.get(job.status)
    if not action:
        inner = (header + "<h1>Job status: {}</h1>".format(html.escape(job.status)) +
                 pay_html + _rail_html(job.status) + detail +
                 "<p class='note'>Nothing for you to do right now.</p>")
        return _shell("Job", inner)

    next_status, label, hint = action

    if next_status == "completed" and request.args.get("arm") != "1":
        # Two-step confirm for the money step — server-side, no JS, CSP-proof.
        act = ('<a class="btn" href="/w/{}?arm=1">{}</a>'.format(token, label))
    elif next_status == "completed":
        act = ('<form method="POST" action="/w/{}/advance">'
               '<input type="hidden" name="to" value="completed">'
               '<button type="submit" class="danger" '
               'style="background:#d9534f;color:#fff">Yes — everything\'s loaded, '
               'finish job</button></form>'
               '<a class="btn quiet" href="/w/{}">Not yet — go back</a>'
               .format(token, token))
    else:
        act = ('<form method="POST" action="/w/{}/advance">'
               '<input type="hidden" name="to" value="{}">'
               '<button type="submit">{}</button></form>'
               .format(token, next_status, html.escape(label)))

    nav = ('<a class="btn quiet" href="{}">Open in Maps</a>'.format(maps)
           if maps and job.status in ("accepted", "en_route") else "")

    inner = (header + "<h1>{}</h1>".format(
                 "Next: " + html.escape(label) if job.status != "assigned"
                 else "You've got this job") +
             pay_html + _rail_html(job.status) + detail +
             "<p class='hint'>{}</p>".format(html.escape(hint)) +
             act + nav)
    return _shell("Job console", inner)


@concierge_bp.route("/w/<token>/advance", methods=["POST"])
def concierge_advance(token):
    ctx, err = _console_ctx(token)
    if err:
        return err
    offer, job, contractor = ctx

    target = (request.form.get("to") or "").strip()
    expected = NEXT_ACTION.get(job.status)
    if not expected or target != expected[0]:
        # Stale double-submit (status already moved on) — just re-render.
        return redirect("/w/" + token)

    from routes.drivers import apply_job_status_transition
    ok, payload, code = apply_job_status_transition(job, contractor, target, {})
    if not ok:
        logger.warning("Concierge advance rejected for job %s: %s",
                       job.id, payload.get("error"))
    return redirect("/w/" + token)
