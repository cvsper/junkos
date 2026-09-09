#!/usr/bin/env python3
"""
Operator hygiene before flipping ads on.

Dispatch routes a paid job to whoever is approved + ONLINE + closest. If a
leftover TEST account is online, a real customer's first job routes to someone
who can't fulfill it. This lists every operator (online/approved, flagging
likely-test names) so you can see who'd actually receive jobs — and suspends
the ones you name (suspend = approval revoked + forced offline, so they drop
out of dispatch entirely).

Usage:
    # list everyone (safe, read-only):
    python3 scripts/operators.py --email you@admin --password 'xxx'
    # suspend specific test accounts (comma-separated contractor IDs):
    python3 scripts/operators.py --email ... --password ... --suspend <id>,<id>
    # env: ADMIN_LOGIN_EMAIL / ADMIN_LOGIN_PASSWORD (or --token)
"""
import argparse, json, os, re, ssl, sys, urllib.request, urllib.error
try:
    import certifi; CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    CTX = ssl.create_default_context()

TEST_RE = re.compile(r"\b(test|dummy|demo|sample|qa|jumm|dings|claw|pete|james)\b", re.I)


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
    ap.add_argument("--email", default=os.environ.get("ADMIN_LOGIN_EMAIL"))
    ap.add_argument("--password", default=os.environ.get("ADMIN_LOGIN_PASSWORD"))
    ap.add_argument("--token", default=os.environ.get("ADMIN_TOKEN"))
    ap.add_argument("--suspend", default="", help="comma-separated contractor IDs to suspend")
    a = ap.parse_args()
    base = a.base.rstrip("/")
    token = a.token or (login(base, a.email, a.password) if (a.email and a.password) else None)
    if not token:
        print("Auth failed — need --email/--password or --token."); return 2

    s, r = call(base, "/api/admin/contractors?per_page=200", token=token)
    if s != 200:
        print(f"contractors fetch failed (HTTP {s}): {r}"); return 2
    rows = r.get("contractors") or r.get("data") or []

    print(f"\n{'name':26} {'status':10} {'online':7} {'likely-test':11} id")
    print("-" * 92)
    online_real, online_test = [], []
    for c in rows:
        name = (c.get("name") or "?")
        st = c.get("approval_status", "?")
        online = bool(c.get("is_online"))
        cid = c.get("id", "?")
        suspect = bool(TEST_RE.search(name)) or not name or name == "?"
        if online and st == "approved":
            (online_test if suspect else online_real).append((name, cid))
        flag = "⚠ test?" if suspect else ""
        print(f"  {name[:24]:24} {st:10} {'ONLINE' if online else 'off':7} {flag:11} {cid}")
    print("-" * 92)
    print(f"ONLINE + approved (will receive jobs): {len(online_real)+len(online_test)}")
    if online_real:
        print("  real-looking online: " + ", ".join(n for n, _ in online_real))
    if online_test:
        print("  ⚠ likely-TEST online (suspend these before ads):")
        for n, cid in online_test:
            print(f"      {n}  →  {cid}")

    sus = [x.strip() for x in a.suspend.split(",") if x.strip()]
    if sus:
        print("\nSuspending:")
        for cid in sus:
            s, r = call(base, f"/api/admin/contractors/{cid}/suspend", token=token, method="PUT")
            ok = s == 200
            print(f"  {cid}: {'✅ suspended (offline + approval revoked)' if ok else f'❌ HTTP {s} {r}'}")
    else:
        print("\n(Read-only. Re-run with --suspend <id>,<id> to remove test accounts from dispatch.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
