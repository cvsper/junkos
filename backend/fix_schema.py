#!/usr/bin/env python3
"""
Emergency schema fix for production database.
Makes user columns nullable and adds missing apple_id column.
"""

import os
import sys

# Database connection
DATABASE_URL = os.environ.get('DATABASE_URL', '')
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable not set")
    sys.exit(1)

# Fix postgres:// -> postgresql:// for SQLAlchemy 2.x
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

import psycopg2

print("🔧 Umuve Backend - Emergency Schema Fix")
print("=" * 50)

# Connect to database
try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    print("✅ Connected to database")
except Exception as e:
    print(f"❌ Failed to connect: {e}")
    sys.exit(1)

migrations = []

# 1. Add apple_id column if missing
try:
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='users' AND column_name='apple_id'
    """)
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE users ADD COLUMN apple_id VARCHAR(255) UNIQUE")
        migrations.append("✅ Added apple_id column")
    else:
        migrations.append("⏭️  apple_id column already exists")
except Exception as e:
    migrations.append(f"❌ Failed to add apple_id: {e}")

# 2. Make email nullable
try:
    cursor.execute("ALTER TABLE users ALTER COLUMN email DROP NOT NULL")
    migrations.append("✅ Made email nullable")
except Exception as e:
    migrations.append(f"⏭️  email already nullable or failed: {e}")

# 3. Make phone nullable
try:
    cursor.execute("ALTER TABLE users ALTER COLUMN phone DROP NOT NULL")
    migrations.append("✅ Made phone nullable")
except Exception as e:
    migrations.append(f"⏭️  phone already nullable or failed: {e}")

# 4. Make name nullable
try:
    cursor.execute("ALTER TABLE users ALTER COLUMN name DROP NOT NULL")
    migrations.append("✅ Made name nullable")
except Exception as e:
    migrations.append(f"⏭️  name already nullable or failed: {e}")

# 5. Make password_hash nullable
try:
    cursor.execute("ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL")
    migrations.append("✅ Made password_hash nullable")
except Exception as e:
    migrations.append(f"⏭️  password_hash already nullable or failed: {e}")

# Commit changes
conn.commit()
cursor.close()
conn.close()

print("\n📋 Migration Results:")
for result in migrations:
    print(f"  {result}")

print("\n✅ Schema fix complete!")
print("Driver signup should now work.")
