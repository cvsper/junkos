# Codebase Structure

**Analysis Date:** 2026-02-13

## Directory Layout

```
/Users/sevs/Documents/Programs/webapps/junkos/
├── platform/                          # Next.js web platform (customer, operator, admin portals)
├── backend/                           # Flask API server
├── customer-portal-react/             # React 18 booking flow
├── customer-portal/                   # Svelte 4 booking flow (legacy)
├── dashboard/                         # React operator/admin dashboard
├── mobile/                            # React Native mobile app
├── JunkOS-Clean/                      # iOS Swift customer app (branded as Umuve)
├── JunkOS-Driver/                     # iOS Swift driver app (branded as Umuve Pro)
├── landing-page-premium/              # Vanilla HTML/CSS marketing site
├── database/                          # Database migrations and schemas
├── email-templates/                   # HTML email templates
├── deployment/                        # Deployment scripts and configs
├── docs/                              # Documentation
├── e2e/                               # End-to-end test suites
├── Makefile                           # Docker management commands
├── docker-compose.yml                 # Production Docker services
└── docker-compose.dev.yml             # Development Docker overrides
```

## Directory Purposes

**platform/**
- Purpose: Main Next.js 14 web application (responsive web UI)
- Contains: Customer booking, job tracking, operator dashboard, admin panel
- Key files: `src/app/layout.tsx`, `src/lib/api.ts`, `src/stores/*.ts`
- Deployment: Vercel (platform-olive-nu.vercel.app)
- Entry: `http://localhost:3000` (dev) or `http://goumuve.com` (prod)

**platform/src/app/**
- Layout: Next.js App Router with grouped routes using parentheses
- Groups:
  - `(customer)/` - Customer-facing pages: `/book`, `/dashboard`, `/track`, `/jobs`, `/referrals`
  - `(operator)/` - Operator pages: `/operator/jobs`, `/operator/earnings`, `/operator/settings`
  - `(admin)/` - Admin pages: `/admin/customers`, `/admin/jobs`, `/admin/analytics`
  - `(legal)/` - Legal pages: `/privacy`, `/terms`
  - Root pages: `/login`, `/sitemap.ts`, `/robots.ts`

**platform/src/components/**
- Subdirectories:
  - `ui/` - Radix UI wrapped components (button, card, dialog, tabs, etc)
  - `providers/` - Context/provider wrappers (PostHog analytics)
  - `shared/` - Reusable components (nav, footer, header)
  - `admin/` - Admin-specific components
  - `booking/` - Booking form components
  - `chat/` - Support chat components
  - `tracking/` - Real-time tracking components
  - `photos/` - Photo upload/gallery components
  - `reviews/` - Review display components

**platform/src/lib/**
- `api.ts` - Centralized fetch wrapper with JWT auth injection
- `socket.ts` - Socket.IO client connection
- `utils.ts` - Helper functions (formatting, validation)
- `posthog.ts` - Analytics integration

**platform/src/stores/**
- `auth-store.ts` - User auth state (Zustand + localStorage persist)
- `booking-store.ts` - Booking form state
- `tracking-store.ts` - Job tracking state
- Pattern: Zustand with persist middleware; localStorage key: `umuve-auth` (fallback: `junkos-auth`)

**platform/src/types/**
- `index.ts` - Shared TypeScript interfaces: User, Job, Address, Contractor, Payment, Rating, etc

**backend/**
- Purpose: Flask REST API server
- Root files: `server.py` (main app), `models.py` (SQLAlchemy), `database.py` (legacy SQLite)
- Configuration: `app_config.py`, `.env`, `.env.production`
- Deployment: Render.com, Railway, or Docker

**backend/routes/**
- Modular Flask blueprints, one file per feature:
  - `auth_routes.py` - JWT auth, login, signup
  - `booking.py` - Job creation, promo codes, pricing
  - `jobs.py` - Job status updates, list, detail
  - `payments.py` - Stripe integration, charge processing
  - `driver.py` - Individual driver operations (accept job, update location)
  - `drivers.py` - Driver list, search, location tracking
  - `operator.py` - Operator-specific endpoints
  - `admin.py` - Admin user management, analytics
  - `onboarding.py` - Driver/contractor onboarding
  - `push.py` - Push notification endpoints
  - `ratings.py` - Job reviews and ratings
  - `chat.py` - Support chat messages
  - `support.py` - Support tickets
  - `recurring.py` - Recurring jobs
  - `referrals.py` - Referral code validation
  - `promos.py` - Promo code management
  - `reviews.py` - Business reviews
  - `pricing.py` - Price calculation
  - `tracking.py` - Real-time tracking
  - `service_area.py` - Service area management
  - `upload.py` - Photo upload endpoints
- Pattern: Each returns JSON; validates via request.json; uses SQLAlchemy ORM

**backend/migrations/**
- Database schema migrations (Alembic/Flask-Migrate format)
- Applied on deployment via Makefile: `make migrate`

**customer-portal-react/**
- Purpose: React 18 standalone booking flow (6-step wizard)
- Contains: Booking form components, state management, styles
- Deployment: Vercel
- Uses: React Query for API calls, TailwindCSS for styling

**customer-portal/**
- Purpose: Svelte 4 booking flow (legacy, may be superseded by React version)
- Note: Svelte 5 syntax incompatible; do not upgrade

**dashboard/**
- Purpose: React operator/admin dashboard for job management
- Contains: Job cards, filters, real-time updates via Socket.IO
- Uses: WebSocket connection to backend for live job list

**mobile/**
- Purpose: React Native cross-platform mobile app
- Contains: Navigation, screens, API calls
- Structure: `/src/screens`, `/src/api`, `/src/context`, `/src/utils`, `/src/theme.ts`

**JunkOS-Clean/** (branded Umuve)
- Purpose: Native iOS app for customers (Swift + SwiftUI)
- Xcode project: `JunkOS-Clean.xcodeproj`
- Bundle ID: `com.goumuve.app`
- Note: Directory name unchanged despite rebrand; Xcode project names not renamed to avoid build breakage

**JunkOS-Driver/** (branded Umuve Pro)
- Purpose: Native iOS app for drivers (Swift + SwiftUI)
- Xcode project: `JunkOS-Driver.xcodeproj`
- Bundle ID: `com.goumuve.pro`
- Note: Same directory naming convention as JunkOS-Clean

**landing-page-premium/**
- Purpose: Static marketing website (vanilla HTML/CSS/JS)
- Files: `index.html`, `styles.css`, `script.js`
- Videos: `hero-bg.mp4` (desktop), `hero-mobile.jpg` (mobile fallback)
- Deployment: Vercel with aggressive caching config in `vercel.json`
- Note: Cache set to `max-age=60, must-revalidate` for CSS/JS

**database/**
- `migrations/` - SQL migration files (for PostgreSQL)
- Schema files documenting table structure and relationships
- Deployed via schema definition in backend models

**email-templates/**
- HTML email templates for transactional emails
- Files organized by purpose: booking confirmation, payment receipt, driver notifications
- Used by `backend/email_templates.py`

**deployment/**
- Deployment scripts for AWS, Render, Railway, or Docker-based platforms
- CI/CD configuration

## Key File Locations

**Entry Points:**

- `platform/src/app/layout.tsx` - Web platform root layout (Next.js 14)
- `platform/src/app/(customer)/layout.tsx` - Customer portal layout
- `platform/src/app/(operator)/layout.tsx` - Operator dashboard layout
- `platform/src/app/(admin)/admin/login/page.tsx` - Admin login
- `backend/server.py` - Flask API server main entry
- `backend/socket_events.py` - WebSocket event handlers
- `customer-portal-react/src/App.tsx` - Standalone booking flow
- `dashboard/src/App.jsx` - Operator dashboard
- `mobile/src/App.tsx` - React Native app
- `landing-page-premium/index.html` - Marketing site

**Configuration:**

- `platform/tsconfig.json` - TypeScript config with `@/*` path alias to `./src/*`
- `platform/next.config.mjs` - Next.js configuration
- `platform/tailwind.config.ts` - Tailwind CSS theme
- `backend/app_config.py` - Flask config class (debug, secret key, database)
- `backend/.env` - Environment variables (dev)
- `backend/.env.production` - Environment variables (prod)
- `.env.example` - Example env vars for project setup
- `docker-compose.yml` - Production Docker services (postgres, redis, backend, frontend)
- `docker-compose.dev.yml` - Development overrides
- `Makefile` - Docker command shortcuts

**Core Logic:**

- `backend/models.py` - SQLAlchemy ORM models (User, Job, Contractor, Payment, etc)
- `backend/routes/booking.py` - Job creation and pricing logic
- `backend/routes/payments.py` - Stripe payment processing
- `backend/auth_routes.py` - Authentication and JWT token generation
- `backend/database.py` - Database connection and legacy SQLite access
- `platform/src/lib/api.ts` - Centralized API fetch wrapper with auth
- `platform/src/stores/auth-store.ts` - Zustand auth state with localStorage persistence

**Styling:**

- `platform/src/styles/globals.css` - Global Tailwind directives and custom CSS
- `platform/tailwind.config.ts` - Design system tokens (colors, fonts, spacing)
- Landing page: `landing-page-premium/styles.css` - Vanilla CSS (no framework)

**Testing:**

- `backend/pytest.ini` - Pytest configuration
- `backend/requirements-test.txt` - Test dependencies (pytest, pytest-cov)
- `e2e/` - End-to-end test suites (Playwright or similar)

## Naming Conventions

**Files:**

- TypeScript/JavaScript: `camelCase.ts`, `camelCase.tsx`, `PascalCase` for components
- Python: `snake_case.py` for modules, `PascalCase` for classes
- CSS: `kebab-case.css`
- Database migrations: `YYYYMMDD_HHmmss_description.sql` or Alembic format

**Directories:**

- Feature-based: `/routes/booking.py`, `/components/booking/`
- Functional: `/lib/`, `/stores/`, `/utils/`, `/hooks/`, `/types/`
- Page-based: `/app/(customer)/book/`, `/app/(operator)/jobs/`
- Lowercase with hyphens: `customer-portal/`, `landing-page-premium/`

## Where to Add New Code

**New API Endpoint:**
1. Create function in appropriate `backend/routes/*.py` file (e.g., `jobs.py` for job-related endpoints)
2. Use Flask `@bp.route('/path', methods=['GET', 'POST'])` decorator
3. Validate request data: `data = request.json or {}`
4. Return JSON response: `jsonify({...})`
5. Register blueprint in `backend/server.py`: `app.register_blueprint(new_bp)`

**New Frontend Page:**
1. Create directory: `platform/src/app/(group)/page-name/`
2. Add `page.tsx` with "use client" directive if client component
3. Export default component function
4. Use Zustand stores for state: `const { token } = useAuthStore()`
5. Call API via `api.ts` helper: `apiFetch<JobType>('/api/jobs/123')`
6. Import UI components from `@/components/ui/`

**New Component:**
1. Location: `platform/src/components/[feature]/ComponentName.tsx` (or `platform/src/components/ui/` for reusable UI)
2. Use "use client" at top if hooks are needed
3. Accept typed props
4. Return JSX with Tailwind classes
5. Export component as default

**New Store:**
1. Location: `platform/src/stores/[feature]-store.ts`
2. Use Zustand create() with persist middleware if localStorage needed
3. Define interface for state shape
4. Export useStore hook
5. Import in components: `const { state } = useFeatureStore()`

**New Utilities:**
1. Shared helpers: `platform/src/lib/[feature].ts`
2. Component-specific: `platform/src/components/[feature]/utils.ts`
3. Type-safe helpers with TypeScript

**New Database Model:**
1. Add SQLAlchemy class to `backend/models.py`
2. Define columns and relationships
3. Add to_dict() method for JSON serialization
4. Create migration: `flask db migrate -m 'description'`
5. Reference in routes via `from models import ModelName`

## Special Directories

**node_modules/**
- Generated: Yes (npm install)
- Committed: No (gitignored)
- Purpose: NPM package dependencies
- Present in: `platform/`, `customer-portal-react/`, `dashboard/`, `mobile/`

**instance/**
- Generated: Yes (Flask runtime)
- Committed: No
- Purpose: Flask instance folder for local development database
- Location: `backend/instance/`

**.next/**
- Generated: Yes (Next.js build)
- Committed: No
- Purpose: Build output and cache
- Location: `platform/.next/`

**dist/ / build/**
- Generated: Yes (build output)
- Committed: No
- Purpose: Compiled/bundled application files
- Locations: `customer-portal-react/dist/`, `dashboard/dist/`

**.git/**
- Purpose: Git repository metadata
- Committed: No (directory itself, but tracked by git)

**.env files**
- Location: Root of backend, platform, and projects
- Committed: No (security)
- Purpose: Environment variables (API keys, database URLs, etc)
- Note: `.env.example` IS committed as template

**migrations/**
- Location: `backend/migrations/` (Flask-Migrate/Alembic)
- Committed: Yes
- Purpose: Database schema versions
- Applied on deployment via `flask db upgrade`

**public/**
- Location: `platform/public/`, `customer-portal-react/public/`, `landing-page-premium/`
- Committed: Yes
- Purpose: Static assets (images, logos, manifest.json)
- Served at `/` in production

---

*Structure analysis: 2026-02-13*
