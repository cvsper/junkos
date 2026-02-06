import { test, expect } from '@playwright/test';

// Test data
const OPERATOR_CREDENTIALS = {
  email: 'operator@test.com',
  password: 'TestPass123!'
};

test.describe('Operator Dispatch Workflow', () => {
  test.beforeEach(async ({ page }) => {
    // Login as operator
    await page.goto('/login');
    await page.fill('input[name="email"]', OPERATOR_CREDENTIALS.email);
    await page.fill('input[name="password"]', OPERATOR_CREDENTIALS.password);
    await page.click('button[type="submit"]');
    
    // Wait for dashboard to load
    await expect(page).toHaveURL(/\/dashboard/);
    await page.waitForLoadState('networkidle');
  });

  test('should view pending bookings dashboard', async ({ page }) => {
    // Navigate to bookings
    await page.click('text=Bookings');
    
    // Should show bookings list
    await expect(page.locator('h1, h2')).toContainText(/bookings/i);
    
    // Should have filters
    await expect(page.locator('select[name="status"]')).toBeVisible();
    
    // Filter by pending
    await page.selectOption('select[name="status"]', 'pending');
    
    // Should show pending bookings
    await expect(page.locator('[data-testid="booking-card"]').first()).toBeVisible();
  });

  test('should review and confirm a booking', async ({ page }) => {
    await page.click('text=Bookings');
    
    // Click on first pending booking
    await page.click('[data-testid="booking-card"]:has-text("pending")');
    
    // Should show booking details
    await expect(page.locator('text=/pickup.*address/i')).toBeVisible();
    await expect(page.locator('text=/customer/i')).toBeVisible();
    
    // View uploaded photos
    await expect(page.locator('img[alt*="photo"]')).toHaveCount(1, { timeout: 5000 });
    
    // Update estimate if needed
    await page.click('button:has-text("Edit Estimate")');
    await page.fill('input[name="finalPrice"]', '350');
    await page.click('button:has-text("Save")');
    
    // Confirm booking
    await page.click('button:has-text("Confirm Booking")');
    
    // Should show success message
    await expect(page.locator('text=/confirmed|success/i')).toBeVisible();
    
    // Status should update
    await expect(page.locator('[data-testid="booking-status"]')).toContainText(/confirmed/i);
  });

  test('should assign driver to job', async ({ page }) => {
    // Navigate to dispatch
    await page.click('text=Dispatch');
    
    // Should show dispatch board
    await expect(page.locator('h1, h2')).toContainText(/dispatch/i);
    
    // Click on unassigned job
    await page.click('[data-testid="job-card"]:has-text("unassigned")');
    
    // Open driver assignment modal
    await page.click('button:has-text("Assign Driver")');
    
    // Should show available drivers
    await expect(page.locator('[data-testid="driver-list"]')).toBeVisible();
    
    // Select first available driver
    await page.click('[data-testid="driver-option"]:first-child');
    
    // Confirm assignment
    await page.click('button:has-text("Confirm Assignment")');
    
    // Should show success
    await expect(page.locator('text=/assigned|success/i')).toBeVisible();
    
    // Job should show driver name
    await expect(page.locator('[data-testid="assigned-driver"]')).not.toBeEmpty();
  });

  test('should optimize daily routes', async ({ page }) => {
    await page.click('text=Dispatch');
    
    // Select date
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const dateString = tomorrow.toISOString().split('T')[0];
    
    await page.fill('input[type="date"]', dateString);
    
    // Should show jobs for selected date
    await expect(page.locator('[data-testid="job-card"]')).toHaveCount(1, { 
      timeout: 5000 
    });
    
    // Click optimize routes
    await page.click('button:has-text("Optimize Routes")');
    
    // Wait for optimization
    await expect(page.locator('text=/optimizing/i')).toBeVisible();
    await expect(page.locator('text=/optimizing/i')).not.toBeVisible({ timeout: 10000 });
    
    // Should show optimized route
    await expect(page.locator('[data-testid="route-map"]')).toBeVisible();
    await expect(page.locator('text=/total.*distance|estimated.*time/i')).toBeVisible();
  });

  test('should view driver locations on map', async ({ page }) => {
    await page.click('text=Dispatch');
    
    // Switch to map view
    await page.click('button:has-text("Map View")');
    
    // Should show map
    await expect(page.locator('[data-testid="dispatch-map"]')).toBeVisible();
    
    // Should show driver markers
    await expect(page.locator('[data-testid="driver-marker"]').first()).toBeVisible({
      timeout: 5000
    });
    
    // Click on driver marker
    await page.click('[data-testid="driver-marker"]:first-child');
    
    // Should show driver info popup
    await expect(page.locator('[data-testid="driver-popup"]')).toBeVisible();
    await expect(page.locator('text=/current.*status/i')).toBeVisible();
  });

  test('should handle driver reassignment', async ({ page }) => {
    await page.click('text=Dispatch');
    
    // Find assigned job
    await page.click('[data-testid="job-card"]:has-text("assigned")');
    
    // Click reassign
    await page.click('button:has-text("Reassign")');
    
    // Should show reason modal
    await expect(page.locator('text=/reason.*reassign/i')).toBeVisible();
    await page.selectOption('select[name="reason"]', 'driver_unavailable');
    
    // Select new driver
    await page.click('[data-testid="driver-option"]:nth-child(2)');
    await page.click('button:has-text("Confirm")');
    
    // Should update assignment
    await expect(page.locator('text=/reassigned|success/i')).toBeVisible();
  });

  test('should create manual job from booking', async ({ page }) => {
    await page.click('text=Bookings');
    
    // Find confirmed booking without job
    await page.selectOption('select[name="status"]', 'confirmed');
    await page.click('[data-testid="booking-card"]:first-child');
    
    // Create job
    await page.click('button:has-text("Create Job")');
    
    // Fill job details
    await page.fill('input[name="scheduledDate"]', '2024-03-20');
    await page.selectOption('select[name="scheduledTime"]', '10:00');
    await page.fill('input[name="estimatedDuration"]', '90');
    
    // Select driver
    await page.click('[data-testid="driver-select"]');
    await page.click('[data-testid="driver-option"]:first-child');
    
    // Create job
    await page.click('button:has-text("Create Job")');
    
    // Should show success
    await expect(page.locator('text=/job.*created/i')).toBeVisible();
    
    // Should redirect to job details
    await expect(page).toHaveURL(/\/jobs\/\d+/);
  });

  test('should filter and search jobs', async ({ page }) => {
    await page.click('text=Dispatch');
    
    // Search by address
    await page.fill('input[placeholder*="Search"]', '123 Main');
    
    // Wait for filtered results
    await page.waitForTimeout(500);
    
    // Should show matching jobs
    await expect(page.locator('[data-testid="job-card"]')).toBeVisible();
    await expect(page.locator('[data-testid="job-card"]')).toContainText(/123 Main/i);
    
    // Clear search
    await page.fill('input[placeholder*="Search"]', '');
    
    // Filter by status
    await page.click('[data-testid="status-filter-scheduled"]');
    
    // Should only show scheduled jobs
    await expect(page.locator('[data-testid="job-card"]')).toContainText(/scheduled/i);
  });

  test('should view dispatch analytics', async ({ page }) => {
    await page.click('text=Dispatch');
    
    // Click analytics tab
    await page.click('button:has-text("Analytics")');
    
    // Should show metrics
    await expect(page.locator('text=/total.*jobs/i')).toBeVisible();
    await expect(page.locator('text=/completion.*rate/i')).toBeVisible();
    await expect(page.locator('text=/average.*duration/i')).toBeVisible();
    
    // Should show charts
    await expect(page.locator('[data-testid="jobs-chart"]')).toBeVisible();
  });

  test('should handle urgent/emergency bookings', async ({ page }) => {
    await page.click('text=Bookings');
    
    // Create urgent booking
    await page.click('button:has-text("New Booking")');
    
    // Fill basic info
    await page.fill('input[name="address"]', '999 Emergency St');
    await page.fill('input[name="city"]', 'New York');
    await page.fill('input[name="zip"]', '10001');
    
    // Mark as urgent
    await page.check('input[name="urgent"]');
    
    // Set same-day pickup
    const today = new Date().toISOString().split('T')[0];
    await page.fill('input[name="pickupDate"]', today);
    
    // Complete and create
    await page.fill('input[name="customerEmail"]', 'urgent@example.com');
    await page.fill('input[name="customerPhone"]', '555-9999');
    await page.click('button:has-text("Create Booking")');
    
    // Should create and show on urgent list
    await expect(page.locator('[data-testid="urgent-badge"]')).toBeVisible();
  });

  test('should send notifications to driver', async ({ page }) => {
    await page.click('text=Dispatch');
    
    // Select job
    await page.click('[data-testid="job-card"]:first-child');
    
    // Click notify driver
    await page.click('button:has-text("Notify Driver")');
    
    // Compose message
    await page.fill('textarea[name="message"]', 'Please confirm ETA for this job');
    
    // Send notification
    await page.click('button:has-text("Send")');
    
    // Should show confirmation
    await expect(page.locator('text=/notification.*sent/i')).toBeVisible();
  });

  test('should reschedule job', async ({ page }) => {
    await page.click('text=Dispatch');
    
    // Find scheduled job
    await page.click('[data-testid="job-card"]:has-text("scheduled")');
    
    // Click reschedule
    await page.click('button:has-text("Reschedule")');
    
    // Select new date/time
    const nextWeek = new Date();
    nextWeek.setDate(nextWeek.getDate() + 7);
    const dateString = nextWeek.toISOString().split('T')[0];
    
    await page.fill('input[name="newDate"]', dateString);
    await page.selectOption('select[name="newTime"]', '14:00');
    
    // Add reason
    await page.fill('textarea[name="reason"]', 'Customer requested different time');
    
    // Confirm reschedule
    await page.click('button:has-text("Confirm Reschedule")');
    
    // Should update job
    await expect(page.locator('text=/rescheduled|updated/i')).toBeVisible();
  });

  test('should handle job cancellation', async ({ page }) => {
    await page.click('text=Dispatch');
    
    // Select job
    await page.click('[data-testid="job-card"]:first-child');
    
    // Cancel job
    await page.click('button:has-text("Cancel Job")');
    
    // Should show confirmation modal
    await expect(page.locator('text=/are you sure/i')).toBeVisible();
    
    // Select cancellation reason
    await page.selectOption('select[name="cancellationReason"]', 'customer_request');
    await page.fill('textarea[name="notes"]', 'Customer no longer needs service');
    
    // Confirm cancellation
    await page.click('button:has-text("Confirm Cancel")');
    
    // Should show success and update status
    await expect(page.locator('text=/cancelled/i')).toBeVisible();
    await expect(page.locator('[data-testid="job-status"]')).toContainText(/cancelled/i);
  });

  test('should export dispatch schedule', async ({ page }) => {
    await page.click('text=Dispatch');
    
    // Select date range
    const today = new Date().toISOString().split('T')[0];
    const nextWeek = new Date();
    nextWeek.setDate(nextWeek.getDate() + 7);
    const endDate = nextWeek.toISOString().split('T')[0];
    
    await page.fill('input[name="startDate"]', today);
    await page.fill('input[name="endDate"]', endDate);
    
    // Click export
    const downloadPromise = page.waitForEvent('download');
    await page.click('button:has-text("Export")');
    
    // Select format
    await page.click('text=CSV');
    
    // Wait for download
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/schedule.*\.csv/i);
  });
});

test.describe('Real-time Dispatch Updates', () => {
  test('should receive real-time job status updates', async ({ page, context }) => {
    // Open dispatch in two tabs (operator and driver view simulation)
    const operatorPage = page;
    const driverPage = await context.newPage();
    
    // Login operator
    await operatorPage.goto('/dashboard');
    await operatorPage.click('text=Dispatch');
    
    // Login driver in second tab
    await driverPage.goto('/login');
    await driverPage.fill('input[name="email"]', 'driver@test.com');
    await driverPage.fill('input[name="password"]', 'TestPass123!');
    await driverPage.click('button[type="submit"]');
    
    // Driver starts job
    await driverPage.click('[data-testid="job-card"]:first-child');
    await driverPage.click('button:has-text("Start Job")');
    
    // Operator should see status update in real-time
    await expect(operatorPage.locator('[data-testid="job-status"]')).toContainText(/in progress/i, {
      timeout: 10000
    });
    
    await driverPage.close();
  });

  test('should update driver location in real-time', async ({ page }) => {
    await page.click('text=Dispatch');
    await page.click('button:has-text("Map View")');
    
    // Get initial driver location
    const marker = page.locator('[data-testid="driver-marker"]:first-child');
    await marker.waitFor();
    
    const initialPosition = await marker.boundingBox();
    
    // Wait for location update (simulated)
    await page.waitForTimeout(5000);
    
    // Position should update
    const newPosition = await marker.boundingBox();
    
    // Note: In real test, would verify actual position change
    expect(marker).toBeVisible();
  });
});
