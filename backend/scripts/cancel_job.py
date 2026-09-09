#!/usr/bin/env python3
"""
Cancel a test job after you've confirmed it dispatched + the operator could
accept it — so nobody actually drives a fake job.

Usage:
    python3 scripts/cancel_job.py --job <JOB_ID> --email you@admin --password 'xxx'
    # or env: ADMIN_LOGIN_EMAIL / ADMIN_LOGIN_PASSWORD (or --token)

Note: this sets the job to "cancelled" (and broadcasts it). It does NOT issue a
Stripe refund — if you charged a real card, refund it in the Stripe dashboard,
or use the PBC25 promo to make the test booking free in the first place.
"""
import argparse, json, os, ssl, sys, urllib.request, urllib.error
try:
    import certifi; CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    CTX = ssl.create_default_context()


def call(base, path, token=None, body=None, method=None):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    m = method or ("POST" if data is not None else "GET")
    req = urllib.request.Request(base + path, data=data, headers=h, method=m)
    try:
        with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
            return r.status, json.loads(r.read() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:200]}
    except Exception as e:
        return 0, {"error": str(e)[:200]}


def login(base, email, password):
    s, r = call(base, "/api/auth/login", body={"email": email, "password": password, "role": "admin"})
    tok = r.get("token") or r.get("access_token") or (r.get("data") or {}).get("token")
    return tok if s == 200 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("UMUVE_API", "https://junkos-backend.onrender.com"))
    ap.add_argument("--job", help="internal job id")
    ap.add_argument("--code", help="confirmation code (e.g. OZJT9S5S) — resolved via /api/admin/jobs search")
    ap.add_argument("--email", default=os.environ.get("ADMIN_LOGIN_EMAIL"))
    ap.add_argument("--password", default=os.environ.get("ADMIN_LOGIN_PASSWORD"))
    ap.add_argument("--token", default=os.environ.get("ADMIN_TOKEN"))
    a = ap.parse_args()
    base = a.base.rstrip("/")
    token = a.token or (login(base, a.email, a.password) if (a.email and a.password) else None)
    if not token:
        print("Auth failed — need --email/--password or --token."); return 2
    job_id = a.job
    if not job_id and a.code:
        s, r = call(base, f"/api/admin/jobs?search={a.code}", token=token)
        rows = r.get("jobs") or r.get("data") or []
        match = [j for j in rows if (j.get("confirmation_code") or "").upper() == a.code.upper()]
        if len(match) != 1:
            print(f"❌ Code {a.code} matched {len(match)} jobs (search returned {len(rows)}) — aborting.")
            return 2
        job_id = match[0]["id"]
        print(f"Resolved {a.code} → job {job_id} (status={match[0].get('status')}, "
              f"${match[0].get('total_price')}, {match[0].get('address', '')[:40]})")
    if not job_id:
        print("Need --job or --code."); return 2
    s, r = call(base, f"/api/admin/jobs/{job_id}/cancel", token=token, method="PUT")
    if s == 200:
        job = r.get("job", {})
        print(f"✅ Job {job_id} cancelled (status={job.get('status')}). Refund in Stripe if a real card was charged.")
        return 0
    print(f"❌ Cancel failed (HTTP {s}): {r}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
