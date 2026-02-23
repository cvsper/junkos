#!/usr/bin/env python3
"""Delete test jobs without category field"""
import requests
import os

API_URL = os.getenv("API_URL", "https://junkos-backend.onrender.com")

# First, get all jobs to see what we're deleting
print("Checking current jobs...")
response = requests.get(
    f"{API_URL}/api/drivers/jobs/available",
    headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiYWRhODlhMWE5YWVjMDBkZTI3YzY4ZWExODFlMmYzZjQiLCJleHAiOjE3NzQ0MDUxMjV9.bpc0C-uH6xUo9I57VDtS-t8LpDNT4CvYPPrpZLHpwfM"}
)
jobs = response.json()["jobs"]

# Find jobs without category
jobs_to_delete = []
for job in jobs:
    if job["items"] and "category" not in job["items"][0]:
        jobs_to_delete.append(job["id"])

print(f"Found {len(jobs_to_delete)} jobs without category to delete")
print(f"Keeping {len(jobs) - len(jobs_to_delete)} jobs with category")

# Delete them
if jobs_to_delete:
    print(f"\nDeleting {len(jobs_to_delete)} old jobs...")
    delete_response = requests.post(f"{API_URL}/api/test/delete-jobs-without-category")

    if delete_response.status_code == 200:
        result = delete_response.json()
        print(f"✅ {result['message']}")
        print(f"Deleted: {result['deleted_count']} jobs")
    else:
        print(f"❌ Error: {delete_response.status_code}")
        print(delete_response.text)
else:
    print("No jobs to delete.")
