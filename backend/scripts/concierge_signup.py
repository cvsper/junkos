#!/usr/bin/env python3
"""
Register interested haulers as concierge operators (no app needed).

Each hauler becomes an approved, online Contractor reachable by the SMS
offer wave; they run jobs from the token-gated /w/ console and get paid by
hand via the concierge ledger. Registering the first one in range also
opens the WPB coverage gate.

Usage:
    # one or more "Name,phone" pairs:
    python3 scripts/concierge_signup.py --email you@admin --password 'xxx' \
        "Joshua Daniel,(561) 316-8668" "Ryan,(561) 913-2023"

    # or from a CSV with name,phone columns (extra columns ignored):
    python3 scripts/concierge_signup.py --email ... --password ... --csv ops.csv

    # env: ADMIN_LOGIN_EMAIL / ADMIN_LOGIN_PASSWORD (or --token)
Safe to re-run: an already-registered phone gets a 409 and is skipped.
"""
import argparse, csv, json, os, ssl, sys, urllib.request, urllib.error

try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    CTX = ssl.create_default_context()

BASE = os.environ.get("UMUVE_API", "https://junkos-backend.onrender.com")


def call(path, token=None, body=None, method=None):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = "Bearer {}".format(token)
    data = json.dumps(body).encode() if body is not None else None
    m = method or ("POST" if data is not None else "GET")
    req = urllib.request.Request(BASE + path, data=data, headers=h, method=m)
    try:
        with urllib.request.urlopen(req, timeout=45, context=CTX) as r:
            return r.status, json.loads(r.read() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or "{}")
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)[:200]}


def login(email, password):
    s, r = call("/api/auth/login", body={"email": email, "password": password})
    tok = r.get("token") or r.get("access_token") or (r.get("data") or {}).get("token")
    return tok if s == 200 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pairs", nargs="*", help='"Name,phone" entries')
    ap.add_argument("--csv", help="CSV file with name,phone columns")
    ap.add_argument("--email", default=os.environ.get("ADMIN_LOGIN_EMAIL"))
    ap.add_argument("--password", default=os.environ.get("ADMIN_LOGIN_PASSWORD"))
    ap.add_argument("--token", default=os.environ.get("ADMIN_TOKEN"))
    args = ap.parse_args()

    ops = []
    for p in args.pairs:
        name, _, phone = p.partition(",")
        if name.strip() and phone.strip():
            ops.append({"name": name.strip(), "phone": phone.strip()})
    if args.csv:
        with open(args.csv, newline="") as f:
            for row in csv.DictReader(f):
                name = (row.get("name") or row.get("contact") or "").strip()
                phone = (row.get("phone") or "").strip()
                if name and phone:
                    ops.append({"name": name, "phone": phone})
    if not ops:
        sys.exit("No haulers given. Pass \"Name,phone\" pairs or --csv.")

    token = args.token
    if not token:
        if not (args.email and args.password):
            sys.exit("Need --token or --email/--password (or env ADMIN_LOGIN_*).")
        token = login(args.email, args.password)
        if not token:
            sys.exit("Admin login failed.")

    ok = 0
    for op in ops:
        s, r = call("/api/admin/concierge/operators", token=token, body=op)
        if s == 201:
            ok += 1
            print("  [OK]   {} ({}) — id {}".format(
                op["name"], op["phone"],
                (r.get("contractor") or {}).get("id", "?")[:8]))
        elif s == 409:
            print("  [SKIP] {} ({}) — {}".format(
                op["name"], op["phone"], r.get("error", "already exists")))
        else:
            print("  [FAIL] {} ({}) — HTTP {} {}".format(
                op["name"], op["phone"], s, r.get("error", "")))

    print("\n{}/{} registered. Each got a welcome text; they'll receive job "
          "offers by SMS.".format(ok, len(ops)))
    s, r = call("/api/admin/concierge/operators", token=token)
    if s == 200:
        print("Concierge roster now: {} operator(s).".format(r.get("count")))


if __name__ == "__main__":
    main()
