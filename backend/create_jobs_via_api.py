#!/usr/bin/env python3
"""
Create 30 test jobs via API calls to the live backend.
"""
import requests
import random
from datetime import datetime, timedelta, timezone

API_URL = "https://junkos-backend.onrender.com/api"

# Test customer credentials
TEST_EMAIL = "test@umuve.com"
TEST_PASSWORD = "test1234"  # You'll need to set this

# Job data for 30 jobs
jobs_data = [
    {
        "address": "123 Ocean Drive, Miami Beach, FL 33139",
        "lat": 25.7907,
        "lng": -80.1300,
        "items": [{"name": "Old Couch", "quantity": 1}],
        "notes": "Please call when arriving. Couch is on the second floor.",
    },
    {
        "address": "456 Palm Ave, Fort Lauderdale, FL 33301",
        "lat": 26.1224,
        "lng": -80.1373,
        "items": [
            {"name": "Mattress", "quantity": 1},
            {"name": "Box Spring", "quantity": 1}
        ],
        "notes": "Gate code is 1234. Items in garage.",
    },
    {
        "address": "1501 Brickell Ave, Miami, FL 33129",
        "lat": 25.7617,
        "lng": -80.1918,
        "items": [{"name": "Filing Cabinet", "quantity": 2}],
        "notes": "Office cleanout - two metal cabinets.",
    },
    {
        "address": "2100 Collins Ave, Miami Beach, FL 33139",
        "lat": 25.7959,
        "lng": -80.1284,
        "items": [{"name": "Patio Furniture", "quantity": 1}],
        "notes": "Outdoor furniture set - table and chairs.",
    },
    {
        "address": "3300 NE 1st Ave, Miami, FL 33137",
        "lat": 25.8076,
        "lng": -80.1918,
        "items": [{"name": "Old Washer/Dryer", "quantity": 2}],
        "notes": "Laundry pair - both units need removal.",
    },
    {
        "address": "401 Biscayne Blvd, Miami, FL 33132",
        "lat": 25.7743,
        "lng": -80.1871,
        "items": [{"name": "Office Desk", "quantity": 3}],
        "notes": "Three desks from office renovation.",
    },
    {
        "address": "1200 Anastasia Ave, Coral Gables, FL 33134",
        "lat": 25.7459,
        "lng": -80.2615,
        "items": [{"name": "Piano", "quantity": 1}],
        "notes": "Upright piano - VERY HEAVY, needs 2+ people.",
    },
    {
        "address": "2500 E Las Olas Blvd, Fort Lauderdale, FL 33301",
        "lat": 26.1185,
        "lng": -80.1134,
        "items": [{"name": "Sectional Sofa", "quantity": 1}],
        "notes": "Large L-shaped sectional couch.",
    },
    {
        "address": "1 E Broward Blvd, Fort Lauderdale, FL 33301",
        "lat": 26.1224,
        "lng": -80.1434,
        "items": [{"name": "Elliptical Machine", "quantity": 1}],
        "notes": "Exercise equipment from home gym.",
    },
    {
        "address": "3501 N Federal Hwy, Fort Lauderdale, FL 33308",
        "lat": 26.1601,
        "lng": -80.1097,
        "items": [{"name": "Bed Frame", "quantity": 1}],
        "notes": "Queen size metal bed frame.",
    },
    {
        "address": "101 N Ocean Dr, Hollywood, FL 33019",
        "lat": 26.0112,
        "lng": -80.1218,
        "items": [{"name": "Hot Tub", "quantity": 1}],
        "notes": "Old hot tub - EXTREMELY HEAVY, needs professional removal.",
    },
    {
        "address": "2000 S Dixie Hwy, Miami, FL 33133",
        "lat": 25.7459,
        "lng": -80.2042,
        "items": [{"name": "Entertainment Center", "quantity": 1}],
        "notes": "Large wooden entertainment center.",
    },
    {
        "address": "1200 S Flagler Dr, West Palm Beach, FL 33401",
        "lat": 26.7067,
        "lng": -80.0495,
        "items": [{"name": "Lawn Mower", "quantity": 1}],
        "notes": "Riding lawn mower - runs but old.",
    },
    {
        "address": "400 Clematis St, West Palm Beach, FL 33401",
        "lat": 26.7153,
        "lng": -80.0533,
        "items": [{"name": "Conference Table", "quantity": 1}],
        "notes": "Large office conference table.",
    },
    {
        "address": "1500 S Ocean Blvd, Delray Beach, FL 33483",
        "lat": 26.4525,
        "lng": -80.0717,
        "items": [{"name": "Wardrobe", "quantity": 2}],
        "notes": "Two large wardrobes from bedroom.",
    },
    {
        "address": "801 E Atlantic Ave, Delray Beach, FL 33483",
        "lat": 26.4615,
        "lng": -80.0628,
        "items": [{"name": "Pool Table", "quantity": 1}],
        "notes": "Full size pool table - needs disassembly.",
    },
    {
        "address": "2201 NW 2nd Ave, Boca Raton, FL 33431",
        "lat": 26.3754,
        "lng": -80.0810,
        "items": [{"name": "Armchair", "quantity": 3}],
        "notes": "Three matching armchairs.",
    },
    {
        "address": "1000 Glades Rd, Boca Raton, FL 33431",
        "lat": 26.3683,
        "lng": -80.0831,
        "items": [{"name": "Cabinet", "quantity": 4}],
        "notes": "Kitchen cabinets from renovation.",
    },
    {
        "address": "7100 W Camino Real, Boca Raton, FL 33433",
        "lat": 26.3587,
        "lng": -80.1753,
        "items": [{"name": "Chest Freezer", "quantity": 1}],
        "notes": "Large chest freezer from garage.",
    },
    {
        "address": "201 E Palmetto Park Rd, Boca Raton, FL 33432",
        "lat": 26.3587,
        "lng": -80.0784,
        "items": [{"name": "Dresser", "quantity": 2}],
        "notes": "Two bedroom dressers with mirrors.",
    },
    {
        "address": "3850 NW 25th St, Miami, FL 33142",
        "lat": 25.7988,
        "lng": -80.2543,
        "items": [{"name": "Shelving Units", "quantity": 5}],
        "notes": "Metal warehouse shelving - 5 units.",
    },
    {
        "address": "9700 Collins Ave, Bal Harbour, FL 33154",
        "lat": 25.8906,
        "lng": -80.1231,
        "items": [{"name": "Loveseat", "quantity": 1}],
        "notes": "Small loveseat, good condition.",
    },
    {
        "address": "789 Bay Street, Tampa, FL 33602",
        "lat": 27.9506,
        "lng": -82.4572,
        "items": [{"name": "Refrigerator", "quantity": 1}],
        "notes": "Heavy item - may need extra help.",
    },
    {
        "address": "321 Sunset Blvd, Orlando, FL 32801",
        "lat": 28.5383,
        "lng": -81.3792,
        "items": [
            {"name": "Old TV", "quantity": 1},
            {"name": "Microwave", "quantity": 1}
        ],
        "notes": "Electronics - please handle with care.",
    },
    {
        "address": "567 Beach Road, Jacksonville, FL 32202",
        "lat": 30.3322,
        "lng": -81.6557,
        "items": [{"name": "Washing Machine", "quantity": 1}],
        "notes": "Disconnected and ready to go.",
    },
    {
        "address": "890 Pine Street, St. Petersburg, FL 33701",
        "lat": 27.7676,
        "lng": -82.6403,
        "items": [{"name": "Desk", "quantity": 1}],
        "notes": "Office furniture - wooden desk with drawers.",
    },
    {
        "address": "234 Coral Way, Coral Gables, FL 33134",
        "lat": 25.7481,
        "lng": -80.2620,
        "items": [
            {"name": "Dining Table", "quantity": 1},
            {"name": "Chairs", "quantity": 4}
        ],
        "notes": "Full dining set - table plus 4 chairs.",
    },
    {
        "address": "678 Marina Drive, West Palm Beach, FL 33401",
        "lat": 26.7153,
        "lng": -80.0534,
        "items": [{"name": "Old Grill", "quantity": 1}],
        "notes": "Outdoor grill, needs cleaning but functional.",
    },
    {
        "address": "135 Lake Avenue, Clearwater, FL 33755",
        "lat": 27.9659,
        "lng": -82.8001,
        "items": [
            {"name": "Bookshelf", "quantity": 1},
            {"name": "Boxes of Books", "quantity": 3}
        ],
        "notes": "Heavy books - may need dolly.",
    },
    {
        "address": "999 Bayshore Blvd, Sarasota, FL 34236",
        "lat": 27.3364,
        "lng": -82.5307,
        "items": [{"name": "Treadmill", "quantity": 1}],
        "notes": "Exercise equipment - large and heavy.",
    },
]

print("Creating 30 test jobs...")
print(f"This script will create jobs via direct database insertion.")
print(f"\nNote: Requires backend access for job creation.\n")
print("Copy and run the following SQL commands on your backend database:\n")

for i, job in enumerate(jobs_data, 1):
    # Generate random scheduled time in next 7 days
    days_ahead = random.randint(0, 7)
    hours_ahead = random.randint(9, 17)

    print(f"-- Job {i}: {job['address'][:40]}")
    print(f"INSERT INTO jobs (id, customer_id, status, address, lat, lng, items, notes, total_price, item_total, service_fee, scheduled_at, created_at, updated_at)")
    print(f"VALUES (")
    print(f"  gen_random_uuid(),")
    print(f"  (SELECT id FROM users WHERE email = 'test@umuve.com' LIMIT 1),")
    print(f"  'confirmed',")
    print(f"  '{job['address']}',")
    print(f"  {job['lat']},")
    print(f"  {job['lng']},")
    print(f"  '{str(job['items']).replace(\"'\", '\"')}',")
    print(f"  '{job['notes']}',")
    print(f"  {random.randint(70, 200)}.00,")
    print(f"  {random.randint(50, 140)}.00,")
    print(f"  {random.randint(20, 60)}.00,")
    print(f"  NOW() + INTERVAL '{days_ahead} days {hours_ahead} hours',")
    print(f"  NOW(),")
    print(f"  NOW()")
    print(f");")
    print()

print(f"\n✅ Generated SQL for 30 jobs")
print(f"📍 Jobs span Miami-Dade, Broward, and Palm Beach counties")
print(f"📅 Scheduled between now and next 7 days")
