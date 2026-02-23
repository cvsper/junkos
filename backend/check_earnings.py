#!/usr/bin/env python3
"""Check earnings endpoint"""
import requests

API_URL = "https://junkos-backend.onrender.com"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiYWRhODlhMWE5YWVjMDBkZTI3YzY4ZWExODFlMmYzZjQiLCJleHAiOjE3NzQ0MDUxMjV9.bpc0C-uH6xUo9I57VDtS-t8LpDNT4CvYPPrpZLHpwfM"

print("Checking earnings history...")
response = requests.get(
    f"{API_URL}/api/drivers/earnings/history",
    headers={"Authorization": f"Bearer {TOKEN}"}
)

print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"Success: {data.get('success')}")
    print(f"Earnings count: {len(data.get('earnings', []))}")

    # Show first few earnings
    for i, earning in enumerate(data.get('earnings', [])[:3]):
        print(f"\nEarning {i+1}:")
        print(f"  Amount: ${earning.get('driver_payout_amount', 0)}")
        print(f"  Job ID: {earning.get('job_id')}")
        print(f"  Date: {earning.get('completed_at')}")
else:
    print(f"Error: {response.text}")

print("\n\nChecking earnings summary...")
response = requests.get(
    f"{API_URL}/api/drivers/earnings/summary",
    headers={"Authorization": f"Bearer {TOKEN}"}
)

print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"Success: {data.get('success')}")
    summary = data.get('summary', {})
    print(f"Today: ${summary.get('today', 0)}")
    print(f"This week: ${summary.get('this_week', 0)}")
    print(f"This month: ${summary.get('this_month', 0)}")
    print(f"All time: ${summary.get('all_time', 0)}")
else:
    print(f"Error: {response.text}")
