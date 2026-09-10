"""Same-day hauler pay.

1. Instant payout after every completed job (app haulers with Stripe):
   the platform already transfers the hauler's share to their connected
   account on completion; `instant_after_transfer` then pushes it to their
   debit card with a Stripe instant payout and covers the instant fee with a
   small follow-up transfer so the hauler nets the full amount. If the
   account can't take instant payouts (no debit card yet) it falls back to
   the free standard payout and texts the hauler why. Flag `auto_instant_payout`.
2. Owed-today ledger for phone-only haulers: every completed job whose payout
   is parked (no Stripe) or failed, grouped by hauler, with a Zelle memo and
   one-tap mark-paid; a 5pm ET alert if anything from today is still unpaid.
3. Text-based Stripe onboarding so phone-only haulers graduate to automatic.
4. Balance guard for the desk health check: Umuve's available Stripe balance
   vs the payouts coming due.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from models import db, Payment, Job, Contractor, User, Notification, DeskSetting, generate_uuid, utcnow
from desk_auth import require_desk, audit, MANAGER_ROLES

try:
    from extensions import limiter
except Exception:  # pragma: no cover
    limiter = None

logger = logging.getLogger(__name__)
pay_bp = Blueprint("sameday_pay", __name__)
_ratelimit = (limiter.limit("240 per hour; 30 per minute") if limiter is not None else (lambda f: f))

INSTANT_FEE_RATE = float(os.environ.get("INSTANT_PAYOUT_FEE_RATE", "0.015") or 0.015)
INSTANT_FEE_MIN = float(os.environ.get("INSTANT_PAYOUT_FEE_MIN", "0.50") or 0.50)
INSTANT_MIN_CENTS = 100          # Stripe minimum instant payout is $1.00
MIN_BALANCE = float(os.environ.get("STRIPE_MIN_BALANCE", "500") or 500)
UNPAID_STATUSES = ("pending_connect", "failed")


def _stripe():
    from routes.payments import _get_stripe
    return _get_stripe()


def _now():
    return datetime.now(timezone.utc)


def _local_day_bounds(dt_utc=None):
    from timeutils import to_local, local_naive_to_utc
    d = to_local(dt_utc or _now()).date()
    start = local_naive_to_utc(datetime.combine(d, datetime.min.time())).replace(tzinfo=None)
    return start, start + timedelta(days=1)


def fee_estimate(amount):
    return round(max(INSTANT_FEE_MIN, amount * INSTANT_FEE_RATE), 2)


def instant_enabled():
    try:
        from flags import flag
        return flag("auto_instant_payout") and bool(os.environ.get("STRIPE_SECRET_KEY", ""))
    except Exception:
        return False


def instant_optout(contractor):
    return (DeskSetting.get("instant_optout:" + contractor.id) or "").lower() in ("1", "on", "true")


def _sms(contractor, text):
    try:
        from sms_service import send_sms_async
        phone = contractor.user.phone if contractor.user else None
        if phone:
            send_sms_async(phone, text)
    except Exception:
        logger.exception("payout sms failed for contractor %s", contractor.id)


# ---------------------------------------------------------------------------
# 1. instant payout after the transfer
# ---------------------------------------------------------------------------
def instant_after_transfer(payment, contractor, amount):
    """Called right after the completion transfer. Never raises. Returns a dict."""
    result = {"method": "standard", "reason": None}
    if amount <= 0:
        return result
    if not instant_enabled():
        payment.payout_method = payment.payout_method or "standard"
        db.session.commit()
        return dict(result, reason="instant payouts off")
    if instant_optout(contractor):
        payment.payout_method = "standard"
        db.session.commit()
        return dict(result, reason="hauler opted out")
    cid = contractor.stripe_connect_id or ""
    if not cid or cid.startswith("acct_dev_"):
        from app_config import is_production
        if is_production():
            # Fail closed (audit F08): a missing/mock Connect id in production
            # is never a payout destination — no fake po_mock success.
            logger.error("instant payout refused for job %s: contractor %s has no real Connect account",
                         payment.job_id, contractor.id)
            payment.payout_method = "standard"
            db.session.commit()
            return dict(result, reason="payments unavailable: no real payout account")
        payment.payout_method = "instant"
        payment.instant_payout_id = "po_mock"
        payment.payout_arrival_at = _now().replace(tzinfo=None)
        db.session.commit()
        return {"method": "instant", "reason": "mock account", "payout_id": "po_mock"}
    stripe = _stripe()
    try:
        bal = stripe.Balance.retrieve(stripe_account=cid)
        available = next((b.amount for b in bal.available if b.currency == "usd"), 0)
        cents = min(int(round(amount * 100)), int(available))
        if cents < INSTANT_MIN_CENTS:
            raise RuntimeError("balance not yet available for instant payout")
        payout = stripe.Payout.create(
            amount=cents, currency="usd", method="instant",
            stripe_account=cid, idempotency_key="instant_{}".format(payment.job_id),
            metadata={"job_id": payment.job_id, "kind": "same_day"},
        )
        fee = fee_estimate(cents / 100.0)
        covered = 0.0
        try:
            stripe.Transfer.create(
                amount=int(round(fee * 100)), currency="usd", destination=cid,
                idempotency_key="instantfee_{}".format(payment.job_id),
                metadata={"job_id": payment.job_id, "kind": "instant_fee_cover"},
            )
            covered = fee
        except Exception:
            logger.exception("instant fee cover transfer failed for job %s", payment.job_id)
        payment.payout_method = "instant"
        payment.instant_payout_id = getattr(payout, "id", None)
        arrival = getattr(payout, "arrival_date", None)
        payment.payout_arrival_at = (datetime.fromtimestamp(arrival, tz=timezone.utc).replace(tzinfo=None)
                                     if arrival else _now().replace(tzinfo=None))
        payment.payout_fee_cover = covered
        db.session.commit()
        _sms(contractor, "umuve: ${:.2f} is on its way to your debit card right now (instant payout). "
                         "Thanks for the haul.".format(cents / 100.0))
        audit("instant_payout", "payment", payment.id,
              {"job_id": payment.job_id, "amount": cents / 100.0, "fee_cover": covered,
               "payout_id": payment.instant_payout_id}, via="system")
        return {"method": "instant", "payout_id": payment.instant_payout_id, "amount": cents / 100.0,
                "fee_cover": covered}
    except Exception as e:
        msg = str(e)
        low = msg.lower()
        if "instant" in low or "external" in low or "debit" in low or "eligib" in low:
            reason = "no debit card set up for instant payouts"
        elif "balance" in low or "insufficient" in low:
            reason = "funds not yet available"
        else:
            reason = "instant payout failed"
        logger.warning("instant payout fallback for job %s: %s (%s)", payment.job_id, reason, msg[:200])
        payment.payout_method = "standard"
        db.session.commit()
        _sms(contractor, "umuve: ${:.2f} is in your Umuve payout account and lands in your bank in about "
                         "2 business days. Add a debit card in the Umuve Pro app to get paid the same day "
                         "next time.".format(amount))
        audit("instant_payout_fallback", "payment", payment.id,
              {"job_id": payment.job_id, "amount": amount, "reason": reason}, via="system")
        return {"method": "standard", "reason": reason}


# ---------------------------------------------------------------------------
# 2. owed-today ledger
# ---------------------------------------------------------------------------
def _short_addr(addr):
    return (addr or "").split(",")[0][:40]


def owed_rows(days=30):
    since = (_now() - timedelta(days=days)).replace(tzinfo=None)
    day_start, day_end = _local_day_bounds()
    q = (db.session.query(Payment, Job).join(Job, Job.id == Payment.job_id)
         .filter(Payment.payout_status.in_(UNPAID_STATUSES), Job.driver_id.isnot(None),
                 Job.status.in_(("completed", "paid", "closed")) | Job.completed_at.isnot(None))
         .filter((Job.completed_at >= since) | (Payment.updated_at >= since)))
    rows = []
    for payment, job in q.all():
        amount = round(payment.driver_payout_amount or 0.0, 2)
        if amount <= 0:
            continue
        c = db.session.get(Contractor, job.driver_id)
        u = c.user if c else None
        done = job.completed_at or payment.updated_at
        rows.append({
            "payment_id": payment.id, "job_id": job.id, "job_code": getattr(job, "confirmation_code", None) or job.id[:8],
            "contractor_id": c.id if c else None,
            "hauler": (getattr(c, "business_name", None) or (u.name if u else None) or "Hauler"),
            "phone": u.phone if u else None, "concierge": bool(getattr(c, "is_concierge", False)) if c else False,
            "has_stripe": bool(c and c.stripe_connect_id and not c.stripe_connect_id.startswith("acct_dev_")),
            "amount": amount, "status": payment.payout_status,
            "completed_at": (done.isoformat() + "Z") if done else None,
            "today": bool(done and day_start <= done < day_end),
            "address": _short_addr(job.address),
            "memo": "Umuve {} · {} · ${:.2f}".format(getattr(job, "confirmation_code", None) or job.id[:8],
                                                   _short_addr(job.address), amount),
        })
    rows.sort(key=lambda r: (not r["today"], r["completed_at"] or ""), reverse=False)
    by_hauler = {}
    for r in rows:
        k = r["contractor_id"] or r["hauler"]
        h = by_hauler.setdefault(k, {"hauler": r["hauler"], "phone": r["phone"], "contractor_id": r["contractor_id"],
                                     "concierge": r["concierge"], "has_stripe": r["has_stripe"],
                                     "total": 0.0, "today_total": 0.0, "jobs": []})
        h["total"] = round(h["total"] + r["amount"], 2)
        if r["today"]:
            h["today_total"] = round(h["today_total"] + r["amount"], 2)
        h["jobs"].append(r)
    haulers = sorted(by_hauler.values(), key=lambda h: (-h["today_total"], -h["total"]))
    return {"rows": rows, "haulers": haulers,
            "today_total": round(sum(r["amount"] for r in rows if r["today"]), 2),
            "total": round(sum(r["amount"] for r in rows), 2),
            "count": len(rows), "today_count": sum(1 for r in rows if r["today"])}


def mark_paid(payment, method, ref, actor_name=None):
    job = db.session.get(Job, payment.job_id)
    contractor = db.session.get(Contractor, job.driver_id) if job and job.driver_id else None
    amount = payment.driver_payout_amount or 0.0
    payment.payout_status = "paid_manual"
    payment.payout_method = "manual"
    payment.payout_arrival_at = _now().replace(tzinfo=None)
    payment.updated_at = utcnow()
    if contractor:
        db.session.add(Notification(id=generate_uuid(), user_id=contractor.user_id, type="payment",
                                    title="Payout Sent", body="${:.2f} paid via {}.".format(amount, method),
                                    data={"job_id": payment.job_id, "amount": amount, "method": method, "ref": ref}))
    db.session.commit()
    if contractor:
        _sms(contractor, "umuve: ${:.2f} sent to you via {}{}. Thanks for the haul — more jobs coming.".format(
            amount, method, (" (" + ref + ")") if ref else ""))
    audit("payout_marked_paid", "payment", payment.id, {"amount": amount, "method": method, "ref": ref, "by": actor_name})
    return amount


def owed_alert(app=None):
    """5pm ET: anything completed today and still unpaid → alert. Never raises."""
    def _do():
        rep = owed_rows(days=7)
        todays = [r for r in rep["rows"] if r["today"]]
        summary = {"at": _now().isoformat(), "today_count": len(todays), "today_total": rep["today_total"]}
        DeskSetting.put("owed:last", json.dumps(summary))
        if not todays:
            return summary
        lines = ["${:.2f} owed to {} hauler{} for jobs completed today:".format(
            rep["today_total"], len({r['contractor_id'] for r in todays}), "" if len(todays) == 1 else "s")]
        for h in rep["haulers"]:
            if h["today_total"]:
                lines.append("  {} — ${:.2f}{}{}".format(h["hauler"], h["today_total"],
                                                       (" · " + h["phone"]) if h["phone"] else "",
                                                       "" if h["has_stripe"] else " · no Stripe (Zelle)"))
        lines.append("Settle from /va/manager → Haulers owed today.")
        try:
            from desk_health import _send_alert
            _send_alert("Haulers owed today: ${:.2f}".format(rep["today_total"]), "\n".join(lines))
        except Exception:
            logger.exception("owed alert send failed")
        return summary
    if app is not None:
        with app.app_context():
            try:
                return _do()
            except Exception:
                logger.exception("owed alert failed")
    else:
        return _do()


# ---------------------------------------------------------------------------
# 3. text-based Stripe onboarding
# ---------------------------------------------------------------------------
def onboarding_link(contractor):
    """Express account (created if missing) + onboarding link. Returns the URL."""
    stripe = _stripe()
    base_url = os.environ.get("APP_BASE_URL", "https://junkos-backend.onrender.com").rstrip("/")
    acct_id = contractor.stripe_connect_id
    if not acct_id or acct_id.startswith("acct_dev_"):
        acct = stripe.Account.create(type="express", country="US",
                                     capabilities={"card_payments": {"requested": True},
                                                   "transfers": {"requested": True}})
        contractor.stripe_connect_id = acct.id
        db.session.commit()
        acct_id = acct.id
    link = stripe.AccountLink.create(account=acct_id,
                                     refresh_url=base_url + "/api/payments/connect/refresh",
                                     return_url=base_url + "/api/payments/connect/return",
                                     type="account_onboarding")
    return link.url


def send_onboarding_text(contractor):
    url = onboarding_link(contractor)
    _sms(contractor, "umuve: set up same-day payouts (about 2 minutes, add a debit card at the end): {} "
                     "— after that every job pays to your card the day it's done.".format(url))
    audit("payout_onboarding_sent", "contractor", contractor.id, {"has_account": bool(contractor.stripe_connect_id)})
    return url


# ---------------------------------------------------------------------------
# 4. balance guard
# ---------------------------------------------------------------------------
# A payout is only a real obligation when the customer's money actually
# landed and the job is live. Counting every Payment row whose payout_status
# is still the default "pending" swept in unconfirmed bookings and years-old
# placeholder rows, which made the balance guard cry wolf.
LIVE_JOB_STATUSES = ("confirmed", "accepted", "en_route", "arrived", "in_progress", "completed")
STALE_JOB_DAYS = 3


def expected_payouts(hours=36, stale_days=STALE_JOB_DAYS):
    """Hauler payouts genuinely coming due, with the rows that make them up.

    Counts a job only when the customer's payment succeeded, the job is in a
    live status, and it is scheduled inside [now - stale_days, now + hours].
    Anything older is abandoned or test data, not an obligation.
    """
    now = _now().replace(tzinfo=None)
    until = now + timedelta(hours=hours)
    since = now - timedelta(days=stale_days)
    q = (db.session.query(Payment, Job).join(Job, Job.id == Payment.job_id)
         .filter(Payment.payout_status == "pending",
                 Payment.payment_status == "succeeded",
                 Job.status.in_(LIVE_JOB_STATUSES),
                 Job.scheduled_at.isnot(None),
                 Job.scheduled_at >= since, Job.scheduled_at <= until))
    rows = []
    for payment, job in q.all():
        amount = round(payment.driver_payout_amount or 0.0, 2)
        if amount <= 0:
            continue
        rows.append({
            "job_id": job.id,
            "job_code": getattr(job, "confirmation_code", None) or job.id[:8],
            "amount": amount, "status": job.status,
            "scheduled_at": job.scheduled_at.isoformat() + "Z" if job.scheduled_at else None,
        })
    rows.sort(key=lambda r: r["scheduled_at"] or "")
    return {"total": round(sum(r["amount"] for r in rows), 2), "count": len(rows), "jobs": rows}


def balance_check():
    """→ {"state": ok|warn|fail, "reason", "available", "expected", "floor"} for desk_health."""
    if not os.environ.get("STRIPE_SECRET_KEY", ""):
        return {"state": "warn", "reason": "STRIPE_SECRET_KEY not set"}
    try:
        bal = _stripe().Balance.retrieve()
        available = round(next((b.amount for b in bal.available if b.currency == "usd"), 0) / 100.0, 2)
        # Card money sits in `pending` for ~2 business days before it can be
        # transferred. Reporting only `available` made a healthy account with
        # settling revenue look empty.
        pending = round(next((b.amount for b in getattr(bal, "pending", []) if b.currency == "usd"), 0) / 100.0, 2)
    except Exception as e:
        return {"state": "warn", "reason": "Stripe balance unavailable: " + type(e).__name__}
    due = expected_payouts()
    expected, jobs = due["total"], due["jobs"]
    floor = max(MIN_BALANCE, expected)
    soon = "${:.2f} available (+${:.2f} settling) vs ${:.2f} due across {} job{}".format(
        available, pending, expected, due["count"], "" if due["count"] == 1 else "s")
    if available < expected:
        state, reason = "fail", soon + " — transfers will fail until it settles"
    elif available < floor:
        state, reason = "warn", soon + ", below the ${:.0f} operating floor".format(floor)
    else:
        state, reason = "ok", soon
    return {"state": state, "reason": reason, "available": available, "pending": pending,
            "expected": expected, "floor": floor, "due_count": due["count"], "due_jobs": jobs[:10]}


# ---------------------------------------------------------------------------
# endpoints (manager)
# ---------------------------------------------------------------------------
@pay_bp.route("/api/va/pay/owed", methods=["POST"])
@require_desk(MANAGER_ROLES)
def pay_owed(ident):
    data = request.get_json(silent=True) or {}
    rep = owed_rows(days=int(data.get("days") or 30))
    last = DeskSetting.get("owed:last")
    rep["last_alert"] = json.loads(last) if last else None
    return jsonify(rep), 200


@pay_bp.route("/api/va/pay/mark-paid", methods=["POST"])
@require_desk(MANAGER_ROLES)
def pay_mark_paid(ident):
    data = request.get_json(silent=True) or {}
    payment = db.session.get(Payment, data.get("payment_id") or "")
    if not payment:
        return jsonify({"error": "Payment not found."}), 404
    if payment.payout_status not in UNPAID_STATUSES:
        return jsonify({"error": "That payout is '{}' — nothing to settle.".format(payment.payout_status)}), 409
    method = (data.get("method") or "zelle").strip().lower()[:20]
    if method not in ("zelle", "cash", "check", "venmo", "cashapp", "other"):
        return jsonify({"error": "Method must be zelle, cash, check, venmo, cashapp or other."}), 400
    amount = mark_paid(payment, method, (data.get("ref") or "").strip()[:80], ident.get("name"))
    return jsonify({"ok": True, "amount": amount, "owed": owed_rows()}), 200


@pay_bp.route("/api/va/pay/onboard-link", methods=["POST"])
@require_desk(MANAGER_ROLES)
def pay_onboard_link(ident):
    data = request.get_json(silent=True) or {}
    c = db.session.get(Contractor, data.get("contractor_id") or "")
    if not c:
        return jsonify({"error": "Hauler not found."}), 404
    try:
        url = send_onboarding_text(c) if data.get("send", True) else onboarding_link(c)
    except Exception as e:
        logger.exception("onboarding link failed for %s", c.id)
        return jsonify({"error": "Stripe couldn't create the link: " + type(e).__name__}), 502
    return jsonify({"ok": True, "url": url, "sent": bool(data.get("send", True))}), 200


@pay_bp.route("/api/va/pay/status", methods=["POST"])
@require_desk(MANAGER_ROLES)
def pay_status(ident):
    day_start, day_end = _local_day_bounds()
    rows = Payment.query.filter(Payment.updated_at >= day_start, Payment.updated_at < day_end).all()
    by = {"instant": 0, "standard": 0, "manual": 0}
    fees = 0.0
    for p in rows:
        m = (p.payout_method or "").lower()
        if m in by and p.payout_status in ("paid", "paid_manual"):
            by[m] += 1
            fees += p.payout_fee_cover or 0.0
    from flags import flag
    return jsonify({"today": by, "fee_cover_today": round(fees, 2), "auto_instant": flag("auto_instant_payout"),
                    "balance": balance_check()}), 200
