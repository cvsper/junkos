#!/usr/bin/env python3
"""
Send the "set up payouts" reminder to signed contractors.

Pulls approved contractors from the admin API, filters out likely-test
accounts, and sends the `stripe_payout` campaign template to each one.
Approved contractors with NO usable email on file (phone-only signups)
get the reminder by SMS instead, via /api/admin/contractors/payout-reminder-sms.

Dry-run by default — prints the exact email recipient list AND the SMS
candidate list, then exits. Nothing is sent until you re-run with --send.

Usage:
    # preview recipients (safe, read-only):
    python3 scripts/send_payout_reminder.py --email you@admin --password 'xxx'
    # actually send:
    python3 scripts/send_payout_reminder.py --email ... --password ... --send
    # include contractors the test-name filter would skip:
    python3 scripts/send_payout_reminder.py ... --include <id>,<id>
    # env: ADMIN_LOGIN_EMAIL / ADMIN_LOGIN_PASSWORD (or --token)
"""
import argparse, json, os, re, ssl, urllib.request, urllib.error
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
        return e.code, {"error": e.read().decode()[:300]}
    except Exception as e:
        return 0, {"error": str(e)[:300]}


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
    ap.add_argument("--send", action="store_true", help="actually create + send the campaign")
    ap.add_argument("--include", default="", help="contractor IDs to include despite the test-name filter")
    a = ap.parse_args()
    base = a.base.rstrip("/")

    token = a.token or (login(base, a.email, a.password) if (a.email and a.password) else None)
    if not token:
        print("Auth failed — need --email/--password or --token."); return 2

    s, r = call(base, "/api/admin/contractors?status=approved&per_page=200", token=token)
    if s != 200:
        print(f"contractors fetch failed (HTTP {s}): {r}"); return 2
    rows = r.get("contractors") or []

    force_ids = {x.strip() for x in a.include.split(",") if x.strip()}
    seen, recipients, skipped = set(), [], []
    for c in rows:
        name = (c.get("name") or "").strip()
        email = (c.get("email") or "").strip().lower()
        cid = c.get("id", "?")
        if not email or "@" not in email or email in seen:
            continue
        if TEST_RE.search(name or "") and cid not in force_ids:
            skipped.append((name, email, cid)); continue
        seen.add(email)
        first = name.split()[0].title() if name else None
        recipients.append({"email": email, "first_name": first})

    print(f"\nEmail recipients ({len(recipients)}):")
    for rec in recipients:
        print(f"  {rec['first_name'] or '?':16} {rec['email']}")
    if skipped:
        print(f"\nSkipped as likely-test ({len(skipped)}) — use --include <id> to add back:")
        for name, email, cid in skipped:
            print(f"  {name:24} {email:32} {cid}")

    # Phone-only contractors (no usable email) get the reminder by text.
    s, r = call(base, "/api/admin/contractors/payout-reminder-sms", token=token,
                body={"send": False})
    sms_candidates = r.get("candidates", []) if s == 200 else []
    if s != 200:
        print(f"\n⚠ SMS candidate check failed (HTTP {s}): {r} — email leg unaffected.")
    print(f"\nSMS candidates — no email on file ({len(sms_candidates)}):")
    for cand in sms_candidates:
        name = cand.get("name") or "?"
        skip_flag = " ⚠ test?" if TEST_RE.search(name) else ""
        print(f"  {name:24} {cand.get('phone', '?'):16}{skip_flag}")

    if not recipients and not sms_candidates:
        print("\nNo recipients — nothing to do."); return 1
    if not a.send:
        print("\nDRY RUN — re-run with --send to send emails + texts."); return 0

    if sms_candidates:
        targets = [c["contractor_id"] for c in sms_candidates
                   if not TEST_RE.search(c.get("name") or "")]
        if targets:
            s, r = call(base, "/api/admin/contractors/payout-reminder-sms", token=token,
                        body={"send": True, "contractor_ids": targets})
            if s == 200:
                print(f"\nSMS: {r.get('sent')}/{r.get('total')} sent")
                for res in r.get("results", []):
                    print(f"  {'✅' if res.get('sent') else '❌'} {res.get('name'):24} {res.get('phone')}")
            else:
                print(f"\nSMS send failed (HTTP {s}): {r}")

    if not recipients:
        print("\nNo email recipients — done (SMS only)."); return 0

    s, r = call(base, "/api/campaigns", token=token, body={
        "name": "Payout setup reminder (Stripe Connect)",
        "template": "stripe_payout",
        "recipients": recipients,
    })
    if s != 201:
        print(f"campaign create failed (HTTP {s}): {r}"); return 2
    camp_id = r.get("id")
    print(f"\nCampaign created: {camp_id} ({r.get('total_recipients')} recipients)")

    s, r = call(base, f"/api/campaigns/{camp_id}/send", token=token, body={})
    if s != 200:
        print(f"send failed (HTTP {s}): {r}"); return 2
    print(f"Sending in background. Check status: GET /api/campaigns/{camp_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
