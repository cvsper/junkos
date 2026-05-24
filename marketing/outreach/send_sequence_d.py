"""Send Sequence D (jobs-first hauler follow-up) via Resend — plain text.

Why a separate sender: the phase-1 tool (send_resend.py) pitches "ops
software" and leans on an invented case study. Sequence D pitches the real
marketplace hook — we route you paying jobs — and makes no claims we can't
back. Plain text on purpose: a founder recruiting local haulers should not
look like a marketing blast, and plain text lands in the inbox.

Usage:
    # Safe preview (default) — prints exactly what would send, sends nothing:
    python send_sequence_d.py --csv pbc-targets.csv --email 2

    # One real test to yourself:
    RESEND_API_KEY=re_xxx python send_sequence_d.py --csv pbc-targets.csv --email 2 --test

    # Live send to every eligible row (throttled, logged, resumable):
    RESEND_API_KEY=re_xxx python send_sequence_d.py --csv pbc-targets.csv --email 2 --live

--email 2  -> the jobs pivot (send first)
--email 3  -> the breakup (send ~4 days later, only to non-repliers)

Eligibility: rows where `replied` is blank AND (email, email_num) not already
in send_log_seq_d.csv. Set replied=yes in the CSV when someone responds so the
breakup skips them.
"""
import argparse
import csv
import os
import sys
import time
from pathlib import Path

import requests

API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM = "Shamar Donaldson <shamar@goumuve.com>"
REPLY_TO = "se7nz7@gmail.com"
TEST_RECIPIENT = "se7nz7@gmail.com"
LOG_PATH = Path(__file__).parent / "send_log_seq_d.csv"
THROTTLE_SECONDS = 2.0


def greeting(first_name: str, company: str) -> str:
    fn = (first_name or "").strip()
    if fn:
        return f"Hi {fn},"
    co = (company or "").strip() or "there"
    return f"Hi {co} team,"


def render(email_num: int, first_name: str, company: str, city: str) -> tuple[str, str]:
    city = (city or "").strip() or "your area"
    company = (company or "").strip() or "your team"
    g = greeting(first_name, company)

    if email_num == 2:
        subject = f"jobs in {city}, not software"
        body = f"""{g}

I emailed last week about Umuve and led with software — wrong pitch.

Here's the real reason I reached out: we're bringing customer demand for junk removal to {city}, and I'd rather route those jobs to an established operator like {company} than a stranger with a rented truck.

How it works: a customer books and pays through Umuve, we send you the job, you haul it, you get paid. No subscription, no upfront cost — you only deal with jobs you choose to accept.

We're onboarding a small number of haulers in {city} before we switch on local ads. Want one of those spots?

Reply "in" and I'll send the 5-minute setup.

Shamar
Founder, Umuve
https://goumuve.com
"""
        return subject, body

    if email_num == 3:
        subject = f"closing the {city} list"
        body = f"""{g}

Last note from me, promise.

We're finalizing the {company}-area hauler list this week. If you want first dibs on Umuve jobs in {city}, just reply and I'll hold a spot. If it's not for you, no hard feelings — I'll stop here.

Either way, good luck out there this season.

Shamar
Founder, Umuve
"""
        return subject, body

    raise SystemExit(f"--email must be 2 or 3, got {email_num}")


def send_one(to_email, first_name, company, city, email_num, dry_run):
    subject, body = render(email_num, first_name, company, city)
    if dry_run:
        print(f"\n[DRY] -> {to_email}  ({company} / {city})")
        print(f"       subject: {subject}")
        print("       " + body.strip().splitlines()[0])
        return True, "dry"
    if not API_KEY:
        return False, "RESEND_API_KEY not set"
    r = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"from": FROM, "to": [to_email], "reply_to": REPLY_TO,
              "subject": subject, "text": body},
        timeout=15,
    )
    if r.status_code in (200, 202):
        return True, r.json().get("id", "")
    return False, f"{r.status_code}:{r.text[:120]}"


def already_sent(email_num: int) -> set[str]:
    if not LOG_PATH.exists():
        return set()
    with LOG_PATH.open() as f:
        return {row["email"] for row in csv.DictReader(f)
                if row.get("status") == "ok" and row.get("email_num") == str(email_num)}


def log_send(email, company, email_num, status, msg_id):
    new = not LOG_PATH.exists()
    with LOG_PATH.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "email", "company", "email_num", "status", "message_id"])
        w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), email, company, email_num, status, msg_id])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--email", type=int, default=2, help="2=jobs pivot, 3=breakup")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--test", action="store_true", help="send ONE real email to yourself")
    g.add_argument("--live", action="store_true", help="send to all eligible rows")
    args = ap.parse_args()
    dry = not (args.test or args.live)

    rows = list(csv.DictReader(open(args.csv)))
    sent = already_sent(args.email)

    eligible, skipped_replied, skipped_sent = [], 0, 0
    for r in rows:
        if (r.get("replied") or "").strip():
            skipped_replied += 1
            continue
        if r["email"] in sent:
            skipped_sent += 1
            continue
        eligible.append(r)

    mode = "DRY-RUN (nothing sends)" if dry else ("TEST (1 email to you)" if args.test else "LIVE")
    print(f"Sequence D · Email {args.email} · {mode}")
    print(f"{len(rows)} rows | {len(eligible)} eligible | "
          f"{skipped_replied} already replied | {skipped_sent} already sent\n")

    if args.test:
        ok, info = send_one(TEST_RECIPIENT, "Shamar", "Test Co", "West Palm Beach", args.email, False)
        print(f"  test -> {TEST_RECIPIENT}: {'OK '+info if ok else 'FAIL '+info}")
        return

    ok_n = 0
    for r in eligible:
        ok, info = send_one(r["email"], r.get("first_name", ""), r.get("company", ""),
                            r.get("city", ""), args.email, dry)
        status = "ok" if ok else "fail"
        if ok and not dry:
            ok_n += 1
        if not dry:
            log_send(r["email"], r.get("company", ""), args.email, status, info)
            print(f"  {status:4} {r['email']:38} {info}")
            time.sleep(THROTTLE_SECONDS)

    if dry:
        print(f"\n→ {len(eligible)} emails queued. Re-run with --live to send (needs RESEND_API_KEY).")
    else:
        print(f"\nSent {ok_n}/{len(eligible)}. Log: {LOG_PATH.name}")


if __name__ == "__main__":
    main()
