#!/usr/bin/env python3
"""Promote a user to admin and print a 30-day API token.

Use it to open the pricing dashboard (and any /api/admin/* endpoint). This is
SERVER-SIDE only on purpose — there is no public route that hands out admin
access, so minting one requires reaching the database.

Run it where the PRODUCTION database is reachable:

  • Render shell (DATABASE_URL + JWT_SECRET already in the env):
        python scripts/mint_admin_token.py you@email.com

  • Locally against prod (supply the prod DB + same JWT secret):
        DATABASE_URL='<prod-url>' JWT_SECRET='<prod-secret>' \
            python scripts/mint_admin_token.py you@email.com

Flags:
  --create --password 'Pass123'   create the user first (then promote)
  --name 'Your Name'              name for a newly created user

Then paste the printed token into the "Admin token" box at
/api/admin/pricing-dashboard. JWT_SECRET must match the running backend or the
token won't validate.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func

from server import app
from models import db, User
from auth_routes import generate_token


def main():
    ap = argparse.ArgumentParser(description="Promote a user to admin + print a token.")
    ap.add_argument("email", help="user's email")
    ap.add_argument("--create", action="store_true", help="create the user if missing")
    ap.add_argument("--password", help="password to set (required with --create)")
    ap.add_argument("--name", help="name for a newly created user")
    args = ap.parse_args()

    email = args.email.strip().lower()

    with app.app_context():
        user = (
            db.session.query(User)
            .filter(func.lower(User.email) == email)
            .first()
        )

        created = False
        if user is None:
            if not args.create:
                print(
                    "No user with email {}.\n"
                    "Re-run with:  --create --password 'YourPass123'".format(email)
                )
                sys.exit(1)
            if not args.password:
                print("--create requires --password")
                sys.exit(1)
            user = User(
                email=email,
                name=args.name or email.split("@")[0],
                role="admin",
            )
            user.set_password(args.password)
            db.session.add(user)
            db.session.flush()
            created = True
        else:
            if args.password:
                user.set_password(args.password)

        previous_role = user.role
        user.role = "admin"
        db.session.commit()

        token = generate_token(user.id)

        bar = "=" * 64
        print("\n" + bar)
        if created:
            print("Created admin user: {}  (id={})".format(email, user.id))
        else:
            print("User: {}  (id={})".format(email, user.id))
            if previous_role != "admin":
                print("Role: {} -> admin".format(previous_role))
            else:
                print("Role: already admin")
        print(bar)
        print("\nAdmin token (valid 30 days) — paste into the dashboard:\n")
        print(token)
        print(
            "\nDashboard:\n"
            "  https://junkos-backend.onrender.com/api/admin/pricing-dashboard\n"
        )


if __name__ == "__main__":
    main()
