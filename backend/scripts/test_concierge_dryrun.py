"""
Concierge-pipe dry-run harness — exercises the shadow-operator path against
an in-memory SQLite database. NO network, NO Stripe, NO Twilio.

What it proves (the "no app operator online, but Marco has a truck" path):
  1. find_best_operator NEVER auto-assigns a concierge hauler (they can't
     act on a silent app assign).
  2. With DISPATCH_MODE=assign and zero app operators, auto_assign_job falls
     back to the broadcast offer wave: a JobOffer reaches the concierge
     hauler and the job goes to 'broadcasting' — never silently dropped.
  3. accept_offer(token) claims the job for the concierge hauler.
  4. The /w/<token> console renders, and its advance path walks
     accepted -> en_route -> arrived -> started -> completed through the
     SHARED transition engine (drivers.apply_job_status_transition).
  5. Completion auto-payout DEFERS to pending_connect (no Stripe account),
     the admin ledger owes the hauler, and mark-paid flips the payout to
     paid_manual.

Run:
    cd backend && python scripts/test_concierge_dryrun.py
Exit code 0 = all assertions passed; non-zero = a break in the pipe.

This is a diagnostic, not a production unit test. It imports the real
dispatcher / payments / drivers / concierge modules so any drift in their
logic is caught here.
"""

from __future__ import annotations

import os
import sys
import types

# --- Force a hermetic environment BEFORE importing app modules ---
os.environ["DISPATCH_MODE"] = "assign"      # assign mode w/ concierge fallback
os.environ["JWT_SECRET"] = "dryrun-secret"  # for admin-endpoint tokens
os.environ.pop("STRIPE_SECRET_KEY", None)   # dev mode: no real transfers
os.environ.pop("TWILIO_ACCOUNT_SID", None)  # dev mode: SMS logs only
os.environ.pop("TWILIO_AUTH_TOKEN", None)

# Make the backend package importable whether run from repo root or backend/.
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
sys.path.insert(0, _BACKEND)

import importlib.util  # noqa: E402

from flask import Flask  # noqa: E402
from models import (  # noqa: E402
    db, Contractor, Job, JobOffer, Payment, User, generate_uuid, utcnow,
)


def _load_module_by_path(mod_name, rel_path):
    """Import a single backend module by file path WITHOUT triggering
    ``routes/__init__.py`` (which eagerly imports every blueprint)."""
    path = os.path.join(_BACKEND, rel_path)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Stub the ``routes`` package so lazy `from routes.X import ...` inside the
# modules under test resolves to our path-loaded copies, not the eager
# __init__.py.
_routes_pkg = types.ModuleType("routes")
_routes_pkg.__path__ = []  # mark as package
sys.modules["routes"] = _routes_pkg

# West Palm Beach city center — where Marco (concierge) is seeded.
WPB = (26.7153, -80.0534)
# A nearby customer booking (Lake Worth, ~10 mi south).
CUSTOMER = (26.6160, -80.0570)

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
    # Mirror server.py: the shared transition engine emits socket events, and
    # an uninitialized SocketIO() crashes on .emit (server is None).
    import socket_events
    socket_events.socketio.init_app(app, async_mode="threading")
    return app


def seed_marco():
    """Seed a concierge (phone-only) hauler: approved, online, NO Stripe."""
    user = User(id=generate_uuid(), email="marco@example.test",
                name="Marco Hauls", phone="+15615550199", role="driver")
    db.session.add(user)
    db.session.flush()
    c = Contractor(
        id=generate_uuid(),
        user_id=user.id,
        truck_type="pickup",
        truck_capacity=None,
        is_online=True,
        approval_status="approved",
        current_lat=WPB[0],
        current_lng=WPB[1],
        is_operator=False,
        is_concierge=True,
        stripe_connect_id=None,
    )
    db.session.add(c)
    db.session.commit()
    return c


def make_paid_job(lat, lng, total=129.0):
    uniq = generate_uuid()[:8]
    cust = User(id=generate_uuid(), email="cust+{}@example.test".format(uniq),
                name="Customer Jane", phone="+1561444{}".format(
                    uniq[:4].translate(str.maketrans("abcdef", "012345"))),
                role="customer")
    db.session.add(cust)
    db.session.flush()
    job = Job(
        id=generate_uuid(),
        customer_id=cust.id,
        status="confirmed",
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
        driver_payout_amount=round(total * 0.72, 2),
        payout_status=None,
    )
    db.session.add(payment)
    db.session.commit()
    return job


def main():
    app = make_app()

    import dispatcher  # noqa: E402  (module-level, no routes dependency)
    _load_module_by_path("auth_routes", "auth_routes.py")
    _payments = _load_module_by_path("routes.payments", "routes/payments.py")
    _drivers = _load_module_by_path("routes.drivers", "routes/drivers.py")
    _concierge = _load_module_by_path("routes.concierge", "routes/concierge.py")
    _routes_pkg.payments = _payments
    _routes_pkg.drivers = _drivers
    _routes_pkg.concierge = _concierge

    app.register_blueprint(_concierge.concierge_bp)
    client = app.test_client()

    with app.app_context():
        db.create_all()

        print("\n=== 1. Concierge is invisible to app auto-assign ===")
        marco = seed_marco()
        job = make_paid_job(*CUSTOMER)
        cands = dispatcher.find_best_operator(job)
        check("find_best_operator skips the concierge hauler",
              len(cands) == 0, "{} candidate(s)".format(len(cands)))

        print("\n=== 2. Assign-mode fallback offer wave ===")
        dispatcher.auto_assign_job(job.id, app=None)
        db.session.refresh(job)
        offer = JobOffer.query.filter_by(
            job_id=job.id, contractor_id=marco.id).first()
        check("Fallback wave created a JobOffer for the concierge hauler",
              offer is not None and offer.status == "sent")
        check("Job -> 'broadcasting' (not dropped, not auto-assigned)",
              job.status == "broadcasting" and job.driver_id is None,
              job.status)

        print("\n=== 3. First-to-accept claim ===")
        res = dispatcher.accept_offer(offer.accept_token)
        db.session.refresh(job)
        check("accept_offer claims the job for Marco",
              res["ok"] and job.driver_id == marco.id, res["status"])
        check("Job status -> 'assigned'", job.status == "assigned", job.status)

        print("\n=== 4. Console renders + shared-engine advance ===")
        page = client.get("/w/{}".format(offer.accept_token))
        check("GET /w/<token> renders (200)", page.status_code == 200)
        body = page.get_data(as_text=True)
        check("Console shows payout + confirm action",
              "take-home" in body and "Confirm job" in body)

        bad = client.get("/w/{}".format(generate_uuid()))
        check("Bogus token is rejected (404)", bad.status_code == 404)

        chain = ["accepted", "en_route", "arrived", "started", "completed"]
        walked = True
        for target in chain:
            r = client.post("/w/{}/advance".format(offer.accept_token),
                            data={"to": target})
            db.session.refresh(job)
            step_ok = r.status_code == 302 and job.status == target
            walked = walked and step_ok
            if not step_ok:
                check("advance -> {}".format(target), False,
                      "http={} status={}".format(r.status_code, job.status))
        check("Full accepted->completed walk via shared engine", walked,
              job.status)
        check("completed_at stamped + total_jobs incremented",
              job.completed_at is not None
              and (db.session.get(Contractor, marco.id).total_jobs or 0) == 1)

        # Stale double-submit: advancing a completed job must be a no-op.
        r = client.post("/w/{}/advance".format(offer.accept_token),
                        data={"to": "completed"})
        db.session.refresh(job)
        check("Double-submit after completion is a safe no-op",
              r.status_code == 302 and job.status == "completed")

        print("\n=== 5. Payout deferral + manual ledger ===")
        payment = job.payment
        db.session.refresh(payment)
        check("Auto-payout DEFERRED to pending_connect (no Stripe)",
              payment.payout_status == "pending_connect",
              payment.payout_status)

        # Admin token for the ledger endpoints.
        import auth_routes as _auth
        admin = User(id=generate_uuid(), email="admin@example.test",
                     name="Admin", role="admin")
        admin.set_password("x")
        db.session.add(admin)
        db.session.commit()
        headers = {"Authorization": "Bearer {}".format(
            _auth.generate_token(admin.id))}

        led = client.get("/api/admin/concierge/ledger", headers=headers)
        data = led.get_json() or {}
        owed = data.get("owed_total", 0)
        check("Ledger owes Marco his payout",
              led.status_code == 200
              and abs(owed - (payment.driver_payout_amount or 0)) < 0.01,
              "owed_total={}".format(owed))

        mp = client.post(
            "/api/admin/concierge/payments/{}/mark-paid".format(payment.id),
            headers=headers, json={"method": "zelle", "note": "dry-run"})
        db.session.refresh(payment)
        check("mark-paid flips payout to paid_manual",
              mp.status_code == 200 and payment.payout_status == "paid_manual",
              payment.payout_status)

        mp2 = client.post(
            "/api/admin/concierge/payments/{}/mark-paid".format(payment.id),
            headers=headers, json={"method": "zelle"})
        check("mark-paid is NOT double-applicable (409)",
              mp2.status_code == 409)

        led2 = client.get("/api/admin/concierge/ledger", headers=headers)
        check("Ledger owed drops to 0 after settlement",
              (led2.get_json() or {}).get("owed_total") == 0)

        noauth = client.get("/api/admin/concierge/ledger")
        check("Ledger requires admin auth", noauth.status_code in (401, 403))

    failures = [r for r in _results if not r[1]]
    print("\n{}/{} checks passed.".format(
        len(_results) - len(failures), len(_results)))
    if failures:
        print("FAILURES:")
        for label, _, detail in failures:
            print("  - {}{}".format(label, " — " + detail if detail else ""))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
