#!/usr/bin/env python3
"""Check completed jobs and their payment status"""
import requests

API_URL = "https://junkos-backend.onrender.com"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiYWRhODlhMWE5YWVjMDBkZTI3YzY4ZWExODFlMmYzZjQiLCJleHAiOjE3NzQ0MDUxMjV9.bpc0C-uH6xUo9I57VDtS-t8LpDNT4CvYPPrpZLHpwfM"

# Get contractor profile to get driver ID
print("Getting contractor profile...")
response = requests.get(
    f"{API_URL}/api/drivers/profile",
    headers={"Authorization": f"Bearer {TOKEN}"}
)

if response.status_code != 200:
    print(f"Error getting profile: {response.status_code}")
    exit(1)

contractor = response.json()["contractor"]
contractor_id = contractor["id"]
print(f"Contractor ID: {contractor_id}")

# Use admin endpoint to check all jobs for this driver
print(f"\nChecking all jobs...")
response = requests.get(
    f"{API_URL}/api/admin/jobs?driver_id={contractor_id}",
    headers={"Authorization": f"Bearer {TOKEN}"}
)

if response.status_code == 200:
    jobs = response.json().get("jobs", [])

    completed_jobs = [j for j in jobs if j["status"] == "completed"]

    print(f"\nTotal jobs: {len(jobs)}")
    print(f"Completed jobs: {len(completed_jobs)}")

    print(f"\nCompleted job details:")
    for job in completed_jobs:
        print(f"\n  Job {job['id'][:8]}...")
        print(f"    Address: {job.get('address', 'N/A')}")
        print(f"    Status: {job['status']}")
        print(f"    Price: ${job.get('total_price', 0)}")
        print(f"    Completed: {job.get('completed_at', 'N/A')}")
        print(f"    Payment Status: {job.get('payment_status', 'N/A')}")
else:
    print(f"Error: {response.status_code}")
    print(response.text)
