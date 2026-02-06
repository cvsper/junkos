-- ============================================================================
-- JunkOS Database Schema
-- ============================================================================
-- Purpose: Create all tables, indexes, triggers, and constraints
-- Usage: psql -U postgres -d junkos -f 02_schema.sql
-- ============================================================================

-- Ensure we're connected to the right database
\c junkos

BEGIN;

-- ============================================================================
-- TENANTS & ORGANIZATION
-- ============================================================================

CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    subscription_tier VARCHAR(50) NOT NULL DEFAULT 'basic',
    contact_email VARCHAR(255) NOT NULL,
    contact_phone VARCHAR(50),
    
    branding_config JSONB DEFAULT '{
        "logo_url": null,
        "primary_color": "#3B82F6",
        "secondary_color": "#10B981",
        "company_name": null,
        "custom_domain": null,
        "email_from_name": null,
        "email_from_address": null
    }'::jsonb,
    
    billing_address TEXT,
    billing_email VARCHAR(255),
    
    trial_ends_at TIMESTAMP WITH TIME ZONE,
    subscription_started_at TIMESTAMP WITH TIME ZONE,
    subscription_cancelled_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_tenants_slug ON tenants(slug) WHERE deleted_at IS NULL;
CREATE INDEX idx_tenants_status ON tenants(status) WHERE deleted_at IS NULL;

-- ============================================================================
-- USERS & AUTHENTICATION
-- ============================================================================

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone VARCHAR(50),
    
    role VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    
    driver_license_number VARCHAR(100),
    driver_license_expiry DATE,
    vehicle_info JSONB,
    
    email_verified_at TIMESTAMP WITH TIME ZONE,
    last_login_at TIMESTAMP WITH TIME ZONE,
    password_changed_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT unique_email_per_tenant UNIQUE (tenant_id, email)
);

CREATE INDEX idx_users_tenant_id ON users(tenant_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_email ON users(email) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_role ON users(tenant_id, role) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_status ON users(tenant_id, status) WHERE deleted_at IS NULL;

-- ============================================================================
-- CUSTOMERS
-- ============================================================================

CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50) NOT NULL,
    
    address_line1 VARCHAR(255),
    address_line2 VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(50),
    postal_code VARCHAR(20),
    country VARCHAR(2) DEFAULT 'US',
    
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    
    notes TEXT,
    rating DECIMAL(3, 2),
    total_jobs_completed INTEGER DEFAULT 0,
    total_spent DECIMAL(10, 2) DEFAULT 0.00,
    
    marketing_opt_in BOOLEAN DEFAULT false,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_customers_tenant_id ON customers(tenant_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_customers_phone ON customers(tenant_id, phone) WHERE deleted_at IS NULL;
CREATE INDEX idx_customers_email ON customers(tenant_id, email) WHERE deleted_at IS NULL;
CREATE INDEX idx_customers_location ON customers USING gist (ll_to_earth(latitude, longitude)) WHERE deleted_at IS NULL AND latitude IS NOT NULL;
CREATE INDEX idx_customers_search ON customers USING gin(
    to_tsvector('english', 
        coalesce(first_name, '') || ' ' || 
        coalesce(last_name, '') || ' ' || 
        coalesce(email, '') || ' ' || 
        coalesce(phone, '')
    )
) WHERE deleted_at IS NULL;

-- ============================================================================
-- SERVICE CATALOG & PRICING
-- ============================================================================

CREATE TABLE IF NOT EXISTS services (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    name VARCHAR(255) NOT NULL,
    description TEXT,
    
    pricing_type VARCHAR(50) NOT NULL,
    base_price DECIMAL(10, 2),
    price_per_unit DECIMAL(10, 2),
    unit_type VARCHAR(50),
    
    estimated_duration_minutes INTEGER,
    requires_dump_fee BOOLEAN DEFAULT false,
    active BOOLEAN DEFAULT true,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_services_tenant_id ON services(tenant_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_services_active ON services(tenant_id, active) WHERE deleted_at IS NULL;

-- ============================================================================
-- JOBS & BOOKINGS
-- ============================================================================

CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    service_id UUID REFERENCES services(id) ON DELETE RESTRICT,
    
    job_number VARCHAR(50) NOT NULL,
    
    scheduled_date DATE NOT NULL,
    scheduled_time_start TIME,
    scheduled_time_end TIME,
    estimated_duration_minutes INTEGER,
    
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    priority VARCHAR(50) DEFAULT 'normal',
    
    service_address_line1 VARCHAR(255) NOT NULL,
    service_address_line2 VARCHAR(255),
    service_city VARCHAR(100) NOT NULL,
    service_state VARCHAR(50) NOT NULL,
    service_postal_code VARCHAR(20) NOT NULL,
    service_country VARCHAR(2) DEFAULT 'US',
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    
    items_description TEXT,
    special_instructions TEXT,
    access_instructions TEXT,
    
    estimated_volume DECIMAL(10, 2),
    actual_volume DECIMAL(10, 2),
    
    actual_start_time TIMESTAMP WITH TIME ZONE,
    actual_end_time TIMESTAMP WITH TIME ZONE,
    
    customer_rating INTEGER,
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
CREATE INDEX idx_jobs_tenant_status_date ON jobs(tenant_id, status, scheduled_date) WHERE deleted_at IS NULL;
CREATE INDEX idx_jobs_search ON jobs USING gin(
    to_tsvector('english',
        coalesce(job_number, '') || ' ' ||
        coalesce(items_description, '') || ' ' ||
        coalesce(service_address_line1, '')
    )
) WHERE deleted_at IS NULL;

-- ============================================================================
-- JOB ASSIGNMENTS & DISPATCH
-- ============================================================================

CREATE TABLE IF NOT EXISTS job_assignments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    assigned_by UUID REFERENCES users(id),
    role_in_job VARCHAR(50) DEFAULT 'driver',
    
    status VARCHAR(50) DEFAULT 'assigned',
    
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
CREATE INDEX idx_job_assignments_tenant_user_date ON job_assignments(tenant_id, user_id, assigned_at DESC);

CREATE TABLE IF NOT EXISTS routes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    route_date DATE NOT NULL,
    route_name VARCHAR(255),
    
    status VARCHAR(50) DEFAULT 'planned',
    
    total_distance_miles DECIMAL(10, 2),
    estimated_duration_minutes INTEGER,
    optimized_order JSONB,
    
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_routes_tenant_id ON routes(tenant_id);
CREATE INDEX idx_routes_user_id ON routes(tenant_id, user_id);
CREATE INDEX idx_routes_date ON routes(tenant_id, route_date);

-- ============================================================================
-- PAYMENTS & INVOICING
-- ============================================================================

CREATE TABLE IF NOT EXISTS invoices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    job_id UUID REFERENCES jobs(id) ON DELETE RESTRICT,
    
    invoice_number VARCHAR(50) NOT NULL,
    
    status VARCHAR(50) NOT NULL DEFAULT 'draft',
    
    subtotal DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    tax_amount DECIMAL(10, 2) DEFAULT 0.00,
    dump_fee DECIMAL(10, 2) DEFAULT 0.00,
    discount_amount DECIMAL(10, 2) DEFAULT 0.00,
    total_amount DECIMAL(10, 2) NOT NULL,
    amount_paid DECIMAL(10, 2) DEFAULT 0.00,
    amount_due DECIMAL(10, 2) NOT NULL,
    
    invoice_date DATE NOT NULL,
    due_date DATE NOT NULL,
    paid_at TIMESTAMP WITH TIME ZONE,
    
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
CREATE INDEX idx_invoices_tenant_customer_status ON invoices(tenant_id, customer_id, status) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS invoice_line_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    
    description VARCHAR(255) NOT NULL,
    quantity DECIMAL(10, 2) NOT NULL DEFAULT 1,
    unit_price DECIMAL(10, 2) NOT NULL,
    total_price DECIMAL(10, 2) NOT NULL,
    
    line_order INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_invoice_line_items_invoice_id ON invoice_line_items(invoice_id);

CREATE TABLE IF NOT EXISTS payments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE RESTRICT,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    
    payment_method VARCHAR(50) NOT NULL,
    payment_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    
    amount DECIMAL(10, 2) NOT NULL,
    
    transaction_id VARCHAR(255),
    processor VARCHAR(50),
    processor_response JSONB,
    
    payment_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    reference_number VARCHAR(100),
    
    notes TEXT,
    
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
CREATE INDEX idx_payments_tenant_status_date ON payments(tenant_id, payment_status, payment_date DESC);

-- ============================================================================
-- PHOTOS & MEDIA
-- ============================================================================

CREATE TABLE IF NOT EXISTS photos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    uploaded_by UUID REFERENCES users(id),
    
    photo_type VARCHAR(50) NOT NULL,
    
    file_path VARCHAR(500) NOT NULL,
    file_url VARCHAR(500) NOT NULL,
    thumbnail_url VARCHAR(500),
    file_size_bytes BIGINT,
    mime_type VARCHAR(100),
    
    width INTEGER,
    height INTEGER,
    
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

-- ============================================================================
-- ACTIVITY LOG & AUDIT TRAIL
-- ============================================================================

CREATE TABLE IF NOT EXISTS activity_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    user_id UUID REFERENCES users(id),
    
    entity_type VARCHAR(100) NOT NULL,
    entity_id UUID NOT NULL,
    
    action VARCHAR(100) NOT NULL,
    
    old_values JSONB,
    new_values JSONB,
    
    ip_address INET,
    user_agent TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_activity_log_tenant_id ON activity_log(tenant_id);
CREATE INDEX idx_activity_log_user_id ON activity_log(user_id);
CREATE INDEX idx_activity_log_entity ON activity_log(tenant_id, entity_type, entity_id);
CREATE INDEX idx_activity_log_created_at ON activity_log(tenant_id, created_at DESC);

-- ============================================================================
-- NOTIFICATIONS
-- ============================================================================

CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    type VARCHAR(100) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    
    related_entity_type VARCHAR(100),
    related_entity_id UUID,
    
    read_at TIMESTAMP WITH TIME ZONE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    
    email_sent BOOLEAN DEFAULT false,
    sms_sent BOOLEAN DEFAULT false,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_notifications_tenant_id ON notifications(tenant_id);
CREATE INDEX idx_notifications_user_id ON notifications(user_id, created_at DESC);
CREATE INDEX idx_notifications_unread ON notifications(user_id, read_at) WHERE read_at IS NULL;

-- ============================================================================
-- SETTINGS & CONFIGURATION
-- ============================================================================

CREATE TABLE IF NOT EXISTS tenant_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    business_hours JSONB,
    service_area_radius_miles INTEGER DEFAULT 50,
    auto_accept_bookings BOOLEAN DEFAULT false,
    require_customer_signature BOOLEAN DEFAULT true,
    
    default_tax_rate DECIMAL(5, 4) DEFAULT 0.0000,
    default_dump_fee DECIMAL(10, 2) DEFAULT 0.00,
    
    email_notifications_enabled BOOLEAN DEFAULT true,
    sms_notifications_enabled BOOLEAN DEFAULT false,
    
    integrations JSONB DEFAULT '{}'::jsonb,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_settings_per_tenant UNIQUE (tenant_id)
);

-- ============================================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

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
-- ROW LEVEL SECURITY
-- ============================================================================

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

COMMIT;

-- Display success message
DO $$
BEGIN
    RAISE NOTICE '✓ All tables created successfully';
    RAISE NOTICE '✓ Indexes and triggers configured';
    RAISE NOTICE '✓ Row Level Security enabled';
    RAISE NOTICE '→ Next: Run 03_seed_data.sql to populate test data';
END $$;
