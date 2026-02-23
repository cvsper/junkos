#!/usr/bin/env python3
"""Check if all jobs have category field"""
import requests

API_URL = "https://junkos-backend.onrender.com"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiYWRhODlhMWE5YWVjMDBkZTI3YzY4ZWExODFlMmYzZjQiLCJleHAiOjE3NzQ0MDUxMjV9.bpc0C-uH6xUo9I57VDtS-t8LpDNT4CvYPPrpZLHpwfM"

response = requests.get(
    f"{API_URL}/api/drivers/jobs/available",
    headers={"Authorization": f"Bearer {TOKEN}"}
)

if response.status_code == 200:
    data = response.json()
    jobs = data.get("jobs", [])

    total = len(jobs)
    with_category = sum(1 for j in jobs if j.get("items") and all("category" in item for item in j["items"]))
    without_category = total - with_category

    print(f"✅ Total jobs: {total}")
    print(f"✅ Jobs with category: {with_category}")
    print(f"❌ Jobs without category: {without_category}")

    if without_category == 0:
        print("\n🎉 All jobs have category field! iOS app should work now.")
    else:
        print(f"\n⚠️  {without_category} jobs still missing category field")
        # Show first few jobs without category
        for i, job in enumerate(jobs[:5]):
            if job.get("items") and any("category" not in item for item in job["items"]):
                print(f"  Job {job['id']}: {job['items']}")
else:
    print(f"❌ Error: {response.status_code}")
    print(response.text)
