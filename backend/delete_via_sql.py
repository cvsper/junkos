#!/usr/bin/env python3
"""Delete jobs without category field via direct SQL"""
import psycopg2
import json
import os

# Get database URL from environment (same as Flask app uses)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "postgresql://junkos_db_user:9VcwYdvLAMkxB0wH4FvmG6i3dCJZS28V@dpg-d02lk7btq21c738mhe00-a.oregon-postgres.render.com/junkos_db"

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
