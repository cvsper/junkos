"""
Revenue-pipe dry-run harness — exercises the assign-mode dispatch + payout
deferral logic against an in-memory SQLite database. NO network, NO Stripe,
NO Twilio, NO real charges.

What it proves (the "Nathan's first PBC job" path):
  1. A West Palm Beach booking PASSES has_active_coverage() once an
     approved contractor is seeded in range (and FAILS when none is).
  2. auto_assign_job() (DISPATCH_MODE=assign) assigns the paid job to the
     approved + online contractor and flips status pending -> assigned.
  3. The driver-side accept -> en_route -> arrived -> started -> completed
     transition table is valid end to end.
  4. attempt_payout() DEFERS (pending_connect) when the contractor has no
     Stripe Connect account, and PAYS (status=paid, no real Stripe call in
     dev mode) once a connect id is present.

Run:
    cd backend && python scripts/test_pipe_dryrun.py
Exit code 0 = all assertions passed; non-zero = a break in the pipe.

This is a diagnostic, not a production unit test. It imports the real
dispatcher / payments modules so any drift in their logic is caught here.
"""

from __future__ import annotations

import os
import sys

# --- Force a hermetic environment BEFORE importing app modules ---
os.environ["DISPATCH_MODE"] = "assign"      # the mode under test
os.environ.pop("STRIPE_SECRET_KEY", None)   # dev mode: no real transfers
os.environ.pop("TWILIO_ACCOUNT_SID", None)  # dev mode: SMS logs only
os.environ.pop("TWILIO_AUTH_TOKEN", None)

# Make the backend package importable whether run from repo root or backend/.
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
sys.path.insert(0, _BACKEND)

import importlib.util  # noqa: E402

from flask import Flask  # noqa: E402
from models import db, User, Contractor, Job, Payment, generate_uuid, utcnow  # noqa: E402


def _load_module_by_path(mod_name, rel_path):
    """Import a single backend module by file path WITHOUT triggering
    ``routes/__init__.py`` (which eagerly imports every blueprint and drags
    in heavy deps we don't need for a logic dry-run)."""
    path = os.path.join(_BACKEND, rel_path)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod

# West Palm Beach city center — where Nathan is seeded.
WPB = (26.7153, -80.0534)
# A nearby customer booking (Lake Worth, ~10 mi south) — inside the polygon.
CUSTOMER = (26.6160, -80.0570)
# Far-away point (NYC) used to prove the coverage gate can also say "no".
NYC = (40.7580, -73.9855)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

_results = []


def check(label, cond, detail=""):
    _results.append((label, bool(cond), detail))
    print("  [{}] {}{}".format(PASS if cond else FAIL, label,
                               " — " + detail if detail else ""))
    return bool(cond)


def make_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    return app


def seed_nathan(online=True, approved=True, connect=False):
    """Seed an approved, online, independent PBC hauler ('Nathan')."""
    user = User(id=generate_uuid(), email="nathan@example.test",
                name="Nathan", phone="+15615550123", role="driver")
    db.session.add(user)
    db.session.flush()
    c = Contractor(
        id=generate_uuid(),
        user_id=user.id,
        truck_type="Pickup",
        truck_capacity=None,                # unknown -> capacity score neutral
        is_online=online,
        approval_status="approved" if approved else "pending",
        current_lat=WPB[0],
        current_lng=WPB[1],
        avg_rating=0.0,
        total_jobs=0,
        is_operator=False,
        operator_id=None,
        stripe_connect_id=("acct_dev_nathan" if connect else None),
    )
    db.session.add(c)
    db.session.flush()
    return c


def make_paid_job(lat, lng, total=99.0):
    uniq = generate_uuid()[:8]
    cust = User(id=generate_uuid(), email="cust+{}@example.test".format(uniq),
                name="Customer", phone="+1561555{}".format(uniq[:4].translate(
                    str.maketrans("abcdef", "012345"))),
                role="customer")
    db.session.add(cust)
    db.session.flush()
    job = Job(
        id=generate_uuid(),
        customer_id=cust.id,
        status="confirmed",          # payment already succeeded
        address="123 Test St, Lake Worth, FL 33460",
        lat=lat, lng=lng,
        items=[{"category": "sofa", "quantity": 1}],
        total_price=total,
        volume_estimate=None,
    )
    db.session.add(job)
    db.session.flush()
    payment = Payment(
        id=generate_uuid(),
        job_id=job.id,
        amount=total,
        payment_status="succeeded",
        driver_payout_amount=round(total * 0.80, 2),
        payout_status=None,
    )
    db.session.add(payment)
    db.session.commit()
    return job


def main():
    app = make_app()
    with app.app_context():
        db.create_all()

        import dispatcher
        # Load payments + drivers directly by path so we don't import the whole
        # routes package (auth/jwt/celery/etc). auth_routes is a dependency of
        # payments.py, so register it under its real name first.
        _load_module_by_path("auth_routes", "auth_routes.py")
        _payments = _load_module_by_path("routes.payments", "routes/payments.py")
        _drivers = _load_module_by_path("routes.drivers", "routes/drivers.py")
        attempt_payout = _payments.attempt_payout
        VALID_STATUS_TRANSITIONS = _drivers.VALID_STATUS_TRANSITIONS

        print("\n=== 1. Coverage gate (pre-payment) ===")
        # No contractor yet -> WPB area should NOT be covered.
        check("WPB uncovered when no hauler seeded",
              dispatcher.has_active_coverage(*CUSTOMER) is False)

        nathan = seed_nathan(online=True, approved=True, connect=False)
        check("WPB COVERED once Nathan (approved) is in range",
              dispatcher.has_active_coverage(*CUSTOMER) is True,
              "Nathan @ WPB, customer ~10mi away")
        check("NYC still uncovered (gate can say no)",
              dispatcher.has_active_coverage(*NYC) is False)

        print("\n=== 2. Assign-mode dispatch ===")
        check("DISPATCH_MODE is 'assign'", dispatcher.DISPATCH_MODE == "assign",
              dispatcher.DISPATCH_MODE)
        job = make_paid_job(*CUSTOMER)

        cands = dispatcher.find_best_operator(job)
        check("find_best_operator returns Nathan",
              len(cands) == 1 and cands[0]["contractor"].id == nathan.id,
              "{} candidate(s)".format(len(cands)))

        # Run the real auto_assign (context already active, app=None).
        dispatcher.auto_assign_job(job.id, app=None)
        db.session.refresh(job)
        check("Job assigned to Nathan", job.driver_id == nathan.id)
        check("Job status -> 'assigned'", job.status == "assigned", job.status)

        # Offline hauler must NOT be eligible.
        nathan.is_online = False
        db.session.commit()
        job2 = make_paid_job(*CUSTOMER)
        dispatcher.auto_assign_job(job2.id, app=None)
        db.session.refresh(job2)
        check("Offline hauler NOT auto-assigned (stays unassigned)",
              job2.driver_id is None and job2.status == "confirmed",
              job2.status)
        nathan.is_online = True
        db.session.commit()

        print("\n=== 3. Driver lifecycle transitions ===")
        # Validate the transition table from assigned -> completed.
        chain = ["assigned", "accepted", "en_route", "arrived", "started", "completed"]
        ok = True
        for frm, to in zip(chain, chain[1:]):
            allowed = to in VALID_STATUS_TRANSITIONS.get(frm, [])
            ok = ok and allowed
            if not allowed:
                check("transition {} -> {}".format(frm, to), False)
        check("Full assigned->completed transition chain is valid", ok)

        # Persist the chain on the real job (mimic update_job_status writes).
        job.status = "completed"
        job.completed_at = utcnow()
        db.session.commit()
        db.session.refresh(job)
        check("Completion persists (status + completed_at)",
              job.status == "completed" and job.completed_at is not None)

        print("\n=== 4. Payout (deferral + dev-mode pay) ===")
        # Nathan has NO Stripe Connect yet -> must defer, not fail.
        res = attempt_payout(job.id)
        db.session.refresh(job.payment)
        check("Payout DEFERS to pending_connect (no Stripe account)",
              res["status"] == "no_connect"
              and job.payment.payout_status == "pending_connect",
              "status={} payout_status={}".format(res["status"], job.payment.payout_status))

        # Nathan finishes onboarding -> sweep retries -> paid (dev mode, no real call).
        nathan.stripe_connect_id = "acct_dev_nathan"
        db.session.commit()
        res2 = attempt_payout(job.id)
        db.session.refresh(job.payment)
        check("Payout PAYS once connected (dev-mode, no real transfer)",
              res2["status"] == "paid" and job.payment.payout_status == "paid",
              "status={} amount=${}".format(res2["status"], res2["amount"]))
        check("Payout is idempotent (second call = already_paid)",
              attempt_payout(job.id)["status"] == "already_paid")

    # --- Summary ---
    passed = sum(1 for _, ok, _ in _results if ok)
    total = len(_results)
    print("\n" + "=" * 56)
    print("PIPE DRY-RUN: {}/{} checks passed".format(passed, total))
    print("=" * 56)
    if passed != total:
        print("BREAK(S) DETECTED:")
        for label, ok, detail in _results:
            if not ok:
                print("  - {} {}".format(label, "(" + detail + ")" if detail else ""))
        sys.exit(1)
    print("All assignment + payout logic is sound for the assign-mode pipe.")
    sys.exit(0)


if __name__ == "__main__":
    main()
