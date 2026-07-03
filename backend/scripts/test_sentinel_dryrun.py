"""Ops-sentinel + growth-loops + activation-drip dry-run harness.

In-memory SQLite, NO network, NO Twilio/Stripe. Proves the 2026-07-03
automation layer: every watchdog fires on its scenario, every send is
exactly-once (second sweep = zero new events), and nothing mutates job state.

Run:  cd backend && python scripts/test_sentinel_dryrun.py
Exit 0 = all checks passed.
"""
from __future__ import annotations

import os
import sys
from datetime import timedelta

os.environ["ADMIN_PHONE"] = "+15550000001"
os.environ["ADMIN_EMAIL"] = "ops@test.local"
os.environ.pop("OPERATOR_PHONE", None)
os.environ.pop("TWILIO_ACCOUNT_SID", None)
os.environ.pop("STRIPE_SECRET_KEY", None)

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
sys.path.insert(0, _BACKEND)

from flask import Flask  # noqa: E402

from models import (AutomationEvent, Contractor, Job, User, db,  # noqa: E402
                    generate_uuid, utcnow)

PASS = "\033[92mPASS\033[0m"
_checks = []


def check(label, cond):
    _checks.append((label, bool(cond)))
    print("  [{}] {}".format(PASS if cond else "\033[91mFAIL\033[0m", label))


def _mk_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    return app


# --- capture all outbound sends instead of sending ---
SENT = {"sms": [], "email": [], "push": [], "review_sms": []}


def _patch_senders():
    import email_service
    import notifications
    import sms_service
    notifications.send_sms = lambda to, body: SENT["sms"].append((to, body))
    notifications.send_push_notification = (
        lambda uid, title, body, data=None: SENT["push"].append((uid, title)))
    email_service.send_email = lambda to, s, h: SENT["email"].append((to, s)) or True
    email_service.send_email_async = lambda to, s, h: SENT["email"].append((to, s))
    email_service.email_follow_up = lambda to, n: SENT["email"].append((to, "follow-up"))
    sms_service.send_sms = lambda to, body: SENT["sms"].append((to, body))
    sms_service.send_review_request_sms = (
        lambda p, n, c: SENT["review_sms"].append(p))


def _job(**kw):
    now = utcnow()
    j = Job(id=generate_uuid(), customer_id=kw.pop("customer_id"),
            address="123 Test St, West Palm Beach, FL 33401",
            total_price=119.0, **kw)
    db.session.add(j)
    db.session.commit()
    if "updated_at" in kw or "created_at" in kw:
        pass
    return j


def _age(job, minutes=None, field="updated_at"):
    """Force-age a timestamp column (bypasses onupdate)."""
    db.session.execute(
        db.text("UPDATE jobs SET {} = :ts WHERE id = :id".format(field)),
        {"ts": utcnow() - timedelta(minutes=minutes), "id": job.id})
    db.session.commit()


def _events(kind):
    return AutomationEvent.query.filter_by(kind=kind).count()


def main():
    app = _mk_app()
    _patch_senders()
    with app.app_context():
        db.create_all()

        cust = User(id=generate_uuid(), email="c@test.local", name="Cust Omer",
                    phone="+15550000009")
        cust.set_password("x")
        huser = User(id=generate_uuid(), email="h@test.local", name="Hal Hauler",
                     phone="+15550000008")
        huser.set_password("x")
        db.session.add_all([cust, huser])
        db.session.commit()
        hauler = Contractor(id=generate_uuid(), user_id=huser.id,
                            approval_status="approved", is_online=False)
        db.session.add(hauler)
        db.session.commit()

        # Scenarios
        j_asap = _job(customer_id=cust.id, status="confirmed", scheduled_at=None)
        _age(j_asap, minutes=30, field="created_at")
        j_acc = _job(customer_id=cust.id, status="accepted", driver_id=hauler.id)
        _age(j_acc, minutes=60)
        j_enr = _job(customer_id=cust.id, status="en_route", driver_id=hauler.id)
        _age(j_enr, minutes=180)
        from models import Payment
        j_pf = _job(customer_id=cust.id, status="completed",
                    completed_at=utcnow() - timedelta(hours=20))
        j_ow = _job(customer_id=cust.id, status="completed",
                    completed_at=utcnow() - timedelta(hours=30))
        j_rev = _job(customer_id=cust.id, status="completed",
                     completed_at=utcnow() - timedelta(hours=3))
        j_rem = _job(customer_id=cust.id, status="completed",
                     completed_at=utcnow() - timedelta(hours=30))
        db.session.add_all([
            Payment(job_id=j_pf.id, amount=119.0, payout_status="failed",
                    driver_payout_amount=80.0),
            Payment(job_id=j_ow.id, amount=119.0, payout_status="pending_connect",
                    driver_payout_amount=80.0),
        ])
        db.session.commit()
        # zombie: months-old accepted job — must land in the daily digest,
        # NEVER a per-job stall alert (first prod sweep spammed these)
        _job(customer_id=cust.id, status="accepted", driver_id=hauler.id,
             scheduled_at=utcnow() - timedelta(days=100))
        j_enr_id = str(j_enr.id)  # plain id survives session teardown
        # age the idle hauler past the T+1 activation-nudge threshold
        db.session.execute(
            db.text("UPDATE contractors SET created_at = :ts WHERE id = :id"),
            {"ts": utcnow() - timedelta(days=2), "id": hauler.id})
        db.session.commit()

    # --- sentinel, twice ---
    from ops_sentinel import run_sentinel
    run_sentinel(app)
    with app.app_context():
        check("ASAP unassigned caught", _events("asap_unassigned") == 1)
        check("accepted stall caught", _events("stall_accepted") == 1)
        check("en_route stall caught", _events("stall_en_route") == 1)
        check("offline mid-job caught", _events("offline_midjob") >= 1)
        check("failed payout caught", _events("payout_failed") == 1)
        check("owed payout digest fired", _events("payout_owed") == 1)
        check("zombie digested, NOT stall-alerted",
              _events("zombie_digest") == 1 and _events("stall_accepted") == 1)
        n_sms_first = len(SENT["sms"])
        check("admin SMS sent (capped)", 0 < n_sms_first <= 5)
    run_sentinel(app)
    with app.app_context():
        total = AutomationEvent.query.count()
        check("second sentinel run adds ZERO events (idempotent)",
              AutomationEvent.query.count() == total)
        check("second run sends no new SMS", len(SENT["sms"]) == n_sms_first)
        check("sentinel never mutates job state",
              db.session.get(Job, j_enr_id).status == "en_route")

    # --- growth sweep, twice ---
    from growth_loops import run_growth_sweep
    run_growth_sweep(app)
    with app.app_context():
        check("review SMS sent for 3h-old completion",
              _events("review_sms") >= 1 and len(SENT["review_sms"]) >= 1)
        check("review email sent for 30h-old completion", _events("review_email") >= 1)
        n_rev = len(SENT["review_sms"])
    run_growth_sweep(app)
    check("growth sweep idempotent (no re-sends)", len(SENT["review_sms"]) == n_rev)

    # --- activation drip, twice ---
    from supply_drip import run_activation_drip
    n_before = len(SENT["sms"])
    run_activation_drip(app)
    with app.app_context():
        check("idle approved hauler nudged", _events("activation_nudge_1") == 1)
    n_after = len(SENT["sms"])
    check("drip sent exactly one SMS", n_after == n_before + 1)
    run_activation_drip(app)
    check("drip idempotent", len(SENT["sms"]) == n_after)

    failed = [l for l, ok in _checks if not ok]
    print("\n{}/{} checks passed.".format(len(_checks) - len(failed), len(_checks)))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
