# Codebase Concerns

**Analysis Date:** 2026-02-13

## Tech Debt

**Hardcoded API Keys in iOS Apps:**
- Issue: Production API key is hardcoded as a placeholder string in Config.swift files
- Files:
  - `JunkOS-Clean/JunkOS/Services/Config.swift` (line 31: `return "umuve-api-key-12345"`)
  - `JunkOS-Driver/Config/Config.swift` (similar hardcoded key)
- Impact: If app is compiled for production, it will use a test key rather than the actual production key. This breaks all API calls to the backend.
- Fix approach: Implement secure key management using:
  - iOS Keychain for storing production API keys
  - Environment-specific build configurations (XCConfig files)
  - Code-sign automated key injection or Firebase Config for remote key management
  - Remove hardcoded keys entirely from source code

**Production URL Hardcoded to Old Domain:**
- Issue: iOS apps hardcode `https://junkos-backend.onrender.com` as production API endpoint, not updated to current Render URL
- Files:
  - `JunkOS-Clean/JunkOS/Services/Config.swift` (line 21)
  - `JunkOS-Driver/Config/Config.swift` (line 20)
  - `landing-page-premium/operators.js` (TODO comment on line 83)
- Impact: App may fail to reach the correct backend after Render deployment changes. Customers and drivers cannot function.
- Fix approach: Implement dynamic URL configuration that can be updated without rebuilding:
  - Use environment variables and build configuration
  - Implement remote configuration (Firebase Remote Config or similar)
  - Add config validation on app startup

**Legacy Database References Still Active:**
- Issue: Code references both `junkos.db` and `umuve.db`, with migration fallbacks in place but creating dual paths
- Files:
  - `platform/src/lib/api.ts` (lines 96-98: fallback to `junkos_referral_code` localStorage key)
  - Multiple authentication stores maintain legacy key support
- Impact: Technical debt from rebrand. Increases cognitive load and maintenance burden. Creates subtle bugs when only one key is updated.
- Fix approach:
  - Establish a hard migration deadline (e.g., 30 days post-rebrand)
  - Create one-time data migration script that converts all old keys to new ones
  - Remove all fallback code and legacy references after migration period

**Placeholder API Endpoint in Operator Form:**
- Issue: Operator signup form submits to a placeholder endpoint without actual handler
- Files: `landing-page-premium/operators.js` (line 84: `fetch('/api/operator-applications')` with TODO comment)
- Impact: Form submissions are silently lost. Operator applications cannot be collected.
- Fix approach: Implement actual backend endpoint at `/api/operator-applications` in `backend/routes/` or wire existing endpoint

## Known Bugs

**SMS Service Graceful Failures Mask Real Issues:**
- Symptoms: SMS sending failures are logged but not surfaced to user. Confirmation/reminder SMS may silently fail.
- Files: `backend/sms_service.py` (entire module returns None on any error)
- Trigger: If Twilio credentials are misconfigured or network fails, SMS is silently dropped
- Workaround: Check backend logs for SMS failures. Manual SMS verification not available.
- Risk: Customers miss critical job reminders and completion confirmations, leading to support tickets

**Missing Stripe Webhook Signature Verification:**
- Symptoms: Webhook endpoints may accept fraudulent webhook payloads if signature verification fails
- Files: `backend/routes/payments.py` (line that catches `stripe.error.SignatureVerificationError`)
- Trigger: Invalid or spoofed Stripe webhook request
- Impact: Attackers could trigger false job completions or payment confirmations
- Fix approach: Ensure all webhook endpoints verify the X-Stripe-Signature header against STRIPE_WEBHOOK_SECRET

**Unimplemented SMS Functions Return Silently:**
- Symptoms: All SMS helper functions in `backend/sms_service.py` are designed to never raise exceptions and return None on failure
- Files: `backend/sms_service.py` (functions on lines 147-244)
- Impact: No audit trail of which SMSes failed. Customers don't know if their SMS was sent. Creates support burden.
- Fix approach: Implement proper SMS status tracking in database, add monitoring/alerting for SMS failures

## Security Considerations

**API Keys Exposed in Production Builds:**
- Risk: If iOS app is compiled with hardcoded test API key, production API authentication fails completely
- Files: `JunkOS-Clean/JunkOS/Services/Config.swift`, `JunkOS-Driver/Config/Config.swift`
- Current mitigation: Conditional compilation (#if DEBUG) switches between dev and prod, but production value is still hardcoded
- Recommendations:
  - Use Xcode build settings or XCConfig files to inject keys per environment
  - Store API keys in iOS Keychain, never in source code
  - Implement certificate pinning to prevent MITM attacks on API calls
  - Add token rotation mechanism for long-lived API keys

**Loose Environment Variable Requirements:**
- Risk: If required env vars (JWT_SECRET, SECRET_KEY, DATABASE_URL) are missing in production, app starts with degraded security
- Files: `backend/server.py` (lines 36-67)
- Current mitigation: Server logs warnings but continues startup
- Recommendations:
  - Make JWT_SECRET and SECRET_KEY mandatory in non-development environments (crash on startup if missing)
  - Validate all critical secrets before accepting requests
  - Implement secret rotation and versioning

**No Input Sanitization Visible in Forms:**
- Risk: XSS, SQL injection, or prompt injection in user-provided data (photos, addresses, descriptions)
- Files:
  - `landing-page-premium/operators.js` - form data passed directly to API
  - `platform/src/components/booking/step-6-payment.tsx` - form inputs
- Current mitigation: `backend/sanitize.py` module exists but usage not visible across all routes
- Recommendations:
  - Apply sanitization middleware to all routes accepting user input
  - Validate data types and formats on backend before database insert
  - Use parameterized queries consistently (verify no string concatenation in SQL)

**Twilio Credentials in Environment:**
- Risk: If .env file is accidentally committed, Twilio credentials are exposed
- Files: `.env`, `.env.production` (not readable due to security), referenced in `backend/sms_service.py` (lines 25-28)
- Current mitigation: .env files are in .gitignore
- Recommendations:
  - Use secret management service (AWS Secrets Manager, HashiCorp Vault, or Render/Railway environment secrets)
  - Rotate Twilio auth token regularly
  - Implement audit logging for which services access credentials

## Performance Bottlenecks

**Large Component Files with Complex Logic:**
- Problem: Component files exceed 800+ lines, containing state management, API calls, and UI rendering
- Files (Top candidates):
  - `platform/src/components/booking/step-6-payment.tsx` (879 lines) - payment processing, validation, Stripe integration
  - `platform/src/app/(admin)/admin/pricing/page.tsx` (1341 lines) - pricing management, analytics, editing
  - `mobile/App.tsx` (1693 lines) - entire app navigation and state
- Cause: Lack of component decomposition. Too many responsibilities per file.
- Improvement path:
  - Extract Stripe integration into separate component/hook
  - Break pricing page into smaller composable components
  - Create custom hooks for payment state, booking state, etc.
  - Consider state management library (Zustand, Jotai) for complex stores

**Missing Database Query Optimization:**
- Problem: No visible indexes on frequently queried columns. ORM lazy-loading may cause N+1 queries.
- Files: `backend/models.py` - SQLAlchemy relationship definitions use `lazy="dynamic"` which defers loading
- Impact: As job count grows (100+ jobs), dashboard and admin pages will slow down significantly.
- Improvement path:
  - Add database indexes on `tenant_id`, `user_id`, `status`, `scheduled_date`
  - Use `eager` loading strategically in high-traffic endpoints
  - Implement query result caching for analytics endpoints
  - Add query performance monitoring with SQLAlchemy events

**No Pagination on Admin Dashboard:**
- Problem: Admin endpoints may load thousands of jobs/payments without pagination
- Files: `platform/src/app/(admin)/admin/jobs/page.tsx` (783 lines), `platform/src/app/(admin)/admin/analytics/page.tsx` (524 lines)
- Impact: Dashboard becomes unusable at scale (100+ jobs per tenant)
- Improvement path: Implement cursor-based or offset pagination with limit (default 50-100 items)

## Fragile Areas

**Backend Routes with Manual JSON Parsing:**
- Files: `backend/server.py` (lines indicate try/except blocks for JSON parsing)
- Why fragile: If a client sends malformed JSON, the error handling is opaque (`pass` statements)
- Safe modification:
  - Add explicit error logging before `pass` statements
  - Return structured error response to client
  - Add request validation middleware
- Test coverage: Need integration tests for malformed request bodies

**Multi-Database Support (SQLite + PostgreSQL):**
- Files: `backend/database.py` (lines 15-100) - maintains separate code paths for SQLite and PostgreSQL
- Why fragile: Changes to schema must be tested on both databases. Easy to break one when fixing the other.
- Safe modification:
  - Run test suite against both database types before deploying
  - Consider deprecating SQLite in production (use only for local development)
  - Add database-specific migration tests
- Test coverage: Missing integration tests for PostgreSQL-specific features (JSONB, Window functions)

**Payment Processing Without Idempotency Keys:**
- Files: `backend/routes/payments.py`, `platform/src/components/booking/step-6-payment.tsx`
- Why fragile: If payment request is retried (network timeout, browser refresh), charge may be duplicated
- Safe modification:
  - Implement Stripe idempotency keys on all payment endpoints
  - Store idempotency key in booking record
  - Validate duplicate charges before creating new payment record
- Test coverage: Need tests for network timeout scenarios and duplicate payment detection

**iOS App Configuration Hardcoded:**
- Files: `JunkOS-Clean/JunkOS/Services/Config.swift`, `JunkOS-Driver/Config/Config.swift`
- Why fragile: Any production deployment requires code changes and recompilation
- Safe modification:
  - Implement remote configuration (Firebase, AWS AppConfig, or custom API endpoint)
  - Allow configuration to be updated without app rebuild
  - Version configuration schema to handle client-server mismatches
- Test coverage: Need tests for fallback behavior when remote config is unreachable

## Scaling Limits

**SQLite Database for Production:**
- Current capacity: ~10,000 records before performance degrades
- Limit: SQLite has write contention issues with concurrent requests. Not suitable for production SaaS.
- Scaling path:
  - Migrate to PostgreSQL (infrastructure already supports it)
  - Implement connection pooling (pgBouncer or PgHero)
  - Add read replicas for analytics queries
  - Implement caching layer (Redis) for frequently accessed data

**Single Monolithic Backend Server:**
- Current capacity: ~50-100 concurrent users before CPU bottleneck
- Limit: Flask single-threaded by default. No load balancing or auto-scaling configured.
- Scaling path:
  - Add Gunicorn/uWSGI with multiple worker processes
  - Implement containerized deployment (Docker) with orchestration (Kubernetes or Render auto-scaling)
  - Separate heavy operations (image processing, PDF generation) into background jobs (Celery + Redis)
  - Implement API rate limiting and request queuing

**File Upload Storage:**
- Current implementation: Files likely stored on local filesystem or Render ephemeral storage
- Limit: Render ephemeral filesystems are destroyed on each deploy. Files are lost.
- Scaling path:
  - Migrate to cloud storage (AWS S3, Google Cloud Storage, or Render blob storage)
  - Implement signed URLs for secure file access
  - Add virus scanning for uploaded photos
  - Implement cleanup for old/stale uploads

## Dependencies at Risk

**Stripe Integration Without Webhook Retry Logic:**
- Risk: Webhook delivery failures are not retried by app. If webhook is lost, job status becomes inconsistent.
- Impact: Customer payment confirmed but operator job not marked as paid.
- Migration plan:
  - Implement webhook event log table to track all received/processed webhooks
  - Add retry mechanism for failed webhook processing
  - Use Stripe Event API to backfill missed webhooks during outages

**Twilio SMS Without Fallback Provider:**
- Risk: Twilio outage blocks all SMS notifications
- Impact: Customers and operators cannot receive booking confirmations or status updates
- Migration plan:
  - Add fallback SMS provider (AWS SNS, Vonage/Nexmo, or custom PSTN gateway)
  - Implement provider health checking
  - Queue SMS requests so they can be retried with fallback provider

**React Query Version in Admin Dashboard:**
- Risk: TanStack Query (React Query) major version changes may break pagination/caching logic
- Impact: Admin pages may display stale data or cause unnecessary API calls
- Migration plan:
  - Pin dependency version with caret (^) to allow patch/minor updates only
  - Add automated dependency update checks (Dependabot)
  - Test major version upgrades in staging before applying to production

## Missing Critical Features

**No API Rate Limiting Enforcement:**
- Problem: Endpoints lack per-user/per-IP rate limits
- Blocks: Cannot prevent brute force attacks on auth endpoints. DDoS vulnerable.
- Files: `backend/server.py` references `limiter` extension but implementation unclear
- Priority: HIGH - deploy before public launch
- Implementation: Use Flask-Limiter with Redis backend for distributed rate limiting

**No Input Validation Framework:**
- Problem: Manual validation scattered across routes. Inconsistent error messages.
- Blocks: Cannot validate complex booking data (address, photos, scheduling). Security risk.
- Files: Multiple route handlers in `backend/routes/` perform ad-hoc validation
- Priority: HIGH - many security implications
- Implementation: Use Marshmallow or Pydantic schemas for request/response validation

**No Audit Logging for Financial Operations:**
- Problem: Payment processing, refunds, and payout changes are not logged with user/admin attribution
- Blocks: Cannot investigate payment disputes or detect fraud. Compliance issues.
- Files: `backend/routes/payments.py` lacks audit trail
- Priority: MEDIUM - required for production SaaS
- Implementation: Create audit_log table, log all payment/refund operations

**No Consent/Privacy Compliance Tracking:**
- Problem: No record of customer consent for SMS, email, or data usage
- Blocks: Cannot demonstrate GDPR/CCPA compliance for audits
- Files: Customer signup in platform and iOS apps
- Priority: MEDIUM - legal/compliance risk
- Implementation: Add consent tracking table, require explicit opt-in before SMS/email

## Test Coverage Gaps

**No Automated Tests for Payment Flow:**
- What's not tested: Stripe payment integration, idempotency, webhook handling, error scenarios
- Files: `backend/routes/payments.py`, `platform/src/components/booking/step-6-payment.tsx`
- Risk: Payment failures in production are undetected until customer reports them
- Priority: CRITICAL - payments are revenue-critical

**No Integration Tests for SMS:**
- What's not tested: SMS delivery success/failure handling, phone number formatting edge cases
- Files: `backend/sms_service.py` has 244 lines of production code with no test file visible
- Risk: SMS failures go unnoticed. Customers miss booking confirmations.
- Priority: HIGH - customer-facing feature

**No End-to-End Tests for Booking Flow:**
- What's not tested: Full customer journey from address entry → photo upload → payment → confirmation
- Files: Multiple components and backend routes involved
- Risk: Changes to any component break the entire flow without detection
- Priority: HIGH - core business process

**Minimal Backend Route Tests:**
- What's not tested: Error handling, missing parameters, database constraints, concurrent access
- Files: `backend/routes/` directory has ~15 route files (admin.py, jobs.py, booking.py, etc.)
- Risk: Route changes cause production failures (500 errors, data corruption)
- Priority: MEDIUM - systematic approach needed

**No Mobile App Tests Beyond Mocks:**
- What's not tested: Real API integration, offline handling, deep link routing
- Files: `JunkOS-Clean/` and `JunkOS-Driver/` projects have test files but many are mocks
- Risk: Critical flows fail only when customer uses the app
- Priority: HIGH - users interact primarily with iOS apps

## Environment Configuration Issues

**Missing DATABASE_URL in Local Development:**
- Problem: Backend falls back to SQLite (umuve.db) if DATABASE_URL not set, but production expects PostgreSQL
- Impact: Local development behavior differs from production. Subtle bugs only appear in prod.
- Fix: Require DATABASE_URL in development `.env` file, document setup clearly

**Inconsistent Environment Variable Naming:**
- Problem: Some vars use NEXT_PUBLIC prefix (frontend), others don't (backend)
- Files: Multiple `.env` and `.env.example` files across projects
- Impact: Confusion during deployment. Easy to miss required variables.
- Fix: Standardize naming conventions. Use README in each service to document all required vars.

---

*Concerns audit: 2026-02-13*
