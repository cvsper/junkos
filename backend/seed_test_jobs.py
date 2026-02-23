#!/usr/bin/env python3
"""
Seed 10 test jobs for driver testing.
Creates jobs with "confirmed" status so they appear as available for drivers.

Usage:
    flask shell < seed_test_jobs.py
    OR
    python3 seed_test_jobs.py
"""

# For direct execution
if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    from models import db, User, Job, generate_uuid, utcnow
    from app_config import create_app
    from datetime import datetime, timezone, timedelta
    import random

    app = create_app()
    app_context = app.app_context()
    app_context.push()
else:
    # For flask shell execution
    from models import db, User, Job, generate_uuid, utcnow
    from datetime import datetime, timezone, timedelta
    import random

def seed_test_jobs():
    """Create 30 test jobs in confirmed status."""
    # When run from flask shell, app context is already active
    if True:
        # Find or create a test customer
        test_customer = User.query.filter_by(email="test@umuve.com").first()
        if not test_customer:
            test_customer = User(
                id=generate_uuid(),
                name="Test Customer",
                email="test@umuve.com",
                phone="+15555551234",
                role="customer",
            )
            db.session.add(test_customer)
            db.session.commit()
            print(f"✅ Created test customer: {test_customer.email}")
        else:
            print(f"✅ Found existing test customer: {test_customer.email}")

        # Test job data - various Florida locations
        test_jobs_data = [
            {
                "address": "123 Ocean Drive, Miami Beach, FL 33139",
                "lat": 25.7907,
                "lng": -80.1300,
                "items": [{"name": "Old Couch", "quantity": 1, "price": 50.0}],
                "notes": "Please call when arriving. Couch is on the second floor.",
                "total_price": 85.0,
            },
            {
                "address": "456 Palm Ave, Fort Lauderdale, FL 33301",
                "lat": 26.1224,
                "lng": -80.1373,
                "items": [
                    {"name": "Mattress", "quantity": 1, "price": 40.0},
                    {"name": "Box Spring", "quantity": 1, "price": 40.0}
                ],
                "notes": "Gate code is 1234. Items in garage.",
                "total_price": 105.0,
            },
            {
                "address": "789 Bay Street, Tampa, FL 33602",
                "lat": 27.9506,
                "lng": -82.4572,
                "items": [{"name": "Refrigerator", "quantity": 1, "price": 75.0}],
                "notes": "Heavy item - may need extra help.",
                "total_price": 120.0,
            },
            {
                "address": "321 Sunset Blvd, Orlando, FL 32801",
                "lat": 28.5383,
                "lng": -81.3792,
                "items": [
                    {"name": "Old TV", "quantity": 1, "price": 30.0},
                    {"name": "Microwave", "quantity": 1, "price": 25.0}
                ],
                "notes": "Electronics - please handle with care.",
                "total_price": 80.0,
            },
            {
                "address": "567 Beach Road, Jacksonville, FL 32202",
                "lat": 30.3322,
                "lng": -81.6557,
                "items": [{"name": "Washing Machine", "quantity": 1, "price": 70.0}],
                "notes": "Disconnected and ready to go.",
                "total_price": 115.0,
            },
            {
                "address": "890 Pine Street, St. Petersburg, FL 33701",
                "lat": 27.7676,
                "lng": -82.6403,
                "items": [{"name": "Desk", "quantity": 1, "price": 45.0}],
                "notes": "Office furniture - wooden desk with drawers.",
                "total_price": 90.0,
            },
            {
                "address": "234 Coral Way, Coral Gables, FL 33134",
                "lat": 25.7481,
                "lng": -80.2620,
                "items": [
                    {"name": "Dining Table", "quantity": 1, "price": 60.0},
                    {"name": "Chairs", "quantity": 4, "price": 40.0}
                ],
                "notes": "Full dining set - table plus 4 chairs.",
                "total_price": 125.0,
            },
            {
                "address": "678 Marina Drive, West Palm Beach, FL 33401",
                "lat": 26.7153,
                "lng": -80.0534,
                "items": [{"name": "Old Grill", "quantity": 1, "price": 35.0}],
                "notes": "Outdoor grill, needs cleaning but functional.",
                "total_price": 70.0,
            },
            {
                "address": "135 Lake Avenue, Clearwater, FL 33755",
                "lat": 27.9659,
                "lng": -82.8001,
                "items": [
                    {"name": "Bookshelf", "quantity": 1, "price": 50.0},
                    {"name": "Boxes of Books", "quantity": 3, "price": 30.0}
                ],
                "notes": "Heavy books - may need dolly.",
                "total_price": 110.0,
            },
            {
                "address": "999 Bayshore Blvd, Sarasota, FL 34236",
                "lat": 27.3364,
                "lng": -82.5307,
                "items": [{"name": "Treadmill", "quantity": 1, "price": 80.0}],
                "notes": "Exercise equipment - large and heavy.",
                "total_price": 130.0,
            },
            # Additional 20 jobs for 30 total
            {
                "address": "1501 Brickell Ave, Miami, FL 33129",
                "lat": 25.7617,
                "lng": -80.1918,
                "items": [{"name": "Filing Cabinet", "quantity": 2, "price": 60.0}],
                "notes": "Office cleanout - two metal cabinets.",
                "total_price": 95.0,
            },
            {
                "address": "2100 Collins Ave, Miami Beach, FL 33139",
                "lat": 25.7959,
                "lng": -80.1284,
                "items": [{"name": "Patio Furniture", "quantity": 1, "price": 70.0}],
                "notes": "Outdoor furniture set - table and chairs.",
                "total_price": 115.0,
            },
            {
                "address": "3300 NE 1st Ave, Miami, FL 33137",
                "lat": 25.8076,
                "lng": -80.1918,
                "items": [{"name": "Old Washer/Dryer", "quantity": 2, "price": 90.0}],
                "notes": "Laundry pair - both units need removal.",
                "total_price": 140.0,
            },
            {
                "address": "401 Biscayne Blvd, Miami, FL 33132",
                "lat": 25.7743,
                "lng": -80.1871,
                "items": [{"name": "Office Desk", "quantity": 3, "price": 75.0}],
                "notes": "Three desks from office renovation.",
                "total_price": 120.0,
            },
            {
                "address": "1200 Anastasia Ave, Coral Gables, FL 33134",
                "lat": 25.7459,
                "lng": -80.2615,
                "items": [{"name": "Piano", "quantity": 1, "price": 100.0}],
                "notes": "Upright piano - VERY HEAVY, needs 2+ people.",
                "total_price": 175.0,
            },
            {
                "address": "2500 E Las Olas Blvd, Fort Lauderdale, FL 33301",
                "lat": 26.1185,
                "lng": -80.1134,
                "items": [{"name": "Sectional Sofa", "quantity": 1, "price": 80.0}],
                "notes": "Large L-shaped sectional couch.",
                "total_price": 130.0,
            },
            {
                "address": "1 E Broward Blvd, Fort Lauderdale, FL 33301",
                "lat": 26.1224,
                "lng": -80.1434,
                "items": [{"name": "Elliptical Machine", "quantity": 1, "price": 65.0}],
                "notes": "Exercise equipment from home gym.",
                "total_price": 105.0,
            },
            {
                "address": "3501 N Federal Hwy, Fort Lauderdale, FL 33308",
                "lat": 26.1601,
                "lng": -80.1097,
                "items": [{"name": "Bed Frame", "quantity": 1, "price": 55.0}],
                "notes": "Queen size metal bed frame.",
                "total_price": 90.0,
            },
            {
                "address": "101 N Ocean Dr, Hollywood, FL 33019",
                "lat": 26.0112,
                "lng": -80.1218,
                "items": [{"name": "Hot Tub", "quantity": 1, "price": 120.0}],
                "notes": "Old hot tub - EXTREMELY HEAVY, needs professional removal.",
                "total_price": 200.0,
            },
            {
                "address": "2000 S Dixie Hwy, Miami, FL 33133",
                "lat": 25.7459,
                "lng": -80.2042,
                "items": [{"name": "Entertainment Center", "quantity": 1, "price": 50.0}],
                "notes": "Large wooden entertainment center.",
                "total_price": 85.0,
            },
            {
                "address": "1200 S Flagler Dr, West Palm Beach, FL 33401",
                "lat": 26.7067,
                "lng": -80.0495,
                "items": [{"name": "Lawn Mower", "quantity": 1, "price": 40.0}],
                "notes": "Riding lawn mower - runs but old.",
                "total_price": 75.0,
            },
            {
                "address": "400 Clematis St, West Palm Beach, FL 33401",
                "lat": 26.7153,
                "lng": -80.0533,
                "items": [{"name": "Conference Table", "quantity": 1, "price": 85.0}],
                "notes": "Large office conference table.",
                "total_price": 135.0,
            },
            {
                "address": "1500 S Ocean Blvd, Delray Beach, FL 33483",
                "lat": 26.4525,
                "lng": -80.0717,
                "items": [{"name": "Wardrobe", "quantity": 2, "price": 70.0}],
                "notes": "Two large wardrobes from bedroom.",
                "total_price": 115.0,
            },
            {
                "address": "801 E Atlantic Ave, Delray Beach, FL 33483",
                "lat": 26.4615,
                "lng": -80.0628,
                "items": [{"name": "Pool Table", "quantity": 1, "price": 110.0}],
                "notes": "Full size pool table - needs disassembly.",
                "total_price": 180.0,
            },
            {
                "address": "2201 NW 2nd Ave, Boca Raton, FL 33431",
                "lat": 26.3754,
                "lng": -80.0810,
                "items": [{"name": "Armchair", "quantity": 3, "price": 45.0}],
                "notes": "Three matching armchairs.",
                "total_price": 80.0,
            },
            {
                "address": "1000 Glades Rd, Boca Raton, FL 33431",
                "lat": 26.3683,
                "lng": -80.0831,
                "items": [{"name": "Cabinet", "quantity": 4, "price": 80.0}],
                "notes": "Kitchen cabinets from renovation.",
                "total_price": 125.0,
            },
            {
                "address": "7100 W Camino Real, Boca Raton, FL 33433",
                "lat": 26.3587,
                "lng": -80.1753,
                "items": [{"name": "Chest Freezer", "quantity": 1, "price": 60.0}],
                "notes": "Large chest freezer from garage.",
                "total_price": 100.0,
            },
            {
                "address": "201 E Palmetto Park Rd, Boca Raton, FL 33432",
                "lat": 26.3587,
                "lng": -80.0784,
                "items": [{"name": "Dresser", "quantity": 2, "price": 55.0}],
                "notes": "Two bedroom dressers with mirrors.",
                "total_price": 95.0,
            },
            {
                "address": "3850 NW 25th St, Miami, FL 33142",
                "lat": 25.7988,
                "lng": -80.2543,
                "items": [{"name": "Shelving Units", "quantity": 5, "price": 65.0}],
                "notes": "Metal warehouse shelving - 5 units.",
                "total_price": 110.0,
            },
            {
                "address": "9700 Collins Ave, Bal Harbour, FL 33154",
                "lat": 25.8906,
                "lng": -80.1231,
                "items": [{"name": "Loveseat", "quantity": 1, "price": 45.0}],
                "notes": "Small loveseat, good condition.",
                "total_price": 80.0,
            },
        ]

        # Create jobs
        created_count = 0
        for job_data in test_jobs_data:
            # Schedule for various times in the next 7 days
            days_ahead = random.randint(0, 7)
            hours_ahead = random.randint(9, 17)  # 9 AM to 5 PM
            scheduled_at = datetime.now(timezone.utc) + timedelta(days=days_ahead, hours=hours_ahead)

            job = Job(
                id=generate_uuid(),
                customer_id=test_customer.id,
                status="confirmed",  # Available for drivers to accept
                address=job_data["address"],
                lat=job_data["lat"],
                lng=job_data["lng"],
                items=job_data["items"],
                notes=job_data.get("notes", ""),
                total_price=job_data["total_price"],
                item_total=job_data["total_price"] * 0.7,  # Rough item cost
                service_fee=job_data["total_price"] * 0.3,  # Rough service fee
                scheduled_at=scheduled_at,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            db.session.add(job)
            created_count += 1

        db.session.commit()
        print(f"✅ Created {created_count} test jobs in 'confirmed' status")
        print(f"📍 Jobs span Miami-Dade, Broward, and Palm Beach counties")
        print(f"📅 Scheduled between now and next 7 days")
        print(f"\n🚀 Drivers can now see and accept these jobs!")

if __name__ == "__main__":
    seed_test_jobs()
