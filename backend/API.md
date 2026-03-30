# Umuve API Documentation

**Base URL**: `https://junkos-backend.onrender.com`
**Authentication**: Bearer token via `Authorization: Bearer <JWT>` header
**API Key**: `X-API-Key` header required on most endpoints
**Rate Limiting**: 100 requests/minute default; stricter limits on auth endpoints

---

## Authentication

All authenticated endpoints require `Authorization: Bearer <token>` header. Tokens are obtained via `/api/auth/*` endpoints.

### POST /api/auth/send-code
Send SMS verification code. **Rate limit: 5/min**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| phoneNumber | string | yes | Phone number to verify |

**Response**: `{ success, message }` (dev mode includes `code` field)

### POST /api/auth/verify-code
Verify SMS code and authenticate. **Rate limit: 10/min**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| phoneNumber | string | yes | Phone number |
| code | string | yes | 6-digit verification code |

**Response**: `{ token, user: { id, name, email, phoneNumber, role } }`

### POST /api/auth/signup
Create account with email/password.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| email | string | yes | Email address |
| password | string | yes | Password (min 8 chars) |
| name | string | no | Display name |

**Response**: `{ token, user }` (201)

### POST /api/auth/login
Email/password login.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| email | string | yes | Email address |
| password | string | yes | Password |

**Response**: `{ token, user }`

### POST /api/auth/apple
Apple Sign In. **Rate limit: 10/min**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| identityToken | string | yes | Apple identity token |
| authorizationCode | string | yes | Apple auth code |
| fullName | object | no | `{ givenName, familyName }` |

**Response**: `{ token, user, isNewUser }`

### POST /api/auth/forgot-password
Request password reset email.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| email | string | yes | Account email |

**Response**: `{ success, message }`

### GET /api/auth/me
Get current user profile. **Auth required.**

**Response**: `{ id, name, email, phoneNumber, role, ... }`

### PUT /api/auth/me
Update current user profile. **Auth required.**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | no | Display name |
| email | string | no | Email address |
| phoneNumber | string | no | Phone number |

### PUT /api/auth/change-password
Change password. **Auth required.**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| currentPassword | string | yes | Current password |
| newPassword | string | yes | New password |

### DELETE /api/auth/me
Delete account. **Auth required.**

### POST /api/auth/validate
Validate a JWT token.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| token | string | yes | JWT to validate |

### POST /api/auth/refresh
Refresh JWT token. **Auth required.**

**Response**: `{ token }`

### POST /api/auth/driver-signup
Register as a driver.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| email | string | yes | Email |
| password | string | yes | Password |
| name | string | yes | Full name |
| phone | string | no | Phone number |
| truck_type | string | no | Vehicle type |

### POST /api/auth/driver-login
Driver-specific login.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| email | string | yes | Email |
| password | string | yes | Password |

### POST /api/auth/upgrade_operator
Upgrade driver to operator role. **Auth required.**

---

## Bookings (Customer)

### POST /api/bookings/estimate
Get price estimate for a booking. **Rate limit: 10/min**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| items | array | yes | `[{ category, quantity }]` |
| address | string | yes | Pickup address |
| scheduledDate | string | no | ISO date |
| promoCode | string | no | Discount code |

**Response**: `{ success, estimate: { base_price, item_total, service_fee, surge_multiplier, total } }`

### POST /api/bookings/create
Create a new booking. **Auth required. Rate limit: 10/min**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| items | array | yes | `[{ category, quantity }]` |
| address | string | yes | Pickup address |
| lat | float | no | Latitude |
| lng | float | no | Longitude |
| scheduledDate | string | yes | ISO datetime |
| notes | string | no | Special instructions |
| promoCode | string | no | Promo code |
| paymentMethodId | string | no | Stripe payment method |

**Response**: `{ success, job, payment_intent }` (201)

### GET /api/bookings/available-slots
Get available scheduling slots.

**Response**: `{ success, slots: [...] }`

### POST /api/bookings/validate-address
Validate a pickup address.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| address | string | yes | Address to validate |

### POST /api/bookings/upload-photos
Upload booking reference photos. **Auth required.**

Multipart form-data with `files` field (max 5 files, 10MB each).

**Response**: `{ success, urls: [...] }`

---

## Jobs (Customer)

**Prefix**: `/api/jobs`

### GET /api/jobs
List customer's jobs with pagination. **Auth required.**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| status | string | - | Filter by status |
| page | int | 1 | Page number |
| per_page | int | 20 | Results per page |

**Response**: `{ success, jobs: [...], total, page, pages }`

### GET /api/jobs/lookup/:confirmation_code
Look up a job by confirmation code.

### GET /api/jobs/:job_id
Get job details. **Auth required.**

### POST /api/jobs/:job_id/cancel
Cancel a job. **Auth required.**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| reason | string | no | Cancellation reason |

### PUT /api/jobs/:job_id/reschedule
Reschedule a job. **Auth required.**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| scheduledDate | string | yes | New ISO datetime |

### GET /api/jobs/:job_id/proof
Get completion proof photos. **Auth required.**

### GET /api/jobs/:job_id/photos
Get all job photos (before/after). **Auth required.**

### POST /api/jobs/:job_id/photos/before
Upload before photos. **Auth required.** Multipart form-data.

### POST /api/jobs/:job_id/photos/after
Upload after photos. **Auth required.** Multipart form-data.

### POST /api/jobs/:job_id/volume/approve
Approve volume adjustment. **Auth required.**

### POST /api/jobs/:job_id/volume/decline
Decline volume adjustment. **Auth required.**

---

## Booking (V2)

**Prefix**: `/api/booking`

### POST /api/booking/estimate
V2 price estimate endpoint.

### POST /api/booking
Create booking (V2). **Auth required (optional for guest).**

### GET /api/booking/:job_id
Get booking details. **Auth required.**

---

## Drivers

**Prefix**: `/api/drivers`

### POST /api/drivers/register
Register as a contractor. **Auth required.**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| truck_type | string | yes | Vehicle type |
| operator_invite_code | string | no | Operator invite code |

### GET /api/drivers/profile
Get contractor profile. **Auth required.**

### PUT /api/drivers/availability
Toggle online/offline. **Auth required.**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| available | boolean | yes | Availability status |

### PUT /api/drivers/location
Update GPS location. **Auth required.**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| lat | float | yes | Latitude |
| lng | float | yes | Longitude |

### GET /api/drivers/jobs/available
Get nearby available jobs with pagination. **Auth required.**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| radius | float | 50 | Search radius in km |
| page | int | 1 | Page number |
| per_page | int | 20 | Results per page |

**Response**: `{ success, jobs: [...], total, page, pages }`

### GET /api/drivers/jobs/current
Get driver's current active job. **Auth required.**

### POST /api/drivers/jobs/:job_id/accept
Accept a job. **Auth required.**

### POST /api/drivers/jobs/:job_id/decline
Decline a job. **Auth required.**

### PUT /api/drivers/jobs/:job_id/status
Update job status. **Auth required.**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| status | string | yes | `en_route`, `arrived`, `started`, `completed` |

### POST /api/drivers/jobs/:job_id/proof
Upload completion proof. **Auth required.** Multipart form-data.

### POST /api/drivers/jobs/:job_id/volume
Submit volume adjustment. **Auth required.**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| actual_volume | float | yes | Measured volume |
| notes | string | no | Explanation |

---

## Driver Earnings

**Prefix**: `/api/driver`

### GET /api/driver/earnings
Get earnings summary. **Auth required.**

### GET /api/driver/earnings/history
Get earnings history. **Auth required.**

### GET /api/driver/profile
Get driver profile. **Auth required.**

### PUT /api/driver/profile
Update driver profile. **Auth required.**

### GET /api/driver/stats
Get driver statistics. **Auth required.**

---

## Driver Onboarding

### GET /api/drivers/onboarding/status
Get onboarding checklist and status. **Auth required.**

**Response**: `{ success, onboarding_status, checklist, can_submit, documents }`

### POST /api/drivers/onboarding/documents
Upload onboarding documents. **Auth required.** Multipart form-data.

Fields: `insurance` (file), `drivers_license` (file), `vehicle_registration` (file), `insurance_expiry` (ISO date), `license_expiry` (ISO date).

### POST /api/drivers/onboarding/submit
Submit documents for admin review. **Auth required.**

---

## Chat

**Prefix**: `/api/chat`

### GET /api/chat/:job_id/messages
Get chat messages for a job. **Auth required.** Cursor-based pagination.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| limit | int | 50 | Messages per page |
| before | string | - | Cursor (message ID) |

### POST /api/chat/:job_id/messages
Send a message. **Auth required.**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| message | string | yes | Message text |

### PUT /api/chat/:job_id/messages/read
Mark messages as read. **Auth required.**

### GET /api/chat/:job_id/messages/unread-count
Get unread message count. **Auth required.**

---

## Ratings

**Prefix**: `/api/ratings`

### POST /api/ratings
Submit a rating. **Auth required.**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| job_id | string | yes | Job ID |
| stars | int | yes | 1-5 rating |
| comment | string | no | Optional comment |

### GET /api/ratings/user/:target_user_id
Get ratings for a user. Paginated.

### GET /api/ratings/contractor/:contractor_id
Get ratings for a contractor. Paginated.

### GET /api/ratings/job/:job_id
Get rating for a specific job.

---

## Reviews

**Prefix**: `/api/reviews`

### POST /api/reviews
Submit a review. **Auth required.**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| job_id | string | yes | Job ID |
| rating | int | yes | 1-5 stars |
| comment | string | no | Review text |

### GET /api/reviews/job/:job_id
Get review for a job.

### GET /api/reviews/contractor/:contractor_id
Get reviews for a contractor. Paginated.

---

## Payments

**Prefix**: `/api/payments`

### POST /api/payments/create-intent
Create Stripe PaymentIntent. **Auth required.**

### POST /api/payments/confirm
Confirm payment. **Auth required.**

### POST /api/payments/create-intent-simple
Simplified payment intent creation. **Auth required.**

### POST /api/payments/confirm-simple
Simplified payment confirmation. **Auth required.**

### POST /api/payments/payout/:job_id
Process driver payout for a job. **Auth required (admin).**

### GET /api/payments/earnings
Get driver earnings summary. **Auth required.**

### GET /api/payments/earnings/history
Get driver earnings history. **Auth required.**

### POST /api/payments/connect/create-account
Create Stripe Connect account. **Auth required.**

### POST /api/payments/connect/account-link
Generate Stripe Connect onboarding link. **Auth required.**

### GET /api/payments/connect/status
Check Stripe Connect account status. **Auth required.**

### GET /api/payments/connect/return
Stripe Connect return URL handler.

### GET /api/payments/connect/refresh
Stripe Connect refresh URL handler.

### POST /api/webhooks/stripe
Stripe webhook handler. Signature verified.

---

## Pricing

**Prefix**: `/api/pricing`

### POST /api/pricing/estimate
Get detailed price estimate.

### GET /api/pricing/rules
Get active pricing rules.

### GET /api/pricing/surge
Get current surge multiplier.

### GET /api/pricing/categories
Get item categories with base prices.

### GET /api/pricing/config
Get full pricing configuration.

---

## Promo Codes

### POST /api/promos/validate
Validate a promo code.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| code | string | yes | Promo code |

---

## Recurring Bookings

**Prefix**: `/api/recurring`

### POST /api/recurring
Create recurring booking. **Auth required.**

### GET /api/recurring
List user's recurring bookings. **Auth required.**

### GET /api/recurring/:recurring_id
Get recurring booking details. **Auth required.**

### PUT /api/recurring/:recurring_id
Update recurring booking. **Auth required.**

### DELETE /api/recurring/:recurring_id
Cancel recurring booking. **Auth required.**

### POST /api/recurring/generate-next
Generate next scheduled job. **Auth required.**

---

## Referrals

**Prefix**: `/api/referrals`

### GET /api/referrals/my-code
Get user's referral code. **Auth required.**

### GET /api/referrals/stats
Get referral stats. **Auth required.**

### POST /api/referrals/validate/:code
Validate a referral code.

---

## Tracking

**Prefix**: `/api/tracking`

### GET /api/tracking/:job_id
Get job tracking status.

### GET /api/tracking/:job_id/driver-location
Get driver's live location for a job.

---

## Push Notifications

**Prefix**: `/api/push`

### POST /api/push/register-token
Register push notification token. **Auth required.**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| token | string | yes | Device push token |
| platform | string | yes | `ios` or `android` |

### DELETE /api/push/unregister-token
Unregister push token. **Auth required.**

### GET /api/push/test
Send test notification. **Auth required.**

---

## Service Area

**Prefix**: `/api/service-area`

### GET /api/service-area
Get supported service areas.

### POST /api/service-area/check
Check if address is in service area.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| lat | float | yes | Latitude |
| lng | float | yes | Longitude |

---

## Support

### POST /api/support/message
Submit support message.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | yes | Sender name |
| email | string | yes | Sender email |
| message | string | yes | Support message |

---

## File Upload

### POST /api/upload/photos
Upload photos. **Auth required.** Multipart form-data.

`files` field, max 10 files, 10MB each. Allowed: jpg, jpeg, png, webp.

**Response**: `{ success, urls: [...] }`

### GET /uploads/:filename
Serve uploaded file (public).

---

## AI Analysis

### POST /api/ai/analyze-photos
AI-powered photo analysis for volume estimation. **Auth required.**

---

## Operator Portal

**Prefix**: `/api/operator`

### GET /api/operator/dashboard
Operator dashboard stats. **Auth required (operator).**

### GET /api/operator/fleet
List fleet contractors. **Auth required (operator).** Paginated.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| page | int | 1 | Page number |
| per_page | int | 20 | Results per page |

### POST /api/operator/invites
Create fleet invite code. **Auth required (operator).**

### GET /api/operator/invites
List invite codes. **Auth required (operator).** Paginated.

### DELETE /api/operator/invites/:invite_id
Revoke invite code. **Auth required (operator).**

### GET /api/operator/jobs
List operator's fleet jobs. **Auth required (operator).** Paginated.

### PUT /api/operator/jobs/:job_id/delegate
Delegate job to fleet member. **Auth required (operator).**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| contractor_id | string | yes | Target contractor |

### GET /api/operator/notifications
Get operator notifications. **Auth required (operator).**

### PUT /api/operator/notifications/:notification_id/read
Mark notification as read. **Auth required (operator).**

### PUT /api/operator/notifications/read-all
Mark all notifications as read. **Auth required (operator).**

### GET /api/operator/earnings
Operator earnings with fleet breakdown. **Auth required (operator).**

### GET /api/operator/analytics
Operator analytics. **Auth required (operator).**

---

## Operator Applications

### POST /api/operator-applications
Submit operator application.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| business_name | string | yes | Business name |
| contact_name | string | yes | Contact person |
| email | string | yes | Email address |
| phone | string | yes | Phone number |
| fleet_size | int | yes | Number of trucks |
| service_area | string | yes | Desired service area |

---

## Admin

**Prefix**: `/api/admin` (all require admin role)

### GET /api/admin/dashboard
Dashboard summary stats.

### GET /api/admin/contractors
List all contractors. Paginated with search.

### PUT /api/admin/contractors/:contractor_id/approve
Approve a contractor.

### PUT /api/admin/contractors/:contractor_id/suspend
Suspend a contractor.

### PUT /api/admin/contractors/:contractor_id/promote-operator
Promote contractor to operator.

### GET /api/admin/jobs
List all jobs with search and date filtering.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| status | string | - | Filter by status |
| search | string | - | Search name/email/address/ID/code |
| date_from | string | - | ISO date start |
| date_to | string | - | ISO date end |
| page | int | 1 | Page number |
| per_page | int | 20 | Results per page |

### GET /api/admin/jobs/:job_id
Get full job details.

### PUT /api/admin/jobs/:job_id/assign
Assign job to contractor.

### PUT /api/admin/jobs/:job_id/cancel
Admin cancel a job.

### GET /api/admin/customers
List all customers. Paginated with search.

### GET /api/admin/analytics
Full analytics dashboard.

**Response**: `{ jobs_by_day, revenue_by_week, jobs_by_status, top_contractors, busiest_hours }`

### GET /api/admin/map-data
Get map data for active jobs and drivers.

### GET /api/admin/notifications
Get admin notifications.

### PUT /api/admin/notifications/:notification_id/read
Mark notification as read.

### PUT /api/admin/notifications/read-all
Mark all notifications as read.

### GET /api/admin/pricing/rules
Get pricing rules.

### PUT /api/admin/pricing/rules
Update pricing rules.

### GET /api/admin/pricing/surge
Get surge pricing status.

### POST /api/admin/pricing/surge
Set surge pricing.

### GET /api/admin/pricing/config
Get full pricing config.

### PUT /api/admin/pricing/config
Update pricing config.

### GET /api/admin/payments
List all payments. Paginated.

### GET /api/admin/reviews
List all reviews. Paginated.

### POST /api/admin/sms/send
Send SMS to user.

### GET /api/admin/onboarding/applications
List onboarding applications. Paginated.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| status | string | - | Filter by onboarding status |
| page | int | 1 | Page number |
| per_page | int | 20 | Results per page |

### PUT /api/admin/onboarding/:contractor_id/review
Approve or reject onboarding application.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| action | string | yes | `approve` or `reject` |
| rejection_reason | string | conditional | Required if rejecting |

### GET /api/admin/operator-applications
List operator applications. Paginated.

### PUT /api/admin/operator-applications/:application_id/review
Review operator application.

### GET /api/admin/support-messages
List support messages. Paginated.

### PUT /api/admin/support-messages/:message_id/resolve
Resolve support message.

### GET /api/admin/promos
List promo codes. Paginated.

### POST /api/admin/promos
Create promo code.

### PUT /api/admin/promos/:promo_id
Update promo code.

### DELETE /api/admin/promos/:promo_id
Delete promo code.

---

## Utility

### GET /api/health
Health check endpoint.

**Response**: `{ status: "ok", timestamp }`

### GET /api/services
List available service categories.

---

## Common Response Patterns

**Success**: `{ success: true, ... }`
**Error**: `{ error: "message" }` with appropriate HTTP status
**Pagination**: `{ success: true, items: [...], total: N, page: N, pages: N }`

## HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad request / validation error |
| 401 | Unauthorized (missing/invalid token) |
| 403 | Forbidden (insufficient role) |
| 404 | Not found |
| 409 | Conflict (duplicate, invalid state) |
| 429 | Rate limited |
| 500 | Server error |
