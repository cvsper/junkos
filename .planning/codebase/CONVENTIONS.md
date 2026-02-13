# Coding Conventions

**Analysis Date:** 2026-02-13

## Naming Patterns

**Files:**
- React/Next.js components: PascalCase (e.g., `support-chat.tsx`, `notification-bell.tsx`)
- Utilities and services: camelCase (e.g., `api.ts`, `socket.ts`, `posthog.ts`)
- Hooks: PascalCase with `use` prefix (e.g., `useBookingForm.js`, `useAdminMapSocket.ts`)
- Store files: camelCase with `-store` suffix (e.g., `auth-store.ts`, `booking-store.ts`)
- Test files: Suffixed with `.test.` or `.spec.` (e.g., `PhotoUpload.test.jsx`, `booking-flow.spec.js`)

**Functions:**
- Async functions: camelCase (e.g., `apiFetch`, `sendSupportMessage`, `getPriceEstimate`)
- Helper functions: camelCase (e.g., `generateVerificationCode`, `hashPassword`, `formatPhoneNumber`)
- React hooks: `use` prefix, camelCase (e.g., `useAuthStore`, `useBookingForm`, `useAdminMapSocket`)
- Route handlers (Flask): snake_case (e.g., `send_verification_code`, `find_or_create_user_by_phone`)
- API endpoint functions: camelCase, grouped in object (e.g., `authApi.login`, `jobsApi.list`, `bookingApi.submit`)

**Variables:**
- Constants: UPPER_SNAKE_CASE for globals (e.g., `API_BASE_URL`, `JWT_SECRET`, `WS_URL`, `CRITICAL_ENV_VARS`)
- State variables: camelCase (e.g., `isLoading`, `formData`, `currentStep`, `isConnected`)
- Boolean variables: prefix `is`, `has`, `should` (e.g., `isAuthenticated`, `hasError`, `shouldValidate`)
- Refs: suffix `Ref` (e.g., `socketRef`, `onContractorLocationRef`)

**Types:**
- Interfaces: PascalCase (e.g., `ChatMessage`, `AuthState`, `BookingFormData`, `UserRole`)
- Discriminated unions: snake_case or kebab-case variants (e.g., `where_is_driver`, `en_route`, `in_progress`)
- Generic props: PascalCase, suffix `Props` (e.g., component props are implicit)

## Code Style

**Formatting:**
- Tool: No explicit prettier config found in platform root
- Inferred settings:
  - 2-space indentation (observed in config files)
  - Semicolons enabled (all TypeScript and JS files use semicolons)
  - Single quotes for most files (observed in platform code)

**Linting:**
- Tool: ESLint 8.57.0 (platform) and 8.57.0 (customer-portal-react)
- Config: `extends: "next/core-web-vitals"` in platform, `extends: "eslint:recommended"` + react plugins in React projects
- Key rules enforced: No unused variables, proper React hooks dependencies

**Strict TypeScript:**
- `strict: true` enabled in `tsconfig.json`
- All types must be explicitly defined
- No implicit `any` types
- `noEmit: true` for type checking (no runtime JS generation from tsc)

## Import Organization

**Order:**
1. External libraries (React, Next, third-party packages)
2. Internal type imports (`import type { ... } from "@/types"`)
3. Internal modules (`import { ... } from "@/lib"`, `"@/stores"`, `"@/components"`)
4. Relative imports (`./../utils`)

**Path Aliases:**
- `@/*` maps to `./src/*` (both platform and customer-portal-react)
- Use `@/` for all absolute imports from src/

**Examples from codebase:**
```typescript
// From support-chat.tsx
import { useState, useRef, useEffect, useCallback } from "react";
import { MessageCircle, X, Send, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";
```

```typescript
// From api.ts
import { useAuthStore } from "@/stores/auth-store";
import type {
  User,
  Job,
  JobItem,
  Address,
  BookingFormData,
  TrackingUpdate,
} from "@/types";
```

## Error Handling

**Patterns:**
- Custom error class: `ApiError` with status and data properties (in `api.ts`)
- Fetch wrapper catches JSON parsing errors and normalizes responses
- Conditional logging with console.error for debugging with context prefix (e.g., `[admin-map]`, `[tracking]`, `[socket]`)
- Promise rejection handling with try-catch in async functions

**Example:**
```typescript
class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}
```

**Client-side error display:**
- Store error state in form hooks (e.g., `useBookingForm` has `error` state)
- Validation functions return `null` on success, error message string on failure

## Logging

**Framework:** Console methods (`console.error`) with context labels

**Patterns:**
- Prefix with bracketed service name: `[admin-map]`, `[tracking]`, `[socket]`, `[socket]`
- Only error-level logging used in production code
- Format: `console.error("[context] message:", detail)`

**Backend (Python):**
- Standard `logging` module with `getLogger(__name__)`
- Logger names follow module name (e.g., `logging.getLogger("umuve.startup")`)
- Critical/warning levels for startup checks and environment validation
- Sentry integration for error monitoring when `SENTRY_DSN` is set

## Comments

**When to Comment:**
- Explain WHY, not WHAT (code should be self-documenting)
- Section separators with comment lines: `// ---------------------------------------------------------------------------`
- Used for grouping logical sections (Auth API, Booking API, Payments API, etc.)

**JSDoc/TSDoc:**
- Used sparingly for public API functions
- Example from `analytics.tsx`:
```typescript
/**
 * Analytics component that conditionally renders tracking scripts.
 *
 * Supports two providers:
 * - Google Analytics: set NEXT_PUBLIC_GA_ID (e.g., "G-XXXXXXXXXX")
 * - Plausible Analytics: set NEXT_PUBLIC_PLAUSIBLE_DOMAIN (e.g., "goumuve.com")
 *
 * If neither env var is set, this component renders nothing (safe for dev).
 */
export function Analytics() { ... }
```

## Function Design

**Size:** Most functions are 5-30 lines; API functions are concise (1-5 lines using arrow functions)

**Parameters:**
- Destructure props where practical: `({ className, ...props })`
- Use object parameters for multiple related arguments (e.g., `UseAdminMapSocketOptions`)
- Optional parameters in interfaces with `?` (e.g., `onContractorLocation?: (data) => void`)

**Return Values:**
- Explicit return types in TypeScript (e.g., `Promise<T>`, `Promise<{ success: boolean; job: Job }>`)
- Async functions return Promises with typed data payloads
- Validation functions return `null` (success) or error message string

**Async/await vs promises:**
- Async/await preferred for readability (all fetch wrappers use async)
- Promise chains used in some middleware patterns (e.g., Zustand persist)

## Module Design

**Exports:**
- Named exports for functions and components
- Default exports rarely used (mostly only for pages in Next.js)
- Barrel exports in index files (e.g., Card exports all sub-components from `ui/card.tsx`)

**Barrel Files:**
- `src/types/index.ts` exports all TypeScript type definitions
- `src/components/ui/card.tsx` exports Card, CardHeader, CardTitle, etc. as named exports

**Zustand Store Pattern:**
- Defined with `create<StateInterface>()(middleware(...))`
- Persist middleware configured with storage name and field selection
- Migration functions in `onRehydrateStorage` for legacy key fallbacks
- Example from `auth-store.ts`: Handles migration from `junkos-auth` to `umuve-auth` keys

## Special Patterns

**API Grouping:**
- Related API endpoints grouped in objects: `authApi`, `jobsApi`, `bookingApi`, `paymentsApi`
- Each endpoint is a concise arrow function: `(params) => apiFetch<ReturnType>(endpoint, options)`
- Comments separate logical groups with section headers

**Component Composition:**
- Use `React.forwardRef` for UI components that need ref forwarding (e.g., Card subcomponents)
- Set `displayName` on forwardRef components for dev tools
- Prop merging with `cn()` utility for Tailwind CSS classes and custom overrides

**Environment Configuration:**
- Environment variables: `process.env.NEXT_PUBLIC_*` for client (Next.js convention)
- Backend: `os.environ.get()` with defaults and validation during startup
- Critical env vars validated at startup in `server.py`

---

*Convention analysis: 2026-02-13*
