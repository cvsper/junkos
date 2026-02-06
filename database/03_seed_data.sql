-- ============================================================================
-- JunkOS Seed Data Script
-- ============================================================================
-- Purpose: Populate database with sample data for testing and development
-- Usage: psql -U postgres -d junkos -f 03_seed_data.sql
-- ============================================================================

\c junkos

BEGIN;

-- ============================================================================
-- SEED DATA: TENANTS (2 companies)
-- ============================================================================

INSERT INTO tenants (id, name, slug, status, subscription_tier, contact_email, contact_phone, branding_config, trial_ends_at, subscription_started_at) VALUES
(
    '550e8400-e29b-41d4-a716-446655440001',
    'QuickHaul Junk Removal',
    'quickhaul',
    'active',
    'pro',
    'admin@quickhaul.com',
    '+1-555-0101',
    '{
        "logo_url": "https://example.com/logos/quickhaul.png",
        "primary_color": "#2563EB",
        "secondary_color": "#16A34A",
        "company_name": "QuickHaul Junk Removal",
        "custom_domain": "quickhaul.junkos.com",
        "email_from_name": "QuickHaul Team",
        "email_from_address": "hello@quickhaul.com"
    }'::jsonb,
    NULL,
    '2024-01-15 00:00:00+00'
),
(
    '550e8400-e29b-41d4-a716-446655440002',
    'EcoJunk Solutions',
    'ecojunk',
    'trial',
    'basic',
    'contact@ecojunk.com',
    '+1-555-0202',
    '{
        "logo_url": "https://example.com/logos/ecojunk.png",
        "primary_color": "#059669",
        "secondary_color": "#F59E0B",
        "company_name": "EcoJunk Solutions",
        "custom_domain": null,
        "email_from_name": "EcoJunk",
        "email_from_address": "info@ecojunk.com"
    }'::jsonb,
    '2024-03-31 23:59:59+00',
    NULL
);

-- ============================================================================
-- SEED DATA: USERS (Admin, Dispatchers, Drivers)
-- ============================================================================

-- QuickHaul Users (Tenant 1)
INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name, phone, role, status, email_verified_at) VALUES
-- Admin
('650e8400-e29b-41d4-a716-446655440001', '550e8400-e29b-41d4-a716-446655440001', 'admin@quickhaul.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5gy9VcPGFGxJS', 'Sarah', 'Johnson', '+1-555-1001', 'admin', 'active', NOW()),
-- Dispatcher
('650e8400-e29b-41d4-a716-446655440002', '550e8400-e29b-41d4-a716-446655440001', 'dispatch@quickhaul.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5gy9VcPGFGxJS', 'Mike', 'Chen', '+1-555-1002', 'dispatcher', 'active', NOW()),
-- Drivers
('650e8400-e29b-41d4-a716-446655440003', '550e8400-e29b-41d4-a716-446655440001', 'james.driver@quickhaul.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5gy9VcPGFGxJS', 'James', 'Rodriguez', '+1-555-1003', 'driver', 'active', NOW()),
('650e8400-e29b-41d4-a716-446655440004', '550e8400-e29b-41d4-a716-446655440001', 'lisa.driver@quickhaul.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5gy9VcPGFGxJS', 'Lisa', 'Thompson', '+1-555-1004', 'driver', 'active', NOW());

-- Update driver-specific info
UPDATE users SET 
    driver_license_number = 'DL-12345678',
    driver_license_expiry = '2026-12-31',
    vehicle_info = '{
        "type": "box_truck",
        "make": "Ford",
        "model": "E-450",
        "year": 2022,
        "plate": "ABC-1234",
        "capacity": "16 cubic yards"
    }'::jsonb
WHERE id = '650e8400-e29b-41d4-a716-446655440003';

UPDATE users SET 
    driver_license_number = 'DL-87654321',
    driver_license_expiry = '2027-06-30',
    vehicle_info = '{
        "type": "pickup_truck",
        "make": "Chevrolet",
        "model": "Silverado 3500",
        "year": 2021,
        "plate": "XYZ-5678",
        "capacity": "8 cubic yards"
    }'::jsonb
WHERE id = '650e8400-e29b-41d4-a716-446655440004';

-- EcoJunk Users (Tenant 2)
INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name, phone, role, status, email_verified_at) VALUES
('650e8400-e29b-41d4-a716-446655440005', '550e8400-e29b-41d4-a716-446655440002', 'admin@ecojunk.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5gy9VcPGFGxJS', 'David', 'Park', '+1-555-2001', 'admin', 'active', NOW()),
('650e8400-e29b-41d4-a716-446655440006', '550e8400-e29b-41d4-a716-446655440002', 'tony.driver@ecojunk.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5gy9VcPGFGxJS', 'Tony', 'Martinez', '+1-555-2002', 'driver', 'active', NOW());

UPDATE users SET 
    driver_license_number = 'DL-99887766',
    driver_license_expiry = '2025-09-15',
    vehicle_info = '{
        "type": "box_truck",
        "make": "Isuzu",
        "model": "NPR",
        "year": 2020,
        "plate": "ECO-777",
        "capacity": "14 cubic yards"
    }'::jsonb
WHERE id = '650e8400-e29b-41d4-a716-446655440006';

-- ============================================================================
-- SEED DATA: SERVICES
-- ============================================================================

INSERT INTO services (id, tenant_id, name, description, pricing_type, base_price, price_per_unit, unit_type, estimated_duration_minutes, requires_dump_fee, active) VALUES
-- QuickHaul Services
('750e8400-e29b-41d4-a716-446655440001', '550e8400-e29b-41d4-a716-446655440001', 'Full Truck Load', 'Complete truck load - residential junk removal', 'fixed', 450.00, NULL, NULL, 120, true, true),
('750e8400-e29b-41d4-a716-446655440002', '550e8400-e29b-41d4-a716-446655440001', 'Half Truck Load', 'Partial truck load - smaller junk removal', 'fixed', 250.00, NULL, NULL, 90, true, true),
('750e8400-e29b-41d4-a716-446655440003', '550e8400-e29b-41d4-a716-446655440001', 'Volume-Based Removal', 'Charged per cubic yard of junk', 'volume_based', 50.00, 35.00, 'cubic_yard', 60, true, true),
('750e8400-e29b-41d4-a716-446655440004', '550e8400-e29b-41d4-a716-446655440001', 'Single Item Removal', 'Remove one or two large items (couch, fridge, etc)', 'fixed', 100.00, NULL, NULL, 45, false, true),

-- EcoJunk Services
('750e8400-e29b-41d4-a716-446655440005', '550e8400-e29b-41d4-a716-446655440002', 'Eco Full Load', 'Environmentally-friendly full truck removal', 'fixed', 500.00, NULL, NULL, 120, true, true),
('750e8400-e29b-41d4-a716-446655440006', '550e8400-e29b-41d4-a716-446655440002', 'Eco Partial Load', 'Green disposal - partial load', 'fixed', 275.00, NULL, NULL, 90, true, true);

-- ============================================================================
-- SEED DATA: CUSTOMERS (5 customers)
-- ============================================================================

INSERT INTO customers (id, tenant_id, first_name, last_name, email, phone, address_line1, city, state, postal_code, latitude, longitude, marketing_opt_in, total_jobs_completed) VALUES
-- QuickHaul Customers
('850e8400-e29b-41d4-a716-446655440001', '550e8400-e29b-41d4-a716-446655440001', 'Robert', 'Smith', 'robert.smith@email.com', '+1-555-3001', '123 Oak Street', 'Austin', 'TX', '78701', 30.2672, -97.7431, true, 2),
('850e8400-e29b-41d4-a716-446655440002', '550e8400-e29b-41d4-a716-446655440001', 'Jennifer', 'Davis', 'jennifer.davis@email.com', '+1-555-3002', '456 Maple Avenue', 'Austin', 'TX', '78702', 30.2656, -97.7208, true, 1),
('850e8400-e29b-41d4-a716-446655440003', '550e8400-e29b-41d4-a716-446655440001', 'Michael', 'Wilson', 'michael.w@email.com', '+1-555-3003', '789 Pine Road', 'Round Rock', 'TX', '78664', 30.5088, -97.6789, false, 0),
('850e8400-e29b-41d4-a716-446655440004', '550e8400-e29b-41d4-a716-446655440001', 'Emily', 'Brown', 'emily.brown@email.com', '+1-555-3004', '321 Elm Street', 'Cedar Park', 'TX', '78613', 30.5052, -97.8203, true, 1),

-- EcoJunk Customers
('850e8400-e29b-41d4-a716-446655440005', '550e8400-e29b-41d4-a716-446655440002', 'Christopher', 'Lee', 'chris.lee@email.com', '+1-555-4001', '555 Birch Lane', 'Portland', 'OR', '97201', 45.5152, -122.6784, true, 0);

-- ============================================================================
-- SEED DATA: JOBS (10 jobs with various statuses)
-- ============================================================================

INSERT INTO jobs (id, tenant_id, customer_id, service_id, job_number, scheduled_date, scheduled_time_start, scheduled_time_end, status, priority, service_address_line1, service_city, service_state, service_postal_code, latitude, longitude, items_description, special_instructions, estimated_volume, actual_volume, customer_rating) VALUES
-- QuickHaul Jobs
(
    '950e8400-e29b-41d4-a716-446655440001',
    '550e8400-e29b-41d4-a716-446655440001',
    '850e8400-e29b-41d4-a716-446655440001',
    '750e8400-e29b-41d4-a716-446655440001',
    'QH-2024-0001',
    '2024-02-10',
    '09:00',
    '11:00',
    'completed',
    'normal',
    '123 Oak Street',
    'Austin',
    'TX',
    '78701',
    30.2672,
    -97.7431,
    'Old furniture: sofa, dining table, 4 chairs, mattress',
    'Gate code: #1234. Park in driveway',
    12.5,
    14.0,
    5
),
(
    '950e8400-e29b-41d4-a716-446655440002',
    '550e8400-e29b-41d4-a716-446655440001',
    '850e8400-e29b-41d4-a716-446655440001',
    '750e8400-e29b-41d4-a716-446655440003',
    'QH-2024-0002',
    '2024-02-15',
    '10:00',
    '11:30',
    'completed',
    'normal',
    '123 Oak Street',
    'Austin',
    'TX',
    '78701',
    30.2672,
    -97.7431,
    'Garage cleanout - boxes, old tools, garden equipment',
    NULL,
    8.0,
    7.5,
    4
),
(
    '950e8400-e29b-41d4-a716-446655440003',
    '550e8400-e29b-41d4-a716-446655440001',
    '850e8400-e29b-41d4-a716-446655440002',
    '750e8400-e29b-41d4-a716-446655440002',
    'QH-2024-0003',
    '2024-02-20',
    '14:00',
    '16:00',
    'completed',
    'normal',
    '456 Maple Avenue',
    'Austin',
    'TX',
    '78702',
    30.2656,
    -97.7208,
    'Old appliances: refrigerator, washer, dryer',
    'Heavy items - need 2 people',
    6.0,
    5.5,
    5
),
(
    '950e8400-e29b-41d4-a716-446655440004',
    '550e8400-e29b-41d4-a716-446655440001',
    '850e8400-e29b-41d4-a716-446655440003',
    '750e8400-e29b-41d4-a716-446655440001',
    'QH-2024-0004',
    CURRENT_DATE,
    '09:00',
    '11:00',
    'in_progress',
    'high',
    '789 Pine Road',
    'Round Rock',
    'TX',
    '78664',
    30.5088,
    -97.6789,
    'Estate cleanout - full house',
    'Contact customer 30 min before arrival',
    15.0,
    NULL,
    NULL
),
(
    '950e8400-e29b-41d4-a716-446655440005',
    '550e8400-e29b-41d4-a716-446655440001',
    '850e8400-e29b-41d4-a716-446655440004',
    '750e8400-e29b-41d4-a716-446655440004',
    'QH-2024-0005',
    CURRENT_DATE,
    '13:00',
    '14:00',
    'assigned',
    'normal',
    '321 Elm Street',
    'Cedar Park',
    'TX',
    '78613',
    30.5052,
    -97.8203,
    'Single item: old couch',
    'Apartment building - 3rd floor, no elevator',
    2.0,
    NULL,
    NULL
),
(
    '950e8400-e29b-41d4-a716-446655440006',
    '550e8400-e29b-41d4-a716-446655440001',
    '850e8400-e29b-41d4-a716-446655440002',
    '750e8400-e29b-41d4-a716-446655440002',
    'QH-2024-0006',
    CURRENT_DATE + 1,
    '10:00',
    '12:00',
    'confirmed',
    'normal',
    '456 Maple Avenue',
    'Austin',
    'TX',
    '78702',
    30.2656,
    -97.7208,
    'Yard waste and old deck materials',
    'Backyard access via side gate',
    9.0,
    NULL,
    NULL
),
(
    '950e8400-e29b-41d4-a716-446655440007',
    '550e8400-e29b-41d4-a716-446655440001',
    '850e8400-e29b-41d4-a716-446655440001',
    '750e8400-e29b-41d4-a716-446655440003',
    'QH-2024-0007',
    CURRENT_DATE + 2,
    '09:00',
    '10:30',
    'pending',
    'low',
    '123 Oak Street',
    'Austin',
    'TX',
    '78701',
    30.2672,
    -97.7431,
    'Miscellaneous items from storage unit',
    NULL,
    4.0,
    NULL,
    NULL
),

-- EcoJunk Jobs
(
    '950e8400-e29b-41d4-a716-446655440008',
    '550e8400-e29b-41d4-a716-446655440002',
    '850e8400-e29b-41d4-a716-446655440005',
    '750e8400-e29b-41d4-a716-446655440005',
    'EJ-2024-0001',
    CURRENT_DATE,
    '08:00',
    '10:00',
    'assigned',
    'urgent',
    '555 Birch Lane',
    'Portland',
    'OR',
    '97201',
    45.5152,
    -122.6784,
    'Office cleanout - desks, chairs, electronics',
    'Business location - arrive before 8am',
    12.0,
    NULL,
    NULL
),
(
    '950e8400-e29b-41d4-a716-446655440009',
    '550e8400-e29b-41d4-a716-446655440002',
    '850e8400-e29b-41d4-a716-446655440005',
    '750e8400-e29b-41d4-a716-446655440006',
    'EJ-2024-0002',
    CURRENT_DATE + 1,
    '14:00',
    '16:00',
    'confirmed',
    'normal',
    '555 Birch Lane',
    'Portland',
    'OR',
    '97201',
    45.5152,
    -122.6784,
    'Garage cleanout',
    NULL,
    7.0,
    NULL,
    NULL
),
(
    '950e8400-e29b-41d4-a716-446655440010',
    '550e8400-e29b-41d4-a716-446655440002',
    '850e8400-e29b-41d4-a716-446655440005',
    '750e8400-e29b-41d4-a716-446655440005',
    'EJ-2024-0003',
    CURRENT_DATE + 7,
    '09:00',
    '11:00',
    'pending',
    'normal',
    '555 Birch Lane',
    'Portland',
    'OR',
    '97201',
    45.5152,
    -122.6784,
    'Construction debris removal',
    'Driveway access only',
    10.0,
    NULL,
    NULL
);

-- Update completed job timestamps
UPDATE jobs SET 
    actual_start_time = scheduled_date + scheduled_time_start - INTERVAL '5 minutes',
    actual_end_time = scheduled_date + scheduled_time_start + INTERVAL '2 hours'
WHERE status = 'completed';

-- ============================================================================
-- SEED DATA: JOB ASSIGNMENTS
-- ============================================================================

INSERT INTO job_assignments (tenant_id, job_id, user_id, assigned_by, role_in_job, status, accepted_at) VALUES
-- Completed jobs
('550e8400-e29b-41d4-a716-446655440001', '950e8400-e29b-41d4-a716-446655440001', '650e8400-e29b-41d4-a716-446655440003', '650e8400-e29b-41d4-a716-446655440002', 'driver', 'completed', NOW() - INTERVAL '5 days'),
('550e8400-e29b-41d4-a716-446655440001', '950e8400-e29b-41d4-a716-446655440002', '650e8400-e29b-41d4-a716-446655440003', '650e8400-e29b-41d4-a716-446655440002', 'driver', 'completed', NOW() - INTERVAL '3 days'),
('550e8400-e29b-41d4-a716-446655440001', '950e8400-e29b-41d4-a716-446655440003', '650e8400-e29b-41d4-a716-446655440004', '650e8400-e29b-41d4-a716-446655440002', 'driver', 'completed', NOW() - INTERVAL '2 days'),

-- In-progress / assigned jobs
('550e8400-e29b-41d4-a716-446655440001', '950e8400-e29b-41d4-a716-446655440004', '650e8400-e29b-41d4-a716-446655440003', '650e8400-e29b-41d4-a716-446655440002', 'driver', 'accepted', NOW() - INTERVAL '30 minutes'),
('550e8400-e29b-41d4-a716-446655440001', '950e8400-e29b-41d4-a716-446655440005', '650e8400-e29b-41d4-a716-446655440004', '650e8400-e29b-41d4-a716-446655440002', 'driver', 'assigned', NOW() - INTERVAL '1 hour'),

-- EcoJunk assignment
('550e8400-e29b-41d4-a716-446655440002', '950e8400-e29b-41d4-a716-446655440008', '650e8400-e29b-41d4-a716-446655440006', '650e8400-e29b-41d4-a716-446655440005', 'driver', 'accepted', NOW() - INTERVAL '1 hour');

-- ============================================================================
-- SEED DATA: TENANT SETTINGS
-- ============================================================================

INSERT INTO tenant_settings (tenant_id, business_hours, service_area_radius_miles, default_tax_rate, default_dump_fee, email_notifications_enabled) VALUES
(
    '550e8400-e29b-41d4-a716-446655440001',
    '{
        "monday": {"open": "08:00", "close": "18:00"},
        "tuesday": {"open": "08:00", "close": "18:00"},
        "wednesday": {"open": "08:00", "close": "18:00"},
        "thursday": {"open": "08:00", "close": "18:00"},
        "friday": {"open": "08:00", "close": "18:00"},
        "saturday": {"open": "09:00", "close": "15:00"},
        "sunday": {"closed": true}
    }'::jsonb,
    50,
    0.0825,
    45.00,
    true
),
(
    '550e8400-e29b-41d4-a716-446655440002',
    '{
        "monday": {"open": "07:00", "close": "19:00"},
        "tuesday": {"open": "07:00", "close": "19:00"},
        "wednesday": {"open": "07:00", "close": "19:00"},
        "thursday": {"open": "07:00", "close": "19:00"},
        "friday": {"open": "07:00", "close": "19:00"},
        "saturday": {"open": "08:00", "close": "14:00"},
        "sunday": {"closed": true}
    }'::jsonb,
    35,
    0.0900,
    50.00,
    true
);

-- Update customer stats based on completed jobs
UPDATE customers c
SET 
    total_jobs_completed = (
        SELECT COUNT(*)
        FROM jobs j
        WHERE j.customer_id = c.id AND j.status = 'completed' AND j.deleted_at IS NULL
    ),
    rating = (
        SELECT AVG(customer_rating)
        FROM jobs j
        WHERE j.customer_id = c.id AND j.customer_rating IS NOT NULL AND j.deleted_at IS NULL
    );

COMMIT;

-- Display success message
DO $$
DECLARE
    tenant_count INTEGER;
    user_count INTEGER;
    customer_count INTEGER;
    job_count INTEGER;
    service_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO tenant_count FROM tenants;
    SELECT COUNT(*) INTO user_count FROM users;
    SELECT COUNT(*) INTO customer_count FROM customers;
    SELECT COUNT(*) INTO job_count FROM jobs;
    SELECT COUNT(*) INTO service_count FROM services;
    
    RAISE NOTICE '✓ Seed data loaded successfully';
    RAISE NOTICE '  → % tenants', tenant_count;
    RAISE NOTICE '  → % users (admins, dispatchers, drivers)', user_count;
    RAISE NOTICE '  → % customers', customer_count;
    RAISE NOTICE '  → % services', service_count;
    RAISE NOTICE '  → % jobs', job_count;
    RAISE NOTICE '→ Next: Run 04_views.sql to create useful views';
END $$;
