#!/usr/bin/env python3
"""One-shot runner for POST /api/admin/maintenance/scheduled-tz-backfill.

Usage:
  python3 scripts/tz_backfill.py --before 2026-09-04T04:17:47Z            # dry run
  python3 scripts/tz_backfill.py --before 2026-09-04T04:17:47Z --apply    # write

Admin login: reads UMUVE_ADMIN_EMAIL / UMUVE_ADMIN_PASSWORD from the env, or
falls back to ~/.config/umuve-admin-pass (one line: email:password). No
credentials are stored in this file or the repo.
"""
import argparse
import json
import os
import sys
import urllib.request

BASE = os.environ.get("UMUVE_API", "https://junkos-backend.onrender.com")


def _creds():
    email = os.environ.get("UMUVE_ADMIN_EMAIL")
    pw = os.environ.get("UMUVE_ADMIN_PASSWORD")
    if email and pw:
        return email, pw
    path = os.path.expanduser("~/.config/umuve-admin-pass")
    if os.path.exists(path):
        line = open(path).read().strip()
        if ":" in line:
            return line.split(":", 1)
    sys.exit("no admin creds: set UMUVE_ADMIN_EMAIL/UMUVE_ADMIN_PASSWORD or write ~/.config/umuve-admin-pass as email:password")


def _post(path, body, token=None):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json",
                 **({"Authorization": "Bearer " + token} if token else {})},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True, help="deploy timestamp, ISO UTC")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--include-past", action="store_true")
    a = ap.parse_args()

    email, pw = _creds()
    token = _post("/api/auth/login", {"email": email, "password": pw}).get("token")
    if not token:
        sys.exit("login failed")

    res = _post("/api/admin/maintenance/scheduled-tz-backfill",
                {"before": a.before, "apply": a.apply, "include_past": a.include_past}, token)
    print("applied={applied} before={before} count={count}".format(**res))
    for c in res["changes"]:
        print("  {kind:9} {id:<38} {was} -> {will}".format(
            kind=c["kind"], id=c.get("code") or c["id"],
            was=c.get("reads_as_florida_now", c["was_stored"]), will=c["will_read_as_florida"]))
    if not a.apply and res["count"]:
        print("\ndry run only. re-run with --apply to write.")


if __name__ == "__main__":
    main()
