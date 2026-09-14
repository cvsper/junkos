"""Extra items found on site, billed without an argument.

The promise the customer was given is that the photo price holds for what is
in the photo, and anything else is priced *before it goes on the truck* and
only with their say-so. This is the machinery behind the second half of that
sentence:

    hauler adds items  →  the engine prices the difference  →  ONE text
    "adds $58, new total $315 — reply YES"  →  YES charges the card they
    already used  →  the hauler is told to load it.

Rules that keep it honest:

  * the hauler never types a price. They pick from the same catalog the desk
    and the website use, and `calculate_estimate` prices the whole job again
    so volume discounts and fees stay correct — the add-on is the difference,
    not a second little invoice;
  * nothing is charged without a recorded yes. No reply is not a yes;
  * the card is charged off-session only up to a cap. Above it, or if the
    bank wants the customer present, they get a payment link instead of a
    surprise charge;
  * the job total moves with the approved add-on, so the hauler's payout is
    calculated on what the job actually was.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from models import db, Job, Payment, User
from models_addon import JobAddon

logger = logging.getLogger(__name__)

# Off-session (no customer tapping anything) is convenient but it must never be
# a way to put a large charge through quietly.
MAX_OFF_SESSION = float(os.environ.get("ADDON_MAX_OFF_SESSION", "250"))
MAX_OFF_SESSION_FRACTION = float(os.environ.get("ADDON_MAX_OFF_SESSION_FRACTION", "0.5"))
REPLY_WINDOW_HOURS = 12
OPEN = ("pending",)


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _env(k):
    return (os.environ.get(k) or "").strip()


def digits_of(v):
    d = "".join(ch for ch in str(v or "") if ch.isdigit())
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return d if len(d) == 10 else ""


def _customer(job):
    return db.session.get(User, job.customer_id) if job and job.customer_id else None


def _items_of(job):
    items = job.items if isinstance(job.items, list) else []
    out = []
    for i in items:
        if isinstance(i, dict) and i.get("category"):
            try:
                q = max(1, int(float(i.get("quantity", 1))))
            except Exception:
                q = 1
            out.append({"category": i["category"], "quantity": q,
                        **({"size": i["size"]} if i.get("size") else {})})
    return out


def _name(cat):
    try:
        from call_kit import price_sheet
        for row in price_sheet():
            if row.get("key") == cat:
                return row.get("label") or cat
    except Exception:
        pass
    return str(cat or "item").replace("_", " ")


# ---------------------------------------------------------------------------
# pricing: re-price the whole job, charge the difference
# ---------------------------------------------------------------------------
def quote(job, extra_items, extra_addons=None):
    """→ {amount, new_total, old_total, items} for the items found on site."""
    from routes.booking import calculate_estimate
    base = _items_of(job)
    add = []
    for i in (extra_items or []):
        if not isinstance(i, dict) or not i.get("category"):
            continue
        try:
            q = max(1, min(60, int(float(i.get("quantity", 1)))))
        except Exception:
            q = 1
        add.append({"category": str(i["category"]).strip().lower(), "quantity": q,
                    **({"size": i["size"]} if i.get("size") else {})})
    if not add and not extra_addons:
        return None
    before = float(job.total_price or 0)
    merged = list(base)
    for a in add:
        for m in merged:
            if m["category"] == a["category"] and m.get("size") == a.get("size"):
                m["quantity"] += a["quantity"]
                break
        else:
            merged.append(dict(a))
    after = calculate_estimate(merged, addons=extra_addons or None)
    new_total = round(float(after.get("total") or 0), 2)
    # Never bill less than the job already is: an add-on is an addition.
    amount = round(max(0.0, new_total - before), 2)
    return {"amount": amount, "new_total": round(max(new_total, before), 2), "old_total": before,
            "items": [{"category": a["category"], "quantity": a["quantity"],
                       "name": _name(a["category"])} for a in add]}


def _lines(addon):
    out = []
    for i in (addon.items or []):
        n = i.get("name") or str(i.get("category", "item")).replace("_", " ")
        q = i.get("quantity", 1)
        out.append("{}{}".format(n, " x{}".format(q) if q > 1 else ""))
    return ", ".join(out) or (addon.note or "extra items")


def _send(digits, body):
    try:
        from sms_service import send_sms_async
        send_sms_async("+1" + digits, body)
        return True
    except Exception:
        logger.exception("addon: could not text %s", digits[-4:])
        return False


def ask_text(addon, job, first_name=None, hauler=None):
    who = (hauler or addon.requested_by or "Our hauler").split()[0]
    hi = "Hi {}, ".format(first_name) if first_name else ""
    return ("{}{} is at your pickup and found {} that wasn't in the original job.\n\n"
            "That adds ${:.0f} — new total ${:.0f}.\n\n"
            "Reply YES to include it, or NO and we'll take only what was quoted. "
            "Nothing goes on the truck until you answer."
            ).format(hi, who, _lines(addon), addon.amount, addon.new_total or 0)


# ---------------------------------------------------------------------------
# request → ask
# ---------------------------------------------------------------------------
def request(job, extra_items, requested_by, note=None, contractor_id=None, extra_addons=None):
    """Price the extras and ask the customer. Returns (addon, error)."""
    if job is None:
        return None, "Job not found."
    if job.status in ("completed", "cancelled", "canceled"):
        return None, "That job is already finished."
    open_one = (JobAddon.query.filter(JobAddon.job_id == job.id, JobAddon.status.in_(OPEN))
                .order_by(JobAddon.created_at.desc()).first())
    if open_one:
        return None, "There's already an add-on waiting on the customer."
    q = quote(job, extra_items, extra_addons)
    if not q:
        return None, "Pick at least one item."
    if q["amount"] <= 0:
        return None, "Those items don't change the price — just take them."

    addon = JobAddon(job_id=job.id, items=q["items"], note=(note or "")[:500],
                     amount=q["amount"], new_total=q["new_total"],
                     requested_by=(requested_by or "hauler")[:80], requested_by_id=contractor_id,
                     status="pending", asked_at=_now())
    db.session.add(addon)
    db.session.commit()

    cust = _customer(job)
    digits = digits_of(getattr(cust, "phone", None))
    first = (getattr(cust, "name", "") or "").split()[0] if cust else None
    if digits:
        _send(digits, ask_text(addon, job, first, requested_by))
    else:
        logger.warning("addon %s: customer has no phone, desk must ask", addon.id)
        addon.last_error = "no customer phone — ask them in person"
        db.session.commit()
    _alert(addon, job, "waiting on the customer")
    return addon, None


def open_for_phone(digits, hours=REPLY_WINDOW_HOURS):
    """The add-on this phone number is being asked about, if any."""
    d = digits_of(digits)
    if not d:
        return None
    since = _now() - timedelta(hours=hours)
    rows = (db.session.query(JobAddon, Job)
            .join(Job, Job.id == JobAddon.job_id)
            .join(User, User.id == Job.customer_id)
            .filter(JobAddon.status.in_(OPEN), JobAddon.asked_at >= since)
            .order_by(JobAddon.asked_at.desc()).limit(40).all())
    for addon, job in rows:
        cust = _customer(job)
        if cust and digits_of(cust.phone) == d:
            return addon
    return None


# ---------------------------------------------------------------------------
# yes / no
# ---------------------------------------------------------------------------
_YES = {"yes", "y", "yeah", "yep", "yup", "ok", "okay", "sure", "do it", "take it",
        "go ahead", "confirmed", "approve", "approved", "yes please"}
_NO = {"no", "n", "nope", "nah", "don't", "dont", "decline", "leave it", "no thanks",
       "skip it", "just what was quoted"}


def read_reply(text):
    t = " ".join((text or "").strip().lower().split())
    t = t.strip(".!,")
    if not t:
        return None
    if t in _YES or t.startswith(("yes", "yeah", "yep", "ok", "okay", "sure", "go ahead", "do it")):
        return True
    if t in _NO or t.startswith(("no", "nope", "nah", "don't", "dont", "decline", "leave it")):
        return False
    return None


def handle_reply(phone, body_text):
    """A text with no photo. Returns the addon when it was an answer, else None."""
    addon = open_for_phone(phone)
    if addon is None:
        return None
    answer = read_reply(body_text)
    if answer is None:
        return None                       # not a yes/no — let normal routing have it
    addon.reply_text = (body_text or "")[:500]
    addon.replied_at = _now()
    addon.approved_via = "sms"
    job = db.session.get(Job, addon.job_id)
    if answer is False:
        addon.status = "declined"
        db.session.commit()
        _tell_hauler(addon, job, "Customer said no — take only what was quoted.")
        _alert(addon, job, "declined")
        digits = digits_of(getattr(_customer(job), "phone", None))
        if digits:
            _send(digits, "No problem — we'll take only what was quoted. Nothing extra charged.")
        return addon
    addon.status = "approved"
    db.session.commit()
    charge(addon)
    return addon


# ---------------------------------------------------------------------------
# money
# ---------------------------------------------------------------------------
def _saved_card(job):
    """(customer_id, payment_method_id) from the card they already used, or None."""
    pay = Payment.query.filter_by(job_id=job.id).first()
    cust = _customer(job)
    pm = getattr(pay, "stripe_payment_method_id", None) if pay else None
    cid = getattr(cust, "stripe_customer_id", None) if cust else None
    return (cid, pm) if (cid and pm) else (None, None)


def _off_session_cap(job):
    base = float(job.total_price or 0)
    return min(MAX_OFF_SESSION, base * MAX_OFF_SESSION_FRACTION) if base else MAX_OFF_SESSION


def charge(addon, job=None):
    """Charge an approved add-on. Falls back to a payment link, never silently."""
    job = job or db.session.get(Job, addon.job_id)
    if job is None or addon.status not in ("approved",):
        return addon
    cap = _off_session_cap(job)
    cid, pm = _saved_card(job)

    if addon.amount > cap or not (cid and pm):
        why = "over the off-session cap" if addon.amount > cap else "no saved card"
        url = _pay_link(addon, job)
        addon.pay_url = url
        addon.last_error = why
        db.session.commit()
        digits = digits_of(getattr(_customer(job), "phone", None))
        if digits and url:
            _send(digits, "Thanks — one tap to add it: {}\nThat's the ${:.0f} difference; "
                          "your original booking is unchanged.".format(url, addon.amount))
        _tell_hauler(addon, job, "Customer approved. Payment link sent ({}), load it.".format(why))
        _alert(addon, job, "approved · link sent ({})".format(why))
        return addon

    from routes.payments import _stripe_key, _get_stripe
    if not _stripe_key():
        addon.status = "charged"          # dev/test: treat as settled so the flow is testable
        addon.charged_at = _now()
        addon.intent_id = "pi_dev_addon_{}".format(addon.id[:8])
        _apply_to_job(addon, job)
        db.session.commit()
        _tell_hauler(addon, job, "Customer approved — load it.")
        return addon

    stripe = _get_stripe()
    try:
        intent = stripe.PaymentIntent.create(
            amount=int(round(addon.amount * 100)), currency="usd",
            customer=cid, payment_method=pm, off_session=True, confirm=True,
            description="Umuve add-on for job {}".format(job.confirmation_code or job.id[:8]),
            metadata={"job_id": job.id, "addon_id": addon.id, "kind": "on_site_addon"},
            idempotency_key="addon_{}".format(addon.id))
        addon.intent_id = getattr(intent, "id", None)
        if getattr(intent, "status", "") == "succeeded":
            addon.status = "charged"
            addon.charged_at = _now()
            _apply_to_job(addon, job)
            db.session.commit()
            digits = digits_of(getattr(_customer(job), "phone", None))
            if digits:
                _send(digits, "Added — ${:.0f} charged to the card on file. New total ${:.0f}. "
                              "Thanks!".format(addon.amount, addon.new_total or 0))
            _tell_hauler(addon, job, "Customer approved and paid — load it.")
            _alert(addon, job, "charged ${:.0f}".format(addon.amount))
            return addon
        addon.last_error = "intent status {}".format(getattr(intent, "status", "?"))
    except Exception as e:                       # includes a bank asking for the customer
        addon.last_error = str(e)[:400]
        logger.exception("addon %s: off-session charge failed", addon.id)

    url = _pay_link(addon, job)
    addon.pay_url = url
    addon.status = "failed"
    db.session.commit()
    digits = digits_of(getattr(_customer(job), "phone", None))
    if digits and url:
        _send(digits, "Your bank wants you to confirm this one — one tap: {}\n"
                      "That's the ${:.0f} difference.".format(url, addon.amount))
    _tell_hauler(addon, job, "Customer approved. Card needs confirming — link sent, load it.")
    _alert(addon, job, "approved but the card needs the customer: " + (addon.last_error or ""))
    return addon


def _pay_link(addon, job):
    """A link for just the difference — never a second charge for the whole job."""
    try:
        from routes.vapi import _build_checkout_url
        return _build_checkout_url(job.id, addon.amount)
    except Exception:
        logger.exception("addon: could not build a pay link")
        return None


def _apply_to_job(addon, job):
    """The job becomes what it actually was, so the payout is right."""
    try:
        job.total_price = round(float(job.total_price or 0) + float(addon.amount), 2)
        items = list(job.items if isinstance(job.items, list) else [])
        for i in (addon.items or []):
            items.append({"category": i.get("category"), "quantity": i.get("quantity", 1),
                          "added_on_site": True})
        job.items = items
        pay = Payment.query.filter_by(job_id=job.id).first()
        if pay:
            pay.amount = round(float(pay.amount or 0) + float(addon.amount), 2)
    except Exception:
        logger.exception("addon %s: could not apply to job %s", addon.id, getattr(job, "id", "?"))


def mark_paid_by_link(job_id, intent_id=None):
    """The Stripe webhook saw the link get paid."""
    addon = (JobAddon.query.filter(JobAddon.job_id == job_id,
                                   JobAddon.status.in_(("approved", "failed")))
             .order_by(JobAddon.created_at.desc()).first())
    if addon is None:
        return None
    job = db.session.get(Job, job_id)
    addon.status = "charged"
    addon.charged_at = _now()
    addon.intent_id = addon.intent_id or intent_id
    if job is not None:
        _apply_to_job(addon, job)
    db.session.commit()
    _tell_hauler(addon, job, "Add-on paid — you're clear.")
    return addon


def expire_stale(hours=REPLY_WINDOW_HOURS):
    """No answer is not a yes. Close the question so it can be asked again."""
    cutoff = _now() - timedelta(hours=hours)
    rows = JobAddon.query.filter(JobAddon.status == "pending", JobAddon.asked_at < cutoff).all()
    for a in rows:
        a.status = "expired"
    if rows:
        db.session.commit()
    return len(rows)


# ---------------------------------------------------------------------------
# telling people
# ---------------------------------------------------------------------------
def _tell_hauler(addon, job, message):
    try:
        if job is None or not job.driver_id:
            return
        from models import Contractor
        c = db.session.get(Contractor, job.driver_id)
        u = db.session.get(User, c.user_id) if c else None
        d = digits_of(getattr(u, "phone", None))
        if d:
            _send(d, "{} — {}".format(job.confirmation_code or "Job", message))
    except Exception:
        logger.exception("addon: could not tell the hauler")


def _alert(addon, job, what):
    try:
        from booking_alerts import _phones
        phones = _phones()
    except Exception:
        phones = []
    head = "Add-on · {}".format(what)
    body = "\n".join([head,
                      "{} · ${:.0f} → new total ${:.0f}".format(
                          (job.confirmation_code if job else "job"), addon.amount, addon.new_total or 0),
                      _lines(addon),
                      "by " + (addon.requested_by or "?"),
                      "Desk: {}/va/dispatch".format(_env("DESK_PUBLIC_URL") or "https://ops.goumuve.com")])
    for p in phones:
        try:
            from sms_service import send_sms_async
            send_sms_async(p, body)
        except Exception:
            logger.exception("addon alert sms failed")
    hook = _env("SLACK_ALERT_WEBHOOK")
    if hook:
        try:
            import requests
            requests.post(hook, json={"text": "*{}*\n```{}```".format(head, body)}, timeout=10)
        except Exception:
            logger.exception("addon alert slack failed")


def for_job(job_id):
    return [a.to_dict() for a in (JobAddon.query.filter_by(job_id=job_id)
                                  .order_by(JobAddon.created_at.desc()).all())]
