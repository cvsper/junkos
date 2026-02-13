# Testing Patterns

**Analysis Date:** 2026-02-13

## Test Framework

**Runner:**
- Jest 29.7.0 (customer-portal-react)
- Vitest (not configured; only Jest/Playwright in use)
- Playwright 1.41.0 (E2E tests)
- Config locations:
  - `customer-portal-react/jest.config.js` — Jest configuration for React tests
  - `e2e/playwright.config.js` — Playwright E2E test configuration

**Assertion Library:**
- Jest matchers (expect, toHaveBeenCalled, toBeInTheDocument, etc.)
- Playwright assertions (expect, toBeVisible, toContainText, etc.)

**Run Commands:**
```bash
# customer-portal-react (React tests)
npm test              # Run all tests
npm run test:watch   # Watch mode
npm run test:coverage # Coverage report

# E2E tests
npm run test:e2e      # Run E2E tests
npm run test:e2e:ui   # UI mode for debugging
```

## Test File Organization

**Location - React Tests:**
- Pattern: `tests/` directory at project root
- Alternative: `src/**/__tests__/` (configured as testMatch option)
- Location: `/Users/sevs/Documents/Programs/webapps/junkos/customer-portal-react/tests/`

**Location - E2E Tests:**
- Pattern: `e2e/tests/` directory
- Location: `/Users/sevs/Documents/Programs/webapps/junkos/e2e/tests/`

**Naming:**
- Jest: `.test.jsx`, `.test.js` suffix
- Playwright: `.spec.js` suffix

**File Structure Example:**
```
customer-portal-react/
├── tests/
│   ├── api.test.js
│   ├── PhotoUpload.test.jsx
│   ├── BookingFlow.test.jsx
│   └── setup.js
└── src/
    └── __tests__/ (alternative location)
```

## Test Structure

**Jest Suite Organization:**
```javascript
describe('API Service', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
  });

  describe('Authentication', () => {
    test('login sends credentials and stores token', async () => {
      // Test implementation
    });
  });

  describe('Error Handling', () => {
    test('handles network errors gracefully', () => {
      // Test implementation
    });
  });
});
```

**Playwright Suite Organization:**
```javascript
test.describe('Complete Booking Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should complete full booking journey from start to confirmation', async ({ page }) => {
    // Test implementation
  });
});
```

**Patterns:**
- Setup: `beforeEach()` for mocks, localStorage reset, page navigation
- Teardown: Automatic in Jest/Playwright (no explicit cleanup needed for mocks)
- Assertion order: Arrange, Act, Assert (AAA pattern)

## Mocking

**Framework:** Jest mocks (jest.mock, jest.fn)

**Patterns - Module Mocking:**
```javascript
// Mock entire module
jest.mock('../src/services/api');

// Mock specific axios instance
jest.mock('axios');
axios.post.mockResolvedValue(mockResponse);
```

**Patterns - Manual Mocks:**
```javascript
// Mock URL API for file handling
global.URL.createObjectURL = jest.fn(() => 'mock-url');

// Mock fetch responses
const mockResponse = {
  data: {
    token: 'mock-jwt-token',
    user: { id: 1, email: 'test@example.com' }
  }
};
axios.post.mockResolvedValue(mockResponse);
```

**What to Mock:**
- External API calls (axios, fetch)
- Complex dependencies (services, utilities)
- Browser APIs that don't work in jsdom (URL.createObjectURL, etc.)
- Zustand stores (where needed)

**What NOT to Mock:**
- React hooks (use real React)
- DOM rendering (test actual component behavior)
- User interactions (use React Testing Library's userEvent)
- Date/time operations (unless explicitly testing date logic)

## Fixtures and Factories

**Test Data Pattern:**
```javascript
// From api.test.js
const mockResponse = {
  data: {
    token: 'mock-jwt-token',
    user: { id: 1, email: 'test@example.com' }
  }
};

// From PhotoUpload.test.jsx
const file = new File(['photo'], 'test.jpg', { type: 'image/jpeg' });
const files = [
  new File(['photo1'], 'test1.jpg', { type: 'image/jpeg' }),
  new File(['photo2'], 'test2.jpg', { type: 'image/jpeg' }),
];
```

**Location:**
- Inline in test files (no separate fixtures directory detected)
- Mock data created on-demand in tests
- `setup.js` in `tests/` directory for global test setup

## Coverage

**Requirements:** 70% threshold enforced in Jest config
```javascript
coverageThreshold: {
  global: {
    branches: 70,
    functions: 70,
    lines: 70,
    statements: 70,
  },
}
```

**View Coverage:**
```bash
npm run test:coverage
```

**Output:** Coverage reports generated in default Jest HTML format

## Test Types

**Unit Tests (Jest):**
- Scope: Individual functions, components, API calls
- Approach: Isolated with mocks for dependencies
- Example: `api.test.js` tests API service functions independently
- Example: `PhotoUpload.test.jsx` tests component with mocked API and file handling

**Integration Tests:**
- Not explicitly configured or found
- E2E tests serve as full integration tests

**E2E Tests (Playwright):**
- Framework: Playwright 1.41.0
- Scope: Complete user workflows (booking flow, operator dispatch)
- Approach: Real browser, real API endpoints (or stubbed)
- Config: `e2e/playwright.config.js`
- Devices tested:
  - Desktop: Chromium, Firefox, WebKit
  - Mobile: Chrome (Pixel 5), Safari (iPhone 12)
- Features:
  - Retries: 2 on CI, 0 locally
  - Screenshots: On failure only
  - Video: Retained on failure
  - Trace: Recorded on first retry for debugging

## Common Patterns

**Async Testing (Jest with React Testing Library):**
```javascript
test('allows selecting files via file input', async () => {
  const user = userEvent.setup();
  const handleChange = jest.fn();
  render(<PhotoUpload onPhotosChange={handleChange} />);

  const file = new File(['photo'], 'test.jpg', { type: 'image/jpeg' });
  const input = screen.getByLabelText(/upload photos/i, { selector: 'input' });

  await user.upload(input, file);

  await waitFor(() => {
    expect(handleChange).toHaveBeenCalled();
  });
});
```

**Error Testing:**
```javascript
test('register creates new user account', async () => {
  const userData = {
    email: 'new@example.com',
    password: 'SecurePass123!',
    first_name: 'John',
    last_name: 'Doe',
    phone: '555-1234'
  };

  const mockResponse = {
    data: {
      token: 'new-token',
      user: { ...userData, id: 2 }
    }
  };
  axios.post.mockResolvedValue(mockResponse);

  const result = await register(userData);

  expect(axios.post).toHaveBeenCalledWith('/api/auth/register', userData);
  expect(result.user.email).toBe('new@example.com');
});
```

**User Interaction Testing (Playwright):**
```javascript
test('should complete full booking journey from start to confirmation', async ({ page }) => {
  // Step 1: Landing and start booking
  await expect(page.locator('h1')).toContainText(/junk removal|book now/i);
  await page.click('text=Book Now');

  // Step 2: Enter address information
  await page.fill('input[name="address"]', '123 Main Street');
  await page.click('button:has-text("Next")');

  // Assertions
  await expect(page.locator('text=/\\$\\d+/')).toBeVisible();
});
```

## Test Configuration Details

**Jest Config (`customer-portal-react/jest.config.js`):**
```javascript
export default {
  testEnvironment: 'jsdom',                           // Browser environment
  setupFilesAfterEnv: ['<rootDir>/tests/setup.js'],  // Global setup
  moduleNameMapper: {
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy', // Mock styles
    '^@/(.*)$': '<rootDir>/src/$1',                   // Path aliases
  },
  transform: {
    '^.+\\.(js|jsx)$': ['babel-jest', { presets: [...] }], // Babel transform
  },
  collectCoverageFrom: [
    'src/**/*.{js,jsx}',
    '!src/main.jsx',
    '!src/**/*.test.{js,jsx}',
    '!src/**/__tests__/**',
  ],
  testMatch: [
    '<rootDir>/tests/**/*.test.{js,jsx}',
    '<rootDir>/src/**/__tests__/**/*.{js,jsx}',
  ],
};
```

**Playwright Config (`e2e/playwright.config.js`):**
```javascript
{
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html'],
    ['json', { outputFile: 'test-results/results.json' }],
    ['junit', { outputFile: 'test-results/junit.xml' }]
  ],
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: {
    command: 'npm run dev',
    port: 5173,
    reuseExistingServer: !process.env.CI,
  },
}
```

## Testing Best Practices Observed

1. **Test isolation:** Each test clears mocks and localStorage in beforeEach
2. **User-centric testing:** Using React Testing Library's getByRole, getByLabelText (user perspective)
3. **Async handling:** Proper use of async/await and waitFor for async operations
4. **Mock management:** jest.clearAllMocks() between tests prevents leakage
5. **File handling:** Tests create mock File objects for upload scenarios
6. **Responsive testing:** Playwright tests both desktop and mobile viewports
7. **Failure artifacts:** Screenshots and videos on failure for debugging

## Test Coverage Gaps Identified

- **Platform (Next.js):** No test files found in `platform/src/` — zero test coverage
- **Backend (Flask):** No test files found in `backend/` — zero test coverage
- **E2E coverage:** Limited to critical user flows (booking, dispatch) — not comprehensive

---

*Testing analysis: 2026-02-13*
