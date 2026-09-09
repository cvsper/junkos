#!/usr/bin/env python3
"""
WPB launch readiness check — is an operator ONLINE and in range so a West Palm
Beach booking will actually dispatch?

Mirrors dispatcher.find_best_operator's gate (approved + is_online + <=30mi) and
has_active_coverage (approved + <=30mi, regardless of online) against PROD via the
admin API. No secrets committed — pass admin creds at runtime.

Usage:
    python3 scripts/check_wpb_coverage.py --email you@admin --password 'xxx'
    # or env: ADMIN_LOGIN_EMAIL / ADMIN_LOGIN_PASSWORD
    # options: --base <url>  --lat 26.7153 --lng -80.0534 --radius 30

Exit 0 = at least one approved operator ONLINE within radius (booking will dispatch).
Exit 1 = covered but nobody online (booking would fall to admin fallback).
Exit 2 = no approved coverage in range / error.
"""
import argparse, json, math, os, ssl, sys, urllib.request, urllib.error

WPB_LAT, WPB_LNG = 26.7153, -80.0534
# Verify TLS against a real CA bundle. macOS' system python often can't find one
# (→ CERTIFICATE_VERIFY_FAILED), so prefer certifi when available.
try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    CTX = ssl.create_default_context()


def haversine(lat1, lng1, lat2, lng2):
    R = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def call(base, path, token=None, body=None):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, headers=h,
                                 method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
            return r.status, json.loads(r.read() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:200]}
    except Exception as e:
        return 0, {"error": str(e)[:200]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("UMUVE_API", "https://junkos-backend.onrender.com"))
    ap.add_argument("--email", default=os.environ.get("ADMIN_LOGIN_EMAIL"))
    ap.add_argument("--password", default=os.environ.get("ADMIN_LOGIN_PASSWORD"))
    ap.add_argument("--token", default=os.environ.get("ADMIN_TOKEN"))
    ap.add_argument("--lat", type=float, default=WPB_LAT)
    ap.add_argument("--lng", type=float, default=WPB_LNG)
    ap.add_argument("--radius", type=float, default=30.0)
    a = ap.parse_args()
    base = a.base.rstrip("/")

    token = a.token
    if not token:
        if not (a.email and a.password):
            print("Need --email/--password (or --token, or env). See --help."); return 2
        s, r = call(base, "/api/auth/login", body={"email": a.email, "password": a.password, "role": "admin"})
        token = r.get("token") or r.get("access_token") or (r.get("data") or {}).get("token")
        if s != 200 or not token:
            print(f"Login failed (HTTP {s}): {r}"); return 2

    s, r = call(base, "/api/admin/contractors?status=approved&per_page=200", token=token)
    if s != 200:
        print(f"contractors fetch failed (HTTP {s}): {r}"); return 2
    rows = r.get("contractors") or r.get("data") or []

    print(f"\nWPB readiness @ ({a.lat:.4f}, {a.lng:.4f})  radius {a.radius:.0f}mi")
    print("-" * 64)
    covered = online_in_range = 0
    for c in rows:
        lat, lng = c.get("current_lat"), c.get("current_lng")
        name = c.get("name") or c.get("id", "?")
        online = bool(c.get("is_online"))
        if lat is None or lng is None:
            print(f"  {name:24} no location"); continue
        d = haversine(a.lat, a.lng, float(lat), float(lng))
        inr = d <= a.radius
        if inr:
            covered += 1
            if online:
                online_in_range += 1
        print(f"  {name:24} {'ONLINE ' if online else 'offline'}  {d:5.1f}mi  {'IN RANGE' if inr else 'out'}")
    print("-" * 64)
    print(f"approved + in range (coverage): {covered}")
    print(f"ONLINE + in range (dispatchable now): {online_in_range}")
    if online_in_range >= 1:
        print("\n✅ GO — a WPB booking will dispatch to an online operator."); return 0
    if covered >= 1:
        print("\n⚠️  Covered, but nobody is online — a booking routes to the admin fallback. Get an operator to Go Online."); return 1
    print("\n❌ No approved coverage in range — onboard/approve an operator near WPB."); return 2


if __name__ == "__main__":
    sys.exit(main())
