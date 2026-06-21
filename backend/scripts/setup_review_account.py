#!/usr/bin/env python3
"""
Set up the Apple App Review demo operator for Umuve Pro — idempotent.

Apple's reviewer logs into Umuve Pro with the credentials you put in App Store
Connect > App Review Information > Sign-In Information. That account must:
  1. exist with a KNOWN password (role='driver'),
  2. be approved (approval_status='approved'), and
  3. have a non-null stripe_connect_id — the app gates the dashboard behind
     StripeConnectOnboardingView until `contractorProfile.stripeConnectId != nil`
     (AppState.swift:29). A non-null value clears that wall; it does NOT require
     Stripe Connect to be fully enabled on your platform, so this works even
     while Connect onboarding isn't live yet.

This talks DIRECTLY to the production Postgres so it needs no admin token and
no Stripe Connect. Run it in YOUR terminal (DATABASE_URL is a secret):

    cd backend
    pip install sqlalchemy psycopg2-binary werkzeug   # if not already present
    DATABASE_URL='<paste from Render > umuve-db > Connections > External URL>' \
    DEMO_PASSWORD='ReviewDemo!2026' \
    python3 scripts/setup_review_account.py

It prints the final email + password to paste into ASC. Re-running is safe
(updates in place). To rotate the demo password later, just run it again with a
new DEMO_PASSWORD.
"""
import os
import sys
import uuid
import datetime

try:
    from sqlalchemy import create_engine, text
    from werkzeug.security import generate_password_hash
except ImportError as e:
    sys.exit(f"Missing dep: {e}. Run: pip install sqlalchemy psycopg2-binary werkzeug")

EMAIL = os.environ.get("DEMO_EMAIL", "applereview@goumuve.com").strip().lower()
PASSWORD = os.environ.get("DEMO_PASSWORD", "ReviewDemo!2026")
NAME = os.environ.get("DEMO_NAME", "Apple Review")
# Placeholder is fine: the app only checks non-null. Looks like a real acct id
# so nothing downstream chokes on the shape.
STRIPE_PLACEHOLDER = os.environ.get("DEMO_STRIPE_ID", "acct_review_demo_only")

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    sys.exit("Set DATABASE_URL (Render > umuve-db > Connections > External Database URL).")
# Render hands out postgres://; SQLAlchemy wants postgresql://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
pw_hash = generate_password_hash(PASSWORD)

# Render's external Postgres requires SSL; force it unless the URL already says so.
connect_args = {}
if "sslmode=" not in db_url:
    connect_args["sslmode"] = "require"
engine = create_engine(db_url, connect_args=connect_args, pool_pre_ping=True)
with engine.begin() as conn:
    # ---- users row ----
    row = conn.execute(text("SELECT id, role FROM users WHERE lower(email) = :e"),
                       {"e": EMAIL}).fetchone()
    if row:
        user_id = row[0]
        conn.execute(text("""
            UPDATE users
               SET password_hash = :ph, role = 'driver', status = 'active',
                   name = COALESCE(name, :n), updated_at = :now
             WHERE id = :id
        """), {"ph": pw_hash, "n": NAME, "now": now, "id": user_id})
        print(f"users: updated existing ({user_id})")
    else:
        user_id = str(uuid.uuid4())
        conn.execute(text("""
            INSERT INTO users (id, email, name, password_hash, role, status,
                               created_at, updated_at)
            VALUES (:id, :e, :n, :ph, 'driver', 'active', :now, :now)
        """), {"id": user_id, "e": EMAIL, "n": NAME, "ph": pw_hash, "now": now})
        print(f"users: created ({user_id})")

    # ---- contractors row ----
    crow = conn.execute(text("SELECT id, stripe_connect_id FROM contractors WHERE user_id = :u"),
                        {"u": user_id}).fetchone()
    if crow:
        cid = crow[0]
        existing_stripe = crow[1]
        conn.execute(text("""
            UPDATE contractors
               SET approval_status = 'approved',
                   onboarding_status = 'approved',
                   stripe_connect_id = COALESCE(stripe_connect_id, :sp),
                   updated_at = :now
             WHERE id = :id
        """), {"sp": STRIPE_PLACEHOLDER, "now": now, "id": cid})
        print(f"contractors: updated existing ({cid}); "
              f"stripe_connect_id={'kept ' + existing_stripe if existing_stripe else 'set ' + STRIPE_PLACEHOLDER}")
    else:
        cid = str(uuid.uuid4())
        conn.execute(text("""
            INSERT INTO contractors (id, user_id, approval_status, onboarding_status,
                                     stripe_connect_id, is_online, avg_rating,
                                     total_jobs, created_at, updated_at)
            VALUES (:id, :u, 'approved', 'approved', :sp, false, 4.9, 0, :now, :now)
        """), {"id": cid, "u": user_id, "sp": STRIPE_PLACEHOLDER, "now": now})
        print(f"contractors: created ({cid}); stripe_connect_id={STRIPE_PLACEHOLDER}")

print("\n" + "=" * 54)
print("  PASTE INTO App Store Connect > Sign-In Information")
print("=" * 54)
print(f"  Username (email): {EMAIL}")
print(f"  Password:         {PASSWORD}")
print("=" * 54)
print("Account is approved + clears the Stripe onboarding wall.")
print("Verify by logging into Umuve Pro with these, then tap Go Online.")
