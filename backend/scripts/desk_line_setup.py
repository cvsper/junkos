#!/usr/bin/env python3
"""Provision the Call Desk line on Twilio (one-time, idempotent where it can be).

What it does, in order:
  1. Picks the desk number: --number +1561xxxxxxx to use one you already own
     (or one you ported in), otherwise buys a local number in --area-code.
  2. Creates a TwiML App whose Voice URL is the backend's browser-dialer
     endpoint (/api/desk/twilio/voice).
  3. Creates an API Key (SID + secret) — the browser token signer.
  4. Points the number's SMS and Voice webhooks at the backend.
  5. Prints the env block to paste into Render.

Credentials: TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN in the environment, or a
file ~/.config/umuve-twilio containing "ACxxxx:authtoken" on one line.

Usage:
  python3 scripts/desk_line_setup.py --dry-run
  python3 scripts/desk_line_setup.py --area-code 561 --forward +1XXXXXXXXXX
  python3 scripts/desk_line_setup.py --number +15615551234 --forward +1XXXXXXXXXX

Not automated (Twilio console, one-time, ~15 min):
  A2P 10DLC — Trust Hub → A2P Messaging → register the Umuve brand (EIN,
  address, website goumuve.com), then a "Low volume mixed" campaign whose use
  case is customer care + conversational follow-up. Attach the desk number to
  the campaign's messaging service. Texts to US numbers are filtered or
  blocked until the campaign is approved (usually 1-3 business days).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BASE = os.environ.get("BACKEND_URL", "https://junkos-backend.onrender.com").rstrip("/")


def creds():
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    tok = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    if sid and tok:
        return sid, tok
    f = Path.home() / ".config" / "umuve-twilio"
    if f.exists():
        raw = f.read_text().strip().splitlines()[0]
        if ":" in raw:
            sid, tok = raw.split(":", 1)
            return sid.strip(), tok.strip()
    sys.exit("No Twilio creds. Set TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN or write "
             "'ACxxx:token' to ~/.config/umuve-twilio (chmod 600).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--number", help="E.164 number you already own on this account")
    ap.add_argument("--area-code", default="561")
    ap.add_argument("--forward", help="VA's cell, E.164 — rings with the browser on inbound")
    ap.add_argument("--friendly", default="Umuve Call Desk")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    sid, tok = creds()
    from twilio.rest import Client
    client = Client(sid, tok)

    acct = client.api.accounts(sid).fetch()
    print("Account: {} [{}]".format(acct.friendly_name, acct.status))
    if acct.status != "active":
        sys.exit("Account is {} — fix billing in the Twilio console first.".format(acct.status))

    sms_url = BASE + "/api/desk/twilio/sms"
    voice_in_url = BASE + "/api/desk/twilio/voice/inbound"
    voice_app_url = BASE + "/api/desk/twilio/voice"

    # 1. number
    number = None
    if args.number:
        owned = client.incoming_phone_numbers.list(phone_number=args.number, limit=1)
        if not owned:
            sys.exit("{} isn't on this account. Port it in first, or omit --number to buy one.".format(args.number))
        number = owned[0]
        print("Using owned number {}".format(number.phone_number))
    else:
        avail = client.available_phone_numbers("US").local.list(
            area_code=args.area_code, sms_enabled=True, voice_enabled=True, limit=5)
        if not avail:
            sys.exit("No {} numbers available right now — try another area code.".format(args.area_code))
        print("Available {}: {}".format(args.area_code, ", ".join(a.phone_number for a in avail)))
        if args.dry_run:
            print("[dry-run] would buy {}".format(avail[0].phone_number))
        else:
            number = client.incoming_phone_numbers.create(
                phone_number=avail[0].phone_number, friendly_name=args.friendly,
                sms_url=sms_url, sms_method="POST",
                voice_url=voice_in_url, voice_method="POST")
            print("Bought {}".format(number.phone_number))

    # 2. TwiML app
    app = None
    existing = [a for a in client.applications.list(friendly_name=args.friendly, limit=5)]
    if existing:
        app = existing[0]
        print("TwiML App exists: {}".format(app.sid))
        if not args.dry_run and app.voice_url != voice_app_url:
            app.update(voice_url=voice_app_url, voice_method="POST")
            print("  updated voice URL")
    elif args.dry_run:
        print("[dry-run] would create TwiML App '{}' → {}".format(args.friendly, voice_app_url))
    else:
        app = client.applications.create(friendly_name=args.friendly,
                                         voice_url=voice_app_url, voice_method="POST")
        print("Created TwiML App {}".format(app.sid))

    # 3. API key (secret is only shown once — printed below, never stored here)
    key = None
    if args.dry_run:
        print("[dry-run] would create API key '{}'".format(args.friendly))
    else:
        key = client.new_keys.create(friendly_name=args.friendly)
        print("Created API key {}".format(key.sid))

    # 4. webhooks on the number
    if number and not args.dry_run:
        number.update(sms_url=sms_url, sms_method="POST",
                      voice_url=voice_in_url, voice_method="POST",
                      friendly_name=args.friendly)
        print("Webhooks set on {}".format(number.phone_number))

    # 5. env block
    print("\n# ---- paste into Render env (junkos-backend) ----")
    print("DESK_TWILIO_NUMBER={}".format(number.phone_number if number else "+1XXXXXXXXXX"))
    if args.forward:
        print("DESK_FORWARD_NUMBER={}".format(args.forward))
    print("TWILIO_TWIML_APP_SID={}".format(app.sid if app else "APxxxxxxxx"))
    print("TWILIO_API_KEY_SID={}".format(key.sid if key else "SKxxxxxxxx"))
    print("TWILIO_API_KEY_SECRET={}".format(key.secret if key else "(shown once at creation)"))
    print("# optional: DESK_RECORD_CALLS=on   DESK_FORWARD_SMS=off")
    print("\nThen: Trust Hub → A2P 10DLC brand + campaign, attach the number (see docstring).")


if __name__ == "__main__":
    main()
