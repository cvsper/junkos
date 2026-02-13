# External Integrations

**Analysis Date:** 2026-02-13

## APIs & External Services

**Payment Processing:**
- Stripe - Payment collection and Connect payouts
  - SDK/Client: `stripe` (Python 5.5.0), `@stripe/stripe-js` (JavaScript 3.0.0), `@stripe/react-stripe-js` (React 2.7.0)
  - Auth: `STRIPE_SECRET_KEY` (backend API key)
  - Webhook: `STRIPE_WEBHOOK_SECRET` for signature verification
  - Handled in: `backend/routes/payments.py`
  - Flow: Customer payment intent → Platform commission + service fee → Driver payout via Stripe Connect

**SMS & Notifications:**
- Twilio - SMS delivery for verification codes, booking confirmations, job updates
  - SDK/Client: `twilio` (Python 9.0.4)
  - Auth: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`
  - Sender: `TWILIO_FROM_NUMBER` or `TWILIO_PHONE_NUMBER`
  - Handled in: `backend/sms_service.py`, `backend/notifications.py`
  - Features: Phone number formatting (US +1 prefix), graceful fallback when unconfigured

**Push Notifications:**
- Apple APNs (HTTP/2 token-based) - iOS push notifications
  - SDK/Client: httpx with HTTP/2 support (`httpx[http2]` 0.27.0), PyJWT for token generation
  - Auth: `.p8` private key file + JWT token (ES256 signed)
  - Config: `APNS_KEY_ID`, `APNS_TEAM_ID`, `APNS_AUTH_KEY_PATH`, `APNS_BUNDLE_ID`
  - Handled in: `backend/push_notifications.py`
  - Features: Automatic token caching/refresh (50-min interval), invalid token cleanup

**Email Delivery:**
- Resend (preferred) - Primary email provider
  - SDK/Client: `resend` (Python 2.5.1)
  - Auth: `RESEND_API_KEY`
- SendGrid (legacy fallback) - Secondary email provider for backwards compatibility
  - SDK/Client: `sendgrid` (Python 6.11.0)
  - Auth: `SENDGRID_API_KEY`
  - Handled in: `backend/notifications.py`
  - Flow: Asynchronous background thread sending to prevent request blocking
  - Email types: Booking confirmation, job assignment, pickup reminders, payment receipts, password reset

**Geolocation & Maps:**
- Mapbox - Map rendering and spatial queries
  - SDK/Client: `mapbox-gl` (JavaScript 3.5.0)
  - Usage: Real-time driver location map, service area visualization (admin/operator portals)
- Geopy - Coordinate-based distance calculations
  - SDK/Client: `geopy` (Python 2.4.1)
  - Usage: Driver radius search, haversine distance calculations for geofencing
  - Implemented in: `backend/geofencing.py` (South Florida tri-county service area polygon)

**Analytics:**
- PostHog - Product analytics and event tracking
  - SDK/Client: `posthog-js` (JavaScript 1.345.5)
  - Auth: `NEXT_PUBLIC_POSTHOG_KEY` (client-side key)
  - Config: `NEXT_PUBLIC_POSTHOG_HOST` (default: `https://us.i.posthog.com`)
  - Handled in: `platform/src/lib/posthog.ts`
  - Features: Page views, page leaves, custom event tracking, user identification

**Error Monitoring:**
- Sentry - Error tracking and performance monitoring
  - SDK/Client: `sentry-sdk[flask]` (Python 2.14.0)
  - Auth: `SENTRY_DSN` (optional)
  - Handled in: `backend/server.py`
  - Integration: FlaskIntegration, 10% trace sample rate
  - Only active when SENTRY_DSN environment variable is set

## Data Storage

**Databases:**
- PostgreSQL (primary, production)
  - Connection: `DATABASE_URL` environment variable (automatically converted from `postgres://` to `postgresql://` for SQLAlchemy 2.x compatibility)
  - Client: SQLAlchemy 2.0.36 (Python ORM), psycopg2-binary 2.9.9
  - Host: Render platform
  - Fallback: SQLite `umuve.db` for local development
  - Models: `backend/models.py`
  - Migrations: `backend/migrations/` (Flask-Migrate compatible)

**File Storage:**
- Local filesystem - Job photos, documents (development/small deployments)
  - Path: `backend/uploads/`
  - Endpoint: `GET /uploads/<filename>`
  - Max file size: 10 MB per file, 10 files per request
  - Allowed types: jpg, jpeg, png, webp
  - Handled in: `backend/routes/upload.py`
- AWS S3 (production-ready, not yet integrated)
  - SDK/Client: `boto3` (1.34.14)
  - Auth: AWS credentials (can be added via environment variables)
  - Note: Dependency present but integration not actively used

**Caching & Session Store:**
- Redis (optional, production)
  - SDK/Client: `redis` (Python 5.0.1)
  - Usage: Distributed rate limiting, session management
  - Config: `RATELIMIT_STORAGE_URI` (if empty, falls back to in-memory rate limiting)
  - Note: Configured but not required for basic functionality

**Task Queue:**
- Celery with broker/backend (infrastructure available, optional)
  - SDK/Client: `celery` (5.3.6)
  - Note: Dependency present but not actively integrated; background tasks currently use threading

## Authentication & Identity

**Auth Provider:**
- Custom JWT-based authentication (self-hosted)
  - Implementation: `backend/auth_routes.py`
  - Libraries: PyJWT 2.10.1, Flask-JWT-Extended 4.6.0
  - Token validation via `Authorization: Bearer <token>` header
  - Token expiry: 30 days
  - Refresh: Not implemented (stateless tokens)

**Sign-in Methods:**
- Phone + SMS verification code (primary customer flow)
  - Verification codes stored in-memory (development) or can use Redis (production)
  - Code format: 6-digit numeric, 10-minute expiry
- Email + password (admin/operator login)
  - Password hashing: Werkzeug `generate_password_hash` / `check_password_hash`
- Apple Sign In (iOS apps)
  - SDK: Native Swift integration (AuthenticationServices)
  - Token exchange happens in `backend/auth_routes.py`
  - User creation with `apple_id` field stored in User model

**User Roles:**
- `customer` - Booking customers
- `driver` / `contractor` - Service providers
- `admin` - Platform administrators
- `operator` - Support/dispatch operators

## Monitoring & Observability

**Error Tracking:**
- Sentry (optional)
  - When configured, captures all unhandled exceptions
  - Dashboard: Post-event sampled at 10% trace rate
  - Not critical; app logs errors to stdout/stderr if Sentry unconfigured

**Logs:**
- Standard Python logging (`logging` module)
  - Output: stdout/stderr (captured by Render/deployment platform)
  - Logger names: Scoped by module (e.g., `umuve.startup`, `umuve.auth`)
  - Startup checks: Critical env var validation at `backend/server.py` lines 34-67

## CI/CD & Deployment

**Hosting:**
- Render - Backend Flask server (Python 3.12)
  - URL: `https://umuve-backend.onrender.com`
  - Deployment: Git-based (pushes to Render trigger automatic build)
  - Env vars: All critical/recommended vars must be set in Render dashboard
- Vercel - Frontend platforms
  - Landing page: `https://landing-page-premium-five.vercel.app` → `https://goumuve.com`
  - Platform (admin/operator): `https://platform-olive-nu.vercel.app` → `https://app.goumuve.com`
  - Customer portal: Deployed separately via Vercel
  - Cache headers: `max-age=60, must-revalidate` for CSS/JS (prevents stale asset issues)
- iOS App Store / TestFlight - Native apps
  - Customer app: Bundle ID `com.goumuve.app`, Xcode project `JunkOS-Clean/`
  - Driver app: Bundle ID `com.goumuve.pro`, Xcode project `JunkOS-Driver/`

**CI Pipeline:**
- GitHub Actions (inferred from git-based deployments)
- Render auto-deploys on `main` branch push
- Vercel auto-deploys on push to main (platform, landing page)
- Manual Xcode builds and TestFlight distribution for iOS

## Environment Configuration

**Critical env vars (production enforcement):**
- `JWT_SECRET` - JWT signing secret
- `SECRET_KEY` - Flask session secret
- `DATABASE_URL` - PostgreSQL connection string

**Recommended env vars (warnings if missing in production):**
- `ADMIN_SEED_SECRET` - Admin account creation secret
- `STRIPE_SECRET_KEY` - Stripe API key
- `STRIPE_WEBHOOK_SECRET` - Stripe webhook signature key
- `CORS_ORIGINS` - Comma-separated domain allowlist
- `SENTRY_DSN` - Error monitoring endpoint

**Integration-specific:**
- Stripe: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`
- Twilio: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` or `TWILIO_PHONE_NUMBER`
- Email: `RESEND_API_KEY` (preferred) or `SENDGRID_API_KEY`
- APNs: `APNS_KEY_ID`, `APNS_TEAM_ID`, `APNS_AUTH_KEY_PATH`, `APNS_BUNDLE_ID`
- Sentry: `SENTRY_DSN` (optional)
- PostHog: `NEXT_PUBLIC_POSTHOG_KEY` (optional, client-side)
- AWS: Credentials for S3 (not yet integrated)

**Secrets location:**
- `.env` file (development, not committed)
- Render platform dashboard (production backend)
- Vercel environment variables (production frontend)
- Xcode build settings / keychain (iOS)

## Webhooks & Callbacks

**Incoming:**
- Stripe webhook handler
  - Endpoint: `POST /api/webhooks/stripe`
  - Events handled: `payment_intent.succeeded`, `payment_intent.payment_failed`, `charge.refunded`
  - Signature verification: `STRIPE_WEBHOOK_SECRET`
  - Stored in: `backend/routes/webhook.py`
  - Storage: `WebhookEvent` model in database (audit log)

**Outgoing:**
- Push notifications → Apple APNs
  - Triggered when: Job status changes (assigned, en route, completed)
  - Content: Job title, status message, optional data payload
  - Failed tokens automatically cleaned up from `DeviceToken` table
- SMS notifications → Twilio
  - Triggered when: Verification code needed, booking confirmed, job updates
- Email notifications → Resend/SendGrid
  - Triggered when: Booking confirmed, job assigned, payment receipt, password reset
  - All email sends happen in background thread to avoid blocking
- Real-time events → WebSocket clients (Socket.IO)
  - Rooms: Per-job rooms for live job tracking, admin room for dispatch map
  - Events: Driver location updates, job status broadcasts, new job alerts

## Third-party API Rate Limits & Best Practices

**Stripe:**
- No strict rate limits for payment intents
- Webhook retries: 5 times over 5 days (handled by Stripe)

**Twilio:**
- SMS rate limits: Varies by account tier
- Implementation: Graceful error logging (never blocks request)

**APNs:**
- Bearer token reused for 50 minutes (reduces signing overhead)
- Invalid tokens (HTTP 410) automatically removed from database
- Recommended: Keep connection open for high-volume sending

**PostHog:**
- Client-side batching (handles locally)
- No rate limits for analytics events

**Sentry:**
- Trace sample rate: 10% (configurable in `backend/server.py`)
- Errors always captured (100% error rate)

---

*Integration audit: 2026-02-13*
