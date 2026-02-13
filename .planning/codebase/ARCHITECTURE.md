# Architecture

**Analysis Date:** 2026-02-13

## Pattern Overview

**Overall:** Microservices-based layered architecture with clear separation between frontend (Next.js platform), backend (Flask API), and multiple client applications (iOS native, React Native).

**Key Characteristics:**
- Backend-agnostic frontend using REST API with JWT authentication
- Centralized Flask backend serving all clients (web platform, iOS apps, React Native)
- Zustand-based state management for client-side persistence
- Real-time updates via Socket.IO WebSocket connections
- Role-based access control (customer, driver/contractor, admin, operator)
- Multi-tenant architecture supporting different user types

## Layers

**Presentation Layer (Frontend):**
- Purpose: User-facing interfaces for customers, operators, and admins
- Location: `platform/src`, `customer-portal-react/src`, `dashboard/src`, `mobile/src`
- Contains: React/Next.js components, UI components (Radix UI), page layouts, forms
- Depends on: API library, auth store, socket connections
- Used by: End users (web and mobile)

**API Integration Layer:**
- Purpose: Standardized communication with backend API
- Location: `platform/src/lib/api.ts`, `platform/src/lib/socket.ts`
- Contains: Fetch wrapper, error handling, auth headers, Socket.IO client
- Depends on: Zustand auth store for token management
- Used by: All frontend components and stores

**State Management Layer:**
- Purpose: Client-side data persistence and state distribution
- Location: `platform/src/stores/`
- Contains: Zustand stores (auth-store.ts, booking-store.ts, tracking-store.ts)
- Depends on: localStorage, auth API
- Used by: React components via hooks
- Pattern: Zustand with persist middleware, localStorage fallback to legacy keys

**Backend API Layer (Flask):**
- Purpose: Core business logic, database queries, external service integrations
- Location: `backend/server.py`, `backend/routes/*.py`
- Contains: Route blueprints, request handlers, validation, error handling
- Depends on: SQLAlchemy ORM, external APIs (Stripe, Twilio, etc)
- Used by: All clients (web platform, mobile apps)

**Data Access Layer:**
- Purpose: Database persistence and model definitions
- Location: `backend/models.py`, `backend/database.py`
- Contains: SQLAlchemy models, migrations, database connection
- Depends on: PostgreSQL (production) or SQLite (development)
- Used by: Route handlers, services

**Cross-layer Services:**
- Authentication: JWT tokens, OAuth (Apple ID)
- Payments: Stripe integration
- Push Notifications: Firebase Cloud Messaging integration
- Email: Template-based notifications via SMTP
- WebSockets: Real-time job tracking and messaging

## Data Flow

**Job Booking Flow:**

1. Customer fills booking form in `platform/src/app/(customer)/book/page.tsx`
2. Component calls `useAuthStore` for JWT token
3. Makes POST to `/api/bookings` via `api.ts` apiFetch wrapper
4. Backend route handler `backend/routes/booking.py` receives request
5. Handler calculates price via pricing engine
6. Creates Job and Payment records in database
7. Returns booking confirmation with job ID
8. WebSocket emits job update to operators/drivers
9. Frontend updates booking-store.ts tracking state

**Job Tracking Flow:**

1. Customer views job status in `platform/src/app/(customer)/track/[jobId]/page.tsx`
2. Component subscribes to Socket.IO channel for job updates
3. Backend emits location/status updates via socket from `socket_events.py`
4. Frontend receives updates and updates tracking-store.ts
5. Map component renders real-time location

**State Management:**
- Auth state persisted in localStorage (key: `umuve-auth`, fallback: `junkos-auth`)
- Booking form state in memory via booking-store.ts
- Tracking state via tracking-store.ts and Socket.IO subscriptions
- Server is source of truth for all persistent data

## Key Abstractions

**User (Role-based):**
- Purpose: Represents all user types in system
- Examples: `backend/models.py` User model, `platform/src/types/index.ts` User interface
- Pattern: Single table inheritance with role column; frontend type discriminates access

**Job:**
- Purpose: Represents a junk removal task with status progression
- Examples: `backend/models.py` Job model, `platform/src/types/index.ts` Job interface
- Pattern: Immutable updates via API; status values: pending → confirmed → delegating → assigned → en_route → arrived → in_progress → completed/cancelled

**Contractor (Driver):**
- Purpose: Represents drivers/operators who complete jobs
- Examples: `backend/models.py` Contractor model
- Pattern: One-to-one relationship with User; includes vehicle info, ratings, service areas

**Payment:**
- Purpose: Tracks financial transactions for jobs
- Examples: `backend/models.py` Payment model
- Pattern: Created with job; linked to Stripe payment intent

**Address:**
- Purpose: Geolocation data for jobs
- Examples: `platform/src/types/index.ts` Address interface
- Pattern: street, city, state, zip, lat, lng coordinates for mapping

## Entry Points

**Web Platform:**
- Location: `platform/src/app/layout.tsx`
- Triggers: Browser navigation to goumuve.com
- Responsibilities: Root layout, font initialization, PostHog analytics provider

**Customer Section:**
- Location: `platform/src/app/(customer)/layout.tsx`
- Triggers: Navigation to /book, /dashboard, /track, /referrals
- Responsibilities: Auth check, navbar, logout, SupportChat component

**Operator Section:**
- Location: `platform/src/app/(operator)/layout.tsx`
- Triggers: Navigation to /operator/*
- Responsibilities: Operator-specific navigation, earnings, jobs, fleet management

**Admin Section:**
- Location: `platform/src/app/(admin)/admin/login/page.tsx`
- Triggers: Navigation to /admin/*
- Responsibilities: Admin dashboard, user management, promos, analytics

**Backend API:**
- Location: `backend/server.py`
- Triggers: HTTP requests to /api/* endpoints
- Responsibilities: CORS setup, blueprint registration, middleware chain, error handling, rate limiting

**WebSocket Server:**
- Location: `backend/socket_events.py`
- Triggers: Client connection to Socket.IO server
- Responsibilities: Job updates, real-time tracking, driver notifications, location broadcasts

## Error Handling

**Strategy:** Centralized error handling with consistent JSON responses

**Patterns:**
- `backend/server.py`: @app.errorhandler(429) for rate limits
- `platform/src/lib/api.ts`: ApiError class with status, message, and data properties
- Backend validates input; returns 400 for invalid data, 401 for auth failures, 500 for server errors
- Frontend catches ApiError and displays user-friendly toasts via component

**HTTP Status Codes:**
- 200: Success
- 204: No content (successful deletion)
- 400: Validation error
- 401: Auth required/token invalid
- 403: Insufficient permissions
- 404: Resource not found
- 429: Rate limit exceeded
- 500: Server error

## Cross-Cutting Concerns

**Logging:**
- Backend: Python logging module in routes and models
- Frontend: Browser console via components
- Sentry integration optional (SENTRY_DSN env var enables error tracking)

**Validation:**
- Backend: Route handlers validate request data before processing
- Frontend: Form validation in component state before submission
- Both: Type safety via TypeScript (frontend) and Python type hints

**Authentication:**
- Backend: JWT tokens validated in auth_routes.py
- Frontend: Token stored in Zustand auth-store, included in Authorization header
- Session strategy: Stateless JWT; no server sessions
- Fallback: Legacy "junkos-auth" localStorage key migrated to "umuve-auth" on first load

**Authorization:**
- Backend: User.role checked against route requirements (customer, driver, admin, operator)
- Frontend: Routes guarded by role checks in layout components
- Pattern: Role-based access control (RBAC) via user.role field

**Rate Limiting:**
- Backend: Flask-Limiter per-route (e.g., auth endpoints)
- In-memory storage; can upgrade to Redis via RATELIMIT_STORAGE_URI
- Returns 429 with Retry-After header

**CORS:**
- Whitelist in server.py: goumuve.com, platform-olive-nu.vercel.app, landing-page-premium-five.vercel.app
- Development: "*" allowed
- Production: Explicit whitelist enforced (no wildcard)

---

*Architecture analysis: 2026-02-13*
