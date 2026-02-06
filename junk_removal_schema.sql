-- ============================================================================
-- Multi-Tenant Junk Removal SaaS - PostgreSQL Database Schema
-- ============================================================================
-- Design Decisions:
-- 1. Multi-tenancy: Every tenant-specific table includes tenant_id with composite indexes
-- 2. Soft deletes: Using deleted_at timestamps for audit trails
-- 3. UUID primary keys: Better for distributed systems and security
-- 4. Timestamps: created_at and updated_at on all tables
-- 5. JSONB: Used for flexible data (branding config, metadata)
-- ============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- TENANTS & ORGANIZATION
-- ============================================================================

-- Tenants: Each customer organization using the SaaS platform
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL, -- For subdomain (e.g., acme-junk.platform.com)
    status VARCHAR(50) NOT NULL DEFAULT 'active', -- active, suspended, trial, cancelled
    subscription_tier VARCHAR(50) NOT NULL DEFAULT 'basic', -- basic, pro, enterprise
    contact_email VARCHAR(255) NOT NULL,
    contact_phone VARCHAR(50),
    
    -- White-label branding stored as JSONB for flexibility
    branding_config JSONB DEFAULT '{
        "logo_url": null,
        "primary_color": "#3B82F6",
        "secondary_color": "#10B981",
        "company_name": null,
        "custom_domain": null,
        "email_from_name": null,
        "email_from_address": null
    }'::jsonb,
    
    -- Billing
    billing_address TEXT,
    billing_email VARCHAR(255),
    
    -- Subscription tracking
    trial_ends_at TIMESTAMP WITH TIME ZONE,
    subscription_started_at TIMESTAMP WITH TIME ZONE,
    subscription_cancelled_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_tenants_slug ON tenants(slug) WHERE deleted_at IS NULL;
CREATE INDEX idx_tenants_status ON tenants(status) WHERE deleted_at IS NULL;

COMMENT ON TABLE tenants IS 'Organizations using the platform (multi-tenant isolation)';
COMMENT ON COLUMN tenants.branding_config IS 'White-label branding settings in JSONB format';

-- ============================================================================
-- USERS & AUTHENTICATION
-- ============================================================================

-- Users: People who access the system (admins, dispatchers, drivers)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone VARCHAR(50),
    
    role VARCHAR(50) NOT NULL, -- admin, dispatcher, driver
    status VARCHAR(50) NOT NULL DEFAULT 'active', -- active, inactive, suspended
    
    -- Driver-specific fields
    driver_license_number VARCHAR(100),
    driver_license_expiry DATE,
    vehicle_info JSONB, -- {type, make, model, year, plate, capacity}
    
    -- Authentication & security
    email_verified_at TIMESTAMP WITH TIME ZONE,
    last_login_at TIMESTAMP WITH TIME ZONE,
    password_changed_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE,
    
    -- Multi-tenant constraint: email unique per tenant
    CONSTRAINT unique_email_per_tenant UNIQUE (tenant_id, email)
);

CREATE INDEX idx_users_tenant_id ON users(tenant_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_email ON users(email) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_role ON users(tenant_id, role) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_status ON users(tenant_id, status) WHERE deleted_at IS NULL;

COMMENT ON TABLE users IS 'Platform users with role-based access (admin, dispatcher, driver)';
COMMENT ON COLUMN users.role IS 'admin: full access, dispatcher: schedule/assign, driver: view assigned jobs';

-- ============================================================================
-- CUSTOMERS
-- ============================================================================

-- Customers: End customers who book junk removal services
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50) NOT NULL,
    
    -- Address information
    address_line1 VARCHAR(255),
    address_line2 VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(50),
    postal_code VARCHAR(20),
    country VARCHAR(2) DEFAULT 'US',
    
    -- Geolocation for routing (populated via geocoding)
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    
    -- Customer relationship management
    notes TEXT,
    rating DECIMAL(3, 2), -- Average rating from completed jobs
    total_jobs_completed INTEGER DEFAULT 0,
    total_spent DECIMAL(10, 2) DEFAULT 0.00,
    
    -- Marketing preferences
    marketing_opt_in BOOLEAN DEFAULT false,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_customers_tenant_id ON customers(tenant_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_customers_phone ON customers(tenant_id, phone) WHERE deleted_at IS NULL;
CREATE INDEX idx_customers_email ON customers(tenant_id, email) WHERE deleted_at IS NULL;
CREATE INDEX idx_customers_location ON customers USING gist (ll_to_earth(latitude, longitude)) WHERE deleted_at IS NULL AND latitude IS NOT NULL;

COMMENT ON TABLE customers IS 'End customers who book junk removal services';
COMMENT ON COLUMN customers.latitude IS 'Used for route optimization and distance calculations';

-- ============================================================================
-- SERVICE CATALOG & PRICING
-- ============================================================================

-- Services: Types of junk removal services offered
CREATE TABLE services (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    name VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- Pricing
    pricing_type VARCHAR(50) NOT NULL, -- fixed, volume_based, hourly, custom
    base_price DECIMAL(10, 2),
    price_per_unit DECIMAL(10, 2), -- Per cubic yard, per hour, etc.
    unit_type VARCHAR(50), -- cubic_yard, hour, item, etc.
    
    -- Service settings
    estimated_duration_minutes INTEGER, -- Average time to complete
    requires_dump_fee BOOLEAN DEFAULT false,
    active BOOLEAN DEFAULT true,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_services_tenant_id ON services(tenant_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_services_active ON services(tenant_id, active) WHERE deleted_at IS NULL;

COMMENT ON TABLE services IS 'Service catalog - types of junk removal offered';
COMMENT ON COLUMN services.pricing_type IS 'Flexible pricing models: fixed, volume-based, hourly, or custom quote';

-- ============================================================================
-- JOBS & BOOKINGS
-- ============================================================================

-- Jobs: Core entity representing a junk removal booking
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    service_id UUID REFERENCES services(id) ON DELETE RESTRICT,
    
    -- Job identification
    job_number VARCHAR(50) NOT NULL, -- Human-readable job number (e.g., JOB-2024-0001)
    
    -- Scheduling
    scheduled_date DATE NOT NULL,
    scheduled_time_start TIME,
    scheduled_time_end TIME,
    estimated_duration_minutes INTEGER,
    
    -- Job details
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- pending, confirmed, assigned, in_progress, completed, cancelled
    priority VARCHAR(50) DEFAULT 'normal', -- low, normal, high, urgent
    
    -- Location (can differ from customer's default address)
    service_address_line1 VARCHAR(255) NOT NULL,
    service_address_line2 VARCHAR(255),
    service_city VARCHAR(100) NOT NULL,
    service_state VARCHAR(50) NOT NULL,
    service_postal_code VARCHAR(20) NOT NULL,
    service_country VARCHAR(2) DEFAULT 'US',
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    
    -- Job specifics
    items_description TEXT, -- What needs to be removed
    special_instructions TEXT,
    access_instructions TEXT, -- Gate codes, parking, etc.
    
    -- Volume/quantity (filled during or after job)
    estimated_volume DECIMAL(10, 2), -- In cubic yards
    actual_volume DECIMAL(10, 2),
    
    -- Timing tracking
    actual_start_time TIMESTAMP WITH TIME ZONE,
    actual_end_time TIMESTAMP WITH TIME ZONE,
    
    -- Customer feedback
    customer_rating INTEGER, -- 1-5 stars
    customer_feedback TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT unique_job_number_per_tenant UNIQUE (tenant_id, job_number)
);

CREATE INDEX idx_jobs_tenant_id ON jobs(tenant_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_jobs_customer_id ON jobs(tenant_id, customer_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_jobs_status ON jobs(tenant_id, status) WHERE deleted_at IS NULL;
CREATE INDEX idx_jobs_scheduled_date ON jobs(tenant_id, scheduled_date) WHERE deleted_at IS NULL;
CREATE INDEX idx_jobs_location ON jobs USING gist (ll_to_earth(latitude, longitude)) WHERE deleted_at IS NULL AND latitude IS NOT NULL;
CREATE INDEX idx_jobs_created_at ON jobs(tenant_id, created_at DESC) WHERE deleted_at IS NULL;

COMMENT ON TABLE jobs IS 'Core booking/job entity - represents each junk removal service request';
COMMENT ON COLUMN jobs.status IS 'Workflow: pending → confirmed → assigned → in_progress → completed/cancelled';

-- ============================================================================
-- JOB ASSIGNMENTS & DISPATCH
-- ============================================================================

-- Job Assignments: Links jobs to drivers (supports multiple drivers per job)
CREATE TABLE job_assignments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, -- Driver assigned
    
    assigned_by UUID REFERENCES users(id), -- Dispatcher who made assignment
    role_in_job VARCHAR(50) DEFAULT 'driver', -- driver, helper, lead
    
    status VARCHAR(50) DEFAULT 'assigned', -- assigned, accepted, rejected, completed
    
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    accepted_at TIMESTAMP WITH TIME ZONE,
    rejected_at TIMESTAMP WITH TIME ZONE,
    rejection_reason TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_job_assignments_tenant_id ON job_assignments(tenant_id);
CREATE INDEX idx_job_assignments_job_id ON job_assignments(job_id);
CREATE INDEX idx_job_assignments_user_id ON job_assignments(tenant_id, user_id);
CREATE INDEX idx_job_assignments_status ON job_assignments(tenant_id, status);
CREATE INDEX idx_job_assignments_assigned_at ON job_assignments(tenant_id, assigned_at DESC);

COMMENT ON TABLE job_assignments IS 'Many-to-many relationship between jobs and drivers';
COMMENT ON COLUMN job_assignments.role_in_job IS 'Supports teams: lead driver vs helpers';

-- Routes: Daily route optimization for drivers
CREATE TABLE routes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, -- Driver
    
    route_date DATE NOT NULL,
    route_name VARCHAR(255), -- E.g., "North Zone - Morning"
    
    status VARCHAR(50) DEFAULT 'planned', -- planned, in_progress, completed
    
    -- Route optimization data
    total_distance_miles DECIMAL(10, 2),
    estimated_duration_minutes INTEGER,
    optimized_order JSONB, -- Array of job_ids in optimized order
    
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_routes_tenant_id ON routes(tenant_id);
CREATE INDEX idx_routes_user_id ON routes(tenant_id, user_id);
CREATE INDEX idx_routes_date ON routes(tenant_id, route_date);

COMMENT ON TABLE routes IS 'Daily optimized routes for drivers';
COMMENT ON COLUMN routes.optimized_order IS 'Stores job IDs in optimized sequence';

-- ============================================================================
-- PAYMENTS & INVOICING
-- ============================================================================

-- Invoices: Bills sent to customers
CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    job_id UUID REFERENCES jobs(id) ON DELETE RESTRICT,
    
    invoice_number VARCHAR(50) NOT NULL,
    
    status VARCHAR(50) NOT NULL DEFAULT 'draft', -- draft, sent, paid, overdue, cancelled
    
    -- Amounts
    subtotal DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    tax_amount DECIMAL(10, 2) DEFAULT 0.00,
    dump_fee DECIMAL(10, 2) DEFAULT 0.00,
    discount_amount DECIMAL(10, 2) DEFAULT 0.00,
    total_amount DECIMAL(10, 2) NOT NULL,
    amount_paid DECIMAL(10, 2) DEFAULT 0.00,
    amount_due DECIMAL(10, 2) NOT NULL,
    
    -- Dates
    invoice_date DATE NOT NULL,
    due_date DATE NOT NULL,
    paid_at TIMESTAMP WITH TIME ZONE,
    
    -- Notes
    notes TEXT,
    internal_notes TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT unique_invoice_number_per_tenant UNIQUE (tenant_id, invoice_number)
);

CREATE INDEX idx_invoices_tenant_id ON invoices(tenant_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_invoices_customer_id ON invoices(tenant_id, customer_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_invoices_job_id ON invoices(job_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_invoices_status ON invoices(tenant_id, status) WHERE deleted_at IS NULL;
CREATE INDEX idx_invoices_due_date ON invoices(tenant_id, due_date) WHERE deleted_at IS NULL;

COMMENT ON TABLE invoices IS 'Bills sent to customers for services rendered';

-- Invoice Line Items: Detailed breakdown of charges
CREATE TABLE invoice_line_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    
    description VARCHAR(255) NOT NULL,
    quantity DECIMAL(10, 2) NOT NULL DEFAULT 1,
    unit_price DECIMAL(10, 2) NOT NULL,
    total_price DECIMAL(10, 2) NOT NULL,
    
    line_order INTEGER DEFAULT 0, -- For display ordering
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_invoice_line_items_invoice_id ON invoice_line_items(invoice_id);

COMMENT ON TABLE invoice_line_items IS 'Itemized charges on invoices';

-- Payments: Payment transactions
CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE RESTRICT,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    
    payment_method VARCHAR(50) NOT NULL, -- cash, check, credit_card, ach, stripe, square, etc.
    payment_status VARCHAR(50) NOT NULL DEFAULT 'pending', -- pending, completed, failed, refunded
    
    amount DECIMAL(10, 2) NOT NULL,
    
    -- Payment processor details
    transaction_id VARCHAR(255), -- External payment processor transaction ID
    processor VARCHAR(50), -- stripe, square, paypal, etc.
    processor_response JSONB, -- Raw response from payment processor
    
    -- Payment details
    payment_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    reference_number VARCHAR(100), -- Check number, last 4 of card, etc.
    
    notes TEXT,
    
    -- Refunds
    refunded_at TIMESTAMP WITH TIME ZONE,
    refund_amount DECIMAL(10, 2),
    refund_reason TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_payments_tenant_id ON payments(tenant_id);
CREATE INDEX idx_payments_invoice_id ON payments(invoice_id);
CREATE INDEX idx_payments_customer_id ON payments(customer_id);
CREATE INDEX idx_payments_status ON payments(tenant_id, payment_status);
CREATE INDEX idx_payments_date ON payments(tenant_id, payment_date DESC);

COMMENT ON TABLE payments IS 'Payment transactions linked to invoices';
COMMENT ON COLUMN payments.processor_response IS 'Stores full API response for audit/debugging';

-- ============================================================================
-- PHOTOS & MEDIA
-- ============================================================================

-- Photos: Before/after photos for jobs
CREATE TABLE photos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    uploaded_by UUID REFERENCES users(id), -- Driver who took the photo
    
    photo_type VARCHAR(50) NOT NULL, -- before, after, during, damage, signature
    
    -- File storage
    file_path VARCHAR(500) NOT NULL, -- S3/storage path
    file_url VARCHAR(500) NOT NULL, -- Public/signed URL
    thumbnail_url VARCHAR(500),
    file_size_bytes BIGINT,
    mime_type VARCHAR(100),
    
    -- Image metadata
    width INTEGER,
    height INTEGER,
    
    -- Geolocation & timestamp (from EXIF or manual)
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    taken_at TIMESTAMP WITH TIME ZONE,
    
    caption TEXT,
    display_order INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_photos_tenant_id ON photos(tenant_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_photos_job_id ON photos(job_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_photos_type ON photos(tenant_id, photo_type) WHERE deleted_at IS NULL;
CREATE INDEX idx_photos_uploaded_by ON photos(uploaded_by) WHERE deleted_at IS NULL;

COMMENT ON TABLE photos IS 'Photos uploaded during/after jobs (before/after, damage documentation)';
COMMENT ON COLUMN photos.photo_type IS 'Categorizes photos for easy filtering and display';

-- ============================================================================
-- ACTIVITY LOG & AUDIT TRAIL
-- ============================================================================

-- Activity Log: Comprehensive audit trail
CREATE TABLE activity_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    user_id UUID REFERENCES users(id), -- Who performed the action (null for system actions)
    
    entity_type VARCHAR(100) NOT NULL, -- jobs, customers, invoices, etc.
    entity_id UUID NOT NULL, -- ID of affected record
    
    action VARCHAR(100) NOT NULL, -- created, updated, deleted, status_changed, assigned, etc.
    
    -- Change tracking
    old_values JSONB, -- Previous state
    new_values JSONB, -- New state
    
    ip_address INET,
    user_agent TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_activity_log_tenant_id ON activity_log(tenant_id);
CREATE INDEX idx_activity_log_user_id ON activity_log(user_id);
CREATE INDEX idx_activity_log_entity ON activity_log(tenant_id, entity_type, entity_id);
CREATE INDEX idx_activity_log_created_at ON activity_log(tenant_id, created_at DESC);

COMMENT ON TABLE activity_log IS 'Comprehensive audit trail for all important actions';
COMMENT ON COLUMN activity_log.old_values IS 'JSON snapshot of record before change';

-- ============================================================================
-- NOTIFICATIONS
-- ============================================================================

-- Notifications: In-app notifications for users
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    type VARCHAR(100) NOT NULL, -- job_assigned, job_updated, payment_received, etc.
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    
    -- Related entities
    related_entity_type VARCHAR(100), -- jobs, payments, etc.
    related_entity_id UUID,
    
    -- Delivery
    read_at TIMESTAMP WITH TIME ZONE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    
    -- Optional: Email/SMS tracking
    email_sent BOOLEAN DEFAULT false,
    sms_sent BOOLEAN DEFAULT false,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_notifications_tenant_id ON notifications(tenant_id);
CREATE INDEX idx_notifications_user_id ON notifications(user_id, created_at DESC);
CREATE INDEX idx_notifications_unread ON notifications(user_id, read_at) WHERE read_at IS NULL;

COMMENT ON TABLE notifications IS 'In-app notifications for users';

-- ============================================================================
-- SETTINGS & CONFIGURATION
-- ============================================================================

-- Tenant Settings: Configurable settings per tenant
CREATE TABLE tenant_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Business settings
    business_hours JSONB, -- {monday: {open: "08:00", close: "18:00"}, ...}
    service_area_radius_miles INTEGER DEFAULT 50,
    auto_accept_bookings BOOLEAN DEFAULT false,
    require_customer_signature BOOLEAN DEFAULT true,
    
    -- Pricing & fees
    default_tax_rate DECIMAL(5, 4) DEFAULT 0.0000,
    default_dump_fee DECIMAL(10, 2) DEFAULT 0.00,
    
    -- Notifications
    email_notifications_enabled BOOLEAN DEFAULT true,
    sms_notifications_enabled BOOLEAN DEFAULT false,
    
    -- Integrations
    integrations JSONB DEFAULT '{}'::jsonb, -- API keys, webhooks, etc.
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_settings_per_tenant UNIQUE (tenant_id)
);

COMMENT ON TABLE tenant_settings IS 'Configurable operational settings per tenant';
COMMENT ON COLUMN tenant_settings.integrations IS 'Stores API keys for Stripe, Twilio, Google Maps, etc.';

-- ============================================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================================

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at trigger to all relevant tables
CREATE TRIGGER update_tenants_updated_at BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_customers_updated_at BEFORE UPDATE ON customers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_services_updated_at BEFORE UPDATE ON services
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_jobs_updated_at BEFORE UPDATE ON jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_job_assignments_updated_at BEFORE UPDATE ON job_assignments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_routes_updated_at BEFORE UPDATE ON routes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_invoices_updated_at BEFORE UPDATE ON invoices
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_payments_updated_at BEFORE UPDATE ON payments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tenant_settings_updated_at BEFORE UPDATE ON tenant_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- SAMPLE VIEWS (Optional but useful)
-- ============================================================================

-- View: Active jobs with customer and assignment details
CREATE VIEW v_active_jobs AS
SELECT 
    j.id,
    j.tenant_id,
    j.job_number,
    j.status,
    j.scheduled_date,
    j.scheduled_time_start,
    c.first_name || ' ' || c.last_name AS customer_name,
    c.phone AS customer_phone,
    j.service_address_line1,
    j.service_city,
    j.service_state,
    STRING_AGG(u.first_name || ' ' || u.last_name, ', ') AS assigned_drivers,
    j.created_at
FROM jobs j
INNER JOIN customers c ON j.customer_id = c.id
LEFT JOIN job_assignments ja ON j.id = ja.job_id AND ja.status = 'assigned'
LEFT JOIN users u ON ja.user_id = u.id
WHERE j.deleted_at IS NULL
    AND j.status NOT IN ('completed', 'cancelled')
GROUP BY j.id, c.first_name, c.last_name, c.phone;

COMMENT ON VIEW v_active_jobs IS 'Quick view of active jobs with customer and driver info';

-- View: Outstanding invoices
CREATE VIEW v_outstanding_invoices AS
SELECT 
    i.id,
    i.tenant_id,
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
    END AS urgency
FROM invoices i
INNER JOIN customers c ON i.customer_id = c.id
WHERE i.deleted_at IS NULL
    AND i.status IN ('sent', 'overdue')
    AND i.amount_due > 0;

COMMENT ON VIEW v_outstanding_invoices IS 'All unpaid invoices with urgency flag';

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) Setup
-- ============================================================================

-- Enable RLS on all tenant-scoped tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE services ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE routes ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice_line_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE photos ENABLE ROW LEVEL SECURITY;
ALTER TABLE activity_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_settings ENABLE ROW LEVEL SECURITY;

-- Example RLS Policy (customize based on your auth system)
-- This assumes you have a current_tenant_id() function that returns the authenticated user's tenant
CREATE POLICY tenant_isolation_policy ON users
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

-- Note: You would create similar policies for all tenant-scoped tables
-- The current_setting approach works well with application-level tenant context

COMMENT ON POLICY tenant_isolation_policy ON users IS 
    'Ensures users can only access data within their tenant using RLS';

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Additional composite indexes for common queries
CREATE INDEX idx_jobs_tenant_status_date ON jobs(tenant_id, status, scheduled_date) 
    WHERE deleted_at IS NULL;

CREATE INDEX idx_job_assignments_tenant_user_date ON job_assignments(tenant_id, user_id, assigned_at DESC);

CREATE INDEX idx_invoices_tenant_customer_status ON invoices(tenant_id, customer_id, status) 
    WHERE deleted_at IS NULL;

CREATE INDEX idx_payments_tenant_status_date ON payments(tenant_id, payment_status, payment_date DESC);

-- Full-text search indexes for common search queries
CREATE INDEX idx_customers_search ON customers USING gin(
    to_tsvector('english', 
        coalesce(first_name, '') || ' ' || 
        coalesce(last_name, '') || ' ' || 
        coalesce(email, '') || ' ' || 
        coalesce(phone, '')
    )
) WHERE deleted_at IS NULL;

CREATE INDEX idx_jobs_search ON jobs USING gin(
    to_tsvector('english',
        coalesce(job_number, '') || ' ' ||
        coalesce(items_description, '') || ' ' ||
        coalesce(service_address_line1, '')
    )
) WHERE deleted_at IS NULL;

-- ============================================================================
-- SUMMARY
-- ============================================================================

-- This schema provides:
-- 
-- 1. ✅ Multi-tenancy: tenant_id on all relevant tables with proper indexing
-- 2. ✅ Customer bookings: customers → jobs with full address and scheduling
-- 3. ✅ Job management: Complete workflow tracking (pending → completed)
-- 4. ✅ Dispatch/routing: job_assignments + routes with optimization support
-- 5. ✅ Payments: invoices, line items, payments with processor integration
-- 6. ✅ White-label branding: JSONB config in tenants table
-- 7. ✅ User roles: admin/dispatcher/driver with role-based access
-- 8. ✅ Photo uploads: Before/after photos linked to jobs
-- 9. ✅ Audit trail: activity_log for comprehensive tracking
-- 10. ✅ Performance: Strategic indexes including spatial, full-text search
-- 11. ✅ Security: Row Level Security (RLS) policies for tenant isolation
-- 12. ✅ Soft deletes: deleted_at for data retention and recovery
-- 
-- Next steps:
-- - Implement application-level tenant context (current_tenant_id function)
-- - Set up S3/storage for photos
-- - Integrate payment processors (Stripe, Square)
-- - Implement geocoding for addresses
-- - Build route optimization algorithm using latitude/longitude
-- - Set up automated invoice generation
-- - Create notification/email templates
