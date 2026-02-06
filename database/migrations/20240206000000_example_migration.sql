-- Migration: Example Migration Template
-- Created: 2024-02-06 00:00:00
-- ============================================================================
-- This is an example migration file showing the proper format.
-- Delete this file before going to production.
-- ============================================================================

BEGIN;

-- ============================================================================
-- UP MIGRATION
-- ============================================================================

-- Example: Add a new table
CREATE TABLE IF NOT EXISTS customer_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    
    -- Preferences stored as JSONB
    preferences JSONB DEFAULT '{}'::jsonb,
    
    -- Communication preferences
    email_notifications BOOLEAN DEFAULT true,
    sms_notifications BOOLEAN DEFAULT false,
    
    -- Scheduling preferences
    preferred_time_of_day VARCHAR(20), -- morning, afternoon, evening
    preferred_days_of_week VARCHAR(50)[], -- array of days
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_preferences_per_customer UNIQUE (tenant_id, customer_id)
);

-- Add indexes
CREATE INDEX idx_customer_preferences_tenant ON customer_preferences(tenant_id);
CREATE INDEX idx_customer_preferences_customer ON customer_preferences(customer_id);

-- Add trigger for updated_at
CREATE TRIGGER update_customer_preferences_updated_at 
    BEFORE UPDATE ON customer_preferences
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Add comment
COMMENT ON TABLE customer_preferences IS 'Customer-specific preferences for scheduling and communication';

-- Example: Add a column to existing table
-- ALTER TABLE customers ADD COLUMN preferred_contact_method VARCHAR(20) DEFAULT 'phone';
-- CREATE INDEX idx_customers_contact_method ON customers(preferred_contact_method);

-- Example: Create a view
CREATE OR REPLACE VIEW v_customer_preferences AS
SELECT 
    c.id AS customer_id,
    c.tenant_id,
    c.first_name || ' ' || c.last_name AS customer_name,
    c.email,
    c.phone,
    cp.email_notifications,
    cp.sms_notifications,
    cp.preferred_time_of_day,
    cp.preferred_days_of_week,
    cp.preferences AS custom_preferences
FROM customers c
LEFT JOIN customer_preferences cp ON c.id = cp.customer_id
WHERE c.deleted_at IS NULL;

-- ============================================================================
-- ROLLBACK SQL (for rollback.py)
-- ============================================================================
-- To rollback this migration, the following SQL will be executed:

-- ROLLBACK: DROP VIEW IF EXISTS v_customer_preferences;
-- ROLLBACK: DROP TRIGGER IF EXISTS update_customer_preferences_updated_at ON customer_preferences;
-- ROLLBACK: DROP TABLE IF EXISTS customer_preferences;

COMMIT;

-- ============================================================================
-- NOTES
-- ============================================================================
-- This example demonstrates:
-- 1. Proper BEGIN/COMMIT transaction wrapping
-- 2. Table creation with constraints and indexes
-- 3. Trigger creation for updated_at
-- 4. View creation
-- 5. Rollback SQL as comments (executed in reverse order)
-- 6. Inline comments and documentation
--
-- Best Practices:
-- - Keep migrations atomic and focused
-- - Always include rollback SQL
-- - Test on development database first
-- - Document complex logic
-- - Use IF NOT EXISTS for idempotency
-- ============================================================================
