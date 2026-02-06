-- ============================================================================
-- Common SQL Queries for Junk Removal SaaS Platform
-- ============================================================================
-- These examples demonstrate typical operations you'll perform frequently.
-- Replace $1, $2, etc. with actual parameter values in your application.
-- ============================================================================

-- ============================================================================
-- 1. TENANT & USER SETUP
-- ============================================================================

-- Create a new tenant (onboarding)
INSERT INTO tenants (name, slug, contact_email, status, subscription_tier)
VALUES ('Acme Junk Removal', 'acme-junk', 'admin@acmejunk.com', 'trial', 'pro')
RETURNING id, slug, trial_ends_at;

-- Create initial admin user for tenant
INSERT INTO users (tenant_id, email, password_hash, first_name, last_name, role, status)
VALUES (
  $tenant_id,
  'admin@acmejunk.com',
  $password_hash, -- Use bcrypt in application layer
  'John',
  'Doe',
  'admin',
  'active'
)
RETURNING id;

-- Add a dispatcher
INSERT INTO users (tenant_id, email, password_hash, first_name, last_name, role, phone)
VALUES ($tenant_id, 'dispatch@acmejunk.com', $password_hash, 'Jane', 'Smith', 'dispatcher', '555-0100');

-- Add a driver with vehicle info
INSERT INTO users (
  tenant_id, email, password_hash, first_name, last_name, role, phone,
  driver_license_number, driver_license_expiry, vehicle_info
)
VALUES (
  $tenant_id,
  'driver@acmejunk.com',
  $password_hash,
  'Mike',
  'Johnson',
  'driver',
  '555-0101',
  'DL123456',
  '2026-12-31',
  '{"type": "truck", "make": "Ford", "model": "F-150", "year": 2022, "plate": "ABC123", "capacity_cubic_yards": 12}'::jsonb
);

-- ============================================================================
-- 2. CUSTOMER MANAGEMENT
-- ============================================================================

-- Add new customer
INSERT INTO customers (
  tenant_id, first_name, last_name, email, phone,
  address_line1, city, state, postal_code, latitude, longitude
)
VALUES (
  $tenant_id,
  'Sarah',
  'Williams',
  'sarah@example.com',
  '555-0200',
  '123 Main St',
  'Springfield',
  'IL',
  '62701',
  39.7817, -- Geocoded from address
  -89.6501
)
RETURNING id;

-- Find customer by phone
SELECT id, first_name, last_name, email, address_line1, city, state, total_jobs_completed
FROM customers
WHERE tenant_id = $tenant_id
  AND phone = $phone
  AND deleted_at IS NULL;

-- Search customers by name or email (full-text search)
SELECT id, first_name || ' ' || last_name AS name, email, phone, city, total_jobs_completed
FROM customers
WHERE tenant_id = $tenant_id
  AND deleted_at IS NULL
  AND to_tsvector('english', coalesce(first_name, '') || ' ' || coalesce(last_name, '') || ' ' || coalesce(email, ''))
      @@ plainto_tsquery('english', $search_term)
LIMIT 20;

-- Update customer's total stats (after job completion)
UPDATE customers
SET total_jobs_completed = total_jobs_completed + 1,
    total_spent = total_spent + $job_amount,
    updated_at = CURRENT_TIMESTAMP
WHERE id = $customer_id;

-- ============================================================================
-- 3. SERVICE CATALOG
-- ============================================================================

-- Add fixed-price service
INSERT INTO services (tenant_id, name, description, pricing_type, base_price, active)
VALUES (
  $tenant_id,
  'Standard Junk Removal',
  'Up to 1/4 truck load of general household junk',
  'fixed',
  299.00,
  true
);

-- Add volume-based service
INSERT INTO services (tenant_id, name, description, pricing_type, price_per_unit, unit_type, active)
VALUES (
  $tenant_id,
  'Volume-Based Removal',
  'Charged per cubic yard of junk removed',
  'volume_based',
  50.00,
  'cubic_yard',
  true
);

-- Get all active services for tenant
SELECT id, name, description, pricing_type, base_price, price_per_unit, unit_type
FROM services
WHERE tenant_id = $tenant_id
  AND active = true
  AND deleted_at IS NULL
ORDER BY name;

-- ============================================================================
-- 4. JOB BOOKING & MANAGEMENT
-- ============================================================================

-- Create new job booking
INSERT INTO jobs (
  tenant_id, customer_id, service_id, job_number,
  scheduled_date, scheduled_time_start, scheduled_time_end,
  service_address_line1, service_city, service_state, service_postal_code,
  latitude, longitude,
  items_description, special_instructions,
  status, priority, estimated_volume
)
VALUES (
  $tenant_id,
  $customer_id,
  $service_id,
  'JOB-2024-' || LPAD(NEXTVAL('job_number_seq')::TEXT, 5, '0'), -- Or generate in app
  '2024-03-15', -- Scheduled date
  '10:00:00',   -- Start time
  '12:00:00',   -- End time
  '123 Main St',
  'Springfield',
  'IL',
  '62701',
  39.7817,
  -89.6501,
  'Old furniture: couch, chair, coffee table',
  'Park in driveway, use side gate',
  'pending',
  'normal',
  8.5 -- Estimated cubic yards
)
RETURNING id, job_number, scheduled_date;

-- Get upcoming jobs (next 7 days)
SELECT 
  j.id,
  j.job_number,
  j.status,
  j.scheduled_date,
  j.scheduled_time_start,
  c.first_name || ' ' || c.last_name AS customer_name,
  c.phone AS customer_phone,
  j.service_address_line1,
  j.service_city,
  j.items_description
FROM jobs j
INNER JOIN customers c ON j.customer_id = c.id
WHERE j.tenant_id = $tenant_id
  AND j.deleted_at IS NULL
  AND j.scheduled_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
  AND j.status NOT IN ('completed', 'cancelled')
ORDER BY j.scheduled_date, j.scheduled_time_start;

-- Update job status
UPDATE jobs
SET status = $new_status,
    updated_at = CURRENT_TIMESTAMP
WHERE id = $job_id
  AND tenant_id = $tenant_id
RETURNING id, job_number, status;

-- Start a job (driver begins work)
UPDATE jobs
SET status = 'in_progress',
    actual_start_time = CURRENT_TIMESTAMP
WHERE id = $job_id
  AND tenant_id = $tenant_id;

-- Complete a job
UPDATE jobs
SET status = 'completed',
    actual_end_time = CURRENT_TIMESTAMP,
    actual_volume = $actual_volume,
    customer_rating = $rating,
    customer_feedback = $feedback
WHERE id = $job_id
  AND tenant_id = $tenant_id;

-- Search jobs by address or description
SELECT 
  j.id,
  j.job_number,
  j.status,
  j.scheduled_date,
  c.first_name || ' ' || c.last_name AS customer_name,
  j.service_address_line1,
  j.service_city
FROM jobs j
INNER JOIN customers c ON j.customer_id = c.id
WHERE j.tenant_id = $tenant_id
  AND j.deleted_at IS NULL
  AND to_tsvector('english', 
        coalesce(j.job_number, '') || ' ' ||
        coalesce(j.items_description, '') || ' ' ||
        coalesce(j.service_address_line1, '')
      ) @@ plainto_tsquery('english', $search_term)
ORDER BY j.scheduled_date DESC
LIMIT 50;

-- ============================================================================
-- 5. JOB ASSIGNMENT & DISPATCH
-- ============================================================================

-- Assign driver(s) to a job
INSERT INTO job_assignments (tenant_id, job_id, user_id, assigned_by, role_in_job, status)
VALUES 
  ($tenant_id, $job_id, $driver1_id, $dispatcher_id, 'lead', 'assigned'),
  ($tenant_id, $job_id, $driver2_id, $dispatcher_id, 'helper', 'assigned');

-- Update job status after assignment
UPDATE jobs
SET status = 'assigned'
WHERE id = $job_id
  AND tenant_id = $tenant_id;

-- Get driver's assigned jobs for today
SELECT 
  j.id,
  j.job_number,
  j.scheduled_time_start,
  j.scheduled_time_end,
  j.service_address_line1,
  j.service_city,
  j.service_state,
  j.latitude,
  j.longitude,
  c.first_name || ' ' || c.last_name AS customer_name,
  c.phone AS customer_phone,
  j.items_description,
  j.special_instructions,
  j.access_instructions,
  ja.role_in_job
FROM jobs j
INNER JOIN customers c ON j.customer_id = c.id
INNER JOIN job_assignments ja ON j.id = ja.job_id
WHERE j.tenant_id = $tenant_id
  AND ja.user_id = $driver_id
  AND j.scheduled_date = CURRENT_DATE
  AND j.status IN ('assigned', 'in_progress')
  AND j.deleted_at IS NULL
ORDER BY j.scheduled_time_start;

-- Driver accepts assignment
UPDATE job_assignments
SET status = 'accepted',
    accepted_at = CURRENT_TIMESTAMP
WHERE job_id = $job_id
  AND user_id = $driver_id
  AND tenant_id = $tenant_id;

-- Find available drivers (not overloaded)
SELECT 
  u.id,
  u.first_name || ' ' || u.last_name AS driver_name,
  u.phone,
  u.vehicle_info->>'type' AS vehicle_type,
  u.vehicle_info->>'capacity_cubic_yards' AS capacity,
  COUNT(ja.id) AS jobs_assigned_today
FROM users u
LEFT JOIN job_assignments ja ON u.id = ja.user_id 
  AND ja.assigned_at::date = CURRENT_DATE
  AND ja.status IN ('assigned', 'accepted')
WHERE u.tenant_id = $tenant_id
  AND u.role = 'driver'
  AND u.status = 'active'
  AND u.deleted_at IS NULL
GROUP BY u.id, u.first_name, u.last_name, u.phone, u.vehicle_info
HAVING COUNT(ja.id) < 5  -- Not overloaded (adjust threshold)
ORDER BY COUNT(ja.id), u.first_name;

-- ============================================================================
-- 6. ROUTE OPTIMIZATION
-- ============================================================================

-- Create daily route for driver
INSERT INTO routes (
  tenant_id, user_id, route_date, route_name,
  optimized_order, total_distance_miles, estimated_duration_minutes,
  status
)
VALUES (
  $tenant_id,
  $driver_id,
  '2024-03-15',
  'North Zone - Morning',
  '["job-uuid-1", "job-uuid-2", "job-uuid-3"]'::jsonb, -- Optimized sequence
  24.5,  -- Total miles
  180,   -- 3 hours estimated
  'planned'
);

-- Get jobs for route optimization (same day, same driver)
SELECT 
  j.id,
  j.job_number,
  j.scheduled_time_start,
  j.latitude,
  j.longitude,
  j.estimated_duration_minutes,
  j.service_address_line1,
  j.service_city,
  c.first_name || ' ' || c.last_name AS customer_name
FROM jobs j
INNER JOIN customers c ON j.customer_id = c.id
INNER JOIN job_assignments ja ON j.id = ja.job_id
WHERE j.tenant_id = $tenant_id
  AND ja.user_id = $driver_id
  AND j.scheduled_date = $route_date
  AND j.status = 'assigned'
  AND j.latitude IS NOT NULL
  AND j.longitude IS NOT NULL
ORDER BY j.scheduled_time_start;

-- ============================================================================
-- 7. INVOICING
-- ============================================================================

-- Generate invoice for completed job
INSERT INTO invoices (
  tenant_id, customer_id, job_id, invoice_number,
  subtotal, tax_amount, dump_fee, discount_amount, total_amount, amount_due,
  invoice_date, due_date, status
)
VALUES (
  $tenant_id,
  $customer_id,
  $job_id,
  'INV-2024-' || LPAD(NEXTVAL('invoice_number_seq')::TEXT, 5, '0'),
  500.00,   -- Subtotal
  40.00,    -- Tax (8%)
  25.00,    -- Dump fee
  0.00,     -- Discount
  565.00,   -- Total
  565.00,   -- Amount due
  CURRENT_DATE,
  CURRENT_DATE + INTERVAL '30 days', -- Due in 30 days
  'draft'
)
RETURNING id, invoice_number;

-- Add line items to invoice
INSERT INTO invoice_line_items (tenant_id, invoice_id, description, quantity, unit_price, total_price, line_order)
VALUES 
  ($tenant_id, $invoice_id, 'Junk Removal Service - 10 cubic yards', 10.00, 50.00, 500.00, 1),
  ($tenant_id, $invoice_id, 'Disposal Fee', 1.00, 25.00, 25.00, 2);

-- Send invoice (update status)
UPDATE invoices
SET status = 'sent'
WHERE id = $invoice_id
  AND tenant_id = $tenant_id;

-- Get all outstanding invoices
SELECT 
  i.id,
  i.invoice_number,
  i.invoice_date,
  i.due_date,
  i.total_amount,
  i.amount_paid,
  i.amount_due,
  c.first_name || ' ' || c.last_name AS customer_name,
  c.email AS customer_email,
  c.phone AS customer_phone,
  CASE 
    WHEN i.due_date < CURRENT_DATE THEN 'overdue'
    WHEN i.due_date <= CURRENT_DATE + INTERVAL '7 days' THEN 'due_soon'
    ELSE 'pending'
  END AS urgency,
  CURRENT_DATE - i.due_date AS days_overdue
FROM invoices i
INNER JOIN customers c ON i.customer_id = c.id
WHERE i.tenant_id = $tenant_id
  AND i.deleted_at IS NULL
  AND i.status IN ('sent', 'overdue')
  AND i.amount_due > 0
ORDER BY i.due_date;

-- Get invoice details with line items
SELECT 
  i.id,
  i.invoice_number,
  i.invoice_date,
  i.due_date,
  i.status,
  i.subtotal,
  i.tax_amount,
  i.dump_fee,
  i.discount_amount,
  i.total_amount,
  i.amount_paid,
  i.amount_due,
  c.first_name || ' ' || c.last_name AS customer_name,
  c.email,
  c.phone,
  c.address_line1,
  c.city,
  c.state,
  c.postal_code,
  j.job_number,
  j.scheduled_date,
  json_agg(
    json_build_object(
      'description', li.description,
      'quantity', li.quantity,
      'unit_price', li.unit_price,
      'total_price', li.total_price
    ) ORDER BY li.line_order
  ) AS line_items
FROM invoices i
INNER JOIN customers c ON i.customer_id = c.id
LEFT JOIN jobs j ON i.job_id = j.id
LEFT JOIN invoice_line_items li ON i.id = li.invoice_id
WHERE i.id = $invoice_id
  AND i.tenant_id = $tenant_id
GROUP BY i.id, c.first_name, c.last_name, c.email, c.phone, c.address_line1, c.city, c.state, c.postal_code, j.job_number, j.scheduled_date;

-- ============================================================================
-- 8. PAYMENTS
-- ============================================================================

-- Record a payment
INSERT INTO payments (
  tenant_id, invoice_id, customer_id,
  payment_method, payment_status, amount,
  transaction_id, processor, processor_response,
  reference_number, notes
)
VALUES (
  $tenant_id,
  $invoice_id,
  $customer_id,
  'credit_card',
  'completed',
  565.00,
  'ch_stripe_abc123',
  'stripe',
  '{"charge_id": "ch_stripe_abc123", "status": "succeeded", "card_last4": "4242"}'::jsonb,
  '****4242',
  'Paid via Stripe'
)
RETURNING id;

-- Update invoice after payment
UPDATE invoices
SET amount_paid = amount_paid + $payment_amount,
    amount_due = amount_due - $payment_amount,
    status = CASE 
      WHEN amount_due - $payment_amount <= 0 THEN 'paid'
      ELSE status
    END,
    paid_at = CASE 
      WHEN amount_due - $payment_amount <= 0 THEN CURRENT_TIMESTAMP
      ELSE paid_at
    END
WHERE id = $invoice_id
  AND tenant_id = $tenant_id;

-- Get payment history for customer
SELECT 
  p.id,
  p.payment_date,
  p.amount,
  p.payment_method,
  p.payment_status,
  p.reference_number,
  i.invoice_number,
  j.job_number
FROM payments p
INNER JOIN invoices i ON p.invoice_id = i.id
LEFT JOIN jobs j ON i.job_id = j.id
WHERE p.tenant_id = $tenant_id
  AND p.customer_id = $customer_id
ORDER BY p.payment_date DESC;

-- ============================================================================
-- 9. PHOTOS
-- ============================================================================

-- Upload before photo
INSERT INTO photos (
  tenant_id, job_id, uploaded_by, photo_type,
  file_path, file_url, thumbnail_url,
  file_size_bytes, mime_type, width, height,
  latitude, longitude, taken_at, caption, display_order
)
VALUES (
  $tenant_id,
  $job_id,
  $driver_id,
  'before',
  's3://bucket/photos/job-123-before-1.jpg',
  'https://cdn.example.com/photos/job-123-before-1.jpg',
  'https://cdn.example.com/photos/thumbs/job-123-before-1.jpg',
  245678,
  'image/jpeg',
  1920,
  1080,
  39.7817,
  -89.6501,
  CURRENT_TIMESTAMP,
  'Before removal - living room',
  1
)
RETURNING id, file_url;

-- Get all photos for a job
SELECT 
  id,
  photo_type,
  file_url,
  thumbnail_url,
  caption,
  taken_at,
  display_order
FROM photos
WHERE tenant_id = $tenant_id
  AND job_id = $job_id
  AND deleted_at IS NULL
ORDER BY photo_type, display_order, taken_at;

-- Get before/after photos for completed job
SELECT 
  photo_type,
  json_agg(
    json_build_object(
      'id', id,
      'url', file_url,
      'thumbnail', thumbnail_url,
      'caption', caption,
      'taken_at', taken_at
    ) ORDER BY display_order
  ) AS photos
FROM photos
WHERE tenant_id = $tenant_id
  AND job_id = $job_id
  AND deleted_at IS NULL
  AND photo_type IN ('before', 'after')
GROUP BY photo_type;

-- ============================================================================
-- 10. ANALYTICS & REPORTING
-- ============================================================================

-- Monthly revenue summary
SELECT 
  DATE_TRUNC('month', i.invoice_date) AS month,
  COUNT(DISTINCT i.id) AS total_invoices,
  COUNT(DISTINCT i.customer_id) AS unique_customers,
  SUM(i.total_amount) AS total_billed,
  SUM(i.amount_paid) AS total_collected,
  SUM(i.amount_due) AS outstanding,
  ROUND(AVG(i.total_amount), 2) AS avg_invoice_value
FROM invoices i
WHERE i.tenant_id = $tenant_id
  AND i.invoice_date >= DATE_TRUNC('year', CURRENT_DATE)
  AND i.deleted_at IS NULL
GROUP BY DATE_TRUNC('month', i.invoice_date)
ORDER BY month DESC;

-- Driver performance (last 30 days)
SELECT 
  u.id,
  u.first_name || ' ' || u.last_name AS driver_name,
  COUNT(DISTINCT j.id) AS total_jobs,
  COUNT(CASE WHEN j.status = 'completed' THEN 1 END) AS completed_jobs,
  COUNT(CASE WHEN j.status = 'cancelled' THEN 1 END) AS cancelled_jobs,
  ROUND(AVG(j.customer_rating), 2) AS avg_rating,
  SUM(EXTRACT(EPOCH FROM (j.actual_end_time - j.actual_start_time))/3600)::numeric(10,1) AS total_hours,
  COUNT(CASE 
    WHEN j.actual_end_time <= (j.scheduled_date + j.scheduled_time_end) THEN 1 
  END) AS on_time_completions
FROM users u
INNER JOIN job_assignments ja ON u.id = ja.user_id
INNER JOIN jobs j ON ja.job_id = j.id
WHERE u.tenant_id = $tenant_id
  AND u.role = 'driver'
  AND j.scheduled_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY u.id, u.first_name, u.last_name
ORDER BY avg_rating DESC, completed_jobs DESC;

-- Customer lifetime value (top 50)
SELECT 
  c.id,
  c.first_name || ' ' || c.last_name AS customer_name,
  c.email,
  c.phone,
  c.total_jobs_completed,
  c.total_spent,
  ROUND(c.rating, 2) AS avg_rating,
  MAX(j.scheduled_date) AS last_service_date,
  CURRENT_DATE - MAX(j.scheduled_date) AS days_since_last_service
FROM customers c
LEFT JOIN jobs j ON c.id = j.customer_id AND j.status = 'completed'
WHERE c.tenant_id = $tenant_id
  AND c.deleted_at IS NULL
GROUP BY c.id, c.first_name, c.last_name, c.email, c.phone, c.total_jobs_completed, c.total_spent, c.rating
ORDER BY c.total_spent DESC
LIMIT 50;

-- Jobs by status (dashboard summary)
SELECT 
  status,
  COUNT(*) AS count,
  SUM(CASE WHEN scheduled_date = CURRENT_DATE THEN 1 ELSE 0 END) AS count_today
FROM jobs
WHERE tenant_id = $tenant_id
  AND deleted_at IS NULL
  AND scheduled_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY status
ORDER BY 
  CASE status
    WHEN 'in_progress' THEN 1
    WHEN 'assigned' THEN 2
    WHEN 'confirmed' THEN 3
    WHEN 'pending' THEN 4
    WHEN 'completed' THEN 5
    WHEN 'cancelled' THEN 6
  END;

-- Daily schedule overview
SELECT 
  j.scheduled_date,
  COUNT(*) AS total_jobs,
  COUNT(DISTINCT ja.user_id) AS drivers_needed,
  SUM(j.estimated_duration_minutes) AS total_estimated_minutes,
  STRING_AGG(DISTINCT u.first_name, ', ') AS assigned_drivers
FROM jobs j
LEFT JOIN job_assignments ja ON j.id = ja.job_id
LEFT JOIN users u ON ja.user_id = u.id
WHERE j.tenant_id = $tenant_id
  AND j.deleted_at IS NULL
  AND j.scheduled_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '14 days'
  AND j.status NOT IN ('completed', 'cancelled')
GROUP BY j.scheduled_date
ORDER BY j.scheduled_date;

-- ============================================================================
-- 11. NOTIFICATIONS & ACTIVITY LOG
-- ============================================================================

-- Create notification for driver
INSERT INTO notifications (tenant_id, user_id, type, title, message, related_entity_type, related_entity_id)
VALUES (
  $tenant_id,
  $driver_id,
  'job_assigned',
  'New Job Assigned',
  'You have been assigned to job #JOB-2024-0001 scheduled for March 15 at 10:00 AM',
  'jobs',
  $job_id
);

-- Get unread notifications for user
SELECT 
  id,
  type,
  title,
  message,
  related_entity_type,
  related_entity_id,
  created_at
FROM notifications
WHERE user_id = $user_id
  AND read_at IS NULL
ORDER BY created_at DESC
LIMIT 20;

-- Mark notification as read
UPDATE notifications
SET read_at = CURRENT_TIMESTAMP
WHERE id = $notification_id
  AND user_id = $user_id;

-- Log activity (job status change)
INSERT INTO activity_log (
  tenant_id, user_id, entity_type, entity_id, action,
  old_values, new_values, ip_address
)
VALUES (
  $tenant_id,
  $user_id,
  'jobs',
  $job_id,
  'status_changed',
  '{"status": "pending"}'::jsonb,
  '{"status": "confirmed"}'::jsonb,
  $ip_address::inet
);

-- Get activity history for a job
SELECT 
  al.action,
  al.old_values,
  al.new_values,
  u.first_name || ' ' || u.last_name AS performed_by,
  al.created_at
FROM activity_log al
LEFT JOIN users u ON al.user_id = u.id
WHERE al.tenant_id = $tenant_id
  AND al.entity_type = 'jobs'
  AND al.entity_id = $job_id
ORDER BY al.created_at DESC;

-- ============================================================================
-- 12. SETTINGS & CONFIGURATION
-- ============================================================================

-- Get tenant settings
SELECT 
  business_hours,
  service_area_radius_miles,
  auto_accept_bookings,
  default_tax_rate,
  default_dump_fee,
  email_notifications_enabled,
  sms_notifications_enabled
FROM tenant_settings
WHERE tenant_id = $tenant_id;

-- Update business hours
UPDATE tenant_settings
SET business_hours = '{
  "monday": {"open": "08:00", "close": "18:00"},
  "tuesday": {"open": "08:00", "close": "18:00"},
  "wednesday": {"open": "08:00", "close": "18:00"},
  "thursday": {"open": "08:00", "close": "18:00"},
  "friday": {"open": "08:00", "close": "18:00"},
  "saturday": {"open": "09:00", "close": "15:00"},
  "sunday": {"closed": true}
}'::jsonb,
updated_at = CURRENT_TIMESTAMP
WHERE tenant_id = $tenant_id;

-- Update white-label branding
UPDATE tenants
SET branding_config = branding_config || '{
  "logo_url": "https://cdn.example.com/logos/acme.png",
  "primary_color": "#FF6B35",
  "company_name": "Acme Junk Removal"
}'::jsonb,
updated_at = CURRENT_TIMESTAMP
WHERE id = $tenant_id;

-- ============================================================================
-- END OF EXAMPLES
-- ============================================================================

-- Pro Tips:
-- 1. Always include tenant_id in WHERE clauses for multi-tenant isolation
-- 2. Use parameterized queries ($1, $2) to prevent SQL injection
-- 3. Add RETURNING clause to INSERT/UPDATE for immediate feedback
-- 4. Use transactions (BEGIN/COMMIT) for multi-step operations
-- 5. Index columns used frequently in WHERE, JOIN, ORDER BY clauses
-- 6. Use EXPLAIN ANALYZE to optimize slow queries
-- 7. Implement connection pooling in your application layer
-- 8. Regular VACUUM ANALYZE for optimal performance
