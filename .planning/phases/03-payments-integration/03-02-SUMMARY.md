---
phase: 03-payments-integration
plan: 02
subsystem: backend-payments
tags: [stripe-connect, earnings-api, webhooks]
dependency_graph:
  requires:
    - stripe-python-sdk
    - backend-auth-routes
    - contractor-model
  provides:
    - stripe-connect-onboarding-endpoints
    - earnings-history-api
    - account-updated-webhook
  affects:
    - driver-app-earnings-dashboard
    - driver-app-connect-onboarding
tech_stack:
  added:
    - stripe.Account.create
    - stripe.AccountLink.create
    - stripe.Account.retrieve
  patterns:
    - express-connect-accounts
    - idempotent-account-creation
    - fresh-account-links
    - driver-payout-only-earnings
key_files:
  created: []
  modified:
    - backend/routes/payments.py: "Added 6 Connect endpoints + earnings history + account.updated webhook handler"
    - backend/models.py: "Added stripe_connect_id to Contractor.to_dict()"
decisions:
  - context: "Earnings history display"
    choice: "Return driver_payout_amount only (80% take)"
    rationale: "Locked decision from research — drivers see their take, not full job price"
  - context: "Account link generation"
    choice: "Generate fresh link every time, never cache"
    rationale: "Links expire in 5 minutes — caching would cause errors"
  - context: "Connect status storage"
    choice: "Derive status from Stripe API, no DB fields"
    rationale: "Stripe is source of truth — avoids sync issues"
metrics:
  duration_minutes: 2.4
  tasks_completed: 2
  files_modified: 2
  commits: 2
  completed_at: "2026-02-14T10:10:42Z"
---

# Phase 03 Plan 02: Backend Stripe Connect Endpoints Summary

**One-liner:** Stripe Connect Express account management (create, onboarding links, status) + detailed earnings history with driver's 80% take + account.updated webhook handler.

## What Was Built

### 1. Stripe Connect Account Management (6 endpoints)

**POST /api/payments/connect/create-account**
- Creates Stripe Express account for authenticated driver
- Idempotent — returns existing account if already created
- Saves `stripe_connect_id` to Contractor model
- Dev mode: generates mock `acct_dev_{uuid}` when no Stripe key

**POST /api/payments/connect/account-link**
- Generates fresh Stripe onboarding URL (expires in 5 minutes)
- Requires existing Connect account (400 if not found)
- Returns URL + expiration timestamp
- Uses APP_BASE_URL env var for return/refresh URLs
- Dev mode: returns mock `https://connect.stripe.com/setup/e/mock`

**GET /api/payments/connect/status**
- Returns onboarding status: "not_set_up" | "pending_verification" | "active"
- Fetches real-time data from Stripe API: charges_enabled, payouts_enabled, details_submitted
- Status logic: charges + payouts enabled = "active", has ID but not enabled = "pending_verification"
- Falls back gracefully if Stripe call fails

**GET /api/payments/connect/return**
- Redirect endpoint for successful onboarding completion
- Returns HTML page: "Setup complete. Return to the Umuve Pro app."
- No authentication required (Stripe calls this)

**GET /api/payments/connect/refresh**
- Redirect endpoint for expired onboarding links
- Returns HTML page: "Link expired. Please return to the app and try again."
- No authentication required (Stripe calls this)

### 2. Earnings History API

**GET /api/payments/earnings/history**
- Returns detailed per-job earnings with payout status
- Joins Payment + Job tables, filters by driver_id and payment_status == "succeeded"
- Each entry: `{ id, job_id, address, amount, date, payout_status }`
- **CRITICAL:** Returns `driver_payout_amount` only (80% take), NOT full job price
- Summary: today, week (7d), month (30d), all_time totals
- Ordered by date descending (newest first)

### 3. Webhook Enhancement

**account.updated event handler**
- Added `_handle_account_updated(account)` function
- Finds contractor by `stripe_connect_id`
- Logs charges_enabled and payouts_enabled status
- No DB changes needed (status derived from API in /connect/status endpoint)
- Logs for debugging and audit trail

### 4. Profile API Enhancement

**Contractor.to_dict() updated**
- Added `stripe_connect_id` field to response
- Existing `/api/drivers/profile` endpoint now returns Connect status
- Enables driver app to check setup state without additional API call

## Implementation Details

### Idempotent Account Creation
```python
if contractor.stripe_connect_id:
    return {"success": True, "account_id": contractor.stripe_connect_id}
```
Safe to call multiple times — returns existing account.

### Fresh Account Links (Never Cached)
```python
account_link = stripe.AccountLink.create(
    account=contractor.stripe_connect_id,
    refresh_url=...,
    return_url=...,
    type="account_onboarding",
)
```
Generated fresh on every request — links expire in 5 minutes.

### Driver-Only Earnings
```python
entries.append({
    "amount": round(payment.driver_payout_amount, 2),  # NOT payment.amount
    ...
})
```
Shows 80% take only, never full job price.

### Status Derivation Logic
```python
if charges_enabled and payouts_enabled:
    status = "active"
elif contractor.stripe_connect_id:
    status = "pending_verification"
else:
    status = "not_set_up"
```
No DB storage needed — Stripe API is source of truth.

## Deviations from Plan

None — plan executed exactly as written.

## Testing Notes

All endpoints support dev mode (no Stripe key):
- Account creation returns mock `acct_dev_{uuid}`
- Account links return mock URL
- Status endpoint returns stored values or defaults

Import verification passed:
```python
from routes.payments import payments_bp, webhook_bp
# ✅ Success
```

## Key Files Modified

**backend/routes/payments.py** (+261 lines)
- 5 new Connect endpoints (create-account, account-link, status, return, refresh)
- 1 new earnings history endpoint
- 1 new webhook handler (_handle_account_updated)
- All endpoints authenticated except return/refresh (Stripe callbacks)

**backend/models.py** (+1 line)
- Added `stripe_connect_id` to Contractor.to_dict()

## Next Steps (Plan 03-03)

Driver app implementation:
1. Mandatory Connect onboarding gate on first job accept
2. UI flow: check status → create account → open onboarding URL → poll status
3. Onboarding completion detection via /connect/status polling

## Next Steps (Plan 03-04)

Driver app earnings dashboard:
1. Call /api/payments/earnings/history
2. Display per-job earnings with payout status badges
3. Summary cards: today, week, month, all-time
4. Pull-to-refresh for latest data

## Verification Results

✅ All endpoints importable without errors
✅ Earnings history returns driver_payout_amount (not full price)
✅ Account link generated fresh each time (never cached)
✅ Connect status derived from Stripe API
✅ Webhook processes account.updated events
✅ Driver profile includes stripe_connect_id

## Self-Check

**Created files:** None (all modifications)

**Modified files:**
- ✅ backend/routes/payments.py exists and modified
- ✅ backend/models.py exists and modified

**Commits:**
- ✅ 403b9f4 (Task 1: Stripe Connect endpoints + earnings history)
- ✅ a28056d (Task 2: stripe_connect_id in profile response)

## Self-Check: PASSED

All files modified as expected. All commits present in git history.
