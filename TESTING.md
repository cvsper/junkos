# Umuve Testing Guide

Comprehensive testing setup for the Umuve junk removal SaaS platform. This document covers backend tests, frontend tests, E2E tests, and CI/CD integration.

## Table of Contents

- [Overview](#overview)
- [Backend Tests](#backend-tests)
- [Frontend Tests](#frontend-tests)
- [E2E Tests](#e2e-tests)
- [Running Tests](#running-tests)
- [Coverage Goals](#coverage-goals)
- [CI/CD Integration](#cicd-integration)
- [Writing Tests](#writing-tests)

## Overview

Umuve uses a multi-layered testing strategy:

- **Backend (Python/Flask)**: pytest with fixtures and factories
- **Frontend (React)**: Jest + React Testing Library
- **E2E (Full stack)**: Playwright for user journey testing
- **CI/CD**: GitHub Actions for automated testing on PRs

### Coverage Goals

| Layer | Coverage Target | Current |
|-------|----------------|---------|
| Backend | 70%+ | - |
| Frontend | 70%+ | - |
| E2E | Critical paths | - |

## Backend Tests

### Location
```
backend/
├── tests/
│   ├── conftest.py          # Fixtures and test setup
│   ├── test_auth.py         # Authentication tests
│   ├── test_bookings.py     # Booking CRUD tests
│   ├── test_jobs.py         # Job lifecycle tests
│   ├── test_dispatch.py     # Dispatch logic tests
│   └── test_payments.py     # Payment processing tests
└── pytest.ini               # Pytest configuration
```

### Installation

```bash
cd backend
pip install -r requirements.txt
pip install -r requirements-test.txt
```

### Running Backend Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html --cov-report=term

# Run specific test file
pytest tests/test_auth.py

# Run specific test class
pytest tests/test_auth.py::TestLogin

# Run specific test
pytest tests/test_auth.py::TestLogin::test_login_success

# Run with verbose output
pytest -v

# Run and stop on first failure
pytest -x

# Run only failed tests from last run
pytest --lf

# Watch mode (requires pytest-watch)
ptw
```

### Test Structure

```python
def test_feature_name(client, auth_headers, test_booking):
    """Test description"""
    # Arrange - Set up test data
    data = {'key': 'value'}
    
    # Act - Perform action
    response = client.post('/api/endpoint', 
        headers=auth_headers, 
        json=data
    )
    
    # Assert - Verify results
    assert response.status_code == 200
    assert 'expected' in response.json()
```

### Key Fixtures

- `app` - Flask application instance
- `client` - Test client for HTTP requests
- `db_session` - Database session with transaction rollback
- `test_customer` - Sample customer user
- `test_operator` - Sample operator user
- `test_driver` - Sample driver user
- `auth_headers` - JWT auth headers
- `test_booking` - Sample booking
- `test_job` - Sample job

## Frontend Tests

### Location
```
frontend/
├── tests/
│   ├── setup.js                  # Jest setup
│   ├── BookingFlow.test.jsx      # Booking flow tests
│   ├── PhotoUpload.test.jsx      # Photo upload tests
│   └── api.test.js               # API client tests
└── jest.config.js                # Jest configuration
```

### Installation

```bash
cd frontend
npm install
```

### Running Frontend Tests

```bash
# Run all tests
npm test

# Run with coverage
npm run test:coverage

# Watch mode
npm run test:watch

# Run specific test file
npm test BookingFlow.test.jsx

# Update snapshots
npm test -- -u

# Run in CI mode
npm test -- --ci --coverage
```

### Test Structure

```jsx
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

test('should do something', async () => {
  const user = userEvent.setup();
  
  // Render component
  render(<Component prop="value" />);
  
  // Find elements
  const button = screen.getByRole('button', { name: /click me/i });
  
  // Interact
  await user.click(button);
  
  // Assert
  expect(screen.getByText(/success/i)).toBeInTheDocument();
});
```

### Testing Patterns

**Component Testing:**
```jsx
import { render, screen } from '@testing-library/react';

test('renders component correctly', () => {
  render(<BookingForm />);
  expect(screen.getByLabelText(/address/i)).toBeInTheDocument();
});
```

**User Interactions:**
```jsx
import userEvent from '@testing-library/user-event';

test('handles form submission', async () => {
  const user = userEvent.setup();
  const handleSubmit = jest.fn();
  
  render(<Form onSubmit={handleSubmit} />);
  
  await user.type(screen.getByLabelText(/name/i), 'John');
  await user.click(screen.getByRole('button', { name: /submit/i }));
  
  expect(handleSubmit).toHaveBeenCalled();
});
```

**API Mocking:**
```jsx
import * as api from '../services/api';

jest.mock('../services/api');

test('fetches and displays data', async () => {
  api.getBookings.mockResolvedValue({ bookings: [...] });
  
  render(<BookingList />);
  
  await waitFor(() => {
    expect(screen.getByText(/booking #1/i)).toBeInTheDocument();
  });
});
```

## E2E Tests

### Location
```
e2e/
├── tests/
│   ├── booking-flow.spec.js      # Complete booking journey
│   └── operator-dispatch.spec.js # Operator workflow
└── playwright.config.js          # Playwright configuration
```

### Installation

```bash
cd e2e
npm install
npx playwright install
```

### Running E2E Tests

```bash
# Run all E2E tests
npm run test:e2e

# Run in UI mode (interactive)
npm run test:e2e:ui

# Run specific test file
npx playwright test booking-flow.spec.js

# Run in headed mode (see browser)
npx playwright test --headed

# Run specific browser
npx playwright test --project=chromium

# Debug mode
npx playwright test --debug

# Generate test report
npx playwright show-report
```

### Test Structure

```javascript
import { test, expect } from '@playwright/test';

test('user journey', async ({ page }) => {
  // Navigate
  await page.goto('/');
  
  // Interact
  await page.click('text=Book Now');
  await page.fill('input[name="address"]', '123 Main St');
  await page.click('button:has-text("Next")');
  
  // Assert
  await expect(page).toHaveURL(/\/booking\/step2/);
  await expect(page.locator('h2')).toContainText(/photos/i);
});
```

### E2E Best Practices

1. **Use data-testid attributes** for stable selectors
2. **Wait for network idle** on page loads
3. **Use proper assertions** with expect()
4. **Clean up test data** after runs
5. **Test critical paths only** (E2E is slow)

## Running All Tests

### Local Development

```bash
# Backend tests
cd backend && pytest

# Frontend tests
cd frontend && npm test

# E2E tests (requires backend + frontend running)
cd backend && python run.py &
cd frontend && npm run dev &
cd e2e && npm run test:e2e
```

### Quick Test Script

Create a `test-all.sh` script:

```bash
#!/bin/bash
set -e

echo "🧪 Running Backend Tests..."
cd backend && pytest --cov=app --cov-report=term

echo "🧪 Running Frontend Tests..."
cd ../frontend && npm test -- --coverage

echo "🧪 Running E2E Tests..."
cd ../e2e && npx playwright test --project=chromium

echo "✅ All tests passed!"
```

Make it executable:
```bash
chmod +x test-all.sh
./test-all.sh
```

## Coverage Goals

### Backend Coverage (70%+)

Focus areas:
- ✅ Authentication & authorization
- ✅ Booking CRUD operations
- ✅ Job lifecycle management
- ✅ Dispatch algorithms
- ✅ Payment processing
- ⚠️ Error handling paths
- ⚠️ Edge cases

### Frontend Coverage (70%+)

Focus areas:
- ✅ Booking flow components
- ✅ Form validation
- ✅ API integration
- ✅ User interactions
- ⚠️ Error boundaries
- ⚠️ Loading states

### E2E Coverage (Critical Paths)

Priority flows:
- ✅ Customer booking journey
- ✅ Operator job assignment
- ✅ Driver job completion
- ✅ Payment processing
- ⚠️ Error recovery

## CI/CD Integration

Tests run automatically on:
- Every push to `main` or `develop`
- Every pull request

### GitHub Actions Workflow

See `.github/workflows/test.yml` for complete configuration.

Pipeline stages:
1. **Backend Tests** - Pytest with PostgreSQL
2. **Frontend Tests** - Jest with coverage
3. **E2E Tests** - Playwright on Chromium
4. **Coverage Report** - Combined coverage to Codecov

### CI Requirements

- Backend tests must pass
- Frontend tests must pass
- E2E tests must pass
- Coverage must meet 70% threshold
- No linting errors

### Viewing Test Results

After CI runs:
1. Check GitHub Actions tab
2. View test summaries
3. Download artifacts (coverage reports, screenshots)
4. Review Codecov report on PR

## Writing Tests

### Backend Test Template

```python
class TestFeature:
    """Test suite for feature"""
    
    def test_success_case(self, client, auth_headers):
        """Test successful operation"""
        response = client.post('/api/endpoint',
            headers=auth_headers,
            json={'data': 'value'}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['result'] == 'expected'
    
    def test_validation_error(self, client, auth_headers):
        """Test validation fails appropriately"""
        response = client.post('/api/endpoint',
            headers=auth_headers,
            json={'invalid': 'data'}
        )
        
        assert response.status_code == 400
        assert 'error' in response.json()
    
    def test_unauthorized_access(self, client):
        """Test authentication is required"""
        response = client.post('/api/endpoint')
        assert response.status_code == 401
```

### Frontend Test Template

```jsx
describe('Component', () => {
  test('renders correctly', () => {
    render(<Component />);
    expect(screen.getByText(/expected/i)).toBeInTheDocument();
  });
  
  test('handles user interaction', async () => {
    const user = userEvent.setup();
    const handleClick = jest.fn();
    
    render(<Component onClick={handleClick} />);
    
    await user.click(screen.getByRole('button'));
    
    expect(handleClick).toHaveBeenCalled();
  });
  
  test('handles errors gracefully', async () => {
    api.fetchData.mockRejectedValue(new Error('Failed'));
    
    render(<Component />);
    
    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument();
    });
  });
});
```

### E2E Test Template

```javascript
test.describe('Feature', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    // Setup test data
  });
  
  test('completes user journey', async ({ page }) => {
    // Step 1
    await page.click('text=Start');
    await expect(page).toHaveURL(/\/step1/);
    
    // Step 2
    await page.fill('input[name="field"]', 'value');
    await page.click('button:has-text("Next")');
    
    // Step 3
    await expect(page.locator('text=Success')).toBeVisible();
  });
});
```

## Debugging Tests

### Backend

```bash
# Run with print statements visible
pytest -s

# Drop into debugger on failure
pytest --pdb

# Run single test with verbose output
pytest -vv tests/test_auth.py::test_login_success
```

### Frontend

```bash
# Run tests in watch mode
npm run test:watch

# Debug specific test
node --inspect-brk node_modules/.bin/jest --runInBand BookingFlow.test.jsx

# Use console.log (will show in output)
```

### E2E

```bash
# Run in headed mode (see browser)
npx playwright test --headed

# Debug mode (step through)
npx playwright test --debug

# Slow down execution
npx playwright test --headed --slow-mo=1000

# Take screenshots
npx playwright test --screenshot=on
```

## Troubleshooting

### Backend Tests Fail

```bash
# Check database connection
psql -h localhost -U umuve_test -d umuve_test

# Reset test database
cd backend && flask db upgrade

# Check Python version
python --version  # Should be 3.11+
```

### Frontend Tests Fail

```bash
# Clear Jest cache
npm test -- --clearCache

# Check Node version
node --version  # Should be 20+

# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install
```

### E2E Tests Fail

```bash
# Update Playwright browsers
npx playwright install

# Check servers are running
curl http://localhost:5000/health  # Backend
curl http://localhost:5173         # Frontend

# View test traces
npx playwright show-trace trace.zip
```

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Jest Documentation](https://jestjs.io/)
- [React Testing Library](https://testing-library.com/react)
- [Playwright Documentation](https://playwright.dev/)
- [Vibetesting Patterns](https://www.vibetesting.dev/)

## Contributing

When adding new features:
1. Write tests first (TDD)
2. Ensure all tests pass
3. Maintain coverage above 70%
4. Add E2E tests for critical paths
5. Update this README if needed

---

**Last Updated:** February 6, 2024  
**Maintained by:** Umuve Development Team
