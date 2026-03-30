# Umuve Platform -- Test Plan

No test framework (Jest, Vitest, or similar) is currently configured in this
Next.js project.  The sections below document what **should** be tested once a
framework is added.

---

## Recommended Setup

Install Vitest (lighter and faster than Jest for Vite/Next.js projects):

```bash
npm install -D vitest @vitejs/plugin-react @testing-library/react @testing-library/jest-dom jsdom
```

Create `vitest.config.ts`:
```ts
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
  },
});
```

---

## Component Tests

### 1. Booking Flow Components

| Component | File | What to Test |
|-----------|------|--------------|
| `BookingForm` | `src/components/booking-form.*` | Form renders, required field validation, submit triggers API call, error states display |
| `PriceEstimate` | `src/components/price-estimate.*` | Renders estimate data, formats currency correctly, shows truck size |
| `AddressInput` | `src/components/address-input.*` | Autocomplete triggers, selected address populates lat/lng, validation message for empty input |
| `DateTimePicker` | `src/components/date-time-picker.*` | Renders available slots, disables past dates, selected value passes to parent |
| `ItemSelector` | `src/components/item-selector.*` | Add/remove items, quantity increment/decrement, category selection |
| `PromoCodeInput` | `src/components/promo-code.*` | Apply code triggers validation, success shows discount, invalid shows error |

### 2. Auth Components

| Component | What to Test |
|-----------|--------------|
| `LoginForm` | Email/password validation, successful login redirects, error message on 401, loading state |
| `SignupForm` | All required fields validated, password strength indicator, duplicate email error (409), redirect on success |
| `ProtectedRoute` | Redirects to login when no token, renders children when authenticated |

### 3. Dashboard / Customer Portal

| Component | What to Test |
|-----------|--------------|
| `BookingList` | Renders list of bookings, empty state when no bookings, status badges render correctly |
| `BookingDetail` | Shows all job fields, confirmation code displayed, driver info when assigned |
| `TrackingMap` | Map renders with service area polygon, driver marker updates on location change |

### 4. Operator Dashboard

| Component | What to Test |
|-----------|--------------|
| `OperatorJobList` | Filters by status, pagination works, delegate button triggers action |
| `FleetManagement` | Lists fleet contractors, invite code generation, removal confirmation dialog |
| `EarningsChart` | Renders chart with correct data, date range selector works |

---

## API Integration Tests (using MSW or similar)

Mock the backend API and test that:

1. **Estimate flow**: `POST /api/bookings/estimate` returns data that populates the UI
2. **Booking creation**: `POST /api/bookings/create` success shows confirmation, failure shows error
3. **Auth token handling**: Token stored after login, attached to subsequent requests, cleared on logout
4. **Service area check**: `POST /api/service-area/check` result shows/hides booking form
5. **Promo code flow**: `POST /api/promos/validate` result updates price display

---

## E2E Tests (Playwright or Cypress)

Full browser-based tests for critical paths:

1. **Happy path booking**: Land on homepage -> Enter address -> Select items -> See estimate -> Enter customer info -> Submit booking -> See confirmation
2. **Auth round trip**: Sign up -> Log out -> Log in -> See dashboard
3. **Operator flow**: Log in as operator -> View jobs -> Delegate a job -> Verify delegation
4. **Mobile responsive**: Booking flow completes on 375px viewport width
5. **Error recovery**: Network failure during booking shows retry option

---

## Priority Order

1. Booking flow components (highest business value)
2. Auth components (gate to all functionality)
3. API integration tests with mocked backend
4. E2E browser tests for critical happy paths
5. Operator dashboard components
6. Tracking and real-time features

---

## Running Tests (once configured)

```bash
# Unit + component tests
npx vitest

# Watch mode during development
npx vitest --watch

# With coverage
npx vitest --coverage
```
