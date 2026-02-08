# JunkOS Platform Design

## Overview

JunkOS is an on-demand junk removal marketplace — "Uber for junk removal." Independent contractors with trucks sign up, customers book pickups, and JunkOS facilitates the transaction, taking a commission + service fee.

**Service area:** Palm Beach & Broward County, South Florida (expandable).

## Revenue Model

- **Commission:** ~20% per job from contractor payout
- **Service fee:** Customer pays a booking/service fee on top of job price (e.g. $4.99 or 8%)
- Contractor receives full job price minus commission

## Platform Components

| Component | Tech | Purpose |
|-----------|------|---------|
| Customer Web App | Next.js + shadcn/ui | Web booking, tracking, payments, ratings |
| Customer iOS App | SwiftUI | Native booking, live tracking, payments, ratings |
| Driver iOS App | SwiftUI | Accept jobs, navigate, complete, earnings |
| Operator Dashboard | Next.js (auth-gated) | Manage contractors, jobs, analytics, payouts |
| Backend API | Flask (existing, extended) | Core business logic |
| Real-time Service | WebSockets (Socket.IO) | Live GPS, status updates |

**URLs:**
- `junkos.com` — Landing page (live)
- `app.junkos.com` — Customer web app + operator dashboard
- App Store — Customer app + Driver app

**iOS apps:** One Xcode workspace, two app targets, shared Swift package for networking, models, auth, and map components.

---

## Customer Experience

### Public Pages (no auth)
- `/book` — 6-step booking flow
- `/track/:jobId` — Live tracking page (link sent via SMS)

### Authenticated Pages (optional account)
- `/dashboard` — Past jobs, active jobs, saved addresses
- `/jobs/:id` — Job detail, status, photos, receipt, rate crew
- `/settings` — Profile, payment methods, notifications

### Booking Flow (6 Steps)
1. **Address** — Google Maps autocomplete + service area validation
2. **Photos** — Drag-drop upload, preview grid
3. **Items** — Category picker with per-item pricing, volume estimate
4. **Schedule** — Available time slots based on contractor availability in area
5. **Estimate** — Hybrid price breakdown (items + volume + surge + service fee)
6. **Payment** — Stripe checkout, pay upfront, saved cards for returning customers

### After Booking
- Customer gets SMS with tracking link
- Live map shows assigned contractor's GPS location
- Status updates: Confirmed → Crew assigned → En route → Arriving → In progress → Complete
- Post-job: rate contractor (1-5 stars), tip option, receipt via email

---

## Driver/Contractor Experience

### Onboarding (one-time)
- Sign up: name, phone, email
- Upload: driver's license, proof of insurance, truck photos
- Bank account for payouts (Stripe Connect onboarding)
- Background check consent
- Admin approves → account goes live

### Main Screens

| Screen | Purpose |
|--------|---------|
| Job Feed | Available jobs nearby, sorted by distance. See address area, item list, estimated payout, time window. Accept or decline. |
| Active Job | Turn-by-turn navigation. Status buttons: En route → Arrived → Started → Complete. Upload before/after photos. |
| Earnings | Today's earnings, weekly summary, payout history. Commission breakdown per job. |
| Schedule | Set availability hours. Toggle online/offline. |
| Profile | Ratings, completed jobs count, documents, truck info. |

### Job Lifecycle (Driver Perspective)
1. Driver goes online → receives push notification for nearby job
2. Sees job details: area, items, estimated payout, time window
3. Accepts → gets full address + customer contact
4. Taps "En route" → customer sees live tracking
5. Arrives → taps "Arrived" → customer notified
6. Loads junk → takes before/after photos
7. If actual load differs from estimate → requests price adjustment (customer approves in app)
8. Taps "Complete" → customer charged, payout queued
9. Customer rates driver, driver can rate customer

---

## Operator Dashboard

Accessible at `app.junkos.com/admin`. Web-only.

| Section | Purpose |
|---------|---------|
| Live Map | Real-time view of all active drivers and jobs. See who's online, en route, or idle. |
| Jobs Board | All jobs: pending, active, completed, cancelled. Filter by date, status, area, contractor. |
| Contractors | Approve new applications, view ratings, documents, earnings, suspend accounts. |
| Customers | Customer list, job history, flagged accounts, support tickets. |
| Pricing Controls | Base item prices, volume multipliers, service fee %, commission %. Surge zones and multipliers. |
| Payouts | Contractor payout schedule, pending/completed payouts. Stripe Connect. |
| Analytics | Jobs per day/week/month, revenue, avg job value, avg rating, busiest areas/times, contractor leaderboard. |
| Settings | Service area boundaries (draw on map), business hours, notification templates, team access. |

### Key Operator Actions
- Approve/reject contractor applications
- Manually assign a job to a specific contractor
- Override pricing on a job
- Issue refunds
- Set surge pricing zones
- Suspend a contractor or customer
- Export reports

---

## Pricing Engine

**Hybrid model:**
- **Item-based baseline** — Each item category has a base price (e.g. couch $75, fridge $100)
- **Volume adjustment** — Total adjusted by estimated truck load fraction (1/8, 1/4, 1/2, full)
- **Dynamic surge** — Multiplier based on demand in area/time (e.g. 1.2x during peak Saturday morning)
- **Service fee** — Customer pays flat fee or percentage on top

**Price breakdown shown to customer:**
```
Items:        $185.00
Volume adj:   -$20.00
Subtotal:     $165.00
Service fee:    $8.25
Surge (1.2x):  $33.00
Total:        $206.25
```

---

## Data Model

### Users
- id, email, phone, name, role (customer/driver/admin)
- avatar, created_at, status (active/suspended)
- stripe_customer_id / stripe_connect_id

### Jobs
- id, customer_id, driver_id, status
- address, lat, lng, photos[]
- items[], volume_estimate
- scheduled_at, started_at, completed_at
- price_breakdown (items, volume, surge, service_fee)
- total_price, driver_payout, platform_commission
- before_photos[], after_photos[]

### Contractors (extends Users)
- license_url, insurance_url, truck_photos[]
- truck_type, truck_capacity
- bank_account (Stripe Connect)
- is_online, current_lat, current_lng
- avg_rating, total_jobs, approval_status
- availability_schedule

### Ratings
- job_id, from_user_id, to_user_id
- stars (1-5), comment, created_at

### Payments
- job_id, stripe_payment_intent_id
- amount, service_fee, commission
- driver_payout_amount, payout_status
- tip_amount

### Pricing Rules
- item_type, base_price
- volume_multipliers
- surge_zones[], surge_multiplier
- service_fee_percent, commission_percent

---

## API Structure

### REST Endpoints
- `/api/auth/*` — Login, signup, token refresh
- `/api/jobs/*` — CRUD, status updates, assignment
- `/api/drivers/*` — Onboarding, availability, location updates
- `/api/payments/*` — Charge, payout, refund
- `/api/pricing/*` — Estimate, surge rules
- `/api/ratings/*` — Submit, fetch
- `/api/admin/*` — Dashboard data, contractor approval, analytics

### WebSocket Events
- `driver:location` — Driver streams GPS every 3-5 seconds
- `job:status` — Status changes broadcast to customer
- `job:new` — New job alert broadcast to nearby online drivers
- Redis stores live driver locations for fast geo queries

---

## Tech Stack

### Frontend (Web)
- Next.js 14 (App Router) — Framework, SSR, API routes
- shadcn/ui + Tailwind — UI components, styling
- Mapbox GL JS — Live tracking map, surge zone drawing
- Stripe.js — Payment form, saved cards
- Socket.IO Client — Real-time updates
- Zustand — State management
- React Query — API data fetching/caching

### iOS Apps (Customer + Driver)
- SwiftUI — UI framework
- MapKit — Live tracking, navigation
- Combine — Reactive data flow
- Stripe iOS SDK — Payments (customer app)
- CoreLocation — GPS streaming (driver app)
- URLSession + WebSocket — API + real-time
- Push Notifications (APNs) — Job alerts, status updates

### Backend
- Flask (existing) — REST API
- Socket.IO (Python) — WebSocket server
- PostgreSQL — Primary database
- Redis — Location cache, job queue, sessions
- Stripe Connect — Marketplace payments + payouts
- AWS S3 — Photo storage
- Celery — Background tasks (payouts, notifications, surge calc)

### Infrastructure
- Vercel — Next.js web app hosting
- Render or Railway — Backend API + WebSocket server
- Supabase or RDS — Managed PostgreSQL
- Upstash — Managed Redis
- AWS S3 — File storage
- Apple Developer — App Store distribution

---

## Build Phases

### Phase 1 — Foundation (Weeks 1-3)
- Set up Next.js project with shadcn/ui, auth (NextAuth or Clerk)
- Extend Flask backend: new data models, Stripe Connect, WebSocket support
- PostgreSQL + Redis setup
- Shared Swift package (networking, models, auth) in Xcode workspace
- API endpoints: auth, jobs CRUD, basic pricing

### Phase 2 — Customer Experience (Weeks 4-6)
- Next.js: booking flow (rebuild from React prototype with new design)
- Next.js: live tracking page with Mapbox
- Customer iOS app: booking flow, tracking, payment
- Backend: photo upload to S3, hybrid pricing engine, job assignment logic

### Phase 3 — Driver Experience (Weeks 7-9)
- Driver iOS app: onboarding, job feed, accept/decline
- Driver iOS app: active job flow, navigation, status updates, photos
- Backend: real-time location streaming, nearby driver queries (Redis geo)
- Push notifications (APNs) for job alerts

### Phase 4 — Operator Dashboard (Weeks 10-11)
- Live map with all drivers/jobs
- Jobs board, contractor management, customer management
- Pricing controls, surge zone editor
- Payout management via Stripe Connect dashboard
- Analytics charts

### Phase 5 — Polish & Launch (Weeks 12-13)
- Ratings system (both directions)
- Email/SMS notifications (job confirmed, en route, complete, receipt)
- Edge cases: cancellations, refunds, disputes, price adjustments
- Testing across all platforms
- App Store submission
- Deploy web app to production

---

## Existing Assets to Leverage

| Asset | Status | Reuse Plan |
|-------|--------|------------|
| Landing page | Live at Vercel | Add "Book Now" link to app.junkos.com |
| React booking flow | Working prototype | Reference for rebuilding in Next.js |
| Flask backend | Partial (auth, bookings, payments) | Extend with new models and WebSocket |
| JunkOS-Clean iOS | SwiftUI scaffolded (auth, views, models) | Becomes the Xcode workspace for both apps |
| Stripe integration | Basic in prototypes | Upgrade to Stripe Connect for marketplace |
