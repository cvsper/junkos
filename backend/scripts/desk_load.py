#!/usr/bin/env python3
"""Load a call list into Tracy's Call Desk queue.

    python3 backend/scripts/desk_load.py ~/Desktop/umuve-call-list-sep08.csv
    python3 backend/scripts/desk_load.py ~/Desktop/umuve-call-desk-import-aug16.json
    python3 backend/scripts/desk_load.py list.csv --dry-run

Accepts the weekly / re-touch CSVs as they are (Tier, Company, Phone, City,
What they do, Contact, Notes …) or a JSON payload {"rows": [...]}. Merges on
phone digits, so re-running a file is safe — nothing already in the queue is
touched.

Auth: the desk passcode, read from ~/.config/umuve-va-passcode (one line,
chmod 600) or the UMUVE_VA_PASSCODE env. Same code Tracy uses to open /va.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

BASE = os.environ.get("UMUVE_API", "https://junkos-backend.onrender.com").rstrip("/")


def passcode():
    code = os.environ.get("UMUVE_VA_PASSCODE", "").strip()
    if code:
        return code
    f = Path.home() / ".config" / "umuve-va-passcode"
    if f.exists():
        return f.read_text().strip().splitlines()[0].strip()
    sys.exit("No desk passcode. Put the VA access code (the one used at goumuve /va) in "
             "~/.config/umuve-va-passcode and chmod 600 it.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--dry-run", action="store_true", help="parse and count, send nothing")
    args = ap.parse_args()

    path = Path(args.file).expanduser()
    if not path.exists():
        sys.exit("No such file: {}".format(path))
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json":
        rows = json.loads(text).get("rows") or []
        payload = {"rows": rows}
        n = len(rows)
    else:
        payload = {"csv": text}
        n = max(0, text.count("\n") - 1)
    print("{}: ~{} rows".format(path.name, n))
    if args.dry_run:
        return

    payload["code"] = passcode()
    req = urllib.request.Request(BASE + "/api/va/calls/import",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            msg = json.load(e).get("error")
        except Exception:
            msg = e.reason
        sys.exit("Import failed ({}): {}".format(e.code, msg))
    print("added {added}  ·  already in queue {skipped_dupes}  ·  skipped {invalid}  ·  "
          "queue total {total}".format(**body))


if __name__ == "__main__":
    main()
