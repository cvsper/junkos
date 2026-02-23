#!/usr/bin/env python3
"""
Seed 30 test jobs directly to production database.
Requires DATABASE_URL environment variable.
"""
import os
import psycopg2
from datetime import datetime, timedelta
import random
import json
import uuid

# Get database URL from environment or use default
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://user:pass@host/db')

if 'postgresql://user:pass@host/db' in DATABASE_URL:
    print("❌ DATABASE_URL not set!")
    print("Set it with: export DATABASE_URL='your_render_postgres_url'")
    exit(1)

# Job locations (30 jobs)
jobs = [
    ("123 Ocean Drive, Miami Beach, FL 33139", 25.7907, -80.1300, '[{"name":"Old Couch","quantity":1}]', "Please call when arriving."),
    ("456 Palm Ave, Fort Lauderdale, FL 33301", 26.1224, -80.1373, '[{"name":"Mattress","quantity":1},{"name":"Box Spring","quantity":1}]', "Gate code is 1234."),
    ("1501 Brickell Ave, Miami, FL 33129", 25.7617, -80.1918, '[{"name":"Filing Cabinet","quantity":2}]', "Office cleanout."),
    ("2100 Collins Ave, Miami Beach, FL 33139", 25.7959, -80.1284, '[{"name":"Patio Furniture","quantity":1}]', "Outdoor furniture set."),
    ("3300 NE 1st Ave, Miami, FL 33137", 25.8076, -80.1918, '[{"name":"Washer/Dryer","quantity":2}]', "Laundry pair removal."),
    ("401 Biscayne Blvd, Miami, FL 33132", 25.7743, -80.1871, '[{"name":"Office Desk","quantity":3}]', "Three desks from office."),
    ("1200 Anastasia Ave, Coral Gables, FL 33134", 25.7459, -80.2615, '[{"name":"Piano","quantity":1}]', "VERY HEAVY - needs 2+ people."),
    ("2500 E Las Olas Blvd, Fort Lauderdale, FL 33301", 26.1185, -80.1134, '[{"name":"Sectional Sofa","quantity":1}]', "L-shaped sectional."),
    ("1 E Broward Blvd, Fort Lauderdale, FL 33301", 26.1224, -80.1434, '[{"name":"Elliptical","quantity":1}]', "Exercise equipment."),
    ("3501 N Federal Hwy, Fort Lauderdale, FL 33308", 26.1601, -80.1097, '[{"name":"Bed Frame","quantity":1}]', "Queen size metal frame."),
    ("101 N Ocean Dr, Hollywood, FL 33019", 26.0112, -80.1218, '[{"name":"Hot Tub","quantity":1}]', "EXTREMELY HEAVY."),
    ("2000 S Dixie Hwy, Miami, FL 33133", 25.7459, -80.2042, '[{"name":"Entertainment Center","quantity":1}]', "Large wooden unit."),
    ("1200 S Flagler Dr, West Palm Beach, FL 33401", 26.7067, -80.0495, '[{"name":"Lawn Mower","quantity":1}]', "Riding lawn mower."),
    ("400 Clematis St, West Palm Beach, FL 33401", 26.7153, -80.0533, '[{"name":"Conference Table","quantity":1}]', "Office table."),
    ("1500 S Ocean Blvd, Delray Beach, FL 33483", 26.4525, -80.0717, '[{"name":"Wardrobe","quantity":2}]', "Two large wardrobes."),
    ("801 E Atlantic Ave, Delray Beach, FL 33483", 26.4615, -80.0628, '[{"name":"Pool Table","quantity":1}]', "Needs disassembly."),
    ("2201 NW 2nd Ave, Boca Raton, FL 33431", 26.3754, -80.0810, '[{"name":"Armchair","quantity":3}]', "Three matching chairs."),
    ("1000 Glades Rd, Boca Raton, FL 33431", 26.3683, -80.0831, '[{"name":"Cabinet","quantity":4}]', "Kitchen cabinets."),
    ("7100 W Camino Real, Boca Raton, FL 33433", 26.3587, -80.1753, '[{"name":"Chest Freezer","quantity":1}]', "Large freezer."),
    ("201 E Palmetto Park Rd, Boca Raton, FL 33432", 26.3587, -80.0784, '[{"name":"Dresser","quantity":2}]', "Two bedroom dressers."),
    ("3850 NW 25th St, Miami, FL 33142", 25.7988, -80.2543, '[{"name":"Shelving Units","quantity":5}]', "Metal warehouse shelving."),
    ("9700 Collins Ave, Bal Harbour, FL 33154", 25.8906, -80.1231, '[{"name":"Loveseat","quantity":1}]', "Small loveseat."),
    ("789 Bay Street, Tampa, FL 33602", 27.9506, -82.4572, '[{"name":"Refrigerator","quantity":1}]', "Heavy item."),
    ("321 Sunset Blvd, Orlando, FL 32801", 28.5383, -81.3792, '[{"name":"TV","quantity":1},{"name":"Microwave","quantity":1}]', "Electronics."),
    ("567 Beach Road, Jacksonville, FL 32202", 30.3322, -81.6557, '[{"name":"Washing Machine","quantity":1}]', "Disconnected."),
    ("890 Pine Street, St. Petersburg, FL 33701", 27.7676, -80.6403, '[{"name":"Desk","quantity":1}]', "Wooden desk."),
    ("234 Coral Way, Coral Gables, FL 33134", 25.7481, -80.2620, '[{"name":"Dining Table","quantity":1},{"name":"Chairs","quantity":4}]', "Full dining set."),
    ("678 Marina Drive, West Palm Beach, FL 33401", 26.7153, -80.0534, '[{"name":"Grill","quantity":1}]', "Outdoor grill."),
    ("135 Lake Avenue, Clearwater, FL 33755", 27.9659, -82.8001, '[{"name":"Bookshelf","quantity":1},{"name":"Books","quantity":3}]', "Heavy books."),
    ("999 Bayshore Blvd, Sarasota, FL 34236", 27.3364, -82.5307, '[{"name":"Treadmill","quantity":1}]', "Exercise equipment."),
]

try:
    # Connect to database
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Get test customer ID
    cur.execute("SELECT id FROM users WHERE email = 'test@umuve.com' LIMIT 1")
    result = cur.fetchone()

    if not result:
        print("❌ Test customer not found! Create test@umuve.com first.")
        exit(1)

    customer_id = result[0]
    print(f"✅ Found test customer: {customer_id}")

    # Create 30 jobs
    created = 0
    for address, lat, lng, items, notes in jobs:
        # Random schedule in next 7 days
        days_ahead = random.randint(0, 7)
        hours_ahead = random.randint(9, 17)
        scheduled_at = datetime.now() + timedelta(days=days_ahead, hours=hours_ahead)

        # Random pricing
        total = random.randint(70, 200)
        item_total = total * 0.7
        service_fee = total * 0.3

        job_id = str(uuid.uuid4())

        cur.execute("""
            INSERT INTO jobs (
                id, customer_id, status, address, lat, lng,
                items, notes, total_price, item_total, service_fee,
                scheduled_at, created_at, updated_at
            ) VALUES (
                %s, %s, 'confirmed', %s, %s, %s,
                %s::jsonb, %s, %s, %s, %s,
                %s, NOW(), NOW()
            )
        """, (job_id, customer_id, address, lat, lng, items, notes,
              total, item_total, service_fee, scheduled_at))

        created += 1
        print(f"✅ Created job {created}/30: {address[:40]}...")

    conn.commit()
    print(f"\n🎉 Successfully created {created} jobs!")
    print(f"📍 Jobs span Miami-Dade, Broward, and Palm Beach counties")
    print(f"📅 Scheduled between now and next 7 days")

except Exception as e:
    print(f"❌ Error: {e}")
    if conn:
        conn.rollback()
finally:
    if cur:
        cur.close()
    if conn:
        conn.close()
