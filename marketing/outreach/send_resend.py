"""Send Sequence B Email 1 to operator prospects via Resend.

Usage:
    RESEND_API_KEY=re_xxx python send_resend.py --csv send-ready.csv --test
    RESEND_API_KEY=re_xxx python send_resend.py --csv send-ready.csv --live

--test  -> sends a SINGLE email to TEST_RECIPIENT only
--live  -> sends to every row in the CSV with throttling

Tracks sends in send_log.csv so re-running --live skips already-sent rows.
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

LOG_PATH = Path(__file__).parent / "send_log.csv"


REPLY_MAILTO = (
    "mailto:se7nz7@gmail.com"
    "?subject=Re%3A%203%20trucks%20%E2%86%92%2010%20trucks%20-%20interested"
)


def _greeting(first_name: str, company: str) -> str:
    fn = (first_name or "").strip()
    if fn:
        return f"Hi {fn},"
    return f"Hi {company} team,"


def render_plain(first_name: str, company: str, city: str) -> tuple[str, str]:
    city_clean = (city or "").strip() or "your area"
    company_clean = (company or "").strip() or "your team"
    subject = "3 trucks → 10 trucks in 18 months"
    body = f"""{_greeting(first_name, company_clean)}

Mike at DFW Hauling started with 3 trucks in {city_clean}, same as {company_clean}.

18 months later? 10 trucks and booked solid 6 days a week.

His secret wasn't marketing — it was operations. Umuve automated his quotes, dispatch, and invoicing. He went from firefighting admin work to actually growing his business.

Think {company_clean} could use that extra time?

Reply to this email and I'll send over the 2-minute playbook.

Best,
Shamar
Founder, Umuve
https://goumuve.com
"""
    return subject, body


def render_html(first_name: str, company: str, city: str) -> str:
    """Operator-recruitment Email 1, Sequence B. Uses the editorial-letter template."""
    from letter_template import render_editorial_letter
    city_clean = (city or "").strip() or "your area"
    company_clean = (company or "").strip() or "your team"
    greeting = _greeting(first_name, company_clean)
    return render_editorial_letter(
        eyebrow="SUBJECT &middot; DFW HAULING, TEXAS",
        headline_html='3 trucks <span style="color:#DC2626">&rarr;</span><br/><em>ten trucks.</em><br/>Eighteen months.',
        paragraphs=[
            greeting,
            f"Mike runs <strong>DFW Hauling</strong>. Same setup as <strong>{company_clean}</strong> &mdash; three trucks, working {city_clean}, riding along himself half the days.",
            "Eighteen months later, ten trucks. Booked six days a week. <em>He stopped riding along.</em>",
            "It wasn&rsquo;t more marketing. It was <strong>operations</strong> &mdash; quoting, dispatch, invoicing, all automated. The stuff you keep meaning to fix when you finally get a free Saturday.",
            "If you want it, I&rsquo;ll send the exact playbook he used. No call. No deck. One email.",
        ],
        cta_text="SEND ME THE PLAYBOOK &rarr;",
        cta_link=REPLY_MAILTO,
    )


def send_one(to_email: str, first_name: str, company: str, city: str, dry_run: bool = False) -> tuple[bool, str]:
    subject, body = render_plain(first_name, company, city)
    html = render_html(first_name, company, city)
    payload = {
        "from": FROM,
        "to": [to_email],
        "reply_to": REPLY_TO,
        "subject": subject,
        "text": body,
        "html": html,
    }
    if dry_run:
        print(f"[DRY] -> {to_email} ({company}) subject={subject}")
        return True, "dry"
    r = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    if r.status_code in (200, 202):
        return True, r.json().get("id", "")
    return False, f"{r.status_code}:{r.text[:120]}"


def already_sent() -> set[str]:
    if not LOG_PATH.exists():
        return set()
    with LOG_PATH.open() as f:
        return {row["email"] for row in csv.DictReader(f) if row.get("status") == "ok"}


def log_send(email: str, company: str, status: str, msg_id: str) -> None:
    new = not LOG_PATH.exists()
    with LOG_PATH.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "email", "company", "status", "message_id"])
        w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), email, company, status, msg_id])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--test", action="store_true", help="Send one to TEST_RECIPIENT")
    ap.add_argument("--live", action="store_true", help="Send to all rows")
    ap.add_argument("--delay", type=float, default=2.5, help="Seconds between sends in --live")
    args = ap.parse_args()

    if not API_KEY:
        print("RESEND_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    if not (args.test or args.live):
        print("Pass --test or --live", file=sys.stderr)
        sys.exit(1)

    rows = list(csv.DictReader(open(args.csv)))
    print(f"Loaded {len(rows)} prospects from {args.csv}")

    if args.test:
        first = rows[0]
        print(f"Test send using personalization from row 1: {first['company']}")
        ok, info = send_one(
            to_email=TEST_RECIPIENT,
            first_name=first.get("first_name", ""),
            company=first.get("company", ""),
            city=first.get("area", ""),
        )
        print(f"  -> {'OK' if ok else 'FAIL'}: {info}")
        return

    sent_emails = already_sent()
    print(f"Already sent: {len(sent_emails)} (will skip)")

    sent = skipped = failed = 0
    for i, row in enumerate(rows, 1):
        email = (row.get("email") or "").strip().lower()
        if not email:
            continue
        if email in sent_emails:
            skipped += 1
            continue
        ok, info = send_one(
            to_email=email,
            first_name=row.get("first_name", ""),
            company=row.get("company", ""),
            city=row.get("area", ""),
        )
        status = "ok" if ok else "fail"
        log_send(email, row.get("company", ""), status, info)
        if ok:
            sent += 1
            print(f"  [{i:3}/{len(rows)}] OK    {email} ({row.get('company','')})")
        else:
            failed += 1
            print(f"  [{i:3}/{len(rows)}] FAIL  {email}: {info}")
        time.sleep(args.delay)

    print(f"\nDone. sent={sent} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    main()
