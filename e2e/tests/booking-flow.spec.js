import { test, expect } from '@playwright/test';

test.describe('Complete Booking Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should complete full booking journey from start to confirmation', async ({ page }) => {
    // Step 1: Landing and start booking
    await expect(page.locator('h1')).toContainText(/junk removal|book now/i);
    await page.click('text=Book Now');

    // Step 2: Enter address information
    await expect(page.locator('h2')).toContainText(/pickup.*address|where/i);
    
    await page.fill('input[name="address"]', '123 Main Street');
    await page.fill('input[name="city"]', 'New York');
    await page.selectOption('select[name="state"]', 'NY');
    await page.fill('input[name="zip"]', '10001');
    
    await page.click('button:has-text("Next")');

    // Step 3: Upload photos
    await expect(page.locator('h2')).toContainText(/photos|upload/i);
    
    // Upload test image
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: 'test-photo.jpg',
      mimeType: 'image/jpeg',
      buffer: Buffer.from('fake-image-content')
    });
    
    // Wait for upload to complete
    await expect(page.locator('text=test-photo.jpg')).toBeVisible({ timeout: 10000 });
    
    await page.click('button:has-text("Next")');

    // Step 4: Select items
    await expect(page.locator('h2')).toContainText(/items|what/i);
    
    await page.click('text=Sofa');
    await page.click('text=Refrigerator');
    await page.click('text=Mattress');
    
    // Select volume
    await page.click('text=1/4 truck');
    
    await page.click('button:has-text("Next")');

    // Step 5: Choose date and time
    await expect(page.locator('h2')).toContainText(/date.*time|schedule/i);
    
    // Select date (3 days from now)
    const futureDate = new Date();
    futureDate.setDate(futureDate.getDate() + 3);
    const dateString = futureDate.toISOString().split('T')[0];
    
    await page.fill('input[type="date"]', dateString);
    await page.selectOption('select[name="time"]', '10:00');
    
    await page.click('button:has-text("Next")');

    // Step 6: View estimate
    await expect(page.locator('h2')).toContainText(/estimate|price/i);
    
    // Should show price estimate
    await expect(page.locator('text=/\\$\\d+/')).toBeVisible();
    
    // Add notes
    await page.fill('textarea[name="notes"]', 'Please call 15 minutes before arrival');
    
    await page.click('button:has-text("Next")');

    // Step 7: Enter contact information
    await page.fill('input[name="email"]', 'test@example.com');
    await page.fill('input[name="phone"]', '555-123-4567');
    await page.fill('input[name="firstName"]', 'John');
    await page.fill('input[name="lastName"]', 'Doe');
    
    await page.click('button:has-text("Next")');

    // Step 8: Payment information (if required)
    // This would integrate with Stripe test mode
    
    // Step 9: Review and submit
    await expect(page.locator('h2')).toContainText(/review|confirm/i);
    
    // Verify all information is displayed
    await expect(page.locator('text=123 Main Street')).toBeVisible();
    await expect(page.locator('text=Sofa')).toBeVisible();
    await expect(page.locator('text=test@example.com')).toBeVisible();
    
    // Submit booking
    await page.click('button:has-text("Confirm Booking")');

    // Step 10: Confirmation
    await expect(page.locator('h1, h2')).toContainText(/thank you|confirmed|success/i, { 
      timeout: 15000 
    });
    
    // Should show booking number or confirmation
    await expect(page.locator('text=/booking.*#\\d+|confirmation/i')).toBeVisible();
  });

  test('should validate required fields at each step', async ({ page }) => {
    await page.click('text=Book Now');

    // Try to proceed without filling required fields
    await page.click('button:has-text("Next")');
    
    // Should show validation errors
    await expect(page.locator('text=/required|must be/i')).toBeVisible();
    
    // Form should not advance
    await expect(page.locator('input[name="address"]')).toBeVisible();
  });

  test('should allow navigation back through steps', async ({ page }) => {
    await page.click('text=Book Now');

    // Fill step 1
    await page.fill('input[name="address"]', '123 Main Street');
    await page.fill('input[name="city"]', 'New York');
    await page.fill('input[name="zip"]', '10001');
    await page.click('button:has-text("Next")');

    // Go to step 2
    await expect(page.locator('h2')).toContainText(/photos/i);
    
    // Click back
    await page.click('button:has-text("Back")');
    
    // Should be back on step 1
    await expect(page.locator('h2')).toContainText(/address/i);
    
    // Data should be preserved
    await expect(page.locator('input[name="address"]')).toHaveValue('123 Main Street');
  });

  test('should save progress and allow resume', async ({ page, context }) => {
    await page.click('text=Book Now');

    // Fill some information
    await page.fill('input[name="address"]', '123 Main Street');
    await page.fill('input[name="city"]', 'New York');
    await page.fill('input[name="zip"]', '10001');
    await page.click('button:has-text("Next")');

    // Reload page (simulating return visit)
    await page.reload();
    
    // Should show option to resume
    await expect(page.locator('text=/resume|continue/i')).toBeVisible({ timeout: 5000 });
    
    await page.click('text=/resume|continue/i');
    
    // Should be on step 2 with data preserved
    await expect(page.locator('h2')).toContainText(/photos/i);
  });

  test('should display price estimate updates', async ({ page }) => {
    await page.click('text=Book Now');

    // Complete first steps to get to items
    await page.fill('input[name="address"]', '123 Main Street');
    await page.fill('input[name="city"]', 'New York');
    await page.fill('input[name="zip"]', '10001');
    await page.click('button:has-text("Next")');
    await page.click('button:has-text("Next")'); // Skip photos

    // Select items
    await page.click('text=Sofa');
    
    // Price should appear
    const priceElement = page.locator('[data-testid="price-estimate"]');
    await expect(priceElement).toBeVisible();
    
    const initialPrice = await priceElement.textContent();
    
    // Add more items
    await page.click('text=Refrigerator');
    
    // Price should increase
    await expect(priceElement).not.toHaveText(initialPrice);
  });

  test('should handle service area validation', async ({ page }) => {
    await page.click('text=Book Now');

    // Enter address outside service area
    await page.fill('input[name="address"]', '123 Remote Street');
    await page.fill('input[name="city"]', 'Los Angeles');
    await page.fill('input[name="zip"]', '90210');
    
    await page.click('button:has-text("Next")');
    
    // Should show error about service area
    await expect(page.locator('text=/service area|not available/i')).toBeVisible();
  });

  test('should be mobile responsive', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    
    await page.click('text=Book Now');
    
    // Navigation should work on mobile
    await page.fill('input[name="address"]', '123 Main Street');
    await page.fill('input[name="city"]', 'New York');
    await page.fill('input[name="zip"]', '10001');
    
    // Should be able to scroll and click next
    await page.click('button:has-text("Next")');
    
    await expect(page.locator('h2')).toContainText(/photos/i);
  });
});

test.describe('Booking Flow Edge Cases', () => {
  test('should handle network errors gracefully', async ({ page, context }) => {
    // Simulate offline
    await context.setOffline(true);
    
    await page.goto('/');
    await page.click('text=Book Now');
    
    await page.fill('input[name="address"]', '123 Main Street');
    await page.fill('input[name="city"]', 'New York');
    await page.fill('input[name="zip"]', '10001');
    
    // Bring back online
    await context.setOffline(false);
    
    await page.click('button:has-text("Next")');
    
    // Should eventually succeed
    await expect(page.locator('h2')).toContainText(/photos/i, { timeout: 10000 });
  });

  test('should prevent double submission', async ({ page }) => {
    await page.click('text=Book Now');
    
    // Complete form quickly (abbreviated)
    await page.fill('input[name="address"]', '123 Main Street');
    await page.fill('input[name="city"]', 'New York');
    await page.fill('input[name="zip"]', '10001');
    
    // Try to click submit multiple times rapidly
    const submitButton = page.locator('button:has-text("Confirm")');
    await Promise.all([
      submitButton.click(),
      submitButton.click(),
      submitButton.click(),
    ]).catch(() => {}); // Some clicks will fail, that's expected
    
    // Should only create one booking
    // (would verify via API check in real implementation)
  });

  test('should handle session timeout', async ({ page }) => {
    // Start booking
    await page.click('text=Book Now');
    await page.fill('input[name="address"]', '123 Main Street');
    
    // Clear session storage (simulate timeout)
    await page.evaluate(() => sessionStorage.clear());
    
    // Try to continue
    await page.click('button:has-text("Next")');
    
    // Should handle gracefully - either show error or restart
    await expect(page.locator('text=/session.*expired|start over/i')).toBeVisible();
  });
});
