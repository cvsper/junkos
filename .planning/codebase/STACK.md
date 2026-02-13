# Technology Stack

**Analysis Date:** 2026-02-13

## Languages

**Primary:**
- Python 3.12 - Backend server (Flask), utilities, migrations
- TypeScript - Next.js platform, React customer portal, configuration
- JavaScript - Landing page, frontend utilities
- Swift - iOS customer app (JunkOS-Clean), driver app (JunkOS-Driver)

**Secondary:**
- SQL - Database schema and migrations
- Shell - Deployment scripts

## Runtime

**Environment:**
- Python 3.12.0 (production via `runtime.txt`)
- Node.js - For Next.js platform and React applications
- iOS 14+ - Customer and driver apps

**Package Managers:**
- pip - Python dependency management
- npm - JavaScript/TypeScript dependency management
- Lockfile: package-lock.json present for all Node.js projects

## Frameworks

**Core Backend:**
- Flask 3.0.0 - REST API server
- Flask-SQLAlchemy 3.1.1 - ORM layer
- Flask-SocketIO 5.3.6 - Real-time WebSocket events
- SQLAlchemy 2.0.36 - Database abstraction

**Frontend Platforms:**
- Next.js 14.2.5 - Admin/operator platform (`platform/`)
- React 18.3.1 - Customer booking portal (`customer-portal-react/`)
- Vite 5.1.6 - Build tool for React portal
- SwiftUI - iOS apps (JunkOS-Clean, JunkOS-Driver)

**Styling:**
- Tailwind CSS 3.4.6 - Utility-first CSS (platform, customer portal)
- Radix UI - Headless UI components (platform)
- Framer Motion 12.34.0 - Animation library (platform)

**Testing:**
- Jest 29.7.0 - JavaScript unit testing
- pytest 8.0.0 - Python unit testing
- Playwright 1.41.0 - E2E testing
- XCTest - iOS unit testing

**Build/Dev:**
- TypeScript 5.5.3 - Type checking
- ESLint 8.57.0 - Linting
- PostCSS 8.4.39 - CSS processing
- Autoprefixer 10.4.19 - CSS vendor prefixing

## Key Dependencies

**Critical Infrastructure:**
- psycopg2-binary 2.9.9 - PostgreSQL driver
- redis 5.0.1 - Caching and session store
- celery 5.3.6 - Async task queue
- gunicorn 21.2.0 - WSGI HTTP server

**Authentication & Security:**
- Flask-JWT-Extended 4.6.0 - JWT token management
- PyJWT 2.10.1 - JWT encoding/decoding
- Werkzeug 3.0.1 - WSGI utilities, password hashing

**API & Integration:**
- stripe 5.5.0 - Payment processing (Stripe Connect)
- twilio 9.0.4 - SMS notifications
- sendgrid 6.11.1 - Email delivery (legacy)
- resend 2.5.1 - Email delivery (preferred)
- boto3 1.34.14 - AWS SDK for S3 file uploads
- httpx[http2] 0.27.0 - HTTP client with HTTP/2 support
- geopy 2.4.1 - Geolocation and distance calculations

**Observability:**
- sentry-sdk[flask] 2.14.0 - Error tracking and monitoring

**Networking & Real-time:**
- socket.io-client 4.7.5 - WebSocket client (platform)
- flask-cors 4.0.0 - CORS middleware
- flask-limiter 4.1.1 - Rate limiting

**Data Processing:**
- python-dotenv 1.0.0 - Environment variable loading
- APScheduler 3.10.4 - Scheduled background tasks
- eventlet 0.35.1 - Async I/O for SocketIO
- python-dateutil 2.9.0 - Date/time parsing
- date-fns 3.6.0 - JavaScript date utilities (client)

**Analytics:**
- posthog-js 1.345.5 - Product analytics (platform)

**UI Components & Utilities:**
- clsx 2.1.1 - Conditional className utility
- lucide-react 0.400.0 - Icon library
- react-hook-form 7.51.0 - Form state management
- axios 1.6.8 - HTTP client for React portal
- react-datepicker 6.3.0 - Date picker component
- react-dropzone 14.2.3 - File upload component
- zustand 4.5.4 - State management (platform)
- @tanstack/react-query 5.51.0 - Server state management (platform)
- mapbox-gl 3.5.0 - Maps rendering (platform)
- @stripe/react-stripe-js 2.7.0 - Stripe React components
- react-use-measure 2.1.7 - Dimension measurement hook

**Testing Utilities:**
- @testing-library/react 14.1.2 - React component testing
- @testing-library/jest-dom 6.2.0 - Jest DOM matchers
- identity-obj-proxy 3.0.0 - CSS module mocking
- factory-boy 3.3.0 - Test data factories (Python)
- faker 22.6.0 - Fake data generation

## Configuration

**Environment Variables:**

Critical (production required):
- `JWT_SECRET` - JWT signing key
- `SECRET_KEY` - Flask session secret
- `DATABASE_URL` - PostgreSQL connection string (fallback: SQLite at `umuve.db`)

Recommended (integration):
- `STRIPE_SECRET_KEY` - Stripe API secret key
- `STRIPE_WEBHOOK_SECRET` - Stripe webhook signature key
- `TWILIO_ACCOUNT_SID` - Twilio account ID
- `TWILIO_AUTH_TOKEN` - Twilio auth token
- `TWILIO_FROM_NUMBER` or `TWILIO_PHONE_NUMBER` - SMS sender number
- `RESEND_API_KEY` - Resend email API key (preferred over SendGrid)
- `SENDGRID_API_KEY` - SendGrid email API key (legacy fallback)
- `EMAIL_FROM` - Default sender email (default: `bookings@goumuve.com`)
- `EMAIL_FROM_NAME` - Default sender name (default: `Umuve`)
- `APNS_KEY_ID` - Apple APNs key ID (10 chars)
- `APNS_TEAM_ID` - Apple Developer Team ID
- `APNS_AUTH_KEY_PATH` - Absolute path to `.p8` private key file
- `APNS_BUNDLE_ID` - iOS app bundle ID (e.g., `com.goumuve.driver`)
- `SENTRY_DSN` - Sentry error tracking URL (optional)
- `CORS_ORIGINS` - Comma-separated allowed origins (production enforced as allowlist)
- `FLASK_ENV` - `development` or `production`
- `ADMIN_SEED_SECRET` - Secret for creating initial admin account
- `RATELIMIT_STORAGE_URI` - Redis connection for distributed rate limiting
- `NEXT_PUBLIC_API_URL` - Backend API base URL
- `NEXT_PUBLIC_POSTHOG_KEY` - PostHog analytics key
- `NEXT_PUBLIC_POSTHOG_HOST` - PostHog server host

**Build Configuration:**

Node.js projects:
- `tsconfig.json` - TypeScript compiler settings
- `next.config.mjs` - Next.js configuration (image remotes from AWS, Unsplash, UFS)
- `tailwind.config.js` - Tailwind CSS customization
- `postcss.config.js` - PostCSS plugin configuration
- `eslint.config.js` - ESLint rules (or `.eslintrc.js`)
- `jest.config.js` - Jest test runner config (customer portal)
- `playwright.config.ts` - E2E testing config (customer portal)

Backend:
- `requirements.txt` - Python dependency versions
- `requirements-test.txt` - Testing-only dependencies
- `runtime.txt` - Python version specification
- `app_config.py` - Flask Config class
- Database migrations in `backend/migrations/`

Deployment:
- `vercel.json` - Vercel cache headers for landing page
- `.vercelignore` - Files to exclude from deployment

## Platform Requirements

**Development:**
- Python 3.12
- Node.js 16+ (for npm)
- PostgreSQL 12+ or SQLite (fallback)
- Redis (optional, for production caching/rate limiting)
- Xcode 15+ (iOS development)
- Swift 5.9+ (iOS)

**Production:**
- Python 3.12 runtime environment
- PostgreSQL database (recommended over SQLite)
- Redis (for caching, rate limiting, session management)
- APNs certificates from Apple Developer account
- AWS S3 bucket (for file uploads via boto3)
- Stripe account with webhook setup
- Twilio account for SMS
- Resend or SendGrid account for email

**Deployment Targets:**
- Render - Backend Flask server (`umuve-backend.onrender.com`)
- Vercel - Next.js platform, landing page
- iOS App Store - Customer and driver apps

---

*Stack analysis: 2026-02-13*
