#!/usr/bin/env python3
"""Delete jobs without category field via direct SQL.

The database URL comes from the environment ONLY. There is deliberately no
hardcoded fallback: this repository is public, and a connection string in a
tracked file is a credential leak the moment it is committed (see the 2026-09
audit, finding F04). Export DATABASE_URL from your secret store before running:

    export DATABASE_URL="$(cat ~/.config/umuve-database-url)"
    python3 delete_via_sql.py
"""
import json
import os
import sys

import psycopg2

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if not DATABASE_URL:
    sys.exit(
        "DATABASE_URL is not set.\n"
        "This script refuses to run without it — it will never carry an "
        "embedded connection string.\n"
        'Set it first, e.g.  export DATABASE_URL="postgresql://USER:PASSWORD@HOST/DBNAME"'
    )

# Connect to database with SSL
conn = psycopg2.connect(DATABASE_URL, sslmode='require')
cur = conn.cursor()

# Find and delete jobs where items don't have category
cur.execute("SELECT id, items FROM jobs WHERE status = 'confirmed'")
rows = cur.fetchall()

deleted_count = 0
for job_id, items_json in rows:
    if items_json:
        items = json.loads(items_json) if isinstance(items_json, str) else items_json
        # Check if any item is missing category
        missing_category = any("category" not in item for item in items)
        if missing_category:
            cur.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
            deleted_count += 1
            print(f"Deleted job {job_id}")

conn.commit()
cur.close()
conn.close()

print(f"\n✅ Deleted {deleted_count} jobs without category field")
